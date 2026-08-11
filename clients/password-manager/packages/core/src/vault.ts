/**
 * Client-owned password vault workflow.
 *
 * 1. createVaultSeed + user second_factor → K0
 * 2. buildInceptionTxn → IdentityAnnouncement (POST /transaction)
 * 3. registerSite → BranchAnnouncement dual-commit (POST /transaction)
 *    + off-chain counter-0 root + counter-1 password dual-commit
 * 4. rotateSitePassword → per-site ratchet 1:1 with password hashes in relationship
 */
import {
  deriveK0,
  deriveMaterial,
  generateSeedPhrase,
  generateSitePassword,
  isValidSeedPhrase,
  siteFactor,
  walkMain,
  type KeyMaterial,
} from "./derive.js";
import { hashPassword, sha256Hex } from "./hash.js";
import {
  branchRelationshipDict,
  branchRelationshipHash,
  buildPasswordRelationshipJson,
  identityRelationshipDict,
  identityRelationshipHash,
  type PasswordDualCommit,
} from "./relationship.js";
import { buildAndSignTxn, signUsername, type SignedTxn } from "./transaction.js";

export interface VaultIdentity {
  mnemonic: string;
  secondFactor: string;
  username: string;
  identityType: string;
  usernameSignature: string;
  k0: KeyMaterial;
  mainDepth: number;
  tipSigner: KeyMaterial;
  tipPrevPkh: string;
  inceptionPublicKeyHash: string;
}

export interface SiteRegistration {
  siteId: string;
  branchPeer: string;
  kp0: KeyMaterial;
  tip: KeyMaterial;
  counter: number;
  tipPrevPkh: string;
  currentPassword: string;
  nextPassword: string;
  branchInceptionPkh: string;
}

export interface NodeApi {
  baseUrl: string;
  fetch?: typeof fetch;
}

async function httpJson(
  api: NodeApi,
  path: string,
  init?: RequestInit
): Promise<{ ok: boolean; status: number; body: any }> {
  const fetchImpl = api.fetch ?? globalThis.fetch.bind(globalThis);
  const res = await fetchImpl(api.baseUrl.replace(/\/+$/, "") + path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
  });
  const text = await res.text();
  let body: any;
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text };
  }
  return { ok: res.ok, status: res.status, body };
}

export function createVaultSeed(strength: 128 | 256 = 128): string {
  return generateSeedPhrase(strength);
}

export function unlockIdentity(
  mnemonic: string,
  secondFactor: string,
  username: string,
  opts?: { identityType?: string; mainDepth?: number; tipPrevPkh?: string }
): VaultIdentity {
  if (!isValidSeedPhrase(mnemonic)) throw new Error("invalid seed phrase");
  if (!secondFactor) throw new Error("second_factor / master password required");
  if (!username?.trim()) throw new Error("username required");

  const k0 = deriveK0(mnemonic, secondFactor);
  const usernameSignature = signUsername(username.trim(), k0.privateKey);
  const mainDepth = opts?.mainDepth ?? 0;
  const tipSigner = walkMain(k0, secondFactor, mainDepth);
  return {
    mnemonic,
    secondFactor,
    username: username.trim(),
    identityType: opts?.identityType ?? "social",
    usernameSignature,
    k0,
    mainDepth,
    tipSigner,
    tipPrevPkh: opts?.tipPrevPkh ?? "",
    inceptionPublicKeyHash: k0.address,
  };
}

export function buildInceptionTxn(
  identity: VaultIdentity,
  time = Math.floor(Date.now() / 1000)
): SignedTxn {
  const k0 = identity.k0;
  const k1 = deriveMaterial(k0, identity.secondFactor);
  const k2 = deriveMaterial(k1, identity.secondFactor);
  const relHash = identityRelationshipHash(
    identity.username,
    identity.usernameSignature,
    identity.identityType
  );
  const relationship = identityRelationshipDict(
    identity.username,
    identity.usernameSignature,
    identity.identityType
  );
  return buildAndSignTxn(k0, {
    time,
    fee: 0,
    outputs: [{ to: k1.address, value: 0 }],
    prerotatedKeyHash: k1.address,
    twicePrerotatedKeyHash: k2.address,
    prevPublicKeyHash: "",
    relationshipHash: relHash,
    relationship,
  });
}

