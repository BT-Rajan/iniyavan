package app.zigora.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.zigora.data.CalItem
import app.zigora.data.CalLink
import app.zigora.data.CalResp
import app.zigora.data.I18n
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale

// The calendar, as on the web: events people add beside what Zigora knows (learn-by dates, study sessions, days studied, results). A parent or
// teacher picks one of their students. Here people add events for themselves (a parent also for a child); course and program events are added on the web.
private val KINDS = listOf("exam" to "Exam", "test" to "Test", "assignment" to "Assignment", "holiday" to "Holiday", "event" to "Event", "reminder" to "Reminder")
private val TAG = mapOf("exam" to "Exam", "test" to "Test", "assignment" to "Assignment", "holiday" to "Holiday", "event" to "Event", "reminder" to "Reminder",
    "deadline" to "Learn by", "session" to "Study session", "studied" to "Studied", "result" to "Result", "plan" to "Plan")
private val STATE = mapOf("done" to "Done", "missed" to "Missed", "overdue" to "Overdue")

@Composable
private fun kindColor(kind: String): Color = when (kind) {
    "exam" -> MaterialTheme.colorScheme.error
    "test" -> Color(0xFF9A6420); "assignment" -> Color(0xFF1C6AA0); "deadline" -> Color(0xFFE07A7A)
    "holiday", "result", "studied" -> Color(0xFF1B7F55); "reminder" -> MaterialTheme.colorScheme.onSurfaceVariant
    "session" -> MaterialTheme.colorScheme.primary.copy(alpha = .55f)
    else -> MaterialTheme.colorScheme.primary
}
private fun covers(x: CalItem, d: String) = x.date == d || (x.end != null && x.date <= d && d <= x.end)
private fun dayLabel(s: String) = runCatching { LocalDate.parse(s).let { "${it.dayOfMonth} ${it.month.getDisplayName(TextStyle.SHORT, Locale.getDefault())}" } }.getOrDefault(s)

/** an event being added or changed */
private data class EventForm(val id: Int? = null, val title: String = "", val kind: String = "reminder", val day: String, val end: String = "", val at: String = "",
                             val notes: String = "", val user: Int? = null)

@Composable
private fun CalRow(x: CalItem, edit: ((CalItem) -> Unit)?) {
    val c = kindColor(x.kind)
    val title = if (x.event != null) x.title else tl(x.title)  // people's own words stay as they are
    val meta = listOfNotNull(tl(TAG[x.kind] ?: ""), x.end?.let { tl("{a} to {b}", "a" to dayLabel(x.date), "b" to dayLabel(it)) }, x.at, x.sub.takeIf { it.isNotEmpty() }?.let { I18n.srv(it) })
        .filter { it.isNotEmpty() }.joinToString(" · ")
    ListRow(title + (STATE[x.state]?.let { " · " + tl(it) } ?: ""), meta, onClick = if (x.event?.can_edit == true && edit != null) ({ edit(x) }) else null,
            leading = { Box(Modifier.size(12.dp).background(c, CircleShape)) },
            extra = { x.event?.notes?.takeIf { it.isNotEmpty() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) } })
}

