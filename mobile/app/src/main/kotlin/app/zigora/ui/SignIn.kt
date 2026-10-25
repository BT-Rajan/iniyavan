package app.zigora.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.autofill.ContentType
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentType
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import app.zigora.R
import app.zigora.data.Config
import app.zigora.data.LoginOut
import app.zigora.data.Me
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** The college's address once, then email and password. The address is checked by asking the server for its name. */
@Composable
fun SignIn(done: (Me) -> Unit) {
    val app = app(); val scope = rememberCoroutineScope()
    var server by rememberSaveable { mutableStateOf(app.store.server) }
    var college by rememberSaveable { mutableStateOf<String?>(null) }
    var canRegister by rememberSaveable { mutableStateOf(false) }
    var editing by rememberSaveable { mutableStateOf(app.store.server.isEmpty()) }
    var email by rememberSaveable { mutableStateOf("") }
    var pw by rememberSaveable { mutableStateOf("") }
    var busy by rememberSaveable { mutableStateOf(false) }
    var msg by rememberSaveable { mutableStateOf("") }

    suspend fun check(): Boolean {
        val typed = server.trim()
        if (typed.isEmpty()) { msg = app.getString(R.string.need_address); return false }
        // "learn.college.edu", "169.58.13.213:5252" or a copied link to the web app: https is tried first, then plain http
        for (s in serverCandidates(typed)) {
            app.store.server = s
            try { val c = app.api.get("/config", Config.serializer()); college = c.name; canRegister = c.self_registration; server = s; editing = false; msg = ""; return true }
            catch (e: Exception) { msg = e.message.orEmpty() }
        }
        return false
    }
    fun go() = scope.launch {
        busy = true; msg = ""
        if (editing && !check()) { busy = false; return@launch }
        try {
            val r = app.api.send("POST", "/login", buildJsonObject { put("email", email.trim()); put("password", pw) }, LoginOut.serializer())
            app.store.token = r.token; done(r.user)
        } catch (e: Exception) { msg = e.message.orEmpty() }
        busy = false
    }
    if (!editing && college == null) androidx.compose.runtime.LaunchedEffect(Unit) { check() }

    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding().verticalScroll(rememberScrollState()).padding(24.dp),
               horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Gap(32)
            Image(painterResource(R.drawable.ic_splash), null, Modifier.size(96.dp))
            Text(college ?: stringResource(R.string.app_name), style = MaterialTheme.typography.headlineMedium)
            Quiet(stringResource(R.string.signin_lead))
            Column(Modifier.widthIn(max = 420.dp).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (editing) {
                    OutlinedTextField(server, { server = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.college_address)) },
                        supportingText = { Text(stringResource(R.string.college_address_hint)) }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Next))
                } else Row2(server, insecure = server.startsWith("http://")) { editing = true }
                OutlinedTextField(email, { email = it }, Modifier.fillMaxWidth().semantics { contentType = ContentType.EmailAddress + ContentType.Username },
                    label = { Text(stringResource(R.string.email)) }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next))
                OutlinedTextField(pw, { pw = it }, Modifier.fillMaxWidth().semantics { contentType = ContentType.Password },
                    label = { Text(stringResource(R.string.password)) }, singleLine = true, visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Go), keyboardActions = KeyboardActions(onGo = { go() }))
                if (msg.isNotEmpty()) Text(msg, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                Button(onClick = { go() }, enabled = !busy && email.isNotBlank() && pw.isNotEmpty(), modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(if (busy) R.string.signing_in else R.string.sign_in))
                }
                Quiet(stringResource(R.string.signin_help))
                if (canRegister && !editing) { // registering (with the emailed code) happens on the college's site; then the person signs in here
                    val ctx = androidx.compose.ui.platform.LocalContext.current
                    androidx.compose.material3.OutlinedButton(onClick = { ctx.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(app.api.base + "/app/"))) },
                        modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.create_account)) }
                    Quiet(stringResource(R.string.create_account_hint))
                }
            }
        }
    }
}

@Composable
private fun Row2(server: String, insecure: Boolean, change: () -> Unit) = Column(Modifier.fillMaxWidth()) {
    androidx.compose.foundation.layout.Row(verticalAlignment = Alignment.CenterVertically) {
        Text(server.removePrefix("https://"), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
        TextButton(onClick = change) { Text(stringResource(R.string.change)) }
    }
    if (insecure) Quiet(stringResource(R.string.not_secure), Modifier.padding(bottom = 4.dp))
}

/** a first sign-in with a password an admin set: the student picks their own before going on */
@Composable
fun ChangePassword(forced: Boolean, done: () -> Unit) {
    val app = app(); val scope = rememberCoroutineScope()
    var cur by rememberSaveable { mutableStateOf("") }
    var new by rememberSaveable { mutableStateOf("") }
    var msg by rememberSaveable { mutableStateOf("") }
    var busy by rememberSaveable { mutableStateOf(false) }
    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding().padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Gap(24)
            Text(stringResource(R.string.choose_password), style = MaterialTheme.typography.headlineSmall)
            if (forced) Quiet(stringResource(R.string.choose_password_lead))
            OutlinedTextField(cur, { cur = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.current_password)) }, singleLine = true, visualTransformation = PasswordVisualTransformation())
            OutlinedTextField(new, { new = it }, Modifier.fillMaxWidth().semantics { contentType = ContentType.NewPassword }, label = { Text(stringResource(R.string.new_password)) },
                supportingText = { Text(stringResource(R.string.password_rule)) }, singleLine = true, visualTransformation = PasswordVisualTransformation())
            if (msg.isNotEmpty()) Text(msg, color = MaterialTheme.colorScheme.error)
            Button(enabled = !busy && cur.isNotEmpty() && new.length >= 8, onClick = {
                scope.launch {
                    busy = true
                    try {
                        val r = app.api.raw("POST", "/me/password", buildJsonObject { put("current", cur); put("new_password", new) })
                        (r as? kotlinx.serialization.json.JsonObject)?.get("token")?.let { app.store.token = (it as kotlinx.serialization.json.JsonPrimitive).content }
                        done()
                    } catch (e: Exception) { msg = e.message.orEmpty() }
                    busy = false
                }
            }) { Text(stringResource(R.string.save_password)) }
        }
    }
}

/** the server's root address for what someone typed: with no http(s):// both are tried, https first; any path (like /app/) is dropped */
fun serverCandidates(typed: String): List<String> {
    val t = typed.trim()
    val withScheme = if (t.startsWith("http://", true) || t.startsWith("https://", true)) listOf(t) else listOf("https://$t", "http://$t")
    return withScheme.mapNotNull { u ->
        runCatching { java.net.URI(u) }.getOrNull()?.takeIf { !it.host.isNullOrEmpty() }?.let { "${it.scheme.lowercase()}://${it.host}" + if (it.port != -1) ":${it.port}" else "" }
    }.distinct()
}
