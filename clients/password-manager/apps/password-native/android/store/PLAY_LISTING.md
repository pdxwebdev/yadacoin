# Google Play listing — Yada Password

Copy these fields into Play Console → **Yada Password** (`io.yadacoin.passwordrotation`).

Graphics already in this folder:
- `play-icon-512.png` — high-res icon (512×512)
- `play-feature-graphic-1024x500.png` — feature graphic (1024×500)

You still need **phone screenshots** (min 2, max 8; 16:9 or 9:16; min short side 320px). Capture from an emulator or device after vault setup.

---

## App details

| Field | Value |
|--------|--------|
| **App name** | Yada Password |
| **Package name** | `io.yadacoin.passwordrotation` |
| **Default language** | English (United States) — `en-US` |
| **App category** | Tools (or Productivity) |
| **Tags** | password, security, identity, authentication |
| **Contact email** | *(your Play developer email)* |
| **Website** | https://yadacoin.io |
| **Privacy policy** | Host `privacy-policy.html` (this folder) at a public HTTPS URL, then paste that URL |

---

## Short description (max 80 characters)

```
Self-custody password vault with rotating site passwords via deep-link auth.
```

(78 characters)

---

## Full description (max 4000 characters)

```
Yada Password is a self-custody password manager and auth provider for the YadaCoin password-rotation protocol.

Your seed phrase and master password never leave the device. Site passwords are derived deterministically and rotate on each approved sign-in—so a stolen password is useless after the next successful login.

WHAT IT DOES
• Create a local vault from a BIP39 seed and master password
• Broadcast identity inception to your YadaCoin node
• Register sites and approve sign-in / rotate requests from other apps
• Verify calling Android apps (package + signing cert) before you approve
• Keep rotations in sync with your node

HOW AUTH WORKS
Other apps open Yada Password with yadapass:// deep links (register, sign-in, status). You review the request, confirm the caller, and approve. The app talks to your node to verify and rotate; the password callback returns only to the attested caller app.

PRIVACY BY DESIGN
• Seed and master password stay on-device
• No Yada account required inside the app
• You choose which node URL to use
• Internet is used only to reach the node you configure and to check Digital Asset Links / site association when verifying HTTPS callers

WHO IT’S FOR
Developers and early users integrating password rotation, and anyone who wants rotating site credentials without a cloud vault vendor holding the keys.

REQUIREMENTS
• A reachable YadaCoin node with the password-rotation plugin
• Android  compatible with the app’s min SDK

Open source components ship under YOSL-1.1. Learn more at https://yadacoin.io
```

---

## Release name (Play Console)

```
0.1.0
```

## Release notes — en-US (max 500 characters per language)

```
Initial public build of Yada Password.

• On-device vault (seed + master password)
• Identity inception to your YadaCoin node
• Deep-link register / sign-in / rotate (yadapass://)
• Android caller verification (package + cert pinning)
• Resync site rotations from the node

Internal testing track. Feedback welcome.
```

---

## Store settings checklist

- [ ] Create app in Play Console with package `io.yadacoin.passwordrotation`
- [ ] Upload high-res icon + feature graphic from this folder
- [ ] Add ≥2 phone screenshots
- [ ] Paste short + full description
- [ ] Set privacy policy URL (host `privacy-policy.html`)
- [ ] Complete Data safety (see `DATA_SAFETY.md`)
- [ ] Complete content rating questionnaire (see below)
- [ ] Target audience: 18+ recommended (security / crypto tooling)
- [ ] News app? **No**
- [ ] COVID-19 contact tracing / status? **No**
- [ ] Ads? **No**
- [ ] In-app purchases / paid? **No** (unless you change that)
- [ ] First AAB: build or tag release (see Ship section)

### Content rating (IARC) — expected answers

| Topic | Answer |
|--------|--------|
| Violence | No |
| Sexuality | No |
| Language | No |
| Controlled substances | No |
| Mature/horror themes | No |
| User-generated content | No (or minimal: user enters own vault data only) |
| Shares user location | No |
| Online interaction / unrestricted internet | Users may connect to a node URL they enter — treat as yes if asked about unrestricted web; app is not a social network |
| Age category result | Likely **Everyone** or **PEGI 3** / equivalent |

---

## Ship AAB (after listing exists)

Versions are currently **0.1.0** / versionCode **1** (or from tag).

**Option A — CI (preferred)**

```bash
# optional: commit version bump first
cd clients/password-manager && npm run set-version -- 0.1.0

git tag password-v0.1.0
git push origin password-v0.1.0
```

Workflow: `.github/workflows/password-release.yml`  
→ builds signed AABs for Yada Password and Yada Auth Demo → uploads Play track **internal**, status **draft**  
when secrets are set: `PASSWORD_ANDROID_*`, `PLAY_SERVICE_ACCOUNT_JSON`  
(packages `io.yadacoin.passwordrotation` and `io.yadacoin.passwordrotation.demo`).

**Option B — local**

```bash
cd clients/password-manager
npm ci && npm run build:password-native
cd apps/password-native && npx cap sync android
cd android
export ANDROID_VERSION_NAME=0.1.0
export ANDROID_VERSION_CODE=1
export ANDROID_KEYSTORE_PATH=/path/to/release.jks
export ANDROID_KEYSTORE_PASSWORD=...
export ANDROID_KEY_ALIAS=...
export ANDROID_KEY_PASSWORD=...
./gradlew bundleRelease
# AAB: app/build/outputs/bundle/release/app-release.aab
```

Then Play Console → Testing → Internal testing → Create release → upload AAB → paste release notes above → Save (draft) → Review → Roll out to internal testers.
