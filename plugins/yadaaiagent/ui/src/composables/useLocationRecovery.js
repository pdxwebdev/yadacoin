/**
 * useLocationRecovery.js — yadaaiagent edition (ZKP location commitment).
 *
 * Adapted from plugins/yadacoinwallet/ui/src/composables/useLocationRecovery.js.
 * Verified by the consensus-side verifier in
 *   yadacoin/core/locationrecovery.py
 *
 * Three locations generate a witness whose commitment is embedded in a
 * blockchain transaction. Recovery re-derives the witness and verifies the
 * proof to decrypt the mnemonic.
 *
 * Cryptographic structure:
 *   Witness:    w  = HKDF(locations, salt, "zkp-witness")     — private, never stored
 *   Scalar:     x  = w as big-endian scalar (mod N)
 *   EC commit:  C  = x·G                                      — published only at recovery
 *   WitnessHash:H  = SHA-256(C_compressed_bytes)              — published in {"recovery": H}
 *   EncKey:     k  = HKDF(w, salt, "mnemonic-enc")            — AES-256-GCM key
 *   Proof:      Schnorr(x, prevKeyHash) via Fiat-Shamir       — no trusted setup
 *     e = SHA-256(R ‖ C ‖ prevKeyHash_or_zeros)
 *     s = r − e·x  mod N
 *
 * On-chain flow:
 *   1. Announce  : tx.relationship = {"recovery": witnessHash}    (KEL unconfirmed entry)
 *   2. Recover   : new KEL inception with prev_public_key_hash set and
 *                  tx.relationship = {"recovers": {commitment, R, s}}
 */

import * as secp from "@noble/secp256k1";
import { sha256 } from "@noble/hashes/sha256";
import { hkdf } from "@noble/hashes/hkdf";
import * as bip39 from "@scure/bip39";
import { wordlist } from "@scure/bip39/wordlists/english.js";
import { getNodeUrl } from "./useStorage.js";
import { storeWitnessSecret } from "./useCredentialReceipts.js";

export const LOCATION_COUNT = 3;

// secp256k1 group order — well-known public constant
const CURVE_N =
  0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141n;

// ── Byte / bigint helpers ─────────────────────────────────────────────────────

function bytesToHex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function hexToBytes(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++)
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return bytes;
}

function bytesToBase64(bytes) {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

function base64ToBytes(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function bytesToBigInt(bytes) {
  let n = 0n;
  for (const b of bytes) n = (n << 8n) | BigInt(b);
  return n;
}

function bigIntToBytes32(n) {
  return hexToBytes(n.toString(16).padStart(64, "0"));
}

// ── Location encoding ─────────────────────────────────────────────────────────

const PRECISION = 4;

function quantize(coord) {
  return Math.round(coord * 10_000) / 10_000;
}

function encodeLocations(locations) {
  return locations
    .map(
      (l) =>
        `${quantize(l.lat).toFixed(PRECISION)},${quantize(l.lng).toFixed(PRECISION)}`,
    )
    .join("|");
}

// ── Witness derivation (HKDF) ─────────────────────────────────────────────────

const APP_SALT = new TextEncoder().encode("yadacoin-location-zkp-v1");
const WITNESS_INFO = new TextEncoder().encode("zkp-witness");
const ENC_INFO = new TextEncoder().encode("mnemonic-enc");

function deriveWitness(locations, secondFactor = null) {
  const locStr = encodeLocations(locations);
  const ikm = new TextEncoder().encode(
    secondFactor ? locStr + ":" + secondFactor : locStr,
  );
  return hkdf(sha256, ikm, APP_SALT, WITNESS_INFO, 32);
}

function deriveEncKey(witnessBytes) {
  return hkdf(sha256, witnessBytes, APP_SALT, ENC_INFO, 32);
}

function witnessToScalar(witnessBytes) {
  return (bytesToBigInt(witnessBytes) % (CURVE_N - 1n)) + 1n;
}

// ── AES-256-GCM encryption of mnemonic ───────────────────────────────────────

async function encryptMnemonic(encKeyBytes, mnemonic) {
  const key = await crypto.subtle.importKey(
    "raw",
    encKeyBytes,
    { name: "AES-GCM" },
    false,
    ["encrypt"],
  );
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    new TextEncoder().encode(mnemonic),
  );
  return {
    iv: Array.from(iv),
    ciphertext: Array.from(new Uint8Array(ciphertext)),
  };
}

async function decryptMnemonic(encKeyBytes, encryptedMnemonic) {
  const key = await crypto.subtle.importKey(
    "raw",
    encKeyBytes,
    { name: "AES-GCM" },
    false,
    ["decrypt"],
  );
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: new Uint8Array(encryptedMnemonic.iv) },
    key,
    new Uint8Array(encryptedMnemonic.ciphertext),
  );
  return new TextDecoder().decode(plain);
}

