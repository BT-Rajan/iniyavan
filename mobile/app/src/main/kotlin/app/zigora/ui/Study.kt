package app.zigora.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.Upload
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.zigora.data.Answer
import app.zigora.data.ApiError
import app.zigora.data.PlanOutWrap
import app.zigora.data.StudyCourseFull
import app.zigora.data.StudyList
import app.zigora.data.StudyMe
import app.zigora.data.StudyPlan
import app.zigora.data.StudyProgressOut
import app.zigora.data.StudyQuiz
import app.zigora.data.StudyRow
import app.zigora.data.STopicFull
import app.zigora.data.json
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.net.URLEncoder

// Build a course from your own notes, as on the web: name it, add material, let the AI (or the headings) slice it into units and topics,
// check the outline, then study it with explanations, quick checks, quizzes and spaced reviews.

/** the line about AI help for your own courses: switched off, or only a few requests left today */
@Composable
fun AiNote(available: Boolean, left: Int?, ownKey: Boolean) = when {
    !available -> Quiet(if (ownKey) tl("Add your own AI key under “My AI key” in the menu to use explanations, quick checks and quizzes.")
                        else tl("AI help is switched off right now. Ask your admin to add an AI key."))
    left != null && left <= 10 -> Quiet(if (left > 0) tl("{n} left today for your own courses.", "n" to pl(left, "AI request"))
                                         else tl("You have used today's AI requests for your own courses. Reviews still work; new questions come back tomorrow."))
    else -> Unit
}

