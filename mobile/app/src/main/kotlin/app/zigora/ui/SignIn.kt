package app.zigora.ui

import app.zigora.data.json
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.jsonObject
import androidx.compose.foundation.Image
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
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
import app.zigora.data.ProgOpts
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
    var googleId by rememberSaveable { mutableStateOf<String?>(null) }  // set when the server offers Sign in with Google
    var gTicket by rememberSaveable { mutableStateOf<String?>(null) }  // a Google email with no account yet: sign-up goes on without an email code
    val ctx = androidx.compose.ui.platform.LocalContext.current
    var editing by rememberSaveable { mutableStateOf(app.store.server.isEmpty()) }
    var mode by rememberSaveable { mutableStateOf("in") } // in, forgot, register, code: the same steps as the web's sign-in page
    var email by rememberSaveable { mutableStateOf("") }
    var pw by rememberSaveable { mutableStateOf("") }
    var busy by rememberSaveable { mutableStateOf(false) }
    var msg by rememberSaveable { mutableStateOf("") }
    var info by rememberSaveable { mutableStateOf("") }
    val reg = rememberSaveable(saver = androidx.compose.runtime.saveable.listSaver(save = { it.toList() }, restore = { it.toMutableStateList() })) { mutableStateListOf("", "", "", "", "") } // name, institution, ID, phone, (unused)
    var domains by remember { mutableStateOf(emptyList<String>()) }
    var level by rememberSaveable { mutableStateOf("") }  // school or college
    var who by rememberSaveable { mutableStateOf("") }  // student, parent or teacher
    var prog by rememberSaveable { mutableStateOf<Int?>(null) }
    var sem by rememberSaveable { mutableStateOf<Int?>(null) }
    val kids = remember { mutableStateListOf(NewStudent()) }
    var opts by remember { mutableStateOf(ProgOpts()) }
    var code by rememberSaveable { mutableStateOf("") }
    var wait by rememberSaveable { mutableIntStateOf(0) }
    LaunchedEffect(wait) { if (wait > 0) { kotlinx.coroutines.delay(1000); wait-- } }

    suspend fun check(): Boolean {
        val typed = server.trim()
        if (typed.isEmpty()) { msg = app.getString(R.string.need_address); return false }
        // "learn.college.edu", "169.58.13.213:5252" or a copied link to the web app: https is tried first, then plain http
        for (s in serverCandidates(typed)) {
            app.store.server = s
            try { val c = app.api.get("/config", Config.serializer()); college = c.name; app.store.appName = c.name; canRegister = c.self_registration; canReset = c.email_reset; googleId = c.google_client_id; server = s; editing = false; msg = ""; return true }
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
    fun google() = act {  // Google's own sheet picks the account; the server checks the ID token it hands back
        val id = googleId ?: return@act
        val token = try {
            val req = androidx.credentials.GetCredentialRequest.Builder()
                .addCredentialOption(com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption.Builder(id).build()).build()
            val cred = androidx.credentials.CredentialManager.create(ctx).getCredential(ctx, req).credential
            if (cred is androidx.credentials.CustomCredential && cred.type == com.google.android.libraries.identity.googleid.GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL)
                com.google.android.libraries.identity.googleid.GoogleIdTokenCredential.createFrom(cred.data).idToken
            else { msg = tl("Google sign-in didn't work. Try again."); return@act }
        } catch (e: androidx.credentials.exceptions.GetCredentialCancellationException) { return@act }  // they closed Google's sheet
        catch (e: androidx.credentials.exceptions.GetCredentialException) { msg = tl("Google sign-in didn't work. Try again."); return@act }
        val r = app.api.raw("POST", "/login/google", buildJsonObject { put("credential", token) }).jsonObject
        if (r["token"] != null) { val out = json.decodeFromJsonElement(LoginOut.serializer(), r); app.store.token = out.token; done(out.user) }
        else {  // no account with this Google email: sign up, with the email Google checked and no password to choose
            gTicket = r["ticket"]?.jsonPrimitive?.content; email = r["email"]?.jsonPrimitive?.content.orEmpty()
            reg[0] = r["name"]?.jsonPrimitive?.content.orEmpty(); mode = "register"
        }
    }
    if (!editing && college == null) LaunchedEffect(Unit) { check() }
    LaunchedEffect(mode) { if (mode == "register") { runCatching { domains = app.api.get("/register/status", RegStatus.serializer()).domains }; runCatching { opts = app.api.get("/register/options", ProgOpts.serializer()) } } }

    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding().verticalScroll(rememberScrollState()).padding(24.dp),
               horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Gap(32)
            Image(painterResource(R.drawable.ic_logo), null, Modifier.size(72.dp))
            Text(college ?: stringResource(R.string.app_name), style = MaterialTheme.typography.headlineMedium)
            Column(Modifier.widthIn(max = 420.dp).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                val emailField = @Composable {
                    OutlinedTextField(email, { email = it }, Modifier.fillMaxWidth().semantics { contentType = ContentType.EmailAddress + ContentType.Username },
                        label = { Text(if (mode == "in") tl("Email or username") else stringResource(R.string.email)) }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next))
                }
                val error = @Composable { if (msg.isNotEmpty()) Text(msg, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
                val toUp = mode != "forgot" && canRegister  // sign-up steps go back to the Create an account tab
                val back = @Composable { TextButton(onClick = { mode = if (toUp) "up" else "in"; msg = ""; info = ""; if (gTicket != null) { gTicket = null; email = "" } }, modifier = Modifier.fillMaxWidth()) {
                    Text(if (toUp) tl("Back") else stringResource(R.string.back_to_sign_in)) } }
                if ((mode == "in" || mode == "up") && !editing && canRegister)  // two tabs when sign-up is open: Sign in, and Create an account
                    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                        listOf("in" to stringResource(R.string.sign_in), "up" to stringResource(R.string.create_account)).forEachIndexed { i, (k, l) ->
                            SegmentedButton(selected = mode == k, onClick = { mode = k; msg = "" },
                                shape = SegmentedButtonDefaults.itemShape(i, 2)) { Text(l) }
                        }
                    }
                when (mode) {
                    "forgot" -> {
                        Text(stringResource(R.string.forgot_title), style = MaterialTheme.typography.titleLarge)
                        if (info.isNotEmpty()) Text(info) else {
                            Quiet(stringResource(R.string.forgot_lead)); Quiet(tl("Sign in with a username? Ask your parent or teacher to set a new password for you.")); emailField(); error()
                            Button(onClick = { act { info = app.api.send("POST", "/forgot", buildJsonObject { put("email", email.trim()) }, Msg.serializer()).message } },
                                   enabled = !busy && email.isNotBlank(), modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.send_reset_link)) }
                        }
                        back()
                    }
                    "up" -> {  // Create an account: with Google (no code to type: Google checked the email) or with an email and a code
                        Text(stringResource(R.string.create_account), style = MaterialTheme.typography.titleLarge)
                        Quiet(if (googleId != null) tl("Sign up with your Google account, or with your email.") else tl("Sign up with your email. We will send you a code to confirm it."))
                        error()
                        if (googleId != null) {
                            Button(onClick = { google() }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text(tl("Sign up with Google")) }
                            Text(tl("or"), Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                        }
                        val email1 = @Composable { Text(tl("Sign up with email")) }
                        if (googleId != null) androidx.compose.material3.OutlinedButton(onClick = { gTicket = null; mode = "register"; msg = "" }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { email1() }
                        else Button(onClick = { gTicket = null; mode = "register"; msg = "" }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { email1() }
                        Quiet(tl("Students, parents and teachers can sign up here. Already have an account? Use Sign in."))
                    }
                    "register" -> {  // 1. who is studying: school or college
                        Text(stringResource(R.string.create_account), style = MaterialTheme.typography.titleLarge)
                        Quiet(tl("Who is studying?"))
                        Pick(tl("A school student"), tl("Grade 1 to Grade 12")) { level = "school"; mode = "who" }
                        Pick(tl("A college student"), tl("College or university")) { level = "college"; mode = "who" }
                        back()
                    }
                    "who" -> {  // 2. who is signing up
                        Text(tl("Who is signing up?"), style = MaterialTheme.typography.titleLarge)
                        Quiet(if (level == "school") tl("For a school student") else tl("For a college student"))
                        Pick(tl("I'm the student"), tl("An account for me")) { who = "student"; mode = "form" }
                        Pick(tl("A parent"), tl("Accounts for one or more of my children")) { who = "parent"; mode = "form" }
                        Pick(tl("A teacher"), tl("I add or invite my students after signing up")) { who = "teacher"; mode = "form" }
                        TextButton(onClick = { mode = "register" }, modifier = Modifier.fillMaxWidth()) { Text(tl("Back")) }
                    }
                    "form" -> {  // 3. the details; a parent adds each child, who signs in with a username
                        val school = level == "school"
                        Text(when (who) { "parent" -> tl("Your details"); "teacher" -> tl("Teacher sign-up"); else -> stringResource(R.string.create_account) }, style = MaterialTheme.typography.titleLarge)
                        Quiet(if (gTicket != null) tl("Signing up with your Google account {email}.", "email" to email)
                              else stringResource(R.string.register_lead) + if (who != "parent" && domains.isNotEmpty()) " " + stringResource(R.string.use_institution_email, domains.joinToString(", ") { "@$it" }) else "")
                        OutlinedTextField(reg[0], { reg[0] = it }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.full_name)) }, singleLine = true)
                        if (who != "parent") OutlinedTextField(reg[1], { reg[1] = it }, Modifier.fillMaxWidth(), label = { Text(if (school) tl("School") else tl("College")) }, singleLine = true)
                        if (who == "student") {
                            OutlinedTextField(reg[2], { reg[2] = it }, Modifier.fillMaxWidth(), label = { Text(if (school) tl("Roll number (optional)") else stringResource(R.string.id_number)) },
                                singleLine = true, placeholder = { Text(stringResource(R.string.id_number_hint)) })
                            PlacePicker(opts, level, prog, sem) { p, s -> prog = p; sem = s }
                        }
                        if (gTicket == null) emailField()
                        OutlinedTextField(reg[3], { reg[3] = it }, Modifier.fillMaxWidth().semantics { contentType = ContentType.PhoneNumber }, label = { Text(stringResource(R.string.phone)) },
                            singleLine = true, placeholder = { Text("+91 98765 43210") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone))
                        if (gTicket == null) OutlinedTextField(pw, { pw = it }, Modifier.fillMaxWidth().semantics { contentType = ContentType.NewPassword }, label = { Text(stringResource(R.string.password)) },
                            singleLine = true, visualTransformation = PasswordVisualTransformation(),
                            supportingText = { Text(if (who == "student" && !school) stringResource(R.string.register_password_note) else tl("At least 8 characters.")) })
                        else Quiet(tl("You sign in with Google. You can set a password later with “Forgot password?”."))
                        if (who == "parent") {
                            Text(tl("Your children"), style = MaterialTheme.typography.titleMedium)
                            Quiet(tl("Each child signs in with their own username and password. They don't need an email."))
                            StudentRows(kids, opts, level, { n -> tl("Child {n}", "n" to n) }, tl("Add another child"), 8)
                        }
                        error()
                        val ok = reg[0].isNotBlank() && (gTicket != null || (email.isNotBlank() && pw.isNotEmpty())) && reg[3].isNotBlank() && (who == "parent" || reg[1].isNotBlank()) &&
                                 (who != "student" || school || reg[2].isNotBlank()) && (who != "student" || prog == null || sem != null) && (who != "parent" || kids.all { it.ok })
                        val ticket = gTicket
                        if (ticket != null) Button(enabled = !busy && ok, modifier = Modifier.fillMaxWidth(), onClick = { act {
                            val r = app.api.send("POST", "/register/google", buildJsonObject {
                                put("ticket", ticket); put("name", reg[0]); put("institution", if (who == "parent") "" else reg[1]); put("id_number", if (who == "student") reg[2] else ""); put("phone", reg[3])
                                put("level", level); put("who", who); put("program_id", if (who == "student") prog else null); put("semester", if (who == "student") sem else null)
                                put("children", studentsJson(if (who == "parent") kids else emptyList())); put("lang", app.resources.configuration.locales[0].language)
                            }, LoginOut.serializer())
                            app.store.token = r.token; done(r.user)
                        } }) { Text(tl("Create my account")) }
                        else Button(enabled = !busy && ok, modifier = Modifier.fillMaxWidth(), onClick = { act {
                            info = app.api.send("POST", "/register/start", buildJsonObject {
                                put("name", reg[0]); put("institution", if (who == "parent") "" else reg[1]); put("id_number", if (who == "student") reg[2] else ""); put("email", email.trim()); put("phone", reg[3]); put("password", pw)
                                put("level", level); put("who", who); put("program_id", if (who == "student") prog else null); put("semester", if (who == "student") sem else null)
                                put("children", studentsJson(if (who == "parent") kids else emptyList()))
                                put("lang", app.resources.configuration.locales[0].language)  // the code's email comes in the app's language
                            }, Msg.serializer()).message
                            code = ""; wait = 30; mode = "code"
                        } }) { Text(stringResource(R.string.send_me_code)) }
                        TextButton(onClick = { mode = "who"; msg = "" }, modifier = Modifier.fillMaxWidth()) { Text(tl("Back")) }
                    }
                    "code" -> {
                        Text(stringResource(R.string.enter_code), style = MaterialTheme.typography.titleLarge)
                        Text(info)
                        OutlinedTextField(code, { code = it.filter(Char::isDigit).take(6) }, Modifier.fillMaxWidth().semantics { contentType = ContentType.SmsOtpCode },
                            label = { Text(stringResource(R.string.six_digit_code)) }, singleLine = true, textStyle = MaterialTheme.typography.headlineSmall,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword))
                        error()
                        Button(enabled = !busy && code.length == 6, modifier = Modifier.fillMaxWidth(), onClick = { act {
                            val r = app.api.send("POST", "/register/verify", buildJsonObject { put("email", email.trim()); put("code", code); put("lang", app.resources.configuration.locales[0].language) }, LoginOut.serializer())
                            app.store.token = r.token; done(r.user)
                        } }) { Text(stringResource(R.string.verify_create)) }
                        TextButton(enabled = wait == 0, modifier = Modifier.fillMaxWidth(), onClick = { act {
                            app.api.raw("POST", "/register/resend", buildJsonObject { put("email", email.trim()); put("lang", app.resources.configuration.locales[0].language) }); wait = 30; code = ""; info = app.getString(R.string.new_code_coming)
                        } }) { Text(if (wait > 0) stringResource(R.string.new_code_in, wait) else stringResource(R.string.send_new_code)) }
                        TextButton(onClick = { mode = "form"; code = ""; msg = "" }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.change_my_details)) }
                    }
                    else -> {
                        Text(if (canRegister && !editing) tl("Welcome back.") else stringResource(R.string.signin_lead), Modifier.fillMaxWidth().padding(bottom = 8.dp), style = MaterialTheme.typography.bodyLarge,
                             color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
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
                        if (!editing && googleId != null) androidx.compose.material3.OutlinedButton(onClick = { google() }, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                            Text(tl("Sign in with Google"))
                        }
                        if (!editing) {
                            if (canReset) TextButton(onClick = { mode = "forgot"; msg = ""; info = "" }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.forgot_password_q)) }
                            else Quiet(stringResource(R.string.forgot_ask_admin) + " " + tl("Sign in with a username? Ask your parent or teacher to set a new password for you."))
                        }
                    }
                }
            }
        }
    }
}

/** a big choice on the sign-up steps: a title and a line under it */
@Composable
private fun Pick(title: String, sub: String, onClick: () -> Unit) = Panel(onClick = onClick) {
    Text(title, style = MaterialTheme.typography.titleMedium); Quiet(sub)
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

/** the server's address for what someone typed: with no http(s):// both are tried, https first. The site's folder is kept (apps.perennia.org/zigora,
 *  for a server with BASE_PATH); the app's own part of a copied link (/app/..., #reset=...) is dropped */
fun serverCandidates(typed: String): List<String> {
    val t = typed.trim()
    val withScheme = if (t.startsWith("http://", true) || t.startsWith("https://", true)) listOf(t) else listOf("https://$t", "http://$t")
    return withScheme.mapNotNull { u ->
        runCatching { java.net.URI(u) }.getOrNull()?.takeIf { !it.host.isNullOrEmpty() }?.let {
            val folder = (it.rawPath ?: "").replace(Regex("/app(/.*)?$"), "").trimEnd('/').takeIf { f -> Regex("(/[A-Za-z0-9._~-]+)*").matches(f) } ?: ""
            "${it.scheme.lowercase()}://${it.host}" + (if (it.port != -1) ":${it.port}" else "") + folder
        }
    }.distinct()
}
