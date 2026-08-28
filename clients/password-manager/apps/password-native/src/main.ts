import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";
import {
  broadcastTxns,
  buildDemoCallbackUrl,
  buildInceptionTxn,
  bytesToHex,
  createVaultSeed,
  fetchAndroidAssetLinks,
  fetchKelDepth,
  fetchSiteTip,
  formatCertSha256Display,
  hashPassword,
  hexToBytes,
  identityAfterInception,
  isAlreadyInceptedError,
  materialFromPrivCc,
  normalizeSiteId,
  parseBridgeRequest,
  registerSite,
  resyncVaultFromNode,
  rotateSitePassword,
  siteAtCounter,
  siteKeysForOrigin,
  unlockIdentity,
  verifyAndroidCaller,
  type AttestedCaller,
  type BridgeRequest,
  type BridgeResult,
  type SiteCallerPin,
  type SiteRegistration,
  type VaultIdentity,
  type VerifyCallerResult,
} from "@yadacoin/password-core";
import { applyTheme, resolveTheme } from "@yadacoin/password-shared-ui";
import { CallerIdentity } from "./caller-plugin";

const VAULT_KEY = "yadaPasswordNativeVault";

interface StoredSite {
  siteId: string;
  branchPeer: string;
  counter: number;
  tipPrevPkh: string;
  branchInceptionPkh: string;
  tipPriv: string;
  tipCc: string;
  currentPassword: string;
  nextPassword: string;
  kp0Priv: string;
  kp0Cc: string;
  androidPackage?: string;
  androidCertSha256?: string[];
}

interface StoredVault {
  nodeUrl: string;
  mnemonic: string;
  secondFactor: string;
  username: string;
  identityType: string;
  mainDepth: number;
  tipPrevPkh: string;
  inceptionDone: boolean;
  sites: Record<string, StoredSite>;
}

let pending: BridgeRequest | null = null;
let pendingCaller: AttestedCaller | null = null;
let pendingVerify: VerifyCallerResult | null = null;

function pinFromStored(s: StoredSite | undefined): SiteCallerPin | null {
  if (!s?.androidPackage || !s.androidCertSha256?.length) return null;
  return {
    packageName: s.androidPackage,
    sha256CertFingerprints: s.androidCertSha256,
  };
}

function applyPin(stored: StoredSite, pin: SiteCallerPin | null | undefined): StoredSite {
  if (!pin?.packageName || !pin.sha256CertFingerprints?.length) return stored;
  return {
    ...stored,
    androidPackage: pin.packageName,
    androidCertSha256: pin.sha256CertFingerprints,
  };
}

function $(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) throw new Error(`#${id}`);
  return el;
}

function alertMsg(msg: string, kind: "" | "error" | "success" = "") {
  const el = $("alert");
  if (!msg) {
    el.hidden = true;
    el.textContent = "";
    el.className = "pm-alert";
    return;
  }
  el.hidden = false;
  el.textContent = msg;
  el.className = `pm-alert${kind ? ` pm-alert--${kind}` : ""}`;
}

function resolveNodeUrl(url: string): string {
  let u = (url || "").trim().replace(/\/+$/, "");
  if (Capacitor.getPlatform() === "android") {
    u = u.replace(/127\.0\.0\.1/g, "10.0.2.2").replace(/localhost/gi, "10.0.2.2");
  }
  return u;
}

async function loadVault(): Promise<StoredVault | null> {
  if (Capacitor.isNativePlatform()) {
    const { value } = await Preferences.get({ key: VAULT_KEY });
    return value ? (JSON.parse(value) as StoredVault) : null;
  }
  const raw = localStorage.getItem(VAULT_KEY);
  return raw ? (JSON.parse(raw) as StoredVault) : null;
}

async function saveVault(v: StoredVault): Promise<void> {
  const raw = JSON.stringify(v);
  if (Capacitor.isNativePlatform()) {
    await Preferences.set({ key: VAULT_KEY, value: raw });
    return;
  }
  localStorage.setItem(VAULT_KEY, raw);
}

