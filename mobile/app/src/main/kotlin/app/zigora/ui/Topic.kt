@file:OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package app.zigora.ui

import android.annotation.SuppressLint
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material.icons.outlined.OpenInFull
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SecondaryTabRow
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import app.zigora.R
import app.zigora.data.AiStatus
import app.zigora.data.Bookmarked
import app.zigora.data.Learning
import app.zigora.data.Me
import app.zigora.data.Step
import app.zigora.data.Highlights
import app.zigora.data.StudyQuiz
import app.zigora.data.SessionOut
import app.zigora.data.ReadOut
import app.zigora.data.SessionItem
import app.zigora.data.TopicFull
import app.zigora.data.Translation
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

private fun JsonObject.str(k: String) = (this[k] as? JsonPrimitive)?.takeIf { it.isString }?.content.orEmpty()
private fun JsonObject.list(k: String) = (this[k] as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.content }.orEmpty()

val PICKS = listOf("why", "example", "exam", "check")
@Composable fun stepLabel(k: String) = stringResource(when (k) {
    "why" -> R.string.step_why; "example" -> R.string.step_example; "exam" -> R.string.step_exam; "check" -> R.string.step_check; else -> R.string.step_simpler
})

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TopicScreen(id: Int, me: Me, back: () -> Unit, jump: (Int) -> Unit, openReader: (Int) -> Unit, openPractice: (Int) -> Unit, openMaterial: (Int, String) -> Unit) {
    val a = api(); val res = LocalResources.current; val scope = rememberCoroutineScope(); val snack = remember { SnackbarHostState() }
    val topic = rememberLoad("topic", id) { get("/topics/$id", TopicFull.serializer()) }
    val ai = rememberLoad("ai") { runCatching { get("/ai/status", AiStatus.serializer()) }.getOrDefault(AiStatus()) }
    val t = (topic.state as? Load.Ok)?.value
    var marked by remember(t) { mutableStateOf(t?.bookmarked ?: false) }
    var status by remember(t) { mutableStateOf(t?.status ?: "not_started") }
    var known by remember(id) { mutableStateOf(emptyList<String>()) }
    var upNext by remember(id) { mutableStateOf<List<SessionItem>?>(null) }
    var practising by remember { mutableStateOf("") }
    LaunchedEffect(id) { runCatching { known = a.send("POST", "/topics/$id/read", null, ReadOut.serializer()).known } } // opening a topic starts it; it never completes it
    LearnClock()
    val scroll = TopAppBarDefaults.enterAlwaysScrollBehavior()
    val student = me.role == "student"
    Scaffold(Modifier.nestedScroll(scroll.nestedScrollConnection), snackbarHost = { SnackbarHost(snack) }, topBar = {
        TopAppBar(scrollBehavior = scroll, title = {
            Column { Text(t?.title.orEmpty(), maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (t != null) Text(listOf(t.course, t.unit).filter { it.isNotEmpty() }.joinToString(" › "), style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis) }
        }, navigationIcon = { IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } },
        actions = {
            if (t != null && me.role != "admin") IconButton(onClick = {
                val on = !marked; marked = on
                scope.launch {
                    try { a.send(if (on) "PUT" else "DELETE", "/topics/$id/bookmark", null, Bookmarked.serializer()); snack.showSnackbar(res.getString(if (on) R.string.bookmarked else R.string.bookmark_removed)) }
                    catch (e: Exception) { marked = !on; snack.showSnackbar(e.message.orEmpty()) }
                }
            }) { Icon(if (marked) Icons.Filled.Bookmark else Icons.Outlined.BookmarkBorder, stringResource(if (marked) R.string.remove_bookmark else R.string.bookmark)) }
        })
    }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(bottom = 32.dp)) {
            Loaded(topic) { t ->
                val aiOn = (ai.state as? Load.Ok)?.value?.available == true
                val aiOff = (ai.state as? Load.Ok)?.value?.off == true  // no parent's or teacher's key: the notes only
                if (aiOn) Steps(id, student)
                Body(t, me, aiOn, aiOff, known, openReader = { openReader(id) }, openMaterial = { openMaterial(t.course_id, t.course) })
                if (student && aiOn) {
                    SectionTitle(stringResource(R.string.test_yourself))
                    androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {  // buttons go to a new line rather than squeeze their text
                        listOf("mcq" to R.string.five_quick, "quiz" to R.string.full_quiz_10).forEach { (k, l) ->
                            OutlinedButton(enabled = practising.isEmpty(), onClick = { scope.launch {
                                practising = k
                                try { openPractice(a.send("POST", "/topics/$id/practice", buildJsonObject { put("kind", k) }, StudyQuiz.serializer()).id) }
                                catch (e: Exception) { snack.showSnackbar(e.message.orEmpty()) }
                                practising = ""
                            } }) { Text(stringResource(if (practising == k) (if (k == "mcq") R.string.writing_questions else R.string.writing_quiz) else l)) }
                        }
                    }
                    Quiet(stringResource(R.string.practice_note), Modifier.padding(top = 4.dp))
                }
                if (student) {
                    Gap(16)
                    Panel {
                        Text(stringResource(if (status == "completed") R.string.you_marked_learned else R.string.not_marked_yet), style = MaterialTheme.typography.bodyMedium)
                        t.learning_due_at?.let { Quiet(stringResource(R.string.teachers_date, day(it))) }
                        TextButton(onClick = {
                            val on = status != "completed"
                            scope.launch {
                                try { status = a.send(if (on) "PUT" else "DELETE", "/topics/$id/complete", null, Learning.serializer()).status
                                      snack.showSnackbar(res.getString(if (on) R.string.marked_completed else R.string.marked_not_completed))
                                      upNext = null
                                      if (on) runCatching { a.get("/me/session", SessionOut.serializer()).session?.items }.getOrNull()  // today's session leads on to its next part
                                          ?.takeIf { items -> items.any { it.id == id && it.kind != "review" && it.src != "study" } }?.let { upNext = it } }
                                catch (e: Exception) { snack.showSnackbar(e.message.orEmpty()) }
                            }
                        }) { Text(stringResource(if (status == "completed") R.string.undo else R.string.ive_learned_this)) }
                    }
                }
                upNext?.let { items ->
                    Gap(12)
                    Panel {
                        Text(stringResource(R.string.todays_session_done, items.count { it.done }, items.size), style = MaterialTheme.typography.titleSmall)
                        val nx = items.firstOrNull { !it.done }
                        when {
                            nx == null -> Quiet(stringResource(R.string.session_all_done))
                            nx.kind != "review" && nx.src != "study" -> Button(onClick = { jump(nx.id) }) { Text(stringResource(R.string.next_colon) + " " + nx.title) }
                            else -> OutlinedButton(onClick = back) { Text(stringResource(R.string.back_for_next_part) + " " + nx.title) }
                        }
                    }
                }
                t.nav?.takeIf { it.total > 1 }?.let { n ->
                    Gap(16)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        OutlinedButton(onClick = { n.prev?.let { jump(it.id) } }, enabled = n.prev != null, modifier = Modifier.weight(1f)) {
                            Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, null); Text(n.prev?.title ?: stringResource(R.string.previous), maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                        Text("${n.position} / ${n.total}", style = MaterialTheme.typography.labelMedium)
                        Button(onClick = { n.next?.let { jump(it.id) } }, enabled = n.next != null, modifier = Modifier.weight(1f)) {
                            Text(n.next?.title ?: stringResource(R.string.next), maxLines = 1, overflow = TextOverflow.Ellipsis); Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null)
                        }
                    }
                }
            }
        }
    }
}