// ── Schnorr ZKP (non-interactive via Fiat-Shamir, no trusted setup) ───────────

function buildChallenge(R_hex, commitment, prevKeyHash) {
  // prevKeyHash is the previous KEL tip's public_key_hash (a base58 P2PKH
  // address string). We hash its raw UTF-8 bytes so the Python verifier can
  // reproduce the same digest without parsing the address codec. When absent
  // a 32-byte zero block is substituted.
  const prevBytes = prevKeyHash
    ? new TextEncoder().encode(prevKeyHash)
    : new Uint8Array(32);
  return new Uint8Array([
    ...hexToBytes(R_hex),
    ...hexToBytes(commitment),
    ...prevBytes,
  ]);
}

function generateProof(x, prevKeyHash = null) {
  const G = secp.Point.BASE;
  const C = G.multiply(x);

  const rBytes = crypto.getRandomValues(new Uint8Array(32));
  const r = (bytesToBigInt(rBytes) % (CURVE_N - 1n)) + 1n;
  const R = G.multiply(r);

  const e =
    bytesToBigInt(
      sha256(buildChallenge(R.toHex(true), C.toHex(true), prevKeyHash)),
    ) % CURVE_N;

  const s = (((r - e * x) % CURVE_N) + CURVE_N) % CURVE_N;

  return {
    commitment: C.toHex(true),
    R: R.toHex(true),
    s: bytesToHex(bigIntToBytes32(s)),
  };
}

function verifyProof(commitment, R_hex, s_hex, prevKeyHash = null) {
  try {
    const G = secp.Point.BASE;
    const C = secp.Point.fromHex(commitment);
    const R = secp.Point.fromHex(R_hex);
    const e =
      bytesToBigInt(sha256(buildChallenge(R_hex, commitment, prevKeyHash))) %
      CURVE_N;
    const s = bytesToBigInt(hexToBytes(s_hex));
    if (s === 0n || s >= CURVE_N) return false;
    return G.multiply(s).add(C.multiply(e)).equals(R);
  } catch {
    return false;
  }
}

// ── IndexedDB storage (separate DB from yadacoinwallet plugin) ───────────────

const DB_NAME = "yadacoin_aiagent";
const DB_VERSION = 1;
const VAULT_STORE = "vault";
const LOCATION_VAULT_KEY = "location_recovery_vault";

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      e.target.result.createObjectStore(VAULT_STORE);
    };
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

async function saveLocationVault(data) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(VAULT_STORE, "readwrite");
    const req = tx.objectStore(VAULT_STORE).put(data, LOCATION_VAULT_KEY);
    req.onsuccess = () => resolve();
    req.onerror = (e) => reject(e.target.error);
  });
}

async function loadLocationVault() {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(VAULT_STORE, "readonly");
    const req = tx.objectStore(VAULT_STORE).get(LOCATION_VAULT_KEY);
    req.onsuccess = (e) => resolve(e.target.result ?? null);
    req.onerror = (e) => reject(e.target.error);
  });
}