function storeSite(site: SiteRegistration, pin?: SiteCallerPin | null): StoredSite {
  return applyPin(
    {
      siteId: site.siteId,
      branchPeer: site.branchPeer,
      counter: site.counter,
      tipPrevPkh: site.tipPrevPkh,
      branchInceptionPkh: site.branchInceptionPkh,
      tipPriv: bytesToHex(site.tip.privateKey),
      tipCc: bytesToHex(site.tip.chainCode),
      currentPassword: site.currentPassword,
      nextPassword: site.nextPassword,
      kp0Priv: bytesToHex(site.kp0.privateKey),
      kp0Cc: bytesToHex(site.kp0.chainCode),
    },
    pin
  );
}

function siteFromStored(s: StoredSite): SiteRegistration {
  return {
    siteId: s.siteId,
    branchPeer: s.branchPeer,
    kp0: materialFromPrivCc(hexToBytes(s.kp0Priv), hexToBytes(s.kp0Cc)),
    tip: materialFromPrivCc(hexToBytes(s.tipPriv), hexToBytes(s.tipCc)),
    counter: s.counter,
    tipPrevPkh: s.tipPrevPkh,
    currentPassword: s.currentPassword,
    nextPassword: s.nextPassword,
    branchInceptionPkh: s.branchInceptionPkh,
  };
}

function identityFromVault(v: StoredVault): VaultIdentity {
  return unlockIdentity(v.mnemonic, v.secondFactor, v.username, {
    identityType: v.identityType || "social",
    mainDepth: v.mainDepth,
    tipPrevPkh: v.tipPrevPkh,
  });
}

async function ensureIncepted(v: StoredVault): Promise<StoredVault> {
  if (v.inceptionDone) return v;
  const nodeUrl = resolveNodeUrl(v.nodeUrl || "");
  if (!nodeUrl) return v;
  const id = identityFromVault(v);
  const depth = await fetchKelDepth({ baseUrl: nodeUrl }, id.k0.publicKeyHex);
  if (depth < 1) return v;
  const next: StoredVault = {
    ...v,
    inceptionDone: true,
    mainDepth: Math.max(v.mainDepth || 0, depth),
    tipPrevPkh: v.tipPrevPkh || id.k0.address,
  };
  await saveVault(next);
  return next;
}

function setTab(name: string) {
  for (const b of document.querySelectorAll<HTMLButtonElement>(".tab")) {
    b.setAttribute("aria-selected", b.dataset.tab === name ? "true" : "false");
  }
  $("panel-home").hidden = name !== "home";
  $("panel-vault").hidden = name !== "vault";
  $("panel-request").hidden = name !== "request";
}

function setVerifyUi(v: VerifyCallerResult | null, caller: AttestedCaller | null) {
  const badge = $("reqVerify");
  const callerEl = $("reqCaller");
  const certEl = $("reqCert");
  const approve = $("approveBtn") as HTMLButtonElement;
  if (!v) {
    badge.textContent = "—";
    badge.className = "mono";
    callerEl.textContent = "—";
    certEl.textContent = "—";
    approve.disabled = true;
    return;
  }
  const who =
    (caller?.appLabel ? `${caller.appLabel} · ` : "") +
    (caller?.packageName || v.displayName || "unknown");
  callerEl.textContent = who;
  const fp = caller?.sha256CertFingerprints?.[0];
  certEl.textContent = fp ? formatCertSha256Display(fp) : "—";
  if (v.ok) {
    badge.textContent = `Verified · ${v.reason}`;
    badge.className = "mono pm-verify pm-verify--ok";
    approve.disabled = false;
  } else {
    badge.textContent = `Not verified · ${v.reason}`;
    badge.className = "mono pm-verify pm-verify--bad";
    approve.disabled = true;
  }
}

function showPending(req: BridgeRequest | null) {
  pending = req;
  if (!req) {
    pendingCaller = null;
    pendingVerify = null;
    $("reqEmpty").hidden = false;
    $("reqBody").hidden = true;
    setVerifyUi(null, null);
    return;
  }
  $("reqEmpty").hidden = true;
  $("reqBody").hidden = false;
  $("reqAction").textContent = req.action;
  $("reqSite").textContent = req.site;
  $("reqCallback").textContent = req.callback;
  setVerifyUi(pendingVerify, pendingCaller);
  setTab("request");
}

