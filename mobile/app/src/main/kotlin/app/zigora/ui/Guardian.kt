package app.zigora.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import app.zigora.R
import app.zigora.data.AiStatus
import app.zigora.data.GProgress
import app.zigora.data.GStudents
import app.zigora.data.I18n
import app.zigora.data.Invitations
import app.zigora.data.KeyState
import app.zigora.data.Me
import app.zigora.data.Msg
import app.zigora.data.ProgOpts
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.addJsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** Parents and teachers (role "guardian"), the same as the web: their children or students, adding them (each signs in with a username),
 *  inviting students who already have an account (teachers), each one's progress (read-only), and the AI key that covers school students. */

const val AI_OFF = "AI help is off. A parent or teacher can turn it on by adding their AI key to their account."

/** true for a school student with no parent's or teacher's key: the app hides AI rather than offering it and failing.
 *  Asked of the server each time, since accepting a teacher's invitation or a parent adding a key turns it on. */
@Composable
fun rememberAiOff(): Boolean {
    val st = rememberLoad("ai-off") { runCatching { get("/ai/status", AiStatus.serializer()).off }.getOrDefault(false) }
    return (st.state as? Load.Ok)?.value == true
}

/** a labelled pick from a short list, as a button that opens a menu */
@Composable
fun Choice(label: String, value: String, options: List<Pair<String, () -> Unit>>) {
    var open by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth()) {
        Quiet(label)
        Box {
            OutlinedButton(onClick = { open = true }, modifier = Modifier.fillMaxWidth()) { Text(value, Modifier.weight(1f)) }
            DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                options.forEach { (l, pick) -> DropdownMenuItem(text = { Text(l) }, onClick = { open = false; pick() }) }
            }
        }
    }
}

/** a program of the chosen level and one of its open terms; "not listed" leaves it for an admin to place them */
@Composable
fun PlacePicker(opts: ProgOpts, level: String, program: Int?, sem: Int?, set: (Int?, Int?) -> Unit) {
    val ps = if (level == "school") opts.school else opts.college
    val p = ps.firstOrNull { it.id == program }
    val none = tl("Not listed: my admin will place me")
    Choice(if (level == "school") tl("School board or program") else tl("Program"), p?.name ?: none,
        listOf<Pair<String, () -> Unit>>(none to { set(null, null) }) + ps.map { x -> x.name to { set(x.id, null) } })
    if (p != null) Choice(tl(p.term), sem?.let { tl(p.term) + " $it" } ?: tl("Choose"), p.terms.map { n -> (tl(p.term) + " $n") to { set(p.id, n) } })
}

/** one child or student being added: a name, the username they sign in with, a password, and where they study */
data class NewStudent(val name: String = "", val username: String = "", val password: String = "", val program: Int? = null, val sem: Int? = null) {
    val ok get() = name.isNotBlank() && username.isNotBlank() && password.isNotEmpty() && (program == null || sem != null)
}
fun studentsJson(rows: List<NewStudent>): JsonArray = buildJsonArray {
    rows.forEach { r -> addJsonObject { put("name", r.name.trim()); put("username", r.username.trim()); put("password", r.password); put("program_id", r.program); put("semester", r.sem) } }
}

@Composable
fun StudentRows(rows: SnapshotStateList<NewStudent>, opts: ProgOpts, level: String, title: (Int) -> String, addLabel: String, max: Int) {
    rows.forEachIndexed { i, r ->
        Panel {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(title(i + 1), style = MaterialTheme.typography.titleSmall)
                OutlinedTextField(r.name, { rows[i] = r.copy(name = it) }, Modifier.fillMaxWidth(), label = { Text(tl("Name")) }, singleLine = true)
                OutlinedTextField(r.username, { v -> rows[i] = r.copy(username = v.lowercase().filterNot { it.isWhitespace() }) }, Modifier.fillMaxWidth(),
                    label = { Text(tl("Username")) }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii))
                OutlinedTextField(r.password, { rows[i] = r.copy(password = it) }, Modifier.fillMaxWidth(), label = { Text(stringResource(R.string.password)) },
                    singleLine = true, visualTransformation = PasswordVisualTransformation())
                PlacePicker(opts, level, r.program, r.sem) { p, s -> rows[i] = r.copy(program = p, sem = s) }
                if (rows.size > 1) TextButton(onClick = { rows.removeAt(i) }) { Text(tl("Remove")) }
            }
        }
    }
    if (rows.size < max) OutlinedButton(onClick = { val last = rows.lastOrNull(); rows.add(NewStudent(program = last?.program, sem = last?.sem)) },
                                        modifier = Modifier.fillMaxWidth()) { Text(addLabel) }
}

