package app.zigora.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.core.content.edit
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** how the sign-in is sealed at rest */
interface Sealer { fun seal(s: String): String; fun open(s: String): String }

/** The server's address and the sign-in. The sign-in is encrypted with a key that lives in the phone's Android Keystore and never leaves it. */
class Store(context: Context, private val sealer: Sealer = Keystore) {
    private val prefs = context.getSharedPreferences("zigora", Context.MODE_PRIVATE)

    var server: String
        get() = prefs.getString("server", null).orEmpty()
        set(v) = prefs.edit { putString("server", v) }

    var token: String?
        get() = prefs.getString("token", null)?.let { runCatching { sealer.open(it) }.getOrNull() }
        set(v) = prefs.edit { if (v == null) remove("token") else putString("token", sealer.seal(v)) }

    var userJson: String?
        get() = prefs.getString("user", null)
        set(v) = prefs.edit { putString("user", v) }

    /** a quiet daily note about deadlines and tests, only when the student turns it on */
    var reminders: Boolean
        get() = prefs.getBoolean("reminders", false)
        set(v) = prefs.edit { putBoolean("reminders", v) }

    /** Material You colours from the wallpaper, or Zigora's own */
    var wallpaper: Boolean
        get() = prefs.getBoolean("wallpaper", true)
        set(v) = prefs.edit { putBoolean("wallpaper", v) }

    /** the college's name for the app, as its server calls it (the web's header shows the same) */
    var appName: String
        get() = prefs.getString("app_name", null) ?: "Zigora"
        set(v) = prefs.edit { putString("app_name", v) }

    /** Auto (the phone's setting), light or dark, as on the web */
    var theme: String
        get() = prefs.getString("theme", "system") ?: "system"
        set(v) = prefs.edit { putString("theme", v) }

    /** the reminder keys already shown, so each deadline is mentioned once */
    var notified: Set<String>
        get() = prefs.getStringSet("notified", emptySet()).orEmpty()
        set(v) = prefs.edit { putStringSet("notified", v) }

    var recallHiddenOn: String
        get() = prefs.getString("recall_off", null).orEmpty()
        set(v) = prefs.edit { putString("recall_off", v) }

    fun signOut() = prefs.edit { remove("token").remove("user") }
}

/** AES-GCM with a key made inside the Android Keystore */
object Keystore : Sealer {
    private const val ALIAS = "zigora-signin"
    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getEntry(ALIAS, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    override fun seal(s: String): String {
        val c = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        return Base64.encodeToString(c.iv + c.doFinal(s.toByteArray()), Base64.NO_WRAP)
    }
    override fun open(s: String): String {
        val b = Base64.decode(s, Base64.NO_WRAP)
        val c = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, b, 0, 12)) }
        return String(c.doFinal(b, 12, b.size - 12))
    }
}
