package app.zigora.ui

import android.annotation.SuppressLint
import android.content.Intent
import androidx.core.net.toUri
import android.os.Handler
import android.os.Looper
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material.icons.filled.Close
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.webkit.WebViewAssetLoader
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import app.zigora.data.Highlight
import app.zigora.data.json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

private const val READER = "https://appassets.androidplatform.net/reader/reader.html"

/** what the reader page asks for (save, remove, update, note, explain, doubt, changed); answer requests that carry "k" with [WebHandle.reply] */
class WebHandle { var view: WebView? = null
    fun reply(k: Int, data: JsonObject) = view?.evaluateJavascript("window.zgReader&&zgReader.reply($k,$data)", null)
    fun scrollTo(id: Int) = view?.evaluateJavascript("window.zgReader&&zgReader.scrollTo($id)", null)
    fun unpaint(id: Int) = view?.evaluateJavascript("window.zgReader&&zgReader.unpaint($id)", null)
}

private fun hex(c: Color) = String.format("#%08X", c.toArgb()).let { "#" + it.substring(3) + it.substring(1, 3) } // #RRGGBBAA
private fun palette(c: ColorScheme) = buildJsonObject {
    put("tx", hex(c.onSurface)); put("mut", hex(c.onSurfaceVariant)); put("line", hex(c.outlineVariant)); put("s1", hex(c.surface)); put("s2", hex(c.surfaceContainerHigh))
    put("acc", hex(c.primary)); put("acct", hex(c.primary)); put("accbg", hex(c.primaryContainer)); put("bg", hex(c.surface))
}

/** A topic's content or a long AI answer, shown by the web app's own renderer (tables, maths, chemistry) from the reader page packed in the app.
 *  With [highlights] the web's highlighter runs on it too, and every request comes to [onEvent]. Sized to its content unless [fill]. */
@SuppressLint("SetJavaScriptEnabled", "JavascriptInterface", "ModifierParameter")
@Composable
fun WebContent(text: String, format: String = "markdown", modifier: Modifier = Modifier, fill: Boolean = false, highlights: Boolean = false,
               list: List<Highlight> = emptyList(), explain: Boolean = false, doubtLabel: String = "Not clear?", handle: WebHandle? = null,
               onEvent: (JsonObject) -> Unit = {}) {
    val ctx = LocalContext.current; val a = api(); val colors = palette(MaterialTheme.colorScheme)
    val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl; val lang = LocalConfiguration.current.locales[0].language
    val fontScale = LocalConfiguration.current.fontScale
    var height by remember { mutableIntStateOf(1) }
    val events by rememberUpdatedState(onEvent)
    val opts = remember(text, format, colors, highlights, explain, rtl, lang) {
        buildJsonObject {
            put("text", text); put("format", format); put("base", a.base); put("highlights", highlights); put("explain", explain); put("doubtLabel", doubtLabel)
            put("dir", if (rtl) "rtl" else "ltr"); put("lang", lang); put("colors", colors); put("fontScale", fontScale)
            put("list", buildJsonArray { list.forEach { h -> add(buildJsonObject { put("id", h.id); put("text", h.text); put("prefix", h.prefix); put("color", h.color) }) } })
        }
    }
    val main = remember { Handler(Looper.getMainLooper()) }
    val view = remember {
        val loader = WebViewAssetLoader.Builder().addPathHandler("/", WebViewAssetLoader.AssetsPathHandler(ctx)).build()
        WebView(ctx).apply {
            setBackgroundColor(0)
            settings.javaScriptEnabled = true; settings.allowFileAccess = false; settings.allowContentAccess = false
            settings.textZoom = 100  // the page scales its own text by the phone's font size (fontScale below), once
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE // images from a college server without https
            webViewClient = object : WebViewClient() {
                override fun shouldInterceptRequest(v: WebView, r: WebResourceRequest) = loader.shouldInterceptRequest(r.url)
                override fun shouldOverrideUrlLoading(v: WebView, r: WebResourceRequest) = true // the page never navigates; links come as messages
                override fun onRenderProcessGone(v: WebView, d: RenderProcessGoneDetail) = goneQuietly(v) // Android ended the page (out of memory): drop it, don't crash
            }
            addJavascriptInterface(object {
                @JavascriptInterface fun post(s: String) {
                    val m = runCatching { json.parseToJsonElement(s).jsonObject }.getOrNull() ?: return
                    main.post {
                        when ((m["type"] as? JsonPrimitive)?.content) {
                            "ready" -> tag.let { evaluateJavascript("zgReader.show(${tag})", null) }
                            "height" -> height = (m["h"] as? JsonPrimitive)?.content?.toIntOrNull() ?: height
                            "link" -> (m["href"] as? JsonPrimitive)?.content?.takeIf { it.startsWith("http") }?.let { ctx.startActivity(Intent(Intent.ACTION_VIEW, it.toUri())) }
                            else -> events(m)
                        }
                    }
                }
            }, "ZigoraBridge")
            loadUrl(READER)
        }
    }
    // the options travel in the view's tag, so a page that reloads (or is ready later) gets the latest
    DisposableEffect(opts) { view.tag = opts.toString(); view.evaluateJavascript("window.zgReader&&zgReader.show(${opts})", null); onDispose { } }
    DisposableEffect(handle) { handle?.view = view; onDispose { handle?.view = null } }
    DisposableEffect(Unit) { onDispose { view.destroy() } }
    AndroidView(factory = { view }, modifier = if (fill) modifier.fillMaxSize() else modifier.fillMaxWidth().height(height.dp))
}

