package app.zigora.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
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
import androidx.compose.ui.input.nestedscroll.nestedScroll
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

/** a lite person's learning minutes: while a learning screen is open and the app is in front, one tick a minute (the server counts each minute once) */
@Composable
fun LearnClock() {
    val a = api(); val lifecycle = androidx.lifecycle.compose.LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(Unit) {
        val lite = runCatching { a.get("/ai/status", app.zigora.data.AiStatus.serializer()).plan == "lite" }.getOrDefault(false)
        while (lite) {
            kotlinx.coroutines.delay(60_000)
            if (lifecycle.currentState.isAtLeast(androidx.lifecycle.Lifecycle.State.RESUMED)) runCatching { a.raw("POST", "/me/plan/tick") }
        }
    }
}

/** the web app's own words (its English is the key), in the reader's language from the same translation files, with {name} values filled in */
fun tl(key: String, vararg v: Pair<String, Any?>): String = app.zigora.data.I18n.t(key, v.associate { (k, x) -> k to x.toString() })
/** "1 topic", "3 topics": each form is its own phrase to translate, as on the web */
fun pl(n: Int, w: String) = tl(if (n == 1) "{n} $w" else "{n} " + (if (w == "quiz") "quizzes" else w + "s"), "n" to n)

/** a time from the server, with the date, in the phone's own language */
fun stamp(iso: String): String = runCatching {
    java.time.format.DateTimeFormatter.ofLocalizedDateTime(java.time.format.FormatStyle.MEDIUM, java.time.format.FormatStyle.SHORT)
        .format(java.time.OffsetDateTime.parse(iso).atZoneSameInstant(java.time.ZoneId.systemDefault()))
}.getOrDefault(iso.take(16).replace('T', ' '))

/** a percentage as a thin bar */
@Composable
fun ScoreBar(v: Int?) = androidx.compose.material3.LinearProgressIndicator(progress = { (v ?: 0).coerceIn(0, 100) / 100f }, Modifier.fillMaxWidth().padding(top = 4.dp))

/** a screen with a title (and a line under it), a back arrow and scrolling content */
@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun Page(title: String, sub: String = "", back: (() -> Unit)? = null, actions: @Composable androidx.compose.foundation.layout.RowScope.() -> Unit = {},
         scroll: androidx.compose.foundation.ScrollState = androidx.compose.foundation.rememberScrollState(), content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
    val bar = androidx.compose.material3.TopAppBarDefaults.pinnedScrollBehavior()
    androidx.compose.material3.Scaffold(Modifier.nestedScroll(bar.nestedScrollConnection), topBar = {
        androidx.compose.material3.TopAppBar(scrollBehavior = bar, actions = actions,
            title = { Column { Text(title, maxLines = 1, overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis)
                               if (sub.isNotEmpty()) Text(sub, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1) } },
            navigationIcon = { if (back != null) IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } })
    }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(scroll).padding(horizontal = 16.dp).padding(bottom = 24.dp),
               verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
    }
}

/** the app's one list row, the same on every screen: an optional mark on the left (40dp), a title, a quieter line, anything [extra],
 *  and on the right [trailing] or an arrow when the row opens something */
@Composable
fun ListRow(title: String, sub: String = "", onClick: (() -> Unit)? = null, leading: (@Composable () -> Unit)? = null,
            trailing: (@Composable () -> Unit)? = null, extra: @Composable () -> Unit = {}) = Panel(onClick = onClick) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        if (leading != null) { Box(Modifier.size(40.dp), contentAlignment = Alignment.Center) { leading() }; androidx.compose.foundation.layout.Spacer(Modifier.size(14.dp)) }
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            if (sub.isNotEmpty()) Text(sub, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 2.dp))
            extra()
        }
        when {
            trailing != null -> trailing()
            onClick != null -> Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** a round mark for the start of a row: an icon on the brand's soft colour */
@Composable
fun RowIcon(icon: androidx.compose.ui.graphics.vector.ImageVector) = Box(
    Modifier.size(40.dp).background(MaterialTheme.colorScheme.primaryContainer, androidx.compose.foundation.shape.CircleShape),
    contentAlignment = Alignment.Center) { Icon(icon, null, tint = MaterialTheme.colorScheme.onPrimaryContainer, modifier = Modifier.size(22.dp)) }

@Composable
fun RowLink(title: String, sub: String = "", onClick: (() -> Unit)?, extra: @Composable () -> Unit = {}) = ListRow(title, sub, onClick, extra = extra)

/** a short note at the bottom of the screen, like the web's toast */
@Composable
fun rememberToast(): (String) -> Unit {
    val ctx = LocalContext.current
    val main = remember { android.os.Handler(android.os.Looper.getMainLooper()) }  // a note can come from any thread a request finished on
    return remember(ctx) { { m: String -> if (m.isNotEmpty()) main.post { android.widget.Toast.makeText(ctx, m, android.widget.Toast.LENGTH_SHORT).show() } } }
}

/** "are you sure?" before something that can't be undone, as the web asks */
class Ask(val title: String, val body: String, val ok: String, val danger: Boolean = false, val yes: () -> Unit)

@Composable
fun AskDialog(ask: Ask?, close: () -> Unit) {
    if (ask == null) return
    androidx.compose.material3.AlertDialog(onDismissRequest = close, title = { Text(ask.title) }, text = { Text(ask.body) },
        confirmButton = { TextButton(onClick = { close(); ask.yes() }) { Text(ask.ok, color = if (ask.danger) MaterialTheme.colorScheme.error else androidx.compose.ui.graphics.Color.Unspecified) } },
        dismissButton = { TextButton(onClick = close) { Text(tl("Cancel")) } })
}

/** navigation after a request: always on the main thread, wherever the request finished */
suspend fun onMain(f: () -> Unit) = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.Main) { f() }
