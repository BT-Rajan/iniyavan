package app.zigora.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Flag
import androidx.compose.material.icons.outlined.FormatColorText
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import app.zigora.R
import app.zigora.data.AiStatus
import app.zigora.data.Answer
import app.zigora.data.Doubt
import app.zigora.data.Explained
import app.zigora.data.Highlight
import app.zigora.data.Highlights
import app.zigora.data.TopicFull
import app.zigora.data.json
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.put

val HL_COLORS = linkedMapOf("coral" to Color(0xFFFF9292), "yellow" to Color(0xFFFFD60A), "green" to Color(0xFF50C878), "blue" to Color(0xFF5AA0FF))
private fun JsonObject.s(k: String) = (this[k] as? JsonPrimitive)?.contentOrNull.orEmpty()
private fun JsonObject.i(k: String) = (this[k] as? JsonPrimitive)?.intOrNull

/** The full-screen reader, as on the web: select text to highlight it in a colour; tap a highlight for its colour, Explain, a note or Remove;
 *  "Not clear?" on a short phrase. Interactive topics run full screen with the same highlights, as the web's sandboxed frame does. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReaderScreen(t: TopicFull, close: () -> Unit) {
    val a = api(); val scope = rememberCoroutineScope()
    val list = remember { mutableStateListOf<Highlight>() }
    var ready by remember { mutableStateOf(false) }
    var aiOn by remember { mutableStateOf(false) }
    var panel by remember { mutableStateOf(false) }
    var noteFor by remember { mutableStateOf<Int?>(null) }
    var doubt by remember { mutableStateOf<String?>(null) }
    var exp by remember { mutableStateOf<Triple<Int, String?, String?>?>(null) } // highlight id, text, error (null text and error: thinking)
    var msg by remember { mutableStateOf("") }
    val handle = remember { WebHandle() }
    val inter = t.content_format == "interactive"
    LaunchedEffect(t.id) {
        runCatching { list.addAll(a.get("/topics/${t.id}/highlights", Highlights.serializer()).items) }.onFailure { msg = it.message.orEmpty() }
        aiOn = runCatching { a.get("/ai/status", AiStatus.serializer()).available }.getOrDefault(false); ready = true
    }
    fun explain(id: Int) {
        list.firstOrNull { it.id == id }?.explain?.let { exp = Triple(id, it.text, null); return }
        exp = Triple(id, null, null)
        scope.launch {
            try { val x = a.send("POST", "/me/highlights/$id/explain", null, Explained.serializer()).explain
                  exp = Triple(id, x.text, null); val i = list.indexOfFirst { it.id == id }; if (i >= 0) list[i] = list[i].copy(explain = x) }
            catch (e: Exception) { exp = Triple(id, null, e.message.orEmpty()) }
        }
    }
    fun answer(k: Int?, data: JsonObject) { if (k == null) return; if (inter) handle.toFrame(buildJsonObject { put("zg", 1); put("k", k); data.forEach { (x, v) -> put(x, v) } }) else handle.reply(k, data) }
    val err = buildJsonObject { put("error", 1) }
    fun onEvent(m: JsonObject) {
        val k = m.i("k")
        when (m.s("type")) {
            "ready" -> if (inter) handle.toFrame(buildJsonObject { put("zg", 1); put("type", "init"); put("list", buildJsonArray { list.forEach { h -> add(buildJsonObject { put("id", h.id); put("text", h.text); put("prefix", h.prefix); put("color", h.color) }) } }) })
            "save" -> scope.launch {
                try {
                    val h = a.send("POST", "/topics/${t.id}/highlights", buildJsonObject { put("text", m.s("text").take(5000)); put("prefix", m.s("prefix").takeLast(200)); put("color", m.s("color").ifEmpty { "coral" }) }, Highlight.serializer())
                    list.add(h); answer(k, buildJsonObject { put("id", h.id) }); if (aiOn) explain(h.id)
                } catch (e: Exception) { msg = e.message.orEmpty(); answer(k, err) }
            }
            "remove" -> scope.launch {
                val id = m.i("id") ?: return@launch
                try { a.raw("DELETE", "/me/highlights/$id"); list.removeAll { it.id == id }; answer(k, JsonObject(emptyMap())) } catch (e: Exception) { msg = e.message.orEmpty(); answer(k, err) }
            }
            "update" -> scope.launch {
                val id = m.i("id") ?: return@launch
                try { val h = a.send("PATCH", "/me/highlights/$id", buildJsonObject { put("color", m.s("color")) }, Highlight.serializer())
                      val i = list.indexOfFirst { it.id == id }; if (i >= 0) list[i] = h.copy(explain = list[i].explain); answer(k, JsonObject(emptyMap())) }
                catch (e: Exception) { msg = e.message.orEmpty(); answer(k, err) }
            }
            "note" -> { noteFor = m.i("id"); panel = true }
            "explain" -> if (aiOn) m.i("id")?.let(::explain)
            "doubt" -> { panel = false; doubt = m.s("phrase") }
            "store" -> (m["data"] as? JsonObject)?.let { d -> // the interactive page's own saved data, kept for this person
                val data = JsonObject(d.filterValues { it is JsonPrimitive && it.isString })
                scope.launch { runCatching { a.raw("PUT", "/topics/${t.id}/store", buildJsonObject { put("data", data) }) } }
            }
        }
    }
    fun goTo(id: Int) { if (inter) handle.toFrame(buildJsonObject { put("zg", 1); put("type", "scroll"); put("id", id) }) else handle.scrollTo(id); panel = false }
    fun drop(h: Highlight) = scope.launch {
        try { a.raw("DELETE", "/me/highlights/${h.id}"); list.removeAll { it.id == h.id }
              if (inter) handle.toFrame(buildJsonObject { put("zg", 1); put("type", "unpaint"); put("id", h.id) }) else handle.unpaint(h.id) }
        catch (e: Exception) { msg = e.message.orEmpty() }
    }

    Scaffold(topBar = {
        TopAppBar(navigationIcon = { IconButton(onClick = close) { Icon(Icons.Filled.Close, stringResource(R.string.close)) } },
            title = { Column { Text(t.title, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(listOf(t.course, t.unit).filter { it.isNotEmpty() }.joinToString(" › "), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1) } },
            actions = { TextButton(onClick = { panel = true }) { Icon(Icons.Outlined.FormatColorText, null); Text(" ${list.size}") } })
    }) { pad ->
        Box(Modifier.padding(pad).fillMaxSize()) {
            if (!ready) Busy()
            else if (inter) t.frame_url?.let { InteractivePage(a.base + it, handle, onEvent = ::onEvent) }
            else Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
                Quiet(stringResource(R.string.select_to_highlight), Modifier.padding(vertical = 4.dp))
                WebContent(t.content.orEmpty(), t.content_format, fill = true, highlights = true, list = list.toList(), explain = aiOn,
                           doubtLabel = stringResource(R.string.not_clear), handle = handle, onEvent = ::onEvent)
            }
            if (msg.isNotEmpty()) Card(Modifier.align(Alignment.TopCenter).padding(12.dp)) { Row(verticalAlignment = Alignment.CenterVertically) {
                Text(msg, Modifier.padding(12.dp).weight(1f, false)); IconButton(onClick = { msg = "" }) { Icon(Icons.Filled.Close, stringResource(R.string.close)) } } }
            exp?.let { (id, text, e) ->
                Card(Modifier.align(Alignment.BottomCenter).padding(12.dp).fillMaxWidth().heightIn(max = 360.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerHigh)) {
                    Column(Modifier.verticalScroll(rememberScrollState()).padding(16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(stringResource(R.string.what_this_means), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary, modifier = Modifier.weight(1f))
                            IconButton(onClick = { exp = null }) { Icon(Icons.Filled.Close, stringResource(R.string.close)) }
                        }
                        val q = list.firstOrNull { it.id == id }?.text.orEmpty()
                        Text("“" + q.take(140) + (if (q.length > 140) "…" else "") + "”", style = MaterialTheme.typography.bodyMedium)
                        when { e != null -> Quiet(e); text == null -> Quiet(stringResource(R.string.thinking)); else -> { Md(text); FlagLink("topic", list.firstOrNull { it.id == id }?.explain?.id, t.id) } }
                    }
                }
            }
        }
    }
    if (panel) ModalBottomSheet(onDismissRequest = { panel = false; noteFor = null }) {
        Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 24.dp).verticalScroll(rememberScrollState())) {
            Text(stringResource(R.string.your_highlights), style = MaterialTheme.typography.titleMedium)
            Quiet(stringResource(R.string.highlights_how), Modifier.padding(vertical = 6.dp))
            if (list.isEmpty()) Quiet(stringResource(R.string.none_yet))
            Paged(list.toList(), key = list.size) { h ->
                HlItem(h, focus = noteFor == h.id, onGo = { goTo(h.id) }, onExplain = if (aiOn) ({ panel = false; explain(h.id) }) else null,
                       onSaved = { r -> val i = list.indexOfFirst { it.id == r.id }; if (i >= 0) list[i] = r.copy(explain = list[i].explain); noteFor = null },
                       onDrop = { drop(h) }, topicId = t.id)
            }
        }
    }
    doubt?.let { p -> ModalBottomSheet(onDismissRequest = { doubt = null }) { DoubtBox(t.id, p) { doubt = null } } }
}

/** one highlight: its passage (tap to go to it), where it is, its explanation or "Explain this", and the reader's note */
@Composable
fun HlItem(h: Highlight, where: String = "", focus: Boolean = false, onGo: (() -> Unit)?, onExplain: (() -> Unit)?, onSaved: (Highlight) -> Unit, onDrop: () -> Unit, topicId: Int?) {
    val a = api(); val scope = rememberCoroutineScope()
    var editing by remember(focus) { mutableStateOf(focus) }
    var note by remember(h.id, h.note) { mutableStateOf(h.note) }
    var err by remember { mutableStateOf("") }
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Box(Modifier.width(4.dp).heightIn(min = 40.dp).background(HL_COLORS[h.color] ?: HL_COLORS.getValue("coral")))
        Column(Modifier.weight(1f).padding(start = 10.dp)) {
            if (onGo != null) TextButton(onClick = onGo, contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp)) { Text(h.text, maxLines = 4, overflow = TextOverflow.Ellipsis) }
            else Text(h.text)
            if (where.isNotEmpty()) Quiet(where)
            h.explain?.let { x -> Md(x.text); FlagLink("topic", x.id, h.topic_id ?: topicId) } ?: onExplain?.let { TextButton(onClick = it) { Text(stringResource(R.string.explain_this)) } }
            if (editing) {
                OutlinedTextField(note, { if (it.length <= 2000) note = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.your_note)) })
                if (err.isNotEmpty()) Quiet(err)
                Row { TextButton(onClick = { scope.launch {
                        try { onSaved(a.send("PATCH", "/me/highlights/${h.id}", buildJsonObject { put("note", note) }, Highlight.serializer())); editing = false } catch (e: Exception) { err = e.message.orEmpty() }
                    } }) { Text(stringResource(R.string.save_note)) }
                    TextButton(onClick = { note = h.note; editing = false }) { Text(stringResource(R.string.cancel)) } }
            } else if (h.note.isNotEmpty()) TextButton(onClick = { editing = true }) { Text(h.note) }
            else TextButton(onClick = { editing = true }) { Text(stringResource(R.string.add_a_note)) }
        }
        IconButton(onClick = onDrop) { Icon(Icons.Outlined.Delete, stringResource(R.string.remove_highlight)) }
    }
}

