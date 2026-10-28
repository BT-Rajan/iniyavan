plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

// The release workflow passes the version (from the number of commits that changed mobile/), the default server and the signing key.
val versionCodeProp = (findProperty("zigoraVersionCode") as String?)?.toIntOrNull() ?: 1
val versionNameProp = (findProperty("zigoraVersionName") as String?) ?: "1.0-dev"
val defaultServer = (findProperty("zigoraServer") as String?).orEmpty()
val keystore = System.getenv("ZIGORA_KEYSTORE")?.takeIf { it.isNotBlank() }?.let { file(it) }?.takeIf { it.exists() } // empty until the key is set up

android {
    namespace = "app.zigora"
    compileSdk = 37

    defaultConfig {
        applicationId = "app.zigora"
        minSdk = 33 // Android 13
        targetSdk = 37
        versionCode = versionCodeProp
        versionName = versionNameProp
        buildConfigField("String", "DEFAULT_SERVER", "\"$defaultServer\"")
    }

    signingConfigs {
        if (keystore != null) create("release") {
            storeFile = keystore
            storePassword = System.getenv("ZIGORA_KEYSTORE_PASSWORD")
            keyAlias = System.getenv("ZIGORA_KEY_ALIAS")
            keyPassword = System.getenv("ZIGORA_KEY_PASSWORD")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    androidResources { generateLocaleConfig = true } // Android 13's per-app language, from res/resources.properties
    lint {
        warningsAsErrors = false
        disable += setOf("NewerVersionAvailable", "GradleDependency", "AndroidGradlePluginVersion", // versions move on their own schedule
                        "PluralsCandidate") // counts like "3 of 10" follow the web app's wording
    }
    testOptions.unitTests.isIncludeAndroidResources = true
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}


dependencies {
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.compose.adaptive.nav)
    implementation(libs.compose.icons)
    implementation(libs.activity.compose)
    implementation(libs.core.ktx)
    implementation(libs.core.splashscreen)
    implementation(libs.lifecycle.viewmodel)
    implementation(libs.lifecycle.runtime)
    implementation(libs.navigation.compose)
    implementation(libs.work)
    implementation(libs.browser)
    implementation(libs.webkit)
    implementation(libs.okhttp)
    implementation(libs.serialization.json)
    implementation(libs.coil.compose)
    implementation(libs.coil.okhttp)
    implementation(libs.markdown.m3)
    implementation(libs.markdown.coil)
    implementation(libs.credentials)  // Sign in with Google, through Android's Credential Manager
    implementation(libs.credentials.play)
    implementation(libs.googleid)
    debugImplementation(libs.compose.ui.tooling)
    testImplementation(libs.junit)
    testImplementation(platform(libs.compose.bom))
    testImplementation(libs.robolectric)
    testImplementation(libs.roborazzi)
    testImplementation(libs.roborazzi.compose)
    testImplementation(libs.androidx.junit)
    testImplementation(libs.compose.ui.test)
    debugImplementation(libs.compose.ui.test.manifest)
}

// The screen tests (src/test/.../screens) drive the real screens against a running Zigora server and save screenshots to build/screens.
// They run only when asked: ./gradlew testDebugUnitTest -Pscreens -PscreensServer=http://127.0.0.1:5299
tasks.withType<Test>().configureEach {
    val screens = providers.gradleProperty("screens").isPresent
    if (!screens) exclude("**/screens/**")
    systemProperty("screens.server", providers.gradleProperty("screensServer").getOrElse("http://127.0.0.1:5299"))
    systemProperty("screens.out", layout.buildDirectory.dir("screens").get().asFile.absolutePath)
    systemProperty("robolectric.graphicsMode", "NATIVE")
    systemProperty("roborazzi.test.record", "true")
    providers.gradleProperty("robolectricRepo").orNull?.let { systemProperty("robolectric.dependency.repo.url", it) }
    outputs.upToDateWhen { !screens }
}

// The web app's dictionaries (locales/ar.json, ta.json) and the shapes of the server's sentences (srv.json) are packed into the app as they are,
// so server messages read the same in Arabic and Tamil on the phone as on the web. One source: frontend/src/locales.
androidComponents {
    onVariants { v ->
        v.sources.assets?.addStaticSourceDirectory(rootDir.resolve("../frontend/src/locales").canonicalPath)
        // the reader page (frontend/reader.html): the web's own renderer and highlighter, built by `npm run build:reader` in frontend/
        v.sources.assets?.addStaticSourceDirectory(rootDir.resolve("../frontend/dist-reader").canonicalPath)
    }
}

// the reader page must be built first; without it topics could not show their content
tasks.named("preBuild") {
    val readerPage = rootDir.resolve("../frontend/dist-reader/reader/reader.html")
    doFirst { check(readerPage.exists()) { "Build the reader page first: cd frontend && npm ci && npm run build:reader" } }
}
