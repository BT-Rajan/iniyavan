package app.zigora.ui

import androidx.compose.material.icons.outlined.AssignmentTurnedIn
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import app.zigora.R
import app.zigora.data.AiStatus
import app.zigora.data.GDash
import app.zigora.data.GDashItem
import app.zigora.data.GProgress
import app.zigora.data.GWard
import app.zigora.data.GStudents
import app.zigora.data.I18n
import app.zigora.data.Invitations
import app.zigora.data.KeyState
import app.zigora.data.Me
import app.zigora.data.Msg
import app.zigora.data.ProgOpts
import app.zigora.data.WardActivity
import app.zigora.data.WardArea
import app.zigora.data.WardMcq
import app.zigora.data.WardScores
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
                    singleLine = true, visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))  // no capitals or autocorrect slipped in unseen
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
    var calOpen by remember { mutableStateOf(false) }
    if (calOpen) { CalendarScreen { calOpen = false }; return }
    var asgOpen by remember { mutableStateOf(false) }
    if (asgOpen) { TeacherAssignmentsScreen { asgOpen = false }; return }
    view?.let { sid -> StudentProgressScreen(sid, me.level ?: "school") { view = null }; return }  // coming back loads the list again, so a change shows
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast()
    val list = rememberLoad("guardian-students") { get("/guardian/students", GStudents.serializer()) }
    val dash = rememberLoad("guardian-dashboard") { get("/guardian/dashboard", GDash.serializer()) }
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
        val dd = (dash.state as? Load.Ok)?.value
        if (dd != null && dd.items.isNotEmpty()) {
            SectionTitle(tl("Needs you"))
            dd.items.forEach { x -> NeedsYouRow(x) { if (x.action == "key") keyOpen = true else view = x.student_id } }
        } else if (dd != null && dd.students.isNotEmpty()) Panel { Text(if (parent) tl("All good. Nothing needs you right now.") else tl("All good. No student needs you right now."), style = MaterialTheme.typography.titleMedium) }
        SectionTitle(if (parent) tl("Your children") else tl("Your students"))
        dd?.students?.forEach { c -> WardSummary(c) { view = c.id } }
        Loaded(list) { d ->
            if (d.students.isEmpty()) Quiet(if (parent) tl("No children are linked to your account yet.") else tl("No students yet. Add your class, or invite students who already have an account."))
            d.students.filter { it.status != "active" || dd == null }.forEach { x ->
                val sub = listOfNotNull(x.username?.let { tl("Signs in as {username}", "username" to it) }, x.place.ifEmpty { tl("Waiting for an admin to place them") }).joinToString(" · ")
                val stop = { ask = Ask(tl("Stop following {name}?", "name" to x.name), tl("Their account and progress stay. You no longer see their progress, and your AI key no longer covers them."),
                                       tl("Stop following"), danger = true) { scope.launch { try { a.raw("DELETE", "/guardian/students/${x.id}"); list.reload(); dash.reload() } catch (e: Exception) { toast(e.message.orEmpty()) } } } }
                ListRow(if (x.status == "invited") x.name + " · " + tl("Invited") else x.name, sub, onClick = if (x.status == "active") ({ view = x.id }) else null,
                        trailing = if (parent) null else ({ TextButton(onClick = stop) { Text(tl("Remove")) } }))
            }
            if (parent && d.students.isNotEmpty()) Quiet(tl("Each child signs in with their own username and password on the sign-in page."))
            if (!parent) ListRow(tl("Assigned tests"), tl("See how each student is doing on the tests you gave"), onClick = { asgOpen = true },
                                 leading = { RowIcon(androidx.compose.material.icons.Icons.Outlined.AssignmentTurnedIn) })
            if (d.students.any { it.status == "active" }) {
                ListRow(if (parent) tl("Your children's calendar") else tl("Your students' calendar"), tl("Exams, deadlines and study days in one place"), onClick = { calOpen = true },
                        leading = { RowIcon(androidx.compose.material.icons.Icons.Outlined.CalendarMonth) })
                GuardianReminders(parent)
            }
        }
        if (!adding) OutlinedButton(onClick = { rows.clear(); rows.add(NewStudent()); adding = true }, modifier = Modifier.fillMaxWidth()) { Text(if (parent) tl("Add a child") else tl("Add students")) }
        else {
            SectionTitle(if (parent) tl("Add a child") else tl("Add students"))
            Quiet(tl("Each one signs in with the username and password you give them. They don't need an email."))
            Loaded(opts) { o -> StudentRows(rows, o, level, { n -> if (parent) tl("Child {n}", "n" to n) else tl("Student {n}", "n" to n) }, tl("Add another student"), if (parent) 1 else 60) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = !busy && rows.all { it.ok }, onClick = { scope.launch {
                    busy = true
                    try { a.raw("POST", "/guardian/students", buildJsonObject { put("students", studentsJson(rows)) }); adding = false; list.reload(); dash.reload()
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
                    Quiet(if (k.key_set) (if (parent) tl("Your children's AI help runs on your AI key.") else tl("Your students' AI help runs on your AI key, unless a parent has added theirs."))
                          else (if (parent) tl("School students use AI only with a parent's or teacher's key. Add your AI key to turn it on for your children.")
                                else tl("School students use AI only with a parent's or teacher's key. Add your AI key to turn it on for your students.")))
                    OutlinedButton(onClick = { keyOpen = true }) { Text(if (k.key_set) tl("Change the key") else tl("Add an AI key")) }
                }
            }
        }
    }
    AskDialog(ask) { ask = null }
}