/** "Not clear?" on a phrase: first where it sits in the topic (and in the student's own notes) and a kept answer, all on the server;
 *  only if asked, the AI gets the program, semester, course and topic names and the phrase, never the notes */
@Composable
fun DoubtBox(tid: Int, phrase: String, close: () -> Unit) {
    val a = api(); val scope = rememberCoroutineScope()
    val d = rememberLoad("doubt", tid, phrase) { send("POST", "/topics/$tid/doubt", buildJsonObject { put("phrase", phrase) }, Doubt.serializer()) }
    var ans by remember(phrase) { mutableStateOf<Answer?>(null) }
    var busy by remember { mutableStateOf(false) }
    var err by remember { mutableStateOf("") }
    Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 24.dp).verticalScroll(rememberScrollState())) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.not_clear), style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
            IconButton(onClick = close) { Icon(Icons.Filled.Close, stringResource(R.string.close)) }
        }
        Text("“$phrase”", style = MaterialTheme.typography.bodyLarge)
        Loaded(d) { x ->
            x.where?.let { w -> Quiet(listOf(w.program, w.semester, w.course, w.topic).filter { it.isNotEmpty() }.joinToString(" › ")) }
            SectionTitle(stringResource(R.string.in_your_topic))
            if (x.passage.isNotEmpty()) Text(x.passage) else Quiet(stringResource(R.string.phrase_not_found))
            if (x.my_passage.isNotEmpty()) { SectionTitle(stringResource(R.string.in_your_own_notes)); Text(x.my_passage) }
            val shown = ans ?: x.saved?.let { Answer(text = it, cached = true) }
            if (shown != null) {
                SectionTitle(stringResource(R.string.explained))
                if (shown.cached) Quiet(stringResource(R.string.saved_nothing_sent))
                if (shown.support) Text(shown.text) else Md(shown.text)
            } else {
                Button(enabled = !busy, onClick = { scope.launch {
                    busy = true; err = ""
                    try { ans = a.send("POST", "/topics/$tid/doubt/ask", buildJsonObject { put("phrase", phrase) }, Answer.serializer()) } catch (e: Exception) { err = e.message.orEmpty() }
                    busy = false
                } }) { Text(stringResource(if (busy) R.string.thinking else R.string.still_not_clear)) }
                Quiet(stringResource(R.string.doubt_privacy) + (x.ai_left?.takeIf { it <= 10 }?.let { " " + stringResource(R.string.n_left_today, it) } ?: ""))
                if (err.isNotEmpty()) Quiet(err)
            }
        }
    }
}

