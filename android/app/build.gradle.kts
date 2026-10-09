import java.util.Properties

plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

// Release signing: android/keystore.properties (gitignored) with storeFile, storePassword, keyAlias, keyPassword.
// Without that file the release is signed with the debug key: a fork still builds, but won't install over the official APK.
val keystoreFile = rootProject.file("keystore.properties")
val keystore = Properties().apply { if (keystoreFile.exists()) keystoreFile.inputStream().use { load(it) } }

android {
    namespace = "com.jackbots.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.jackbots.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 4
        versionName = "2.1"
        ndk { abiFilters += listOf("arm64-v8a") }
    }
    signingConfigs {
        if (keystoreFile.exists()) {
            create("release") {
                storeFile = rootProject.file(keystore.getProperty("storeFile"))
                storePassword = keystore.getProperty("storePassword")
                keyAlias = keystore.getProperty("keyAlias")
                keyPassword = keystore.getProperty("keyPassword")
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    sourceSets["main"].assets.srcDir(layout.buildDirectory.dir("generated/panel"))
}

// The panel (app/, web/, assets/, data/) is not duplicated in android/: it is copied from the repo root before the build.
val syncPanel by tasks.registering(Sync::class) {
    from(rootProject.projectDir.parentFile) {
        include("app/**", "web/**", "assets/**", "data/**")
        exclude("**/__pycache__/**")
    }
    into(layout.buildDirectory.dir("generated/panel/panel"))
}
tasks.named("preBuild") { dependsOn(syncPanel) }

chaquopy {
    defaultConfig {
        version = "3.13"  // the build needs Python 3.13 on PATH (python3.13 or py -3.13)
        pip {
            install("starlette")
            install("uvicorn")
            install("websockets")
            install("httpx")
            install("pillow")
        }
    }
}
