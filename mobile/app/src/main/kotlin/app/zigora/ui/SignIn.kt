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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.toMutableStateList
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
import app.zigora.data.Msg
import app.zigora.data.RegStatus
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
    var canReset by rememberSaveable { mutableStateOf(false) }
    var editing by rememberSaveable { mutableStateOf(app.store.server.isEmpty()) }
    var mode by rememberSaveable { mutableStateOf("in") } // in, forgot, register, code: the same steps as the web's sign-in page
    var email by rememberSaveable { mutableStateOf("") }
    var pw by rememberSaveable { mutableStateOf("") }
    var busy by rememberSaveable { mutableStateOf(false) }
    var msg by rememberSaveable { mutableStateOf("") }
    var info by rememberSaveable { mutableStateOf("") }
    val reg = rememberSaveable(saver = androidx.compose.runtime.saveable.listSaver(save = { it.toList() }, restore = { it.toMutableStateList() })) { mutableStateListOf("", "", "", "", "") } // name, institution, ID, phone, (unused)
    var domains by remember { mutableStateOf(emptyList<String>()) }
    var code by rememberSaveable { mutableStateOf("") }
    var wait by rememberSaveable { mutableIntStateOf(0) }
    LaunchedEffect(wait) { if (wait > 0) { kotlinx.coroutines.delay(1000); wait-- } }

    suspend fun check(): Boolean {
        val typed = server.trim()
        if (typed.isEmpty()) { msg = app.getString(R.string.need_address); return false }
        // "learn.college.edu", "169.58.13.213:5252" or a copied link to the web app: https is tried first, then plain http
        for (s in serverCandidates(typed)) {
            app.store.server = s
            try { val c = app.api.get("/config", Config.serializer()); college = c.name; canRegister = c.self_registration; canReset = c.email_reset; server = s; editing = false; msg = ""; return true }
            catch (e: Exception) { msg = e.message.orEmpty() }
        }
        return false
    }
    fun act(block: suspend () -> Unit) = scope.launch {
        busy = true; msg = ""
        if (editing && !check()) { busy = false; return@launch }
        try { block() } catch (e: Exception) { msg = e.message.orEmpty() }
        busy = false
    }
    fun go() = act {
        val r = app.api.send("POST", "/login", buildJsonObject { put("email", email.trim()); put("password", pw) }, LoginOut.serializer())
        app.store.token = r.token; done(r.user)
    }
    if (!editing && college == null) LaunchedEffect(Unit) { check() }
    LaunchedEffect(mode) { if (mode == "register") runCatching { domains = app.api.get("/register/status", RegStatus.serializer()).domains } }

    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding().verticalScroll(rememberScrollState()).padding(24.dp),
               horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Gap(32)
            Image(painterResource(R.drawable.ic_splash), null, Modifier.size(96.dp))
            Text(college ?: stringResource(R.string.app_name), style = MaterialTheme.typography.headlineMedium)
            Column(Modifier.widthIn(max = 420.dp).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                val emailField = @Composable {
                    OutlinedTextField(email, { email = it }, Modifier.fillMaxWidth().semantics { contentType = ContentType.EmailAddress + ContentType.Username },
                        label = { Text(stringResource(R.string.email)) }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next))
                }
                val error = @Composable { if (msg.isNotEmpty()) Text(msg, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
                val back = @Composable { TextButton(onClick = { mode = "in"; msg = ""; info = "" }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.back_to_sign_in)) } }
                when (mode) {
                    "forgot" -> {
                        Text(stringResource(R.string.forgot_title), style = MaterialTheme.typography.titleLarge)
                        if (info.isNotEmpty()) Text(info) else {
                            Quiet(stringResource(R.string.forgot_lead)); emailField(); error()
                            Button(onClick = { act { info = app.api.send("POST", "/forgot", buildJsonObject { put("email", email.trim()) }, Msg.serializer()).message } },
                                   enabled = !busy && email.isNotBlank(), modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.send_reset_link)) }
                        }
                        back()
                    }
                    "register" -> {
                        Text(stringResource(R.string.create_account), style = MaterialTheme.typography.titleLarge)
                        Quiet(stringResource(R.string.register_lead) + if (domains.isNotEmpty()) " " + stringResource(R.string.use_institution_email, domains.joinToString(", ") { "@$it" }) else "")
                        listOf(R.string.full_name to 0, R.string.institution to 1, R.string.id_number to 2).forEach { (l, i) ->
                            OutlinedTextField(reg[i], { reg[i] = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(l)) }, singleLine = true,
                                placeholder = if (i == 2) ({ Text(stringResource(R.string.id_number_hint)) }) else null)
                        }
                        emailField()
                        OutlinedTextField(reg[3], { reg[3] = it }, Modifier.fillMaxWidth().semantics { contentType = ContentType.PhoneNumber }, label = { Text(stringResource(R.string.phone)) },
                            singleLine = true, placeholder = { Text("+91 98765 43210") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone))
                        OutlinedTextField(pw, { pw = it }, Modifier.fillMaxWidth().semantics { contentType = ContentType.NewPassword }, label = { Text(stringResource(R.string.password)) },
                            singleLine = true, visualTransformation = PasswordVisualTransformation(), supportingText = { Text(stringResource(R.string.register_password_note)) })
                        error()
                        val ok = reg.take(4).all { it.isNotBlank() } && email.isNotBlank() && pw.isNotEmpty()
                        Button(enabled = !busy && ok, modifier = Modifier.fillMaxWidth(), onClick = { act {
                            info = app.api.send("POST", "/register/start", buildJsonObject { put("name", reg[0]); put("institution", reg[1]); put("id_number", reg[2]); put("email", email.trim()); put("phone", reg[3]); put("password", pw) }, Msg.serializer()).message
                            code = ""; wait = 30; mode = "code"
                        } }) { Text(stringResource(R.string.send_me_code)) }
                        back()
                    }
                    "code" -> {
                        Text(stringResource(R.string.enter_code), style = MaterialTheme.typography.titleLarge)
                        Text(info)
                        OutlinedTextField(code, { code = it.filter(Char::isDigit).take(6) }, Modifier.fillMaxWidth().semantics { contentType = ContentType.SmsOtpCode },
                            label = { Text(stringResource(R.string.six_digit_code)) }, singleLine = true, textStyle = MaterialTheme.typography.headlineSmall,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword))
                        error()
                        Button(enabled = !busy && code.length == 6, modifier = Modifier.fillMaxWidth(), onClick = { act {
                            val r = app.api.send("POST", "/register/verify", buildJsonObject { put("email", email.trim()); put("code", code) }, LoginOut.serializer())
                            app.store.token = r.token; done(r.user)
                        } }) { Text(stringResource(R.string.verify_create)) }
                        TextButton(enabled = wait == 0, modifier = Modifier.fillMaxWidth(), onClick = { act {
                            app.api.raw("POST", "/register/resend", buildJsonObject { put("email", email.trim()) }); wait = 30; code = ""; info = app.getString(R.string.new_code_coming)
                        } }) { Text(if (wait > 0) stringResource(R.string.new_code_in, wait) else stringResource(R.string.send_new_code)) }
                        TextButton(onClick = { mode = "register"; code = ""; msg = "" }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.change_my_details)) }
                    }
                    else -> {
                        Quiet(stringResource(R.string.signin_lead))
                        if (editing) {
                            OutlinedTextField(server, { server = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.college_address)) },
                                supportingText = { Text(stringResource(R.string.college_address_hint)) }, singleLine = true,
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Next))
                        } else Row2(server, insecure = server.startsWith("http://")) { editing = true }
                        emailField()
                        OutlinedTextField(pw, { pw = it }, Modifier.fillMaxWidth().semantics { contentType = ContentType.Password },
                            label = { Text(stringResource(R.string.password)) }, singleLine = true, visualTransformation = PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Go), keyboardActions = KeyboardActions(onGo = { go() }))
                        error()
                        Button(onClick = { go() }, enabled = !busy && email.isNotBlank() && pw.isNotEmpty(), modifier = Modifier.fillMaxWidth()) {
                            Text(stringResource(if (busy) R.string.signing_in else R.string.sign_in))
                        }
                        if (!editing) {
                            if (canReset) TextButton(onClick = { mode = "forgot"; msg = ""; info = "" }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.forgot_password_q)) }
                            else Quiet(stringResource(R.string.forgot_ask_admin))
                            if (canRegister) androidx.compose.material3.OutlinedButton(onClick = { mode = "register"; msg = "" }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.create_account)) }
                        }
                    }
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
fun ChangePassword(forced: Boolean, back: (() -> Unit)? = null, done: () -> Unit) {
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
            if (back != null) TextButton(onClick = back) { Text(stringResource(R.string.cancel)) }
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