/** An interactive topic (a teacher's page with its own scripts), full screen. On the web it runs in a sandboxed frame and asks the app, by
 *  postMessage, to save highlights and its stored data; here the same messages come to the app through a script added as the page starts. */
@SuppressLint("SetJavaScriptEnabled", "JavascriptInterface")
@Composable
fun InteractivePage(url: String, handle: WebHandle, modifier: Modifier = Modifier, onEvent: (JsonObject) -> Unit) {
    val ctx = LocalContext.current; val events by rememberUpdatedState(onEvent); val main = remember { Handler(Looper.getMainLooper()) }
    val view = remember {
        WebView(ctx).apply {
            settings.javaScriptEnabled = true; settings.domStorageEnabled = false; settings.allowFileAccess = false; settings.allowContentAccess = false
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(v: WebView, r: WebResourceRequest): Boolean { ctx.startActivity(Intent(Intent.ACTION_VIEW, r.url)); return true }
                override fun onRenderProcessGone(v: WebView, d: RenderProcessGoneDetail) = goneQuietly(v)
            }
            addJavascriptInterface(object {
                @JavascriptInterface fun post(s: String) { runCatching { json.parseToJsonElement(s).jsonObject }.getOrNull()?.let { m -> main.post { events(m) } } }
            }, "ZigoraBridge")
            if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT))
                WebViewCompat.addDocumentStartJavaScript(this, """(function(){var send=window.postMessage.bind(window);
                    window.postMessage=function(m){if(m&&m.zg===1){try{ZigoraBridge.post(JSON.stringify(m))}catch(e){}}else send.apply(null,arguments)};
                    window.zgNative=function(d){send(d,'*')}})()""", setOf("*"))
            loadUrl(url)
        }
    }
    DisposableEffect(handle) { handle.view = view; onDispose { handle.view = null } }
    DisposableEffect(Unit) { onDispose { view.destroy() } }
    AndroidView(factory = { view }, modifier = modifier.fillMaxSize())
}

/** sends a message to an interactive page as if it came from the web app around it */
fun WebHandle.toFrame(data: JsonObject) = view?.evaluateJavascript("window.zgNative&&zgNative($data)", null)

private fun goneQuietly(v: WebView): Boolean { (v.parent as? ViewGroup)?.removeView(v); v.destroy(); return true }

/** A topic's diagram, full screen: the AI's page from the server's sandbox (its scripts run, nothing can be loaded and it can't reach the app). */
@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun DiagramScreen(url: String, close: () -> Unit) {
    val ctx = LocalContext.current; val base = api().base
    val view = remember {
        WebView(ctx).apply {
            settings.javaScriptEnabled = true; settings.domStorageEnabled = false; settings.allowFileAccess = false; settings.allowContentAccess = false
            setBackgroundColor(android.graphics.Color.WHITE)
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(v: WebView, r: WebResourceRequest) = true  // the diagram never goes anywhere else
                override fun onRenderProcessGone(v: WebView, d: RenderProcessGoneDetail) = goneQuietly(v)
            }
            loadUrl(base + url)
        }
    }
    DisposableEffect(Unit) { onDispose { view.destroy() } }
    androidx.compose.material3.Scaffold(topBar = {
        androidx.compose.material3.TopAppBar(title = { androidx.compose.material3.Text(tl("Diagram")) }, navigationIcon = {
            androidx.compose.material3.IconButton(onClick = close) { androidx.compose.material3.Icon(androidx.compose.material.icons.Icons.Default.Close, tl("Close")) } })
    }) { pad -> AndroidView(factory = { view }, modifier = Modifier.padding(pad).fillMaxSize()) }
}
