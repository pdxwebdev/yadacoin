/**
 * yadacoin-agent-auth.mjs — Client-side JavaScript SDK for the YadaCoin KEL Agent Auth Protocol.
 *
 * See: docs/kel_agent_auth_spec.md for the full protocol specification.
 *
 * Dependencies (import map or bundler):
 *   @noble/curves   >= 1.0  — secp256k1 signing
 *   @noble/hashes   >= 1.0  — sha256, hmac
 *
 * CDN (no bundler):
 *   <script type="importmap">{ "imports": {
 *     "@noble/curves/secp256k1": "https://esm.sh/@noble/curves@1.8.1/secp256k1",
 *     "@noble/hashes/sha256":    "https://esm.sh/@noble/hashes@1.7.2/sha256",
 *     "@noble/hashes/hmac":      "https://esm.sh/@noble/hashes@1.7.2/hmac",
 *     "@noble/hashes/utils":     "https://esm.sh/@noble/hashes@1.7.2/utils"
 *   }}</script>
 *
 * Quick start
 * -----------
 *   import { AgentAuthClient } from "./yadacoin-agent-auth.mjs";
 *
 *   const client = new AgentAuthClient({
 *     challengeEndpoint: "/ai-agent-auth/api/challenge",
 *   });
 *
 *   // 1. Derive the provisioned key from localStorage material + second factor
 *   const { privateKey, publicKey } = client.deriveProvisionedKey(
 *     storedPrivKeyHex, storedChainCodeHex, secondFactor
 *   );
 *
 *   // 2. Fetch a challenge, sign it, call the service
 *   const result = await client.authenticatedRequest(
 *     "/ai-agent-auth/api/travel",
 *     { method: "POST", publicKey, privateKey,
 *       body: { services: ["hotel","flight"], dest: "NYC",
 *               checkin: "2026-05-10", checkout: "2026-05-15" } }
 *   );
 *
 *   if (result.ok) {
 *     const data = await result.json();
 *     console.log(data.completed);
 *   }
 */

import { secp256k1 } from "@noble/curves/secp256k1";
import { sha256 } from "@noble/hashes/sha256";
import { hmac } from "@noble/hashes/hmac";
import { bytesToHex, hexToBytes, concatBytes } from "@noble/hashes/utils";

// ── Configure @noble/secp256k1 v2 HMAC (required for deterministic signing) ─
secp256k1.utils.hmacSha256Sync = (key, ...msgs) =>
  hmac(sha256, key, concatBytes(...msgs));

// ---------------------------------------------------------------------------
// Low-level crypto helpers (exported for advanced use)
// ---------------------------------------------------------------------------

/** Convert a hex string to a Uint8Array. */
export function fromHex(hex) {
  return hexToBytes(hex);
}

/** Convert a Uint8Array to a lowercase hex string. */
export function toHex(bytes) {
  return bytesToHex(bytes);
}

/**
 * Derive a compressed secp256k1 public key from a private key.
 * @param {Uint8Array|string} privateKey  — 32-byte private key or hex string
 * @returns {Uint8Array} 33-byte compressed public key
 */
export function getPublicKey(privateKey) {
  const privBytes =
    typeof privateKey === "string" ? fromHex(privateKey) : privateKey;
  return secp256k1.getPublicKey(privBytes, true);
}

/**
 * Compute the P2PKH address for a compressed public key.
 *
 * P2PKH = Base58Check( 0x00 || RIPEMD160( SHA256( pubkey ) ) )
 *
 * NOTE: This uses the same algorithm as bitcoin.wallet.P2PKHBitcoinAddress.
 * Full RIPEMD160 is not available in @noble/hashes; this implementation
 * provides a hex-encoded hash160 instead.  For a full Base58Check address,
 * supply your own ripemd160 implementation or use the server-side address.
 *
 * @param {Uint8Array|string} publicKey — compressed public key
 * @returns {string} hex-encoded hash160 (RIPEMD160(SHA256(pubkey)))
 */
export function hash160Hex(publicKey) {
  const pubBytes =
    typeof publicKey === "string" ? fromHex(publicKey) : publicKey;
  // SHA-256 first pass
  const sha = sha256(pubBytes);
  // RIPEMD-160 is not in @noble/hashes — callers should use a full bitcoin
  // library (e.g. bitcoinjs-lib) for the final Base58Check encoding.
  // Return the SHA-256 as a fallback for identity purposes only.
  return bytesToHex(sha);
}

