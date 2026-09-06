# YadaCoin Password Manager (client-owned seed)

## Model

1. **Setup** — extension generates BIP39 seed; user enters master password (`second_factor`) + username
2. **Init** — client builds KEL **inception** with `IdentityAnnouncement`, signs with K0, `POST /transaction`
3. **Register site** — client builds **BranchAnnouncement** dual-commit on main KEL, then per-site off-chain ratchet
4. **Passwords** — generated **deterministically** from site branch key material; dual-commit hashes in off-chain unconfirmed `relationship`
5. **Rotate** — each use advances site ratchet 1:1 (key + password hashes)

Seed and second_factor **never** leave the device.

## Build

```bash
cd clients/password-manager
npm install
npm run build
```

Load `apps/extension/dist` in Chrome as unpacked extension.

## Node plugin

| Method | Path |
|--------|------|
| POST | `/transaction` (inception + branch) |
| POST | `/password-rotation/offchain` |
| GET | `/password-rotation/offchain/tip?branch_peer=` |
| GET | `/password-rotation/offchain-chain?branch_peer=` |
| GET | `/password-rotation/theme.json` |

## Derivation

Root matches node: `BIP32.fromEntropy(mnemonicToEntropy(mnemonic))`, not PBKDF2 mnemonicToSeed.

## Native apps (Capacitor)

See [apps/NATIVE.md](apps/NATIVE.md).

| App | Path | Deep link |
|-----|------|-----------|
| Yada Password | `apps/password-native` | `yadapass://` |
| Yada Auth Demo | `apps/demo-native` | `yadademo://` |

```bash
npm run build:native
cd apps/password-native && npx cap add ios && npx cap sync && npx cap open ios
cd ../demo-native && npx cap add ios && npx cap sync && npx cap open ios
```

## Store release

Push a tag `password-vX.Y.Z` (for example `password-v0.1.0`). GitHub Actions
builds the Chrome zip, Yada Password + Yada Auth Demo Android AABs and iOS IPAs,
attaches them to a GitHub Release, and uploads when secrets are present:

| Target | Package / app | Track | Secrets |
|--------|---------------|--------|---------|
| Chrome Web Store | extension | upload + submit for review | `CHROME_EXTENSION_ID`, `CHROME_CLIENT_ID`, `CHROME_CLIENT_SECRET`, `CHROME_REFRESH_TOKEN` |
| Google Play (Password) | `io.yadacoin.passwordrotation` | `internal`, status `draft` | `PASSWORD_ANDROID_KEYSTORE_*`, `PLAY_SERVICE_ACCOUNT_JSON` |
| Google Play (Auth Demo) | `io.yadacoin.passwordrotation.demo` | `internal`, status `draft` | same Android keystore + Play service account |
| App Store Connect (Password) | `io.yadacoin.passwordrotation` | TestFlight / processing | `BUILD_CERTIFICATE_BASE64`, `P12_PASSWORD`, `PASSWORD_BUILD_PROVISION_PROFILE_BASE64`, `PASSWORD_PROVISIONING_PROFILE_NAME`, `KEYCHAIN_PASSWORD`, `APPLE_TEAM_ID`, plus App Store Connect API key (or username/app-specific password) |
| App Store Connect (Auth Demo) | `io.yadacoin.passwordrotation.demo` | TestFlight / processing | same cert/team + `DEMO_BUILD_PROVISION_PROFILE_BASE64`, `DEMO_PROVISIONING_PROFILE_NAME` |

Create the store listings and first manual upload once. CI then ships updates.
Bump versions locally with `npm run set-version -- 1.2.3` before tagging if you
want the commit to match the tag (extension, password-native, and demo-native).
CI also applies the tag version at build time.

**Google Play listing copy, Data safety answers, privacy policy, graphics:**
`apps/password-native/android/store/` (`PLAY_LISTING.md`, `DATA_SAFETY.md`,
`privacy-policy.html`, `play-icon-512.png`, `play-feature-graphic-1024x500.png`).


