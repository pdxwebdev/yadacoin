/**
 * useCredentialReceipts.js
 *
 * On-chain encrypted credential receipt storage + resync.
 *
 * After a vendor issues a VC the wallet broadcasts a data-only transaction
 * whose relationship field is:
 *
 *   {"credential_receipt": {
 *       "lookup_key": "<hex>",   // HKDF(witnessSecret, salt, "cred-receipt-lookup")
 *       "iv":         "<hex>",   // 12-byte AES-GCM nonce
 *       "ct":         "<base64>" // AES-GCM ciphertext of the full VC JSON
 *   }}
 *
 * Only the wallet owner can decrypt — they re-derive the witness secret from
 * their locations + secondFactor after recovery, then derive the enc/lookup
 * keys on the fly.  The server stores nothing sensitive; it indexes only by
 * lookup_key.
 *
 * Key derivation:
 *   IKM        = witnessSecret  (32-byte HKDF output from useLocationRecovery)
 *   Salt       = "yadacoin-cred-receipt-v1" (UTF-8)
 *   Enc key    = HKDF-SHA256(IKM, salt, info="cred-receipt-enc",    32 bytes)
 *   Lookup key = HKDF-SHA256(IKM, salt, info="cred-receipt-lookup", 32 bytes) → hex
 *
 * Call storeWitnessSecret(witnessHex) whenever the witness secret is known
 * (after location recovery setup or any location-based restore event).
 * The witness secret is stable across KEL rotations as long as the user
 * re-enters the same locations + secondFactor.
 */

import { hkdf } from "@noble/hashes/hkdf";
import { sha256 } from "@noble/hashes/sha256";
import { bytesToHex, hexToBytes } from "@noble/hashes/utils";

import { LS_PRIV, getNodeUrl } from "./useStorage.js";
import {
  hex,
  getPublicKeyHex,
  secp,
  compactSigToDerBase64,
} from "./useCrypto.js";

// ── Constants ─────────────────────────────────────────────────────────────────
const enc = new TextEncoder();
const CRED_RECEIPT_SALT = enc.encode("yadacoin-cred-receipt-v1");
const CRED_ENC_INFO = enc.encode("cred-receipt-enc");
const CRED_LOOKUP_INFO = enc.encode("cred-receipt-lookup");

export const LS_WITNESS_SECRET = "yadacoin_witness_secret";

// ── Witness secret storage ────────────────────────────────────────────────────

/**
 * Persist the location-recovery witness secret (hex-encoded 32-byte HKDF
 * output from useLocationRecovery.deriveWitness).  All credential receipt
 * keys are derived from this on demand — nothing else needs to be stored.
 */
export function storeWitnessSecret(witnessHex) {
  localStorage.setItem(LS_WITNESS_SECRET, witnessHex);
}

// ── Key derivation from witness secret ───────────────────────────────────────

function _credEncKey() {
  const witnessHex = localStorage.getItem(LS_WITNESS_SECRET);
  if (!witnessHex) return null;
  return hkdf(
    sha256,
    hexToBytes(witnessHex),
    CRED_RECEIPT_SALT,
    CRED_ENC_INFO,
    32,
  );
}

function _credLookupKey() {
  const witnessHex = localStorage.getItem(LS_WITNESS_SECRET);
  if (!witnessHex) return null;
  return bytesToHex(
    hkdf(
      sha256,
      hexToBytes(witnessHex),
      CRED_RECEIPT_SALT,
      CRED_LOOKUP_INFO,
      32,
    ),
  );
}

// ── AES-GCM helpers ──────────────────────────────────────────────────────────

async function _encryptVC(encKeyBytes, vc) {
  const key = await crypto.subtle.importKey(
    "raw",
    encKeyBytes,
    { name: "AES-GCM" },
    false,
    ["encrypt"],
  );
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const plain = enc.encode(JSON.stringify(vc));
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plain);
  return {
    iv: bytesToHex(iv),
    ct: btoa(String.fromCharCode(...new Uint8Array(ct))),
  };
}

async function _decryptVC(encKeyBytes, ivHex, ctB64) {
  const key = await crypto.subtle.importKey(
    "raw",
    encKeyBytes,
    { name: "AES-GCM" },
    false,
    ["decrypt"],
  );
  const iv = hexToBytes(ivHex);
  const ct = Uint8Array.from(atob(ctB64), (c) => c.charCodeAt(0));
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ct);
  return JSON.parse(new TextDecoder().decode(plain));
}

// ── Transaction builder ───────────────────────────────────────────────────────

