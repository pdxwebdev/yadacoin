/**
 * useBip39.js
 *
 * Client-side BIP39 mnemonic generation and BIP32 root key derivation for the
 * yadaaiagent personal-wallet mode.  The mnemonic is NEVER persisted — only
 * the derived working key (K_0) is stored in localStorage.
 *
 * Derivation chain:
 *   BIP39 mnemonic  → (mnemonicToSeed PBKDF2) → 512-bit seed
 *   seed            → (HDKey.fromMasterSeed)   → BIP32 root { priv, chainCode }
 *   root + sf       → (deriveSecurePath × 1)   → K_0 { priv, cc }
 *
 * K_0 is stored as LS_PRIV / LS_CC.  The mnemonic and seed are discarded.
 */

import {
  generateMnemonic,
  mnemonicToSeed,
  validateMnemonic,
} from "@scure/bip39";
import { wordlist } from "@scure/bip39/wordlists/english.js";
import { HDKey } from "@scure/bip32";
import {
  deriveSecurePath,
  hex,
  getPublicKeyHex,
  getP2PKH,
  buildRotationTxn,
} from "./useCrypto.js";
import { LS_PRIV, LS_CC, LS_WALLET_MODE, getNodeUrl } from "./useStorage.js";

// ── Mnemonic helpers ──────────────────────────────────────────────────────────

/** Generate a fresh 12-word BIP39 mnemonic (128-bit entropy). */
export function generateNewMnemonic() {
  return generateMnemonic(wordlist, 128);
}

/** Return true if the phrase is a valid BIP39 mnemonic. */
export function isValidMnemonic(phrase) {
  return validateMnemonic(phrase.trim(), wordlist);
}

// ── Key derivation ────────────────────────────────────────────────────────────

/**
 * Derive the BIP32 root key from a BIP39 mnemonic.
 * Returns { priv: Uint8Array(32), cc: Uint8Array(32) }.
 */
export async function mnemonicToRootKey(mnemonic) {
  const seed = await mnemonicToSeed(mnemonic.trim());
  const hd = HDKey.fromMasterSeed(seed);
  return {
    priv: hd.privateKey, // Uint8Array(32)
    cc: hd.chainCode, // Uint8Array(32)
  };
}

/**
 * Derive K_0 from a mnemonic + second factor, then persist K_0 in localStorage.
 * Sets LS_PRIV, LS_CC, and LS_WALLET_MODE = "client".
 * The mnemonic and seed are NOT stored.
 *
 * @param {string} mnemonic - BIP39 mnemonic phrase
 * @param {string} secondFactor - password / second factor used in deriveSecurePath
 * @returns {{ publicKeyHex: string, address: string }} - K_0's public key info
 */
export async function initClientWallet(mnemonic, secondFactor) {
  const root = await mnemonicToRootKey(mnemonic);
  const k0 = deriveSecurePath(root.priv, root.cc, secondFactor);

  localStorage.setItem(LS_PRIV, hex.fromBytes(k0.priv));
  localStorage.setItem(LS_CC, hex.fromBytes(k0.cc));
  localStorage.setItem(LS_WALLET_MODE, "client");

  return k0;
}

/**
 * Submit an inception key event transaction for a freshly created K_0.
 * The inception establishes the KEL on-chain so that subsequent rotations work.
 *
 * Skipped automatically when re-importing a wallet whose KEL already exists.
 *
 * @param {{ priv: Uint8Array, cc: Uint8Array }} k0 - the initial derived key
 * @param {string} sf - second factor used in deriveSecurePath
 * @returns {Promise<{ skipped?: boolean, transactionId?: string }>}
 */
export async function submitInceptionTransaction(k0, sf) {
  const nodeUrl = getNodeUrl();
  if (!nodeUrl)
    throw new Error(
      "Node URL not configured. Set it in Settings before creating a wallet.",
    );

  const k1 = deriveSecurePath(k0.priv, k0.cc, sf);
  const k2 = deriveSecurePath(k1.priv, k1.cc, sf);

  const k0PubHex = getPublicKeyHex(k0.priv);
  const k0Pkh = getP2PKH(hex.toBytes(k0PubHex));
  const k1Pkh = getP2PKH(hex.toBytes(getPublicKeyHex(k1.priv)));
  const k2Pkh = getP2PKH(hex.toBytes(getPublicKeyHex(k2.priv)));

  // Skip if a KEL already exists (re-import of an existing wallet)
  const kelRes = await fetch(
    `${nodeUrl}/key-event-log?username_signature=asdf&public_key=${encodeURIComponent(k0PubHex)}`,
  );
  const kelData = await kelRes.json();
  if (kelData.key_event_log?.length > 0) {
    return { skipped: true };
  }

  const txnTime = Math.floor(Date.now() / 1000);
  const inceptionTxn = await buildRotationTxn({
    signerPrivBytes: k0.priv,
    publicKeyHex: k0PubHex,
    prerotatedPkh: k1Pkh,
    twicePrerotatedPkh: k2Pkh,
    publicKeyHash: k0Pkh,
    prevPublicKeyHash: "",
    relationship: "",
    relationshipHash: "",
    txnTime,
    inputs: [],
    outputs: [{ to: k1Pkh, value: 0.0 }],
  });

  const res = await fetch(`${nodeUrl}/transaction?username_signature=1`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify([inceptionTxn]),
  });
  const data = await res.json();
  if (!res.ok || data.status === false)
    throw new Error(data.message || `HTTP ${res.status}`);

  // Inception signed by K_0; prerotated = K_1.
  // After it mines, next signer = K_1, so advance localStorage to K_1.
  localStorage.setItem(LS_PRIV, hex.fromBytes(k1.priv));
  localStorage.setItem(LS_CC, hex.fromBytes(k1.cc));

  return { transactionId: inceptionTxn.id };
}
