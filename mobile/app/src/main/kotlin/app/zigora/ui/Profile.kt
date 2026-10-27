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
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Key
import androidx.compose.material.icons.outlined.Password
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
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import app.zigora.BuildConfig
import app.zigora.R
import app.zigora.Reminders
import app.zigora.data.AiPlan
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
fun ProfileScreen(me: Me, wallpaper: (Boolean) -> Unit, themeOf: (String) -> Unit, signOut: () -> Unit, openPassword: () -> Unit, openKey: () -> Unit) {
    val app = app(); val ctx = LocalContext.current; val scope = rememberCoroutineScope()
    val p = rememberLoad("profile") { get("/me/profile", Profile.serializer()) }
    val lm = remember { ctx.getSystemService(LocaleManager::class.java) }
    var lang by remember { mutableStateOf(lm.applicationLocales.get(0)?.language ?: me.lang) }
    var colours by remember { mutableStateOf(app.store.wallpaper) }
    var theme by remember { mutableStateOf(app.store.theme) }
    var about by remember { mutableStateOf(false) }
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
                pr.ai?.takeIf { pr.self_registered && it.plan != "college" }?.let { PlanCard(it) { p.reload() } }
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
            ListItem(leadingContent = { Icon(Icons.Outlined.DarkMode, null) }, headlineContent = { Text(stringResource(R.string.theme)) })
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                listOf("system" to R.string.theme_auto, "light" to R.string.theme_light, "dark" to R.string.theme_dark).forEachIndexed { i, (k, l) ->
                    SegmentedButton(theme == k, shape = SegmentedButtonDefaults.itemShape(i, 3), onClick = { theme = k; themeOf(k) }) { Text(stringResource(l)) }
                }
            }
            ListItem(headlineContent = { Text(stringResource(R.string.wallpaper_colours)) }, supportingContent = { Text(stringResource(R.string.wallpaper_colours_hint)) },
                     trailingContent = { Switch(colours, { colours = it; wallpaper(it) }) })
            ListItem(headlineContent = { Text(stringResource(R.string.daily_note)) }, supportingContent = { Text(stringResource(R.string.daily_note_hint)) },
                     trailingContent = { Switch(remind, { on ->
                         if (on && ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) notify.launch(Manifest.permission.POST_NOTIFICATIONS)
                         else { remind = on; app.store.reminders = on; Reminders.schedule(ctx, on) }
                     }) })
            SectionTitle(stringResource(R.string.account))
            ListItem(modifier = Modifier.clickableRounded(openPassword), leadingContent = { Icon(Icons.Outlined.Password, null) }, headlineContent = { Text(stringResource(R.string.change_password)) })
            if (me.self_registered) ListItem(modifier = Modifier.clickableRounded(openKey), leadingContent = { Icon(Icons.Outlined.Key, null) }, headlineContent = { Text(stringResource(R.string.my_ai_key)) })
            SectionTitle(stringResource(R.string.about_app))
            ListItem(modifier = Modifier.clickableRounded { about = true }, leadingContent = { Icon(Icons.Outlined.Info, null) }, headlineContent = { Text(stringResource(R.string.about)) })
            val rel = rememberLoad("update") { runCatching { get("/app/android", AndroidRelease.serializer()) }.getOrNull() }
            val newer = (rel.state as? Load.Ok)?.value?.takeIf { (it.code ?: 0) > BuildConfig.VERSION_CODE && it.url != null }
            ListItem(headlineContent = { Text(stringResource(R.string.version_n, BuildConfig.VERSION_NAME)) },
                     supportingContent = { Text(if (newer != null) stringResource(R.string.update_ready, newer.version.orEmpty()) else stringResource(R.string.server_n, app.api.base.removePrefix("https://"))) },
                     trailingContent = { if (newer != null) TextButton(onClick = { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(newer.url))) }) { Text(stringResource(R.string.update)) } })
            ListItem(modifier = Modifier.clickableRounded { asking = true }, leadingContent = { Icon(Icons.AutoMirrored.Outlined.Logout, null) },
                     headlineContent = { Text(stringResource(R.string.sign_out)) })
        }
    }
    if (about) AlertDialog(onDismissRequest = { about = false }, confirmButton = { TextButton(onClick = { about = false }) { Text(stringResource(R.string.close)) } },
        title = { Text(stringResource(R.string.app_name)) }, text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(stringResource(R.string.about_text_1)); Text(stringResource(R.string.about_text_2))
            Quiet(stringResource(R.string.signed_in_as, me.name, me.role))
        } })
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
                if (r.mail) DigestToggle(r.digest)
                if (r.items.isEmpty()) Quiet(stringResource(R.string.no_notifications))
                Paged(r.items) { x ->
                    val tid = x.key.substringAfter(":").toIntOrNull().takeIf { !x.key.startsWith("quiz") }
                    ListItem(modifier = if (tid != null) Modifier.clickableRounded { openTopic(tid) } else Modifier,
                             headlineContent = { Text(x.text) }, supportingContent = { if (x.sub.isNotEmpty()) Text(app.zigora.data.I18n.srv(x.sub)) },
                             overlineContent = { if (x.unread) Text(stringResource(R.string.new_label), color = MaterialTheme.colorScheme.primary) })
                }
            }
        }
    }
}

