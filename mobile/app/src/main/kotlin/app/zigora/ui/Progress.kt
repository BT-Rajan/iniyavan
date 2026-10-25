package app.zigora.ui

import android.app.TimePickerDialog
import android.print.PrintAttributes
import android.print.PrintManager
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.outlined.Assessment
import androidx.compose.material.icons.outlined.ExpandLess
import androidx.compose.material.icons.outlined.ExpandMore
import androidx.compose.material.icons.outlined.Print
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryScrollableTabRow
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.zigora.data.AQuestion
import app.zigora.data.AiStatus
import app.zigora.data.AttemptFull
import app.zigora.data.Attempts
import app.zigora.data.Highlight
import app.zigora.data.Highlights
import app.zigora.data.Insights
import app.zigora.data.LearnerOut
import app.zigora.data.PlanOut
import app.zigora.data.ProgramNode
import app.zigora.data.Revision
import app.zigora.data.RevTopic
import app.zigora.data.ScoreCourse
import app.zigora.data.Scores
import app.zigora.data.SessionItem
import app.zigora.data.SessionOut
import app.zigora.data.Step
import app.zigora.data.TopicRef
import coil3.compose.AsyncImage
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.launch
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.put
import java.net.URLEncoder
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.time.format.TextStyle
import java.util.Locale

// The student's own pages, as on the web: Saved (bookmarks and highlights), My progress (what clicked, test results, how the app adapts),
// the study routine and today's session, attempts at a quiz, and a unit's revision sheet.

const val LET = "ABCDEF"

// ---- Saved

@Composable
fun SavedScreen(openTopic: (Int) -> Unit) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var sub by remember { mutableStateOf("") }
    Page(tl("Saved"), sub) {
        PrimaryTabRow(selectedTabIndex = tab) {
            listOf(tl("Bookmarks"), tl("Highlights")).forEachIndexed { i, l -> Tab(selected = tab == i, onClick = { tab = i }, text = { Text(l) }) }
        }
        if (tab == 0) Bookmarks(openTopic) { sub = it } else MyHighlights(openTopic) { sub = it }
    }
}

private data class Mark(val unit: String, val t: TopicRef)

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Bookmarks(openTopic: (Int) -> Unit, sub: (String) -> Unit) {
    val a = api(); val scope = rememberCoroutineScope()
    val tree = rememberLoad("saved-tree") { get("/tree", ListSerializer(ProgramNode.serializer())) }
    var sem by rememberSaveable { mutableStateOf<Int?>(null) }
    var course by rememberSaveable { mutableStateOf<Int?>(null) }
    var gone by remember { mutableStateOf(setOf<Int>()) }
    var msg by remember { mutableStateOf("") }
    Loaded(tree) { list ->
        data class Sem(val id: Int, val prog: String, val name: String, val courses: List<app.zigora.data.CourseNode>)
        val marks = { c: app.zigora.data.CourseNode -> c.units.flatMap { u -> u.topics.filter { it.bookmarked && it.id !in gone }.map { Mark(u.name, it) } } }
        val sems = list.flatMap { p -> p.semesters.map { s -> Sem(s.id, p.name, s.name, s.courses.filter { marks(it).isNotEmpty() }) } }.filter { it.courses.isNotEmpty() }
        val multi = sems.map { it.prog }.toSet().size > 1
        val total = sems.sumOf { s -> s.courses.sumOf { marks(it).size } }
        LaunchedEffect(total) { sub(if (total > 0) tl(if (total == 1) "{n} topic saved" else "{n} topics saved", "n" to total) else tl("Nothing saved yet")) }
        val sm = sems.firstOrNull { it.id == sem } ?: sems.firstOrNull()
        if (sm == null) { Quiet(tl("Open any topic and tap the bookmark icon to save it here. It shows only the topics you saved, grouped by semester or year, course and unit."), Modifier.padding(top = 12.dp)); return@Loaded }
        val co = sm.courses.firstOrNull { it.id == course } ?: sm.courses.first()
        FlowRow(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            sems.forEach { x -> FilterChip(selected = x.id == sm.id, onClick = { sem = x.id; course = null },
                                            label = { Text((if (multi) x.prog + " · " else "") + tl(x.name)) }, trailingIcon = { Count(x.courses.sumOf { marks(it).size }) }) }
        }
        PrimaryScrollableTabRow(selectedTabIndex = sm.courses.indexOf(co), edgePadding = 0.dp) {
            sm.courses.forEach { c -> Tab(selected = c.id == co.id, onClick = { course = c.id }, text = { Row(verticalAlignment = Alignment.CenterVertically) { Text(c.name, maxLines = 1); Count(marks(c).size) } }) }
        }
        if (msg.isNotEmpty()) Quiet(msg)
        val rows = marks(co)
        Paged(rows, key = co.id) { m ->
            val i = rows.indexOf(m)
            if (i == 0 || rows[i - 1].unit != m.unit) SectionTitle(m.unit)
            ListRow(m.t.title, onClick = { openTopic(m.t.id) }, leading = { Dot(m.t.title, CourseColors[i % CourseColors.size]) }, extra = { StatusLine(m.t.status) },
                trailing = { IconButton(onClick = { scope.launch {
                    try { a.raw("DELETE", "/topics/${m.t.id}/bookmark"); gone = gone + m.t.id; msg = tl("Bookmark removed") } catch (e: Exception) { msg = e.message.orEmpty() }
                } }) { Icon(Icons.Filled.Bookmark, tl("Remove bookmark: {title}", "title" to m.t.title), tint = MaterialTheme.colorScheme.primary) } })
        }
    }
}

