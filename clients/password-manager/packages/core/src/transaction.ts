import { secp256k1 } from "@noble/curves/secp256k1";
import { sha256 } from "@noble/hashes/sha256";
import { bytesToBase64, bytesToHex } from "./bytes.js";
import { sha256Hex } from "./hash.js";
import type { KeyMaterial } from "./derive.js";

export interface TxOutput {
  to: string;
  value: number;
}

export interface TxInput {
  id: string;
}

export interface TxFields {
  publicKey: string;
  time: number;
  fee?: number;
  masternodeFee?: number;
  inputs?: TxInput[];
  outputs: TxOutput[];
  prerotatedKeyHash: string;
  twicePrerotatedKeyHash: string;
  publicKeyHash: string;
  prevPublicKeyHash: string;
  relationshipHash?: string;
  relationship?: unknown;
  dhPublicKey?: string;
  rid?: string;
  requesterRid?: string;
  requestedRid?: string;
  version?: number;
}

export interface SignedTxn {
  time: number;
  rid: string;
  id: string;
  relationship: unknown;
  relationship_hash: string;
  public_key: string;
  dh_public_key: string;
  fee: number;
  masternode_fee: number;
  hash: string;
  inputs: TxInput[];
  outputs: TxOutput[];
  version: number;
  private: boolean;
  never_expire: boolean;
  prerotated_key_hash: string;
  twice_prerotated_key_hash: string;
  public_key_hash: string;
  prev_public_key_hash: string;
  requester_rid?: string;
  requested_rid?: string;
}

export function buildTxHash(f: TxFields): string {
  const inputs = f.inputs ?? [];
  const inputsConcat = inputs
    .map((i) => i.id)
    .sort((a, b) => {
      const al = a.toLowerCase();
      const bl = b.toLowerCase();
      return al < bl ? -1 : al > bl ? 1 : 0;
    })
    .join("");

  const outputsConcat = [...f.outputs]
    .sort((a, b) => {
      const al = a.to.toLowerCase();
      const bl = b.to.toLowerCase();
      return al < bl ? -1 : al > bl ? 1 : 0;
    })
    .map((o) => o.to + o.value.toFixed(8))
    .join("");

  const fee = f.fee ?? 0;
  const mn = f.masternodeFee ?? 0;
  const preimage =
    f.publicKey +
    String(f.time) +
    (f.dhPublicKey ?? "") +
    (f.rid ?? "") +
    (f.relationshipHash ?? "") +
    fee.toFixed(8) +
    mn.toFixed(8) +
    (f.requesterRid ?? "") +
    (f.requestedRid ?? "") +
    inputsConcat +
    outputsConcat +
    String(f.version ?? 7) +
    f.prerotatedKeyHash +
    f.twicePrerotatedKeyHash +
    f.publicKeyHash +
    f.prevPublicKeyHash;

  return sha256Hex(preimage);
}

/** base64(DER(secp256k1.sign(sha256(utf8(txHashHex))))) — matches node _sign */
export function signTxHash(txHashHex: string, privateKey: Uint8Array): string {
  const digest = sha256(new TextEncoder().encode(txHashHex));
  const sig = secp256k1.sign(digest, privateKey);
  return bytesToBase64(sig.toDERRawBytes());
}

export function signUsername(username: string, privateKey: Uint8Array): string {
  const digest = sha256(new TextEncoder().encode(username));
  const sig = secp256k1.sign(digest, privateKey);
  return bytesToBase64(sig.toDERRawBytes());
}

export function buildAndSignTxn(
  signer: KeyMaterial,
  fields: Omit<TxFields, "publicKey" | "publicKeyHash"> & {
    publicKeyHash?: string;
    publicKey?: string;
  }
): SignedTxn {
  const publicKey = fields.publicKey ?? signer.publicKeyHex;
  const publicKeyHash = fields.publicKeyHash ?? signer.address;
  const relationshipHash = fields.relationshipHash ?? "";
  const time = fields.time;
  const fee = fields.fee ?? 0;
  const full: TxFields = {
    ...fields,
    publicKey,
    publicKeyHash,
    relationshipHash,
    fee,
  };
  const hash = buildTxHash(full);
  const id = signTxHash(hash, signer.privateKey);
  return {
    time,
    rid: fields.rid ?? "",
    id,
    relationship: fields.relationship ?? "",
    relationship_hash: relationshipHash,
    public_key: publicKey,
    dh_public_key: fields.dhPublicKey ?? "",
    fee,
    masternode_fee: fields.masternodeFee ?? 0,
    hash,
    inputs: fields.inputs ?? [],
    outputs: fields.outputs,
    version: fields.version ?? 7,
    private: false,
    never_expire: false,
    prerotated_key_hash: fields.prerotatedKeyHash,
    twice_prerotated_key_hash: fields.twicePrerotatedKeyHash,
    public_key_hash: publicKeyHash,
    prev_public_key_hash: fields.prevPublicKeyHash,
  };
}

export function materialDebugHex(m: KeyMaterial): {
  privateKey: string;
  chainCode: string;
  publicKey: string;
  address: string;
} {
  return {
    privateKey: bytesToHex(m.privateKey),
    chainCode: bytesToHex(m.chainCode),
    publicKey: m.publicKeyHex,
    address: m.address,
  };
}