/** a self-registered student's AI plan: today's free allowance on Lite, and the two ways to more (their own DeepSeek key, or asking the admin) */
@Composable
private fun PlanCard(ai: AiPlan, changed: () -> Unit) {
    val app = app(); val res = LocalResources.current; val scope = rememberCoroutineScope()
    var dialog by remember { mutableStateOf("") }
    var text by remember { mutableStateOf("") }
    var msg by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    SectionTitle(stringResource(R.string.ai_help))
    Panel {
        Text(stringResource(when (ai.plan) { "pro" -> R.string.plan_pro; "own" -> R.string.plan_own; else -> R.string.plan_lite }), style = MaterialTheme.typography.titleMedium)
        when (ai.plan) {
            "pro" -> Quiet(stringResource(R.string.pro_until_note, ai.pro_until?.let { day(it) }.orEmpty()))
            "own" -> Quiet(stringResource(R.string.own_key_note))
            else -> {
                Quiet(stringResource(R.string.lite_note, ai.searches_limit, ai.minutes_limit))
                Meter(stringResource(R.string.searches_today, ai.searches_used, ai.searches_limit), ai.searches_used, ai.searches_limit)
                Meter(stringResource(R.string.minutes_today, ai.minutes_used, ai.minutes_limit), ai.minutes_used, ai.minutes_limit)
                androidx.compose.foundation.layout.Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { text = ""; msg = ""; dialog = "key" }) { Text(stringResource(R.string.use_own_key)) }
                    TextButton(enabled = !ai.asked, onClick = { text = ""; msg = ""; dialog = "more" }) { Text(stringResource(if (ai.asked) R.string.asked_admin else R.string.ask_admin_more)) }
                }
            }
        }
    }
    if (dialog.isNotEmpty()) AlertDialog(onDismissRequest = { dialog = "" },
        title = { Text(stringResource(if (dialog == "key") R.string.use_own_key else R.string.ask_admin_more)) },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Quiet(stringResource(if (dialog == "key") R.string.own_key_how else R.string.ask_more_how))
            androidx.compose.material3.OutlinedTextField(text, { text = it }, Modifier.fillMaxWidth(), singleLine = dialog == "key",
                label = { Text(stringResource(if (dialog == "key") R.string.deepseek_key else R.string.note_optional)) },
                visualTransformation = if (dialog == "key") androidx.compose.ui.text.input.PasswordVisualTransformation() else androidx.compose.ui.text.input.VisualTransformation.None)
            if (msg.isNotEmpty()) Text(msg, color = MaterialTheme.colorScheme.error)
        } },
        confirmButton = { TextButton(enabled = !busy && (dialog != "key" || text.isNotBlank()), onClick = {
            scope.launch {
                busy = true; msg = ""
                try {
                    if (dialog == "key") app.api.raw("PUT", "/me/ai-key", buildJsonObject { put("key", text.trim()) })
                    else app.api.raw("POST", "/me/plan/request", buildJsonObject { put("note", text.trim()) })
                    dialog = ""; changed()
                } catch (e: Exception) { msg = e.message ?: res.getString(R.string.try_again) }
                busy = false
            }
        }) { Text(stringResource(if (busy) R.string.thinking else if (dialog == "key") R.string.save_key else R.string.send_request)) } },
        dismissButton = { TextButton(onClick = { dialog = "" }) { Text(stringResource(R.string.cancel)) } })
}