async function refreshHome() {
  const v = await loadVault();
  if (!v) {
    $("homeStatus").textContent = "No vault — open Vault tab";
    $("homeK0").textContent = "—";
    $("homeSites").textContent = "—";
    return;
  }
  try {
    const id = identityFromVault(v);
    $("homeK0").textContent = id.k0.address;
    $("homeStatus").textContent = v.inceptionDone
      ? `Ready · main depth ${v.mainDepth}`
      : "Vault saved · inception pending";
    const keys = Object.keys(v.sites || {});
    $("homeSites").textContent = keys.length ? keys.join("\n") : "(none)";
  } catch (e) {
    $("homeStatus").textContent = e instanceof Error ? e.message : String(e);
  }
}

async function capacitorOpenUrl(url: string) {
  const opener = App as unknown as { openUrl: (o: { url: string }) => Promise<void> };
  await opener.openUrl({ url });
}

async function openCallback(url: string, packageName?: string | null) {
  const pkg =
    packageName ||
    pendingCaller?.packageName ||
    pendingVerify?.pin?.packageName;
  try {
    if (Capacitor.getPlatform() === "android" && pkg) {
      await CallerIdentity.openUrlInPackage({ url, packageName: pkg });
      return;
    }
  } catch {
    /* fall through */
  }
  try {
    if (Capacitor.isNativePlatform()) {
      await capacitorOpenUrl(url);
      return;
    }
  } catch {
    /* fall through */
  }
  window.location.href = url;
}

async function respond(result: BridgeResult, callback: string) {
  const url = buildDemoCallbackUrl(callback, result);
  const pkg = pendingCaller?.packageName || pendingVerify?.pin?.packageName;
  await persistPending(null);
  showPending(null);
  console.info("[yadapass] callback:", url);
  await openCallback(url, pkg);
}

const PENDING_PREF = "yadaPendingBridgeRequest";

interface PersistedPending {
  req: BridgeRequest;
  caller: AttestedCaller | null;
}

async function persistPending(req: BridgeRequest | null) {
  try {
    const payload: PersistedPending | null = req
      ? { req, caller: pendingCaller }
      : null;
    if (Capacitor.isNativePlatform()) {
      if (payload) {
        await Preferences.set({
          key: PENDING_PREF,
          value: JSON.stringify(payload),
        });
      } else {
        await Preferences.remove({ key: PENDING_PREF });
      }
    } else if (payload) {
      sessionStorage.setItem(PENDING_PREF, JSON.stringify(payload));
    } else {
      sessionStorage.removeItem(PENDING_PREF);
    }
  } catch {
    /* ignore */
  }
}

function coercePersisted(raw: string): PersistedPending | null {
  const parsed = JSON.parse(raw) as PersistedPending | BridgeRequest;
  if (parsed && typeof parsed === "object" && "action" in parsed && "site" in parsed) {
    return { req: parsed as BridgeRequest, caller: null };
  }
  if (parsed && typeof parsed === "object" && "req" in parsed) {
    return parsed as PersistedPending;
  }
  return null;
}

async function loadPersistedPending(): Promise<PersistedPending | null> {
  try {
    if (Capacitor.isNativePlatform()) {
      const { value } = await Preferences.get({ key: PENDING_PREF });
      return value ? coercePersisted(value) : null;
    }
    const raw = sessionStorage.getItem(PENDING_PREF);
    return raw ? coercePersisted(raw) : null;
  } catch {
    return null;
  }
}

async function snapshotCaller(): Promise<AttestedCaller | null> {
  if (Capacitor.getPlatform() !== "android") return null;
  try {
    const snap = await CallerIdentity.getLastCaller();
    if (!snap.packageName) return null;
    return {
      packageName: snap.packageName,
      appLabel: snap.appLabel || undefined,
      sha256CertFingerprints: snap.sha256CertFingerprints || [],
      handlesCallback: snap.handlesCallback,
    };
  } catch {
    return null;
  }
}

