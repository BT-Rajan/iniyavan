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
import app.zigora.ui.AI_OFF
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

/** The school and college onboarding on a phone: sign-up steps, a parent's and a teacher's screens, a child with no AI key, and a teacher's
 *  invitation. Against the server mobile/screens_seed.py starts; a screenshot of each screen goes to build/screens. */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w411dp-h891dp-xxhdpi")
class OnboardingTest {
    @get:Rule val rule = createComposeRule()
    private val out = System.getProperty("screens.out")!!
    private val server = System.getProperty("screens.server")!!
    private val app get() = ApplicationProvider.getApplicationContext<ZigoraApp>()

    @org.junit.Before fun plainStore() { // Robolectric has no Android Keystore
        app.store = Store(app, object : Sealer { override fun seal(s: String) = s; override fun open(s: String) = s })
        app.api = Api(app.store) { app.signedOut.value++ }
    }
    private fun signIn(who: String) = runBlocking {  // an email, or a child's username
        app.store.server = server
        val r = app.api.send("POST", "/login", buildJsonObject { put("email", who); put("password", "pw123456") }, LoginOut.serializer())
        app.store.token = r.token; app.store.userJson = json.encodeToString(Me.serializer(), r.user)
    }
    private fun see(text: String, ms: Long = 20_000) = rule.waitUntilAtLeastOneExists(hasText(text, substring = true), ms)
    private fun tap(text: String) = rule.onAllNodesWithText(text, substring = true).onFirst().performClick()
    private fun none(text: String) = rule.onAllNodesWithText(text, substring = true).fetchSemanticsNodes().isEmpty()
    private fun shot(name: String) { rule.waitForIdle(); rule.onRoot().captureRoboImage("$out/$name.png") }

    @Test fun signUpAsksSchoolOrCollegeThenWho() {
        app.store.server = server; app.store.signOut()
        rule.setContent { ZigoraRoot(null) {} }
        see("Create an account"); tap("Create an account")
        see("Who is studying?"); shot("onboarding-01-school-or-college")
        tap("A school student"); see("Who is signing up?"); shot("onboarding-02-who")
        tap("A parent"); see("Child 1"); see("Your children"); shot("onboarding-03-parent-form")
        rule.onAllNodesWithText("Add another child").onFirst().performScrollTo(); shot("onboarding-04-parent-form-children")
    }

    @Test fun aParentSeesTheirChildAndTheAiKey() {
        signIn("mum@x.com")
        rule.setContent { ZigoraRoot(null) {} }
        see("Your children"); see("Kavin"); see("Signs in as kavin"); shot("onboarding-05-parent-home")
        assertTrue("the parent's AI panel says off", !none("Add an AI key"))
        tap("Kavin"); see("topics learned"); see("Forgot their password?"); shot("onboarding-06-child-progress")
    }

    @Test fun aTeacherCanAddAndInvite() {
        signIn("rani@school.in")
        rule.setContent { ZigoraRoot(null) {} }
        see("Your students"); see("Divya"); see("Invite a student"); shot("onboarding-07-teacher-home")  // Divya shows as invited until another test accepts
        tap("Add students"); see("Student 1"); shot("onboarding-08-teacher-add")
    }

    @Test fun aChildWithoutAKeyGetsNoAi() {
        signIn("kavin")
        rule.setContent { ZigoraRoot(null) {} }
        see("Science"); shot("onboarding-09-child-home")
        rule.onAllNodesWithText("Science").onFirst().performClick()  // the course card (an exact match, not a topic row that names the course)
        see("Soft water"); tap("Soft water")
        see(AI_OFF); shot("onboarding-10-child-topic-no-ai")
        assertTrue("no Explain tab without a key", none("Sample answer"))
    }

    @Test fun aStudentAcceptsAnInvitation() {
        signIn("divya@x.com")
        rule.setContent { ZigoraRoot(null) {} }
        see("Ms Rani wants to follow your progress"); shot("onboarding-11-invitation")
        tap("Accept")
        rule.waitUntil(20_000) { none("wants to follow your progress") }; shot("onboarding-12-invitation-accepted")
    }
}
