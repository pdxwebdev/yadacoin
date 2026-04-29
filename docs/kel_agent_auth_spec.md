# YadaCoin KEL Agent Auth Protocol — Specification v1.0

## 1. Overview

The **YadaCoin KEL Agent Auth** protocol lets any third-party service authenticate
AI agents (or any automated caller) without the operator's private key ever leaving
the operator's device. Authority is delegated by committing a one-time agent key
on the YadaCoin blockchain, optionally with a structured scope document that binds
exactly what the agent is allowed to do. The service then authenticates the agent
via a stateless challenge-response and enforces the on-chain scope.

**Design goals**

| Goal                          | How it is achieved                                                                                              |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Private key never transmitted | Challenge is signed client-side; only the public key + signature reach the server                               |
| Forward secrecy               | Every agent credential is one-time-use; once spent it appears as a revoked entry in the KEL                     |
| Scope binding                 | The scope document is committed in a blockchain transaction before the request; it cannot be altered in transit |
| Stateless service             | The HMAC challenge is derived deterministically; the service keeps no session state                             |
| Third-party friendly          | The only YadaCoin dependency is a KEL lookup — either via the SDK or the public REST API                        |

---

## 2. Roles

| Role         | Description                                                      |
| ------------ | ---------------------------------------------------------------- |
| **Operator** | Human who owns the root key and approves agent actions           |
| **Agent**    | Automated process that holds a provisioned one-time key          |
| **Service**  | Third-party API endpoint that accepts KEL-authenticated requests |

---

## 3. Key Event Log (KEL)

A KEL is a chain of version-7 transactions on the YadaCoin network. Each entry:

| Field                          | Description                                                                         |
| ------------------------------ | ----------------------------------------------------------------------------------- |
| `public_key`                   | Compressed secp256k1 public key (hex) of the current signer                         |
| `public_key_hash`              | P2PKH address of `public_key` — once this appears in the KEL the key is **revoked** |
| `prerotated_key_hash`          | P2PKH address of the **next** authorised signer                                     |
| `twice_prerotated_key_hash`    | P2PKH address of the signer after next                                              |
| `relationship`                 | Base64-encoded scope document (optional)                                            |
| `id` / `transaction_signature` | Transaction identifier                                                              |

The chain guarantees that:

- Only the holder of the key pre-committed by `kel[-1].prerotated_key_hash` can act next.
- Any key that has signed a rotation transaction (`public_key_hash` appears in the KEL) is revoked.

---

## 4. Agent Provisioning

Before calling a service the operator must provision the agent key on-chain. This
is a one-time rotation transaction broadcast to the YadaCoin network.

```
┌─────────────────────────────────────────────────────────────┐
│  Rotation transaction (UNCONFIRMED + CONFIRMING pair)       │
│                                                             │
│  public_key            = K_{n}   (current signing key)     │
│  public_key_hash       = addr(K_{n})                       │
│  prerotated_key_hash   = addr(K_{n+1})  ← agent identity   │
│  twice_prerotated_key_hash = addr(K_{n+2})                  │
│  relationship          = base64(scope_json)                 │
└─────────────────────────────────────────────────────────────┘
```

After the transaction is broadcast (mempool is sufficient — services check
mempool + chain), `K_{n+1}` is the agent credential.

---

## 5. Scope Document

The `relationship` field MUST be a base64-encoded UTF-8 JSON object. Services
SHOULD define their own task-specific fields; unrecognised keys MUST be ignored.

**Common fields**

| Field                  | Type                   | Description                                          |
| ---------------------- | ---------------------- | ---------------------------------------------------- |
| `task`                 | string                 | Identifies the service type, e.g. `"travel_booking"` |
| `services`             | string[]               | Whitelist of allowed service names                   |
| `dest`                 | string                 | Destination (travel services)                        |
| `checkin` / `checkout` | string (ISO 8601 date) | Date range                                           |

**Example**

```json
{
  "task": "travel_booking",
  "dest": "New York City",
  "checkin": "2026-05-10",
  "checkout": "2026-05-15",
  "services": ["hotel", "flight"]
}
```

If `relationship` is absent or does not parse as JSON, the service MAY apply
default policy (e.g. deny all, or allow a fixed default scope).

---

## 6. Challenge-Response Protocol

### 6.1 Request a Challenge

```
GET /your-endpoint/challenge?public_key=<hex>
```

**Response**

```json
{
  "challenge": "a3f9b2...",
  "expires_in": 27
}
```

The challenge is a **stateless HMAC-SHA256** hex string computed as:

```
challenge = HMAC-SHA256(key=SECRET, msg="{public_key}:{window}")
window    = floor(unix_timestamp / 30)
```

Challenges are valid for the **current window and the previous one** (up to ~60 s
of clock skew tolerance). No server-side session state is required.

### 6.2 Sign the Challenge (client-side)

```
message_hash = SHA-256( challenge.encode("utf-8") )   // 32 raw bytes
signature    = secp256k1_sign( message_hash, agent_private_key )
                 // DER-encoded ECDSA, base64-encoded
```

The message passed to the signing function is the raw 32-byte hash — **do not
hash it again inside the signing library**.

With `@noble/secp256k1` v2:

