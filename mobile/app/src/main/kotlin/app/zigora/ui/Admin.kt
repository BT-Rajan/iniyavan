package app.zigora.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import app.zigora.data.PlanUser
import app.zigora.data.PlanUsers
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** More AI, as on the web's user page: an admin makes a student Pro (no daily limit, four MCQ sets a day) for a while, or ends it.
 *  Students who asked for more come first; Lite and Pro students can be found too. The server checks who may be made Pro. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun MoreAiPanel() {
    val a = api(); val scope = rememberCoroutineScope(); val toast = rememberToast()
    var plan by remember { mutableStateOf("asked") }
    var q by remember { mutableStateOf("") }
    var tick by remember { mutableIntStateOf(0) }
    var pick by remember { mutableStateOf<PlanUser?>(null) }
    var busy by remember { mutableStateOf(false) }
    val list = rememberLoad("plan-users", plan, q, tick) {
        get("/admin/users?plan=$plan&limit=50&q=" + java.net.URLEncoder.encode(q.trim(), "UTF-8"), PlanUsers.serializer())
    }
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionTitle(tl("More AI"))
        Quiet(tl("Make a student Pro for a while: no daily AI limit, and four MCQ sets a day."))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("asked" to tl("Asked for more AI"), "lite" to tl("Lite"), "pro" to tl("Pro")).forEach { (k, l) -> FilterChip(plan == k, { plan = k }, { Text(l) }) }
        }
        OutlinedTextField(q, { q = it }, Modifier.fillMaxWidth(), label = { Text(tl("Search by name or email")) }, singleLine = true)
        Loaded(list) { r ->
            if (r.items.isEmpty()) Quiet(if (plan == "asked") tl("Nobody is asking for more AI right now.") else tl("No one here."))
            r.items.forEach { u ->
                ListRow(u.name, listOfNotNull(u.email ?: u.username, planLine(u)).joinToString(" · "), onClick = { pick = u })
            }
        }
    }
    val u = pick ?: return
    val set = { body: kotlinx.serialization.json.JsonObject, done: String -> scope.launch {
        busy = true
        try { a.raw("PUT", "/admin/users/${u.id}/pro", body); toast(done); pick = null; tick++ } catch (e: Exception) { toast(e.message.orEmpty()) }
        busy = false
    } }
    AlertDialog(onDismissRequest = { pick = null }, title = { Text(u.name) },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Quiet(planLine(u))
            if (u.asked) Text(tl("Asked for more AI"), style = MaterialTheme.typography.labelLarge)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(7, 30, 90, 365).forEach { d -> OutlinedButton(enabled = !busy, onClick = { set(buildJsonObject { put("days", d) }, tl("{name} is Pro now", "name" to u.name)) }) {
                    Text(if (d == 365) tl("1 year") else tl("{n} days", "n" to d)) } }
            }
            if (u.plan == "pro") TextButton(enabled = !busy, onClick = { set(buildJsonObject { put("end", true) }, tl("Back on Lite")) }) { Text(tl("End Pro now"), color = MaterialTheme.colorScheme.error) }
        } },
        confirmButton = {}, dismissButton = { TextButton(onClick = { pick = null }) { Text(tl("Cancel")) } })
}

private fun planLine(u: PlanUser) = when (u.plan) {
    "pro" -> tl("Pro until {date}", "date" to stamp(u.pro_until.orEmpty()))
    "own" -> tl("Own key: uses their own AI key")
    "lite" -> tl("Lite: the free daily allowance")
    else -> u.plan
}