/**
 * Build and sign a data-only credential_receipt transaction.
 *
 * The transaction has no inputs, no value-bearing outputs, and no KEL
 * rotation fields — it carries only the encrypted VC in the relationship
 * field.  No second factor is required because we sign with the current
 * wallet key already in localStorage (LS_PRIV); no child-key derivation
 * is performed.
 *
 * The relationship_hash preimage is: lookup_key + iv + ct
 * (matches CredentialReceipt.to_string() server-side).
 */
async function _buildReceiptTxn(privHex, relationship, relHash) {
  const privBytes = hexToBytes(privHex);
  const pubHex = getPublicKeyHex(privBytes);
  const txnTime = Math.floor(Date.now() / 1000);

  // Pre-image must exactly match Transaction.generate_hash() for version 7
  // with empty KEL fields and no inputs/outputs.
  const fee = (0.0).toFixed(8);
  const masternodeFee = (0.0).toFixed(8);
  const preimage =
    pubHex +
    String(txnTime) +
    "" + // dh_public_key
    "" + // rid
    relHash +
    fee +
    masternodeFee +
    "" + // requester_rid
    "" + // requested_rid
    "" + // inputHashes (empty)
    "" + // outputHashes (empty)
    "7" + // version
    "" + // prerotated_key_hash
    "" + // twice_prerotated_key_hash
    "" + // public_key_hash
    ""; // prev_public_key_hash

  const hashBytes = sha256(enc.encode(preimage));
  const hashHex = hex.fromBytes(hashBytes);

  const sigBytes = await secp.signAsync(enc.encode(hashHex), privBytes);
  const sigB64 = compactSigToDerBase64(sigBytes);

  return {
    public_key: pubHex,
    time: txnTime,
    dh_public_key: "",
    rid: "",
    inputs: [],
    outputs: [],
    relationship,
    relationship_hash: relHash,
    fee: 0.0,
    masternode_fee: 0.0,
    requester_rid: "",
    requested_rid: "",
    version: 7,
    prerotated_key_hash: "",
    twice_prerotated_key_hash: "",
    public_key_hash: "",
    prev_public_key_hash: "",
    hash: hashHex,
    id: sigB64,
  };
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Encrypt a VC and broadcast a data-only credential_receipt transaction.
 *
 * Fire-and-forget: a network failure is non-fatal because the VC is
 * already stored in localStorage.  Call from ChatPane immediately after
 * saveBookingCredential().
 *
 * Returns silently when the credential keys are not yet set up (pre-setup
 * device / hardware wallet with no mnemonic access).
 */
export async function postCredentialReceipt(vc) {
  const encKeyBytes = _credEncKey();
  const lookupKey = _credLookupKey();
  const privHex = localStorage.getItem(LS_PRIV);
  if (!encKeyBytes || !lookupKey || !privHex) {
    return; // witness secret not set up yet — skip silently
  }

  const { iv, ct } = await _encryptVC(encKeyBytes, vc);

  const relationship = {
    credential_receipt: { lookup_key: lookupKey, iv, ct },
  };
  const relString = lookupKey + iv + ct;
  const relHash = hex.fromBytes(sha256(enc.encode(relString)));

  const txn = await _buildReceiptTxn(privHex, relationship, relHash);

  try {
    await fetch(getNodeUrl() + "/transaction?username_signature=1", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify([txn]),
    });
  } catch {
    // Non-fatal — VC is already in localStorage.
  }
}

/**
 * Fetch all credential receipts for this wallet from the chain + mempool,
 * decrypt each one, and return the array of VC objects.
 *
 * Sends the HKDF lookup_key derived from the witness secret.  The witness
 * secret is derived from the user's recovery locations + secondFactor and
 * is stable across KEL rotations and recoveries as long as the same inputs
 * are used.  This makes the lookup independent of the current signing key
 * and works even before a fresh-device recovers-inception is mined.
 *
 * The caller is responsible for saving them via saveBookingCredential().
 *
 * @returns {Promise<Array>} decrypted VC objects (already-known credentials
 *   will be deduplicated by the caller's saveBookingCredential).
 */
export async function resyncCredentials() {
  const lookupKey = _credLookupKey();
  const encKeyBytes = _credEncKey();
  if (!lookupKey || !encKeyBytes) {
    throw new Error(
      "Credential keys not initialised. Complete location recovery setup first.",
    );
  }

  const res = await fetch(
    getNodeUrl() +
      `/ai-agent-auth/api/resync-credentials?lookup_key=${encodeURIComponent(lookupKey)}`,
  );
  if (!res.ok) throw new Error(`Server error: ${res.status}`);
  const data = await res.json();

  const vcs = [];
  for (const receipt of data.receipts || []) {
    if (!receipt.iv || !receipt.ct) continue;
    try {
      const vc = await _decryptVC(encKeyBytes, receipt.iv, receipt.ct);
      vcs.push(vc);
    } catch {
      // Tampered or wrong-key receipt — skip silently.
    }
  }
  return vcs;
}