/** a small count beside a label */
@Composable
fun Count(n: Int) = androidx.compose.material3.Badge(Modifier.padding(start = 6.dp), containerColor = MaterialTheme.colorScheme.secondaryContainer,
    contentColor = MaterialTheme.colorScheme.onSecondaryContainer) { Text("$n") }

/** only what the student marked as learned; nothing for the rest */
@Composable
fun StatusLine(s: String) { if (s == "completed") Row(verticalAlignment = Alignment.CenterVertically) {
    Icon(Icons.Filled.Check, null, Modifier.size(16.dp), tint = MaterialTheme.colorScheme.primary); Quiet(" " + tl("Learned")) } }

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MyHighlights(openTopic: (Int) -> Unit, sub: (String) -> Unit) {
    val a = api(); val scope = rememberCoroutineScope()
    var q by rememberSaveable { mutableStateOf("") }
    var color by rememberSaveable { mutableStateOf("") }
    var page by rememberSaveable(q, color) { mutableIntStateOf(0) }
    var tick by remember { mutableIntStateOf(0) }
    val l = rememberLoad("my-hl", q, color, page, tick) {
        get("/me/highlights?q=${URLEncoder.encode(q, "UTF-8")}&color=$color&limit=$PAGE&offset=${page * PAGE}", Highlights.serializer())
    }
    var items by remember { mutableStateOf<List<Highlight>?>(null) }
    LaunchedEffect(l.state) { (l.state as? Load.Ok)?.value?.let { items = it.items; sub(if (q.isNotEmpty() || color.isNotEmpty()) tl(if (it.total == 1) "{n} match" else "{n} matches", "n" to it.total) else pl(it.total, "highlight")) } }
    var msg by remember { mutableStateOf("") }
    OutlinedTextField(q, { q = it }, Modifier.fillMaxWidth().padding(top = 8.dp), singleLine = true, leadingIcon = { Icon(Icons.Outlined.Search, null) },
                      placeholder = { Text(tl("Search your highlights, notes or topics")) })
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        (listOf("" to tl("All colours")) + HL_COLORS.keys.map { it to tl(it.replaceFirstChar(Char::uppercase)) }).forEach { (k, label) ->
            FilterChip(selected = color == k, onClick = { color = k }, label = { Text(label) },
                       leadingIcon = if (k.isEmpty()) null else ({ Box(Modifier.size(12.dp).background(HL_COLORS.getValue(k), CircleShape)) }))
        }
    }
    if (msg.isNotEmpty()) Quiet(msg)
    val list = items
    if (list == null) { Loaded(l) {}; return }
    list.forEach { h ->
        HlItem(h, where = listOf(h.topic, h.course).filter { it.isNotEmpty() }.joinToString(" · "), onGo = h.topic_id?.let { { openTopic(it) } }, onExplain = null,
               onSaved = { tick++ }, topicId = h.topic_id, onDrop = { scope.launch {
                   try { a.raw("DELETE", "/me/highlights/${h.id}"); msg = tl("Highlight removed"); tick++ } catch (e: Exception) { msg = e.message.orEmpty() }
               } })
    }
    if (list.isEmpty()) Quiet(if (q.isNotEmpty() || color.isNotEmpty()) tl("No highlight matches.") else tl("No highlights yet. Open a topic, select some text and pick a colour."))
    val total = (l.state as? Load.Ok)?.value?.total ?: 0
    val pages = (total + PAGE - 1) / PAGE
    if (pages > 1) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
        TextButton(onClick = { page-- }, enabled = page > 0) { Text(tl("Previous")) }
        Text(tl("Page {v} of", "v" to page + 1) + " $pages", style = MaterialTheme.typography.labelLarge)
        TextButton(onClick = { page++ }, enabled = page < pages - 1) { Text(tl("Next")) }
    }
}

