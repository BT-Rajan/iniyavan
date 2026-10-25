package app.zigora

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import app.zigora.data.I18n
import app.zigora.data.Notes
import java.util.concurrent.TimeUnit

/** One quiet note a day, only when the student turns it on: a teacher's date coming up or a new test, each mentioned once. Nothing about being late or scores. */
class Reminders(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        val app = applicationContext as ZigoraApp
        if (!app.store.reminders || app.store.token == null) return Result.success()
        val items = try { app.api.get("/me/notifications", Notes.serializer()).items } catch (e: Exception) { return Result.retry() }
        val fresh = items.filter { it.unread && it.key !in app.store.notified }
        app.store.notified = (app.store.notified + fresh.map { it.key }).toList().takeLast(200).toSet()
        if (fresh.isEmpty() || ContextCompat.checkSelfPermission(app, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return Result.success()
        val open = PendingIntent.getActivity(app, 0, Intent(app, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE)
        val style = NotificationCompat.InboxStyle().also { s -> fresh.take(5).forEach { s.addLine(it.text + if (it.sub.isNotEmpty()) " · ${I18n.srv(it.sub)}" else "") } }
        val n = NotificationCompat.Builder(app, CHANNEL).setSmallIcon(R.drawable.ic_launcher_monochrome)
            .setContentTitle(app.resources.getQuantityString(R.plurals.new_for_you, fresh.size, fresh.size)).setContentText(fresh.first().text)
            .setStyle(style).setContentIntent(open).setAutoCancel(true).setPriority(NotificationCompat.PRIORITY_LOW).build()
        NotificationManagerCompat.from(app).notify(1, n)
        return Result.success()
    }

    companion object {
        const val CHANNEL = "reminders"
        private const val WORK = "daily-reminder"
        fun schedule(ctx: Context, on: Boolean) {
            val wm = WorkManager.getInstance(ctx)
            if (!on) { wm.cancelUniqueWork(WORK); return }
            val req = PeriodicWorkRequestBuilder<Reminders>(1, TimeUnit.DAYS)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()).build()
            wm.enqueueUniquePeriodicWork(WORK, ExistingPeriodicWorkPolicy.KEEP, req)
        }
    }
}
