import {
  buildAndSignTxn,
  deriveMaterial,
  sha256Hex,
  type SignedTxn,
  type VaultIdentity,
} from "@yadacoin/password-core";

export interface StoreMeta {
  title: string;
  description?: string;
  filename?: string;
  mime?: string;
  size?: number;
  type?: string;
  file_id: string;
  share_url: string;
  thumbnail_file_id?: string;
  thumbnail_share_url?: string;
}

function filePreimage(meta: StoreMeta): string {
  return (
    "sia" +
    meta.file_id +
    meta.title +
    (meta.description || "") +
    "" +
    "" +
    (meta.share_url || "") +
    (meta.thumbnail_file_id || "") +
    (meta.thumbnail_share_url || "") +
    (meta.type || "") +
    "" +
    "" +
    "" +
    "" +
    ""
  );
}

function fileBody(meta: StoreMeta): Record<string, unknown> {
  const file: Record<string, unknown> = {
    backend: "sia",
    file_id: meta.file_id,
    title: meta.title,
    description: meta.description || "",
    keywords: [],
    share_url: meta.share_url || "",
  };
  if (meta.filename) file.filename = meta.filename;
  if (meta.mime) file.mime_type = meta.mime;
  if (meta.size != null) file.size = meta.size;
  if (meta.thumbnail_file_id) file.thumbnail_file_id = meta.thumbnail_file_id;
  if (meta.thumbnail_share_url) file.thumbnail_share_url = meta.thumbnail_share_url;
  if (meta.type) file.type = meta.type;
  return file;
}

export function announceFile(identity: VaultIdentity, meta: StoreMeta): SignedTxn[] {
  if (!identity.mainDepth) throw new Error("broadcast inception before announcing a file");
  const tip = identity.tipSigner;
  const child = deriveMaterial(tip, identity.secondFactor);
  const grand = deriveMaterial(child, identity.secondFactor);
  const great = deriveMaterial(grand, identity.secondFactor);
  const relationshipHash = sha256Hex(filePreimage(meta));
  const time = Math.floor(Date.now() / 1000);
  const unconfirmed = buildAndSignTxn(tip, {
    time,
    outputs: [{ to: child.address, value: 0 }],
    prerotatedKeyHash: child.address,
    twicePrerotatedKeyHash: grand.address,
    prevPublicKeyHash: identity.tipPrevPkh || "",
    relationshipHash,
    relationship: { file: fileBody(meta) },
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