/** what a parent or teacher sees of one student: per course, topics learned and opened, tests, when they last studied. Never their notes */
@Composable
fun StudentProgressScreen(id: Int, level: String, back: () -> Unit) {
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast()
    var pw by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<NewStudent?>(null) }  // the name and place being changed
    var opts by remember { mutableStateOf(ProgOpts()) }
    var ask by remember { mutableStateOf<Ask?>(null) }
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
            d.activity?.let { WardActivityCard(it) }
            d.scores?.let { WardScoresCard(it, d.mcq) }
            Quiet(tl("You see progress only, never their own notes or highlights."))
            if (d.can_reset) {  // a username account has no email to reset from: the parent or teacher sets a new password
                SectionTitle(tl("Forgot their password?"))
                Quiet(tl("They sign in with a username, so there is no email to reset it from. Set a new one here and tell them."))
                OutlinedTextField(pw, { pw = it }, Modifier.fillMaxWidth(), label = { Text(tl("New password")) }, singleLine = true, visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
                OutlinedButton(enabled = !busy && pw.length >= 8, onClick = { scope.launch {
                    busy = true
                    try { a.raw("PUT", "/guardian/students/$id/password", buildJsonObject { put("password", pw) }); pw = ""; toast(tl("Password changed. Tell them the new one.")) }
                    catch (e: Exception) { toast(e.message.orEmpty()) }
                    busy = false
                } }) { Text(tl("Set a new password")) }
                val e = editing
                if (e == null) OutlinedButton(onClick = {
                    editing = NewStudent(name = d.name, program = d.program_id, sem = d.semester)
                    scope.launch { opts = runCatching { a.get("/guardian/options", ProgOpts.serializer()) }.getOrDefault(ProgOpts()) }
                }) { Text(tl("Change their name or grade")) }
                else Panel {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(e.name, { editing = e.copy(name = it) }, Modifier.fillMaxWidth(), label = { Text(tl("Name")) }, singleLine = true)
                        PlacePicker(opts, level, e.program, e.sem) { pg, sm -> editing = e.copy(program = pg, sem = sm) }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(enabled = !busy && e.name.isNotBlank() && (e.program == null || e.sem != null), onClick = { scope.launch {
                                busy = true
                                try { a.raw("PATCH", "/guardian/students/$id", buildJsonObject { put("name", e.name.trim()); put("program_id", e.program); put("semester", e.sem) })
                                      editing = null; p.reload(); toast(tl("Changes saved")) }
                                catch (x: Exception) { toast(x.message.orEmpty()) }
                                busy = false
                            } }) { Text(tl("Save")) }
                            TextButton(onClick = { editing = null }) { Text(tl("Cancel")) }
                        }
                    }
                }
            }
            Gap(8)
            TextButton(onClick = {
                ask = Ask(tl("Remove {name}?", "name" to d.name),
                          if (d.can_reset) tl("Their progress stays. If no other parent or teacher looks after them, their account is switched off, since they have no email of their own. An admin can switch it back on.")
                          else tl("Their account and progress stay. You no longer see their progress, and your AI key no longer covers them."),
                          tl("Remove"), danger = true) { scope.launch { try { a.raw("DELETE", "/guardian/students/$id"); toast(tl("Removed")); onMain { back() } } catch (x: Exception) { toast(x.message.orEmpty()) } } }
            }) { Text(tl("Remove {name} from my list", "name" to d.name), color = MaterialTheme.colorScheme.error) }
        }
    }
    AskDialog(ask) { ask = null }
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

