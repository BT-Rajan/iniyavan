package app.zigora

import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

/** Android's regex engine (ICU) refuses a brace that is neither escaped nor part of a {n,m} count, where desktop Java lets it through:
 *  such a pattern passes every test on a computer and crashes on a phone. Every pattern the app compiles is checked here. */
class RegexTest {
    private fun bare(p: String) = Regex("""(?<!\\)[{}]""").containsMatchIn(p.replace(Regex("""\\\\"""), "").replace(Regex("""\{\d+(,\d*)?\}"""), ""))

    @Test fun theAppsOwnPatternsHaveNoBareBraces() {
        val found = File("src/main/kotlin").walk().filter { it.extension == "kt" }.flatMap { f ->
            Regex("Regex\\(\"\"\"(.*?)\"\"\"").findAll(f.readText()).map { f.name to it.groupValues[1] }
        }.filter { bare(it.second) }.toList()
        assertEquals(emptyList<Pair<String, String>>(), found)
    }

    @Test fun theServersMessageShapesHaveNoBareBraces() {
        val shapes = (app.zigora.data.json.parseToJsonElement(File("../../frontend/src/locales/srv.json").readText()) as kotlinx.serialization.json.JsonArray)
            .map { ((it as kotlinx.serialization.json.JsonArray)[0] as kotlinx.serialization.json.JsonPrimitive).content }
        assert(shapes.isNotEmpty())
        assertEquals(emptyList<String>(), shapes.filter(::bare))
    }

    @Test fun theCheckCatchesTheCrash() {
        assert(bare("""\{(\w+)}""")); assert(!bare("""\{(\w+)\}""")); assert(!bare("""\d{2,4}"""))
    }
}
