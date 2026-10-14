import { secp256k1 } from "@noble/curves/secp256k1";
import { sha256 } from "@noble/hashes/sha2";
import { bytesToBase64, hexToBytes } from "./bytes.js";

const DOMAIN = new TextEncoder().encode("yada-pw-box-v1");

function copyBuffer(bytes: Uint8Array): ArrayBuffer {
  const out = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(out).set(bytes);
  return out;
}

export async function sealToRatchetPub(
  plaintext: string,
  recipientPubHex: string
): Promise<string> {
  const ephPriv = secp256k1.utils.randomPrivateKey();
  const ephPub = secp256k1.getPublicKey(ephPriv, true);
  const shared = secp256k1.getSharedSecret(ephPriv, hexToBytes(recipientPubHex), true);
  const x = sha256(shared);
  const material = new Uint8Array(x.length + DOMAIN.length);
  material.set(x, 0);
  material.set(DOMAIN, x.length);
  const key = await crypto.subtle.importKey(
    "raw",
    copyBuffer(sha256(material)),
    "AES-GCM",
    false,
    ["encrypt"]
  );
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: copyBuffer(nonce) },
      key,
      copyBuffer(new TextEncoder().encode(plaintext))
    )
  );
  const blob = new Uint8Array(ephPub.length + nonce.length + ct.length);
  blob.set(ephPub, 0);
  blob.set(nonce, ephPub.length);
  blob.set(ct, ephPub.length + nonce.length);
  return bytesToBase64(blob);
}