export function identityAfterInception(identity: VaultIdentity): VaultIdentity {
  const k1 = deriveMaterial(identity.k0, identity.secondFactor);
  return {
    ...identity,
    mainDepth: 1,
    tipSigner: k1,
    tipPrevPkh: identity.k0.address,
  };
}

export async function broadcastTxns(
  api: NodeApi,
  txns: SignedTxn | SignedTxn[]
): Promise<{ ok: boolean; status: number; body: any }> {
  const list = Array.isArray(txns) ? txns : [txns];
  return httpJson(api, "/transaction?username_signature=1", {
    method: "POST",
    body: JSON.stringify(list),
  });
}

/**
 * Canonical per-site branch id = origin (scheme + FQDN + port).
 * Examples: https://example.com , http://localhost:8101 , https://app.example.com:8443
 * Path/query/hash are stripped. Default ports 80/443 are omitted by URL.origin.
 */
export function normalizeSiteId(siteId: string): string {
  const raw = siteId.trim();
  if (!raw) return "";
  try {
    const withScheme = raw.includes("://") ? raw : `https://${raw}`;
    const u = new URL(withScheme);
    if (u.protocol !== "http:" && u.protocol !== "https:") {
      throw new Error("site origin must be http(s)");
    }
    // URL.origin is scheme://host:port with FQDN; default ports omitted
    return u.origin.toLowerCase();
  } catch {
    return raw.toLowerCase();
  }
}

export async function registerSite(
  api: NodeApi,
  identity: VaultIdentity,
  siteId: string,
  time = Math.floor(Date.now() / 1000)
): Promise<{
  site: SiteRegistration;
  mainTxns: SignedTxn[];
  offchainRoot: SignedTxn;
  offchainPassword: SignedTxn;
  identity: VaultIdentity;
}> {
  const branchPeer = normalizeSiteId(siteId);
  const sf = identity.secondFactor;
  const kn = identity.tipSigner;
  const kn1 = deriveMaterial(kn, sf);
  const kn2 = deriveMaterial(kn1, sf);
  const kn3 = deriveMaterial(kn2, sf);

  const peerFactor = siteFactor(sf, branchPeer);
  const kp0 = deriveMaterial(kn, peerFactor);
  const kp1 = deriveMaterial(kp0, peerFactor);
  const kp2 = deriveMaterial(kp1, peerFactor);
  const kp3 = deriveMaterial(kp2, peerFactor);

  const branchHash = branchRelationshipHash(kp0.address, kp1.address);
  const branchRel = branchRelationshipDict(kp0.address, kp1.address);

  const unconfirmed = buildAndSignTxn(kn, {
    time,
    outputs: [{ to: kn1.address, value: 0 }],
    prerotatedKeyHash: kn1.address,
    twicePrerotatedKeyHash: kn2.address,
    prevPublicKeyHash: identity.tipPrevPkh || kn.address,
    relationshipHash: branchHash,
    relationship: branchRel,
  });

  const confirming = buildAndSignTxn(kn1, {
    time: time + 1,
    outputs: [{ to: kn2.address, value: 0 }],
    prerotatedKeyHash: kn2.address,
    twicePrerotatedKeyHash: kn3.address,
    prevPublicKeyHash: kn.address,
    relationshipHash: "",
    relationship: "",
  });

  const mainRes = await broadcastTxns(api, [unconfirmed, confirming]);
  if (!mainRes.ok && mainRes.body?.status === false) {
    throw new Error(
      mainRes.body?.message || `branch broadcast failed (${mainRes.status})`
    );
  }

  const rootTxn = buildAndSignTxn(kp0, {
    time: time + 2,
    outputs: [{ to: kp1.address, value: 0 }],
    prerotatedKeyHash: kp1.address,
    twicePrerotatedKeyHash: kp2.address,
    prevPublicKeyHash: kn1.address,
    relationshipHash: "",
    relationship: "",
  });

  const rootRes = await httpJson(api, "/password-rotation/offchain", {
    method: "POST",
    body: JSON.stringify({
      branch_peer: branchPeer,
      counter: 0,
      branch_inception_public_key_hash: kp0.address,
      inception_public_key_hash: identity.inceptionPublicKeyHash,
      txn: rootTxn,
    }),
  });
  if (!rootRes.ok || rootRes.body?.status === false) {
    throw new Error(
      rootRes.body?.message || `offchain root failed (${rootRes.status})`
    );
  }

  const pwCurrent = generateSitePassword(kp1, branchPeer, 1);
  const pwNext = generateSitePassword(kp2, branchPeer, 2);
  const commit: PasswordDualCommit = {
    prerotated_password_hash: hashPassword(pwCurrent),
    twice_prerotated_password_hash: hashPassword(pwNext),
  };
  const relJson = buildPasswordRelationshipJson(commit);
  const relHash = sha256Hex(relJson);

  const step1Txn = buildAndSignTxn(kp1, {
    time: time + 3,
    outputs: [{ to: kp2.address, value: 0 }],
    prerotatedKeyHash: kp2.address,
    twicePrerotatedKeyHash: kp3.address,
    prevPublicKeyHash: kp0.address,
    relationshipHash: relHash,
    relationship: relJson,
  });

  const stepRes = await httpJson(api, "/password-rotation/offchain", {
    method: "POST",
    body: JSON.stringify({
      branch_peer: branchPeer,
      counter: 1,
      branch_inception_public_key_hash: kp0.address,
      inception_public_key_hash: identity.inceptionPublicKeyHash,
      txn: step1Txn,
    }),
  });
  if (!stepRes.ok || stepRes.body?.status === false) {
    throw new Error(
      stepRes.body?.message || `offchain password step failed (${stepRes.status})`
    );
  }

  const nextIdentity: VaultIdentity = {
    ...identity,
    mainDepth: identity.mainDepth + 2,
    tipSigner: kn2,
    tipPrevPkh: kn1.address,
  };

  const site: SiteRegistration = {
    siteId,
    branchPeer,
    kp0,
    tip: kp2,
    counter: 1,
    tipPrevPkh: kp1.address,
    currentPassword: pwCurrent,
    nextPassword: pwNext,
    branchInceptionPkh: kp0.address,
  };

  return {
    site,
    mainTxns: [unconfirmed, confirming],
    offchainRoot: rootTxn,
    offchainPassword: step1Txn,
    identity: nextIdentity,
  };
}