// ---- My progress

@Composable
fun ProgressScreen(openTopic: (Int) -> Unit, openRoutine: () -> Unit, openScores: (Int) -> Unit) {
    val d = rememberLoad("insights") { get("/me/insights", Insights.serializer()) }
    Page(tl("My progress")) {
        Loaded(d) { x ->
            val clicked = x.strong; val looks = x.needs_study + x.getting_there
            val item = @Composable { ar: app.zigora.data.Area -> RowLink(ar.title, ar.course, ar.topic_id?.let { { openTopic(it) } }) }
            if (clicked.isEmpty() && looks.isEmpty()) Quiet(tl("After you try a quiz or a test, the topics that clicked and the ones worth another look show up here."), Modifier.padding(top = 12.dp))
            if (clicked.isNotEmpty()) { SectionTitle(tl("What clicked")); Paged(clicked, key = "c") { item(it) } }
            if (looks.isNotEmpty()) { SectionTitle(tl("Worth another look")); Paged(looks, key = "l") { item(it) } }
        }
        SectionTitle(tl("Study routine"))
        RowLink(tl("Set or change your study days"), tl("Optional. Some people like a rhythm; nothing changes unless you set one."), openRoutine)
        var open by rememberSaveable { mutableStateOf(false) }
        SectionTitle(tl("Test results"))
        ListRow(tl("Scores"), onClick = { open = !open }, leading = { RowIcon(Icons.Outlined.Assessment) },
                trailing = { Icon(if (open) Icons.Outlined.ExpandLess else Icons.Outlined.ExpandMore, null) })
        if (open) MyScores(openScores)
        AdaptCard()
    }
}

@Composable
private fun MyScores(open: (Int) -> Unit) {
    val d = rememberLoad("scores") { get("/me/scores", Scores.serializer()) }
    val x = (d.state as? Load.Ok)?.value ?: return
    if (x.courses.isEmpty()) { Quiet(tl("No test results yet.")); return }
    Paged(x.courses, key = "sc") { c ->
        RowLink(c.course, (if (c.final == null) tl("No tests taken yet") else tl("Final score {final}%", "final" to c.final)) + " " +
                tl("· {taken} of {length} taken · {passed} passed", "taken" to c.taken, "length" to c.tests.size, "passed" to c.passed), { open(c.course_id) }) {
            if (c.final != null) ScoreBar(c.final)
        }
    }
}

@Composable
fun ScoreCourseScreen(cid: Int, back: () -> Unit, openAttempts: (Int) -> Unit) {
    val d = rememberLoad("scores", cid) { get("/me/scores", Scores.serializer()) }
    val c: ScoreCourse? = (d.state as? Load.Ok)?.value?.courses?.firstOrNull { it.course_id == cid }
    Page(c?.course.orEmpty(), c?.let { tl("Final score {v} · {taken} of {length} taken", "v" to (it.final?.let { f -> "$f%" } ?: "–"), "taken" to it.taken, "length" to it.tests.size) }.orEmpty(), back) {
        Loaded(d) { _ ->
            if (c == null) { Quiet(tl("No test results yet.")); return@Loaded }
            Paged(c.tests, key = cid) { t ->
                RowLink(t.title + if (t.attempts > 0) "  ·  " + tl(if (t.passed) "Passed" else "Not yet") else "",
                        (t.unit.ifEmpty { tl("Course test") }) + " " + tl("· {v} · pass {pass_percent}%", "pass_percent" to t.pass_percent,
                            "v" to if (t.attempts > 0) "best ${t.best}% · latest ${t.latest}% · ${pl(t.attempts, "attempt")}" else "not taken yet"),
                        if (t.attempts > 0) ({ openAttempts(t.id) }) else null) { if (t.attempts > 0) ScoreBar(t.best) }
            }
            Quiet(tl("Your final score in a test is your best attempt. The course score is the average of the tests you have taken."), Modifier.padding(top = 8.dp))
        }
    }
}

