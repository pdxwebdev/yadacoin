import { secp256k1 } from "@noble/curves/secp256k1";
import { keccak_256 } from "@noble/hashes/sha3";
import { HDKey } from "@scure/bip32";
import { mnemonicToSeedSync, validateMnemonic } from "@scure/bip39";
import { wordlist } from "@scure/bip39/wordlists/english";
import { bytesToHex, hexToBytes } from "./bytes.js";

export const BASE_CHAIN_ID = 8453;
export const BASE_RPC = "https://mainnet.base.org";
export const BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
export const WYDA_POOL = "0x7beCd9Bbe91DE47eD60da5DE70eb280f947Dd44B";
export const BASE_WYDA = "0x1E9c172610b6251A1e3Bf916b9Ea47f506072651";
export const BASE_BRIDGE = "0xae07D13f34987832f6C6bE572616E17d6FEc94Bb";

function concat(parts: Uint8Array[]): Uint8Array {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}

function rlpBytes(data: Uint8Array): Uint8Array {
  if (data.length === 1 && data[0]! < 0x80) return data;
  return concat([rlpLen(0x80, data.length), data]);
}

function rlpLen(offset: number, length: number): Uint8Array {
  if (length < 56) return new Uint8Array([offset + length]);
  let hex = length.toString(16);
  if (hex.length % 2) hex = "0" + hex;
  const len = hexToBytes(hex);
  return concat([new Uint8Array([offset + 55 + len.length]), len]);
}

type Rlp = Uint8Array | Rlp[];

function rlp(item: Rlp): Uint8Array {
  if (item instanceof Uint8Array) return rlpBytes(item);
  const payload = concat(item.map((x) => rlp(x)));
  return concat([rlpLen(0xc0, payload.length), payload]);
}

function u256(n: bigint): Uint8Array {
  if (n === 0n) return new Uint8Array();
  let hex = n.toString(16);
  if (hex.length % 2) hex = "0" + hex;
  return hexToBytes(hex);
}

function addr(hex: string): Uint8Array {
  return hexToBytes(hex.toLowerCase());
}

function pad32(n: bigint): string {
  return n.toString(16).padStart(64, "0");
}

function baseKey(mnemonic: string): Uint8Array {
  if (!validateMnemonic(mnemonic, wordlist)) throw new Error("invalid BIP39 mnemonic");
  const child = HDKey.fromMasterSeed(mnemonicToSeedSync(mnemonic)).derive("m/2'");
  if (!child.privateKey) throw new Error("failed to derive Base key");
  return child.privateKey;
}