/** "This looks wrong?" under an AI answer: a student sends it to their teacher, with an optional reason */
@Composable
fun FlagLink(source: String, id: Int?, topicId: Int?, excerpt: String = "") {
    val a = api(); val scope = rememberCoroutineScope()
    val student = LocalMe.current?.role == "student"
    var st by remember(id) { mutableStateOf("") }
    var why by remember { mutableStateOf("") }
    var err by remember { mutableStateOf("") }
    if (!student) return
    when (st) {
        "sent" -> Quiet(stringResource(R.string.flag_thanks))
        "" -> TextButton(onClick = { st = "open" }) { Icon(Icons.Outlined.Flag, null, Modifier.size(14.dp)); Text(" " + stringResource(R.string.looks_wrong), style = MaterialTheme.typography.labelMedium) }
        else -> Column {
            OutlinedTextField(why, { if (it.length <= 300) why = it }, Modifier.fillMaxWidth(), placeholder = { Text(stringResource(R.string.what_looks_wrong)) }, singleLine = true)
            Row {
                TextButton(onClick = { scope.launch {
                    err = ""
                    try { a.raw("POST", "/ai/flag", buildJsonObject { put("source", source); id?.let { put("id", it) }; topicId?.let { put("topic_id", it) }; put("excerpt", excerpt.take(600)); put("reason", why) }); st = "sent" }
                    catch (e: Exception) { err = e.message.orEmpty() }
                } }) { Text(stringResource(R.string.send_to_teacher)) }
                TextButton(onClick = { st = "" }) { Text(stringResource(R.string.cancel)) }
            }
            if (err.isNotEmpty()) Quiet(err)
        }
    }
}