@Composable
fun CalendarScreen(back: (() -> Unit)?) {
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast(); val ctx = LocalContext.current
    var month by remember { mutableStateOf(LocalDate.now().withDayOfMonth(1)) }
    var day by remember { mutableStateOf<String?>(null) }
    var student by remember { mutableIntStateOf(0) }
    var tick by remember { mutableIntStateOf(0) }
    var form by remember { mutableStateOf<EventForm?>(null) }
    var link by remember { mutableStateOf<CalLink?>(null) }
    var url by remember { mutableStateOf<String?>(null) }
    var ask by remember { mutableStateOf<Ask?>(null) }
    val start = month.minusDays((month.dayOfWeek.value - 1).toLong())  // the Monday on or before the 1st
    val data = rememberLoad("calendar", month, student, tick) {
        get("/calendar?start=$start&end=${start.plusDays(41)}" + (if (student != 0) "&student=$student" else ""), CalResp.serializer())
    }
    LaunchedEffect(Unit) { link = runCatching { a.get("/calendar/link", CalLink.serializer()) }.getOrNull() }
    val d = (data.state as? Load.Ok)?.value
    val today = d?.today?.takeIf { it.isNotEmpty() } ?: LocalDate.now().toString()
    val items = d?.items.orEmpty()
    val open = { x: CalItem? ->
        form = x?.event?.let { e -> EventForm(e.id, x.title, x.kind, x.date, x.end.orEmpty(), x.at.orEmpty(), e.notes, e.user_id) }
            ?: EventForm(day = day ?: today, user = student.takeIf { it != 0 })
    }
    Page(tl("Calendar"), d?.student?.let { tl("{name}'s calendar", "name" to it.name) }.orEmpty(), back) {
        if (d != null && d.students.isNotEmpty()) Choice(tl("Whose calendar"), d.students.firstOrNull { it.id == student }?.name ?: tl("My own events"),
            listOf<Pair<String, () -> Unit>>(tl("My own events") to { student = 0; day = null }) + d.students.map { s -> s.name to { student = s.id; day = null } })
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
            IconButton(onClick = { month = month.minusMonths(1); day = null }) { Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, tl("Previous month")) }
            Text(month.month.getDisplayName(TextStyle.FULL_STANDALONE, Locale.getDefault()) + " ${month.year}", Modifier.weight(1f), textAlign = TextAlign.Center,
                 style = MaterialTheme.typography.titleMedium)
            IconButton(onClick = { month = month.plusMonths(1); day = null }) { Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, tl("Next month")) }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { month = LocalDate.now().withDayOfMonth(1); day = today }) { Text(tl("Today")) }
            Button(onClick = { open(null) }) { Text(tl("Add event")) }
        }
        Row(Modifier.fillMaxWidth()) {
            (0..6).forEach { i -> Text(start.plusDays(i.toLong()).dayOfWeek.getDisplayName(TextStyle.NARROW, Locale.getDefault()), Modifier.weight(1f),
                                       textAlign = TextAlign.Center, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        (0 until 6).forEach { w ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                (0..6).forEach { i ->
                    val c = start.plusDays((w * 7 + i).toLong()); val k = c.toString(); val xs = items.filter { covers(it, k) }
                    val marks = xs.filter { it.kind != "studied" }; val studied = xs.any { it.kind == "studied" }
                    val out = c.month != month.month; val sel = day == k
                    Column(Modifier.weight(1f).heightIn(min = 48.dp).background(if (sel) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface, RoundedCornerShape(8.dp))
                        .border(if (k == today) 2.dp else 1.dp, if (k == today) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(8.dp))
                        .clickable { day = if (sel) null else k }.padding(vertical = 4.dp)
                        .semantics { contentDescription = "${c.dayOfMonth} ${c.month.getDisplayName(TextStyle.FULL, Locale.getDefault())}" +
                                     (if (marks.isNotEmpty()) ", " + tl(if (marks.size == 1) "{n} item" else "{n} items", "n" to marks.size) else "") + (if (studied) ", " + tl("studied") else "") },
                        horizontalAlignment = Alignment.CenterHorizontally) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("${c.dayOfMonth}", fontWeight = FontWeight.SemiBold, color = if (out) MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = .5f) else MaterialTheme.colorScheme.onSurface)
                            if (studied) Box(Modifier.padding(start = 2.dp).size(5.dp).background(Color(0xFF1B7F55), CircleShape))
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(2.dp)) { marks.take(4).forEach { m -> Box(Modifier.size(6.dp).background(kindColor(m.kind).copy(alpha = if (m.state == "missed") .35f else 1f), CircleShape)) } }
                    }
                }
            }
        }
        Loaded(data) { r ->
            val sel = day
            if (sel != null) {
                SectionTitle(runCatching { LocalDate.parse(sel).let { "${it.dayOfWeek.getDisplayName(TextStyle.FULL, Locale.getDefault())}, ${dayLabel(sel)}" } }.getOrDefault(sel))
                val xs = r.items.filter { covers(it, sel) }
                if (xs.isEmpty()) Quiet(tl("Nothing on this day.")) else xs.forEach { CalRow(it) { x -> open(x) } }
            } else {
                SectionTitle(tl("Coming up"))
                val up = r.items.filter { (it.end ?: it.date) >= today && it.kind !in listOf("studied", "result") && it.state != "done" }.take(8)
                if (up.isEmpty()) Quiet(tl("Nothing coming up this month.")) else up.forEach { CalRow(it) { x -> open(x) } }
            }
        }
        SectionTitle(tl("On your phone's calendar"))
        Quiet(tl("A private link your phone's calendar (Google, Apple or Outlook) can subscribe to. It keeps itself up to date. Anyone with the link can see these dates, so keep it to yourself."))
        val u = url
        if (u != null) {
            Text(u, style = MaterialTheme.typography.bodySmall)
            Button(onClick = {
                ctx.startActivity(android.content.Intent.createChooser(android.content.Intent(android.content.Intent.ACTION_SEND).setType("text/plain")
                    .putExtra(android.content.Intent.EXTRA_TEXT, u), tl("Calendar link")))
            }, modifier = Modifier.fillMaxWidth()) { Text(tl("Share link")) }
            Quiet(tl("In Google Calendar: Other calendars, +, From URL. On an iPhone: Settings, Calendar, Accounts, Add Account, Other, Add Subscribed Calendar."))
        } else if (link?.on == true) Quiet(tl("Your link is on. To see it again, make a new one (the old one then stops)."))
        val make = { scope.launch {
            try { val r = a.send("POST", "/calendar/link", null, CalLink.serializer()); link = r; url = a.base + r.path.orEmpty() } catch (e: Exception) { toast(e.message.orEmpty()) }
        }; Unit }
        OutlinedButton(onClick = {
            if (link?.on == true) ask = Ask(tl("Make a new link?"), tl("The old link stops working: calendars that use it need the new one."), tl("Make a new link")) { make() } else make()
        }, modifier = Modifier.fillMaxWidth()) { Text(if (link?.on == true) tl("Make a new link") else tl("Get my calendar link")) }
        if (link?.on == true) TextButton(onClick = { scope.launch {
            try { link = a.send("POST", "/calendar/link/off", null, CalLink.serializer()); url = null; toast(tl("Calendar link turned off")) } catch (e: Exception) { toast(e.message.orEmpty()) }
        } }, modifier = Modifier.fillMaxWidth()) { Text(tl("Turn the link off")) }
    }
    AskDialog(ask) { ask = null }
    form?.let { f -> EventDialog(f, d?.students.orEmpty().map { it.id to it.name }, close = { form = null }, saved = { m -> form = null; tick++; toast(m) }) }
}

