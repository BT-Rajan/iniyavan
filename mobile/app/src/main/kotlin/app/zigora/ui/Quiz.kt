package app.zigora.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
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
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import app.zigora.R
import app.zigora.data.AttemptOut
import app.zigora.data.Quiz
import coil3.compose.AsyncImage
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.JsonArray

/** a teacher's quiz or test: one question at a time, then the score and (when the quiz shows them) the answers */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuizScreen(id: Int, back: () -> Unit) {
    val a = api(); val scope = rememberCoroutineScope()
    val quiz = rememberLoad("quiz", id) { get("/quizzes/$id", Quiz.serializer()) }
    val q = (quiz.state as? Load.Ok)?.value
    val picks = remember(q) { mutableStateListOf<Int?>().apply { repeat(q?.questions?.size ?: 0) { add(null) } } }
    var at by remember(q) { mutableIntStateOf(0) }
    var out by remember(q) { mutableStateOf<AttemptOut?>(null) }
    var busy by remember { mutableStateOf(false) }
    var msg by remember { mutableStateOf("") }
    Scaffold(topBar = { TopAppBar(title = { Text(q?.title.orEmpty()) },
        navigationIcon = { IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } }) }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Loaded(quiz) { qz ->
                val res = out
                if (res != null) {
                    Panel {
                        Text(stringResource(R.string.score_of, res.score, res.total, res.percent), style = MaterialTheme.typography.headlineSmall)
                        Quiet(stringResource(if (res.passed) R.string.passed else R.string.pass_mark, res.pass_percent))
                    }
                    qz.questions.forEachIndexed { i, x ->
                        val r = res.results.getOrNull(i) ?: return@forEachIndexed
                        Panel {
                            Row(verticalAlignment = Alignment.Top) {
                                Icon(if (r.ok) Icons.Filled.Check else Icons.Filled.Close, null, tint = if (r.ok) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error)
                                Column(Modifier.padding(start = 8.dp)) {
                                    Md(x.text)
                                    r.chosen?.let { Quiet(stringResource(R.string.you_chose, x.options.getOrElse(it) { "" })) } ?: Quiet(stringResource(R.string.left_blank))
                                    if (res.reveal && r.correct != null && !r.ok) Text(stringResource(R.string.correct_is, x.options.getOrElse(r.correct) { "" }))
                                    r.explanation?.takeIf { it.isNotBlank() }?.let { Md(it) }
                                }
                            }
                        }
                    }
                    OutlinedButton(onClick = { out = null; at = 0; for (i in picks.indices) picks[i] = null }) { Text(stringResource(R.string.try_again)) }
                    return@Loaded
                }
                if (qz.questions.isEmpty()) { Quiet(stringResource(R.string.no_questions)); return@Loaded }
                val x = qz.questions[at]
                LinearProgressIndicator(progress = { (at + 1f) / qz.questions.size }, Modifier.fillMaxWidth())
                Quiet(stringResource(R.string.question_n_of, at + 1, qz.questions.size))
                Md(x.text)
                if (x.image.isNotEmpty()) AsyncImage(a.base + x.image, null, Modifier.fillMaxWidth().heightIn(max = 240.dp))
                x.options.forEachIndexed { i, o ->
                    Row(Modifier.fillMaxWidth().selectable(picks[at] == i, role = Role.RadioButton) { picks[at] = i }.padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(picks[at] == i, onClick = null)
                        Column(Modifier.padding(start = 8.dp)) {
                            Md(o)
                            x.option_images.getOrNull(i)?.takeIf { it.isNotEmpty() }?.let { AsyncImage(a.base + it, null, Modifier.heightIn(max = 140.dp)) }
                        }
                    }
                }
                if (msg.isNotEmpty()) Text(msg, color = MaterialTheme.colorScheme.error)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { at-- }, enabled = at > 0) { Text(stringResource(R.string.previous)) }
                    if (at < qz.questions.size - 1) Button(onClick = { at++ }) { Text(stringResource(R.string.next)) }
                    else Button(enabled = !busy, onClick = {
                        scope.launch {
                            busy = true; msg = ""
                            try {
                                val body = buildJsonObject { put("answers", JsonArray(picks.map { it?.let(::JsonPrimitive) ?: JsonNull })) }
                                out = a.send("POST", "/quizzes/$id/attempt", body, AttemptOut.serializer())
                            } catch (e: Exception) { msg = e.message.orEmpty() }
                            busy = false
                        }
                    }) { Text(stringResource(R.string.finish)) }
                }
            }
        }
    }
}