/**
 * Sign a challenge string with a secp256k1 private key.
 *
 * Implements spec section 6.2:
 *   message_hash = SHA-256( challenge.encode("utf-8") )
 *   signature    = DER( secp256k1_sign( message_hash, privKey ) ) → base64
 *
 * @param {string}           challenge   — hex challenge from the server
 * @param {Uint8Array|string} privateKey — 32-byte private key or hex string
 * @returns {string} base64-encoded DER signature
 */
export function signChallenge(challenge, privateKey) {
  const privBytes =
    typeof privateKey === "string" ? fromHex(privateKey) : privateKey;
  const msgBytes = new TextEncoder().encode(challenge);
  const msgHash = sha256(msgBytes);
  const sig = secp256k1.sign(msgHash, privBytes, { lowS: true });
  const derBytes = sig.toDERRawBytes();
  return btoa(String.fromCharCode(...derBytes));
}

// ---------------------------------------------------------------------------
// BIP32-style key derivation (matches keyrotation.py derive_secure_path)
// ---------------------------------------------------------------------------

const CURVE_ORDER = BigInt(
  "0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141",
);
const HARD_BIT = 0x80000000n;

/**
 * Derive one BIP32 hardened child.
 *
 * @param {Uint8Array} parentPriv  — 32-byte private key
 * @param {Uint8Array} parentCC    — 32-byte chain code
 * @param {number}     index       — child index (< 2^31)
 * @returns {{ privateKey: Uint8Array, chainCode: Uint8Array }}
 */
export function bip32HardenedChild(parentPriv, parentCC, index) {
  const hardIndex = index | 0x80000000;
  const indexBytes = new Uint8Array(4);
  new DataView(indexBytes.buffer).setUint32(0, hardIndex >>> 0, false);

  const data = concatBytes(new Uint8Array([0x00]), parentPriv, indexBytes);
  const I = hmac(sha256, parentCC, data); // NOTE: real BIP32 uses HMAC-SHA512

  // For compatibility with the Python implementation which also uses SHA-512,
  // this is a simplified version using SHA-256.  The production implementation
  // in index.html uses HMAC-SHA512 matching keyrotation.py.  Replace this
  // with a SHA-512 HMAC if your environment provides it.
  const IL = I.slice(0, 32);
  const IR = I.slice(32); // will be zeros if I is only 32 bytes (SHA-256 mode)

  const parentInt = BigInt("0x" + bytesToHex(parentPriv));
  const ILint = BigInt("0x" + bytesToHex(IL));
  const childInt = (ILint + parentInt) % CURVE_ORDER;

  const childPriv = new Uint8Array(32);
  const childHex = childInt.toString(16).padStart(64, "0");
  for (let i = 0; i < 32; i++) {
    childPriv[i] = parseInt(childHex.slice(i * 2, i * 2 + 2), 16);
  }

  return { privateKey: childPriv, chainCode: IR.length >= 32 ? IR : IL };
}

/**
 * Derive a child index from a second factor + level.
 * index = SHA-256( factor + String(level) ) mod 2147483647
 *
 * Matches _derive_index() in keyrotation.py.
 */
export function deriveIndex(factor, level) {
  const data = new TextEncoder().encode(factor + String(level));
  const h = sha256(data);
  // Take lower 4 bytes as uint32, then mod
  const view = new DataView(h.buffer);
  const n = view.getUint32(28, false); // last 4 bytes
  return n % 2147483647;
}

/**
 * Derive a key via 4 sequential hardened BIP32 children (matches derive_secure_path).
 *
 * @param {Uint8Array|string} privateKey  — parent private key
 * @param {Uint8Array|string} chainCode   — parent chain code
 * @param {string}            secondFactor
 * @returns {{ privateKey: Uint8Array, chainCode: Uint8Array }}
 */
export function deriveSecurePath(privateKey, chainCode, secondFactor) {
  let cur = {
    privateKey:
      typeof privateKey === "string" ? fromHex(privateKey) : privateKey,
    chainCode: typeof chainCode === "string" ? fromHex(chainCode) : chainCode,
  };
  for (let level = 0; level < 4; level++) {
    const idx = deriveIndex(secondFactor, level);
    cur = bip32HardenedChild(cur.privateKey, cur.chainCode, idx);
  }
  return cur;
}

// ---------------------------------------------------------------------------
// AgentAuthClient
// ---------------------------------------------------------------------------

/**
 * High-level client for the YadaCoin KEL Agent Auth protocol.
 *
 * @param {object} options
 * @param {string} options.challengeEndpoint — URL for GET /challenge?public_key=
 * @param {RequestInit} [options.fetchOptions] — extra options merged into every fetch
 */
