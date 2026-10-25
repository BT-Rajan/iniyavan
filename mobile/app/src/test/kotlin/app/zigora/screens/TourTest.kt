package app.zigora.screens

import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.zigora.ZigoraApp
import app.zigora.data.Api
import app.zigora.data.LoginOut
import app.zigora.data.Me
import app.zigora.data.ProgramNode
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
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** every student screen, with some saved work in it, at the text size many phones use (1.15), for a look at the whole app at once */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w393dp-h852dp-xxhdpi", fontScale = 1.15f)
class TourTest {
    @get:Rule val rule = createComposeRule()
    private val app get() = ApplicationProvider.getApplicationContext<ZigoraApp>()
    private val out = System.getProperty("screens.out")!! + "/tour"

    private fun shot(name: String) { rule.waitForIdle(); rule.onRoot().captureRoboImage("$out/$name.png") }
    private fun see(text: String) = rule.waitUntilAtLeastOneExists(hasText(text, substring = true), 20_000)
    private fun tap(text: String) { see(text); rule.onAllNodesWithText(text, substring = true).onFirst().performScrollTo().performClick() }
    private fun tab(text: String) = rule.onNode(hasText(text) and hasClickAction()).performClick()
    private fun back() = rule.onNodeWithContentDescription("Back").performClick()

    private fun seed() = runBlocking {  // a bookmark, a highlight and a quiz attempt, so Saved and My progress have something in them
        val a = app.api
        val tree = a.get("/tree", ListSerializer(ProgramNode.serializer()))
        val chem = tree.flatMap { p -> p.semesters.flatMap { it.courses } }.first { it.name == "Engineering Chemistry" }
        val water = chem.units.first(); val t = water.topics.first(); val q = water.quizzes.first()
        a.raw("PUT", "/topics/${t.id}/bookmark")
        runCatching { a.raw("POST", "/topics/${t.id}/highlights", buildJsonObject { put("text", "hard water"); put("prefix", ""); put("color", "yellow") }) }
        a.raw("POST", "/quizzes/${q.id}/attempt", buildJsonObject { put("answers", JsonArray(listOf(JsonPrimitive(1), JsonPrimitive(0)))) })
    }

    @Test fun tour() {
        app.store = Store(app, object : Sealer { override fun seal(s: String) = s; override fun open(s: String) = s })  // Robolectric has no Android Keystore
        app.api = Api(app.store) { app.signedOut.value++ }
        app.store.server = System.getProperty("screens.server")!!; app.store.wallpaper = false
        runBlocking {
            val r = app.api.send("POST", "/login", buildJsonObject { put("email", "stu@mail.com"); put("password", "pw123456") }, LoginOut.serializer())
            app.store.token = r.token; app.store.userJson = json.encodeToString(Me.serializer(), r.user)
        }
        seed()
        rule.setContent { ZigoraRoot(null) {} }
        see("Engineering Chemistry"); shot("01-home")
        tab("Courses"); see("Engineering Chemistry"); shot("02-courses")
        tap("Engineering Chemistry"); see("Hardness of Water"); shot("03-course")
        tap("Revision sheet"); see("Ask yourself"); shot("04-revision"); back()
        tap("Hardness of Water"); see("The gist"); shot("05-topic")
        back(); tap("Water Technology quiz"); see("Which salts"); shot("06-quiz"); back(); back()
        tab("Saved"); see("Hardness of Water"); shot("07-saved")
        tap("Highlights"); see("hard water"); shot("08-highlights")
        tab("Progress"); see("Study routine"); shot("09-progress")
        tap("Scores"); see("Final score"); shot("10-test-results")
        tap("Final score"); see("Water Technology quiz"); shot("11-score-course")
        tap("Water Technology quiz"); see("latest"); shot("12-attempts")
        rule.onAllNodesWithText("%", substring = true).onFirst().performClick(); see("Question 1"); shot("13-attempt")
        back(); back(); back()
        tap("Set or change your study days"); see("Minutes a session"); shot("14-routine"); back()
        tab("Me"); see("Settings"); shot("15-me")
        tab("Courses"); tap("Build a course"); see("Thermodynamics notes"); shot("16-build")
        tap("Thermodynamics notes"); see("The zeroth law"); shot("17-own-course")
        rule.onAllNodesWithText("The zeroth law").onFirst().performClick(); see("Check yourself"); shot("18-own-topic")
        back(); back(); back()
        tap("Engineering Chemistry"); see("Bring your own notes"); tap("Bring your own notes"); shot("19-material"); back(); back()
        tab("Home"); rule.onNodeWithContentDescription("Search").performClick(); shot("20-search")
    }
}
