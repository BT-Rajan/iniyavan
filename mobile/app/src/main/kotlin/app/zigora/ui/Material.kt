package app.zigora.ui

import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.UploadFile
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import app.zigora.R
import app.zigora.data.Material
import app.zigora.data.Preview
import app.zigora.data.Source
import app.zigora.data.json
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.net.URLEncoder

const val MAX_FILE_MB = 20

/** a file's name and bytes from the system picker, or a message when it is too big */
suspend fun readPicked(ctx: android.content.Context, uri: Uri): Pair<String, ByteArray?> = withContext(Dispatchers.IO) {
    var name = "file"; var size = -1L
    ctx.contentResolver.query(uri, null, null, null, null)?.use { c -> if (c.moveToFirst()) {
        c.getColumnIndex(OpenableColumns.DISPLAY_NAME).takeIf { it >= 0 }?.let { name = c.getString(it) ?: name }
        c.getColumnIndex(OpenableColumns.SIZE).takeIf { it >= 0 }?.let { size = c.getLong(it) } } }
    if (size > MAX_FILE_MB * 1024L * 1024L) name to null else name to ctx.contentResolver.openInputStream(uri)?.use { it.readBytes() }
}

@Composable
fun sourceLine(x: Source): String = when (x.status) {
    "reading" -> if (x.done > 0) stringResource(R.string.reading_scanned_n, x.done, x.pages) else stringResource(R.string.waiting_scanned, x.pages)
    "failed" -> app.zigora.data.I18n.srv(x.error)
    else -> (if (x.kind == "scan") stringResource(R.string.scanned_read) + " · " else "") + stringResource(R.string.n_words, x.words) + (if (x.note.isNotEmpty()) " · ${x.note}" else "")
}

