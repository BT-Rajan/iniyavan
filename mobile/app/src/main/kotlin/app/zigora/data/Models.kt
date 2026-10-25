package app.zigora.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

// The shapes the server sends. Only what the app shows is read; anything new the server adds is ignored.

@Serializable data class Config(val name: String = "Zigora", val self_registration: Boolean = false, val email_reset: Boolean = false, val version: String? = null)
@Serializable data class Me(val id: Int, val name: String, val role: String, val must_change: Boolean = false, val self_registered: Boolean = false, val placed: Boolean = true, val lang: String = "en")
@Serializable data class Msg(val message: String = "", val ok: Boolean = true)
@Serializable data class RegStatus(val open: Boolean = false, val domains: List<String> = emptyList())
@Serializable data class LoginOut(val token: String, val user: Me)

@Serializable data class QuizRef(val id: Int, val title: String, val published: Boolean = true, val questions: Int = 0, val best: Int? = null, val pass_percent: Int = 50)
@Serializable data class TopicRef(val id: Int, val title: String, val status: String = "not_started", val bookmarked: Boolean = false, val archived: Boolean = false,
                                  val learning_due_at: String? = null, val overdue: Boolean = false, val has_notes: Boolean = false)
@Serializable data class UnitNode(val id: Int, val name: String, val archived: Boolean = false, val topics: List<TopicRef> = emptyList(), val quizzes: List<QuizRef> = emptyList())
@Serializable data class CourseNode(val id: Int, val name: String, val archived: Boolean = false, val units: List<UnitNode> = emptyList(), val tests: List<QuizRef> = emptyList())
@Serializable data class SemesterNode(val id: Int, val name: String, val current: Boolean = false, val courses: List<CourseNode> = emptyList())
@Serializable data class ProgramNode(val id: Int, val name: String, val semesters: List<SemesterNode> = emptyList())

@Serializable data class Focus(val kind: String, val title: String, val reason: String = "", val course: String = "", val unit: String = "", val topic_id: Int? = null, val quiz_id: Int? = null)
@Serializable data class Today(val streak: Int = 0, val percent: Int = 0, val topics_total: Int = 0, val topics_completed: Int = 0, val focus: List<Focus> = emptyList())
@Serializable data class RecallItem(val topic_id: Int, val title: String, val question: String, val answer: String)
@Serializable data class Recall(val item: RecallItem? = null)

@Serializable data class Nav(val prev: NavTopic? = null, val next: NavTopic? = null, val position: Int? = null, val total: Int = 0)
@Serializable data class NavTopic(val id: Int, val title: String)
@Serializable data class TopicFull(val id: Int, val title: String, val course: String = "", val unit: String = "", val semester: String = "", val program: String = "",
                                   val content: String? = null, val content_format: String = "markdown", val question_pattern: String? = null, val guideline: String? = null,
                                   val my_notes: String? = null, val frame_url: String? = null, val status: String = "not_started", val learning_due_at: String? = null,
                                   val bookmarked: Boolean = false, val nav: Nav? = null)
@Serializable data class Learning(val status: String = "not_started")
@Serializable data class AiStatus(val available: Boolean = false, val own_key: Boolean = false, val vision: Boolean = false, val ocr: Boolean = false, val plan: String = "college")
@Serializable data class You(val order: List<String> = emptyList(), val question_first: Boolean = false, val level: String? = null)
/** a topic step: the gist, why, example, exam angle, quick check or "more simply". data holds the step's own JSON */
@Serializable data class Step(val text: String = "", val cached: Boolean = false, val id: Int? = null, val data: JsonObject? = null, val you: You? = null, val own_notes: Boolean = false)
@Serializable data class Translation(val content: String, val format: String = "markdown")
@Serializable data class Bookmarked(val bookmarked: Boolean)

@Serializable data class Hit(val id: Int, val title: String, val unit: String = "", val course: String = "", val snippet: String = "", val in_title: Boolean = false)
@Serializable data class SearchOut(val q: String = "", val results: List<Hit> = emptyList(), val confident: Boolean = false)
@Serializable data class Answer(val text: String, val cached: Boolean = false, val support: Boolean = false, val via: String? = null)
@Serializable data class PhotoText(val text: String = "", val ocr: Boolean = false)

@Serializable data class Question(val id: Int, val text: String, val options: List<String>, val image: String = "", val option_images: List<String> = emptyList())
@Serializable data class Quiz(val id: Int, val title: String, val pass_percent: Int = 50, val course: String = "", val questions: List<Question> = emptyList(), val attempts: Int = 0, val best: Int? = null)
@Serializable data class QResult(val chosen: Int? = null, val ok: Boolean = false, val correct: Int? = null, val explanation: String? = null)
@Serializable data class AttemptOut(val score: Int, val total: Int, val percent: Int, val passed: Boolean, val pass_percent: Int, val reveal: Boolean = false, val results: List<QResult> = emptyList())

@Serializable data class Shared(val source: String, val label: String, val uses: Int)
@Serializable data class Rewards(val uses: Int = 0, val points: Int = 0, val toward_next: Int = 0, val per: Int = 1000, val points_per: Int = 100, val top: List<Shared> = emptyList())
/** a self-registered person's AI plan: lite (a free daily allowance on the college's key), own (their own key) or pro (given by the admin until a date) */
@Serializable data class AiPlan(val plan: String = "college", val pro_until: String? = null, val searches_used: Int = 0, val searches_limit: Int = 0,
                                val minutes_used: Int = 0, val minutes_limit: Int = 0, val asked: Boolean = false)
@Serializable data class Profile(val name: String, val email: String, val role: String, val lang: String = "en", val program: String = "", val semester: Int? = null, val term: String = "",
                                 val self_registered: Boolean = false, val ai: AiPlan? = null, val rewards: Rewards? = null)
@Serializable data class Note(val key: String, val text: String, val sub: String = "", val unread: Boolean = false)
@Serializable data class Notes(val items: List<Note> = emptyList(), val digest: Boolean = false, val mail: Boolean = false)
@Serializable data class KeyState(val own_key: Boolean = false, val key_set: Boolean = false, val key_hint: String = "")
@Serializable data class AndroidRelease(val version: String? = null, val code: Int? = null, val date: String? = null, val url: String? = null)
