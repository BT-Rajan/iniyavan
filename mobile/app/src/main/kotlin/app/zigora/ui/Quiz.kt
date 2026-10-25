package app.zigora.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.zigora.R
import app.zigora.data.AttemptOut
import app.zigora.data.Quiz
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject

/** a teacher's quiz or test, as on the web: every question on one page, then the score, what to revisit, and each answer right or wrong */
@Composable
fun QuizScreen(id: Int, back: () -> Unit, openTopic: (Int) -> Unit, openAttempt: (Int) -> Unit, openAttempts: (Int) -> Unit) {
    val a = api(); val scope = rememberCoroutineScope()
    var tick by remember { mutableIntStateOf(0) }
    val quiz = rememberLoad("quiz", id, tick) { get("/quizzes/$id", Quiz.serializer()) }
    val q = (quiz.state as? Load.Ok)?.value
    val picks = remember(q) { mutableStateListOf<Int?>().apply { repeat(q?.questions?.size ?: 0) { add(null) } } }
    var out by remember(q) { mutableStateOf<AttemptOut?>(null) }
    var busy by remember { mutableStateOf(false) }
    var msg by remember { mutableStateOf("") }
    val scroll = rememberScrollState()
    Page(q?.title ?: tl("Quiz"), q?.let { tl("{length} questions · pass mark {pass_percent}%{v}", "length" to it.questions.size, "pass_percent" to it.pass_percent,
                                             "v" to if (it.kind == "course") " · course test" else "") }.orEmpty(), back, scroll = scroll) {
        Loaded(quiz) { qz ->
            val res = out
            if (res == null && qz.attempts > 0) Row(verticalAlignment = Alignment.CenterVertically) {
                Quiet(tl("You have tried this {n}. Best {best}% · latest {latest}%.", "n" to pl(qz.attempts, "time"), "best" to qz.best, "latest" to qz.latest), Modifier.weight(1f))
                TextButton(onClick = { openAttempts(id) }) { Text(tl("See your attempts")) }
            }
            if (res != null) {
                Panel {
                    Text("${res.score} / ${res.total} · ${res.percent}%", style = MaterialTheme.typography.headlineSmall)
                    Quiet(tl("Pass mark {pass}%.", "pass" to res.pass_percent) + if (res.summary.isNotEmpty()) " " + res.summary else "")
                    Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        res.attempt_id?.let { aid -> Button(onClick = { openAttempt(aid) }) { Text(tl("Review answers")) } }
                        OutlinedButton(onClick = { tick++ }) { Text(tl("Try again")) }
                    }
                    TextButton(onClick = back) { Text(tl("Back")) }
                }
                if (res.areas.isNotEmpty()) { SectionTitle(tl("What you are good at and what to revisit")); AreaList(res.areas, onStudy = openTopic) }
            }
            qz.questions.forEachIndexed { i, x ->
                Panel {
                    Text(tl("Question") + " " + (i + 1), fontWeight = FontWeight.SemiBold)
                    Md(x.text); QImage(x.image)
                    x.options.forEachIndexed { k, o ->
                        val r = res?.results?.getOrNull(i)
                        val st = if (r != null) when { k == r.correct || (r.ok && k == r.chosen) -> OptState.Ok; k == r.chosen -> OptState.Bad; else -> OptState.Plain }
                                 else if (picks.getOrNull(i) == k) OptState.Picked else OptState.Plain
                        Option(k, o, x.option_images.getOrElse(k) { "" }, st, onClick = if (res == null) ({ picks[i] = k }) else null)
                    }
                    res?.results?.getOrNull(i)?.explanation?.takeIf { it.isNotBlank() }?.let { Md(it) }
                }
            }
            if (res == null && qz.questions.isNotEmpty()) {
                if (msg.isNotEmpty()) Text(msg, color = MaterialTheme.colorScheme.error)
                Button(enabled = !busy, modifier = Modifier.fillMaxWidth(), onClick = { scope.launch {
                    busy = true; msg = ""
                    try {
                        val body = buildJsonObject { put("answers", JsonArray(picks.map { it?.let(::JsonPrimitive) ?: JsonNull })) }
                        out = a.send("POST", "/quizzes/$id/attempt", body, AttemptOut.serializer()); scroll.scrollTo(0)
                    } catch (e: Exception) { msg = e.message.orEmpty() }
                    busy = false
                } }) { Text(if (busy) tl("Checking…") else tl("Submit answers")) }
                val left = picks.count { it == null }
                if (left > 0) Quiet("$left " + tl("unanswered. Blank answers count as wrong."))
            }
            if (qz.questions.isEmpty()) Quiet(stringResource(R.string.no_questions))
        }
    }
}
