/**
 * KEL derive_secure_path — matches yadacoin/core/keyrotation.py and
 * plugins/keyrotation/templates/key_rotation.html.
 *
 * Root from BIP39: entropy = mnemonicToEntropy(mnemonic); BIP32.fromEntropy(entropy)
 * (NOT PBKDF2 mnemonicToSeed — that is the wallet path and is incompatible.)
 */
import { secp256k1 } from "@noble/curves/secp256k1";
import { hmac } from "@noble/hashes/hmac";
import { ripemd160 } from "@noble/hashes/ripemd160";
import { sha256 } from "@noble/hashes/sha256";
import { sha512 } from "@noble/hashes/sha512";
import { HDKey } from "@scure/bip32";
import { generateMnemonic, mnemonicToEntropy, validateMnemonic } from "@scure/bip39";
import { wordlist } from "@scure/bip39/wordlists/english";
import { bytesToHex, hexToBytes } from "./bytes.js";

const CURVE_ORDER = BigInt(
  "0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141"
);

export interface KeyMaterial {
  privateKey: Uint8Array;
  chainCode: Uint8Array;
  publicKey: Uint8Array;
  publicKeyHex: string;
  address: string;
}

export function generateSeedPhrase(strength: 128 | 256 = 128): string {
  return generateMnemonic(wordlist, strength);
}

export function isValidSeedPhrase(mnemonic: string): boolean {
  return validateMnemonic(mnemonic, wordlist);
}

/** BIP32 root from mnemonic via entropy (node-compatible). */
export function rootFromMnemonic(mnemonic: string): {
  privateKey: Uint8Array;
  chainCode: Uint8Array;
} {
  if (!validateMnemonic(mnemonic, wordlist)) {
    throw new Error("invalid BIP39 mnemonic");
  }
  // @scure/bip39 returns entropy as Uint8Array (or hex in older versions).
  const entropyRaw = mnemonicToEntropy(mnemonic, wordlist) as string | Uint8Array;
  const entropy =
    typeof entropyRaw === "string" ? hexToBytes(entropyRaw) : entropyRaw;
  // bip32utils BIP32Key.fromEntropy(entropy) == HMAC-SHA512("Bitcoin seed", entropy)
  // == HDKey.fromMasterSeed(entropy) when the master seed material is raw entropy.
  const hd = HDKey.fromMasterSeed(entropy);
  if (!hd.privateKey || !hd.chainCode) {
    throw new Error("failed to derive BIP32 root from entropy");
  }
  return { privateKey: hd.privateKey, chainCode: hd.chainCode };
}

function bip32HardenedChild(
  parentPriv: Uint8Array,
  parentCc: Uint8Array,
  index: number
): { privateKey: Uint8Array; chainCode: Uint8Array } {
  const data = new Uint8Array(37);
  data[0] = 0x00;
  data.set(parentPriv, 1);
  const hardIndex = (0x80000000 + index) >>> 0;
  new DataView(data.buffer).setUint32(33, hardIndex, false);
  const I = hmac(sha512, parentCc, data);
  const IL = I.slice(0, 32);
  const IR = I.slice(32, 64);
  const ILn = BigInt("0x" + bytesToHex(IL));
  const pkn = BigInt("0x" + bytesToHex(parentPriv));
  const child = (ILn + pkn) % CURVE_ORDER;
  return {
    privateKey: hexToBytes(child.toString(16).padStart(64, "0")),
    chainCode: IR,
  };
}

function deriveIndex(factor: string, level: number): number {
  const hash = sha256(new TextEncoder().encode(factor + String(level)));
  const hashInt = BigInt("0x" + bytesToHex(hash));
  return Number(hashInt % 2147483647n);
}

export function deriveSecurePath(
  privKey: Uint8Array,
  chainCode: Uint8Array,
  factor: string
): { privateKey: Uint8Array; chainCode: Uint8Array } {
  let cur = { privateKey: privKey, chainCode };
  for (let level = 0; level < 4; level++) {
    cur = bip32HardenedChild(cur.privateKey, cur.chainCode, deriveIndex(factor, level));
  }
  return cur;
}

const B58 =
  "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

function base58Encode(bytes: Uint8Array): string {
  let n = 0n;
  for (const b of bytes) n = n * 256n + BigInt(b);
  const chars: string[] = [];
  while (n > 0n) {
    chars.push(B58[Number(n % 58n)]!);
    n = n / 58n;
  }
  for (const b of bytes) {
    if (b !== 0) break;
    chars.push("1");
  }
  return chars.reverse().join("");
}

export function getP2PKH(compressedPubKey: Uint8Array): string {
  const s = sha256(compressedPubKey);
  const r = ripemd160(s);
  const payload = new Uint8Array(21);
  payload[0] = 0x00;
  payload.set(r, 1);
  const checksum = sha256(sha256(payload)).slice(0, 4);
  const full = new Uint8Array(25);
  full.set(payload);
  full.set(checksum, 21);
  return base58Encode(full);
}

export function materialFromPrivCc(
  privateKey: Uint8Array,
  chainCode: Uint8Array
): KeyMaterial {
  const publicKey = secp256k1.getPublicKey(privateKey, true);
  return {
    privateKey,
    chainCode,
    publicKey,
    publicKeyHex: bytesToHex(publicKey),
    address: getP2PKH(publicKey),
  };
}

export function deriveMaterial(
  parent: { privateKey: Uint8Array; chainCode: Uint8Array },
  factor: string
): KeyMaterial {
  const next = deriveSecurePath(parent.privateKey, parent.chainCode, factor);
  return materialFromPrivCc(next.privateKey, next.chainCode);
}

/** K0 from mnemonic + second_factor (user password / SF). */
export function deriveK0(mnemonic: string, secondFactor: string): KeyMaterial {
  const root = rootFromMnemonic(mnemonic);
  return deriveMaterial(root, secondFactor);
}

/** Walk n steps from K0 with main factor (K0 is step 0). */
export function walkMain(
  k0: KeyMaterial,
  secondFactor: string,
  steps: number
): KeyMaterial {
  let cur = k0;
  for (let i = 0; i < steps; i++) {
    cur = deriveMaterial(cur, secondFactor);
  }
  return cur;
}

/** Per-site peer factor: second_factor + siteId */
export function siteFactor(secondFactor: string, siteId: string): string {
  return secondFactor + siteId;
}

/**
 * Deterministic site password from branch tip key material + site + counter.
 * Used so passwords are generated, not user-invented, after inception.
 */
export function generateSitePassword(
  branchKey: KeyMaterial,
  siteId: string,
  counter: number
): string {
  const preimage =
    "yada-site-pw-v1|" +
    bytesToHex(branchKey.privateKey) +
    "|" +
    siteId +
    "|" +
    String(counter);
  return bytesToHex(sha256(new TextEncoder().encode(preimage)));
}
