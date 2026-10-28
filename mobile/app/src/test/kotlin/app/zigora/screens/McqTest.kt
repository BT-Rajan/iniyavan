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

/** MCQ practice on a phone: a child (not on Lite or Pro, so no limit) takes a set from the bank and sees the result; a parent has no MCQ practice.
 *  Against the server mobile/screens_seed.py starts; screenshots go to build/screens. */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w411dp-h891dp-xxhdpi")
class McqTest {
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

    @Test fun aChildTakesASetFromTheBankAndSeesTheResult() {
        signIn("kavin")
        rule.setContent { ZigoraRoot(null) {} }
        see("MCQ practice"); tap("MCQ practice")
        see("3 published questions"); shot("mcq-01-home")
        assertTrue("no limit line: only students on Lite or Pro have a limit", none("MCQ set"))
        assertTrue("no AI sets without a parent's or teacher's key", none("A new AI set"))
        tap("Questions from the bank"); see("Question 1"); shot("mcq-02-set")
        tap("easily with soap"); tap("Submit answers"); see("Submit with"); tapExactly("Submit")
        see("/ 3"); see("Correct answer"); shot("mcq-03-result")
    }

    @Test fun aParentHasNoMcqPractice() {
        signIn("mum@x.com")
        rule.setContent { ZigoraRoot(null) {} }
        see("Your children"); assertTrue("a parent sees no MCQ practice", none("MCQ practice"))
    }
}