@Composable
private fun AdaptCard() {
    val a = api(); val scope = rememberCoroutineScope(); val name = app().store.appName
    var tick by remember { mutableIntStateOf(0) }
    val d = rememberLoad("learning", tick) { get("/me/learning", LearnerOut.serializer()) }
    val x = (d.state as? Load.Ok)?.value ?: return
    val taps = x.taps.values.sum()
    val fav = if (taps >= 3) x.order.firstOrNull()?.let { stepLabel(it) } else null  // the topic page's own name for the step
    val lines = listOfNotNull(fav?.let { tl("{step} comes first on a topic, since you reach for it most", "step" to it) },
        if (x.level == "hard") tl("Quick checks ask you to apply ideas, since you have been getting them") else null,
        if (x.level == "easy") tl("Quick checks are plainer for now, with a hint when it helps") else null,
        tl("After a few topics in a unit, a topic starts with its question and keeps the gist one tap away"),
        tl("Remember this? brings back topics you marked “Not quite”"))
    var msg by remember { mutableStateOf("") }
    SectionTitle(tl("How {name} adapts to you", "name" to name))
    Panel {
        lines.forEach { Text("•  $it", Modifier.padding(vertical = 2.dp)) }
        Quiet(tl("It learns only from the steps you open and your own “I had it” / “Not quite”. Your teachers never see this."), Modifier.padding(top = 8.dp))
        if (msg.isNotEmpty()) Quiet(msg)
        if (taps > 0 || x.checks > 0) OutlinedButton(onClick = { scope.launch {
            try { a.raw("DELETE", "/me/learning/steps"); msg = tl("Started fresh"); tick++ } catch (e: Exception) { msg = e.message.orEmpty() }
        } }, modifier = Modifier.padding(top = 8.dp)) { Text(tl("Start fresh")) }
    }
}

// ---- attempts

@Composable
fun AttemptsScreen(quiz: Int, back: () -> Unit, open: (Int) -> Unit) {
    val d = rememberLoad("attempts", quiz) { get("/quizzes/$quiz/attempts", Attempts.serializer()) }
    val x = (d.state as? Load.Ok)?.value
    Page(x?.quiz ?: tl("Attempts"), x?.let { pl(it.items.size, "attempt") }.orEmpty(), back) {
        Loaded(d) { v ->
            if (v.items.isEmpty()) Quiet(tl("No attempts yet."))
            Paged(v.items, key = quiz) { r ->
                RowLink("${r.score} / ${r.total} · ${r.percent}%", stamp(r.at) + (if (r.passed) " · " + tl("reached the pass mark") else "") + (if (r == v.items.first()) tl(" · latest") else ""),
                        { open(r.id) }) { ScoreBar(r.percent) }
            }
        }
    }
}

@Composable
fun AttemptScreen(id: Int, back: () -> Unit, openTopic: (Int) -> Unit) {
    val d = rememberLoad("attempt", id) { get("/attempts/$id", AttemptFull.serializer()) }
    val x = (d.state as? Load.Ok)?.value
    Page(x?.quiz ?: tl("Attempt"), x?.let { stamp(it.at) }.orEmpty(), back) {
        Loaded(d) { v ->
            Panel {
                Text("${v.score} / ${v.total} · ${v.percent}%", style = MaterialTheme.typography.headlineSmall)
                Quiet(tl("Pass mark {pass}%.", "pass" to v.pass_percent) + if (v.summary.isNotEmpty()) " " + v.summary else "")
            }
            if (v.areas.isNotEmpty()) { SectionTitle(tl("What you are good at and what to revisit")); AreaList(v.areas, onStudy = openTopic) }
            if (v.no_detail) Quiet(tl("This attempt was made before answers were kept question by question, so only the score is known."))
            if (v.changed > 0) Quiet(pl(v.changed, "question") + " " + tl("of this attempt {v} changed or removed since, so {v2} not shown.",
                                                                       "v" to if (v.changed == 1) "was" else "were", "v2" to if (v.changed == 1) "it is" else "they are"))
            val right = v.questions.count { it.ok }
            if (!v.reveal && v.questions.isNotEmpty()) Quiet(tl("You see which answers were right ({right} of {length}). This quiz does not show the correct answers.", "right" to right, "length" to v.questions.size))
            v.questions.forEachIndexed { i, q -> AttemptQuestion(i, q, v.reveal) }
        }
    }
}

