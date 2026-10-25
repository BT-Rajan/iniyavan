package app.zigora

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import app.zigora.data.Api
import app.zigora.data.I18n
import app.zigora.data.Store
import kotlinx.coroutines.flow.MutableStateFlow

class ZigoraApp : Application() {
    lateinit var store: Store
    lateinit var api: Api
    /** bumps when the server signs the person out, so the screens go back to sign-in */
    val signedOut = MutableStateFlow(0)

    override fun onCreate() {
        super.onCreate()
        keepCrashes()
        I18n.init(this)
        store = Store(this)
        if (store.server.isEmpty() && BuildConfig.DEFAULT_SERVER.isNotEmpty()) store.server = BuildConfig.DEFAULT_SERVER
        api = Api(store) { signedOut.value++ }
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(Reminders.CHANNEL, getString(R.string.channel_reminders), NotificationManager.IMPORTANCE_LOW)
                .apply { description = getString(R.string.channel_reminders_about) })
    }

    /** where the last crash's report waits, so the app can offer to share it on the next start (nothing leaves the phone unless the person shares it) */
    val crashFile get() = java.io.File(filesDir, "last-crash.txt")

    private fun keepCrashes() {
        val before = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            runCatching {
                crashFile.writeText("Zigora ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}) · Android ${android.os.Build.VERSION.RELEASE} · " +
                                    "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}\n\n" + e.stackTraceToString().take(12_000))
            }
            before?.uncaughtException(t, e)
        }
    }
}