export async function hasLocationVault() {
  try {
    const v = await loadLocationVault();
    return !!v;
  } catch {
    return false;
  }
}

// ── Recovery code (drives on-chain encrypted hints) ──────────────────────────
//
// The Recovery Code is the user-friendly secret a recovering user types in
// on a fresh device.  It now serves two roles:
//   1. Lookup index: lookup_id = sha256("yada-recovery-lookup:" + code)
//      lets the client fetch the matching on-chain announcement without
//      having to know the witnessHash up-front.
//   2. Encryption key seed: AES-256-GCM key = HKDF(sha256(code), salt, info)
//      decrypts the hint labels embedded in the announcement.
// Neither the code nor the plaintext hints ever touch the server.

const B32 = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";
const RECOVERY_CODE_LOOKUP_INFO = new TextEncoder().encode(
  "yada-recovery-lookup",
);
const RECOVERY_CODE_ENC_INFO = new TextEncoder().encode(
  "yada-recovery-hints-enc",
);
const RECOVERY_CODE_LOOKUP_PREFIX = "yada-recovery-lookup:";

function generateRecoveryCode() {
  const bytes = crypto.getRandomValues(new Uint8Array(8));
  const chars = Array.from(bytes, (b) => B32[b % 32]);
  return `${chars.slice(0, 4).join("")}-${chars.slice(4).join("")}`;
}

function normalizeCode(code) {
  return code.replace(/[-\s]/g, "").toUpperCase();
}

function codeLookupId(code) {
  const norm = normalizeCode(code);
  return bytesToHex(
    sha256(new TextEncoder().encode(RECOVERY_CODE_LOOKUP_PREFIX + norm)),
  );
}

function codeEncKey(code) {
  const ikm = sha256(new TextEncoder().encode(normalizeCode(code)));
  return hkdf(sha256, ikm, APP_SALT, RECOVERY_CODE_ENC_INFO, 32);
}

/**
 * Encrypt hint labels with the Recovery Code.  The payload is a JSON object
 * containing the hint label strings.  The on-chain field names (hints_iv /
 * hints_ct) are kept unchanged so the server-side handler needs no update.
 *
 * @param {string}   code  - Recovery Code string
 * @param {string[]} hints - Array of hint label strings
 */
async function encryptHintsWithCode(code, hints) {
  const keyBytes = codeEncKey(code);
  const key = await crypto.subtle.importKey(
    "raw",
    keyBytes,
    { name: "AES-GCM" },
    false,
    ["encrypt"],
  );
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const payload = { hints };
  const plaintext = new TextEncoder().encode(JSON.stringify(payload));
  const ct = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    plaintext,
  );
  return {
    hints_iv: bytesToHex(iv),
    hints_ct: bytesToBase64(new Uint8Array(ct)),
  };
}

/**
 * Decrypt a recovery payload encrypted by encryptHintsWithCode.
 * Returns an object with `hints` (array).
 * Handles the legacy format where only a plain hints array was encrypted.
 */
async function decryptHintsWithCode(code, ivHex, ctB64) {
  const keyBytes = codeEncKey(code);
  const key = await crypto.subtle.importKey(
    "raw",
    keyBytes,
    { name: "AES-GCM" },
    false,
    ["decrypt"],
  );
  const iv = hexToBytes(ivHex);
  const ct = base64ToBytes(ctB64);
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ct);
  const parsed = JSON.parse(new TextDecoder().decode(plain));
  // Legacy format: the ciphertext was just a JSON array of hint strings.
  if (Array.isArray(parsed)) {
    return { hints: parsed };
  }
  return { hints: parsed.hints ?? parsed }; // normalise legacy plain-array form
}

/**
 * Locate the on-chain delegator KEL tip for a given witnessHash so a fresh
 * device can build a recovers-inception that points at the correct
 * `prev_public_key_hash`.  Returns null when the announcement has not yet
 * been mined (or doesn't exist).
 */
