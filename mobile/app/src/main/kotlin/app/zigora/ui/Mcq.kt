package app.zigora.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.zigora.data.Area
import app.zigora.data.McqHist
import app.zigora.data.McqHome
import app.zigora.data.McqSet
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject

/** MCQ practice, as on the web: two ways in (Practice across a course's topics, and Per topic from a topic's page) on one engine. The server keeps the
 *  answers until a set is submitted, counts sets (Lite one every 48 hours, others four a day) and gives back a set still open instead of counting another. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun McqHomeScreen(topic: Int, back: () -> Unit, play: (Int) -> Unit) {
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast()
    var tick by remember { mutableIntStateOf(0) }
    val home = rememberLoad("mcq-home", tick) { get("/mcq/home", McqHome.serializer()) }
    val hist = rememberLoad("mcq-hist", tick) { get("/mcq/attempts?limit=10", McqHist.serializer()) }
    var perTopic by remember { mutableStateOf(topic > 0) }
    var course by remember { mutableIntStateOf(0) }
    var tid by remember { mutableIntStateOf(topic) }
    var size by remember { mutableIntStateOf(10) }
    var busy by remember { mutableStateOf("") }
    var ask by remember { mutableStateOf<Ask?>(null) }
    LaunchedEffect(home.state) { (home.state as? Load.Ok)?.value?.let { h -> if (topic > 0 && course == 0) h.courses.firstOrNull { c -> c.topics.any { it.id == topic } }?.let { course = it.id } } }
    Page(tl("MCQ practice"), tl("Questions from your courses, with answers explained"), back) {
        Loaded(home) { h ->
            val q = h.quota
            if (q.tier != "staff") Quiet(when {
                q.tier == "lite" && (q.left ?: 0) > 0 -> tl("Lite: one free MCQ set every 48 hours. Your set is ready.")
                q.tier == "lite" -> tl("Lite: one free MCQ set every 48 hours. Your next set is ready {when}.", "when" to stamp(q.next_at.orEmpty()))
                (q.left ?: 0) > 0 -> tl("{left} of {limit} MCQ sets left today.", "left" to q.left, "limit" to q.limit)
                else -> tl("You have used today's {limit} MCQ sets. The next is ready {when}.", "limit" to q.limit, "when" to stamp(q.next_at.orEmpty()))
            })
            h.open?.let { o ->
                Panel {
                    Text(tl("A set is waiting for you"), style = MaterialTheme.typography.titleMedium)
                    Quiet(tl("{answered} of {total} answered. Coming back to it doesn't use another set.", "answered" to o.answered, "total" to o.total))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                        Button(onClick = { play(o.id) }) { Text(tl("Continue")) }
                        OutlinedButton(onClick = { ask = Ask(tl("Leave this set?"), tl("It ends without a score. The set it used is not given back."), tl("Leave it"), danger = true) {
                            scope.launch { runCatching { a.raw("POST", "/mcq/attempts/${o.id}/abandon") }.onFailure { toast(it.message.orEmpty()) }; tick++ } } }) { Text(tl("Leave it")) }
                    }
                }
            }
            if (h.courses.isEmpty()) { Quiet(tl("There are no topics to practise yet.")); return@Loaded }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(!perTopic, { perTopic = false }, { Text(tl("Practice")) })
                FilterChip(perTopic, { perTopic = true }, { Text(tl("Per topic")) })
            }
            SectionTitle(tl("Course"))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!perTopic) FilterChip(course == 0, { course = 0; tid = 0 }, { Text(tl("All my courses")) })
                h.courses.forEach { c -> FilterChip(course == c.id, { course = c.id; tid = 0 }, { Text(c.name) }) }
            }
            val c = h.courses.firstOrNull { it.id == course }
            if (perTopic) {
                SectionTitle(tl("Topic"))
                if (c == null) Quiet(tl("Choose a course"))
                c?.topics?.forEach { t ->
                    ListRow(t.title, pl(t.questions, "question") + (t.stats?.let { " · " + tl("you {p}%", "p" to it.percent) } ?: ""), onClick = { tid = t.id },
                            trailing = { if (tid == t.id) Icon(Icons.Filled.Check, tl("Chosen"), tint = MaterialTheme.colorScheme.primary) })
                }
            }
            SectionTitle(tl("Questions in the set"))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { listOf(5, 10, 15, 20).filter { it <= h.max }.forEach { n -> FilterChip(size == n, { size = n }, { Text("$n") }) } }
            val t = c?.topics?.firstOrNull { it.id == tid }
            val pool = if (perTopic) t?.questions ?: 0 else c?.questions ?: h.courses.sumOf { it.questions }
            val ready = !perTopic || t != null; val left = (h.quota.left ?: 1) > 0
            val go = { source: String -> scope.launch {
                busy = source
                try {
                    val r = a.send("POST", "/mcq/attempts", buildJsonObject {
                        put("mode", if (perTopic) "topic" else "practice"); put("source", source); put("size", size); put("request_id", java.util.UUID.randomUUID().toString())
                        if (perTopic) put("topic_id", tid) else if (course > 0) put("course_id", course)
                    }, McqSet.serializer())
                    if (r.resumed) toast(tl("You have a set in progress. Here it is."))
                    onMain { play(r.id) }
                } catch (e: Exception) { toast(e.message.orEmpty()); tick++ }
                busy = ""
            } }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = busy.isEmpty() && ready && pool >= h.min && left, onClick = { go("bank") }) { Text(if (busy == "bank") tl("Starting…") else tl("Questions from the bank")) }
                if (h.ai) OutlinedButton(enabled = busy.isEmpty() && ready && left, onClick = { go("ai") }) { Text(if (busy == "ai") tl("Writing questions…") else tl("A new AI set")) }
            }
            Quiet((if (ready && pool < h.min) tl("Not enough published questions here yet.") else tl(if (pool == 1) "{n} published question to draw from." else "{n} published questions to draw from.", "n" to pool))
                  + " " + tl("A set counts when it starts."))
        }
        (hist.state as? Load.Ok)?.value?.takeIf { it.total > 0 }?.let { hs ->
            SectionTitle(tl("Your sets"))
            hs.items.forEach { x ->
                ListRow(x.topic.ifEmpty { x.course.ifEmpty { tl("All my courses") } },
                        stamp(x.at.orEmpty()) + " · " + (if (x.mode == "topic") tl("Per topic") else tl("Practice")) + " · " + (if (x.source == "ai") tl("AI set") else tl("Bank")),
                        onClick = if (x.status == "submitted") ({ play(x.id) }) else null,
                        trailing = { Text(if (x.status == "submitted") "${x.score}/${x.total} · ${x.percent}%" else tl("Left"), style = MaterialTheme.typography.labelLarge) })
            }
        }
    }
    AskDialog(ask) { ask = null }
}

/** one set: answers are saved as they go (so the app can close and carry on later); after submitting, the score, each answer explained, and what to revisit */
@Composable
fun McqSetScreen(id: Int, back: () -> Unit, openTopic: (Int) -> Unit) {
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast(); val scroll = rememberScrollState()
    var tick by remember { mutableIntStateOf(0) }
    val load = rememberLoad("mcq-set", id, tick) { get("/mcq/attempts/$id", McqSet.serializer()) }
    var done by remember { mutableStateOf<McqSet?>(null) }
    var busy by remember { mutableStateOf(false) }
    var ask by remember { mutableStateOf<Ask?>(null) }
    val set0 = (load.state as? Load.Ok)?.value
    val picks = remember(set0) { mutableStateListOf<Int?>().apply { set0?.questions?.forEach { add(it.chosen) } } }
    val d = done ?: set0
    Page(if (d?.mode == "topic") d.questions.firstOrNull()?.topic.orEmpty() else tl("MCQ practice"),
         if (d?.status == "open") tl("{n} questions · answers are saved as you go", "n" to d.total) else d?.submitted_at?.let { stamp(it) }.orEmpty(), back, scroll = scroll) {
        Loaded(load) { _ ->
            val s = d ?: return@Loaded; val open = s.status == "open"
            if (!open) {
                Panel {
                    Text("${s.score} / ${s.total} · ${s.percent}%", style = MaterialTheme.typography.headlineSmall)
                    Quiet(if (s.source == "ai") tl("An AI set, written from your topics' notes.") else tl("A set from the question bank."))
                }
                if (s.feedback.isNotEmpty()) {
                    SectionTitle(tl("What you are good at and what to revisit"))
                    AreaList(s.feedback.map { Area(topic_id = it.topic_id, title = it.topic, percent = it.percent, status = it.status, correct = it.correct, total = it.total) }, onStudy = openTopic)
                }
            }
            s.questions.forEachIndexed { i, x ->
                Panel {
                    Text(tl("Question") + " ${i + 1}" + (if (!open) " · " + (if (x.ok) tl("Right") else tl("Wrong")) else "") + (if (s.mode != "topic" && x.topic.isNotEmpty()) " · ${x.topic}" else ""), fontWeight = FontWeight.SemiBold)
                    MathMd(x.text); QImage(x.image)
                    x.options.forEachIndexed { k, o ->
                        val st = if (open) (if (picks.getOrNull(i) == k) OptState.Picked else OptState.Plain)
                                 else if (k == x.correct) OptState.Ok else if (k == x.chosen) OptState.Bad else OptState.Plain
                        val tag = if (open) "" else listOfNotNull(if (k == x.chosen) tl("Your answer") else null, if (k == x.correct) tl("Correct answer") else null).joinToString(" · ")
                        Option(k, o, x.option_images.getOrElse(k) { "" }, st, tag, onClick = if (open) ({
                            picks[i] = k
                            scope.launch { runCatching { a.raw("PUT", "/mcq/attempts/$id/answers", buildJsonObject { putJsonObject("answers") { put(x.pos.toString(), k) } }) }.onFailure { toast(it.message.orEmpty()) } }
                        }) else null)
                    }
                    if (!open && x.chosen == null) Quiet(tl("Left blank."))
                    if (!open && x.explanation.isNotBlank()) MathMd(x.explanation)
                    if (!open) QImage(x.explanation_image)
                }
            }
            if (open) {
                val left = picks.count { it == null }
                val submit = { scope.launch {
                    busy = true
                    try {
                        val body = buildJsonObject { putJsonObject("answers") { s.questions.forEachIndexed { i, x -> put(x.pos.toString(), picks.getOrNull(i)?.let(::JsonPrimitive) ?: JsonNull) } } }
                        done = a.send("POST", "/mcq/attempts/$id/submit", body, McqSet.serializer()); scroll.scrollTo(0)
                    } catch (e: Exception) { toast(e.message.orEmpty()) }
                    busy = false
                } }
                Button(enabled = !busy, modifier = Modifier.fillMaxWidth(), onClick = {
                    if (left > 0) ask = Ask(tl("Submit with {n} unanswered?", "n" to left), tl("Blank answers count as wrong."), tl("Submit")) { submit() } else submit()
                }) { Text(if (busy) tl("Checking…") else tl("Submit answers")) }
                if (left > 0) Quiet("$left " + tl("unanswered. Blank answers count as wrong."))
            } else TextButton(onClick = back, modifier = Modifier.align(Alignment.CenterHorizontally)) { Text(tl("Back")) }
        }
    }
    AskDialog(ask) { ask = null }
}
