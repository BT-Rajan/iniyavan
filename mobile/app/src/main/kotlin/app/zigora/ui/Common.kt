package app.zigora.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.zigora.R
import app.zigora.ZigoraApp
import app.zigora.data.Api
import com.mikepenz.markdown.coil3.Coil3ImageTransformerImpl
import com.mikepenz.markdown.m3.Markdown
import com.mikepenz.markdown.m3.markdownTypography

/** a screen's data: loading, loaded, or the server's message with a way to try again */
sealed interface Load<out T> {
    data object Loading : Load<Nothing>
    data class Ok<T>(val value: T) : Load<T>
    data class Failed(val message: String) : Load<Nothing>
}

@Composable fun app(): ZigoraApp = LocalContext.current.applicationContext as ZigoraApp
@Composable fun api(): Api = app().api

/** loads once per key; reload() asks again */
class Loader<T>(val state: Load<T>, val reload: () -> Unit)
@Composable
fun <T> rememberLoad(vararg keys: Any?, fetch: suspend Api.() -> T): Loader<T> {
    val a = api(); var tick by remember { mutableIntStateOf(0) }
    var state by remember(*keys) { mutableStateOf<Load<T>>(Load.Loading) }
    LaunchedEffect(*keys, tick) {
        if (state !is Load.Ok) state = Load.Loading
        state = try { Load.Ok(a.fetch()) } catch (e: Exception) { Load.Failed(e.message ?: "Something went wrong") }
    }
    return Loader(state) { tick++ }
}

@Composable
fun <T> Loaded(l: Loader<T>, content: @Composable (T) -> Unit) = when (val s = l.state) {
    is Load.Loading -> Busy()
    is Load.Failed -> Problem(s.message, l.reload)
    is Load.Ok -> content(s.value)
}

@Composable fun Busy(modifier: Modifier = Modifier) =
    Box(modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }

@Composable
fun Problem(message: String, retry: (() -> Unit)? = null) = Column(Modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
    Text(message, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
    if (retry != null) FilledTonalButton(onClick = retry, modifier = Modifier.padding(top = 12.dp)) { Text(stringResource(R.string.try_again)) }
}

@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier) =
    Text(text, style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.primary, modifier = modifier.padding(top = 20.dp, bottom = 8.dp))

@Composable
fun Quiet(text: String, modifier: Modifier = Modifier) =
    Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = modifier)

/** a tonal card, the app's main surface */
@Composable
fun Panel(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, content: @Composable () -> Unit) {
    val colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)
    val shape = RoundedCornerShape(20.dp)
    if (onClick != null) Card(onClick = onClick, modifier = modifier.fillMaxWidth(), shape = shape, colors = colors) { Column(Modifier.padding(16.dp)) { content() } }
    else Card(modifier = modifier.fillMaxWidth(), shape = shape, colors = colors) { Column(Modifier.padding(16.dp)) { content() } }
}

/** Markdown from the server; its images (uploads) are loaded from the college's server */
@Composable
fun Md(text: String, modifier: Modifier = Modifier) {
    val base = api().base
    val fixed = remember(text, base) { text.replace("](/api/", "]($base/api/").replace("src=\"/api/", "src=\"$base/api/") }
    val t = MaterialTheme.typography // headings sized for reading on a phone, not for a poster
    Markdown(content = fixed, modifier = modifier, imageTransformer = Coil3ImageTransformerImpl,
             typography = markdownTypography(h1 = t.titleLarge, h2 = t.titleLarge, h3 = t.titleMedium, h4 = t.titleSmall, h5 = t.titleSmall, h6 = t.titleSmall))
}

/** "think, then tap": the answer stays hidden until asked for */
@Composable
fun Reveal(label: String, content: @Composable () -> Unit) {
    var open by rememberSaveable { mutableStateOf(false) }
    if (!open) TextButton(onClick = { open = true }) { Text(label) }
    AnimatedVisibility(open) { Column(Modifier.padding(top = 4.dp)) { content() } }
}

const val PAGE = 10

/** every list longer than ten is shown ten at a time, with a pager under it */
@Composable
fun <T> Paged(rows: List<T>, key: Any? = null, item: @Composable (T) -> Unit) {
    var page by rememberSaveable(key, rows.size) { mutableIntStateOf(0) }
    val pages = (rows.size + PAGE - 1) / PAGE
    val at = page.coerceIn(0, maxOf(0, pages - 1))
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        rows.drop(at * PAGE).take(PAGE).forEach { item(it) }
        if (pages > 1) Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center) {
            IconButton(onClick = { page = at - 1 }, enabled = at > 0) { Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, stringResource(R.string.previous_page)) }
            Text(stringResource(R.string.page_of, at + 1, pages), style = MaterialTheme.typography.labelLarge)
            IconButton(onClick = { page = at + 1 }, enabled = at < pages - 1) { Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, stringResource(R.string.next_page)) }
        }
    }
}

@Composable
fun Dot(letter: String, color: androidx.compose.ui.graphics.Color) = Box(
    Modifier.size(40.dp).padding(0.dp), contentAlignment = Alignment.Center
) {
    androidx.compose.foundation.Canvas(Modifier.size(40.dp)) { drawCircle(color) }
    Text(letter.take(1).uppercase(), color = androidx.compose.ui.graphics.Color.White, fontWeight = FontWeight.SemiBold)
}

@Composable fun Gap(h: Int = 12) = androidx.compose.foundation.layout.Spacer(Modifier.height(h.dp))