/** Your material: your own notes or book chapters, filed under the college's syllabus for this course, private to you. Same steps as the web. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MyMaterialScreen(cid: Int, name: String, back: () -> Unit) {
    val a = api(); val ctx = LocalContext.current; val res = LocalResources.current; val scope = rememberCoroutineScope(); val snack = remember { SnackbarHostState() }
    val base = "/courses/$cid/my-material"
    var v by remember { mutableStateOf<Material?>(null) }
    var busy by remember { mutableStateOf("") }
    var paste by remember { mutableStateOf<String?>(null) }
    var pick by remember { mutableStateOf<Int?>(null) }
    var confirmRemove by remember { mutableStateOf(false) }
    val open = remember { mutableStateMapOf<Int, String>() }
    suspend fun load() { v = a.get(base, Material.serializer()) }
    LaunchedEffect(cid) { try { load() } catch (e: Exception) { snack.showSnackbar(e.message.orEmpty()); back() } }
    LaunchedEffect(v?.reading) { while (v?.reading == true) { delay(3000); runCatching { load() } } } // while scanned pages are being read
    fun run(label: String, done: String? = null, block: suspend () -> kotlinx.serialization.json.JsonElement?) = scope.launch {
        busy = label
        try { val r = block(); if (r is JsonObject && r.containsKey("syllabus")) v = json.decodeFromJsonElement(Material.serializer(), r) else load(); done?.let { snack.showSnackbar(it) } }
        catch (e: Exception) { snack.showSnackbar(e.message.orEmpty()) }
        busy = ""
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        uris.forEach { uri -> run("file") {
            val (n, bytes) = readPicked(ctx, uri)
            if (bytes == null) { snack.showSnackbar(res.getString(R.string.file_too_big, n, MAX_FILE_MB.toString())); null }
            else { val r = a.upload("$base/files?name=" + URLEncoder.encode(n, "UTF-8"), bytes) as? JsonObject
                   if ((r?.get("status") as? JsonPrimitive)?.content == "reading") snack.showSnackbar(res.getString(R.string.scanned_reading_now, n))
                   else if (!n.lowercase().endsWith(".pdf")) snack.showSnackbar(res.getString(R.string.added_name, n)); null }
        } }
    }
    Scaffold(snackbarHost = { SnackbarHost(snack) }, topBar = { TopAppBar(title = { Column { Text(stringResource(R.string.your_material)); Text(name, style = MaterialTheme.typography.labelMedium) } },
        navigationIcon = { IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } }) }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            val m = v ?: run { Busy(); return@Column }
            Quiet(stringResource(R.string.material_lead))
            SectionTitle(stringResource(R.string.material_step1))
            if (m.sources.isEmpty()) Quiet(stringResource(R.string.no_files_yet, MAX_FILE_MB) + " " + stringResource(if (m.ocr_available) R.string.scanned_ok else R.string.scanned_not_here))
            Paged(m.sources) { x ->
                val i = m.sources.indexOf(x)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) { Text(x.name); Quiet(sourceLine(x)) }
                    IconButton(enabled = busy.isEmpty(), onClick = { run("drop") { a.raw("DELETE", "$base/sources/$i") } }) { Icon(Icons.Filled.Close, stringResource(R.string.remove_name, x.name)) }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(enabled = busy.isEmpty(), onClick = { picker.launch(arrayOf("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown")) }) {
                    Icon(Icons.Outlined.UploadFile, null); Text(" " + stringResource(if (busy == "file") R.string.reading else R.string.add_a_file)) }
                OutlinedButton(enabled = busy.isEmpty(), onClick = { paste = "" }) { Text(stringResource(R.string.paste_text)) }
            }
            if (m.sources.isNotEmpty()) {
                SectionTitle(stringResource(R.string.material_step2))
                if (m.reading) Quiet(stringResource(R.string.scanned_still_reading))
                val noAi = !m.ai_available || m.ai_left == 0
                val matched = res.getString(R.string.matched_check)
                if (m.ai_available) Button(enabled = busy.isEmpty() && !noAi && !m.reading, onClick = { run("ai", matched) { a.raw("POST", "$base/match", buildJsonObject { put("method", "ai") }) } }) {
                    Icon(Icons.Outlined.AutoAwesome, null); Text(" " + stringResource(if (busy == "ai") R.string.matching else R.string.match_ai)) }
                OutlinedButton(enabled = busy.isEmpty() && !m.reading, onClick = { run("headings", matched) { a.raw("POST", "$base/match", buildJsonObject { put("method", "headings") }) } }) {
                    Text(stringResource(if (busy == "headings") R.string.matching else if (m.ai_available) R.string.match_headings_no_ai else R.string.match_headings)) }
                if (noAi) Quiet((if (m.ai_available) stringResource(R.string.no_ai_left_today) + " " else "") + stringResource(R.string.headings_work_best))
            }
            if (m.sections.isNotEmpty()) {
                SectionTitle(stringResource(R.string.material_step3))
                val names = m.syllabus.flatMap { u -> u.topics.map { it.id to it.title } }.toMap(); val filed = m.sections.mapNotNull { it.topic_id }.toSet()
                val missing = m.syllabus.flatMap { u -> u.topics.filter { it.id !in filed }.map { it.title } }
                Quiet(stringResource(R.string.notes_cover, m.covered, m.topics) + if (missing.isNotEmpty()) " " + stringResource(R.string.not_covered_yet, missing.take(6).joinToString(", ") + if (missing.size > 6) " +" + (missing.size - 6) else "") else "")
                Paged(m.sections) { x ->
                    val i = m.sections.indexOf(x)
                    Panel {
                        if (x.heading.isNotEmpty()) Text(x.heading, style = MaterialTheme.typography.titleSmall) else Text("“" + x.excerpt.take(80) + (if (x.excerpt.length > 80) "…" else "") + "”")
                        Quiet(stringResource(R.string.part_n_words, i + 1, x.words))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            AssistChip(onClick = { pick = i }, label = { Text(x.topic_id?.let { names[it] } ?: stringResource(R.string.left_out)) })
                            TextButton(enabled = busy.isEmpty(), onClick = { pick = i }) { Text(stringResource(if (x.topic_id != null) R.string.change else R.string.file_it)) }
                            DropdownMenu(expanded = pick == i, onDismissRequest = { pick = null }) {
                                DropdownMenuItem(text = { Text(stringResource(R.string.not_in_syllabus)) }, onClick = { pick = null; file(i, null, m) { b -> run("sec") { a.raw("PUT", "$base/sections", b) } } })
                                m.syllabus.forEach { u ->
                                    DropdownMenuItem(text = { Text(u.name, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary) }, onClick = {}, enabled = false)
                                    u.topics.forEach { tp -> DropdownMenuItem(text = { Text(tp.title) }, onClick = { pick = null; file(i, tp.id, m) { b -> run("sec") { a.raw("PUT", "$base/sections", b) } } }) }
                                }
                            }
                        }
                        TextButton(onClick = {
                            if (open.containsKey(x.from)) open.remove(x.from)
                            else scope.launch { runCatching { open[x.from] = a.get("$base/preview?start=${x.from}&end=${x.to}", Preview.serializer()).content }.onFailure { snack.showSnackbar(it.message.orEmpty()) } }
                        }) { Text(stringResource(if (open.containsKey(x.from)) R.string.hide else R.string.read_it)) }
                        open[x.from]?.let { WebContent(it) }
                    }
                }
                Button(enabled = busy.isEmpty() && filed.isNotEmpty(), onClick = { run("save", res.getString(R.string.saved_open_topic)) { a.raw("POST", "$base/save") } }) {
                    Text(stringResource(if (m.saved_at != null) R.string.save_again else R.string.save_to_topics)) }
                m.saved_at?.let { Quiet(stringResource(R.string.last_saved_rebuild, day(it))) }
            }
            if (m.sources.isNotEmpty()) TextButton(enabled = busy.isEmpty(), onClick = { confirmRemove = true }) { Text(stringResource(R.string.remove_my_material), color = MaterialTheme.colorScheme.error) }
        }
    }
    paste?.let { text -> AlertDialog(onDismissRequest = { paste = null }, title = { Text(stringResource(R.string.paste_text)) },
        text = { OutlinedTextField(text, { paste = it }, Modifier.fillMaxWidth(), minLines = 6, placeholder = { Text(stringResource(R.string.paste_hint)) }) },
        confirmButton = { TextButton(enabled = text.isNotBlank() && busy.isEmpty(), onClick = { run("paste", res.getString(R.string.added)) { a.raw("POST", "$base/text", buildJsonObject { put("text", text) }) }; paste = null }) { Text(stringResource(R.string.add)) } },
        dismissButton = { TextButton(onClick = { paste = null }) { Text(stringResource(R.string.cancel)) } }) }
    if (confirmRemove) AlertDialog(onDismissRequest = { confirmRemove = false }, title = { Text(stringResource(R.string.remove_material_q)) }, text = { Text(stringResource(R.string.remove_material_body)) },
        confirmButton = { TextButton(onClick = { confirmRemove = false; run("del", res.getString(R.string.material_removed)) { a.raw("DELETE", base) } }) { Text(stringResource(R.string.remove)) } },
        dismissButton = { TextButton(onClick = { confirmRemove = false }) { Text(stringResource(R.string.cancel)) } })
}

private fun file(i: Int, tid: Int?, m: Material, send: (JsonObject) -> Unit) = send(buildJsonObject {
    put("sections", JsonArray(m.sections.mapIndexed { k, x -> buildJsonObject { put("from", x.from); put("to", x.to); put("topic_id", if (k == i) tid?.let(::JsonPrimitive) ?: JsonNull else x.topic_id?.let(::JsonPrimitive) ?: JsonNull) } }))
})
