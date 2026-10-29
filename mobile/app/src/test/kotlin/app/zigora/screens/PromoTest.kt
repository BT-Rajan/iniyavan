package app.zigora.screens

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onLast
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.zigora.ZigoraApp
import app.zigora.data.Api
import app.zigora.data.Highlights
import app.zigora.data.LoginOut
import app.zigora.data.Me
import app.zigora.data.ProgramNode
import app.zigora.data.Quiz
import app.zigora.data.Sealer
import app.zigora.data.Store
import app.zigora.data.json
import app.zigora.ui.ZigoraRoot
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** The shots for the marketing promo (.promo/capture.js runs this against .promo/server.py): a student's day in the app with some
 *  saved work in it, at the promo's phone size (390×844 at 3×), and Home and a topic in Tamil and Arabic. Saved to screens/promo. */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w390dp-h844dp-xxhdpi")
class PromoTest {
    @get:org.junit.Rule val rule = createComposeRule()
    private val app get() = ApplicationProvider.getApplicationContext<ZigoraApp>()
    private val out = System.getProperty("screens.out")!! + "/promo"

    private fun shot(name: String) { rule.waitForIdle(); Thread.sleep(300); rule.waitForIdle(); rule.onRoot().captureRoboImage("$out/$name.png") }
    private fun see(text: String) = rule.waitUntilAtLeastOneExists(hasText(text, substring = true), 20_000)
    private fun tap(text: String) { see(text); rule.onAllNodesWithText(text, substring = true).onFirst().performScrollTo().performClick() }
    private fun tapLast(text: String) { see(text); rule.onAllNodesWithText(text).onLast().performScrollTo().performClick() }  // Home: the course row, not the session line
    private fun tab(text: String) = rule.onNode(hasText(text) and hasClickAction()).performClick()
    private fun back() = rule.onNodeWithContentDescription("Back").performClick()

    private fun signIn() = runBlocking {
        app.store = Store(app, object : Sealer { override fun seal(s: String) = s; override fun open(s: String) = s })  // Robolectric has no Android Keystore
        app.api = Api(app.store) { app.signedOut.value++ }
        app.store.server = System.getProperty("screens.server")!!; app.store.wallpaper = false
        val r = app.api.send("POST", "/login", buildJsonObject { put("email", "stu@mail.com"); put("password", "pw123456") }, LoginOut.serializer())
        app.store.token = r.token; app.store.userJson = json.encodeToString(Me.serializer(), r.user)
    }

    /** a week into using it: a routine, a bookmark, highlights in a few colours (one with a note) and a passed quiz. Safe to run twice. */
    private fun seed() = runBlocking {
        val a = app.api
        val chem = a.get("/tree", ListSerializer(ProgramNode.serializer())).flatMap { p -> p.semesters.flatMap { it.courses } }.first { it.name == "Engineering Chemistry" }
        val water = chem.units.first(); val t = water.topics.first(); val q = water.quizzes.first()
        a.raw("PUT", "/me/routine", buildJsonObject { put("days", "1111111"); put("minutes", 30); put("at", "19:30") })
        a.raw("PUT", "/topics/${t.id}/bookmark")
        if (a.get("/topics/${t.id}/highlights", Highlights.serializer()).items.isEmpty()) {
            for ((text, color) in listOf("hard water" to "yellow", "calcium" to "green", "Boilers scale up" to "coral", "Ion exchange, lime-soda" to "blue")) {
                val h = a.raw("POST", "/topics/${t.id}/highlights", buildJsonObject { put("text", text); put("prefix", ""); put("color", color) })
                if (color == "yellow") a.raw("PATCH", "/me/highlights/${(h as kotlinx.serialization.json.JsonObject)["id"]}", buildJsonObject { put("note", "Remember: soap won't lather") })
            }
        }
        if (a.get("/quizzes/${q.id}", Quiz.serializer()).attempts == 0)
            a.raw("POST", "/quizzes/${q.id}/attempt", buildJsonObject { put("answers", JsonArray(listOf(JsonPrimitive(1), JsonPrimitive(1)))) })
    }

    @Test fun english() {
        signIn(); seed()
        rule.setContent { ZigoraRoot(null) {} }
        see("Today's session"); see("Engineering Chemistry"); shot("home")
        tapLast("Engineering Chemistry"); see("Hardness of Water"); shot("course")
        tap("Hardness of Water"); see("The gist"); shot("topic")
        tap("Why?"); see("calcium bicarbonate breaks down"); shot("step")
        back(); tap("Revision sheet"); see("Ask yourself"); shot("revision"); back()
        tap("Water Technology quiz"); see("Which salts")
        tap("Bicarbonates"); tap("Calcium carbonate"); tap("Submit answers"); see("2 / 2"); shot("quiz")
        tap("Review answers"); see("Your answer"); shot("attempt"); back(); back(); back()
        tab("Saved"); tap("Highlights"); see("soap won't lather"); shot("highlights")
        tab("Progress"); see("Study routine"); tap("Scores"); see("Final score"); shot("progress")
        tab("Courses"); tap("Build a course"); see("Thermodynamics notes"); shot("build")
        tap("Thermodynamics notes"); see("The zeroth law"); shot("own-course")
    }

    /** MCQ practice: a set from the bank, four right and one to revise */
    @Test fun practice() {
        signIn()
        rule.setContent { ZigoraRoot(null) {} }
        tap("MCQ practice"); see("5 published questions"); shot("mcq-home")
        tap("Questions from the bank"); see("Question 1")
        tap("Hard water"); tap("Heating to a boil"); shot("mcq-set")
        tap("Chlorides and sulphates"); tap("Saves fuel"); tap("Calcium salts")
        tap("Submit answers"); runCatching { rule.waitUntilAtLeastOneExists(hasText("Submit with", substring = true), 3_000); rule.onAllNodesWithText("Submit").onFirst().performClick() }
        see("/ 5"); see("Correct answer"); shot("mcq-result")
    }

    /** the sign-in screen with Sign in with Google under the password (Google's own account sheet can't open in a test) */
    @Test fun signInScreen() {
        app.store = Store(app, object : Sealer { override fun seal(s: String) = s; override fun open(s: String) = s })
        app.api = Api(app.store) { app.signedOut.value++ }
        app.store.server = System.getProperty("screens.server")!!; app.store.wallpaper = false
        rule.setContent { ZigoraRoot(null) {} }
        see("Sign in with Google"); shot("signin")
    }

    @Config(qualifiers = "ta-w390dp-h844dp-xxhdpi")
    @Test fun tamil() = inOtherLanguage("ta")

    @Config(qualifiers = "ar-w390dp-h844dp-xxhdpi")
    @Test fun arabic() = inOtherLanguage("ar")

    /** Home and a topic in the app's other languages (courses and topics are the college's own names, the same in every language) */
    private fun inOtherLanguage(l: String) {
        signIn(); seed()
        rule.setContent { ZigoraRoot(null) {} }
        see("Engineering Chemistry"); shot("home-$l")
        tapLast("Engineering Chemistry"); see("Hardness of Water"); tap("Hardness of Water"); see("calcium and magnesium"); shot("topic-$l")
    }
}
