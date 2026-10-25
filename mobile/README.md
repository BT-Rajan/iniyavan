# Zigora for Android

A native Android app (Kotlin, Jetpack Compose, Material 3) for students, for **Android 13 (API 33) and later**. It uses the same API as the web app.

What it uses from Android: Material You colours from the wallpaper (or Zigora's purple), dark mode, edge-to-edge and predictive back, the splash screen,
a themed (monochrome) icon, the per-app language setting (English, Arabic right to left, Tamil), the photo picker and the camera, sharing a photo or text
into Zigora, "Zigora" in the text-selection menu of other apps, launcher shortcuts (Search, Photo), an adaptive layout for tablets, an optional quiet
daily notification (WorkManager), and the sign-in encrypted with a key in the Android Keystore (never backed up).

Screens: sign in (with the college's address), Home (where you left off, "Remember this?", courses), courses and units, a topic (the gist and the
steps, notes, Explain, sample answer, translation, "I've learned this"), quizzes, search with the AI, ask from a photo, notifications and Me (rewards,
language, colours, daily note, version and update). Teachers and admins keep using the web app.

## Releases

`.github/workflows/android.yml` builds the app on every change to `mobile/`. On `main`, and once a day, it publishes a GitHub release tagged
`android-v1.0.N` (N = the number of commits that changed `mobile/`) with `zigora-1.0.N.apk`, unless that version is already out. The Zigora server checks
GitHub for the newest release once a day (`GET /api/app/android`); the home page shows its version, date and a download button, and the app shows a
quiet "Version … is ready" note.

### One-time setup: the signing key

Releases need a signing key, kept in the repository's secrets. Every version must be signed with the same key, or phones refuse the update. Make it once,
on your own computer, and keep a copy somewhere safe:

```
keytool -genkeypair -v -keystore zigora.keystore -alias zigora -keyalg RSA -keysize 4096 -validity 10000
base64 -w0 zigora.keystore > zigora.keystore.b64
```

Then in GitHub: Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_B64` | the contents of `zigora.keystore.b64` |
| `ANDROID_KEYSTORE_PASSWORD` | the keystore password |
| `ANDROID_KEY_ALIAS` | `zigora` |
| `ANDROID_KEY_PASSWORD` | the key password (the same as the keystore's unless you chose another) |

Optional, under **Variables**: `ZIGORA_SERVER` = your server's address (for example `https://learn.yourcollege.edu`), so the app opens with it filled in.
Without the key the workflow still builds and checks the app, and keeps the APK as a download on the workflow run, but publishes nothing.
To publish right away instead of waiting for the daily run: Actions → Android → Run workflow.

Server settings (`backend/.env`): `ANDROID_REPO` is the GitHub repository whose releases carry the APK (default `BT-Rajan/iniyavan`; empty turns it off).

## Building it yourself

Android Studio, or: `cd mobile && ./gradlew assembleDebug` (needs JDK 17+ and the Android SDK). The screen tests drive the real screens against a running
Zigora server and save screenshots to `app/build/screens`: `./gradlew testDebugUnitTest -Pscreens -PscreensServer=http://127.0.0.1:5299`
(a student `stu@mail.com` / `pw123456` is expected). The app's words are in `app/src/main/res/values*/strings.xml`; change all three languages together.

Plain http is allowed (a college may not have https yet); the app says when an address is not secure.
