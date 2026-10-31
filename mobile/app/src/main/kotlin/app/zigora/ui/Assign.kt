package app.zigora.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import app.zigora.data.McqSet
import app.zigora.data.MyAssignment
import app.zigora.data.MyAssignments
import app.zigora.data.TAssignDetail
import app.zigora.data.TAssignments
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** "1 attempt", "3 attempts" or unlimited (0), as on the web */
fun attemptsText(n: Int) = if (n == 0) tl("Unlimited attempts") else tl(if (n == 1) "1 attempt" else "{n} attempts", "n" to n)

/** a due time the server gave on the students' clock ("2026-11-05T17:00"), in the phone's own language */
fun dueText(v: String): String = runCatching {
    java.time.format.DateTimeFormatter.ofLocalizedDateTime(java.time.format.FormatStyle.MEDIUM, java.time.format.FormatStyle.SHORT).format(java.time.LocalDateTime.parse(v.take(16)))
}.getOrDefault(v.take(16).replace('T', ' '))

/** done, late, missed or to do, with the score that counts; the colour says which */
@Composable
fun StateText(status: String, best: Int?, lateBest: Int?) {
    val (label, color) = when (status) {
        "done" -> tl("Done") to Color(0xFF2E7D32); "late" -> tl("Late") to Color(0xFFB26A00)
        "missed" -> tl("Missed") to MaterialTheme.colorScheme.error; else -> tl("To do") to MaterialTheme.colorScheme.onSurfaceVariant
    }
    val score = if (status == "done" && best != null) " · $best%" else if (status == "late" && lateBest != null) " · $lateBest%" else ""
    Text(label + score, style = MaterialTheme.typography.labelLarge, color = color)
}

/** a student's assigned tests: still to do first (soonest due), each with who gave it, when it is due and the attempts left. A quiz opens as any quiz does;
 *  an MCQ set starts through its assignment (outside the daily MCQ limit) and gives back the set already open for it */
@Composable
fun AssignedScreen(back: () -> Unit, openQuiz: (Int) -> Unit, openSet: (Int) -> Unit) {
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast()
    val list = rememberLoad("me-assignments") { get("/me/assignments", MyAssignments.serializer()) }
    var busy by remember { androidx.compose.runtime.mutableIntStateOf(0) }
    val open = { x: MyAssignment ->
        if (x.kind == "quiz") x.quiz_id?.let(openQuiz) ?: Unit
        else scope.launch {
            busy = x.id
            try { val s = a.send("POST", "/assignments/${x.id}/start", buildJsonObject { put("request_id", "a${x.id}-" + java.util.UUID.randomUUID()) }, McqSet.serializer()); onMain { openSet(s.id) } }
            catch (e: Exception) { toast(e.message.orEmpty()); list.reload() }
            busy = 0
        }.let { }
    }
    Page(tl("Assigned to me"), back = back) {
        Loaded(list) { d ->
            if (d.items.isEmpty()) Quiet(tl("Nothing assigned to you right now."))
            d.items.forEach { x ->
                val can = x.left != 0 || runCatching { java.time.Instant.parse(x.due_at) < java.time.Instant.now() }.getOrDefault(false)  // with no attempts left, only late tries, after the due time
                ListRow(x.title, listOf(x.course + (if (x.by.isNotEmpty()) " · " + tl("from {name}", "name" to x.by) else ""),
                                        tl("due {when}", "when" to stamp(x.due_at)) + " · " + (x.left?.let { tl("Attempts left: {n}", "n" to it) } ?: tl("Unlimited attempts"))).joinToString("\n"),
                        extra = {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                                StateText(x.status, x.best, x.late_best)
                                if (can) OutlinedButton(enabled = busy == 0, onClick = { open(x) }) { Text(if (x.status == "to_do") tl("Start") else tl("Try again")) }
                            }
                        })
            }
        }
    }
}

/** a school teacher's assigned tests, newest due first, with how many students are done, late, missed or still to do. Tapping one shows each student;
 *  giving a new test is on the website, where there is room to choose topics and students */
@Composable
fun TeacherAssignmentsScreen(back: () -> Unit) {
    var view by remember { mutableStateOf<Int?>(null) }
    view?.let { id -> AssignmentStudentsScreen(id) { view = null }; return }
    val list = rememberLoad("assignments") { get("/assignments", TAssignments.serializer()) }
    Page(tl("Assigned tests"), back = back) {
        Loaded(list) { d ->
            if (d.items.isEmpty()) Quiet(tl("Nothing assigned yet. Give a quiz, a test or an MCQ set to one student or a group, with a due date and time."))
            d.items.forEach { x ->
                val counts = listOfNotNull(tl("{done} of {n} done", "done" to x.done, "n" to x.students),
                                           if (x.late > 0) tl("{n} late", "n" to x.late) else null, if (x.missed > 0) tl("{n} missed", "n" to x.missed) else null).joinToString(" · ")
                ListRow(x.title, tl("due {when}", "when" to stamp(x.due_at)) + " · " + attemptsText(x.attempts) + "\n" + counts, onClick = { view = x.id })
            }
        }
    }
}

/** one assignment: each student, with their state, their attempts and the score that counts */
@Composable
fun AssignmentStudentsScreen(id: Int, back: () -> Unit) {
    val d = rememberLoad("assignment", id) { get("/assignments/$id", TAssignDetail.serializer()) }
    val v = (d.state as? Load.Ok)?.value
    Page(v?.title ?: tl("Assigned tests"), v?.let { tl("due {when}", "when" to stamp(it.due_at)) + " · " + attemptsText(it.attempts) }.orEmpty(), back) {
        Loaded(d) { x ->
            Quiet(pl(x.rows.size, "student"))
            x.rows.forEach { r ->
                ListRow(r.name, if (x.attempts > 0) tl("{used} of {n} attempts used", "used" to r.used, "n" to x.attempts) else tl("{used} attempts", "used" to r.used),
                        trailing = { StateText(r.status, r.best, r.late_best) })
            }
        }
    }
}