export async function findRecoveryTip(witnessHash) {
  const url = `${getNodeUrl()}/ai-agent-auth/api/find-recovery-tip?witness_hash=${encodeURIComponent(
    witnessHash,
  )}`;
  const res = await fetch(url);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Server error: ${res.status}`);
  return res.json();
}

/**
 * Locate the on-chain announcement that embeds encrypted hints for *code*.
 * Used at the start of fresh-device recovery so the user can see hint
 * labels before re-pinning any locations.  Returns the same payload as
 * `findRecoveryTip` plus `hints_iv`/`hints_ct` when the announcement
 * carries them.
 */
export async function findRecoveryTipByCode(code) {
  const lookupId = codeLookupId(code);
  const url = `${getNodeUrl()}/ai-agent-auth/api/find-recovery-tip?lookup_id=${encodeURIComponent(
    lookupId,
  )}`;
  const res = await fetch(url);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Server error: ${res.status}`);
  return res.json();
}

/**
 * Build the on-chain `{recovery: ...}` relationship payload for embedding
 * in a follow-up KEL rotation.  When *code* + *hints* are supplied the
 * announcement carries the lookup index and AES-GCM ciphertext of the
 * hint labels (decryptable only by holders of the Recovery Code).  When
 * omitted the legacy flat-string form is emitted, byte-compatible with
 * older announcements.
 *
 * The wire format is a plain object/string (Transaction.__init__ on the
 * node hydrates it into a RecoveryAnnouncement instance via
 * from_relationship).  The relationship_hash is sha256 over
 * RecoveryAnnouncement.to_string(), which concatenates
 *   witness_hash || lookup_id || hints_iv || hints_ct
 * (any of the trailing fields empty when absent).
 */
export async function buildRecoveryAnnouncementRelationship(
  witnessHash,
  code = null,
  hints = null,
) {
  const enc = new TextEncoder();
  if (!code || !hints || hints.length === 0) {
    const relationship = { recovery: witnessHash };
    const relationshipHash = bytesToHex(sha256(enc.encode(witnessHash)));
    return { relationship, relationshipHash };
  }
  const lookupId = codeLookupId(code);
  const { hints_iv, hints_ct } = await encryptHintsWithCode(code, hints);
  const relationship = {
    recovery: {
      witness_hash: witnessHash,
      lookup_id: lookupId,
      hints_iv,
      hints_ct,
    },
  };
  const preimage = witnessHash + lookupId + hints_iv + hints_ct;
  const relationshipHash = bytesToHex(sha256(enc.encode(preimage)));
  return { relationship, relationshipHash };
}

/**
 * Build the on-chain `{recovers: {commitment, R, s}}` relationship payload
 * embedded in a recovers-inception transaction signed by the user's freshly
 * generated K_0 on the recovering device.  The wire format is a plain dict
 * (Transaction.__init__ on the node hydrates it into a RecoveryProof
 * instance).  The relationship_hash is sha256 over
 * RecoveryProof.to_string(), which is `commitment || R || s` concatenated
 * lowercase hex.
 */
export function buildRecoversRelationship(commitment, R, s) {
  const relationship = { recovers: { commitment, R, s } };
  const enc = new TextEncoder();
  // Must match RecoveryProof.to_string() server-side.
  const relationshipHash = bytesToHex(sha256(enc.encode(commitment + R + s)));
  return { relationship, relationshipHash };
}

