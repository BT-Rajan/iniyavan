package app.zigora.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import app.zigora.R
import app.zigora.data.Area
import app.zigora.data.Checked
import app.zigora.data.StudyAttemptOut
import app.zigora.data.StudyQuiz
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

private val LETTERS = "ABCDEF"

/** A practice set the AI wrote: "5 quick questions" (each answer right away), a full quiz (scored at the end) or a review. Same as the web. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StudyQuizScreen(id: Int, back: () -> Unit, again: ((String) -> Unit)? = null, next: Pair<String, () -> Unit>? = null) {
    val a = api(); val scope = rememberCoroutineScope()
    val q = rememberLoad("squiz", id) { get("/study/quizzes/$id", StudyQuiz.serializer()) }
    val quiz = (q.state as? Load.Ok)?.value
    val ans = remember(quiz) { mutableStateListOf<Int?>().apply { repeat(quiz?.questions?.size ?: 0) { add(null) } } }
    val fb = remember(quiz) { mutableStateMapOf<Int, Checked>() }
    val flagged = remember(quiz) { mutableStateMapOf<Int, Boolean>() }
    var res by remember(quiz) { mutableStateOf<StudyAttemptOut?>(null) }
    var busy by remember { mutableStateOf(false) }
    var msg by remember { mutableStateOf("") }
    val mcq = quiz?.kind != "quiz"; val review = quiz?.kind == "review"
    Scaffold(topBar = { TopAppBar(title = { Column {
            Text(stringResource(if (review) R.string.review else if (mcq) R.string.step_check else R.string.full_quiz))
            quiz?.let { Text(it.topic + " · " + pluralStringResource(R.plurals.questions, it.questions.size, it.questions.size), style = MaterialTheme.typography.labelMedium) } } },
        navigationIcon = { IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } }) }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Loaded(q) { qz ->
                res?.let { r ->
                    Panel {
                        Text("${r.score} / ${r.total} · ${r.percent}%", style = MaterialTheme.typography.headlineSmall)
                        Quiet(stringResource(if (review) R.string.review_done else if (mcq) R.string.done_answers_below else R.string.done_new_set) +
                              (if (r.summary.isNotEmpty()) " " + r.summary else "") + (r.next_review?.let { " $it." } ?: ""))
                        next?.let { (title, go) -> Button(onClick = go) { Text(stringResource(R.string.next_topic, title)) } }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            again?.let { OutlinedButton(onClick = { it(qz.kind) }) { Text(stringResource(if (mcq) R.string.new_questions else R.string.new_quiz)) } }
                            OutlinedButton(onClick = back) { Text(stringResource(if (review) R.string.done else R.string.back_to_topic)) }
                        }
                    }
                    if (!mcq && r.areas.isNotEmpty()) { SectionTitle(stringResource(R.string.know_well_revisit)); AreaList(r.areas, staff = true) }
                }
                qz.questions.forEachIndexed { i, x ->
                    val f: Checked? = if (mcq) fb[i] else res?.results?.getOrNull(i)?.let { Checked(it.ok, it.correct, it.explanation) }
                    Panel {
                        Text(stringResource(R.string.question_n, i + 1) + (f?.let { if (it.ok) " · " + stringResource(R.string.right) else " · " + stringResource(R.string.wrong) } ?: ""), style = MaterialTheme.typography.titleSmall)
                        if (x.topic.isNotEmpty()) Quiet(x.topic)
                        Md(x.text)
                        x.options.forEachIndexed { k, o ->
                            val color = when { f != null && k == f.correct -> MaterialTheme.colorScheme.primary; f != null && k == ans[i] -> MaterialTheme.colorScheme.error
                                               ans[i] == k -> MaterialTheme.colorScheme.primary; else -> MaterialTheme.colorScheme.outlineVariant }
                            OutlinedCard(onClick = {
                                if (res != null || (mcq && fb[i] != null)) return@OutlinedCard
                                ans[i] = k
                                if (mcq) scope.launch { try { fb[i] = a.send("POST", "/study/quizzes/${qz.id}/check", buildJsonObject { put("index", i); put("answer", k) }, Checked.serializer()) } catch (e: Exception) { msg = e.message.orEmpty() } }
                            }, enabled = f == null && res == null, border = BorderStroke(if (ans[i] == k || (f != null && k == f.correct)) 2.dp else 1.dp, color), modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
                                Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Text(LETTERS[k].toString() + "  ", style = MaterialTheme.typography.titleSmall)
                                    Column(Modifier.weight(1f)) { Md(o) }
                                    if (f != null && k == f.correct) { Icon(Icons.Filled.Check, null, tint = MaterialTheme.colorScheme.primary); Text(stringResource(R.string.correct)) }
                                }
                            }
                        }
                        if (f != null && f.explanation.isNotEmpty()) Column(Modifier.padding(top = 8.dp)) { Md(f.explanation) }
                        if (f != null) { if (flagged[i] == true) Quiet(stringResource(R.string.reported)) else TextButton(onClick = { scope.launch {
                            try { a.raw("POST", "/study/quizzes/${qz.id}/flag", buildJsonObject { put("index", i) }); flagged[i] = true; msg = app.zigora.data.I18n.str(R.string.question_wont_come_back) } catch (e: Exception) { msg = e.message.orEmpty() }
                        } }) { Text(stringResource(R.string.question_is_wrong)) } }
                    }
                }
                if (msg.isNotEmpty()) Quiet(msg)
                if (res == null) {
                    Button(enabled = !busy && (!mcq || fb.size == qz.questions.size), onClick = { scope.launch {
                        busy = true
                        try { res = a.send("POST", "/study/quizzes/${qz.id}/attempt", buildJsonObject { put("answers", JsonArray(ans.map { v -> v?.let(::JsonPrimitive) ?: JsonNull })) }, StudyAttemptOut.serializer()) }
                        catch (e: Exception) { msg = e.message.orEmpty() }
                        busy = false
                    } }) { Text(stringResource(if (busy) R.string.checking else if (mcq) R.string.see_my_score else R.string.submit_answers)) }
                    val left = ans.count { it == null }
                    if (mcq) Quiet(stringResource(R.string.pick_to_see) + if (fb.size < qz.questions.size) " " + stringResource(R.string.n_to_go, qz.questions.size - fb.size) else "")
                    else if (left > 0) Quiet(stringResource(R.string.n_unanswered, left))
                }
            }
        }
    }
}


/** strong, getting there and needs another round, as on the web */
@Composable
fun AreaList(areas: List<Area>, staff: Boolean = false, onStudy: ((Int) -> Unit)? = null) {
    listOf(Triple("needs_study", R.string.needs_another_round, R.string.needs_another_round_hint), Triple("getting_there", R.string.getting_there, 0),
           Triple("strong", R.string.strong_areas, R.string.strong_areas_hint)).forEach { (k, title, hint) ->
        val l = areas.filter { it.status == k }; if (l.isEmpty()) return@forEach
        Panel(Modifier.padding(bottom = 8.dp)) {
            Text(stringResource(title) + " (${l.size})", style = MaterialTheme.typography.titleSmall,
                 color = when (k) { "strong" -> Color(0xFF2E7D5B); "needs_study" -> MaterialTheme.colorScheme.error; else -> MaterialTheme.colorScheme.tertiary })
            if (hint != 0 && !staff) Quiet(stringResource(hint))
            Paged(l, key = k) { x ->
                Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(x.title)
                        Quiet(stringResource(R.string.of_total_right, x.correct, x.total, x.percent) + (if (x.course.isNotEmpty()) " · ${x.course}" else ""))
                        LinearProgressIndicator(progress = { x.percent / 100f }, Modifier.fillMaxWidth().padding(top = 4.dp))
                    }
                    if (x.topic_id != null && onStudy != null) TextButton(onClick = { onStudy(x.topic_id) }) { Text(stringResource(if (k == "strong") R.string.review else R.string.study_again)) }
                }
            }
        }
    }
}
