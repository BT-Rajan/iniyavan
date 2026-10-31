package app.zigora.ui

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.MenuBook
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.automirrored.outlined.TrendingUp
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteScaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.toRoute
import app.zigora.Incoming
import app.zigora.R
import app.zigora.data.Me
import app.zigora.data.json
import kotlinx.serialization.Serializable
import kotlinx.coroutines.launch
import kotlinx.serialization.json.put

@Serializable object HomeR
@Serializable object CoursesR
@Serializable data class SearchR(val q: String = "")
@Serializable object MeR
@Serializable data class CourseR(val id: Int)
@Serializable data class TopicR(val id: Int)
@Serializable data class QuizR(val id: Int)
@Serializable data class PhotoR(val uri: String = "")
@Serializable object NotesR
@Serializable data class ReaderR(val id: Int)
@Serializable data class DiagramR(val url: String)
@Serializable data class StudyQuizR(val id: Int, val topic: Int = 0, val own: Int = 0)  // topic: a college topic's practice; own: a topic of the student's own course
@Serializable object StudyR
@Serializable data class StudyCourseR(val id: Int)
@Serializable data class StudyWizardR(val id: Int)
@Serializable data class StudyTopicR(val id: Int)
@Serializable data class MaterialR(val cid: Int, val name: String = "")
@Serializable object PasswordR
@Serializable object KeyR
@Serializable object SavedR
@Serializable object ProgressR
@Serializable object RoutineR
@Serializable object CalendarR
@Serializable data class ScoreCourseR(val cid: Int)
@Serializable data class AttemptsR(val quiz: Int)
@Serializable data class AttemptR(val id: Int)
@Serializable data class RevisionR(val uid: Int)
@Serializable data class McqR(val topic: Int = 0)  // MCQ practice; a topic for the Per topic way in
@Serializable data class McqSetR(val id: Int)

@Composable
fun ZigoraRoot(incoming: Incoming?, handled: () -> Unit) {
    val app = app(); val out by app.signedOut.collectAsState()
    var wallpaper by remember { mutableStateOf(app.store.wallpaper) }
    var theme by remember { mutableStateOf(app.store.theme) }
    var me by remember(out) { mutableStateOf(app.store.userJson?.let { runCatching { json.decodeFromString(Me.serializer(), it) }.getOrNull() }.takeIf { app.store.token != null }) }
    ZigoraTheme(wallpaper, theme) {
        val user = me
        if (user == null || user.role != "student" || user.must_change) LaunchedEffect(Unit) { app.firstScreenReady.value = true }  // Home says so itself, once it has loaded
        when {
            user == null -> SignIn { m -> app.store.userJson = json.encodeToString(Me.serializer(), m); me = m }
            user.role == "guardian" -> GuardianHome(user) { app.store.signOut(); me = null }  // a parent or teacher who signed up: their children or students
            user.role != "student" -> StaffNote(user) { app.store.signOut(); me = null }  // college staff and admins stay on the web
            user.must_change -> ChangePassword(forced = true) { me = user.copy(must_change = false).also { app.store.userJson = json.encodeToString(Me.serializer(), it) } }
            else -> Main(user, incoming, handled, wallpaper = { wallpaper = it; app.store.wallpaper = it }, theme = { theme = it; app.store.theme = it }) { app.store.signOut(); me = null }
        }
        CrashNote()
    }
}

