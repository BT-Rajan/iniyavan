package app.zigora.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.AutoStories
import androidx.compose.material.icons.outlined.Checklist
import androidx.compose.material.icons.outlined.SystemUpdate
import androidx.core.net.toUri
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LargeTopAppBar
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import app.zigora.BuildConfig
import app.zigora.R
import app.zigora.data.AndroidRelease
import app.zigora.data.CourseNode
import app.zigora.data.Me
import app.zigora.data.Notes
import app.zigora.data.ProgramNode
import app.zigora.data.Recall
import app.zigora.data.Today
import kotlinx.serialization.builtins.ListSerializer
import java.time.LocalDate
import java.time.LocalTime

val CourseColors = listOf(Color(0xFF722F99), Color(0xFFC2185B), Color(0xFF00796B), Color(0xFF5D4037), Color(0xFF3949AB))

/** each course once, wherever it is shown; a live place wins over an archived one */
fun coursesOf(tree: List<ProgramNode>): List<CourseNode> {
    val out = LinkedHashMap<Int, CourseNode>()
    for (p in tree) for (s in p.semesters) for (c in s.courses) { val at = out[c.id]; if (at == null || (at.archived && !c.archived)) out[c.id] = c }
    return out.values.toList()
}

fun firstName(n: String): String {  // as on the web: a title stays with the surname ("Dr. A. Kumar" -> "Dr. Kumar"), skipping initials
    val w = n.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
    if (w.isEmpty()) return ""
    if (!Regex("^(dr|prof|mr|mrs|ms|miss)\\.?$", RegexOption.IGNORE_CASE).matches(w[0])) return w[0]
    return w.drop(1).firstOrNull { it.replace(".", "").length > 1 }?.let { w[0] + " " + it } ?: w[0]
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(me: Me, openTopic: (Int) -> Unit, openCourse: (Int) -> Unit, openQuiz: (Int) -> Unit, openNotes: () -> Unit, openPhoto: () -> Unit,
               openSearch: () -> Unit, openRoutine: () -> Unit, openSession: (app.zigora.data.SessionItem) -> Unit, openStudy: () -> Unit,
               openOwn: (Int, Int) -> Unit, review: (Int) -> Unit, openMcq: () -> Unit = {}) {
    val tree = rememberLoad("tree") { get("/tree", ListSerializer(ProgramNode.serializer())) }
    val zapp = app(); androidx.compose.runtime.LaunchedEffect(tree.state) { if (tree.state !is Load.Loading) zapp.firstScreenReady.value = true }
    val today = rememberLoad("today") { get("/me/today", Today.serializer()) }
    val notes = rememberLoad("notes") { get("/me/notifications", Notes.serializer()) }
    val sme = (rememberLoad("study-me") { get("/study/me", app.zigora.data.StudyMe.serializer()) }.state as? Load.Ok)?.value
    val session = rememberLoad("session") { get("/me/session", app.zigora.data.SessionOut.serializer()) }
    var sess by remember { mutableStateOf<app.zigora.data.SessionOut?>(null) }
    androidx.compose.runtime.LaunchedEffect(session.state) { (session.state as? Load.Ok)?.value?.let { sess = it } }
    val aiOff = rememberAiOff()
    val scroll = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()
    val h = LocalTime.now().hour
    val hi = stringResource(if (h < 12) R.string.good_morning else if (h < 17) R.string.good_afternoon else R.string.good_evening, firstName(me.name))
    Scaffold(Modifier.nestedScroll(scroll.nestedScrollConnection), topBar = {
        LargeTopAppBar(title = { Text(hi) }, scrollBehavior = scroll, actions = {
            IconButton(onClick = openSearch) { Icon(Icons.Outlined.Search, stringResource(R.string.tab_search)) }
            if (!aiOff) IconButton(onClick = openPhoto) { Icon(Icons.Outlined.CameraAlt, stringResource(R.string.ask_photo)) }  // asking from a photo is AI
            val unread = (notes.state as? Load.Ok)?.value?.items?.count { it.unread } ?: 0
            IconButton(onClick = openNotes) {
                BadgedBox(badge = { if (unread > 0) Badge { Text("$unread") } }) { Icon(Icons.Outlined.Notifications, stringResource(R.string.notifications)) }
            }
        })
    }) { pad ->
        PullToRefreshBox(isRefreshing = tree.state is Load.Loading, onRefresh = { tree.reload(); today.reload(); notes.reload(); session.reload() }, modifier = Modifier.padding(pad)) {
            Column(Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                UpdateCard()
                InvitationsCard()
                sess?.let { SessionCard(it, openRoutine, openSession) { n -> sess = n } }
                (today.state as? Load.Ok)?.value?.takeIf { sess?.routine == null }?.let { t ->  // with a routine, its session says what is next
                    val f = t.focus.filter { it.kind == "resume" }.maxByOrNull { it.last_read.orEmpty() } ?: t.focus.firstOrNull { it.kind == "next" }
                    if (f?.topic_id != null) ListRow(f.title, stringResource(if (f.kind == "resume") R.string.where_left_off else R.string.up_next) + " · " + f.course,
                                                     onClick = { openTopic(f.topic_id) }, leading = { RowIcon(Icons.Filled.PlayArrow) })
                }
                RecallCard(openTopic)
                ListRow(tl("MCQ practice"), tl("Questions from your courses, with answers explained"), onClick = openMcq, leading = { RowIcon(Icons.Outlined.Checklist) })
                if (sme != null && sme.courses > 0) { SectionTitle(tl("Your own courses")); LearnCard(sme, openOwn, review) }
                Loaded(tree) { list ->
                    val courses = coursesOf(list)
                    if (sme != null && sme.courses == 0 && courses.isEmpty())
                        ListRow(tl("Build a course from your own notes"), tl("Upload a PDF or Word file and study it with quick checks, quizzes and reviews"), onClick = openStudy,
                                leading = { RowIcon(Icons.Outlined.AutoStories) })
                    if (courses.isEmpty()) Quiet(stringResource(if (me.self_registered && !me.placed) R.string.not_placed else R.string.not_enrolled), Modifier.padding(top = 16.dp))
                    else {
                        SectionTitle(stringResource(R.string.my_courses))
                        CourseList(courses, openCourse)
                    }
                }
            }
        }
    }
}

@Composable
fun CourseList(courses: List<CourseNode>, open: (Int) -> Unit) {
    val ctx = LocalContext.current
    Paged(courses) { c ->
        val topics = c.units.flatMap { it.topics }
        val done = topics.count { it.status == "completed" }; val opened = topics.count { it.status != "not_started" }
        val i = courses.indexOf(c)
        ListRow(c.name,
            if (c.archived) stringResource(R.string.course_unavailable)
            else listOfNotNull(pluralStringResource(R.plurals.topics, topics.size, topics.size),
                if (opened > 0) stringResource(R.string.n_opened, opened) else null, if (done > 0) stringResource(R.string.n_learned, done) else null).joinToString(" · "),
            onClick = { if (c.archived) android.widget.Toast.makeText(ctx, R.string.course_unavailable, android.widget.Toast.LENGTH_SHORT).show() else open(c.id) },
            leading = { if (c.archived) RowIcon(Icons.Outlined.Lock) else Dot(c.name, CourseColors[i % CourseColors.size]) },
            trailing = if (c.archived) ({}) else null)
    }
}

fun Modifier.clickableRounded(onClick: () -> Unit) = clip(RoundedCornerShape(16.dp)).clickable(onClick = onClick)

/** "Remember this?": one question from something read a few days ago; easy to ignore, hidden for the day once dismissed */
@Composable
fun RecallCard(openTopic: (Int) -> Unit) {
    val app = app(); val day = LocalDate.now().toString()
    var off by remember { mutableStateOf(app.store.recallHiddenOn == day) }
    if (off) return
    val r = rememberLoad("recall") { get("/me/recall", Recall.serializer()) }
    val item = (r.state as? Load.Ok)?.value?.item ?: return
    Panel {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.remember_this), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary, modifier = Modifier.weight(1f))
            IconButton(onClick = { app.store.recallHiddenOn = day; off = true }) { Icon(Icons.Filled.Close, stringResource(R.string.not_now)) }
        }
        Text(item.question, style = MaterialTheme.typography.titleMedium)
        Reveal(stringResource(R.string.think_then_tap)) {
            Md(item.answer)
            TextButton(onClick = { openTopic(item.topic_id) }) { Text(stringResource(R.string.open_title, item.title)) }
        }
    }
}

/** a quiet note when a newer version of this app is out (the server checks once a day) */
@Composable
fun UpdateCard() {
    val r = rememberLoad("update") { runCatching { get("/app/android", AndroidRelease.serializer()) }.getOrNull() }
    val rel = (r.state as? Load.Ok)?.value ?: return
    if ((rel.code ?: 0) <= BuildConfig.VERSION_CODE || rel.url == null) return
    val ctx = LocalContext.current
    ListRow(stringResource(R.string.update_ready, rel.version.orEmpty()), stringResource(R.string.update_tap),
            onClick = { ctx.startActivity(Intent(Intent.ACTION_VIEW, rel.url.toUri())) }, leading = { RowIcon(Icons.Outlined.SystemUpdate) })
}
