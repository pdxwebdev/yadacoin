# The `did:yadacoin` DID Method Specification

**Specification version:** 1.1-draft  
**Date:** 2026-05-01  
**Authors:** Matthew Vogel (YadaCoin)  
**Status:** Draft — intended for submission to the W3C DID Extensions Registry  
**Specification URL:** https://pdxwebdev.github.io/yadacoin/did-yadacoin-method-spec.html  
**Repository:** https://github.com/pdxwebdev/yadacoin

---

## Abstract

`did:yadacoin` is a decentralized identifier method anchored to the YadaCoin
blockchain. Each identifier maps to a compressed secp256k1 public key. The
corresponding DID Document is derived deterministically from that key's **Key
Event Log (KEL)** — a chain of version-7 blockchain transactions that record
key rotations, pre-rotation commitments, and optional relationship/scope data.
This method supports creation, resolution, key rotation (update), and
deactivation without any trusted registry beyond the YadaCoin peer-to-peer
network.

---

## 1. Introduction

YadaCoin is a proof-of-work blockchain whose transaction format natively
supports **pre-rotation key management**: each transaction commits a
cryptographic hash of the _next_ key before the current key is used, bounding
the damage from key compromise. The KEL mechanism is a blockchain-anchored
subset of [KERI](https://keri.one/) (Key Event Receipt Infrastructure).

`did:yadacoin` exposes this infrastructure through the W3C DID specification,
allowing any standard DID resolver to:

- Retrieve the active verification keys for a subject.
- Determine whether a key has been rotated or revoked.
- Read optional relationship / agent-authorization scope committed on-chain.

### 1.1 Design Goals

| Goal                 | How it is achieved                                                                                                                      |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Decentralization     | No registry, DNS, or third-party service required for resolution                                                                        |
| Key rotation         | Pre-rotation commitments bound on-chain before exposure                                                                                 |
| Revocation           | A key whose `public_key_hash` appears in the KEL is immediately revoked                                                                 |
| Minimal trust anchor | Proof-of-work blockchain; no permissioned validator set                                                                                 |
| Interoperability     | DIDs expressed as standard W3C DID URIs; DID Documents include `JsonWebKey2020` and `EcdsaSecp256k1VerificationKey2019` representations |

---

## 2. DID Method Name

The method name is: **`yadacoin`**

A `did:yadacoin` DID has the form:

```
did:yadacoin:<method-specific-id>
```

---

## 3. Method-Specific Identifier

### 3.1 Syntax

```abnf
did-yadacoin  = "did:yadacoin:" method-specific-id
method-specific-id = 66HEXDIG   ; 33-byte compressed secp256k1 public key, lowercase hex
HEXDIG        = DIGIT / "a" / "b" / "c" / "d" / "e" / "f"
DIGIT         = %x30-39
```

The method-specific identifier is the **66-character lowercase hexadecimal
encoding of a compressed secp256k1 public key** (33 bytes: a one-byte prefix
`02` or `03` followed by the 32-byte X coordinate).

### 3.2 Example DIDs

```
did:yadacoin:02a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2
did:yadacoin:03f1e2d3c4b5a6978869504132beef01234567890abcdef01234567890abcdef0102
```

### 3.3 Address Derivation

A **P2PKH address** is derived from a public key using the Bitcoin-compatible
procedure:

```
address = Base58Check( 0x00 || RIPEMD160( SHA256( compressed_public_key_bytes ) ) )
```

This address is used within the KEL as `public_key_hash`, `prerotated_key_hash`,
`twice_prerotated_key_hash`, and `prev_public_key_hash`.

---

## 4. Key Event Log (KEL)

The KEL is an ordered list of version-7 YadaCoin transactions associated with a
public key. Each entry records a key state transition.

### 4.1 KEL Entry Fields

| Field                       | Type   | Description                                                                         |
| --------------------------- | ------ | ----------------------------------------------------------------------------------- |
| `id`                        | string | Transaction identifier (hex)                                                        |
| `public_key`                | string | Compressed secp256k1 public key (hex) — the signer of this entry                    |
| `public_key_hash`           | string | P2PKH address of `public_key` — once this appears in the KEL the key is **revoked** |
| `prerotated_key_hash`       | string | P2PKH address of the **next** authorized signer                                     |
| `twice_prerotated_key_hash` | string | P2PKH address of the signer after next                                              |
| `prev_public_key_hash`      | string | P2PKH address of the previous signer (empty for inception)                          |
| `relationship`              | string | Base64-encoded UTF-8 JSON scope/relationship document (optional)                    |
| `transaction_signature`     | string | Signature over the serialized transaction by `public_key`                           |

### 4.2 Key Event Types

| Type            | Location            | Description                                                                                                                   |
| --------------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **Inception**   | On-chain            | First entry for a public key. No `prev_public_key_hash`. Single output to `prerotated_key_hash`. `relationship` MUST be `""`. |
| **Unconfirmed** | Mempool             | Rotation transaction that carries the optional scope/relationship. Always in mempool when active.                             |
| **Confirming**  | Mempool or on-chain | Countersigns the unconfirmed rotation. `relationship` is `""`. Once confirmed, the new key is the head of the KEL.            |

### 4.3 Chain Integrity Rules

1. `kel[n+1].prev_public_key_hash == kel[n].public_key_hash` for all n ≥ 0.
2. `kel[n+1].public_key` corresponds to the key whose P2PKH address equals `kel[n].prerotated_key_hash`.
3. A key is **revoked** if its P2PKH address appears as any `public_key_hash` in the KEL.
4. The **active key** is the `public_key` of `kel[-1]` (the latest confirming entry).

---

## 5. DID Document

### 5.1 Production Rules

A DID Document for `did:yadacoin:<pubkey_hex>` is produced as follows:

1. Resolve the KEL for `<pubkey_hex>` (see Section 6).
2. Determine the active key:
   - If the KEL is empty: the DID is unresolvable (not found).
   - If `addr(<pubkey_hex>)` appears as a `public_key_hash` in the KEL: the key is revoked — return a deactivated DID Document (see Section 8).
   - Otherwise: `<pubkey_hex>` is the active verification key.
3. Construct the DID Document as specified below.

### 5.2 DID Document Example

```json
{
  "@context": [
    "https://www.w3.org/ns/did/v1",
    "https://w3id.org/security/suites/secp256k1-2019/v1",
    "https://w3id.org/security/suites/jws-2020/v1"
  ],
  "id": "did:yadacoin:02a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
  "verificationMethod": [
    {
      "id": "did:yadacoin:02a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2#key-1",
      "type": "EcdsaSecp256k1VerificationKey2019",
      "controller": "did:yadacoin:02a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
      "publicKeyHex": "02a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2"
    },
    {
      "id": "did:yadacoin:02a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2#jws-key-1",
      "type": "JsonWebKey2020",
      "controller": "did:yadacoin:02a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
      "publicKeyJwk": {
        "kty": "EC",
        "crv": "secp256k1",
        "x": "<base64url-encoded X coordinate>",
        "y": "<base64url-encoded Y coordinate>"
      }
    }
  ],
  "authentication": [
    "did:yadacoin:02a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2#key-1"
  ],
  "assertionMethod": [
    "did:yadacoin:02a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2#key-1"
  ],
  "keyAgreement": [],
  "yadacoinKel": {
    "depth": 3,
    "headTransactionId": "abcdef0123456789...",
    "prerotatedKeyHash": "1BpEi6DfDAUFd152iiBFiEkioYCf...",
    "twicePrerotatedKeyHash": "1AXm5SomeDifferentAddress..."
  }
}
```

### 5.3 `yadacoinKel` Extension Property

The `yadacoinKel` property is a method-specific extension that exposes:

| Field                    | Description                                      |
| ------------------------ | ------------------------------------------------ |
| `depth`                  | Number of entries in the resolved KEL            |
| `headTransactionId`      | `id` field of the latest confirming KEL entry    |
| `prerotatedKeyHash`      | P2PKH address committed as the next signer       |
| `twicePrerotatedKeyHash` | P2PKH address committed as the signer after next |

Resolvers that do not understand `yadacoinKel` MUST ignore it.

### 5.4 `YadaKELStatus` — Method-Defined Credential Status Type

`did:yadacoin` defines a W3C Verifiable Credential status type,
`YadaKELStatus`, for use in the `credentialStatus` field of VCs committed
in the KEL `relationship` field. This type is registered in the
`https://yadacoin.io/contexts/agent-auth/v1` JSON-LD context.

```json
"credentialStatus": {
  "type": "YadaKELStatus",
  "mode": "rotation"
}
```

The `mode` field governs how a verifier interprets a key rotation in the
_holder's_ KEL when checking whether the VC is still valid:

| `mode`     | Revocation behaviour                                                                                                                                                                       |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `rotation` | **One-time-use.** If the holder's public key address appears as `public_key_hash` in any KEL entry the VC is considered revoked. Default if `mode` is absent.                              |
| `temporal` | **Persists across holder key rotations.** The revocation-by-rotation check is skipped. Verifiers MUST instead confirm the VP is signed with the holder's _current_ active key per the KEL. |

**Verifier algorithm (abridged)**

1. Locate the KEL entry `E` where `E.twice_prerotated_key_hash == addr(holder_key)`.
2. Decode `E.relationship` and read `credentialStatus.mode` (default `"rotation"`).
3. If `mode == "rotation"`: reject if `addr(holder_key)` appears as any `public_key_hash` in the KEL.
4. Regardless of mode: confirm `kel[-1].prerotated_key_hash == addr(holder_key)` — the VP MUST be signed with the current active key.

**Note on DID-level vs. VC-level revocation**: `YadaKELStatus` controls
VC validity, not DID Document state. At the DID level, a key that has
signed a rotation transaction is always deactivated (§5.1, §6.4). `temporal`
mode allows the _credential_ to remain valid even after the holder's DID has
cycled through key rotations, provided the VP is signed with the current
active key.

---

## 6. CRUD Operations

### 6.1 Create

To create a `did:yadacoin` DID:

1. Generate a compressed secp256k1 key pair `(K_0_private, K_0_public)`.
2. Pre-generate at least two additional key pairs `(K_1, K_2)` for pre-rotation.
3. Compute P2PKH addresses: `addr_0 = addr(K_0)`, `addr_1 = addr(K_1)`, `addr_2 = addr(K_2)`.
4. Construct and broadcast an **inception transaction** (version-7) to the YadaCoin network:

   | Field                       | Value                     |
   | --------------------------- | ------------------------- |
   | `public_key`                | `K_0` (hex)               |
   | `public_key_hash`           | `addr_0`                  |
   | `prerotated_key_hash`       | `addr_1`                  |
   | `twice_prerotated_key_hash` | `addr_2`                  |
   | `prev_public_key_hash`      | `""`                      |
   | `relationship`              | `""`                      |
   | outputs                     | single output to `addr_1` |

5. Once the inception transaction is confirmed on-chain, the DID
   `did:yadacoin:<K_0_hex>` is created and resolvable.

**Inception transaction MUST**:

- Have exactly one output, sent to `prerotated_key_hash`.
- Have `relationship == ""`.
- Have `prev_public_key_hash == ""`.

### 6.2 Read (Resolve)

To resolve `did:yadacoin:<pubkey_hex>`:

#### Option A — Public REST API

```
GET https://yadacoin.io/key-event-log?public_key=<pubkey_hex>
```

Returns a JSON array of KEL entries ordered from oldest to newest. Apply the
DID Document production rules in Section 5.1.

#### Option B — YadaCoin Python SDK

```python
from yadacoin.core.keyeventlog import KeyEventLog

kel = await KeyEventLog.build_from_public_key(pubkey_hex)
# kel is an ordered list of KeyEvent objects
```

#### DID Resolution Metadata

The resolver SHOULD return the following resolution metadata:

| Key           | Value                                                           |
| ------------- | --------------------------------------------------------------- |
| `contentType` | `"application/did+ld+json"`                                     |
| `retrieved`   | ISO 8601 timestamp of resolution                                |
| `error`       | `"notFound"` if KEL is empty; `"deactivated"` if key is revoked |

### 6.3 Update (Key Rotation)

To rotate the active key from `K_n` to `K_{n+1}`:

1. Pre-generate additional key pairs `K_{n+2}`, `K_{n+3}` as needed.
2. Broadcast an **unconfirmed rotation transaction** (signed by `K_n`):

   | Field                       | Value                                         |
   | --------------------------- | --------------------------------------------- |
   | `public_key`                | `K_n` (hex)                                   |
   | `public_key_hash`           | `addr(K_n)`                                   |
   | `prerotated_key_hash`       | `addr(K_{n+1})`                               |
   | `twice_prerotated_key_hash` | `addr(K_{n+2})`                               |
   | `prev_public_key_hash`      | `addr(K_{n-1})`                               |
   | `relationship`              | base64-encoded JSON scope document (optional) |
   | outputs                     | sent to `addr(K_{n+1})`                       |

3. Broadcast a **confirming rotation transaction** (signed by `K_{n+1}`):

   | Field                       | Value                   |
   | --------------------------- | ----------------------- |
   | `public_key`                | `K_{n+1}` (hex)         |
   | `public_key_hash`           | `addr(K_{n+1})`         |
   | `prerotated_key_hash`       | `addr(K_{n+2})`         |
   | `twice_prerotated_key_hash` | `addr(K_{n+3})`         |
   | `prev_public_key_hash`      | `addr(K_n)`             |
   | `relationship`              | `""`                    |
   | outputs                     | sent to `addr(K_{n+2})` |

After both transactions are accepted into the mempool (or confirmed on-chain),
resolving `did:yadacoin:<K_{n+1}_hex>` returns the updated DID Document. The old
DID `did:yadacoin:<K_n_hex>` resolves as revoked (deactivated).

> **Note**: Mempool transactions are sufficient for resolution. Services SHOULD
> check both mempool and on-chain entries to support agent credentials that have
> not yet been confirmed in a block.

### 6.4 Deactivate

To deactivate a DID, the current key holder broadcasts a final rotation
transaction that moves funds to a well-known **burn address** or to a dedicated
tombstone address with no corresponding private key. Once this transaction
appears in the KEL, the `public_key_hash` of the current key is present in the
KEL, rendering the DID resolved with `"deactivated": true` and an empty
`verificationMethod` array.

Alternatively, if the private key for the current active key is destroyed
without rotating, the DID becomes permanently unresolvable-as-active (the last
KEL entry remains, but no further updates are possible). This is equivalent to
abandonment rather than a formal deactivation.

#### Deactivated DID Document

```json
{
  "@context": ["https://www.w3.org/ns/did/v1"],
  "id": "did:yadacoin:<pubkey_hex>",
  "deactivated": true,
  "verificationMethod": [],
  "authentication": [],
  "assertionMethod": []
}
```

---

## 7. Security Considerations

### 7.1 Cryptographic Assumptions

This method relies on the security of secp256k1 ECDSA and the Bitcoin-compatible
P2PKH address scheme (SHA-256 + RIPEMD-160). Both are widely deployed and
peer-reviewed. Implementors SHOULD monitor NIST and IETF for guidance on
post-quantum migration paths.

### 7.2 Key Compromise Before Rotation

If the active key `K_n` is compromised before the unconfirmed rotation
transaction is broadcast, an attacker may attempt to rotate to a key they
control. The pre-rotation commitment (`prerotated_key_hash` in the previous KEL
entry) limits the scope of damage:

- The attacker must also know or derive the pre-committed `K_{n+1}` key.
- Because `K_{n+1}` was committed by hash _before_ the compromise, the attacker cannot substitute their own key.
- This is the core security property of pre-rotation: commitment precedes exposure.

### 7.3 Blockchain Finality

YadaCoin uses proof-of-work consensus. Transactions with fewer than 6
confirmations SHOULD be treated as tentative. High-value operations SHOULD
require more confirmations. Mempool-only transactions are accepted by this
method for agent credential use cases (see [KEL Agent Auth Spec](./kel_agent_auth_spec.md))
but SHOULD NOT be relied upon for high-value or irreversible operations.

### 7.4 51% Attack

A majority hash-rate attacker could in principle rewrite KEL history. The same
risk applies to all blockchain-anchored DID methods. Mitigations include:

- Requiring more confirmations (increasing finality depth).
- Cross-anchoring to a higher-hashrate chain.
- Using witness receipts (as in KERI) to provide non-blockchain corroboration.

### 7.5 Key Recovery

This method does not support social recovery or multi-signature inception. If
the active private key and all pre-rotated private keys are lost, the DID
cannot be updated or deactivated. Implementors SHOULD store key material using
hardware security modules (HSMs) or encrypted, redundant backups.

### 7.6 Replay Attacks

DID resolution is read-only; replay attacks do not directly apply. Applications
built on top of `did:yadacoin` (such as the KEL Agent Auth protocol) MUST
implement their own replay protection (e.g., time-windowed challenges).

### 7.7 Sybil Resistance

Creating a `did:yadacoin` DID requires broadcasting a transaction to the
YadaCoin network, which entails a transaction fee. This provides modest Sybil
resistance.

### 7.8 Method-Specific Extension Security

The `yadacoinKel` extension property in the DID Document is informational and
derived directly from on-chain data. Resolvers MUST NOT trust the extension
value over the raw KEL data returned by the resolution endpoint.

---

## 8. Privacy Considerations

### 8.1 Pseudonymity

`did:yadacoin` DIDs are pseudonymous. The method-specific identifier is a
compressed public key and does not directly expose personal information.
However, correlation of DIDs with on-chain transaction graphs, IP addresses, or
application-layer data may allow de-anonymization.

### 8.2 Correlation

All KEL entries and their `relationship` fields are publicly readable on-chain.
Implementors MUST NOT commit sensitive personal data in the `relationship`
field. Scope documents SHOULD contain only the minimum information necessary
for the intended authorization.

### 8.3 Personally Identifiable Information

The DID Document produced by this method does not include any PII. Application
protocols that include PII in associated Verifiable Credentials MUST apply
appropriate data minimization and purpose-limitation controls per applicable
privacy regulations (e.g., GDPR, CCPA).

### 8.4 Selective Disclosure

This method does not natively support selective disclosure of DID Document
attributes. Applications requiring selective disclosure SHOULD use Verifiable
Presentations with BBS+ or SD-JWT signatures over Verifiable Credentials rather
than exposing raw DID Documents.

### 8.5 Key Rotation and Unlinkability

Each key rotation creates a new DID (new public key = new DID). Parties wishing
to maintain unlinkability between interactions SHOULD use fresh DIDs for each
relationship, and SHOULD NOT reuse DIDs across contexts.

---

## 9. Verifiable Data Registry

The verifiable data registry for `did:yadacoin` is the **YadaCoin blockchain**
— a public, proof-of-work distributed ledger. The network is permissionless;
any node may participate in block production and validation.

- **Network:** YadaCoin mainnet
- **Block time:** approximately 10 minutes
- **Transaction version:** 7 (key event transactions)
- **Public node:** `https://yadacoin.io`
- **KEL lookup endpoint:** `GET https://yadacoin.io/key-event-log?public_key=<hex>`

---

## 10. Conformance

A conforming `did:yadacoin` resolver:

1. MUST implement the Read operation as specified in Section 6.2.
2. MUST return `"error": "notFound"` when the KEL is empty.
3. MUST return `"deactivated": true` when the resolved public key's address appears as a `public_key_hash` in the KEL.
4. MUST check both the confirmed blockchain and the mempool when building the KEL.
5. MUST apply chain integrity rules in Section 4.3 and discard invalid KEL entries.
6. MUST NOT require the `yadacoinKel` extension property to produce a valid DID Document.

A conforming `did:yadacoin` DID controller:

1. MUST use a compressed secp256k1 public key as the method-specific identifier.
2. MUST pre-generate at least two additional key pairs before broadcasting the inception transaction.
3. MUST NOT reuse a public key once its P2PKH address appears as a `public_key_hash` in the KEL.
4. SHOULD use low-S normalized ECDSA signatures in all transactions.

---

## 11. Reference Implementation

- **Blockchain node / SDK (Python):** https://github.com/pdxwebdev/yadacoin
  - `yadacoin.core.keyeventlog.KeyEventLog`
  - `yadacoin.core.identity.Identity`
  - `yadacoin.core.transaction.Transaction`
- **Agent auth SDK (Python):** `sdk/python/yadacoin_agent_auth.py`
- **Agent auth SDK (JavaScript):** `sdk/js/yadacoin-agent-auth.mjs`
- **Public resolver endpoint:** `https://yadacoin.io/key-event-log?public_key=<hex>`

---

## 12. Related Work

| Specification                                                     | Relationship                                                                                                     |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| [W3C DID Core 1.0](https://www.w3.org/TR/did-core/)               | This method conforms to the DID Core specification                                                               |
| [W3C VC Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/) | Scope documents use the VC 2.0 format                                                                            |
| [KERI](https://keri.one/) (IETF draft)                            | YadaCoin KEL is a blockchain-anchored subset of KERI pre-rotation semantics                                      |
| [did:ion](https://identity.foundation/ion/)                       | Similar blockchain-anchored key management; ION uses Bitcoin Sidetree                                            |
| [did:key](https://w3c-ccg.github.io/did-method-key/)              | Self-contained; no revocation; used for ephemeral keys in the agent auth protocol                                |
| [KEL Agent Auth Spec v1.2](./kel_agent_auth_spec.md)              | Application protocol built on top of `did:yadacoin` for AI agent authentication; v1.2 introduces `YadaKELStatus` |
| [RFC 9421](https://www.rfc-editor.org/rfc/rfc9421)                | HTTP Message Signatures; complementary authentication mechanism                                                  |

---

## 13. Revision History

| Version   | Date       | Changes                                                                                                                                          |
| --------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1.0-draft | 2026-05-01 | Initial draft for W3C CCG submission                                                                                                             |
| 1.1-draft | 2026-05-03 | Added §5.4 `YadaKELStatus` credential status type with `rotation` / `temporal` modes; updated Related Work to reference KEL Agent Auth Spec v1.2 |

---

_YadaCoin Open Source License (YOSL) v1.1 — Copyright © 2017-2025 Matthew Vogel, Inc._
