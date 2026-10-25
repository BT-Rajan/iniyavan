package app.zigora.ui

import android.Manifest
import android.app.LocaleManager
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.LocaleList
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.Translate
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import app.zigora.BuildConfig
import app.zigora.R
import app.zigora.Reminders
import app.zigora.data.AndroidRelease
import app.zigora.data.Me
import app.zigora.data.Notes
import app.zigora.data.Profile
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

val LANGS = listOf("en" to "English", "ar" to "العربية", "ta" to "தமிழ்")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(me: Me, wallpaper: (Boolean) -> Unit, signOut: () -> Unit) {
    val app = app(); val ctx = LocalContext.current; val scope = rememberCoroutineScope()
    val p = rememberLoad("profile") { get("/me/profile", Profile.serializer()) }
    val lm = remember { ctx.getSystemService(LocaleManager::class.java) }
    var lang by remember { mutableStateOf(lm.applicationLocales.get(0)?.language ?: me.lang) }
    var colours by remember { mutableStateOf(app.store.wallpaper) }
    var remind by remember { mutableStateOf(app.store.reminders) }
    var asking by remember { mutableStateOf(false) }
    val notify = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok -> remind = ok; app.store.reminders = ok; Reminders.schedule(ctx, ok) }
    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.tab_me)) }) }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Loaded(p) { pr ->
                Panel {
                    Text(pr.name, style = MaterialTheme.typography.titleLarge)
                    Quiet(pr.email)
                    if (pr.program.isNotEmpty()) Quiet(pr.program + (pr.semester?.let { " · ${pr.term} $it" } ?: ""))
                }
                pr.rewards?.let { r ->
                    SectionTitle(stringResource(R.string.rewards))
                    Panel {
                        Text(pluralStringResource(R.plurals.points, r.points, r.points), style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
                        Quiet(stringResource(R.string.rewards_how, r.per, r.points_per))
                        LinearProgressIndicator(progress = { r.toward_next.toFloat() / r.per.coerceAtLeast(1) }, Modifier.fillMaxWidth().padding(vertical = 8.dp))
                        Quiet(stringResource(R.string.toward_next, r.toward_next, r.per))
                        if (r.top.isNotEmpty()) {
                            SectionTitle(stringResource(R.string.most_used))
                            r.top.forEach { s -> ListItem(headlineContent = { Text(s.label) }, trailingContent = { Text("${s.uses}") }) }
                        }
                    }
                }
            }
            SectionTitle(stringResource(R.string.settings))
            ListItem(leadingContent = { Icon(Icons.Outlined.Translate, null) }, headlineContent = { Text(stringResource(R.string.language)) },
                     supportingContent = { Text(stringResource(R.string.language_hint)) })
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                LANGS.forEachIndexed { i, (code, name) ->
                    SegmentedButton(lang == code, shape = SegmentedButtonDefaults.itemShape(i, LANGS.size), onClick = {
                        lang = code
                        scope.launch { runCatching { app.api.raw("PUT", "/me/lang", buildJsonObject { put("lang", code) }) } }
                        lm.applicationLocales = LocaleList.forLanguageTags(code) // Android 13's per-app language: the app restarts in it
                    }) { Text(name) }
                }
            }
            ListItem(headlineContent = { Text(stringResource(R.string.wallpaper_colours)) }, supportingContent = { Text(stringResource(R.string.wallpaper_colours_hint)) },
                     trailingContent = { Switch(colours, { colours = it; wallpaper(it) }) })
            ListItem(headlineContent = { Text(stringResource(R.string.daily_note)) }, supportingContent = { Text(stringResource(R.string.daily_note_hint)) },
                     trailingContent = { Switch(remind, { on ->
                         if (on && ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) notify.launch(Manifest.permission.POST_NOTIFICATIONS)
                         else { remind = on; app.store.reminders = on; Reminders.schedule(ctx, on) }
                     }) })
            SectionTitle(stringResource(R.string.about_app))
            val rel = rememberLoad("update") { runCatching { get("/app/android", AndroidRelease.serializer()) }.getOrNull() }
            val newer = (rel.state as? Load.Ok)?.value?.takeIf { (it.code ?: 0) > BuildConfig.VERSION_CODE && it.url != null }
            ListItem(headlineContent = { Text(stringResource(R.string.version_n, BuildConfig.VERSION_NAME)) },
                     supportingContent = { Text(if (newer != null) stringResource(R.string.update_ready, newer.version.orEmpty()) else stringResource(R.string.server_n, app.api.base.removePrefix("https://"))) },
                     trailingContent = { if (newer != null) TextButton(onClick = { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(newer.url))) }) { Text(stringResource(R.string.update)) } })
            ListItem(modifier = Modifier.clickableRounded { asking = true }, leadingContent = { Icon(Icons.AutoMirrored.Outlined.Logout, null) },
                     headlineContent = { Text(stringResource(R.string.sign_out)) })
        }
    }
    if (asking) AlertDialog(onDismissRequest = { asking = false }, title = { Text(stringResource(R.string.sign_out_q)) },
        confirmButton = { TextButton(onClick = { asking = false; Reminders.schedule(ctx, false); signOut() }) { Text(stringResource(R.string.sign_out)) } },
        dismissButton = { TextButton(onClick = { asking = false }) { Text(stringResource(R.string.cancel)) } })
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationsScreen(back: () -> Unit, openTopic: (Int) -> Unit) {
    val n = rememberLoad("notes") {
        get("/me/notifications", Notes.serializer()).also { r ->
            val keys = r.items.filter { it.unread }.map { it.key }
            if (keys.isNotEmpty()) runCatching { raw("POST", "/me/notifications/seen", buildJsonObject { put("keys", kotlinx.serialization.json.JsonArray(keys.map { kotlinx.serialization.json.JsonPrimitive(it) })) }) }
        }
    }
    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.notifications)) },
        navigationIcon = { IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } }) }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(16.dp)) {
            Loaded(n) { r ->
                if (r.items.isEmpty()) Quiet(stringResource(R.string.no_notifications))
                Paged(r.items) { x ->
                    val tid = x.key.substringAfter(":").toIntOrNull().takeIf { !x.key.startsWith("quiz") }
                    ListItem(modifier = if (tid != null) Modifier.clickableRounded { openTopic(tid) } else Modifier,
                             headlineContent = { Text(x.text) }, supportingContent = { if (x.sub.isNotEmpty()) Text(x.sub) },
                             overlineContent = { if (x.unread) Text(stringResource(R.string.new_label), color = MaterialTheme.colorScheme.primary) })
                }
            }
        }
    }
}
