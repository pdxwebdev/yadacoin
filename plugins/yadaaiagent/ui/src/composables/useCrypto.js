import * as secp from "@noble/secp256k1";
import { sha256 } from "@noble/hashes/sha256";
import { sha512 } from "@noble/hashes/sha512";
import { hmac } from "@noble/hashes/hmac";
import { ripemd160 } from "@noble/hashes/ripemd160";
import { createBase58check } from "@scure/base";

// NOTE: secp.etc is sealed after bundling — do NOT assign hmacSha256Sync.
// All signing uses secp.signAsync() which handles HMAC internally.

// ── hex helpers ──────────────────────────────────────────────────────────────
export const hex = {
  toBytes(h) {
    h = h.trim().toLowerCase();
    if (h.length % 2) throw new Error("odd hex length");
    const out = new Uint8Array(h.length / 2);
    for (let i = 0; i < out.length; i++)
      out[i] = parseInt(h.substr(i * 2, 2), 16);
    return out;
  },
  fromBytes: (b) =>
    Array.from(b)
      .map((x) => x.toString(16).padStart(2, "0"))
      .join(""),
};

// ── DER-encode a secp256k1 compact signature ─────────────────────────────────
// sigBytes: 64-byte Uint8Array (compact R‖S) as returned by secp.signAsync
export function compactSigToDerBase64(sigBytes) {
  function encDerInt(bytes32) {
    // Strip leading zeros but keep at least one byte
    let start = 0;
    while (start < 31 && bytes32[start] === 0) start++;
    const trimmed = bytes32.slice(start);
    // Prepend 0x00 if high bit is set (to keep positive)
    const needsPad = trimmed[0] >= 0x80;
    const len = trimmed.length + (needsPad ? 1 : 0);
    const out = new Uint8Array(2 + len);
    out[0] = 0x02;
    out[1] = len;
    if (needsPad) out[2] = 0x00;
    out.set(trimmed, needsPad ? 3 : 2);
    return out;
  }
  const r = encDerInt(sigBytes.slice(0, 32));
  const s = encDerInt(sigBytes.slice(32, 64));
  const body = new Uint8Array(r.length + s.length);
  body.set(r);
  body.set(s, r.length);
  const der = new Uint8Array(2 + body.length);
  der[0] = 0x30;
  der[1] = body.length;
  der.set(body, 2);
  return btoa(String.fromCharCode(...der));
}

// ── BIP32 hardened child derivation (matches keyrotation.py) ─────────────────
const CURVE_ORDER = BigInt(
  "0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141",
);
const HARD_BIT = 0x80000000n;
const INDEX_MOD = 2147483647n;

function bytesToBigIntBE(b) {
  let v = 0n;
  for (const x of b) v = (v << 8n) | BigInt(x);
  return v;
}
function bigIntToBytesBE(v, len) {
  const out = new Uint8Array(len);
  for (let i = len - 1; i >= 0; i--) {
    out[i] = Number(v & 0xffn);
    v >>= 8n;
  }
  return out;
}
function deriveIndex(factor, level) {
  const d = new TextEncoder().encode(factor + String(level));
  return Number(bytesToBigIntBE(sha256(d)) % INDEX_MOD);
}
function bip32HardenedChild(parentPriv, parentCc, index) {
  const hi = (HARD_BIT + BigInt(index)) & 0xffffffffn;
  const data = new Uint8Array(37);
  data[0] = 0x00;
  data.set(parentPriv, 1);
  data[33] = Number((hi >> 24n) & 0xffn);
  data[34] = Number((hi >> 16n) & 0xffn);
  data[35] = Number((hi >> 8n) & 0xffn);
  data[36] = Number(hi & 0xffn);
  const I = hmac(sha512, parentCc, data);
  const childInt =
    (bytesToBigIntBE(I.slice(0, 32)) + bytesToBigIntBE(parentPriv)) %
    CURVE_ORDER;
  return { priv: bigIntToBytesBE(childInt, 32), cc: I.slice(32, 64) };
}

export function deriveSecurePath(privBytes, ccBytes, sf) {
  let cur = { priv: privBytes, cc: ccBytes };
  for (let l = 0; l < 4; l++)
    cur = bip32HardenedChild(cur.priv, cur.cc, deriveIndex(sf, l));
  return cur;
}

