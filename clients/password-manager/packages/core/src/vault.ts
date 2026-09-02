/**
 * Client-owned password vault workflow.
 *
 * 1. createVaultSeed + user second_factor → K0
 * 2. buildInceptionTxn → IdentityAnnouncement (POST /transaction)
 * 3. registerSite → unique off-chain branch from K0 + site origin
 *    (counter-0 root + counter-1 password dual-commit)
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
import {
  buildPasswordRelationshipJson,
  identityRelationshipDict,
  identityRelationshipHash,
} from "./relationship.js";
import { buildAndSignTxn, signUsername, type SignedTxn } from "./transaction.js";
import {
  hashPassword,
  parsePhc,
  phcSaltB64ForPassword,
  sha256Hex,
  verifyPassword,
} from "./hash.js";

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
  const url = api.baseUrl.replace(/\/+$/, "") + path;
  let res: Response;
  try {
    res = await fetchImpl(url, {
      ...init,
      credentials: init?.credentials ?? "include",
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers || {}),
      },
    });
  } catch (e) {
    const why = e instanceof Error ? e.message : String(e);
    throw new Error(
      `Failed to reach node ${api.baseUrl} (${path}): ${why}. ` +
        `On a phone use the computer's LAN IP (not 127.0.0.1). On an emulator use 10.0.2.2.`
    );
  }
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

export function isAlreadyInceptedError(message: string | undefined): boolean {
  const m = (message || "").toLowerCase();
  return (
    m.includes("already onchain") ||
    m.includes("already on-chain") ||
    m.includes("already incepted") ||
    m.includes("duplicate kel inception") ||
    m.includes("key event log already exists")
  );
}

/** Derivation steps from a KEL list: one inception, plus real rotations. */
export function kelRotationDepth(
  entries: Array<{ prev_public_key_hash?: string }> | undefined | null
): number {
  if (!Array.isArray(entries) || !entries.length) return 0;
  let inception = 0;
  let rotations = 0;
  for (const e of entries) {
    const prev = (e && e.prev_public_key_hash) || "";
    if (!prev) {
      if (!inception) inception = 1;
    } else {
      rotations += 1;
    }
  }
  return inception + rotations;
}

