@file:OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)

package app.zigora.ui

import android.content.Context
import android.graphics.Bitmap
import android.graphics.ImageDecoder
import android.net.Uri
import android.util.Base64
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.PhotoLibrary
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.core.net.toUri
import app.zigora.R
import app.zigora.data.AiStatus
import app.zigora.data.Answer
import app.zigora.data.PhotoText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.ByteArrayOutputStream
import java.io.File

/** the photo as a JPEG of at most 1568 px, re-encoded so it carries no location or camera details */
private suspend fun shrink(ctx: Context, uri: Uri): Pair<Bitmap, String> = withContext(Dispatchers.IO) {
    val bmp = ImageDecoder.decodeBitmap(ImageDecoder.createSource(ctx.contentResolver, uri)) { d, info, _ ->
        val k = minOf(1f, 1568f / maxOf(info.size.width, info.size.height)); d.setTargetSize((info.size.width * k).toInt(), (info.size.height * k).toInt())
        d.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
    }
    val out = ByteArrayOutputStream(); bmp.compress(Bitmap.CompressFormat.JPEG, 85, out)
    bmp to "data:image/jpeg;base64," + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
}

/** Snap a question, a paragraph or a diagram. The server reads the text first (nothing leaves); the student checks it and asks.
 *  Only that text goes to the AI, unless they say it is about a diagram: then the photo goes to the vision AI, which can see it. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PhotoScreen(shared: String, back: () -> Unit) {
    val a = api(); val ctx = LocalContext.current; val res = LocalResources.current; val scope = rememberCoroutineScope()
    val st = rememberLoad("ai") { runCatching { get("/ai/status", AiStatus.serializer()) }.getOrDefault(AiStatus()) }
    var bmp by remember { mutableStateOf<Bitmap?>(null) }
    var image by remember { mutableStateOf<String?>(null) }
    var text by rememberSaveable { mutableStateOf("") }
    var q by rememberSaveable { mutableStateOf("") }
    var diagram by rememberSaveable { mutableStateOf(false) }
    var reading by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var msg by remember { mutableStateOf("") }
    val answers = remember { mutableStateListOf<Pair<String, Answer>>() }
    fun use(uri: Uri) = scope.launch {
        msg = ""; reading = true; answers.clear()
        try {
            val (b, data) = shrink(ctx, uri); bmp = b; image = data
            text = a.send("POST", "/photo/read", buildJsonObject { put("image", data) }, PhotoText.serializer()).text
        } catch (e: Exception) { msg = e.message ?: res.getString(R.string.photo_unreadable) }
        reading = false
    }
    val shot = remember { File(ctx.cacheDir, "photos").apply { mkdirs() }.let { File(it, "shot.jpg") } }
    val shotUri = remember { FileProvider.getUriForFile(ctx, ctx.packageName + ".files", shot) }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok -> if (ok) use(shotUri) }
    val gallery = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { it?.let(::use) } // Android's photo picker: no storage permission needed
    LaunchedEffect(shared) { if (shared.isNotEmpty()) use(shared.toUri()) }
    val vision = (st.state as? Load.Ok)?.value?.vision == true

    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.ask_photo)) },
        navigationIcon = { IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } }) }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Quiet(stringResource(R.string.photo_lead))
            androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {  // buttons go to a new line rather than squeeze their text
                Button(onClick = { camera.launch(shotUri) }) { Icon(Icons.Outlined.CameraAlt, null); Text("  " + stringResource(R.string.take_photo)) }
                FilledTonalButton(onClick = { gallery.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }) {
                    Icon(Icons.Outlined.PhotoLibrary, null); Text("  " + stringResource(R.string.choose_photo)) }
            }
            bmp?.let { Image(it.asImageBitmap(), null, Modifier.fillMaxWidth().heightIn(max = 280.dp).clip(RoundedCornerShape(16.dp)), contentScale = ContentScale.Fit) }
            if (reading) { Busy(); Quiet(stringResource(R.string.reading_photo)) }
            if (image != null && !reading) {
                OutlinedTextField(text, { text = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.text_in_photo)) },
                    supportingText = { Text(stringResource(R.string.text_in_photo_hint)) }, minLines = 3, maxLines = 10)
                if (vision) ListItem(headlineContent = { Text(stringResource(R.string.about_diagram)) }, supportingContent = { Text(stringResource(R.string.about_diagram_hint)) },
                                     trailingContent = { Switch(diagram, { diagram = it }) })
                OutlinedTextField(q, { q = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.your_question)) }, minLines = 2)
                Button(enabled = !busy && q.isNotBlank(), onClick = {
                    scope.launch {
                        busy = true; msg = ""
                        try {
                            val r = a.send("POST", "/photo/ask", buildJsonObject { put("question", q.trim()); put("text", text); put("diagram", diagram && vision); if (diagram && vision) put("image", image) }, Answer.serializer())
                            answers.add(0, q.trim() to r); q = ""
                        } catch (e: Exception) { msg = e.message.orEmpty() }
                        busy = false
                    }
                }) { Text(stringResource(if (busy) R.string.thinking else R.string.ask)) }
            }
            if (msg.isNotEmpty()) Text(msg, color = MaterialTheme.colorScheme.error)
            answers.forEach { (question, r) -> Panel { Text(question, style = MaterialTheme.typography.titleSmall); SelectionContainer { Md(r.text) } } }
        }
    }
}
