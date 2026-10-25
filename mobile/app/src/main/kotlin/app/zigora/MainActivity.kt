package app.zigora

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.mutableStateOf
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import app.zigora.ui.ZigoraRoot

/** what another app or a shortcut asked for: look something up, or ask about a photo */
sealed interface Incoming {
    data class Lookup(val text: String) : Incoming
    data class Photo(val uri: Uri?) : Incoming
}

class MainActivity : ComponentActivity() {
    private val incoming = mutableStateOf<Incoming?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        val start = android.os.SystemClock.uptimeMillis(); val app = application as ZigoraApp
        installSplashScreen().setKeepOnScreenCondition { !app.firstScreenReady.value && android.os.SystemClock.uptimeMillis() - start < 2_000 }
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (savedInstanceState == null) incoming.value = read(intent)
        setContent { ZigoraRoot(incoming.value) { incoming.value = null } }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        incoming.value = read(intent)
    }

    private fun read(i: Intent?): Incoming? = when (i?.action) {
        Intent.ACTION_SEND -> if (i.type?.startsWith("image/") == true) Incoming.Photo(i.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java))
            else i.getStringExtra(Intent.EXTRA_TEXT)?.take(200)?.let { Incoming.Lookup(it) }
        Intent.ACTION_PROCESS_TEXT -> i.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)?.toString()?.take(200)?.let { Incoming.Lookup(it) }
        "app.zigora.SEARCH" -> Incoming.Lookup("")
        "app.zigora.PHOTO" -> Incoming.Photo(null)
        else -> null
    }
}
