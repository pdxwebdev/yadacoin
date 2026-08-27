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