export async function rotateSitePassword(
  api: NodeApi,
  identity: VaultIdentity,
  site: SiteRegistration,
  time = Math.floor(Date.now() / 1000)
): Promise<{
  site: SiteRegistration;
  txn: SignedTxn;
  password: string;
  authenticated: true;
}> {
  const peerFactor = siteFactor(identity.secondFactor, site.branchPeer);
  const signer = site.tip;
  const next = deriveMaterial(signer, peerFactor);
  const twice = deriveMaterial(next, peerFactor);

  const newTwicePassword = generateSitePassword(
    next,
    site.branchPeer,
    site.counter + 2
  );
  const commit: PasswordDualCommit = {
    prerotated_password_hash: hashPassword(site.nextPassword),
    twice_prerotated_password_hash: hashPassword(newTwicePassword),
  };
  const relJson = buildPasswordRelationshipJson(commit);
  const relHash = sha256Hex(relJson);

  const txn = buildAndSignTxn(signer, {
    time,
    outputs: [{ to: next.address, value: 0 }],
    prerotatedKeyHash: next.address,
    twicePrerotatedKeyHash: twice.address,
    prevPublicKeyHash: site.tipPrevPkh,
    relationshipHash: relHash,
    relationship: relJson,
  });

  const nextCounter = site.counter + 1;
  // Backend enforces rotation: password must match tip.pre and txn advances dual-commit.
  const res = await httpJson(api, "/password-rotation/verify", {
    method: "POST",
    body: JSON.stringify({
      branch_peer: site.branchPeer,
      password: site.currentPassword,
      counter: nextCounter,
      branch_inception_public_key_hash: site.branchInceptionPkh,
      inception_public_key_hash: identity.inceptionPublicKeyHash,
      txn,
    }),
  });
  if (!res.ok || res.body?.status === false || !res.body?.authenticated) {
    throw new Error(res.body?.message || `sign-in/rotate failed (${res.status})`);
  }

  const usedPassword = site.currentPassword;
  const updated: SiteRegistration = {
    ...site,
    tip: next,
    counter: nextCounter,
    tipPrevPkh: signer.address,
    currentPassword: site.nextPassword,
    nextPassword: newTwicePassword,
  };

  // password = the one just consumed at sign-in; site.currentPassword is now the next unlock secret
  return { site: updated, txn, password: usedPassword, authenticated: true as const };
}

export async function fetchSiteTip(api: NodeApi, branchPeer: string) {
  return httpJson(
    api,
    `/password-rotation/offchain/tip?branch_peer=${encodeURIComponent(branchPeer)}`
  );
}