@Composable
private fun AttemptQuestion(i: Int, x: AQuestion, reveal: Boolean) = Panel {
    Text(tl("Question {v} ·", "v" to i + 1) + " " + (if (x.ok) tl("Right") else tl("Wrong")) + (if (x.area.isNotEmpty()) " · " + x.area else ""), fontWeight = FontWeight.SemiBold)
    Md(x.text); QImage(x.image)
    x.options.forEachIndexed { k, o ->
        val mine = x.chosen_known && x.chosen == k; val key = reveal && x.correct == k
        Option(k, o, x.option_images.getOrElse(k) { "" }, when { key || (mine && x.ok) -> OptState.Ok; mine -> OptState.Bad; else -> OptState.Plain },
               tag = listOfNotNull(if (mine) tl("Your answer") else null, if (key) tl("Correct answer") else null).joinToString(" · "))
    }
    if (x.chosen_known && x.chosen == null) Quiet(tl("Left blank."))
    if (x.explanation.isNotEmpty()) Md(x.explanation)
}

enum class OptState { Plain, Picked, Ok, Bad }

/** one answer of a question: its letter, its text or picture; picked, right or wrong as on the web */
@Composable
fun Option(k: Int, text: String, img: String, state: OptState, tag: String = "", onClick: (() -> Unit)? = null) {
    val cs = MaterialTheme.colorScheme
    val (bg, line) = when (state) {
        OptState.Ok -> Color(0x332E7D5B) to Color(0xFF2E7D5B)
        OptState.Bad -> cs.errorContainer to cs.error
        OptState.Picked -> cs.primaryContainer to cs.primary
        OptState.Plain -> cs.surface to cs.outline
    }
    val shape = RoundedCornerShape(12.dp)
    val body = @Composable {
        Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(LET[k].toString(), fontWeight = FontWeight.Bold, color = line, modifier = Modifier.padding(end = 12.dp))
            Column(Modifier.weight(1f)) {
                if (img.isNotEmpty()) QImage(img)
                if (text.isNotEmpty()) Md(text) else if (img.isEmpty()) Text("—")
                if (tag.isNotEmpty()) Text(tag, style = MaterialTheme.typography.labelMedium, color = line)
            }
        }
    }
    val colors = CardDefaults.cardColors(containerColor = bg)
    if (onClick != null) Card(onClick = onClick, Modifier.fillMaxWidth().padding(top = 6.dp), shape = shape, colors = colors, border = BorderStroke(1.dp, line)) { body() }
    else Card(Modifier.fillMaxWidth().padding(top = 6.dp), shape = shape, colors = colors, border = BorderStroke(1.dp, line)) { body() }
}

@Composable
fun QImage(src: String) { if (src.isNotEmpty()) AsyncImage(api().base + src, null, Modifier.fillMaxWidth().heightIn(max = 260.dp).padding(vertical = 4.dp)) }

// ---- the study routine and today's session

private fun weekday(i: Int) = DayOfWeek.of(i + 1).getDisplayName(TextStyle.SHORT, Locale.getDefault())  // Monday first, as the server counts
private fun nextStudyDay(days: String): String {
    for (k in 1..7) { val d = LocalDate.now().plusDays(k.toLong()); val i = d.dayOfWeek.value - 1; if (days.getOrNull(i) == '1') return if (k == 1) tl("tomorrow") else weekday(i) }
    return ""
}
private fun shortDay(iso: String?, year: Boolean = false) = runCatching {
    LocalDate.parse(iso).format(DateTimeFormatter.ofPattern(if (year) "d MMM yyyy" else "d MMM", Locale.getDefault()))
}.getOrDefault(iso.orEmpty())

