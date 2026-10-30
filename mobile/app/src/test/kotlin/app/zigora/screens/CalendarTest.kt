package app.zigora.screens

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.zigora.ZigoraApp
import app.zigora.data.Api
import app.zigora.data.LoginOut
import app.zigora.data.Me
import app.zigora.data.Sealer
import app.zigora.data.Store
import app.zigora.data.json
import app.zigora.ui.CalendarScreen
import app.zigora.ui.ZigoraRoot
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** The calendar on a phone: a child sees the Grade 6 test on Home and in the calendar; their parent sees it in the child's calendar.
 *  Against the server mobile/screens_seed.py starts; screenshots go to build/screens. */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w411dp-h891dp-xxhdpi")
class CalendarTest {
    @get:Rule val rule = createComposeRule()
    private val out = System.getProperty("screens.out")!!
    private val server = System.getProperty("screens.server")!!
    private val app get() = ApplicationProvider.getApplicationContext<ZigoraApp>()

    @org.junit.Before fun plainStore() {
        app.store = Store(app, object : Sealer { override fun seal(s: String) = s; override fun open(s: String) = s })
        app.api = Api(app.store) { app.signedOut.value++ }
    }
    private fun signIn(who: String) = runBlocking {
        app.store.server = server
        val r = app.api.send("POST", "/login", buildJsonObject { put("email", who); put("password", "pw123456") }, LoginOut.serializer())
        app.store.token = r.token; app.store.userJson = json.encodeToString(Me.serializer(), r.user)
    }
    private fun see(text: String, ms: Long = 20_000) = rule.waitUntilAtLeastOneExists(hasText(text, substring = true), ms)
    private fun tap(text: String) { val n = rule.onAllNodesWithText(text, substring = true).onFirst(); runCatching { n.performScrollTo() }; n.performClick() }
    private fun shot(name: String) { rule.waitForIdle(); rule.onRoot().captureRoboImage("$out/$name.png") }

    @Test fun aChildSeesTheTestComingUpOnHome() {
        signIn("kavin")
        rule.setContent { ZigoraRoot(null) {} }
        see("Coming up"); see("Science test"); shot("calendar-01-home")
    }

    @Test fun aChildSeesTheTestInTheCalendar() {
        signIn("kavin")
        rule.setContent { CalendarScreen(null) }
        see("On your phone's calendar"); see("Science test"); shot("calendar-02-month")
    }

    @Test fun aChildOpensTheFormToAddAnEvent() {
        signIn("kavin")
        rule.setContent { CalendarScreen(null) }
        see("Science test"); tap("Add event"); see("Add an event"); shot("calendar-03-add")
    }

    @Test fun aParentSeesTheirChildsCalendar() {
        signIn("mum@x.com")
        rule.setContent { ZigoraRoot(null) {} }
        see("Your children's calendar"); tap("Your children's calendar"); see("Whose calendar")
        tap("My own events"); see("Kavin"); rule.onAllNodesWithText("Kavin").onFirst().performClick()
        see("Kavin's calendar"); see("Science test"); shot("calendar-04-parent")
    }
}