/** The gist and one curious question, then short steps the student picks. Each reply is a few lines and saved for everyone; the notes stay the reference. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Steps(id: Int, student: Boolean) {
    val a = api(); val scope = rememberCoroutineScope()
    val gist = rememberLoad("gist", id) { get("/topics/$id/ai/gist", Step.serializer()) }
    val g = (gist.state as? Load.Ok)?.value
    if (gist.state is Load.Failed) return // without AI the page is the notes
    val trail = remember(id) { mutableStateListOf<Triple<String, JsonObject, Int?>>() }
    var busy by remember(id) { mutableStateOf("") }
    var err by remember(id) { mutableStateOf("") }
    var showGist by rememberSaveable(id) { mutableStateOf(false) }
    fun step(k: String) = scope.launch {
        busy = k; err = ""
        try { val r = a.get("/topics/$id/ai/$k", Step.serializer()); r.data?.let { d -> trail.removeAll { it.first == k }; trail.add(Triple(k, d, r.id)) } }
        catch (e: Exception) { err = e.message.orEmpty() }
        busy = ""
    }
    Panel(Modifier.padding(top = 8.dp).animateContentSize()) {
        if (g?.data == null) { Busy(); return@Panel }
        val d = g.data
        val qFirst = g.you?.question_first == true && !showGist && d.str("hook").isNotEmpty()
        if (qFirst) {
            Text(stringResource(R.string.question_first), style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
            Hook(d.str("hook"), d.str("hook_answer"))
            TextButton(onClick = { showGist = true }) { Text(stringResource(R.string.show_gist)) }
        } else {
            Text(stringResource(R.string.the_gist), style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
            d.list("points").forEach { p -> Row(Modifier.padding(top = 6.dp)) { Text("•  "); Md(p) } }
            if (d.str("hook").isNotEmpty() && !showGist) Hook(d.str("hook"), d.str("hook_answer"))
            FlagLink("topic", g.id, id)
        }
        trail.forEach { (k, sd, rid) -> StepCard(id, rid, k, sd, student, onSimpler = if (trail.any { it.first == "simpler" }) null else ({ step("simpler") })) }
        if (err.isNotEmpty()) Quiet(err, Modifier.padding(top = 8.dp))
        val order = (g.you?.order?.takeIf { it.isNotEmpty() } ?: PICKS).filter { k -> trail.none { it.first == k } }
        if (order.isNotEmpty()) FlowRow(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            order.forEach { k -> AssistChip(onClick = { step(k) }, enabled = busy.isEmpty(), label = { Text(if (busy == k) stringResource(R.string.thinking) else stepLabel(k)) }) }
        }
        if (busy == "simpler") Quiet(stringResource(R.string.thinking))
    }
}

@Composable
private fun Hook(q: String, answer: String) = Column(Modifier.padding(top = 12.dp)) {
    Text(q, style = MaterialTheme.typography.titleMedium)
    if (answer.isNotEmpty()) Reveal(stringResource(R.string.think_then_tap)) { Md(answer) }
}

@Composable
private fun StepCard(id: Int, rid: Int?, k: String, d: JsonObject, student: Boolean, onSimpler: (() -> Unit)?) = Column(Modifier.padding(top = 16.dp)) {
    Text(stepLabel(k), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.secondary)
    if (k in listOf("why", "example", "simpler")) {
        Md(d.str("text"))
        if (d.str("hook").isNotEmpty()) Text(d.str("hook"), style = MaterialTheme.typography.bodyLarge, modifier = Modifier.padding(top = 6.dp))
    } else {
        Md(d.str("question"))
        Reveal(stringResource(if (k == "exam") R.string.show_model_answer else R.string.show_answer)) {
            Md(d.str("answer"))
            if (d.str("tip").isNotEmpty()) Quiet(stringResource(R.string.examiners_look_for, d.str("tip")))
            if (k == "check" && student) SelfMark(id, onSimpler)
        }
    }
    FlagLink("topic", rid, id)
}

/** after a quick check: the student's own private "I had it" / "Not quite"; never a score */
@Composable
private fun SelfMark(id: Int, onSimpler: (() -> Unit)?) {
    val a = api(); val scope = rememberCoroutineScope()
    var got by rememberSaveable(id) { mutableStateOf("") }
    fun mark(o: String) { got = o; scope.launch { runCatching { a.raw("POST", "/topics/$id/check-result", buildJsonObject { put("outcome", o) }) } } }
    when (got) {
        "knew" -> Quiet(stringResource(R.string.nice_stretch))
        "not_yet" -> Column { Quiet(stringResource(R.string.takes_a_few_goes)); if (onSimpler != null) TextButton(onClick = onSimpler) { Text(stringResource(R.string.explain_more_simply)) } }
        else -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            FilterChip(selected = false, onClick = { mark("knew") }, label = { Text(stringResource(R.string.i_had_it)) })
            FilterChip(selected = false, onClick = { mark("not_yet") }, label = { Text(stringResource(R.string.not_quite)) })
            Quiet(stringResource(R.string.only_you_see))
        }
    }
}

