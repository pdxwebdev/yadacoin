import { deriveMaterial } from "./derive.js";
import { sha256Hex } from "./hash.js";
import { buildAndSignTxn, type SignedTxn } from "./transaction.js";
import type { VaultIdentity } from "./vault.js";

export function announceUnwrap(identity: VaultIdentity, burn: string, amount: string, yadacoinAddress: string): SignedTxn[] {
  if (!identity.mainDepth) throw new Error("broadcast inception before requesting an unwrap");
  const tip = identity.tipSigner;
  const child = deriveMaterial(tip, identity.secondFactor);
  const grand = deriveMaterial(child, identity.secondFactor);
  const great = deriveMaterial(grand, identity.secondFactor);
  const relationship = "unwrap" + burn + amount + yadacoinAddress;
  const relationshipHash = sha256Hex(relationship);
  const time = Math.floor(Date.now() / 1000);
  const unconfirmed = buildAndSignTxn(tip, {
    time,
    outputs: [{ to: child.address, value: 0 }],
    prerotatedKeyHash: child.address,
    twicePrerotatedKeyHash: grand.address,
    prevPublicKeyHash: identity.tipPrevPkh || "",
    relationshipHash,
    relationship,
  });
  const confirming = buildAndSignTxn(child, {
    time,
    outputs: [{ to: grand.address, value: 0 }],
    prerotatedKeyHash: grand.address,
    twicePrerotatedKeyHash: great.address,
    prevPublicKeyHash: tip.address,
    relationshipHash: "",
    relationship: "",
  });
  const inception = identity.k0.address;
  return [
    { ...unconfirmed, counter: identity.mainDepth, inception_public_key_hash: inception },
    { ...confirming, counter: identity.mainDepth + 1, inception_public_key_hash: inception },
  ];
}