async function rpc(method: string, params: unknown[]): Promise<string> {
  const res = await fetch(BASE_RPC, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  const data = await res.json();
  if (data.error) throw new Error(data.error.message || "base rpc failed");
  return data.result;
}

function recoveryBit(sighash: Uint8Array, key: Uint8Array, sig: { r: bigint; s: bigint; recovery?: number }): number {
  if (typeof sig.recovery === "number") return sig.recovery;
  const pub = secp256k1.getPublicKey(key, false);
  const compact = new Uint8Array(64);
  const r = u256(sig.r);
  const s = u256(sig.s);
  compact.set(r, 32 - r.length);
  compact.set(s, 64 - s.length);
  for (const bit of [0, 1]) {
    const rec = secp256k1.Signature.fromCompact(compact).addRecoveryBit(bit).recoverPublicKey(sighash).toRawBytes(false);
    if (bytesToHex(rec) === bytesToHex(pub)) return bit;
  }
  throw new Error("could not recover signature");
}

function signTx(
  key: Uint8Array,
  nonce: bigint,
  gas: bigint,
  to: string,
  data: string,
  maxFee: bigint
): string {
  const fields: Rlp[] = [
    u256(BigInt(BASE_CHAIN_ID)),
    u256(nonce),
    u256(1_000_000n),
    u256(maxFee),
    u256(gas),
    addr(to),
    u256(0n),
    hexToBytes(data),
    [],
  ];
  const sighash = keccak_256(concat([new Uint8Array([2]), rlp(fields)]));
  const sig = secp256k1.sign(sighash, key);
  const raw = concat([
    new Uint8Array([2]),
    rlp([...fields, u256(BigInt(recoveryBit(sighash, key, sig))), u256(sig.r), u256(sig.s)]),
  ]);
  return "0x" + bytesToHex(raw);
}

function addressFromKey(key: Uint8Array): string {
  return "0x" + bytesToHex(keccak_256(secp256k1.ProjectivePoint.fromHex(secp256k1.getPublicKey(key, false)).toRawBytes(false).slice(1)).slice(-20));
}

export async function signUsdcPermit(mnemonic: string, amount?: string): Promise<{
  owner: string;
  spender: string;
  value: string;
  nonce: string;
  deadline: string;
  v: string;
  r: string;
  s: string;
}> {
  const key = baseKey(mnemonic);
  const owner = addressFromKey(key);
  const balance = BigInt(await rpc("eth_call", [{ to: BASE_USDC, data: "0x70a08231" + owner.slice(2).padStart(64, "0") }, "latest"]));
  if (balance === 0n) throw new Error("no USDC on the Base address");
  const requested = amount ? BigInt(Math.round(Number(amount) * 1e6)) : balance;
  if (!requested || requested <= 0n) throw new Error("purchase amount is required");
  if (requested > balance) throw new Error("USDC balance is below the purchase amount");
  const value = requested;
  const nonce = BigInt(await rpc("eth_call", [{ to: BASE_USDC, data: "0x7ecebe00" + owner.slice(2).padStart(64, "0") }, "latest"]));
  const domain = await rpc("eth_call", [{ to: BASE_USDC, data: "0x3644e515" }, "latest"]);
  const deadline = BigInt(Math.floor(Date.now() / 1000) + 7 * 24 * 60 * 60);
  const typehash = keccak_256(new TextEncoder().encode("Permit(address owner,address spender,uint256 value,uint256 nonce,uint256 deadline)"));
  const struct = keccak_256(hexToBytes(
    bytesToHex(typehash) +
    owner.slice(2).padStart(64, "0") +
    BASE_BRIDGE.slice(2).toLowerCase().padStart(64, "0") +
    pad32(value) +
    pad32(nonce) +
    pad32(deadline)
  ));
  const sighash = keccak_256(concat([new Uint8Array([0x19, 0x01]), hexToBytes(domain.slice(2)), struct]));
  const sig = secp256k1.sign(sighash, key);
  const bit = recoveryBit(sighash, key, sig);
  return {
    owner,
    spender: BASE_BRIDGE,
    value: value.toString(),
    nonce: nonce.toString(),
    deadline: deadline.toString(),
    v: String(27 + bit),
    r: "0x" + pad32(sig.r),
    s: "0x" + pad32(sig.s),
  };
}

export async function swapUsdcToWyda(mnemonic: string): Promise<{ approve: string; swap: string; amount: string }> {
  const key = baseKey(mnemonic);
  const from = "0x" + bytesToHex(keccak_256(secp256k1.ProjectivePoint.fromHex(secp256k1.getPublicKey(key, false)).toRawBytes(false).slice(1)).slice(-20));
  const usdc = BigInt(await rpc("eth_call", [{ to: BASE_USDC, data: "0x70a08231" + from.slice(2).padStart(64, "0") }, "latest"]));
  if (usdc === 0n) throw new Error("no USDC on the Base address");
  const eth = BigInt(await rpc("eth_getBalance", [from, "latest"]));
  if (eth === 0n) throw new Error("Send a little ETH for gas to " + from + " before the swap");
  const reserveUsdc = BigInt(await rpc("eth_call", [{ to: WYDA_POOL, data: "0x5eb94d2a" }, "latest"]));
  const reserveWyda = BigInt(await rpc("eth_call", [{ to: WYDA_POOL, data: "0x80cf21ce" }, "latest"]));
  if (reserveUsdc === 0n || reserveWyda === 0n) throw new Error("pool is empty");
  const out = (reserveWyda * usdc) / (reserveUsdc + usdc);
  const minOut = (out * 99n) / 100n;
  const nonce = BigInt(await rpc("eth_getTransactionCount", [from, "pending"]));
  const gasPrice = BigInt(await rpc("eth_gasPrice", []));
  const maxFee = gasPrice * 2n + 1_000_000n;
  const approveData = "0x095ea7b3" + WYDA_POOL.slice(2).toLowerCase().padStart(64, "0") + pad32(usdc);
  const swapData = "0x36480f08" + pad32(usdc) + pad32(minOut);
  const approve = signTx(key, nonce, 80_000n, BASE_USDC, approveData, maxFee);
  const swap = signTx(key, nonce + 1n, 160_000n, WYDA_POOL, swapData, maxFee);
  const approveHash = await rpc("eth_sendRawTransaction", [approve]);
  const swapHash = await rpc("eth_sendRawTransaction", [swap]);
  return { approve: approveHash, swap: swapHash, amount: usdc.toString() };
}

function encodeString(value: string): string {
  const bytes = new TextEncoder().encode(value);
  const words = Math.ceil(bytes.length / 32) || 1;
  const padded = new Uint8Array(words * 32);
  padded.set(bytes);
  return pad32(BigInt(bytes.length)) + bytesToHex(padded);
}

export async function baseTokenBalance(mnemonic: string, token: string): Promise<string> {
  const key = baseKey(mnemonic);
  const from = "0x" + bytesToHex(keccak_256(secp256k1.ProjectivePoint.fromHex(secp256k1.getPublicKey(key, false)).toRawBytes(false).slice(1)).slice(-20));
  return BigInt(await rpc("eth_call", [{ to: token, data: "0x70a08231" + from.slice(2).padStart(64, "0") }, "latest"])).toString();
}

export async function unwrapWyda(mnemonic: string, yadacoinAddress: string): Promise<{ burn: string; amount: string }> {
  if (!yadacoinAddress || yadacoinAddress.length > 42) throw new Error("Yadacoin address is missing");
  const key = baseKey(mnemonic);
  const from = "0x" + bytesToHex(keccak_256(secp256k1.ProjectivePoint.fromHex(secp256k1.getPublicKey(key, false)).toRawBytes(false).slice(1)).slice(-20));
  const amount = BigInt(await rpc("eth_call", [{ to: BASE_WYDA, data: "0x70a08231" + from.slice(2).padStart(64, "0") }, "latest"]));
  if (amount === 0n) throw new Error("no WYDA on the Base address");
  const eth = BigInt(await rpc("eth_getBalance", [from, "latest"]));
  if (eth === 0n) throw new Error("Send a little ETH for gas to " + from + " before the unwrap");
  const selector = bytesToHex(keccak_256(new TextEncoder().encode("unwrap(address,uint256,string)"))).slice(0, 8);
  const data =
    "0x" +
    selector +
    BASE_WYDA.slice(2).toLowerCase().padStart(64, "0") +
    pad32(amount) +
    pad32(96n) +
    encodeString(yadacoinAddress);
  const nonce = BigInt(await rpc("eth_getTransactionCount", [from, "pending"]));
  const gasPrice = BigInt(await rpc("eth_gasPrice", []));
  const raw = signTx(key, nonce, 180_000n, BASE_BRIDGE, data, gasPrice * 2n + 1_000_000n);
  const burn = await rpc("eth_sendRawTransaction", [raw]);
  return { burn, amount: amount.toString() };
}