/** the notes (the reference), and AI help on request: Explain and a sample answer */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Body(t: TopicFull, me: Me, aiOn: Boolean, aiOff: Boolean, known: List<String>, openReader: () -> Unit, openMaterial: () -> Unit) {
    var tab by rememberSaveable(t.id) { mutableIntStateOf(0) }
    Gap(12)
    if (aiOff) { Quiet(tl(AI_OFF), Modifier.padding(bottom = 8.dp)); Notes(t, me, aiOn, openReader, openMaterial); return }  // no Explain or Sample answer tabs
    SecondaryTabRow(selectedTabIndex = tab, containerColor = MaterialTheme.colorScheme.surface) {
        listOf(R.string.tab_notes, R.string.tab_explain, R.string.tab_answer).forEachIndexed { i, s -> Tab(tab == i, onClick = { tab = i }, text = { Text(stringResource(s), maxLines = 2, textAlign = androidx.compose.ui.text.style.TextAlign.Center) }) }
    }
    Gap(8)
    when (tab) {
        0 -> Notes(t, me, aiOn, openReader, openMaterial)
        1 -> { if (known.isNotEmpty()) Quiet(stringResource(R.string.already_covered) + " " + known.joinToString(", "), Modifier.padding(bottom = 8.dp)); AiAnswer(t.id, "explain", aiOn, R.string.explain_it, t.my_notes != null) }
        else -> { Outline(t.id, aiOn); AiAnswer(t.id, "answer", aiOn, R.string.full_sample_answer, t.my_notes != null) }
    }
}

