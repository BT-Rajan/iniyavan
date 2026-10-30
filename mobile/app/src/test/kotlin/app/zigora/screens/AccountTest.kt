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
import app.zigora.ui.ZigoraRoot
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** The account screens on a phone: a child who signs in with a username opens Me; an admin gives a student who asked for more AI a month of Pro.
 *  Against the server mobile/screens_seed.py starts; screenshots go to build/screens. */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w411dp-h891dp-xxhdpi")
class AccountTest {
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
    private fun tapExactly(text: String) = rule.onAllNodesWithText(text).onFirst().performClick()  // "Submit" in a dialog, not "Submit answers"
    private fun none(text: String) = rule.onAllNodesWithText(text, substring = true).fetchSemanticsNodes().isEmpty()
    private fun shot(name: String) { rule.waitForIdle(); rule.onRoot().captureRoboImage("$out/$name.png") }

    @Test fun aChildOpensMe() {  // a username account has no email: Me shows the username and the plan reads as no AI, not Lite
        signIn("kavin")
        rule.setContent { ZigoraRoot(null) {} }
        see("Me"); tapExactly("Me")
        see("Kavin"); see("kavin"); see("No AI"); shot("account-01-child-me")
        assertTrue("a child's plan is not shown as Lite", none("Free each day"))
    }

    @Test fun theSignInScreenOffersGoogle() {  // the server has a Google client ID: its button sits under Sign in (Google's own sheet can't open here)
        app.store.server = server; app.store.signOut()
        rule.setContent { ZigoraRoot(null) {} }
        see("Sign in with Google"); see("Create an account"); shot("account-04-sign-in-with-google")
        rule.onAllNodesWithText("Create an account").onFirst().performClick()  // the other tab: sign up with Google or with an email
        see("Sign up with Google"); see("Sign up with email"); assertTrue("no password box on the sign-up tab", rule.onAllNodesWithText("Password").fetchSemanticsNodes().isEmpty())
        shot("account-05-create-an-account")
    }

    @Test fun anAdminGivesMoreAi() {
        signIn("admin@x.com")
        rule.setContent { ZigoraRoot(null) {} }
        see("More AI"); see("Asha"); shot("account-02-more-ai")
        tap("Asha"); see("30 days"); tap("30 days")
        rule.waitUntil(20_000) { none("asha@x.com") }  // she leaves the list of people asking
        tapExactly("Pro"); see("Asha"); see("Pro until"); shot("account-03-now-pro")
    }
}