@Composable
private fun EventDialog(start: EventForm, students: List<Pair<Int, String>>, close: () -> Unit, saved: (String) -> Unit) {
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast(); val ctx = LocalContext.current
    var f by remember { mutableStateOf(start) }
    var busy by remember { mutableStateOf(false) }
    var ask by remember { mutableStateOf<Ask?>(null) }
    fun pickDate(cur: String, set: (String) -> Unit) {
        val d = runCatching { LocalDate.parse(cur) }.getOrDefault(LocalDate.now())
        android.app.DatePickerDialog(ctx, { _, y, m, dd -> set(LocalDate.of(y, m + 1, dd).toString()) }, d.year, d.monthValue - 1, d.dayOfMonth).show()
    }
    val save = { scope.launch {
        busy = true
        try {
            val body = buildJsonObject {
                put("title", f.title.trim()); put("kind", f.kind); put("day", f.day); put("end_day", if (f.end.isEmpty()) JsonNull else JsonPrimitive(f.end))
                put("at", if (f.at.isEmpty() || f.end.isNotEmpty()) JsonNull else JsonPrimitive(f.at)); put("notes", f.notes.trim()); put("scope", "user"); put("user_id", f.user?.let { JsonPrimitive(it) } ?: JsonNull)
            }
            if (f.id != null) a.raw("PUT", "/calendar/events/${f.id}", body) else a.raw("POST", "/calendar/events", body)
            saved(if (f.id != null) tl("Event saved") else tl("Event added"))
        } catch (e: Exception) { toast(e.message.orEmpty()) }
        busy = false
    }; Unit }
    AlertDialog(onDismissRequest = close, title = { Text(if (f.id != null) tl("Edit event") else tl("Add an event")) }, text = {
        Column(Modifier.fillMaxWidth().padding(top = 4.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(f.title, { f = f.copy(title = it.take(200)) }, Modifier.fillMaxWidth(), label = { Text(tl("Title")) }, singleLine = true)
            Choice(tl("Kind"), tl(KINDS.firstOrNull { it.first == f.kind }?.second ?: "Event"), KINDS.map { (k, l) -> tl(l) to { f = f.copy(kind = k) } })
            Choice(tl("Date"), dayLabel(f.day), listOf(tl("Choose") to { pickDate(f.day) { f = f.copy(day = it) } }))
            Choice(tl("Ends on (optional)"), if (f.end.isEmpty()) "—" else dayLabel(f.end),
                   listOf(tl("Choose") to { pickDate(f.end.ifEmpty { f.day }) { f = f.copy(end = it) } }) + (if (f.end.isNotEmpty()) listOf(tl("Clear") to { f = f.copy(end = "") }) else emptyList()))
            if (f.end.isEmpty()) Choice(tl("Time (optional)"), f.at.ifEmpty { "—" }, listOf(tl("Choose") to {
                val (h, m) = f.at.split(":").let { (it.getOrNull(0)?.toIntOrNull() ?: 9) to (it.getOrNull(1)?.toIntOrNull() ?: 0) }
                android.app.TimePickerDialog(ctx, { _, hh, mm -> f = f.copy(at = "%02d:%02d".format(hh, mm)) }, h, m, true).show()
            }) + (if (f.at.isNotEmpty()) listOf(tl("Clear") to { f = f.copy(at = "") }) else emptyList()))
            if (students.isNotEmpty()) Choice(tl("For"), students.firstOrNull { it.first == f.user }?.second ?: tl("Me"),
                                              listOf<Pair<String, () -> Unit>>(tl("Me") to { f = f.copy(user = null) }) + students.map { (id, n) -> n to { f = f.copy(user = id) } })
            OutlinedTextField(f.notes, { f = f.copy(notes = it.take(1000)) }, Modifier.fillMaxWidth(), label = { Text(tl("Notes (optional)")) }, minLines = 2,
                              keyboardOptions = KeyboardOptions.Default)
            if (f.id != null) TextButton(onClick = { ask = Ask(tl("Delete this event?"), tl("It goes from everyone's calendar it was on."), tl("Delete"), danger = true) {
                scope.launch { try { a.raw("DELETE", "/calendar/events/${f.id}"); saved(tl("Event deleted")) } catch (e: Exception) { toast(e.message.orEmpty()) } }
            } }) { Text(tl("Delete event"), color = MaterialTheme.colorScheme.error) }
        }
    }, confirmButton = { TextButton(enabled = !busy && f.title.isNotBlank(), onClick = save) { Text(if (f.id != null) tl("Save") else tl("Add event")) } },
       dismissButton = { TextButton(onClick = close) { Text(tl("Cancel")) } })
    AskDialog(ask) { ask = null }
}

/** Home: the next few things on the calendar, and the way into it */
@Composable
fun ComingUp(openCalendar: () -> Unit) {
    val now = LocalDate.now()
    val r = rememberLoad("coming-up") { runCatching { get("/calendar?start=$now&end=${now.plusDays(14)}", CalResp.serializer()) }.getOrNull() }
    val xs = (r.state as? Load.Ok)?.value?.items.orEmpty().filter { it.kind !in listOf("studied", "result", "session") && it.state != "done" }
    if (xs.isNotEmpty()) { SectionTitle(tl("Coming up")); xs.take(3).forEach { CalRow(it, null) } }
    ListRow(tl("Calendar"), tl("Exams, deadlines and your study days in one place"), onClick = openCalendar, leading = { RowIcon(Icons.Outlined.CalendarMonth) })
}