@Composable
private fun Notes(t: TopicFull, me: Me, aiOn: Boolean, openReader: () -> Unit, openMaterial: () -> Unit) {
    val a = api(); val res = LocalResources.current; val scope = rememberCoroutineScope()
    var mine by rememberSaveable(t.id) { mutableStateOf(false) }
    var tr by remember(t.id) { mutableStateOf<Translation?>(null) }
    var trMsg by remember(t.id) { mutableStateOf("") }
    val content = t.content.orEmpty(); val inter = t.content_format == "interactive"
    if (content.isNotEmpty()) FilledTonalButton(onClick = openReader, modifier = Modifier.padding(bottom = 8.dp)) {
        Icon(Icons.Outlined.OpenInFull, null); Text("  " + stringResource(if (inter) R.string.open_interactive else R.string.read_full_screen))
    }
    if (!inter && content.isNotEmpty() && me.lang in listOf("ar", "ta") && aiOn) {
        SingleChoiceSegmentedButtonRow(Modifier.padding(bottom = 8.dp)) {
            SegmentedButton(!mine, onClick = { mine = false }, shape = SegmentedButtonDefaults.itemShape(0, 2)) { Text(stringResource(R.string.original)) }
            SegmentedButton(mine, onClick = {
                mine = true
                if (tr == null) scope.launch {
                    trMsg = res.getString(R.string.translating)
                    trMsg = try { tr = a.get("/topics/${t.id}/translation", Translation.serializer()); "" } catch (e: Exception) { mine = false; e.message.orEmpty() }
                }
            }, shape = SegmentedButtonDefaults.itemShape(1, 2)) { Text(stringResource(R.string.my_language)) }
        }
        if (trMsg.isNotEmpty()) Quiet(trMsg)
    }
    Panel {
        when {
            inter && content.isNotEmpty() -> Quiet(stringResource(R.string.interactive_note_long))
            content.isNotEmpty() -> tr.takeIf { mine }?.let { WebContent(it.content, it.format) } ?: WebContent(content, t.content_format)
            t.my_notes == null -> Quiet(stringResource(R.string.no_notes_yet))
        }
        t.my_notes?.let { SectionTitle(stringResource(R.string.your_notes)); WebContent(it) }
        t.question_pattern?.takeIf { it.isNotBlank() }?.let { SectionTitle(stringResource(R.string.question_pattern)); WebContent(it) }
        t.guideline?.takeIf { it.isNotBlank() }?.let { SectionTitle(stringResource(R.string.answer_guideline)); WebContent(it) }
        if (me.role == "student") TextButton(onClick = openMaterial) { Text(stringResource(if (t.my_notes != null) R.string.update_your_notes else R.string.add_your_notes)) }
    }
    // the reader's highlights in this topic, as under the web's notes
    val hl = rememberLoad("tophl", t.id) { get("/topics/${t.id}/highlights", Highlights.serializer()).items }
    (hl.state as? Load.Ok)?.value?.takeIf { it.isNotEmpty() }?.let { list ->
        SectionTitle(stringResource(R.string.your_highlights_n, list.size))
        Paged(list, key = t.id) { h ->
            HlItem(h, onGo = openReader, onExplain = null, onSaved = { hl.reload() }, topicId = t.id,
                   onDrop = { scope.launch { runCatching { a.raw("DELETE", "/me/highlights/${h.id}") }; hl.reload() } })
        }
    }
}