export async function fetchKelDepth(
  api: NodeApi,
  publicKeyHex: string
): Promise<number> {
  const kel = await httpJson(
    api,
    `/key-event-log?public_key=${encodeURIComponent(publicKeyHex)}`
  );
  if (kel.ok && Array.isArray(kel.body?.key_event_log)) {
    return kelRotationDepth(kel.body.key_event_log);
  }
  return 0;
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

export type PasswordPhcOpts = {
  passwordPhc?: string;
  nextPasswordPhc?: string;
};

export async function registerSite(
  api: NodeApi,
  identity: VaultIdentity,
  siteId: string,
  time = Math.floor(Date.now() / 1000),
  _opts?: PasswordPhcOpts & { replaceExisting?: boolean }
): Promise<{
  site: SiteRegistration;
  mainTxns: SignedTxn[];
  offchainRoot: SignedTxn;
  offchainPassword: SignedTxn;
  identity: VaultIdentity;
}> {
  const branchPeer = normalizeSiteId(siteId);
  const sf = identity.secondFactor;
  const peerFactor = siteFactor(sf, branchPeer);
  // Branch keys are derived from K0 + site origin so each site/app is unique
  // and does not consume (or collide with) the identity KEL tip.
  const kp0 = deriveMaterial(identity.k0, peerFactor);
  const kp1 = deriveMaterial(kp0, peerFactor);
  const kp2 = deriveMaterial(kp1, peerFactor);
  const kp3 = deriveMaterial(kp2, peerFactor);

  const existing = await fetchSiteTip(api, branchPeer);
  if (existing.ok && existing.body?.tip) {
    if (!_opts?.replaceExisting) {
      throw new Error(
        "site already has a branch on the node — resync instead of registering again"
      );
    }
    const resetRes = await httpJson(api, "/password-rotation/offchain/reset", {
      method: "POST",
      body: JSON.stringify({
        branch_peer: branchPeer,
        inception_public_key_hash: identity.inceptionPublicKeyHash,
      }),
    });
    if (!resetRes.ok || resetRes.body?.status === false) {
      throw new Error(
        resetRes.body?.message || "failed to replace existing site branch"
      );
    }
  }

  const pwCurrent = generateSitePassword(kp1, branchPeer, 1);
  const pwNext = generateSitePassword(kp2, branchPeer, 2);
  let rootTxn: SignedTxn | undefined;
  {
    rootTxn = buildAndSignTxn(kp0, {
      time,
      outputs: [{ to: kp1.address, value: 0 }],
      prerotatedKeyHash: kp1.address,
      twicePrerotatedKeyHash: kp2.address,
      prevPublicKeyHash: identity.k0.address,
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
  }

  const step1Commit = {
    prerotated_password_hash: hashPassword(pwCurrent),
    twice_prerotated_password_hash: hashPassword(pwNext),
  };
  const step1RelJson = buildPasswordRelationshipJson(step1Commit);
  const step1Txn = buildAndSignTxn(kp1, {
    time: time + 1,
    outputs: [{ to: kp2.address, value: 0 }],
    prerotatedKeyHash: kp2.address,
    twicePrerotatedKeyHash: kp3.address,
    prevPublicKeyHash: kp0.address,
    relationshipHash: sha256Hex(step1RelJson),
    relationship: JSON.parse(step1RelJson),
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
    mainTxns: [],
    offchainRoot: rootTxn || step1Txn,
    offchainPassword: step1Txn,
    identity,
  };
}



export function siteKeysForOrigin(
  identity: VaultIdentity,
  siteId: string
): { branchPeer: string; kp0: KeyMaterial } {
  const branchPeer = normalizeSiteId(siteId);
  return {
    branchPeer,
    kp0: deriveMaterial(identity.k0, siteFactor(identity.secondFactor, branchPeer)),
  };
}


/** Walk deterministic site passwords until one verifies against the RP next-hash. */
export function findPasswordMatchingHash(
  identity: VaultIdentity,
  siteId: string,
  expectedHash: string,
  max = 64
): { index: number; password: string; nextPassword: string } | null {
  const { branchPeer, kp0 } = siteKeysForOrigin(identity, siteId);
  const peerFactor = siteFactor(identity.secondFactor, branchPeer);
  const expectedSalt = parsePhc(expectedHash)?.salt;
  let k = kp0;
  for (let i = 1; i <= max; i++) {
    k = deriveMaterial(k, peerFactor);
    const password = generateSitePassword(k, branchPeer, i);
    if (expectedSalt && phcSaltB64ForPassword(password) !== expectedSalt) {
      continue;
    }
    if (verifyPassword(password, expectedHash)) {
      const kNext = deriveMaterial(k, peerFactor);
      return {
        index: i,
        password,
        nextPassword: generateSitePassword(kNext, branchPeer, i + 1),
      };
    }
  }
  return null;
}

export async function rotateSitePassword(
  api: NodeApi,
  identity: VaultIdentity,
  site: SiteRegistration,
  time = Math.floor(Date.now() / 1000),
  opts?: PasswordPhcOpts & { expectedHash?: string; _replaced?: boolean }
): Promise<{
  site: SiteRegistration;
  txn: SignedTxn;
  password: string;
  nextPassword: string;
  authenticated: true;
}> {
  const keys = siteKeysForOrigin(identity, site.branchPeer || site.siteId);
  const tipRes = await fetchSiteTip(api, keys.branchPeer);
  const tip = tipRes.body?.tip;
  if (!tipRes.ok || !tip) {
    throw new Error("site not registered on node");
  }
  const tipCounter = Number(tip.counter ?? site.counter ?? 0);
  const live = siteAtCounter(
    identity,
    {
      siteId: keys.branchPeer,
      branchPeer: keys.branchPeer,
      kp0: keys.kp0,
    },
    tipCounter
  );
  if (tip.prerotated_key_hash && live.tip.address !== tip.prerotated_key_hash) {
    if (opts?._replaced) {
      throw new Error(
        "branch keys do not match the tip after rebuild"
      );
    }
    const replaced = await registerSite(
      api,
      identity,
      keys.branchPeer,
      time,
      { replaceExisting: true }
    );
    return rotateSitePassword(api, identity, replaced.site, time, {
      ...opts,
      _replaced: true,
    });
  }
  let password = live.nextPassword || site.nextPassword || live.currentPassword;
  let nextReveal = "";
  if (opts?.expectedHash) {
    const found = findPasswordMatchingHash(
      identity,
      keys.branchPeer,
      opts.expectedHash
    );
    if (!found) {
      throw new Error(
        "stored next hash is not in this vault's password chain"
      );
    }
    password = found.password;
    nextReveal = found.nextPassword;
  }
  if (!password) {
    throw new Error("no site password available");
  }

  const peerFactor = siteFactor(identity.secondFactor, site.branchPeer);
  const signer = live.tip;
  const next = deriveMaterial(signer, peerFactor);
  const twice = deriveMaterial(next, peerFactor);

  const newTwicePassword = generateSitePassword(
    next,
    site.branchPeer,
    tipCounter + 2
  );
  const consumedPassword = live.currentPassword || password;
  const newPrePassword = live.nextPassword || newTwicePassword;
  const rotateRelJson = buildPasswordRelationshipJson({
    prerotated_password_hash: hashPassword(newPrePassword),
    twice_prerotated_password_hash: hashPassword(newTwicePassword),
  });
  const txn = buildAndSignTxn(signer, {
    time,
    outputs: [{ to: next.address, value: 0 }],
    prerotatedKeyHash: next.address,
    twicePrerotatedKeyHash: twice.address,
    prevPublicKeyHash: live.tipPrevPkh,
    relationshipHash: sha256Hex(rotateRelJson),
    relationship: JSON.parse(rotateRelJson),
  });

  const nextCounter = tipCounter + 1;
  const res = await httpJson(api, "/password-rotation/verify", {
    method: "POST",
    body: JSON.stringify({
      branch_peer: site.branchPeer,
      counter: nextCounter,
      password: consumedPassword,
      branch_inception_public_key_hash: site.branchInceptionPkh,
      inception_public_key_hash: identity.inceptionPublicKeyHash,
      txn,
    }),
  });
  if (!res.ok || res.body?.status === false) {
    throw new Error(res.body?.message || `sign-in/rotate failed (${res.status})`);
  }

  const usedPassword = consumedPassword;
  const updated: SiteRegistration = {
    ...live,
    tip: next,
    counter: nextCounter,
    tipPrevPkh: signer.address,
    currentPassword: live.nextPassword,
    nextPassword: newTwicePassword,
  };

  // password = the one just consumed at sign-in; site.currentPassword is now the next unlock secret
  return {
    site: updated,
    txn,
    password: usedPassword,
    nextPassword: nextReveal || newTwicePassword,
    authenticated: true as const,
  };
}


/** Rebuild one site from the node's off-chain tip (counter + password hashes). */
export async function resyncSiteFromNode(
  api: NodeApi,
  identity: VaultIdentity,
  siteId: string
): Promise<SiteRegistration> {
  const keys = siteKeysForOrigin(identity, siteId);
  const tipRes = await fetchSiteTip(api, keys.branchPeer);
  if (!tipRes.ok || tipRes.body?.status === false || !tipRes.body?.tip) {
    throw new Error("site not registered on node — register this origin first");
  }
  const tip = tipRes.body.tip;
  const counter = Number(tip.counter ?? 0);
  if (!Number.isFinite(counter) || counter < 0) {
    throw new Error("invalid tip counter on node");
  }
  const rebuilt = siteAtCounter(
    identity,
    { siteId: keys.branchPeer, branchPeer: keys.branchPeer, kp0: keys.kp0 },
    counter
  );
  if (tip.prerotated_key_hash && rebuilt.tip.address !== tip.prerotated_key_hash) {
    const replaced = await registerSite(api, identity, keys.branchPeer, undefined, {
      replaceExisting: true,
    });
    return replaced.site;
  }
  return rebuilt;
}

export async function fetchSiteTip(api: NodeApi, branchPeer: string) {
  return httpJson(
    api,
    `/password-rotation/offchain/tip?branch_peer=${encodeURIComponent(branchPeer)}`
  );
}

/** Rebuild a site registration to match an off-chain tip counter. */
export function siteAtCounter(
  identity: VaultIdentity,
  site: Pick<SiteRegistration, "siteId" | "branchPeer" | "kp0">,
  counter: number
): SiteRegistration {
  const peerFactor = siteFactor(identity.secondFactor, site.branchPeer);
  let atC = site.kp0;
  for (let i = 0; i < counter; i++) {
    atC = deriveMaterial(atC, peerFactor);
  }
  const tip = deriveMaterial(atC, peerFactor);
  return {
    siteId: site.siteId,
    branchPeer: site.branchPeer,
    kp0: site.kp0,
    tip,
    counter,
    tipPrevPkh: atC.address,
    currentPassword: generateSitePassword(atC, site.branchPeer, counter),
    nextPassword: generateSitePassword(tip, site.branchPeer, counter + 1),
    branchInceptionPkh: site.kp0.address,
  };
}

export interface VaultResyncResult {
  identity: VaultIdentity;
  sites: Record<string, SiteRegistration>;
  removedSites: string[];
  rewoundSites: string[];
  replacedSites: string[];
  kelDepth: number;
}

/**
 * Drop or rewind local rotations that no longer exist on the node
 * (expired mempool KEL / off-chain branch tips).
 */
export async function resyncVaultFromNode(
  api: NodeApi,
  identity: VaultIdentity,
  sites: Record<string, SiteRegistration>
): Promise<VaultResyncResult> {
  let kelDepth = identity.mainDepth;
  const kelRes = await httpJson(
    api,
    `/key-event-log?public_key=${encodeURIComponent(identity.k0.publicKeyHex)}`
  );
  if (kelRes.ok && Array.isArray(kelRes.body?.key_event_log)) {
    kelDepth = kelRotationDepth(kelRes.body.key_event_log);
  } else if (kelRes.status === 404 || kelRes.body?.status === false) {
    kelDepth = 0;
  }

  const tipSigner = walkMain(identity.k0, identity.secondFactor, kelDepth);
  const tipPrevPkh =
    kelDepth === 0
      ? ""
      : walkMain(identity.k0, identity.secondFactor, kelDepth - 1).address;
  const nextIdentity: VaultIdentity = {
    ...identity,
    mainDepth: kelDepth,
    tipSigner,
    tipPrevPkh,
  };

  const removedSites: string[] = [];
  const rewoundSites: string[] = [];
  const replacedSites: string[] = [];
  const nextSites: Record<string, SiteRegistration> = {};
  for (const [key, site] of Object.entries(sites)) {
    const keys = siteKeysForOrigin(nextIdentity, site.branchPeer || site.siteId || key);
    const tipRes = await fetchSiteTip(api, keys.branchPeer);
    if (!tipRes.ok || tipRes.body?.status === false || !tipRes.body?.tip) {
      removedSites.push(key);
      continue;
    }
    const tip = tipRes.body.tip;
    const counter = Number(tip.counter ?? 0);
    if (!Number.isFinite(counter) || counter < 0) {
      removedSites.push(key);
      continue;
    }
    const inception = (tip.branch_inception_public_key_hash as string) || "";
    const rebuilt = siteAtCounter(
      nextIdentity,
      { siteId: keys.branchPeer, branchPeer: keys.branchPeer, kp0: keys.kp0 },
      counter
    );
    const keysMismatch =
      (inception && inception !== keys.kp0.address) ||
      !!(tip.prerotated_key_hash && rebuilt.tip.address !== tip.prerotated_key_hash);
    if (keysMismatch) {
      const replaced = await registerSite(
        api,
        nextIdentity,
        keys.branchPeer,
        undefined,
        { replaceExisting: true }
      );
      nextSites[key] = replaced.site;
      replacedSites.push(key);
      continue;
    }
    nextSites[key] = rebuilt;
    if (counter !== site.counter || site.kp0.address !== keys.kp0.address) {
      rewoundSites.push(key);
    }
  }

  return {
    identity: nextIdentity,
    sites: nextSites,
    removedSites,
    rewoundSites,
    replacedSites,
    kelDepth,
  };
}
