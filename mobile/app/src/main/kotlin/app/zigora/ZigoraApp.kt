package app.zigora

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import app.zigora.data.Api
import app.zigora.data.Store
import kotlinx.coroutines.flow.MutableStateFlow

class ZigoraApp : Application() {
    lateinit var store: Store
    lateinit var api: Api
    /** bumps when the server signs the person out, so the screens go back to sign-in */
    val signedOut = MutableStateFlow(0)

    override fun onCreate() {
        super.onCreate()
        store = Store(this)
        if (store.server.isEmpty() && BuildConfig.DEFAULT_SERVER.isNotEmpty()) store.server = BuildConfig.DEFAULT_SERVER
        api = Api(store) { signedOut.value++ }
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(Reminders.CHANNEL, getString(R.string.channel_reminders), NotificationManager.IMPORTANCE_LOW)
                .apply { description = getString(R.string.channel_reminders_about) })
    }
}