/** what to do next in your own courses: the next topic, and the reviews that are due */
@Composable
fun LearnCard(me: StudyMe, onContinue: (Int, Int) -> Unit, onReview: (Int) -> Unit) = Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
    me.next?.let { n -> Button(onClick = { onContinue(n.course_id, n.topic_id) }, Modifier.fillMaxWidth()) {
        Icon(Icons.Filled.PlayArrow, null)
        Column(Modifier.padding(start = 8.dp)) { Text((if (n.done > 0) tl("Continue") else tl("Start")) + ": " + n.topic, maxLines = 1); Text(n.course, style = MaterialTheme.typography.labelSmall) }
    } }
    if (me.reviews_due > 0) me.review_courses.firstOrNull()?.let { r ->
        OutlinedButton(onClick = { onReview(r.course_id) }, Modifier.fillMaxWidth()) { Icon(Icons.Filled.Refresh, null); Text("  " + tl("Look again at {n}", "n" to pl(me.reviews_due, "topic"))) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudyHomeScreen(back: () -> Unit, open: (Int, Boolean) -> Unit, openTopic: (Int, Int) -> Unit, review: (Int) -> Unit) {
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast()
    val d = rememberLoad("study-list") { get("/study/courses", StudyList.serializer()) }
    val me = (rememberLoad("study-me") { get("/study/me", StudyMe.serializer()) }.state as? Load.Ok)?.value
    var make by remember { mutableStateOf(false) }
    var title by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    Page(tl("Build a course"), tl("Turn your own notes into a course"), back) {
        if (me != null && me.courses > 0) LearnCard(me, openTopic, review)
        Quiet(tl("Upload your notes, textbook chapters or handouts. The AI slices them into units and small topics, you check and adjust the outline, and then you study it with explanations, practice MCQs and quizzes."),
              Modifier.padding(top = 8.dp))
        Button(onClick = { make = true }, Modifier.fillMaxWidth()) { Icon(Icons.Outlined.Upload, null); Text("  " + tl("New course from my material")) }
        Loaded(d) { x ->
            val card = @Composable { c: StudyRow ->
                RowLink(c.title + (if (c.status != "ready") "  ·  " + tl("Setup not finished") else "") + (if (c.mine && c.share == "program") "  ·  " + tl("Shared") else ""),
                        (if (c.status == "ready") tl("{completed} of {topics} topics completed", "completed" to c.completed, "topics" to c.topics) else tl("Continue the setup")) +
                        (if (!c.mine) tl(" · by {owner}", "owner" to c.owner) else ""), { open(c.id, c.mine && c.status != "ready") }) {
                    if (c.status == "ready" && c.topics > 0) ScoreBar(100 * c.completed / c.topics)
                }
            }
            if (x.mine.isNotEmpty()) { SectionTitle(tl("My courses")); Paged(x.mine, key = "m") { card(it) } }
            if (x.shared.isNotEmpty()) { SectionTitle(tl("Shared by classmates")); Paged(x.shared, key = "s") { card(it) } }
            if (x.mine.isEmpty() && x.shared.isEmpty()) Quiet(tl("You have not built a course yet."))
        }
    }
    if (make) ModalBottomSheet(onDismissRequest = { make = false }) {
        Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(tl("New course"), style = MaterialTheme.typography.titleLarge)
            OutlinedTextField(title, { title = it }, Modifier.fillMaxWidth(), singleLine = true, label = { Text(tl("Course name")) }, placeholder = { Text(tl("e.g. Islamic Education · Unit 4")) })
            Button(enabled = !busy && title.isNotBlank(), modifier = Modifier.fillMaxWidth(), onClick = { scope.launch {
                busy = true
                try { val r = a.raw("POST", "/study/courses", buildJsonObject { put("title", title) }) as JsonObject
                      make = false; title = ""; onMain { open((r["id"] as JsonPrimitive).content.toInt(), true) } } catch (e: Exception) { toast(e.message.orEmpty()) }
                busy = false
            } }) { Text(tl("Next: add material")) }
            TextButton(onClick = { make = false }) { Text(tl("Cancel")) }
        }
    }
}

private val STEPS = listOf("Name", "Material", "Slice", "Preview")
private const val NOTES_HINT = "Optional. For example: \"One topic per verse\", \"Keep the vocabulary table in one topic\", \"Units should follow the chapters\", \"Make topics very short\"."

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudyWizardScreen(id: Int, back: () -> Unit, done: () -> Unit) {
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast(); val ctx = LocalContext.current
    var c by remember { mutableStateOf<StudyCourseFull?>(null) }
    var step by remember { mutableStateOf<Int?>(null) }
    var text by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }
    var plan by remember { mutableStateOf<StudyPlan?>(null) }
    var dirty by remember { mutableStateOf(false) }
    var peek by remember { mutableStateOf<Pair<String, String>?>(null) }
    var ask by remember { mutableStateOf<Ask?>(null) }
    val scroll = rememberScrollState()
    suspend fun load(go: Int? = null) {
        try { val d = a.get("/study/courses/$id", StudyCourseFull.serializer()); c = d; notes = d.notes; plan = d.plan; dirty = false
              step = go ?: if (d.plan != null) 3 else if (d.sources.isNotEmpty()) 2 else 1 } catch (e: Exception) { toast(e.message.orEmpty()); onMain(back) }
    }
    LaunchedEffect(id) { load() }
    LaunchedEffect(c?.reading) { while (c?.reading == true) { delay(3000); runCatching { a.get("/study/courses/$id", StudyCourseFull.serializer()) }.onSuccess { c = it } } }  // only the file list refreshes
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris -> scope.launch {
        for (uri in uris) {
            val (n, bytes) = readPicked(ctx, uri)
            if (bytes == null) { toast(tl("{name} is over {MAX_FILE_MB} MB. Split it into smaller files.", "name" to n, "MAX_FILE_MB" to MAX_FILE_MB)); continue }
            busy = tl("Reading {name}…", "name" to n)
            try { val r = a.upload("/study/courses/$id/files?name=" + URLEncoder.encode(n, "UTF-8"), bytes) as JsonObject
                  toast(if ((r["status"] as? JsonPrimitive)?.content == "reading") tl("{name} is scanned pages. Reading them now…", "name" to n)
                        else tl("{name}: {n} read", "name" to n, "n" to pl((r["words"] as? JsonPrimitive)?.content?.toIntOrNull() ?: 0, "word")))
            } catch (e: Exception) { toast("$n: ${e.message}") }
        }
        busy = ""; load(1)
    } }
    fun slice(method: String) {
        val go = { scope.launch {
            busy = if (method == "ai") "The AI is reading your material and slicing it. This can take a minute…" else "Slicing by headings…"
            try { val r = a.send("POST", "/study/courses/$id/slice", buildJsonObject { put("notes", notes); put("method", method) }, PlanOutWrap.serializer())
                  plan = r.plan; dirty = false; step = 3; scroll.scrollTo(0) } catch (e: Exception) { toast(e.message.orEmpty()) }
            busy = ""
        }; Unit }
        if (dirty) ask = Ask(tl("Slice again?"), tl("Your renames, merges and removals in the current outline are replaced."), tl("Slice again"), yes = go) else go()
    }
    fun edit(f: (MutableList<app.zigora.data.PUnit>) -> Unit) { val p = plan ?: return; val u = p.units.toMutableList(); f(u); plan = StudyPlan(u.filter { it.topics.isNotEmpty() }); dirty = true }
    suspend fun savePlan() { val p = plan ?: return
        plan = a.send("PUT", "/study/courses/$id/plan", json.encodeToJsonElement(StudyPlan.serializer(), p), PlanOutWrap.serializer()).plan; dirty = false }
    fun finish() = scope.launch {
        busy = "Building your course…"
        try {
            if (dirty) savePlan()
            try { a.raw("POST", "/study/courses/$id/finish", buildJsonObject {}); toast(tl("Your course is ready")); onMain(done) }
            catch (e: ApiError) {
                if (e.code != 409) throw e
                busy = ""
                ask = Ask(tl("Replace the course's topics?"), tl("Finishing again builds the topics from this outline. Progress and quiz results on the old topics are removed."), tl("Replace topics"), true) {
                    scope.launch { busy = "Building your course…"
                        try { a.raw("POST", "/study/courses/$id/finish", buildJsonObject { put("replace", true) }); toast(tl("Your course is ready")); onMain(done) } catch (x: Exception) { toast(x.message.orEmpty()) }
                        busy = "" }
                }
            }
        } catch (e: Exception) { toast(e.message.orEmpty()) }
        if (ask == null) busy = ""
    }
    val cc = c; val st = step
    Page(cc?.title ?: tl("Set up your course"), if (st != null) tl("Set up · step {step}{v} of 4", "step" to st, "v" to 1) else "", back, scroll = scroll) {
        if (cc == null || st == null) { Busy(); return@Page }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            STEPS.forEachIndexed { i, s -> Text((if (i < st) "✓ " else "${i + 1}. ") + tl(s), fontWeight = if (i == st) FontWeight.Bold else FontWeight.Normal,
                                                 color = if (i <= st) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelLarge) }
        }
        if (busy.isNotEmpty()) Panel { Text(tl(busy), fontWeight = FontWeight.SemiBold) }
        when (st) {
            1 -> {
                SectionTitle(tl("Add your material"))
                Quiet(tl("PDF, Word (.docx), or .txt and .md files, up to {MAX_FILE_MB} MB each. Add several and they are joined in the order you add them. You can also paste text.", "MAX_FILE_MB" to MAX_FILE_MB) +
                      if (cc.ocr_available) tl(" Scanned PDFs are read with text recognition, a few seconds a page.") else tl(" Scanned PDFs can't be read on this server yet."))
                Button(enabled = busy.isEmpty(), onClick = { picker.launch(arrayOf("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown")) },
                       modifier = Modifier.fillMaxWidth()) { Icon(Icons.Outlined.Upload, null); Text("  " + tl("Choose files")) }
                OutlinedTextField(text, { text = it }, Modifier.fillMaxWidth().heightIn(min = 140.dp), label = { Text(tl("Or paste text")) },
                                  placeholder = { Text(tl("Paste notes here. Leave an empty line between paragraphs; lines starting with # become headings.")) })
                OutlinedButton(enabled = busy.isEmpty() && text.isNotBlank(), modifier = Modifier.fillMaxWidth(), onClick = { scope.launch {
                    busy = "Adding…"
                    try { val r = a.raw("POST", "/study/courses/$id/text", buildJsonObject { put("text", text) }) as JsonObject; text = ""
                          toast(tl("{n} added", "n" to pl((r["words"] as? JsonPrimitive)?.content?.toIntOrNull() ?: 0, "word"))) } catch (e: Exception) { toast(e.message.orEmpty()) }
                    busy = ""; load(1)
                } }) { Text(tl("Add this text")) }
                if (cc.sources.isNotEmpty()) {
                    SectionTitle(tl("Your material ·") + " " + pl(cc.sources.sumOf { it.words }, "word"))
                    cc.sources.forEachIndexed { i, x ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) { Text(x.name)
                                Quiet(if (x.status.isNotEmpty()) sourceLine(x) else "${x.kind.uppercase()} · ${pl(x.words, "word")} · ${pl(x.paras, "paragraph")}") }
                            IconButton(onClick = { ask = Ask(tl("Remove this material?"), tl("Its text is taken out of the course. Any outline already made is cleared."), tl("Remove"), true) {
                                scope.launch { try { a.raw("DELETE", "/study/courses/$id/sources/$i"); load(1) } catch (e: Exception) { toast(e.message.orEmpty()) } } }
                            }) { Icon(Icons.Outlined.Delete, tl("Remove {name}", "name" to x.name)) }
                        }
                    }
                    Button(enabled = !cc.reading, onClick = { step = 2 }, modifier = Modifier.fillMaxWidth()) {
                        Text(if (cc.reading) tl("Reading scanned pages…") else tl("Next: slice it into topics"))
                    }
                }
            }
            2 -> {
                SectionTitle(tl("How should it be sliced?"))
                Quiet(tl("The AI groups your {n} into units and the smallest topics that make sense on their own. It keeps your own words; it only decides where each topic starts and ends and what to call it.",
                         "n" to pl(cc.paragraphs, "paragraph")))
                OutlinedTextField(notes, { notes = it }, Modifier.fillMaxWidth().heightIn(min = 100.dp), label = { Text(tl("Notes for the AI")) }, placeholder = { Text(tl(NOTES_HINT)) })
                AiNote(cc.ai_available, cc.ai_left, cc.ai_own_key)
                val aiOk = cc.ai_available && cc.ai_left != 0
                if (aiOk) Button(enabled = busy.isEmpty(), onClick = { slice("ai") }, modifier = Modifier.fillMaxWidth()) { Text(tl("Slice with AI")) }
                else OutlinedButton(enabled = false, onClick = {}, modifier = Modifier.fillMaxWidth()) { Text(tl("Slice with AI")) }
                if (aiOk) OutlinedButton(enabled = busy.isEmpty(), onClick = { slice("headings") }, modifier = Modifier.fillMaxWidth()) { Text(tl("Slice by headings instead (no AI)")) }
                else Button(enabled = busy.isEmpty(), onClick = { slice("headings") }, modifier = Modifier.fillMaxWidth()) { Text(tl("Slice by headings instead (no AI)")) }
                TextButton(onClick = { step = 1 }) { Text(tl("Back to material")) }
            }
            else -> plan?.let { p ->
                val flat = p.units.flatMap { it.topics }
                SectionTitle(tl("Check the outline"))
                Quiet(pl(p.units.size, "unit") + tl(", {n}{v}. Rename anything, merge a topic into the next one, or remove one you don't need. Not right? Change the notes and slice again.",
                                                    "n" to pl(flat.size, "topic"), "v" to if (cc.sliced_by == "headings") tl(" · sliced by headings") else ""))
                p.units.forEachIndexed { ui, u ->
                    Panel {
                        OutlinedTextField(u.title, { v -> edit { it[ui] = it[ui].copy(title = v) } }, Modifier.fillMaxWidth(), singleLine = true, label = { Text(tl("Unit {v} title", "v" to ui + 1)) },
                                          textStyle = MaterialTheme.typography.titleMedium)
                        u.topics.forEachIndexed { ti, t ->
                            val last = ui == p.units.size - 1 && ti == u.topics.size - 1
                            Column(Modifier.padding(top = 10.dp)) {
                                OutlinedTextField(t.title, { v -> edit { it[ui] = it[ui].copy(topics = it[ui].topics.toMutableList().also { l -> l[ti] = l[ti].copy(title = v) }) } },
                                                  Modifier.fillMaxWidth(), singleLine = true, label = { Text(tl("Topic title")) })
                                Quiet((if (t.summary.isNotEmpty()) t.summary + " · " else "") + pl(t.words, "word"))
                                if (t.excerpt.isNotEmpty()) Text(t.excerpt + if (t.excerpt.length >= 280) "…" else "", style = MaterialTheme.typography.bodySmall, maxLines = 4)
                                Row {
                                    TextButton(onClick = { scope.launch {
                                        try { val r = a.raw("GET", "/study/courses/$id/preview?start=${t.from}&end=${t.to}") as JsonObject
                                              peek = t.title to ((r["content"] as? JsonPrimitive)?.content.orEmpty()) } catch (e: Exception) { toast(e.message.orEmpty()) }
                                    } }) { Text(tl("Read it all")) }
                                    if (!last) TextButton(onClick = { edit { us ->  // this topic takes in the next one, wherever that is
                                        val pos = us.flatMapIndexed { a2, x -> x.topics.indices.map { b -> a2 to b } }; val k = pos.indexOf(ui to ti); val (na, nb) = pos[k + 1]
                                        val nx = us[na].topics[nb]
                                        us[ui] = us[ui].copy(topics = us[ui].topics.toMutableList().also { l -> l[ti] = l[ti].copy(to = nx.to, words = l[ti].words + nx.words) })
                                        us[na] = us[na].copy(topics = us[na].topics.toMutableList().also { l -> l.removeAt(nb) })
                                    } }) { Text(tl("Merge with next")) }
                                    if (flat.size > 1) TextButton(onClick = { edit { us -> us[ui] = us[ui].copy(topics = us[ui].topics.toMutableList().also { l -> l.removeAt(ti) }) } }) { Text(tl("Remove")) }
                                }
                            }
                        }
                    }
                }
                SectionTitle(tl("Slice it differently"))
                OutlinedTextField(notes, { notes = it }, Modifier.fillMaxWidth().heightIn(min = 100.dp), label = { Text(tl("Notes for the AI")) }, placeholder = { Text(tl(NOTES_HINT)) })
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(enabled = busy.isEmpty(), onClick = { slice("ai") }, modifier = Modifier.weight(1f)) { Text(tl("Slice again with AI")) }
                    OutlinedButton(enabled = busy.isEmpty(), onClick = { step = 1 }, modifier = Modifier.weight(1f)) { Text(tl("Change material")) }
                }
                Button(enabled = busy.isEmpty(), onClick = { finish() }, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Filled.Check, null); Text("  " + tl("Finish: build my course")) }
                if (dirty) OutlinedButton(enabled = busy.isEmpty(), modifier = Modifier.fillMaxWidth(), onClick = { scope.launch {
                    try { savePlan(); toast(tl("Outline saved")) } catch (e: Exception) { toast(e.message.orEmpty()) }
                } }) { Text(tl("Save outline and finish later")) }
            }
        }
    }
    peek?.let { (t, body) -> ModalBottomSheet(onDismissRequest = { peek = null }) {
        Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 24.dp).verticalScroll(rememberScrollState())) {
            Text(t, style = MaterialTheme.typography.titleLarge); Md(body); TextButton(onClick = { peek = null }) { Text(tl("Close")) }
        }
    } }
    AskDialog(ask) { ask = null }
}