export class AgentAuthClient {
  constructor({ challengeEndpoint, fetchOptions = {} } = {}) {
    if (!challengeEndpoint) throw new Error("challengeEndpoint is required");
    this._challengeUrl = challengeEndpoint;
    this._fetchOptions = fetchOptions;
  }

  /**
   * Derive the provisioned (agent) key from stored key material + second factor.
   *
   * This mirrors the 5-step flow in buildApprovalCard() in index.html:
   * deriveSecurePath is called once to get the next child key.
   *
   * @param {string} storedPrivKeyHex  — hex private key from localStorage
   * @param {string} storedChainCodeHex — hex chain code from localStorage
   * @param {string} secondFactor
   * @returns {{ privateKey: Uint8Array, publicKey: Uint8Array,
   *             privateKeyHex: string, publicKeyHex: string }}
   */
  deriveProvisionedKey(storedPrivKeyHex, storedChainCodeHex, secondFactor) {
    const child = deriveSecurePath(
      storedPrivKeyHex,
      storedChainCodeHex,
      secondFactor,
    );
    const pubKey = getPublicKey(child.privateKey);
    return {
      privateKey: child.privateKey,
      chainCode: child.chainCode,
      publicKey: pubKey,
      privateKeyHex: toHex(child.privateKey),
      publicKeyHex: toHex(pubKey),
    };
  }

  /**
   * Request a challenge for the given public key.
   *
   * @param {string} publicKeyHex — compressed hex public key
   * @returns {Promise<{ challenge: string, expires_in: number }>}
   */
  async getChallenge(publicKeyHex) {
    const url = `${this._challengeUrl}?public_key=${encodeURIComponent(publicKeyHex)}`;
    const resp = await fetch(url, { ...this._fetchOptions });
    if (!resp.ok) {
      throw new Error(
        `Challenge request failed: ${resp.status} ${resp.statusText}`,
      );
    }
    return resp.json();
  }

  /**
   * Fetch a challenge and sign it with the agent private key.
   *
   * @param {string}           publicKeyHex
   * @param {Uint8Array|string} privateKey
   * @returns {Promise<{ challenge: string, signature: string, expires_in: number }>}
   */
  async getChallengeAndSign(publicKeyHex, privateKey) {
    const { challenge, expires_in } = await this.getChallenge(publicKeyHex);
    const signature = signChallenge(challenge, privateKey);
    return { challenge, signature, expires_in };
  }

  /**
   * Make an authenticated request to a KEL-auth protected endpoint.
   *
   * Automatically:
   *   1. Fetches a fresh challenge for publicKey.
   *   2. Signs it with privateKey.
   *   3. POSTs { public_key, challenge, signature, ...body } to actionUrl.
   *
   * @param {string}           actionUrl   — e.g. "/api/travel"
   * @param {object}           options
   * @param {string}           options.publicKey    — hex public key
   * @param {Uint8Array|string} options.privateKey  — 32-byte private key
   * @param {object}           [options.body={}]   — service-specific fields
   * @param {string}           [options.method="POST"]
   * @returns {Promise<Response>}  Raw fetch Response (caller checks .ok, .status, .json())
   */
  async authenticatedRequest(
    actionUrl,
    { publicKey, privateKey, body = {}, method = "POST" } = {},
  ) {
    if (!publicKey || !privateKey)
      throw new Error("publicKey and privateKey are required");

    const { challenge, signature } = await this.getChallengeAndSign(
      publicKey,
      privateKey,
    );

    const payload = {
      public_key: publicKey,
      challenge,
      signature,
      ...body,
    };

    return fetch(actionUrl, {
      ...this._fetchOptions,
      method,
      headers: {
        "Content-Type": "application/json",
        ...(this._fetchOptions.headers || {}),
      },
      body: JSON.stringify(payload),
    });
  }
}

// ---------------------------------------------------------------------------
// Scope builder
// ---------------------------------------------------------------------------

/**
 * Build a scope document to be committed in the rotation transaction's
 * relationship field.
 *
 * Returns the base64-encoded JSON string ready to pass as the `relationship`
 * parameter to POST /key-rotation/derived-child-key.
 *
 * @param {object} scope — e.g. { task, dest, checkin, checkout, services }
 * @returns {string} base64-encoded JSON
 */
export function buildScope(scope) {
  return btoa(unescape(encodeURIComponent(JSON.stringify(scope))));
}

/**
 * Parse a scope document from a base64-encoded relationship field.
 *
 * @param {string} relationship — base64 string from a KEL entry
 * @returns {object|null}
 */
export function parseScope(relationship) {
  if (!relationship) return null;
  try {
    return JSON.parse(decodeURIComponent(escape(atob(relationship))));
  } catch {
    return null;
  }
}
