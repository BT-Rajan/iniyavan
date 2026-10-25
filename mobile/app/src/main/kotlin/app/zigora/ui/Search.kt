package app.zigora.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import app.zigora.R
import app.zigora.data.Answer
import app.zigora.data.SearchOut
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.net.URLEncoder

/** The college's own topics first; the AI only when they don't cover it, and its answer is saved for everyone who asks the same. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchScreen(initial: String, back: () -> Unit, openTopic: (Int) -> Unit, openPhoto: () -> Unit) {
    val a = api(); val scope = rememberCoroutineScope(); val kb = LocalSoftwareKeyboardController.current
    var q by rememberSaveable { mutableStateOf(initial) }
    var found by remember { mutableStateOf<SearchOut?>(null) }
    var answer by remember { mutableStateOf<Answer?>(null) }
    var busy by remember { mutableStateOf(false) }
    var asking by remember { mutableStateOf(false) }
    var msg by remember { mutableStateOf("") }
    val focus = remember { FocusRequester() }
    fun look() = scope.launch {
        if (q.trim().length < 2) return@launch
        kb?.hide(); busy = true; msg = ""; answer = null
        try { found = a.get("/search?limit=25&q=" + URLEncoder.encode(q.trim(), "UTF-8"), SearchOut.serializer()) } catch (e: Exception) { msg = e.message.orEmpty() }
        busy = false
    }
    fun askAi(refresh: Boolean) = scope.launch {
        asking = true; msg = ""
        try { answer = a.send("POST", "/search/ai", buildJsonObject { put("q", q.trim()); put("refresh", refresh) }, Answer.serializer()) } catch (e: Exception) { msg = e.message.orEmpty() }
        asking = false
    }
    LaunchedEffect(initial) { if (initial.isNotBlank()) look() else focus.requestFocus() }
    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.tab_search)) },
        navigationIcon = { IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } }, actions = {
        IconButton(onClick = openPhoto) { Icon(Icons.Outlined.CameraAlt, stringResource(R.string.ask_photo)) } }) }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(q, { q = it }, Modifier.fillMaxWidth().focusRequester(focus), singleLine = true, placeholder = { Text(stringResource(R.string.search_hint)) },
                leadingIcon = { Icon(Icons.Outlined.Search, null) },
                trailingIcon = { if (q.isNotEmpty()) IconButton(onClick = { q = ""; found = null; answer = null }) { Icon(Icons.Filled.Clear, stringResource(R.string.clear)) } },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search), keyboardActions = KeyboardActions(onSearch = { look() }))
            if (busy) Busy()
            if (msg.isNotEmpty()) Quiet(msg)
            found?.let { f ->
                if (f.results.isEmpty()) Quiet(stringResource(R.string.nothing_in_topics))
                else {
                    SectionTitle(stringResource(R.string.in_your_topics))
                    Paged(f.results, key = f.q) { h ->
                        ListItem(modifier = Modifier.clickableRounded { openTopic(h.id) }, colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                            headlineContent = { Text(h.title) }, overlineContent = { Text(listOf(h.course, h.unit).filter { it.isNotEmpty() }.joinToString(" › ")) },
                            supportingContent = { Text(h.snippet, maxLines = 3) })
                    }
                }
                Gap(8)
                val ans = answer
                if (ans == null) {
                    if (!f.confident || f.results.isEmpty()) Quiet(stringResource(R.string.not_covered))
                    FilledTonalButton(onClick = { askAi(false) }, enabled = !asking) {
                        Icon(Icons.Outlined.AutoAwesome, null); Text("  " + stringResource(if (asking) R.string.thinking else R.string.ask_ai))
                    }
                } else Panel {
                    if (ans.cached) Quiet(stringResource(R.string.saved_answer))
                    SelectionContainer { Md(ans.text) }
                    if (!ans.support) TextButton(onClick = { askAi(true) }, enabled = !asking) { Text(stringResource(if (asking) R.string.thinking else R.string.explain_differently)) }
                }
            }
        }
    }
}