private const val STAR_HELP = "★ topic completed · ★★ quiz passed · ★★★ mastered (90%+ in a quiz)"
private val AREA_LABEL = mapOf("strong" to "Strong", "getting_there" to "Getting there", "needs_study" to "Revisit")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudyCourseScreen(id: Int, back: () -> Unit, setup: () -> Unit, openTopic: (Int) -> Unit, review: (StudyQuiz) -> Unit) {
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast()
    var tick by remember { mutableIntStateOf(0) }
    val d = rememberLoad("study-course", id, tick) { get("/study/courses/$id", StudyCourseFull.serializer()) }
    val p = (rememberLoad("study-progress", id, tick) { get("/study/courses/$id/progress", StudyProgressOut.serializer()) }.state as? Load.Ok)?.value
    var ren by remember { mutableStateOf<String?>(null) }
    var find by rememberSaveable { mutableStateOf("") }
    var ask by remember { mutableStateOf<Ask?>(null) }
    val c = (d.state as? Load.Ok)?.value
    Page(c?.title ?: tl("Course"), c?.takeIf { it.status == "ready" }?.let { if (it.mine) tl("Your course") else tl("Shared by {owner}", "owner" to it.owner) }.orEmpty(), back) {
        Loaded(d) { cc ->
            if (cc.status != "ready") {
                Quiet(tl("This course is being set up."))
                if (cc.can_edit) Button(onClick = setup) { Text(tl("Continue the setup")) }
                return@Loaded
            }
            val all = cc.units.flatMap { it.topics }; val done = all.count { it.status == "completed" }; val next = all.firstOrNull { it.status != "completed" }
            Panel {
                Quiet(pl(all.size, "topic"))
                if (cc.reviews_due > 0) OutlinedButton(onClick = { scope.launch {
                    try { val q = a.send("POST", "/study/courses/$id/review", null, StudyQuiz.serializer()); onMain { review(q) } } catch (e: Exception) { toast(e.message.orEmpty()) }
                } }, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Filled.Refresh, null); Text("  " + tl("Look again at {n}", "n" to pl(cc.reviews_due, "topic"))) }
                if (p != null && p.quizzed > 0) Quiet(tl("Quiz average {average}% over {n}.", "average" to p.average, "n" to pl(p.quizzed, "topic")) + if (p.summary.isNotEmpty()) " " + p.summary else "")
                next?.let { n -> val go = { openTopic(n.id) }; val label = (if (done > 0) tl("Continue") else tl("Start")) + ": " + n.title
                    if (cc.reviews_due > 0) OutlinedButton(onClick = go, Modifier.fillMaxWidth()) { Text(label, maxLines = 1) } else Button(onClick = go, Modifier.fillMaxWidth()) { Text(label, maxLines = 1) } }
                Quiet(tl(STAR_HELP), Modifier.padding(top = 8.dp))
            }
            if (all.size > 12) OutlinedTextField(find, { find = it }, Modifier.fillMaxWidth(), singleLine = true, leadingIcon = { Icon(Icons.Outlined.Search, null) }, placeholder = { Text(tl("Find a topic")) })
            val q = find.trim().lowercase()
            val rows = cc.units.flatMap { u -> u.topics.filter { q.isEmpty() || q in it.title.lowercase() || q in it.summary.lowercase() }.map { u to it } }
            Paged(rows, key = "$id/$q") { (u, t) ->
                val i = rows.indexOfFirst { it.second.id == t.id }
                if (i == 0 || rows[i - 1].first.id != u.id) SectionTitle(u.title)
                RowLink(t.title + (if (t.stars > 0) "  " + "★".repeat(t.stars) else "") + (if (t.due) "  ·  " + tl("Review due") else ""),
                        t.summary + (t.best?.let { tl("{v}best quiz {best}%", "v" to if (t.summary.isNotEmpty()) " · " else "", "best" to it) } ?: ""), { openTopic(t.id) })
            }
            if (p != null && p.areas.isNotEmpty()) {
                SectionTitle(tl("From your quizzes")); Quiet(tl("Your best quiz score in each topic, weakest first."))
                Paged(p.areas, key = "ar") { ar -> RowLink(ar.title + "  ·  " + tl(AREA_LABEL[ar.status].orEmpty()), tl("Best quiz {percent}%", "percent" to ar.percent), ar.topic_id?.let { { openTopic(it) } }) { ScoreBar(ar.percent) } }
            }
            if (cc.can_edit) {
                SectionTitle(tl("Course settings"))
                Text(tl("Who can study it"), style = MaterialTheme.typography.labelLarge)
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    listOf("private" to tl("Only me"), "program" to tl("My classmates")).forEachIndexed { i, (k, l) ->
                        SegmentedButton(selected = cc.share == k, shape = SegmentedButtonDefaults.itemShape(i, 2), onClick = { if (cc.share != k) scope.launch {
                            try { a.raw("PUT", "/study/courses/$id", buildJsonObject { put("share", k) })
                                  toast(if (k == "program") tl("Classmates in your program can now study it") else tl("Only you can see it now")); tick++ } catch (e: Exception) { toast(e.message.orEmpty()) }
                        } }) { Text(l) }
                    }
                }
                Quiet(if (cc.share == "program") tl("Students in your program can open it and take their own quizzes. Only you can change it.") else tl("Private: only you can see it."))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { ren = cc.title }, Modifier.weight(1f)) { Text(tl("Rename")) }
                    OutlinedButton(onClick = { ask = Ask(tl("Change the setup?"), tl("You go back to the outline. Your topics stay as they are until you finish the setup again."), tl("Change the setup")) {
                        scope.launch { try { a.raw("POST", "/study/courses/$id/reopen"); onMain(setup) } catch (e: Exception) { toast(e.message.orEmpty()) } } } }, Modifier.weight(1f)) { Text(tl("Change the setup")) }
                }
                OutlinedButton(onClick = { ask = Ask(tl("Delete “{title}”?", "title" to cc.title), tl("Its topics, your progress and your quiz results are removed. This can't be undone."), tl("Delete course"), true) {
                    scope.launch { try { a.raw("DELETE", "/study/courses/$id"); toast(tl("Course deleted")); onMain(back) } catch (e: Exception) { toast(e.message.orEmpty()) } } }
                }, Modifier.fillMaxWidth()) { Text(tl("Delete course"), color = MaterialTheme.colorScheme.error) }
            }
        }
    }
    ren?.let { r -> ModalBottomSheet(onDismissRequest = { ren = null }) {
        Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(tl("Rename course"), style = MaterialTheme.typography.titleLarge)
            OutlinedTextField(r, { ren = it }, Modifier.fillMaxWidth(), singleLine = true, label = { Text(tl("Course name")) })
            Button(enabled = r.isNotBlank(), onClick = { scope.launch {
                try { a.raw("PUT", "/study/courses/$id", buildJsonObject { put("title", r) }); ren = null; tick++ } catch (e: Exception) { toast(e.message.orEmpty()) }
            } }, modifier = Modifier.fillMaxWidth()) { Text(tl("Save")) }
            TextButton(onClick = { ren = null }) { Text(tl("Cancel")) }
        }
    } }
    AskDialog(ask) { ask = null }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudyTopicScreen(id: Int, back: () -> Unit, go: (Int) -> Unit, quiz: (StudyQuiz) -> Unit) {
    LearnClock()  // a lite person's learning minutes
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast()
    var tick by remember { mutableIntStateOf(0) }
    val d = rememberLoad("study-topic", id, tick) { get("/study/topics/$id", STopicFull.serializer()) }
    var tab by rememberSaveable(id) { mutableIntStateOf(0) }
    var ex by remember(id) { mutableStateOf<Answer?>(null) }
    var busy by remember { mutableStateOf("") }
    var ed by remember { mutableStateOf<Pair<String, String>?>(null) }
    var ask by remember { mutableStateOf<Ask?>(null) }
    var completed by remember(id) { mutableStateOf<Boolean?>(null) }
    val t = (d.state as? Load.Ok)?.value
    fun make(kind: String) = scope.launch {
        busy = kind
        try { val q = a.send("POST", "/study/topics/$id/quizzes", buildJsonObject { put("kind", kind) }, StudyQuiz.serializer()); onMain { quiz(q) } } catch (e: Exception) { toast(e.message.orEmpty()) }
        busy = ""
    }
    Page(t?.title ?: tl("Topic"), t?.let { tl("{course} › {unit} · {position} of {total}", "course" to it.course, "unit" to it.unit, "position" to it.position, "total" to it.total) }.orEmpty(), back) {
        Loaded(d) { x ->
            val noAi = !x.ai_available || x.ai_left == 0
            PrimaryTabRow(selectedTabIndex = tab) { listOf(tl("Notes"), tl("Explain")).forEachIndexed { i, l -> Tab(selected = tab == i, onClick = { tab = i }, text = { Text(l) }) } }
            if (tab == 0) WebContent(x.content)
            else ex?.let { e -> if (e.cached) Quiet(tl("Saved explanation · no AI request used")); WebContent(e.text) }
                ?: if (x.has_explain || !noAi) Button(enabled = busy.isEmpty(), onClick = { scope.launch {
                       busy = "explain"; try { ex = a.get("/study/topics/$id/explain", Answer.serializer()) } catch (e: Exception) { toast(e.message.orEmpty()) }; busy = ""
                   } }) { Text(if (busy == "explain") tl("Thinking…") else tl("Explain it to me")) }
                   else AiNote(x.ai_available, x.ai_left, x.ai_own_key)
            SectionTitle(tl("Check yourself"))
            AiNote(x.ai_available, x.ai_left, x.ai_own_key)
            Button(enabled = busy.isEmpty() && !noAi, onClick = { make("mcq") }, modifier = Modifier.fillMaxWidth()) { Text(if (busy == "mcq") tl("Writing questions…") else tl("5 quick questions")) }
            OutlinedButton(enabled = busy.isEmpty() && !noAi, onClick = { make("quiz") }, modifier = Modifier.fillMaxWidth()) { Text(if (busy == "quiz") tl("Writing the quiz…") else tl("Full quiz · 10")) }
            Quiet(tl("Quick check: 5 practice MCQs with the answer right after each one; 4 right marks the topic completed. Full quiz: 10 questions scored at the end; pass it for ★★, score 90% for ★★★. New questions every time, and the topic comes back for review before you forget it."))
            if (x.attempts.isNotEmpty()) {
                SectionTitle(tl("Your results here"))
                Paged(x.attempts, key = id) { r -> RowLink((if (r.kind == "quiz") tl("Quiz") else tl("Practice MCQs")) + " · ${r.score} / ${r.total} · ${r.percent}%", stamp(r.at), null) { ScoreBar(r.percent) } }
            }
            val isDone = completed ?: x.completed
            val mark = { on: Boolean -> scope.launch {
                try { a.raw("PUT", "/study/topics/$id/progress", buildJsonObject { put("completed", on) }); completed = on
                      toast(if (on) tl("Marked as completed") else tl("Marked as not completed")) } catch (e: Exception) { toast(e.message.orEmpty()) }
            }; Unit }
            if (isDone) OutlinedButton(onClick = { mark(false) }, Modifier.fillMaxWidth().padding(top = 8.dp)) { Text(tl("Mark as not completed")) }
            else Button(onClick = { mark(true) }, Modifier.fillMaxWidth().padding(top = 8.dp)) { Icon(Icons.Filled.Check, null); Text("  " + tl("Mark as completed")) }
            Row(Modifier.fillMaxWidth()) {
                x.prev?.let { p -> TextButton(onClick = { go(p.id) }) { Text("‹ " + tl("Previous")) } }
                androidx.compose.foundation.layout.Spacer(Modifier.weight(1f))
                x.next?.let { n -> TextButton(onClick = { go(n.id) }) { Text(tl("Next") + " ›") } }
            }
            if (x.can_edit) Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { ed = x.title to x.content }, Modifier.weight(1f)) { Text(tl("Edit topic")) }
                OutlinedButton(onClick = { ask = Ask(tl("Delete “{title}”?", "title" to x.title), tl("The topic, your progress and your checks on it are removed. This can't be undone."), tl("Delete topic"), true) {
                    scope.launch { try { a.raw("DELETE", "/study/topics/$id"); toast(tl("Topic deleted")); onMain(back) } catch (e: Exception) { toast(e.message.orEmpty()) } } } }, Modifier.weight(1f)) { Text(tl("Delete topic")) }
            }
        }
    }
    ed?.let { (title, content) -> ModalBottomSheet(onDismissRequest = { ed = null }) {
        Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 24.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(tl("Edit topic"), style = MaterialTheme.typography.titleLarge)
            OutlinedTextField(title, { ed = it to content }, Modifier.fillMaxWidth(), singleLine = true, label = { Text(tl("Title")) })
            OutlinedTextField(content, { ed = title to it }, Modifier.fillMaxWidth().heightIn(min = 260.dp), label = { Text(tl("Text")) })
            Quiet(tl("Markdown works: # for headings, - for lists, **bold**. Your progress and stars stay."))
            Button(enabled = title.isNotBlank() && content.isNotBlank(), modifier = Modifier.fillMaxWidth(), onClick = { scope.launch {
                try { a.raw("PUT", "/study/topics/$id", buildJsonObject { put("title", title); put("content", content) }); ed = null; ex = null; toast(tl("Topic saved")); tick++ }
                catch (e: Exception) { toast(e.message.orEmpty()) }
            } }) { Text(tl("Save")) }
            TextButton(onClick = { ed = null }) { Text(tl("Cancel")) }
        }
    } }
    AskDialog(ask) { ask = null }
}