@Composable
fun RoutineScreen(back: () -> Unit) {
    val a = api(); val scope = rememberCoroutineScope(); val ctx = LocalContext.current; val toast = rememberToast()
    val d = rememberLoad("session-r") { get("/me/session", SessionOut.serializer()) }
    var days by rememberSaveable { mutableStateOf("1111110") }
    var minutes by rememberSaveable { mutableIntStateOf(30) }
    var at by rememberSaveable { mutableStateOf("") }
    var plan by remember { mutableStateOf<PlanOut?>(null) }
    var busy by remember { mutableStateOf(false) }
    var msg by remember { mutableStateOf("") }
    var asking by remember { mutableStateOf(false) }
    val v = (d.state as? Load.Ok)?.value
    LaunchedEffect(v) { v?.routine?.let { days = it.days; minutes = it.minutes; at = it.at.orEmpty() }; plan = v?.plan }
    Page(tl("My routine"), tl("Study at your own pace, a little every day"), back) {
        val per = mapOf(15 to 1, 30 to 1, 45 to 2, 60 to 3)[minutes] ?: 1
        Quiet(tl("Pick the days you study and how long. Each study day you get one session: {v} and any reviews that are due. Miss a day and nothing piles up: the next session is the same size.",
                 "v" to if (per == 1) tl("one new topic") else tl("{n} new topics", "n" to per)))
        SectionTitle(tl("Study days"))
        @OptIn(ExperimentalLayoutApi::class)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            (0..6).forEach { k -> FilterChip(selected = days[k] == '1', onClick = { days = days.substring(0, k) + (if (days[k] == '1') '0' else '1') + days.substring(k + 1) },
                                             label = { Text(weekday(k)) }) }
        }
        SectionTitle(tl("Minutes a session"))
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            listOf(15, 30, 45, 60).forEachIndexed { i, m -> SegmentedButton(selected = minutes == m, onClick = { minutes = m }, shape = SegmentedButtonDefaults.itemShape(i, 4)) { Text("$m") } }
        }
        SectionTitle(tl("Usual time (optional)"))
        Row(verticalAlignment = Alignment.CenterVertically) {
            AssistChip(onClick = {
                val (h, m) = at.split(":").let { (it.getOrNull(0)?.toIntOrNull() ?: 19) to (it.getOrNull(1)?.toIntOrNull() ?: 0) }
                TimePickerDialog(ctx, { _, hh, mm -> at = "%02d:%02d".format(Locale.ROOT, hh, mm) }, h, m, android.text.format.DateFormat.is24HourFormat(ctx)).show()
            }, label = { Text(at.ifEmpty { "--:--" }) }, leadingIcon = { Icon(Icons.Outlined.Schedule, null) })
            if (at.isNotEmpty()) TextButton(onClick = { at = "" }) { Text(tl("Clear")) }
        }
        plan?.let { p ->
            Quiet((if (p.left > 0) tl("With your current routine you would finish the {left} topics left by {v}.", "left" to p.left, "v" to shortDay(p.finish, true))
                   else tl("Nothing is left to study right now.")) + if (p.late > 0) tl(" {late} topics would miss their deadline. {v}", "late" to p.late, "v" to p.advice.orEmpty()) else "",
                  Modifier.padding(top = 8.dp))
        }
        if (msg.isNotEmpty()) Text(msg, color = MaterialTheme.colorScheme.error)
        Button(enabled = !busy && '1' in days, modifier = Modifier.fillMaxWidth().padding(top = 8.dp), onClick = { scope.launch {
            busy = true; msg = ""
            try {
                a.send("PUT", "/me/routine", buildJsonObject { put("days", days); put("minutes", minutes); put("at", if (at.isEmpty()) JsonNull else JsonPrimitive(at)) }, SessionOut.serializer())
                toast(tl("Routine saved")); onMain(back)
            } catch (e: Exception) { msg = e.message.orEmpty() }
            busy = false
        } }) { Text(tl("Save routine")) }
        if (v?.routine != null) OutlinedButton(onClick = { asking = true }, Modifier.fillMaxWidth()) { Text(tl("Stop the routine")) }
    }
    if (asking) AlertDialog(onDismissRequest = { asking = false }, title = { Text(tl("Stop your routine?")) }, text = { Text(tl("Your progress stays. Home goes back to showing what to do next.")) },
        confirmButton = { TextButton(onClick = { asking = false; scope.launch {
            try { a.raw("POST", "/me/routine/stop"); toast(tl("Routine stopped")); onMain(back) } catch (e: Exception) { msg = e.message.orEmpty() }
        } }) { Text(tl("Stop the routine")) } },
        dismissButton = { TextButton(onClick = { asking = false }) { Text(tl("Cancel")) } })
}

