package app.zigora.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.MenuBook
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Search
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

@Serializable object HomeR
@Serializable object CoursesR
@Serializable data class SearchR(val q: String = "")
@Serializable object MeR
@Serializable data class CourseR(val id: Int)
@Serializable data class TopicR(val id: Int)
@Serializable data class QuizR(val id: Int)
@Serializable data class PhotoR(val uri: String = "")
@Serializable object NotesR
@Serializable object PasswordR
@Serializable object KeyR

@Composable
fun ZigoraRoot(incoming: Incoming?, handled: () -> Unit) {
    val app = app(); val out by app.signedOut.collectAsState()
    var wallpaper by remember { mutableStateOf(app.store.wallpaper) }
    var theme by remember { mutableStateOf(app.store.theme) }
    var me by remember(out) { mutableStateOf(app.store.userJson?.let { runCatching { json.decodeFromString(Me.serializer(), it) }.getOrNull() }.takeIf { app.store.token != null }) }
    ZigoraTheme(wallpaper, theme) {
        val user = me
        when {
            user == null -> SignIn { m -> app.store.userJson = json.encodeToString(Me.serializer(), m); me = m }
            user.must_change -> ChangePassword(forced = true) { me = user.copy(must_change = false).also { app.store.userJson = json.encodeToString(Me.serializer(), it) } }
            else -> Main(user, incoming, handled, wallpaper = { wallpaper = it; app.store.wallpaper = it }, theme = { theme = it; app.store.theme = it }) { app.store.signOut(); me = null }
        }
    }
}

private data class Tab(val route: Any, val label: Int, val icon: androidx.compose.ui.graphics.vector.ImageVector)

@Composable
private fun Main(me: Me, incoming: Incoming?, handled: () -> Unit, wallpaper: (Boolean) -> Unit, theme: (String) -> Unit, signOut: () -> Unit) {
    val nav = rememberNavController()
    val tabs = listOf(Tab(HomeR, R.string.tab_home, Icons.Outlined.Home), Tab(CoursesR, R.string.tab_courses, Icons.AutoMirrored.Outlined.MenuBook),
                      Tab(SearchR(), R.string.tab_search, Icons.Outlined.Search), Tab(MeR, R.string.tab_me, Icons.Outlined.AccountCircle))
    val entry by nav.currentBackStackEntryAsState(); val dest = entry?.destination
    LaunchedEffect(incoming) {
        when (incoming) {
            is Incoming.Lookup -> nav.navigate(SearchR(incoming.text))
            is Incoming.Photo -> nav.navigate(PhotoR(incoming.uri?.toString().orEmpty()))
            null -> return@LaunchedEffect
        }
        handled()
    }
    NavigationSuiteScaffold(navigationSuiteItems = {
        tabs.forEach { t ->
            item(selected = dest?.hasRoute(t.route::class) == true, icon = { Icon(t.icon, null) }, label = { Text(stringResource(t.label)) },
                 onClick = { nav.navigate(t.route) { popUpTo(nav.graph.findStartDestination().id) { saveState = true }; launchSingleTop = true; restoreState = true } })
        }
    }) {
        val open = { id: Int -> nav.navigate(TopicR(id)) }
        NavHost(nav, startDestination = HomeR) {
            composable<HomeR> { HomeScreen(me, openTopic = open, openCourse = { nav.navigate(CourseR(it)) }, openQuiz = { nav.navigate(QuizR(it)) },
                                           openNotes = { nav.navigate(NotesR) }, openPhoto = { nav.navigate(PhotoR()) }) }
            composable<CoursesR> { CoursesScreen(me) { nav.navigate(CourseR(it)) } }
            composable<SearchR> { SearchScreen(it.toRoute<SearchR>().q, openTopic = open, openPhoto = { nav.navigate(PhotoR()) }) }
            composable<MeR> { ProfileScreen(me, wallpaper, theme, signOut, openPassword = { nav.navigate(PasswordR) }, openKey = { nav.navigate(KeyR) }) }
            composable<PasswordR> { ChangePassword(forced = false, back = { nav.popBackStack() }) { nav.popBackStack() } }
            composable<KeyR> { MyKeyScreen { nav.popBackStack() } }
            composable<CourseR> { CourseScreen(it.toRoute<CourseR>().id, back = { nav.popBackStack() }, openTopic = open, openQuiz = { q -> nav.navigate(QuizR(q)) }) }
            composable<TopicR> { TopicScreen(it.toRoute<TopicR>().id, me, back = { nav.popBackStack() }, jump = { id -> nav.navigate(TopicR(id)) { popUpTo<TopicR> { inclusive = true } } }) }
            composable<QuizR> { QuizScreen(it.toRoute<QuizR>().id) { nav.popBackStack() } }
            composable<PhotoR> { PhotoScreen(it.toRoute<PhotoR>().uri) { nav.popBackStack() } }
            composable<NotesR> { NotificationsScreen(back = { nav.popBackStack() }, openTopic = open) }
        }
    }
}
