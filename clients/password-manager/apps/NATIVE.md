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


## Android caller verification

The `site` query param on `yadapass://` is attacker-controlled. Yada Password does
**not** trust it on Android.

1. `AuthRequestActivity` (standard launch) records the OS-attested caller:
   `PendingIntent.getCreatorPackage()` (demo attaches this extra), else
   `getLaunchedFromPackage()` (API 31+).
2. SHA-256 of the caller’s signing certs is read from PackageManager.
3. Policy (`verifyAndroidCaller`):
   - `android://<package>` — package must equal the OS caller
   - `https://…` — Digital Asset Links
     (`/.well-known/assetlinks.json`) must list that package + cert
   - custom scheme (e.g. `yadademo://app`) — callback scheme must match;
     first successful request **pins** package+certs (TOFU)
4. Later requests for the same site fail if package or certs don’t match the pin.
5. The password callback is opened with `Intent.setPackage(caller)` so another
   app that also registered the callback scheme cannot intercept it.

Approve is disabled until the check passes. Web keeps the previous unverified
deep-link behavior.

## iOS caller verification

iOS does not expose another app’s code-signing certificate. The password app
records `UIApplication.OpenURLOptionsKey.sourceApplication` (bundle ID) when
`yadapass://` is opened and pins that bundle ID (TOFU).

- `ios://<bundle>` — bundle must equal the OS caller
- `https://…` — `apple-app-site-association` must list that bundle
- custom scheme — callback scheme must match; pin bundle ID

If `sourceApplication` is missing, the request is **not** verified and Approve
stays disabled. iOS cannot target a callback at a specific bundle (no
`setPackage`); the callback still uses the pinned scheme.

`npx cap sync` regenerates `packageClassList`; `npm run cap:sync` in each app
re-adds the local plugin class names.

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

## Android Studio: JDK 17

Capacitor 6 + AGP 8.2 need **JDK 17**. Do not pin `org.gradle.java.home` in
`gradle.properties` (that breaks CI and other machines). Set `JAVA_HOME` or
Android Studio’s Gradle JDK instead.

1. **File → Settings → Build, Execution, Deployment → Build Tools → Gradle**
2. **Gradle JDK** → JDK 17 (Temurin, jbr-17, or Android Studio Embedded JDK 17)
3. **File → Sync Project with Gradle Files**

Do **not** use JDK 21+ as the Gradle JVM unless you also upgrade AGP.

```bash
export JAVA_HOME="$(/usr/libexec/java_home -v 17 2>/dev/null || echo "$JAVA_HOME")"
cd clients/password-manager/apps/password-native/android
./gradlew assembleDebug
```