/**
 * Build a combined "recovers + recovery" relationship for a recovers-inception
 * that simultaneously proves recovery eligibility AND announces a new
 * witnessHash for the freshly-recovered KEL.  This lets the new KEL be
 * immediately recoverable without a separate announcement rotation.
 *
 * Wire format:
 *   {
 *     "recovers": { commitment, R, s },
 *     "recovery": { witness_hash, lookup_id, hints_iv, hints_ct }
 *   }
 *
 * The relationship_hash preimage is:
 *   commitment + R + s + witness_hash + lookup_id + hints_iv + hints_ct
 * which is the concatenation of RecoveryProof.to_string() and
 * RecoveryAnnouncement.to_string() — matching RecoveryTransition.to_string()
 * on the Python side.
 *
 * @param {object}      proof        - {commitment, R, s} from deriveRecoveryProof
 * @param {object}      recoveryInner - inner recovery dict from setupLocationRecovery
 *                                      txnData.announcementData.relationship.recovery
 * @returns {{ relationship, relationshipHash }}
 */
export function buildRecoveryTransitionRelationship(proof, recoveryInner) {
  const relationship = {
    recovers: { commitment: proof.commitment, R: proof.R, s: proof.s },
    recovery: recoveryInner,
  };
  const enc = new TextEncoder();
  // Must match RecoveryTransition.to_string() server-side.
  const proofStr = proof.commitment + proof.R + proof.s;
  const annStr =
    (recoveryInner.witness_hash || "") +
    (recoveryInner.lookup_id || "") +
    (recoveryInner.hints_iv || "") +
    (recoveryInner.hints_ct || "");
  const relationshipHash = bytesToHex(sha256(enc.encode(proofStr + annStr)));
  return { relationship, relationshipHash };
}

/**
 * Derive the public commitment + Schnorr proof from a re-pinned set of
 * locations + the lost KEL tip's `public_key_hash`.  The caller embeds the
 * returned `(commitment, R, s)` triple into a recovers-inception
 * transaction; the chain verifies it via
 * yadacoin/core/locationrecovery.verify_proof.
 */