@Composable
private fun AiAnswer(tid: Int, kind: String, aiOn: Boolean, label: Int, ownNotes: Boolean) {
    val a = api(); val scope = rememberCoroutineScope()
    var ans by remember(tid, kind) { mutableStateOf<Step?>(null) }
    var busy by remember(tid, kind) { mutableStateOf(false) }
    var msg by remember(tid, kind) { mutableStateOf("") }
    if (!aiOn) { Quiet(stringResource(R.string.ai_unavailable)); return }
    ans?.let { s ->
        if (s.cached) Quiet(stringResource(R.string.saved_answer))
        if (s.own_notes) Quiet(stringResource(R.string.written_with_notes))
        Panel { WebContent(s.text) }
        FlagLink("topic", s.id, tid)
        return
    }
    FilledTonalButton(enabled = !busy, onClick = {
        scope.launch { busy = true; msg = ""; try { ans = a.get("/topics/$tid/ai/$kind", Step.serializer()) } catch (e: Exception) { msg = e.message.orEmpty() }; busy = false }
    }) { Icon(Icons.Outlined.AutoAwesome, null); Text("  " + stringResource(if (busy) R.string.thinking else label)) }
    if (ownNotes) Quiet(stringResource(R.string.uses_own_notes), Modifier.padding(top = 4.dp))
    if (msg.isNotEmpty()) Quiet(msg, Modifier.padding(top = 8.dp))
}

/** the shape of a full answer: what to write, and where the marks are */
@Composable
private fun Outline(tid: Int, aiOn: Boolean) {
    if (!aiOn) return
    val o = rememberLoad("outline", tid) { get("/topics/$tid/ai/outline", Step.serializer()) }
    val d = (o.state as? Load.Ok)?.value?.data ?: return
    Panel(Modifier.padding(bottom = 12.dp)) {
        Text(stringResource(R.string.answer_skeleton), style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary)
        d.list("points").forEachIndexed { i, p -> Row(Modifier.padding(top = 6.dp)) { Text("${i + 1}.  "); Md(p) } }
        if (d.str("marks").isNotEmpty()) Quiet(stringResource(R.string.marks, d.str("marks")), Modifier.padding(top = 8.dp))
    }
}