/** a parent's or teacher's whole app: one screen, with a student's progress and the AI key opened from it */
@Composable
fun GuardianHome(me: Me, signOut: () -> Unit) {
    var view by remember { mutableStateOf<Int?>(null) }
    var keyOpen by remember { mutableStateOf(false) }
    if (keyOpen) { MyKeyScreen(guardian = true) { keyOpen = false }; return }
    view?.let { sid -> StudentProgressScreen(sid) { view = null }; return }
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast()
    val list = rememberLoad("guardian-students") { get("/guardian/students", GStudents.serializer()) }
    val opts = rememberLoad("guardian-options") { runCatching { get("/guardian/options", ProgOpts.serializer()) }.getOrDefault(ProgOpts()) }
    val key = rememberLoad("guardian-key") { get("/me/ai-key", KeyState.serializer()) }
    val parent = me.relation == "parent"; val level = me.level ?: "school"
    var adding by remember { mutableStateOf(false) }
    val rows = remember { mutableStateListOf(NewStudent()) }
    var invite by remember { mutableStateOf("") }
    var sent by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var ask by remember { mutableStateOf<Ask?>(null) }
    Page(tl("Hello, {name}", "name" to firstName(me.name)), actions = { TextButton(onClick = signOut) { Text(stringResource(R.string.sign_out)) } }) {
        SectionTitle(if (parent) tl("Your children") else tl("Your students"))
        Loaded(list) { d ->
            if (d.students.isEmpty()) Quiet(if (parent) tl("No children are linked to your account yet.") else tl("No students yet. Add your class, or invite students who already have an account."))
            d.students.forEach { x ->
                val sub = listOfNotNull(x.username?.let { tl("Signs in as {username}", "username" to it) }, x.place.ifEmpty { tl("Waiting for an admin to place them") }).joinToString(" · ")
                val stop = { ask = Ask(tl("Stop following {name}?", "name" to x.name), tl("Their account and progress stay. You no longer see their progress, and your AI key no longer covers them."),
                                       tl("Stop following"), danger = true) { scope.launch { try { a.raw("DELETE", "/guardian/students/${x.id}"); list.reload() } catch (e: Exception) { toast(e.message.orEmpty()) } } } }
                ListRow(if (x.status == "invited") x.name + " · " + tl("Invited") else x.name, sub, onClick = if (x.status == "active") ({ view = x.id }) else null,
                        trailing = if (parent) null else ({ TextButton(onClick = stop) { Text(tl("Remove")) } }))
            }
            if (parent && d.students.isNotEmpty()) Quiet(tl("Each child signs in with their own username and password on the sign-in page."))
        }
        if (!adding) OutlinedButton(onClick = { rows.clear(); rows.add(NewStudent()); adding = true }, modifier = Modifier.fillMaxWidth()) { Text(if (parent) tl("Add a child") else tl("Add students")) }
        else {
            SectionTitle(if (parent) tl("Add a child") else tl("Add students"))
            Quiet(tl("Each one signs in with the username and password you give them. They don't need an email."))
            Loaded(opts) { o -> StudentRows(rows, o, level, { n -> if (parent) tl("Child {n}", "n" to n) else tl("Student {n}", "n" to n) }, tl("Add another student"), if (parent) 1 else 60) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = !busy && rows.all { it.ok }, onClick = { scope.launch {
                    busy = true
                    try { a.raw("POST", "/guardian/students", buildJsonObject { put("students", studentsJson(rows)) }); adding = false; list.reload()
                          toast(if (parent) tl("Added. They can sign in now.") else tl("Students added. They can sign in now.")) }
                    catch (e: Exception) { toast(e.message.orEmpty()) }
                    busy = false
                } }) { Text(tl("Save")) }
                TextButton(onClick = { adding = false }) { Text(tl("Cancel")) }
            }
        }
        if (!parent) {
            SectionTitle(tl("Invite a student"))
            Quiet(tl("For a student who already has an account. They see your invitation and choose whether to accept."))
            OutlinedTextField(invite, { invite = it }, Modifier.fillMaxWidth(), label = { Text(tl("Their email or username")) }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email))
            Button(enabled = !busy && invite.isNotBlank(), onClick = { scope.launch {
                busy = true
                try { sent = I18n.srv(a.send("POST", "/guardian/invite", buildJsonObject { put("login", invite.trim()) }, Msg.serializer()).message); invite = ""; list.reload() }
                catch (e: Exception) { toast(e.message.orEmpty()) }
                busy = false
            } }) { Text(tl("Send invitation")) }
            if (sent.isNotEmpty()) Quiet(sent)
        }
        if (level == "school") {
            SectionTitle(tl("AI help"))
            Loaded(key) { k ->
                Panel {
                    Text(if (k.key_set) tl("On, with your key {hint}", "hint" to k.key_hint) else tl("Off"), style = MaterialTheme.typography.titleMedium)
                    Quiet(if (k.key_set) (if (parent) tl("Your children's AI help runs on your DeepSeek key.") else tl("Your students' AI help runs on your DeepSeek key, unless a parent has added theirs."))
                          else (if (parent) tl("School students use AI only with a parent's or teacher's key. Add your DeepSeek key to turn it on for your children.")
                                else tl("School students use AI only with a parent's or teacher's key. Add your DeepSeek key to turn it on for your students.")))
                    OutlinedButton(onClick = { keyOpen = true }) { Text(if (k.key_set) tl("Change the key") else tl("Add an AI key")) }
                }
            }
        }
    }
    AskDialog(ask) { ask = null }
}