/** today's one session on Home, from the student's own routine; nothing at all without a routine (it is never pushed on anyone) */
@Composable
fun SessionCard(v: SessionOut, onRoutine: () -> Unit, open: (SessionItem) -> Unit, changed: (SessionOut) -> Unit) {
    val a = api(); val scope = rememberCoroutineScope()
    val r = v.routine ?: return
    var busy by remember { mutableStateOf(false) }
    val ss = v.session; val left = ss?.items?.filter { !it.done }.orEmpty()
    val cs = MaterialTheme.colorScheme
    Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = cs.primaryContainer, contentColor = cs.onPrimaryContainer)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(tl("Today's session · {minutes} min", "minutes" to r.minutes) + (r.at?.let { " · $it" } ?: ""), Modifier.weight(1f), style = MaterialTheme.typography.labelLarge)
                AssistChip(onClick = onRoutine, label = { Text(tl("Routine")) }, leadingIcon = { Icon(Icons.Outlined.Schedule, tl("Change my routine"), Modifier.size(16.dp)) })
            }
            if (v.missed >= 2 && !v.studied_today) Text(tl("Welcome back. Today is just one session, the same as always. No catching up needed."))
            when {
                ss == null -> {
                    Text(tl("Rest day"), style = MaterialTheme.typography.headlineSmall)
                    Text(tl("Your next session is {nextStudyDay}.", "nextStudyDay" to nextStudyDay(r.days)))
                    Button(enabled = !busy, onClick = { scope.launch {
                        busy = true; runCatching { a.send("POST", "/me/session", null, SessionOut.serializer()) }.onSuccess(changed); busy = false
                    } }) { Text(tl("Study anyway")) }
                }
                ss.caught_up -> { Text(tl("All caught up"), style = MaterialTheme.typography.headlineSmall); Text(tl("Nothing is left to study right now. Well done.")) }
                else -> {
                    Text(if (ss.done) "✓ " + tl("Done for today") else "${left.size} " + tl("of {length} to go", "length" to ss.items.size), style = MaterialTheme.typography.headlineSmall)
                    ss.items.forEach { x ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 2.dp).let { m -> m }, verticalAlignment = Alignment.CenterVertically) {
                            Icon(if (x.done) Icons.Filled.Check else if (x.kind == "review") Icons.Filled.Refresh else Icons.Filled.PlayArrow, null, Modifier.size(18.dp))
                            TextButton(onClick = { open(x) }, modifier = Modifier.weight(1f)) {
                                Column(Modifier.fillMaxWidth()) { Text(x.title, fontWeight = FontWeight.SemiBold); Text(x.course, style = MaterialTheme.typography.bodySmall) }
                            }
                        }
                    }
                    if (!ss.done && left.isNotEmpty()) Button(onClick = { open(left[0]) }, Modifier.fillMaxWidth()) {
                        Text((if (left.size == ss.items.size) tl("Start") else tl("Continue")) + ": " + left[0].title, maxLines = 1)
                    }
                    if (ss.done) Text(tl("See you {nextStudyDay}.", "nextStudyDay" to nextStudyDay(r.days)))
                }
            }
            v.plan?.let { p ->
                Text((if (p.left > 0) tl("{left} topics left · at this pace, done by {v}", "left" to p.left, "v" to shortDay(p.finish)) else tl("Nothing left in your courses")) +
                     (if (p.late > 0) tl(" · {late} would miss their deadline. {v}", "late" to p.late, "v" to p.advice.orEmpty()) else ""), style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

// ---- a unit's revision sheet

private fun JsonObject.text(k: String) = (this[k] as? JsonPrimitive)?.contentOrNull.orEmpty()
private fun JsonObject.texts(k: String) = (this[k] as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }.orEmpty()

@Composable
fun RevisionScreen(uid: Int, back: () -> Unit) {
    val a = api(); val ctx = LocalContext.current
    val d = rememberLoad("revision", uid) { get("/units/$uid/revision", Revision.serializer()) }
    val gists = remember(uid) { mutableStateMapOf<Int, JsonObject>() }
    var left by remember(uid) { mutableIntStateOf(0) }
    val x = (d.state as? Load.Ok)?.value
    LaunchedEffect(x) {  // the topics without a gist yet get one written, two at a time, when AI help is on
        val q = ArrayDeque(x?.topics?.filter { it.gist == null }.orEmpty()); if (q.isEmpty()) return@LaunchedEffect
        if (!runCatching { a.get("/ai/status", AiStatus.serializer()).available }.getOrDefault(false)) return@LaunchedEffect
        left = q.size
        kotlinx.coroutines.coroutineScope {
            (1..2).map { async { while (true) { val t = q.removeFirstOrNull() ?: break
                runCatching { a.get("/topics/${t.id}/ai/gist", Step.serializer()).data }.getOrNull()?.let { gists[t.id] = it }  // a topic stays without its gist on failure
                left-- } } }.awaitAll()
        }
    }
    Page(tl("Revision sheet"), x?.let { it.course + " · " + it.unit }.orEmpty(), back) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedButton(enabled = x != null, onClick = { x?.let { printSheet(ctx, it, gists) } }) { Icon(Icons.Outlined.Print, null); Text("  " + tl("Print or save as PDF")) }
            if (left > 0) Quiet(tl("Writing {n} more…", "n" to left), Modifier.padding(start = 12.dp))
        }
        Loaded(d) { v ->
            Text(v.unit, style = MaterialTheme.typography.headlineSmall, modifier = Modifier.padding(top = 8.dp)); Quiet(v.course)
            v.topics.forEach { t -> RevSection(t, t.gist ?: gists[t.id], left > 0) }
        }
    }
}

