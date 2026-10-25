package app.zigora.data

import android.content.Context
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive

/** The web app's way of showing what the server says in the reader's language (i18n.js srv): an exact sentence first, then the known
 *  shapes, with numbers and names carried into the translation. Anything else is shown as it came. Same files as the web. */
object I18n {
    private var ctx: Context? = null
    private val dicts = HashMap<String, Map<String, String>>()
    private val shapes by lazy {
        runCatching { (json.parseToJsonElement(read("srv.json")) as JsonArray).map { val a = it as JsonArray; Regex(a[0].jsonPrimitive.content) to a[1].jsonPrimitive.content } }.getOrDefault(emptyList())
    }
    private val terms = setOf("Semester", "Semesters", "Year", "Years", "Grade", "Grades", "Term", "Terms", "semester", "semesters", "year", "years", "grade", "grades", "term", "terms")

    fun init(c: Context) { ctx = c.applicationContext }
    /** the app's own words, from its string resources */
    fun str(id: Int): String = ctx?.getString(id).orEmpty()
    private fun read(name: String) = ctx!!.assets.open(name).bufferedReader().use { it.readText() }
    private fun lang() = ctx?.resources?.configuration?.locales?.get(0)?.language ?: "en"
    private fun dict(l: String): Map<String, String>? = if (l != "ar" && l != "ta") null else dicts.getOrPut(l) {
        runCatching { (json.parseToJsonElement(read("$l.json")) as JsonObject).mapValues { it.value.jsonPrimitive.content } }.getOrDefault(emptyMap())
    }

    /** a label in the reader's language, with {name} values filled in (term words like Semester are translated too) */
    fun t(key: String, vars: Map<String, String> = emptyMap()): String {
        val d = dict(lang()); val out = d?.get(key) ?: key
        return Regex("""\{(\w+)}""").replace(out) { m -> vars[m.groupValues[1]]?.let { v -> if (v in terms) t(v) else v } ?: m.value }
    }

    fun srv(s: String?): String {
        if (s.isNullOrEmpty()) return s.orEmpty()
        val d = dict(lang()) ?: return s
        d[s]?.let { return it }
        for ((re, key) in shapes) {
            val m = re.find(s) ?: continue
            if (d[key] == null) continue
            val names = Regex("""\(\?<(\w+)>""").findAll(re.pattern).map { it.groupValues[1] }.toList()
            return t(key, names.associateWith { n -> m.groups[n]?.value.orEmpty() })
        }
        return s
    }
}
