# Native apps (Capacitor)

Same pattern as **web harness ↔ browser extension**:

| App | Package | Role | Deep link |
|-----|---------|------|-----------|
| **Yada Password** | `apps/password-native` | Vault + signs rotations | `yadapass://` |
| **Yada Auth Demo** | `apps/demo-native` | Test harness / demo login | `yadademo://` |

Demo never holds seed or site passwords. It opens the password manager; the manager
calls `POST /password-rotation/verify` (server-enforced rotate) and returns via
`yadademo://result?...`.

```
Demo                         Password manager                     Node
 |  yadapass://signin?... ->  |                                    |
 |                            |  user Approves                     |
 |                            |  POST /password-rotation/verify -> |
 |                            |  <- ok + rotated                   |
 |  <- yadademo://result?...  |                                    |
```

Demo site id (branch_peer): `yadademo://app`

## Prerequisites

- Node 18+
- Xcode 15+ **or** Android Studio
- For iOS pods: a modern CocoaPods (not system Ruby 2.0). Example:
  ```bash
  brew install cocoapods
  # ensure `which pod` is Homebrew, not ~/.rvm ... ruby-2.0
  ```
- Running YadaCoin node with `passwordrotation` plugin (`web` in modes)

## Build JS bundles

```bash
cd clients/password-manager
npm install
npm run build:native
# or: ./scripts/setup-native.sh
```

## Android (recommended on this machine)

```bash
cd clients/password-manager/apps/password-native
npx cap sync android
npx cap open android
# Android Studio → Run on emulator/device

cd ../demo-native
npx cap sync android
npx cap open android
# Run on the SAME emulator/device
```

Deep-link intent filters and cleartext LAN HTTP are already in each
`AndroidManifest.xml`.

## iOS

URL schemes are already in each `ios/App/App/Info.plist` (`yadapass` /
`yadademo`, ATS local networking allowed).

```bash
cd clients/password-manager/apps/password-native
npx cap sync ios
npx cap open ios
# Xcode → Signing team → Run

cd ../demo-native
npx cap sync ios
npx cap open ios
```

If `pod install` fails with old Ruby/OpenSSL, install CocoaPods via Homebrew
and re-run `npx cap sync ios`.

## Demo flow

1. **Yada Password** → Vault tab → generate seed → username + master password →
   **Save vault** → Node URL = `http://<mac-lan-ip>:<serve_port>` →
   **Broadcast inception**.
2. **Yada Auth Demo** → set the same Node URL (tip display) →
   **Register via Password app** → switch to Password → **Approve**.
3. Demo shows tip registered / counter.
4. **Sign in & rotate via Password app** → Approve → counter advances.
5. Repeat sign-in; each success consumes the prior password (backend enforces).

## Dev without a device

Web fallback (no real app switch):

```bash
# serve password manager www
cd clients/password-manager/apps/password-native/www && python3 -m http.server 5180

# serve demo www
cd clients/password-manager/apps/demo-native/www && python3 -m http.server 5181
```

Deep links won’t hop apps in desktop browsers; use Android/iOS for the full flow.

## After code changes

```bash
cd clients/password-manager
npm run build:native
cd apps/password-native && npx cap sync
cd ../demo-native && npx cap sync
# then rebuild/run from Android Studio or Xcode
```

## Android Studio: "Incompatible JVM" / select JVM 17

Capacitor 6 + AGP 8.2 need **JDK 17**. This machine already has:

```
/Users/matt.vogel/Library/Java/JavaVirtualMachines/jbr-17.0.14/Contents/Home
```

Both Android projects pin Gradle to that JDK via `android/gradle.properties`
(`org.gradle.java.home=...`) and `compileOptions` Java 17.

In Android Studio, if prompted:

1. **File → Settings → Build, Execution, Deployment → Build Tools → Gradle**
2. **Gradle JDK** → pick **jbr-17** (or “Embedded JDK” if it’s 17)
3. **File → Sync Project with Gradle Files**

Or from the banner: choose **JVM 17** / `jbr-17.0.14`.

Do **not** use JDK 21+ as the Gradle JVM for these projects unless you also
upgrade AGP.

Verify from terminal:

```bash
export JAVA_HOME=/Users/matt.vogel/Library/Java/JavaVirtualMachines/jbr-17.0.14/Contents/Home
cd clients/password-manager/apps/password-native/android
./gradlew assembleDebug
```
