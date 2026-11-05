plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.cyber.warframeprofile"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.cyber.warframeprofile"
        minSdk = 26
        targetSdk = 34
        versionCode = 4
        versionName = "1.3"
        // Python 3.12 no Chaquopy não tem 32 bits; celulares atuais são arm64
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
    }

    // Chave fixa: todo build sai com a mesma assinatura, então o APK novo instala POR CIMA do antigo
    // (sem perder o lastData salvo no app).
    signingConfigs {
        create("fixa") {
            storeFile = file("signing.keystore")
            storePassword = "wfprofile123"
            keyAlias = "wfprofile"
            keyPassword = "wfprofile123"
        }
    }

    buildTypes {
        debug { signingConfig = signingConfigs.getByName("fixa") }
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("fixa")
        }
    }

    buildFeatures { buildConfig = true }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin { jvmToolchain(17) }

chaquopy {
    defaultConfig {
        version = "3.12"
        pip {
            install("pycryptodome")   // descriptografar o lastData.dat
        }
    }
}
