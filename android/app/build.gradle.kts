import java.util.Properties

plugins {
    id("com.android.application")
    id("com.chaquo.python")
}

// Подпись релиза: android/keystore.properties (в .gitignore) с полями storeFile, storePassword, keyAlias, keyPassword.
// Без файла релиз подписывается debug-ключом — форк соберётся, но поверх официального APK не встанет.
val keystoreFile = rootProject.file("keystore.properties")
val keystore = Properties().apply { if (keystoreFile.exists()) keystoreFile.inputStream().use { load(it) } }

android {
    namespace = "com.jackbots.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.jackbots.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 3
        versionName = "2.0"
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

// Панель (app/, web/, assets/, data/) не дублируется в android/: перед сборкой копируется из корня репозитория.
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
        version = "3.13"  // для сборки нужен Python 3.13 в PATH (python3.13 или py -3.13)
        pip {
            install("starlette")
            install("uvicorn")
            install("websockets")
            install("httpx")
            install("pillow")
        }
    }
}