export function deriveRecoveryProof(
  locations,
  prevKeyHash,
  secondFactor = null,
) {
  if (locations.length !== LOCATION_COUNT)
    throw new Error(`Exactly ${LOCATION_COUNT} locations required`);
  const witness = deriveWitness(locations, secondFactor);
  const x = witnessToScalar(witness);
  return generateProof(x, prevKeyHash);
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Set up location-based recovery.
 *
 * @param {Array}       locations        - 3 {lat, lng, hint} objects
 * @param {string|null} existingMnemonic - existing mnemonic to protect; if null
 *                                         a fresh random BIP-39 phrase is generated
 * @param {string|null} prevKeyHash      - hex hash of the latest key log entry
 *                                         (public input that binds proof to KEL)
 * @returns {{ mnemonic, code, txnData }}
 */
export async function setupLocationRecovery(
  locations,
  existingMnemonic = null,
  prevKeyHash = null,
  secondFactor = null,
) {
  if (locations.length !== LOCATION_COUNT)
    throw new Error(`Exactly ${LOCATION_COUNT} locations required`);

  const witness = deriveWitness(locations, secondFactor);
  storeWitnessSecret(bytesToHex(witness));
  const x = witnessToScalar(witness);
  const proof = generateProof(x, prevKeyHash);

  const witnessHash = bytesToHex(sha256(hexToBytes(proof.commitment)));

  const encKey = deriveEncKey(witness);
  const mnemonic = existingMnemonic ?? bip39.generateMnemonic(wordlist, 128);
  const encryptedMnemonic = await encryptMnemonic(encKey, mnemonic);

  await saveLocationVault({
    commitment: proof.commitment,
    proof: { R: proof.R, s: proof.s },
    prevKeyHash: prevKeyHash ?? null,
    encryptedMnemonic,
  });

  const code = generateRecoveryCode();
  // The Recovery Code drives both the on-chain lookup index and the AES
  // key used to encrypt the hint labels.  Hints are embedded directly in
  // the announcement's relationship field (see
  // buildRecoveryAnnouncementRelationship) so the server stores nothing
  // about this user's recovery setup — the encrypted vault and the
  // Schnorr proof never leave this device, and even the hint labels are
  // ciphertext on-chain.
  const hintLabels = locations.map((l) => l.hint || "");
  const announcement = await buildRecoveryAnnouncementRelationship(
    witnessHash,
    code,
    hintLabels,
  );

  const txnData = {
    announcementData: {
      relationship: announcement.relationship,
      relationshipHash: announcement.relationshipHash,
    },
    recoveryData: {
      relationship: {
        recovers: { commitment: proof.commitment, R: proof.R, s: proof.s },
      },
    },
    encryptedMnemonic,
    witnessHash,
    prevKeyHash: prevKeyHash ?? null,
  };

  return { mnemonic, code, txnData };
}

/**
 * Recover the wallet mnemonic by re-entering 3 locations.
 *
 * @param {Array} locations - 3 {lat, lng} objects
 * @returns {string} BIP-39 mnemonic
 */
export async function recoverWithLocations(locations, secondFactor = null) {
  if (locations.length !== LOCATION_COUNT)
    throw new Error(`Exactly ${LOCATION_COUNT} locations required`);

  const stored = await loadLocationVault();
  if (!stored)
    throw new Error(
      "No location recovery vault found on this device. Set up location recovery first.",
    );

  const witness = deriveWitness(locations, secondFactor);
  const x = witnessToScalar(witness);
  const G = secp.Point.BASE;
  const recomputedCommitment = G.multiply(x).toHex(true);

  if (recomputedCommitment !== stored.commitment)
    throw new Error("Incorrect locations — please try again.");

  storeWitnessSecret(bytesToHex(witness));

  const valid = verifyProof(
    stored.commitment,
    stored.proof.R,
    stored.proof.s,
    stored.prevKeyHash ?? null,
  );
  if (!valid) throw new Error("Zero-knowledge proof verification failed.");

  const encKey = deriveEncKey(witness);
  return decryptMnemonic(encKey, stored.encryptedMnemonic);
}

/**
 * Look up an on-chain recovery announcement by Recovery Code and return
 * the decrypted hint labels (or null if the code does not match any
 * announcement, or if the matching announcement has no embedded hints).
 *
 * The returned object also carries the tip metadata so the caller can skip
 * a second `findRecoveryTip` round-trip when proceeding to re-pin.
 */
export async function getLocationHints(code) {
  const tip = await findRecoveryTipByCode(code);
  if (!tip) return null;
  if (!tip.hints_iv || !tip.hints_ct) {
    return { hints: null, tip };
  }
  try {
    const payload = await decryptHintsWithCode(
      code,
      tip.hints_iv,
      tip.hints_ct,
    );
    return {
      hints: payload.hints,
      tip,
    };
  } catch {
    // Wrong code (or tampered ciphertext) — surface as "not found" so the
    // caller's UX matches the legacy behaviour.
    return null;
  }
}

/**
 * Backwards-compatible no-op: server no longer stores the encrypted vault.
 * Fresh-device recovery now goes through the on-chain ZKP path instead
 * (see `deriveRecoveryProof` + `findRecoveryTip` + the recovers-inception
 * built in LocationRecoveryRecover.vue).
 */
export async function hydrateLocationVaultFromServer(/* code */) {
  return false;
}

/**
 * Compute just the public `witnessHash` from a re-pinned set of locations.
 * Used by fresh-device recovery to look up the on-chain announcement
 * (`/api/find-recovery-tip?witness_hash=…`) before constructing the
 * recovers-inception transaction.
 */
export function computeWitnessHashFromLocations(
  locations,
  secondFactor = null,
) {
  if (locations.length !== LOCATION_COUNT)
    throw new Error(`Exactly ${LOCATION_COUNT} locations required`);
  const witness = deriveWitness(locations, secondFactor);
  const x = witnessToScalar(witness);
  const G = secp.Point.BASE;
  const commitment = G.multiply(x).toHex(true);
  return bytesToHex(sha256(hexToBytes(commitment)));
}