export function getPublicKeyHex(privBytes) {
  return hex.fromBytes(secp.getPublicKey(privBytes, true));
}

// signAsync prehash:true (default) hashes msgBytes with sha256 internally.
export async function signMessage(msgBytes, privBytes) {
  return secp.signAsync(msgBytes, privBytes);
}

// ── P2PKH address from compressed public key bytes ───────────────────────────
const _b58check = createBase58check(sha256);

export function getP2PKH(pubKeyBytes) {
  // hash160 = RIPEMD160(SHA256(pubKeyBytes))
  const hash160 = ripemd160(sha256(pubKeyBytes));
  // version byte 0x00 (mainnet P2PKH) + 20-byte hash160
  const payload = new Uint8Array(21);
  payload[0] = 0x00;
  payload.set(hash160, 1);
  return _b58check.encode(payload);
}

// ── Build and sign a single rotation transaction ─────────────────────────────
// Returns the transaction JSON object (as expected by POST /transaction).
export async function buildRotationTxn({
  signerPrivBytes, // Uint8Array – private key of the signer
  publicKeyHex, // hex – compressed public key of the signer
  prerotatedPkh, // string – P2PKH of prerotated key
  twicePrerotatedPkh, // string – P2PKH of twice-prerotated key
  publicKeyHash, // string – P2PKH of signer
  prevPublicKeyHash, // string – P2PKH of previous key ("" for inception)
  relationship, // string – relationship payload or ""
  relationshipHash, // string – sha256 hex of relationship or sha256("")
  txnTime, // number – unix timestamp (seconds)
  inputs, // array  – [{id: "..."}] or []
  outputs, // array  – [{to: "...", value: 0}]
}) {
  // Build the hash pre-image (matches transaction.jsx generateHash)
  const fee = (0.0).toFixed(8);
  const masternodeFee = (0.0).toFixed(8);
  const inputHashes = inputs
    .map((i) => i.id)
    .sort((a, b) => {
      const A = a.toLowerCase(),
        B = b.toLowerCase();
      return A < B ? -1 : A > B ? 1 : 0;
    })
    .join("");
  const outputHashes = [...outputs]
    .map((o) => ({ to: o.to, value: o.value }))
    .sort((a, b) => {
      const A = a.to.toLowerCase(),
        B = b.to.toLowerCase();
      return A < B ? -1 : A > B ? 1 : 0;
    })
    .map((o) => `${o.to}${o.value.toFixed(8)}`)
    .join("");

  const preimage =
    publicKeyHex +
    String(txnTime) +
    "" + // dh_public_key
    "" + // rid
    (relationshipHash || "") +
    fee +
    masternodeFee +
    "" + // requester_rid
    "" + // requested_rid
    inputHashes +
    outputHashes +
    "7" + // version
    (prerotatedPkh || "") +
    (twicePrerotatedPkh || "") +
    (publicKeyHash || "") +
    (prevPublicKeyHash || "");

  // hash = sha256(preimage) as hex string
  const enc = new TextEncoder();
  const hashBytes = sha256(enc.encode(preimage));
  const hashHex = hex.fromBytes(hashBytes);

  // id = DER-base64(sign(hashHex))
  // secp.signAsync prehash defaults to true → internally computes sha256(enc.encode(hashHex))
  // Python coincurve.verify_signature(sig, hashHex.encode('utf-8'), pubkey) with default
  // hasher='sha256' also computes sha256(hashHex_utf8) before verifying — exact match.
  const idBytes = await secp.signAsync(enc.encode(hashHex), signerPrivBytes);
  const idB64 = compactSigToDerBase64(idBytes);

  return {
    public_key: publicKeyHex,
    time: txnTime,
    dh_public_key: "",
    rid: "",
    inputs,
    outputs,
    relationship: relationship || "",
    relationship_hash: relationshipHash || "",
    fee: 0.0,
    masternode_fee: 0.0,
    requester_rid: "",
    requested_rid: "",
    version: 7,
    prerotated_key_hash: prerotatedPkh || "",
    twice_prerotated_key_hash: twicePrerotatedPkh || "",
    public_key_hash: publicKeyHash || "",
    prev_public_key_hash: prevPublicKeyHash || "",
    hash: hashHex,
    id: idB64,
  };
}

export { secp, sha256 };
