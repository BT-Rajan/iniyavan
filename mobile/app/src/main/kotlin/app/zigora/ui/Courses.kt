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
import androidx.compose.material.icons.outlined.Quiz
import androidx.compose.material.icons.outlined.Timelapse
import androidx.compose.material3.AssistChip
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
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
fun CoursesScreen(me: Me, open: (Int) -> Unit) {
    val tree = rememberLoad("tree") { get("/tree", ListSerializer(ProgramNode.serializer())) }
    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.tab_courses)) }) }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(16.dp)) {
            Loaded(tree) { list ->
                val courses = coursesOf(list)
                if (courses.isEmpty()) Quiet(stringResource(if (me.self_registered && !me.placed) R.string.not_placed else R.string.not_enrolled))
                else CourseList(courses, open)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CourseScreen(id: Int, back: () -> Unit, openTopic: (Int) -> Unit, openQuiz: (Int) -> Unit) {
    val tree = rememberLoad("tree", id) { get("/tree", ListSerializer(ProgramNode.serializer())) }
    val c = (tree.state as? Load.Ok)?.value?.let { coursesOf(it).firstOrNull { x -> x.id == id } }
    val scroll = TopAppBarDefaults.pinnedScrollBehavior()
    Scaffold(Modifier.nestedScroll(scroll.nestedScrollConnection), topBar = {
        TopAppBar(title = { Text(c?.name ?: "") }, scrollBehavior = scroll,
                  navigationIcon = { IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back)) } })
    }) { pad ->
        Column(Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(bottom = 24.dp)) {
            Loaded(tree) {
                if (c == null) { Problem(stringResource(R.string.course_unavailable)); return@Loaded }
                Tests(c.tests, openQuiz)
                c.units.forEach { un ->
                    SectionTitle(un.name)
                    if (un.topics.isEmpty()) Quiet(stringResource(R.string.no_topics_yet))
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
            AssistChip(onClick = { open(q.id) }, leadingIcon = { Icon(Icons.Outlined.Quiz, null) },
                label = { Text(q.title + (q.best?.let { " · " + stringResource(R.string.best_percent, it) } ?: "")) })
        }
    }
}

@Composable
fun TopicRow(t: TopicRef, open: () -> Unit) = ListItem(
    modifier = Modifier.fillMaxWidth().clickableRounded(open),
    colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    leadingContent = {
        when (t.status) {
            "completed" -> Icon(Icons.Filled.CheckCircle, stringResource(R.string.learned), tint = MaterialTheme.colorScheme.primary)
            "in_progress" -> Icon(Icons.Outlined.Timelapse, stringResource(R.string.started), tint = MaterialTheme.colorScheme.primary)
            else -> Icon(Icons.Outlined.Circle, stringResource(R.string.not_started), tint = MaterialTheme.colorScheme.outlineVariant)
        }
    },
    headlineContent = { Text(t.title) },
    supportingContent = when {
        t.overdue -> ({ Text(stringResource(R.string.teachers_date_passed)) })
        t.learning_due_at != null && t.status != "completed" -> ({ Text(stringResource(R.string.learn_by, day(t.learning_due_at))) })
        else -> null
    },
    trailingContent = if (t.bookmarked) ({ Icon(Icons.Filled.Bookmark, stringResource(R.string.bookmarked), tint = MaterialTheme.colorScheme.secondary) }) else null)

/** a date from the server, in the phone's own language and calendar style */
fun day(iso: String): String = runCatching {
    java.time.format.DateTimeFormatter.ofLocalizedDate(java.time.format.FormatStyle.MEDIUM)
        .format(java.time.OffsetDateTime.parse(iso).atZoneSameInstant(java.time.ZoneId.systemDefault()))
}.getOrDefault(iso.take(10))