async function verifyRequest(
  req: BridgeRequest,
  caller: AttestedCaller | null,
  pin: SiteCallerPin | null
): Promise<VerifyCallerResult> {
  let assetLinks = null;
  const site = req.site || "";
  if (
    Capacitor.getPlatform() === "android" &&
    (site.startsWith("https://") || site.startsWith("HTTPS://"))
  ) {
    assetLinks = await fetchAndroidAssetLinks(site);
  }
  return verifyAndroidCaller({
    platform: Capacitor.getPlatform(),
    claimedSite: req.site,
    callback: req.callback,
    caller,
    pin,
    assetLinks,
  });
}

async function handleDeepLink(url: string) {
  console.info("[yadapass] deep link:", url);
  const req = parseBridgeRequest(url);
  if (!req) {
    alertMsg(`Unrecognized link (not a bridge request): ${url.slice(0, 120)}`, "error");
    return;
  }
  // Keep custom site ids like yadademo://app; only normalize http(s) origins
  if (req.site.startsWith("http://") || req.site.startsWith("https://")) {
    req.site = normalizeSiteId(req.site);
  }
  const vault = await loadVault();
  const pin = pinFromStored(vault?.sites?.[req.site]);
  pendingCaller = await snapshotCaller();
  pendingVerify = await verifyRequest(req, pendingCaller, pin);
  await persistPending(req);
  showPending(req);
  if (pendingVerify.ok) {
    alertMsg(`Request: ${req.action} · ${req.site} · ${pendingVerify.displayName}`, "success");
  } else {
    alertMsg(`Caller not verified: ${pendingVerify.reason}`, "error");
  }
}

async function approvePending() {
  if (!pending) return;
  const req = pending;
  const btn = $("approveBtn") as HTMLButtonElement;
  btn.disabled = true;
  alertMsg("Working…", "success");
  try {
    if (Capacitor.getPlatform() === "android" && !pendingVerify?.ok) {
      alertMsg(`Caller not verified: ${pendingVerify?.reason || "unknown"}`, "error");
      return;
    }
    const pin = pendingVerify?.ok ? pendingVerify.pin : null;
    let v = await loadVault();
    if (!v) {
      await respond(
        {
          nonce: req.nonce,
          ok: false,
          action: req.action,
          message: "no vault — open Yada Password Vault tab and save first",
        },
        req.callback
      );
      return;
    }
    v = await ensureIncepted(v);
    if (!v.inceptionDone) {
      await respond(
        {
          nonce: req.nonce,
          ok: false,
          action: req.action,
          message: "vault not incepted — open Vault tab and Broadcast inception",
        },
        req.callback
      );
      return;
    }
    const nodeUrl = resolveNodeUrl(v.nodeUrl);
    if (!nodeUrl) {
      await respond(
        {
          nonce: req.nonce,
          ok: false,
          action: req.action,
          message: "node URL not configured in password manager",
        },
        req.callback
      );
      return;
    }
    const identity = identityFromVault(v);
    const siteKey = req.site;

    if (req.action === "status") {
      const stored = v.sites[siteKey];
      await respond(
        {
          nonce: req.nonce,
          ok: true,
          action: "status",
          registered: !!stored,
          counter: stored?.counter ?? null,
          message: stored ? "registered" : "not registered",
        },
        req.callback
      );
      await refreshHome();
      return;
    }

    if (req.action === "register") {
      if (v.sites[siteKey]) {
        const keys = siteKeysForOrigin(identity, siteKey);
        const tipRes = await fetchSiteTip({ baseUrl: nodeUrl }, keys.branchPeer);
        const counter = Number(
          tipRes.body?.tip?.counter ?? v.sites[siteKey]!.counter ?? 0
        );
        const live = siteAtCounter(
          identity,
          { siteId: siteKey, branchPeer: keys.branchPeer, kp0: keys.kp0 },
          counter
        );
        v.sites[keys.branchPeer] = applyPin(storeSite(live), pin);
        await saveVault(v);
        await respond(
          {
            nonce: req.nonce,
            ok: true,
            action: "register",
            registered: true,
            counter: live.counter,
            password: live.currentPassword,
            nextPasswordHash: hashPassword(live.nextPassword),
            message: "already registered · next hash synced to tip",
          },
          req.callback
        );
        return;
      }
      const result = await registerSite({ baseUrl: nodeUrl }, identity, siteKey);
      v.mainDepth = result.identity.mainDepth;
      v.tipPrevPkh = result.identity.tipPrevPkh;
      v.sites[result.site.branchPeer] = applyPin(storeSite(result.site), pin);
      await saveVault(v);
      await respond(
        {
          nonce: req.nonce,
          ok: true,
          action: "register",
          registered: true,
          counter: result.site.counter,
          password: result.site.currentPassword,
          nextPasswordHash: hashPassword(result.site.nextPassword),
          message: `registered · counter ${result.site.counter}`,
        },
        req.callback
      );
      await refreshHome();
      return;
    }

    if (req.action === "signin") {
      const stored = v.sites[siteKey];
      if (!stored) {
        await respond(
          {
            nonce: req.nonce,
            ok: false,
            action: "signin",
            message: "site not registered — register first",
          },
          req.callback
        );
        return;
      }
      const site = siteFromStored(stored);
      const result = await rotateSitePassword(
        { baseUrl: nodeUrl },
        identity,
        site,
        undefined,
        { expectedHash: req.expectedHash }
      );
      v.sites[siteKey] = applyPin(storeSite(result.site), pin);
      await saveVault(v);
      await respond(
        {
          nonce: req.nonce,
          ok: true,
          action: "signin",
          registered: true,
          counter: result.site.counter,
          password: result.password,
          nextPasswordHash: hashPassword(result.nextPassword),
          message: `signed in & rotated · counter ${result.site.counter}`,
        },
        req.callback
      );
      await refreshHome();
      return;
    }
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    alertMsg(message, "error");
    await respond(
      { nonce: req.nonce, ok: false, action: req.action, message },
      req.callback
    );
  } finally {
    btn.disabled = false;
  }
}