/** the quiet daily note, for a parent or teacher: what is on their children's calendar today and tomorrow (the same note students can turn on) */
@Composable
private fun GuardianReminders(parent: Boolean) {
    val ctx = androidx.compose.ui.platform.LocalContext.current; val a = app()
    var on by remember { mutableStateOf(a.store.reminders) }
    val ask = androidx.activity.compose.rememberLauncherForActivityResult(androidx.activity.result.contract.ActivityResultContracts.RequestPermission()) { ok ->
        on = ok; a.store.reminders = ok; app.zigora.Reminders.schedule(ctx, ok)
    }
    ListRow(stringResource(R.string.daily_note), if (parent) tl("Once a day, when something on your children's calendar is today or tomorrow") else tl("Once a day, when one of your own calendar events is today or tomorrow"),
            trailing = { androidx.compose.material3.Switch(on, { v ->
                if (v && androidx.core.content.ContextCompat.checkSelfPermission(ctx, android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED)
                    ask.launch(android.Manifest.permission.POST_NOTIFICATIONS)
                else { on = v; a.store.reminders = v; app.zigora.Reminders.schedule(ctx, v) }
            }) })
}

/** a student's study days over the last four weeks, their streak and the routine they set, as their parent or teacher sees it */
@Composable
private fun WardActivityCard(a: WardActivity) {
    val loc = LocalConfiguration.current.locales[0]
    SectionTitle(tl("Study activity"))
    Quiet(tl("{streak}-day streak · studied on {week} of the last 7 days and {days} of the last 28 · {done} topics learned this week",
        "streak" to a.streak, "week" to a.active_days_week, "days" to a.active_days_28, "done" to a.completed_this_week))
    a.days.chunked(7).forEach { week ->
        Row(Modifier.fillMaxWidth().padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            week.forEach { x ->
                val wd = runCatching { java.time.LocalDate.parse(x.date).dayOfMonth.toString() }.getOrDefault("")  // the date, so the four weeks read as a calendar
                Text(wd, Modifier.weight(1f).background(if (x.active) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(50)).padding(vertical = 4.dp),
                    textAlign = TextAlign.Center, style = MaterialTheme.typography.labelSmall,
                    color = if (x.active) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
    val r = a.routine
    Quiet(if (r == null) tl("They have not set a study routine yet.") else {
        val names = r.days.mapIndexedNotNull { i, c -> if (c == '1') java.time.DayOfWeek.of(i + 1).getDisplayName(java.time.format.TextStyle.SHORT, loc) else null }.joinToString(", ")
        tl("Their routine: {days}, {minutes} minutes{at}", "days" to names, "minutes" to r.minutes, "at" to (r.at?.let { " " + tl("at {time}", "time" to it) } ?: ""))
    }, Modifier.padding(top = 8.dp))
}

/** their quiz and test scores per course, the topics they are strong in and the ones to study again, and their MCQ practice */
@Composable
private fun WardScoresCard(sc: WardScores, mcq: WardMcq?) {
    SectionTitle(tl("Scores"))
    if (sc.quizzes_taken == 0) Quiet(tl("No quizzes or tests taken yet."))
    else {
        sc.courses.forEach { c -> ListRow(c.course, tl("Correct answers in quizzes and tests"), extra = { ScoreBar(c.percent) }, trailing = { Text("${c.percent}%") }) }
        listOf(tl("Needs more study") to sc.needs_study, tl("Getting there") to sc.getting_there, tl("Strong") to sc.strong).forEach { (title, list: List<WardArea>) ->
            if (list.isNotEmpty()) {
                Text(title, style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 10.dp))
                list.forEach { x -> ListRow(x.title, x.course, trailing = { Text("${x.percent}%") }) }
            }
        }
    }
    if (mcq != null) {
        SectionTitle(tl("MCQ practice"))
        Quiet(if (mcq.sets > 0) tl("{sets} sets done, {average}% correct on average. Last practised {when}.", "sets" to mcq.sets, "average" to (mcq.average ?: 0), "when" to (mcq.last_at?.let { day(it) } ?: ""))
              else tl("No MCQ practice yet."))
        if (mcq.revisit.isNotEmpty()) Quiet(tl("Topics to revisit: {topics}", "topics" to mcq.revisit.joinToString(", ")))
    }
}

/** one thing a child needs from their parent or teacher, with the one action that deals with it; the dot says how soon */
@Composable
private fun NeedsYouRow(x: GDashItem, act: () -> Unit) {
    val v = x.vars.mapValues { (k, e) -> val raw = (e as? kotlinx.serialization.json.JsonPrimitive)?.content.orEmpty(); if (k == "date") day(raw) else raw }
    val dot = when (x.level) { "now" -> MaterialTheme.colorScheme.error; "soon" -> MaterialTheme.colorScheme.tertiary; else -> MaterialTheme.colorScheme.outline }
    ListRow(tl(x.text, *v.map { it.key to it.value }.toTypedArray()), "", onClick = act,
        leading = { Box(Modifier.padding(4.dp).background(dot, RoundedCornerShape(50)).padding(5.dp)) },
        trailing = { TextButton(onClick = act) { Text(if (x.action == "key") tl("Add an AI key") else tl("See progress")) } })
}

/** a child at a glance: streak, this week's study days, topics learned this week and when they last studied. Tapping opens their progress */
@Composable
private fun WardSummary(c: GWard, open: () -> Unit) {
    val loc = LocalConfiguration.current.locales[0]; val today = java.time.LocalDate.now()
    Panel(onClick = open) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(c.name, style = MaterialTheme.typography.titleMedium)
            Text(tl("{n}-day streak", "n" to c.streak), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        }
        if (c.place.isNotEmpty()) Quiet(c.place)
        Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            c.week.forEachIndexed { i, on ->
                val wd = today.minusDays((6 - i).toLong()).dayOfWeek.getDisplayName(java.time.format.TextStyle.NARROW, loc)
                Text(wd, Modifier.weight(1f).background(if (on) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(50)).padding(vertical = 6.dp),
                    textAlign = TextAlign.Center, style = MaterialTheme.typography.labelMedium,
                    color = if (on) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Quiet(tl("Topics learned this week: {n}", "n" to c.completed_this_week) + " · " + (c.last_studied?.let { tl("last studied {when}", "when" to day(it)) } ?: tl("not started yet")))
    }
}