```js
import { secp256k1 } from "@noble/curves/secp256k1";
import { sha256 } from "@noble/hashes/sha256";

const msgHash = sha256(new TextEncoder().encode(challenge));
const sigObj = secp256k1.sign(msgHash, privateKeyBytes, { lowS: true });
const derBytes = sigObj.toDERRawBytes();
const signature = btoa(String.fromCharCode(...derBytes));
```

### 6.3 Submit the Authenticated Request

```
POST /your-endpoint/action
Content-Type: application/json

{
  "public_key": "<66-char hex compressed secp256k1 key>",
  "challenge":  "<64-char hex HMAC-SHA256>",
  "signature":  "<base64-encoded DER signature>",
  ...service-specific fields...
}
```

---

## 7. Server Validation (Required Steps)

A conforming service MUST perform these checks **in order**, returning the
specified HTTP status on failure:

| Step | Check                                                                        | Failure status |
| ---- | ---------------------------------------------------------------------------- | -------------- |
| 1    | `challenge` matches HMAC-SHA256 for current or previous 30-second window     | 401            |
| 2    | `secp256k1_verify(b64decode(signature), sha256(challenge), public_key)`      | 401            |
| 3    | KEL exists for `public_key`                                                  | 403            |
| 4    | `addr(public_key)` does NOT appear as `public_key_hash` in any KEL entry     | 403            |
| 5    | `kel[-1].prerotated_key_hash == addr(public_key)`                            | 403            |
| 6    | Request is within the scope committed in `kel[-1].relationship` (if present) | 403            |

Step 6 is service-defined; the SDK provides helpers but ultimate enforcement
is the service's responsibility.

---

## 8. HTTP Status Semantics

Services SHOULD use these codes to communicate booking / action outcomes:

| Code    | Meaning                                                                  |
| ------- | ------------------------------------------------------------------------ |
| **200** | All requested actions completed successfully                             |
| **206** | Partial success: some actions completed, others failed                   |
| **400** | Malformed request (missing fields, bad encoding)                         |
| **401** | Challenge expired/invalid or signature verification failed               |
| **403** | Revoked key, KEL mismatch, or scope violation                            |
| **422** | Authentication passed but nothing could be fulfilled (e.g. no inventory) |

---

## 9. Signature Format

Signatures MUST be:

- **Algorithm**: ECDSA over secp256k1
- **Message**: raw 32-byte SHA-256 of the challenge string (`hasher=None` / pre-hashed)
- **Encoding**: DER-encoded, then base64 (standard, with `=` padding)
- **Canonicalisation**: low-S form RECOMMENDED (prevents signature malleability)

Example value: `MEUCIQCGhWcXJnjbbOvb...=`

---

## 10. KEL Lookup

Services need to resolve the KEL for a given `public_key`. Two options:

### Option A — Bundled YadaCoin node

```python
from yadacoin.core.keyeventlog import KeyEventLog
kel = await KeyEventLog.build_from_public_key(public_key_hex)
```

### Option B — REST API (no local node required)

```
GET https://yadacoin.io/key-rotation/kel?public_key=<hex>
```

Response: JSON array of KEL entries (same schema as on-chain transactions).

The Python SDK `YadaCoinRestKelProvider` implements option B out of the box.

---

## 11. Security Considerations

**Challenge secret**  
The HMAC secret must be kept server-side. Use an environment variable:
`YADACOIN_AGENT_SECRET`. Rotating the secret immediately invalidates all
outstanding challenges (at most 60 s disruption).

**One-time use**  
Each provisioned key SHOULD be used for a single request then discarded. The
revocation check (step 4) enforces this: once the key signs a rotation it
appears as `public_key_hash` in the KEL and is rejected.

**Scope binding**  
The scope is committed in a blockchain transaction _before_ the request. An
attacker who intercepts the request cannot widen the scope.

**Replay protection**  
The 30-second challenge window provides replay protection. Services that
require stronger guarantees (e.g. financial transactions) SHOULD track used
challenges in a short-lived cache keyed by `(public_key, challenge)`.

**Clock skew**  
The ±30-second window (two windows accepted) tolerates typical NTP drift.
Services MAY tighten this by accepting only the current window.

**DER malleability**  
Require `lowS: true` from clients and verify the s-value constraint on the
server to prevent signature malleability.

---

## 12. Minimal Endpoint Template

```python
from yadacoin_agent_auth import AgentAuthValidator, AuthError
import os

validator = AgentAuthValidator(
    challenge_secret=os.environ["YADACOIN_AGENT_SECRET"].encode()
)

# GET /challenge?public_key=<hex>
async def challenge_handler(request):
    info = validator.make_challenge(request.args["public_key"])
    return json_response(info)          # {challenge, expires_in}

# POST /action
async def action_handler(request):
    body = await request.json()
    try:
        auth = await validator.validate(
            public_key=body["public_key"],
            challenge=body["challenge"],
            signature=body["signature"],
        )
    except AuthError as exc:
        return json_response({"error": str(exc)}, status=exc.http_status)

    scope = auth.scope          # dict from on-chain relationship field
    # ... implement your service logic here ...
    return json_response({"status": True})
```

---

## 13. Versioning

This document describes **protocol version 1.0**. Breaking changes will
increment the major version. The `public_key` field in requests MAY carry a
`protocol_version` hint in future versions.

---

_YadaCoin Open Source License (YOSL) v1.1 — Copyright © 2017-2025 Matthew Vogel, Reynold Vogel, Inc._
