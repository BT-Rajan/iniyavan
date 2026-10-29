package app.zigora

import app.zigora.data.CourseNode
import app.zigora.data.ProgramNode
import app.zigora.data.SemesterNode
import app.zigora.ui.coursesOf
import app.zigora.ui.firstName
import app.zigora.ui.serverCandidates
import org.junit.Assert.assertEquals
import org.junit.Test

class LogicTest {
    @Test fun aCourseShownInTwoSemestersIsListedOnceAndItsLivePlaceWins() {
        val live = CourseNode(7, "Chemistry"); val off = CourseNode(7, "Chemistry", archived = true)
        val tree = listOf(ProgramNode(1, "B.E.", listOf(SemesterNode(1, "S1", courses = listOf(off, CourseNode(8, "Maths"))), SemesterNode(2, "S2", courses = listOf(live)))))
        assertEquals(listOf(7, 8), coursesOf(tree).map { it.id })
        assertEquals(false, coursesOf(tree).first().archived)
    }
    @Test fun theGreetingUsesTheFirstName() {
        assertEquals("Meena", firstName("  Meena Kumar "))
        assertEquals("", firstName(""))
    }
    @Test fun aTypedAddressBecomesTheServersRoot() {
        assertEquals(listOf("https://169.58.13.213:5252", "http://169.58.13.213:5252"), serverCandidates(" 169.58.13.213:5252 "))
        assertEquals(listOf("http://169.58.13.213:5252"), serverCandidates("http://169.58.13.213:5252/app/#reset=x"))
        assertEquals(listOf("https://learn.college.edu", "http://learn.college.edu"), serverCandidates("learn.college.edu/app"))
        assertEquals(listOf("https://learn.college.edu"), serverCandidates("HTTPS://learn.college.edu/"))
        assertEquals(emptyList<String>(), serverCandidates("http://"))
        // a site under a folder of its address (BASE_PATH): the folder stays, the app's own part goes
        assertEquals(listOf("https://apps.perennia.org/zigora", "http://apps.perennia.org/zigora"), serverCandidates("apps.perennia.org/zigora"))
        assertEquals(listOf("https://apps.perennia.org/zigora"), serverCandidates("https://apps.perennia.org/zigora/app/#reset=x"))
        assertEquals(listOf("https://apps.perennia.org/zigora"), serverCandidates("https://apps.perennia.org/zigora/"))
        assertEquals(listOf("https://learn.college.edu/apps"), serverCandidates("https://learn.college.edu/apps"))  // only "app" itself is the app's part
    }
}
