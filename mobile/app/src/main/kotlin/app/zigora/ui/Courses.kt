package app.zigora.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.outlined.Circle
import androidx.compose.material.icons.outlined.Timelapse
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.AutoStories
import androidx.compose.material.icons.outlined.Quiz
import androidx.compose.material.icons.outlined.UploadFile
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import kotlinx.coroutines.launch
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import app.zigora.R
import app.zigora.data.Me
import app.zigora.data.ProgramNode
import app.zigora.data.QuizRef
import app.zigora.data.TopicRef
import kotlinx.serialization.builtins.ListSerializer

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CoursesScreen(me: Me, openSearch: () -> Unit, openStudy: () -> Unit, open: (Int) -> Unit) {
    val tree = rememberLoad("tree") { get("/tree", ListSerializer(ProgramNode.serializer())) }
    Scaffold(topBar = { TopAppBar(title = { Text(tl("My courses")) }, actions = {
        IconButton(onClick = openSearch) { Icon(Icons.Outlined.Search, stringResource(R.string.tab_search)) } }) }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(16.dp)) {
            Loaded(tree) { list ->
                val courses = coursesOf(list)
                if (courses.isEmpty()) Quiet(stringResource(if (me.self_registered && !me.placed) R.string.not_placed else R.string.not_enrolled))
                else CourseList(courses, open)
            }
            Gap(16)
            ListRow(tl("Build a course"), tl("Upload a PDF or Word file and study it with quick checks, quizzes and reviews"), onClick = openStudy,
                    leading = { RowIcon(Icons.Outlined.AutoStories) })
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CourseScreen(id: Int, back: () -> Unit, openTopic: (Int) -> Unit, openQuiz: (Int) -> Unit, openMaterial: (Int, String) -> Unit, openRevision: (Int) -> Unit) {
    val tree = rememberLoad("tree", id) { get("/tree", ListSerializer(ProgramNode.serializer())) }
    val c = (tree.state as? Load.Ok)?.value?.let { coursesOf(it).firstOrNull { x -> x.id == id } }
    val scroll = TopAppBarDefaults.pinnedScrollBehavior()
    val a = api(); val scope = androidx.compose.runtime.rememberCoroutineScope()
    var redoAsk by remember { mutableStateOf(false) }  // asking before the whole course starts over
    Scaffold(Modifier.nestedScroll(scroll.nestedScrollConnection), topBar = {
        TopAppBar(title = { Text(c?.name ?: "") }, scrollBehavior = scroll,
                  navigationIcon = { IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } })
    }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(bottom = 24.dp)) {
            Loaded(tree) {
                if (c == null) { Problem(stringResource(R.string.course_unavailable)); return@Loaded }
                val ts = c.units.flatMap { it.topics }; val k = ts.count { it.has_notes }
                ListRow(if (k > 0) tl("Your notes in {k} of {length} topics", "k" to k, "length" to ts.size) else tl("Bring your own notes"),
                        if (k > 0) tl("Add or update your material") else tl("Upload your PDF or Word notes. They are filed under this course's topics, for you only."),
                        onClick = { openMaterial(c.id, c.name) }, leading = { RowIcon(Icons.Outlined.UploadFile) })
                if (ts.any { it.status != "not_started" }) TextButton(onClick = { redoAsk = true }) { Text(tl("Start this course over")) }
                if (redoAsk) androidx.compose.material3.AlertDialog(onDismissRequest = { redoAsk = false }, title = { Text(tl("Start {name} over?", "name" to c.name)) },
                    text = { Text(tl("Every topic goes back to not started, so you can study the course again. Your quiz scores and your streak stay.")) },
                    confirmButton = { TextButton(onClick = { redoAsk = false; scope.launch { runCatching { a.raw("POST", "/courses/${c.id}/redo") }; tree.reload() } }) { Text(tl("Start over")) } },
                    dismissButton = { TextButton(onClick = { redoAsk = false }) { Text(stringResource(R.string.cancel)) } })
                if (c.tests.any { it.published && it.questions > 0 }) SectionTitle(tl("MCQ tests"))
                Tests(c.tests, openQuiz)
                c.units.forEach { un ->
                    SectionTitle(un.name)
                    if (un.topics.isEmpty()) Quiet(stringResource(R.string.no_topics_yet))
                    else TextButton(onClick = { openRevision(un.id) }) { Icon(Icons.Outlined.Description, null); Text("  " + tl("Revision sheet")) }
                    Paged(un.topics, key = un.id) { t -> TopicRow(t) { openTopic(t.id) } }
                    Tests(un.quizzes, openQuiz)
                }
            }
        }
    }
}

@Composable
private fun Tests(list: List<QuizRef>, open: (Int) -> Unit) {
    val ready = list.filter { it.published && it.questions > 0 }
    if (ready.isEmpty()) return
    Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        ready.forEach { q ->
            ListRow(q.title, "${q.questions} " + tl("questions · pass {pass_percent}%", "pass_percent" to q.pass_percent) +
                    (q.best?.let { tl(" · best {best}%", "best" to it) } ?: "") + (if (q.best != null && q.best >= q.pass_percent) "  ✓" else ""), onClick = { open(q.id) }, leading = { RowIcon(Icons.Outlined.Quiz) })
        }
    }
}

@Composable
fun TopicRow(t: TopicRef, open: () -> Unit) = ListRow(t.title,
    when {
        t.overdue -> stringResource(R.string.teachers_date_passed)
        t.learning_due_at != null && t.status != "completed" -> stringResource(R.string.learn_by, day(t.learning_due_at))
        else -> ""
    }, onClick = open,
    leading = {
        when (t.status) {
            "completed" -> Icon(Icons.Filled.CheckCircle, stringResource(R.string.learned), tint = MaterialTheme.colorScheme.primary)
            "in_progress" -> Icon(Icons.Outlined.Timelapse, stringResource(R.string.started), tint = MaterialTheme.colorScheme.primary)
            else -> Icon(Icons.Outlined.Circle, stringResource(R.string.not_started), tint = MaterialTheme.colorScheme.outline)
        }
    },
    trailing = if (t.bookmarked) ({ Icon(Icons.Filled.Bookmark, stringResource(R.string.bookmarked), tint = MaterialTheme.colorScheme.primary) }) else null)

/** a date from the server, in the phone's own language and calendar style */
fun day(iso: String): String = runCatching {
    java.time.format.DateTimeFormatter.ofLocalizedDate(java.time.format.FormatStyle.MEDIUM)
        .format(java.time.OffsetDateTime.parse(iso).atZoneSameInstant(java.time.ZoneId.systemDefault()))
}.getOrDefault(iso.take(10))
