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
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Assigned tests on a phone: a child takes the MCQ set their teacher assigned (outside the daily MCQ limit), and the teacher sees each student's state.
 *  Against the server mobile/screens_seed.py starts; screenshots go to build/screens. */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w411dp-h891dp-xxhdpi")
class AssignTest {
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
    private fun shot(name: String) { rule.waitForIdle(); rule.onRoot().captureRoboImage("$out/$name.png") }

    @Test fun aChildTakesTheSetTheirTeacherAssigned() {
        signIn("kavin")
        rule.setContent { ZigoraRoot(null) {} }
        see("Assigned to me"); tap("Assigned to me")
        see("Water revision check"); see("from Ms Rani"); see("Unlimited attempts"); shot("assign-01-student-list")
        tap("Start"); see("Question 1"); shot("assign-02-set")
        tap("easily with soap"); tap("Submit answers"); see("Submit with"); tapExactly("Submit")
        see("/ 3"); shot("assign-03-result")
    }

    @Test fun aTeacherSeesEachStudentOnTheirAssignment() {
        signIn("rani@school.in")
        rule.setContent { ZigoraRoot(null) {} }
        see("Assigned tests"); tap("Assigned tests")
        see("Water revision check"); see("of 1 done"); shot("assign-04-teacher-list")
        tap("Water revision check"); see("Kavin"); see("1 student"); shot("assign-05-teacher-students")
    }
}