private data class Tab(val route: Any, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

@Composable
private fun Main(me: Me, incoming: Incoming?, handled: () -> Unit, wallpaper: (Boolean) -> Unit, theme: (String) -> Unit, signOut: () -> Unit) {
    val nav = rememberNavController()
    // the web's menu for students (My courses, Saved, My progress) with Home and the account; search sits at the top, as in the web's header
    // short labels, so five fit on any phone at any text size; the screens themselves carry the web's full titles
    val tabs = listOf(Tab(HomeR, stringResource(R.string.tab_home), Icons.Outlined.Home), Tab(CoursesR, stringResource(R.string.tab_courses), Icons.AutoMirrored.Outlined.MenuBook),
                      Tab(SavedR, stringResource(R.string.tab_saved), Icons.Outlined.BookmarkBorder), Tab(ProgressR, stringResource(R.string.tab_progress), Icons.AutoMirrored.Outlined.TrendingUp),
                      Tab(MeR, stringResource(R.string.tab_me), Icons.Outlined.AccountCircle))
    val entry by nav.currentBackStackEntryAsState(); val dest = entry?.destination
    LaunchedEffect(incoming) {
        when (incoming) {
            is Incoming.Lookup -> nav.navigate(SearchR(incoming.text))
            is Incoming.Photo -> nav.navigate(PhotoR(incoming.uri?.toString().orEmpty()))
            null -> return@LaunchedEffect
        }
        handled()
    }
    androidx.compose.runtime.CompositionLocalProvider(LocalMe provides me) { NavigationSuiteScaffold(navigationSuiteItems = {
        tabs.forEach { t ->
            item(selected = dest?.hasRoute(t.route::class) == true, icon = { Icon(t.icon, null) }, label = { Text(t.label, maxLines = 1, softWrap = false, autoSize = androidx.compose.foundation.text.TextAutoSize.StepBased(minFontSize = 9.sp, maxFontSize = 12.sp)) },
                 onClick = { nav.navigate(t.route) { popUpTo(nav.graph.findStartDestination().id) { saveState = true }; launchSingleTop = true; restoreState = true } })
        }
    }) {
        val open = { id: Int -> nav.navigate(TopicR(id)) }
        val search = { nav.navigate(SearchR()) }
        val scope = androidx.compose.runtime.rememberCoroutineScope(); val a = api(); val toast = rememberToast()
        val ownTopic = { cid: Int, tid: Int -> nav.navigate(StudyCourseR(cid)); nav.navigate(StudyTopicR(tid)) }
        val review = { cid: Int -> scope.launch {  // a review set from the student's own earlier questions
            try { val q = a.send("POST", "/study/courses/$cid/review", null, app.zigora.data.StudyQuiz.serializer()).id; onMain { nav.navigate(StudyQuizR(q)) } } catch (e: Exception) { toast(e.message.orEmpty()) }
        }; Unit }
        val session = { x: app.zigora.data.SessionItem -> when {
            x.kind == "review" -> x.course_id?.let { review(it) } ?: Unit
            x.src == "study" -> x.course_id?.let { ownTopic(it, x.id) } ?: nav.navigate(StudyTopicR(x.id))
            else -> open(x.id)
        } }
        NavHost(nav, startDestination = HomeR) {
            composable<HomeR> { HomeScreen(me, openTopic = open, openCourse = { nav.navigate(CourseR(it)) }, openQuiz = { nav.navigate(QuizR(it)) },
                                           openNotes = { nav.navigate(NotesR) }, openPhoto = { nav.navigate(PhotoR()) }, openSearch = search,
                                           openRoutine = { nav.navigate(RoutineR) }, openSession = session, openStudy = { nav.navigate(StudyR) }, openMcq = { nav.navigate(McqR()) }, openCalendar = { nav.navigate(CalendarR) }, openProgress = { nav.navigate(ProgressR) }, openPlan = { nav.navigate(MeR) },
                                           openOwn = ownTopic, review = review) }
            composable<CoursesR> { CoursesScreen(me, search, openStudy = { nav.navigate(StudyR) }) { nav.navigate(CourseR(it)) } }
            composable<StudyR> { StudyHomeScreen(back = { nav.popBackStack() }, open = { id, wizard -> nav.navigate(if (wizard) StudyWizardR(id) else StudyCourseR(id)) },
                                                 openTopic = ownTopic, review = review) }
            composable<StudyWizardR> { e -> val id = e.toRoute<StudyWizardR>().id
                StudyWizardScreen(id, back = { nav.popBackStack() }) { nav.navigate(StudyCourseR(id)) { popUpTo<StudyWizardR> { inclusive = true } } } }
            composable<StudyCourseR> { e -> val id = e.toRoute<StudyCourseR>().id
                StudyCourseScreen(id, back = { nav.popBackStack() }, setup = { nav.navigate(StudyWizardR(id)) { popUpTo<StudyCourseR> { inclusive = true } } },
                                  openTopic = { nav.navigate(StudyTopicR(it)) }, review = { q -> nav.navigate(StudyQuizR(q.id)) }) }
            composable<StudyTopicR> { e -> val id = e.toRoute<StudyTopicR>().id
                StudyTopicScreen(id, back = { nav.popBackStack() }, go = { t -> nav.navigate(StudyTopicR(t)) { popUpTo<StudyTopicR> { inclusive = true } } },
                                 quiz = { q -> nav.navigate(StudyQuizR(q.id, own = id)) }) }
            composable<SavedR> { SavedScreen(open) }
            composable<ProgressR> { ProgressScreen(open, openRoutine = { nav.navigate(RoutineR) }, openScores = { nav.navigate(ScoreCourseR(it)) }) }
            composable<RoutineR> { RoutineScreen { nav.popBackStack() } }
            composable<CalendarR> { CalendarScreen { nav.popBackStack() } }
            composable<ScoreCourseR> { ScoreCourseScreen(it.toRoute<ScoreCourseR>().cid, back = { nav.popBackStack() }) { q -> nav.navigate(AttemptsR(q)) } }
            composable<AttemptsR> { AttemptsScreen(it.toRoute<AttemptsR>().quiz, back = { nav.popBackStack() }) { id -> nav.navigate(AttemptR(id)) } }
            composable<AttemptR> { AttemptScreen(it.toRoute<AttemptR>().id, back = { nav.popBackStack() }, openTopic = open) }
            composable<RevisionR> { RevisionScreen(it.toRoute<RevisionR>().uid) { nav.popBackStack() } }
            composable<SearchR> { SearchScreen(it.toRoute<SearchR>().q, back = { nav.popBackStack() }, openTopic = open, openPhoto = { nav.navigate(PhotoR()) }) }
            composable<MeR> { ProfileScreen(me, wallpaper, theme, signOut, openPassword = { nav.navigate(PasswordR) }, openKey = { nav.navigate(KeyR) }) }
            composable<PasswordR> { ChangePassword(forced = false, back = { nav.popBackStack() }) { nav.popBackStack() } }
            composable<KeyR> { MyKeyScreen { nav.popBackStack() } }
            composable<CourseR> { CourseScreen(it.toRoute<CourseR>().id, back = { nav.popBackStack() }, openTopic = open, openQuiz = { q -> nav.navigate(QuizR(q)) },
                                               openMaterial = { cid, name -> nav.navigate(MaterialR(cid, name)) }, openRevision = { u -> nav.navigate(RevisionR(u)) }) }
            composable<TopicR> { TopicScreen(it.toRoute<TopicR>().id, me, back = { nav.popBackStack() }, jump = { id -> nav.navigate(TopicR(id)) { popUpTo<TopicR> { inclusive = true } } },
                                             openReader = { id -> nav.navigate(ReaderR(id)) }, openPractice = { q -> nav.navigate(StudyQuizR(q, it.toRoute<TopicR>().id)) },
                                             openMcq = { t -> nav.navigate(McqR(t)) }, openDiagram = { u -> nav.navigate(DiagramR(u)) },
                                             openMaterial = { cid, name -> nav.navigate(MaterialR(cid, name)) }) }
            composable<DiagramR> { DiagramScreen(it.toRoute<DiagramR>().url) { nav.popBackStack() } }
            composable<ReaderR> { e -> val id = e.toRoute<ReaderR>().id
                val t = rememberLoad("reader", id) { get("/topics/$id", app.zigora.data.TopicFull.serializer()) }
                Loaded(t) { ReaderScreen(it) { nav.popBackStack() } } }
            composable<StudyQuizR> { e -> val r = e.toRoute<StudyQuizR>()
                val own = if (r.own == 0) null else (rememberLoad("own-next", r.own) { get("/study/topics/${r.own}", app.zigora.data.STopicFull.serializer()) }.state as? Load.Ok)?.value
                val path = if (r.topic != 0) "/topics/${r.topic}/practice" else if (r.own != 0) "/study/topics/${r.own}/quizzes" else null
                StudyQuizScreen(r.id, back = { nav.popBackStack() }, again = path?.let { p -> { kind: String -> scope.launch {
                    try { val q = a.send("POST", p, kotlinx.serialization.json.buildJsonObject { put("kind", kind) }, app.zigora.data.StudyQuiz.serializer()).id
                          onMain { nav.navigate(StudyQuizR(q, r.topic, r.own)) { popUpTo<StudyQuizR> { inclusive = true } } } } catch (x: Exception) { toast(x.message.orEmpty()) }
                }; Unit } }, next = own?.next?.let { n -> n.title to { nav.popBackStack(); nav.navigate(StudyTopicR(n.id)) { popUpTo<StudyTopicR> { inclusive = true } } } }) }
            composable<MaterialR> { e -> val r = e.toRoute<MaterialR>(); MyMaterialScreen(r.cid, r.name) { nav.popBackStack() } }
            composable<QuizR> { QuizScreen(it.toRoute<QuizR>().id, back = { nav.popBackStack() }, openTopic = open,
                                           openAttempt = { id -> nav.navigate(AttemptR(id)) }, openAttempts = { q -> nav.navigate(AttemptsR(q)) }) }
            composable<McqR> { McqHomeScreen(it.toRoute<McqR>().topic, back = { nav.popBackStack() }) { id -> nav.navigate(McqSetR(id)) } }
            composable<McqSetR> { McqSetScreen(it.toRoute<McqSetR>().id, back = { nav.popBackStack() }, openTopic = open) }
            composable<PhotoR> { PhotoScreen(it.toRoute<PhotoR>().uri) { nav.popBackStack() } }
            composable<NotesR> { NotificationsScreen(back = { nav.popBackStack() }, openTopic = open) }
        }
    }
    }
}

/** who is signed in, for parts that differ by role (only students flag an AI answer, as on the web) */
val LocalMe = androidx.compose.runtime.staticCompositionLocalOf<Me?> { null }

/** the app is the students' half of Zigora: staff are pointed to the web, where their tools are */
@Composable
private fun StaffNote(me: Me, signOut: () -> Unit) {
    val ctx = androidx.compose.ui.platform.LocalContext.current; val app = app()
    androidx.compose.material3.Scaffold { pad ->
        androidx.compose.foundation.layout.Column(androidx.compose.ui.Modifier.padding(pad).fillMaxWidth().verticalScroll(androidx.compose.foundation.rememberScrollState()).padding(24.dp),
                                                  verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(16.dp), horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
            Gap(if (me.role == "admin") 16 else 48)
            androidx.compose.foundation.Image(androidx.compose.ui.res.painterResource(R.drawable.ic_logo), null, androidx.compose.ui.Modifier.size(72.dp))
            Text(stringResource(R.string.staff_title), style = androidx.compose.material3.MaterialTheme.typography.headlineSmall)
            Text(stringResource(R.string.staff_body, firstName(me.name), app.store.appName, app.store.server), textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                 color = androidx.compose.material3.MaterialTheme.colorScheme.onSurfaceVariant)
            androidx.compose.material3.Button(onClick = { runCatching { ctx.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, app.store.server.toUri())) } },
                                              modifier = androidx.compose.ui.Modifier.fillMaxWidth()) { Text(stringResource(R.string.open_in_browser)) }
            androidx.compose.material3.OutlinedButton(onClick = signOut, modifier = androidx.compose.ui.Modifier.fillMaxWidth()) { Text(stringResource(R.string.sign_out)) }
            if (me.role == "admin") MoreAiPanel()  // the one admin task the app does too: giving a student more AI
        }
    }
}

/** after a crash, the next start offers the report to share (by mail, chat, anything); it stays on the phone otherwise */
@Composable
private fun CrashNote() {
    val app = app(); val ctx = androidx.compose.ui.platform.LocalContext.current
    var report by remember { mutableStateOf(runCatching { app.crashFile.takeIf { it.exists() }?.readText() }.getOrNull()) }
    val text = report ?: return
    val done = { runCatching { app.crashFile.delete() }; report = null }
    androidx.compose.material3.AlertDialog(onDismissRequest = done, title = { Text(stringResource(R.string.crash_title)) }, text = { Text(stringResource(R.string.crash_body)) },
        confirmButton = { androidx.compose.material3.TextButton(onClick = {
            val send = android.content.Intent(android.content.Intent.ACTION_SEND).setType("text/plain").putExtra(android.content.Intent.EXTRA_SUBJECT, "Zigora crash report")
                .putExtra(android.content.Intent.EXTRA_TEXT, text)
            runCatching { ctx.startActivity(android.content.Intent.createChooser(send, null)) }; done()
        }) { Text(stringResource(R.string.crash_share)) } },
        dismissButton = { androidx.compose.material3.TextButton(onClick = done) { Text(stringResource(R.string.not_now)) } })
}
