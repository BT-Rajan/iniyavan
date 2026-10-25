package app.zigora

import app.zigora.data.CourseNode
import app.zigora.data.ProgramNode
import app.zigora.data.SemesterNode
import app.zigora.ui.coursesOf
import app.zigora.ui.firstName
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
}
