# MENACRAFT – Digital Sieve (Mobile)

Flutter Android app for real-time media verification and link analysis.

---

## Prerequisites

| Tool | Required version | Notes |
|------|-----------------|-------|
| Flutter | 3.41+ | Run `flutter upgrade` if older |
| Java JDK | 21 | JRE alone is not enough — install the **JDK** |
| Android SDK | API 36 | Platforms + Build-tools 34+ |
| Android NDK | 28.x | Auto-installed on first build |
| Android device | API 21+ (Android 5+) | USB debugging enabled |

---

## One-time machine setup

### 1. Install Java 21 JDK (Fedora/RHEL)

```bash
sudo dnf install -y java-21-openjdk-devel
```

Verify:
```bash
/usr/lib/jvm/java-21-openjdk/bin/javac -version
# javac 21.0.x
```

> **Why Java 21 specifically?**
> The system default may be Java 25, which the bundled Kotlin compiler inside Gradle cannot parse.
> Java 21 is the latest LTS that the full Flutter/Gradle/Kotlin toolchain supports.

### 2. Tell Flutter and Gradle to use Java 21

```bash
flutter config --jdk-dir /usr/lib/jvm/java-21-openjdk
```

This is already persisted in `android/gradle.properties`:
```properties
org.gradle.java.home=/usr/lib/jvm/java-21-openjdk
```

And register it with Gradle's toolchain resolver in `~/.gradle/gradle.properties`:
```properties
org.gradle.java.installations.paths=/usr/lib/jvm/java-21-openjdk
org.gradle.java.installations.auto-download=false
org.gradle.java.installations.auto-detect=false
```

### 3. Install Android SDK command-line tools

Download `commandlinetools-linux-*_latest.zip` from [developer.android.com/studio#command-line-tools-only](https://developer.android.com/studio/index.html) and install:

```bash
mkdir -p ~/Android/Sdk/cmdline-tools
unzip commandlinetools-linux-*_latest.zip -d /tmp/ct
mv /tmp/ct/cmdline-tools ~/Android/Sdk/cmdline-tools/latest
```

Accept SDK licenses:
```bash
yes | ~/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --licenses
```

### 4. Point Flutter at the Android SDK

```bash
flutter config --android-sdk ~/Android/Sdk
```

---

## Android device setup

1. **Enable Developer Options** on your phone:
   *Settings → About phone → tap Build number 7 times*

2. **Enable USB Debugging**:
   *Settings → Developer Options → USB Debugging → ON*

3. Connect via USB cable. When prompted on the phone, tap **Allow**.

4. Verify the device is visible:
   ```bash
   adb devices
   # Should show: <serial>  device
   ```

---

## Running the app

```bash
cd mobile

# Set Java 21 for this shell session
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk
export PATH=$JAVA_HOME/bin:$PATH

# Run on your connected device
flutter run -d <device-serial>
```

Get the device serial from `adb devices` or `flutter devices`.

---

## Build configuration explained

The project required several fixes to work with a modern Fedora system:

| File | What was changed | Why |
|------|-----------------|-----|
| `android/build.gradle` | `kotlin_version` → `2.1.0` | Flutter 3.41 requires KGP ≥ 1.8.10 |
| `android/build.gradle` | `gradle.projectsEvaluated` block | Forces all plugin Kotlin targets to JVM 17 (avoids "Unknown Kotlin JVM target: 21" from old plugins) |
| `android/settings.gradle` | AGP `8.7.0` → `8.7.3` | Patch release compatible with Flutter 3.41 Gradle plugin |
| `android/app/build.gradle` | `compileSdkVersion 34` → `36` | `flutter_plugin_android_lifecycle` requires SDK 36 |
| `android/gradle.properties` | `org.gradle.java.home` | Pins Gradle daemon to Java 21 JDK |
| `android/gradle.properties` | `kotlin.jvm.target.validation.mode=IGNORE` | Suppresses Kotlin/Java JVM target mismatch in third-party plugins |
| `~/.gradle/gradle.properties` | `java.installations.*` | Registers Java 21 JDK with Gradle's toolchain resolver |
| `pubspec.yaml` | `file_picker ^6` → `^8` | v6 pulls in `win32 5.2.0` which uses a removed Dart API |

---

## Troubleshooting

### `IllegalArgumentException: 25.0.2`
Gradle is running with Java 25 and the bundled Kotlin compiler can't parse its version string.
**Fix:** Set `JAVA_HOME=/usr/lib/jvm/java-21-openjdk` and ensure `org.gradle.java.home` is set in `android/gradle.properties`.

### `Toolchain installation does not provide JAVA_COMPILER`
Gradle's toolchain resolver can't verify the JDK — usually because the Red Hat OpenJDK `release` file is missing `IMAGE_TYPE=JDK`.
**Fix:** Set `org.gradle.java.installations.paths` and `org.gradle.java.installations.auto-detect=false` in `~/.gradle/gradle.properties`.

### `Unknown Kotlin JVM target: 21`
A third-party plugin uses an old Kotlin version that doesn't support JVM target 21.
**Fix:** The `gradle.projectsEvaluated` block in `android/build.gradle` overrides all Kotlin tasks to `jvmTarget = '17'`.

### `Error resolving plugin dev.flutter.flutter-plugin-loader > 25.0.2`
Flutter SDK is too old (pre-3.19) to work with the current `settings.gradle` format.
**Fix:** Run `flutter upgrade`.

### Device not detected by Flutter but visible in `adb devices`
Android SDK path not configured.
**Fix:** `flutter config --android-sdk ~/Android/Sdk`

---

## Project structure

```
mobile/
├── lib/
│   ├── main.dart               # App entry, theme (AppColors), overlay FAB, sharing intent
│   ├── ui/
│   │   ├── home_screen.dart    # Main screen: upload zone, history, ResultBottomSheet
│   │   └── overlay_widget.dart # Floating overlay bubble (collapsed + expanded states)
│   ├── services/
│   │   └── api_service.dart    # HTTP calls to the orchestrator backend
│   ├── models/
│   │   └── verification_result.dart
│   └── utils/
│       └── regex_extractor.dart
└── android/
    ├── app/build.gradle        # compileSdk 36, ndkVersion
    ├── build.gradle            # Kotlin 2.1.0, JVM target override for plugins
    ├── settings.gradle         # AGP 8.7.3, Flutter plugin loader
    └── gradle.properties       # Java 21 home, toolchain settings, Kotlin target validation
```
