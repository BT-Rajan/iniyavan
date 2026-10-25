package app.zigora.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import androidx.compose.material3.Typography
import app.zigora.R

val Plum = Color(0xFF722F99)
val Coral = Color(0xFFFF9292)
val Cream = Color(0xFFFEE7C8)

private val Light = lightColorScheme(
    primary = Plum, onPrimary = Color.White, primaryContainer = Color(0xFFF2DAFF), onPrimaryContainer = Color(0xFF2A1238),
    secondary = Color(0xFF8E4A5B), secondaryContainer = Color(0xFFFFD9DF), onSecondaryContainer = Color(0xFF3A0718),
    tertiary = Color(0xFF7A5900), tertiaryContainer = Cream, onTertiaryContainer = Color(0xFF261A00),
    background = Color(0xFFFBF9FC), surface = Color(0xFFFBF9FC), surfaceContainerLow = Color(0xFFF6F1F8), surfaceContainer = Color(0xFFF3EEF6),
    surfaceContainerHigh = Color(0xFFEDE7F0), onSurfaceVariant = Color(0xFF655B6E), outlineVariant = Color(0xFFE8E0EE),
)
private val Dark = darkColorScheme(
    primary = Color(0xFFDFB7FF), onPrimary = Color(0xFF45106A), primaryContainer = Color(0xFF5D2483), onPrimaryContainer = Color(0xFFF2DAFF),
    secondary = Color(0xFFFFB1C1), secondaryContainer = Color(0xFF72334A), tertiary = Color(0xFFF2C14F), tertiaryContainer = Color(0xFF5B4300),
    background = Color(0xFF120E17), surface = Color(0xFF120E17), surfaceContainerLow = Color(0xFF1B1522), surfaceContainer = Color(0xFF1F1826),
    surfaceContainerHigh = Color(0xFF251D2E), onSurfaceVariant = Color(0xFFA79DB0), outlineVariant = Color(0xFF322839),
)

/** the web's heading face (Instrument Sans) for headings and titles; body text and labels in the phone's own font, as the web does.
 *  One scale for every screen: screens pick a role from here and never set a size of their own. */
private val Heading = FontFamily(Font(R.font.instrument_sans_600, FontWeight.SemiBold), Font(R.font.instrument_sans_700, FontWeight.Bold))
private fun h(size: Int, line: Int, w: FontWeight = FontWeight.SemiBold) = TextStyle(fontFamily = Heading, fontWeight = w, fontSize = size.sp, lineHeight = line.sp, letterSpacing = (-0.01).em)
private fun b(size: Int, line: Int, w: FontWeight = FontWeight.Normal, track: Double = 0.0) = TextStyle(fontWeight = w, fontSize = size.sp, lineHeight = line.sp, letterSpacing = track.em)
val ZigoraType = Typography(
    displaySmall = h(32, 40, FontWeight.Bold), headlineLarge = h(28, 36, FontWeight.Bold), headlineMedium = h(26, 32), headlineSmall = h(22, 28),
    titleLarge = h(20, 26), titleMedium = h(17, 23), titleSmall = h(15, 20),
    bodyLarge = b(16, 24), bodyMedium = b(14, 20), bodySmall = b(12, 16),
    labelLarge = b(14, 20, FontWeight.Medium), labelMedium = b(12, 16, FontWeight.Medium, 0.01), labelSmall = b(11, 16, FontWeight.Medium, 0.02),
)

/** Material You: the phone's own wallpaper colours by default, or Zigora's plum when the student prefers it. Dark follows the system. */
@Composable
fun ZigoraTheme(wallpaper: Boolean, theme: String = "system", content: @Composable () -> Unit) {
    val dark = when (theme) { "light" -> false; "dark" -> true; else -> isSystemInDarkTheme() }; val ctx = LocalContext.current
    val scheme = when {
        wallpaper && dark -> dynamicDarkColorScheme(ctx)
        wallpaper -> dynamicLightColorScheme(ctx)
        dark -> Dark
        else -> Light
    }
    MaterialTheme(colorScheme = scheme, typography = ZigoraType, content = content)
}