async function main() {
  applyTheme(resolveTheme({ preset: "dark", user: { mode: "dark" } }));

  for (const b of document.querySelectorAll<HTMLButtonElement>(".tab")) {
    b.addEventListener("click", () => {
      setTab(b.dataset.tab || "home");
      if (b.dataset.tab === "home") void refreshHome();
    });
  }

  const v0 = await loadVault();
  if (v0) {
    ($("nodeUrl") as HTMLInputElement).value = v0.nodeUrl || "";
    ($("username") as HTMLInputElement).value = v0.username || "";
    ($("secondFactor") as HTMLInputElement).value = v0.secondFactor || "";
    ($("mnemonic") as HTMLTextAreaElement).value = v0.mnemonic || "";
  }

  $("genSeedBtn").addEventListener("click", () => {
    ($("mnemonic") as HTMLTextAreaElement).value = createVaultSeed(128);
    alertMsg("Seed generated — save the vault", "success");
  });

  $("saveVaultBtn").addEventListener("click", async () => {
    alertMsg("");
    try {
      const nodeUrl = resolveNodeUrl(($("nodeUrl") as HTMLInputElement).value);
      const username = ($("username") as HTMLInputElement).value.trim();
      const secondFactor = ($("secondFactor") as HTMLInputElement).value;
      const mnemonic = ($("mnemonic") as HTMLTextAreaElement).value.trim();
      const id = unlockIdentity(mnemonic, secondFactor, username);
      const prev = await loadVault();
      const stored: StoredVault = {
        nodeUrl,
        mnemonic,
        secondFactor,
        username,
        identityType: "social",
        mainDepth: prev?.mainDepth ?? 0,
        tipPrevPkh: prev?.tipPrevPkh ?? "",
        inceptionDone: prev?.inceptionDone ?? false,
        sites: prev?.sites ?? {},
      };
      if (!prev || prev.mnemonic !== mnemonic) {
        stored.mainDepth = 0;
        stored.tipPrevPkh = "";
        stored.inceptionDone = false;
        stored.sites = {};
      }
      await saveVault(stored);
      alertMsg(`Vault saved · ${id.k0.address.slice(0, 12)}…`, "success");
      await refreshHome();
    } catch (e) {
      alertMsg(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("inceptionBtn").addEventListener("click", async () => {
    alertMsg("");
    try {
      let v = await loadVault();
      if (!v) throw new Error("Save vault first");
      const nodeUrl = resolveNodeUrl(($("nodeUrl") as HTMLInputElement).value);
      if (!nodeUrl) throw new Error("Node URL required");
      v.nodeUrl = nodeUrl;
      v = await ensureIncepted({ ...v, nodeUrl });
      if (v.inceptionDone) {
        alertMsg("Already incepted — ready to approve requests", "success");
        await refreshHome();
        setTab(pending ? "request" : "home");
        return;
      }
      let identity = identityFromVault(v);
      const txn = buildInceptionTxn(identity);
      const res = await broadcastTxns({ baseUrl: nodeUrl }, txn);
      const already = isAlreadyInceptedError(res.body?.message);
      if (!res.ok && res.body?.status === false && !already) {
        throw new Error(res.body?.message || `broadcast failed (${res.status})`);
      }
      identity = identityAfterInception(identity);
      v = {
        ...v,
        nodeUrl,
        mainDepth: identity.mainDepth,
        tipPrevPkh: identity.tipPrevPkh,
        inceptionDone: true,
      };
      await saveVault(v);
      alertMsg(already ? "Inception already on chain — vault updated" : "Inception broadcast", "success");
      await refreshHome();
      setTab("home");
    } catch (e) {
      alertMsg(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("resyncBtn").addEventListener("click", async () => {
    alertMsg("");
    try {
      let v = await loadVault();
      if (!v) throw new Error("No vault");
      const nodeUrl = resolveNodeUrl(v.nodeUrl || ($("nodeUrl") as HTMLInputElement).value || "");
      if (!nodeUrl) throw new Error("Node URL required");
      const identity = identityFromVault(v);
      const sites: Record<string, SiteRegistration> = {};
      for (const [k, s] of Object.entries(v.sites || {})) {
        sites[k] = siteFromStored(s);
      }
      const result = await resyncVaultFromNode({ baseUrl: nodeUrl }, identity, sites);
      const nextSites: Record<string, StoredSite> = {};
      for (const [k, s] of Object.entries(result.sites)) {
        nextSites[k] = storeSite(s);
      }
      v = {
        ...v,
        nodeUrl,
        mainDepth: result.identity.mainDepth,
        tipPrevPkh: result.identity.tipPrevPkh,
        inceptionDone: result.kelDepth > 0,
        sites: nextSites,
      };
      await saveVault(v);
      await refreshHome();
      const bits = [
        `KEL depth ${result.kelDepth}`,
        result.rewoundSites.length ? `rewound ${result.rewoundSites.length} site(s)` : "",
        result.removedSites.length ? `removed ${result.removedSites.length} stale site(s)` : "",
      ].filter(Boolean);
      alertMsg("Resync complete · " + bits.join(" · "), "success");
    } catch (e) {
      alertMsg(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("approveBtn").addEventListener("click", () => void approvePending());
  $("denyBtn").addEventListener("click", () => {
    if (!pending) return;
    void respond(
      {
        nonce: pending.nonce,
        ok: false,
        action: pending.action,
        message: "denied by user",
      },
      pending.callback
    );
  });

  // Deep links — register listener BEFORE reading launch URL
  if (Capacitor.isNativePlatform()) {
    await App.addListener("appUrlOpen", ({ url }) => {
      void handleDeepLink(url);
    });
  }

  // Restore any in-flight request (app was backgrounded mid-approve)
  const restored = await loadPersistedPending();
  if (restored) {
    pendingCaller = restored.caller;
    const vault = await loadVault();
    const pin = pinFromStored(vault?.sites?.[restored.req.site]);
    if (!pendingCaller) pendingCaller = await snapshotCaller();
    pendingVerify = await verifyRequest(restored.req, pendingCaller, pin);
    showPending(restored.req);
  }

  // Cold start via deep link
  let launchUrl: string | undefined;
  if (Capacitor.isNativePlatform()) {
    try {
      const launch = await App.getLaunchUrl();
      launchUrl = launch?.url;
    } catch {
      launchUrl = undefined;
    }
  } else {
    const params = new URLSearchParams(location.search);
    launchUrl = params.get("dl") || undefined;
  }

  if (launchUrl) {
    await handleDeepLink(launchUrl);
  }

  await refreshHome();

  // Do NOT overwrite Request tab if a bridge request is pending
  if (pending) {
    setTab("request");
  } else {
    setTab(v0?.inceptionDone ? "home" : "vault");
  }
}

void main();