@Composable
private fun Meter(label: String, used: Int, max: Int) = Column(Modifier.padding(top = 8.dp)) {
    Quiet(label)
    LinearProgressIndicator(progress = { (used.toFloat() / max.coerceAtLeast(1)).coerceIn(0f, 1f) }, Modifier.fillMaxWidth().padding(top = 4.dp))
}

/** "Email me a daily summary of new ones": the same switch as under the web's bell */
@Composable
private fun DigestToggle(initial: Boolean) {
    val a = api(); val scope = rememberCoroutineScope(); var on by remember { mutableStateOf(initial) }
    ListItem(headlineContent = { Text(stringResource(R.string.daily_email)) }, trailingContent = { Switch(on, { v ->
        on = v; scope.launch { runCatching { a.raw("PUT", "/me/notifications/settings", buildJsonObject { put("digest", v) }) }.onFailure { on = !v } }
    }) })
}

/** My AI key: save or remove a self-registered person's own DeepSeek key (checked with DeepSeek first, stored encrypted) */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MyKeyScreen(guardian: Boolean = false, back: () -> Unit) {  // guardian: a parent's or teacher's key, which covers their school students
    val a = api(); val scope = rememberCoroutineScope()
    val k = rememberLoad("key") { get("/me/ai-key", app.zigora.data.KeyState.serializer()) }
    var key by remember { mutableStateOf("") }
    var msg by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var confirm by remember { mutableStateOf(false) }
    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.my_ai_key)) },
        navigationIcon = { IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } }) }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Loaded(k) { st ->
                Text(if (st.key_set) stringResource(R.string.key_on, st.key_hint) else stringResource(R.string.key_off), style = MaterialTheme.typography.titleMedium)
                Quiet(if (guardian) tl("Your DeepSeek key powers AI help for the school students linked to you. Usage is billed to your DeepSeek account. The key is stored encrypted and never shown to them.") else stringResource(R.string.key_explain))
                androidx.compose.material3.OutlinedTextField(key, { key = it }, Modifier.fillMaxWidth(), singleLine = true, label = { Text(stringResource(R.string.deepseek_key)) },
                    placeholder = { Text(stringResource(if (st.key_set) R.string.key_replace else R.string.key_placeholder)) },
                    visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation())
                if (msg.isNotEmpty()) Text(msg, color = MaterialTheme.colorScheme.error)
                androidx.compose.material3.Button(enabled = !busy && key.isNotBlank(), onClick = { scope.launch {
                    busy = true; msg = ""
                    try { a.raw("PUT", "/me/ai-key", buildJsonObject { put("key", key.trim()) }); key = ""; k.reload() } catch (e: Exception) { msg = e.message.orEmpty() }
                    busy = false
                } }) { Text(stringResource(if (busy) R.string.checking_key else R.string.save_key)) }
                if (st.key_set) androidx.compose.material3.OutlinedButton(onClick = { confirm = true }) { Text(stringResource(R.string.remove_my_key)) }
            }
        }
    }
    if (confirm) AlertDialog(onDismissRequest = { confirm = false }, title = { Text(stringResource(R.string.remove_key_q)) }, text = { Text(if (guardian) tl("AI help turns off for your school students, unless another parent or teacher linked to them has a key.") else stringResource(R.string.remove_key_body)) },
        confirmButton = { TextButton(onClick = { confirm = false; scope.launch { runCatching { a.raw("DELETE", "/me/ai-key") }; k.reload() } }) { Text(stringResource(R.string.remove_key)) } },
        dismissButton = { TextButton(onClick = { confirm = false }) { Text(stringResource(R.string.cancel)) } })
}
