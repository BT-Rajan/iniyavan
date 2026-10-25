package app.zigora

import android.content.res.Configuration
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.zigora.data.I18n
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

/** server sentences read the same on the phone as on the web: the same dictionaries and shapes (frontend/src/locales) */
@RunWith(AndroidJUnit4::class)
class I18nTest {
    @Config(sdk = [35], qualifiers = "ar")
    @Test fun serverSentencesAreTranslatedLikeTheWeb() {
        I18n.init(ApplicationProvider.getApplicationContext())
        assertEquals("Wrong email or password".let { I18n.srv(it) }.isNotEmpty(), true)
        val exact = I18n.srv("Wrong email or password"); assert(exact != "Wrong email or password") { exact }
        val shaped = I18n.srv("Best so far 40%, pass mark 50%"); assert(shaped.contains("40") && shaped.contains("50") && !shaped.startsWith("Best")) { shaped }
        assertEquals("Something nobody translated", I18n.srv("Something nobody translated"))
    }
    @Config(sdk = [35])
    @Test fun englishStaysAsItCame() {
        I18n.init(ApplicationProvider.getApplicationContext())
        assertEquals("Best so far 40%, pass mark 50%", I18n.srv("Best so far 40%, pass mark 50%"))
    }
}
