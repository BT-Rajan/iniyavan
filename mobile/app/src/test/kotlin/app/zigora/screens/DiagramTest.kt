package app.zigora.screens

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onLast
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
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** A topic's diagram (the teacher turned it on for "Hardness of Water" in .promo/server.py): a college student opens it full screen;
 *  a student on Lite sees that it comes with Pro. The drawing itself runs in a WebView, which Robolectric leaves blank. */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w390dp-h844dp-xxhdpi")
class DiagramTest {
    @get:org.junit.Rule val rule = createComposeRule()
    private val app get() = ApplicationProvider.getApplicationContext<ZigoraApp>()
    private val out = System.getProperty("screens.out")!! + "/diagram"

    private fun shot(name: String) { rule.waitForIdle(); rule.onRoot().captureRoboImage("$out/$name.png") }
    private fun see(text: String) = rule.waitUntilAtLeastOneExists(hasText(text, substring = true), 20_000)
    private fun tap(text: String) { see(text); rule.onAllNodesWithText(text, substring = true).onFirst().performScrollTo().performClick() }

    private fun signIn(email: String) = runBlocking {
        app.store = Store(app, object : Sealer { override fun seal(s: String) = s; override fun open(s: String) = s })  // Robolectric has no Android Keystore
        app.api = Api(app.store) { app.signedOut.value++ }
        app.store.server = System.getProperty("screens.server")!!; app.store.wallpaper = false
        val r = app.api.send("POST", "/login", buildJsonObject { put("email", email); put("password", "pw123456") }, LoginOut.serializer())
        app.store.token = r.token; app.store.userJson = json.encodeToString(Me.serializer(), r.user)
    }

    private fun openTheTopic() {
        rule.setContent { ZigoraRoot(null) {} }
        see("Engineering Chemistry"); rule.onNode(hasText("Courses") and hasClickAction()).performClick()
        see("Engineering Chemistry"); rule.onAllNodesWithText("Engineering Chemistry").onLast().performClick()
        tap("Hardness of Water"); see("The gist")
    }

    @Test fun aCollegeStudentOpensTheDiagramFullScreen() {
        signIn("stu@mail.com"); openTheTopic()
        rule.onAllNodesWithText("Diagram").onFirst().performScrollTo(); shot("1-diagram-step")
        tap("Diagram")
        rule.waitUntil(20_000) { rule.onAllNodesWithText("The gist").fetchSemanticsNodes().isEmpty() }  // the topic gave way to the full-screen diagram
        see("Diagram"); shot("2-diagram-open")
    }

    @Test fun aLiteStudentSeesItComesWithPro() {
        signIn("ravi@gmail.com"); openTheTopic()
        tap("Diagram"); see("Diagrams come with Pro"); shot("3-diagram-pro")
    }
}