/** what a parent or teacher sees of one student: per course, topics learned and opened, tests, when they last studied. Never their notes */
@Composable
fun StudentProgressScreen(id: Int, back: () -> Unit) {
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast()
    var pw by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    val p = rememberLoad("guardian-progress", id) { get("/guardian/students/$id/progress", GProgress.serializer()) }
    val d0 = (p.state as? Load.Ok)?.value
    Page(d0?.name ?: tl("Loading"), d0?.place.orEmpty(), back = back) {
        Loaded(p) { d ->
            if (d.courses.isEmpty()) Quiet(tl("No courses yet. They appear once an admin places them in a program."))
            d.courses.forEach { c ->
                val bits = mutableListOf(tl("{done} of {n} topics learned · {opened} opened", "done" to c.completed, "n" to c.topics, "opened" to c.opened))
                if (c.tests > 0) bits += tl("tests {taken} of {n}", "taken" to c.tests_taken, "n" to c.tests) + (c.test_average?.let { ", " + tl("average {p}%", "p" to it) } ?: "")
                bits += c.last_active?.let { tl("last studied {when}", "when" to day(it)) } ?: tl("not started yet")
                ListRow(c.course, bits.joinToString(" · "), extra = { ScoreBar(if (c.topics > 0) 100 * c.completed / c.topics else 0) })
            }
            Quiet(tl("You see progress only, never their own notes or highlights."))
            if (d.can_reset) {  // a username account has no email to reset from: the parent or teacher sets a new password
                SectionTitle(tl("Forgot their password?"))
                Quiet(tl("They sign in with a username, so there is no email to reset it from. Set a new one here and tell them."))
                OutlinedTextField(pw, { pw = it }, Modifier.fillMaxWidth(), label = { Text(tl("New password")) }, singleLine = true, visualTransformation = PasswordVisualTransformation())
                OutlinedButton(enabled = !busy && pw.length >= 8, onClick = { scope.launch {
                    busy = true
                    try { a.raw("PUT", "/guardian/students/$id/password", buildJsonObject { put("password", pw) }); pw = ""; toast(tl("Password changed. Tell them the new one.")) }
                    catch (e: Exception) { toast(e.message.orEmpty()) }
                    busy = false
                } }) { Text(tl("Set a new password")) }
            }
        }
    }
}

/** on a student's Home: a teacher asked to follow their progress. Nothing is shared until they accept */
@Composable
fun InvitationsCard() {
    val a = api(); val scope = rememberCoroutineScope()
    val inv = rememberLoad("invitations") { runCatching { get("/me/invitations", Invitations.serializer()) }.getOrDefault(Invitations()) }
    (inv.state as? Load.Ok)?.value?.invitations.orEmpty().forEach { x ->
        Panel {
            Text(tl("{name} wants to follow your progress", "name" to x.name), style = MaterialTheme.typography.titleMedium)
            Quiet((if (x.institution.isNotEmpty()) x.institution + " · " else "") +
                  tl("They would see which topics you have learned and your test scores, never your notes. For school students, their AI key can also give you AI help."))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { scope.launch { runCatching { a.raw("POST", "/me/invitations/${x.id}/accept") }; inv.reload() } }) { Text(tl("Accept")) }
                OutlinedButton(onClick = { scope.launch { runCatching { a.raw("POST", "/me/invitations/${x.id}/decline") }; inv.reload() } }) { Text(tl("Decline")) }
            }
        }
    }
}
