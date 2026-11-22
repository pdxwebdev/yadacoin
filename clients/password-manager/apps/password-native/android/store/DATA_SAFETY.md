# Google Play Data safety — Yada Password

Use these answers in Play Console → **App content** → **Data safety**.

Review against the live build before submit; this matches the Capacitor vault app as of the 0.1.0 codebase (Preferences storage, node HTTP, deep links, optional Asset Links fetch).

---

## Overview

| Question | Answer |
|----------|--------|
| Does your app collect or share any of the required user data types? | **Yes** (collected on device / processed; see types) |
| Is all user data encrypted in transit? | **Yes** when the user configures an **https://** node URL. If the user enters **http://** (e.g. LAN dev node), traffic is not encrypted — disclose that users should use HTTPS in production. |
| Do you provide a way for users to request that their data is deleted? | **Yes** — user can clear app data / uninstall; vault lives on device. No cloud account to delete at Yada. |

**Encryption at rest:** Android app sandbox + OS storage. No separate “encrypted vault file” claim beyond normal app private storage unless you add it later.

**Data deletion:** Uninstall or clear storage removes local vault. On-chain / node data (inception, tips) is controlled by the user’s node, not by a Yada Play “account.”

---

## Data collection & sharing

**Account / identity**

| Type | Collected? | Shared? | Ephemeral? | Required? | Purpose |
|------|------------|---------|------------|-----------|---------|
| Name | No | — | — | — | — |
| Email | No | — | — | — | — |
| User IDs | **Yes** (username string user enters for vault / identity) | **Yes** — sent to the **user-configured node** as part of identity / tx flow | No | Yes for core feature | App functionality |
| Address | No | — | — | — | — |

**Financial** — No (unless you later add payments).

**Health** — No.

**Messages** — No.

**Photos / video** — No.

**Audio** — No.

**Files / docs** — No.

**Calendar / contacts** — No.

**App activity**

| Type | Collected? | Shared? | Notes |
|------|------------|---------|--------|
| App interactions | Optional / No for Play “collection” | No | Local UI only |
| In-app search history | No | — | — |
| Installed apps | **Yes** (caller package name + signing cert hashes when handling `yadapass://`) | No (used on-device for verification; may be stored as site pin) | App functionality / security |
| Other user-generated content | **Yes** (seed phrase, master password, site passwords, node URL — **on device**) | Seed/master password **must not** be shared. Site password material and tx payloads go to **user’s node** on approve | App functionality |

**Web browsing** — No (not a browser).

**Location** — No.

**Device or other IDs**

| Type | Collected? | Shared? | Purpose |
|------|------------|---------|---------|
| Device ID | No (not advertising ID) | — | — |

**Caller package name + cert SHA-256** are security attestations, not advertising IDs. Map under **App activity → Installed apps** or **Device or other IDs** if Play forces a bucket; purpose: **Fraud prevention, security, and compliance** + **App functionality**.

---

## Sensitive: passwords & credentials

- **Seed phrase, master password, derived site passwords:** processed **on device**.
- **Shared with third parties?** Only the **user-chosen YadaCoin node** receives protocol payloads needed for inception / register / verify-rotate (e.g. password hashes, public key material, transactions)—**not** a Yada-operated backend unless the user points the node URL there.
- In Data safety, treat the node as a **third party** the user configures, or as “user-directed” transfer. Be accurate: you do not operate a mandatory cloud vault.

**Do not claim “no data collected”** — username, node URL, pins, and crypto payloads are user data.

---

## Data usage purposes (check as applicable)

- App functionality  
- Fraud prevention, security, and compliance  
- **Not:** Analytics, Advertising, Personalization, Developer communications (unless you add them)

---

## Sharing

| Shared? | With whom |
|---------|-----------|
| Yes (protocol data) | User-configured node operator (may be self-hosted) |
| No | Ad networks, data brokers, unrelated third parties |

---

## Security practices checklist (Play form)

- [x] Data is encrypted in transit (when using HTTPS node)
- [ ] Users can request deletion → **Yes** (local clear / uninstall; explain no central account)
- [ ] Independent security review → **No** (unless you have one)
- [ ] Committed to Play Families Policy → **No** (not a kids app)

---

## Privacy policy alignment

`privacy-policy.html` must match this form. If you add crash reporting, analytics, or accounts later, update both.