@Composable
private fun RevSection(t: RevTopic, g: JsonObject?, writing: Boolean) = Column(Modifier.padding(top = 16.dp)) {
    Text(t.title, style = MaterialTheme.typography.titleMedium)
    if (g != null) g.texts("points").forEach { p ->  // short plain points, shown as on the topic page's gist
        Row(Modifier.padding(top = 4.dp)) { Text("•", Modifier.padding(end = 10.dp)); Text(p.replace(Regex("""\*\*|__|`"""), "")) }
    }
    else Quiet(if (writing) tl("Writing…") else tl("No gist yet. Open the topic once to make it."))
    g?.text("hook")?.takeIf { it.isNotEmpty() }?.let { Text(tl("Ask yourself") + ": " + it, fontWeight = FontWeight.Medium, modifier = Modifier.padding(top = 4.dp)) }
    if (t.highlights.isNotEmpty()) {
        Text(tl("Your highlights"), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(top = 8.dp))
        t.highlights.forEach { Quiet("•  $it") }
    }
    HorizontalDivider(Modifier.padding(top = 12.dp))
}

/** the sheet through Android's own printing, which also saves it as a PDF */
private fun printSheet(ctx: android.content.Context, r: Revision, gists: Map<Int, JsonObject>) {
    fun esc(s: String) = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    fun plain(s: String) = esc(s.replace(Regex("""\*\*|__|`"""), ""))
    val html = buildString {
        append("<html><head><meta charset='utf-8'><style>body{font-family:sans-serif;margin:24px}h1{margin:0}small{color:#666}h3{margin:18px 0 4px}li{margin:2px 0}.q{font-style:italic}.hl{color:#555}</style></head><body>")
        append("<h1>${esc(r.unit)}</h1><small>${esc(r.course)}</small>")
        r.topics.forEach { t ->
            val g = t.gist ?: gists[t.id]
            append("<h3>${esc(t.title)}</h3>")
            if (g != null) append("<ul>" + g.texts("points").joinToString("") { "<li>${plain(it)}</li>" } + "</ul>")
            g?.text("hook")?.takeIf { it.isNotEmpty() }?.let { append("<p class='q'>${esc(tl("Ask yourself"))}: ${plain(it)}</p>") }
            if (t.highlights.isNotEmpty()) append("<div class='hl'><small>${esc(tl("Your highlights"))}</small><ul>" + t.highlights.joinToString("") { "<li>${esc(it)}</li>" } + "</ul></div>")
        }
        append("</body></html>")
    }
    val w = WebView(ctx)
    w.webViewClient = object : WebViewClient() {
        override fun onRenderProcessGone(view: WebView, detail: android.webkit.RenderProcessGoneDetail?): Boolean { view.destroy(); return true }  // no sheet then, but no crash
        override fun onPageFinished(view: WebView, url: String?) {
            val pm = ctx.getSystemService(android.content.Context.PRINT_SERVICE) as PrintManager
            pm.print(r.unit, view.createPrintDocumentAdapter(r.unit), PrintAttributes.Builder().build())
        }
    }
    w.loadDataWithBaseURL(null, html, "text/html", "utf-8", null)
}
