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
  fetchAppleAppSiteAssociation,
  fetchKelDepth,
  fetchPendingAuthSessions,
  fetchSiteTip,
  formatCertSha256Display,
  hashPassword,
  hexToBytes,
  identityAfterInception,
  isAlreadyInceptedError,
  materialFromPrivCc,
  nodeUrlToWebSocketUrl,
  normalizeSiteId,
  parseBridgeRequest,
  postAuthSessionResult,
  publishPasswordHome,
  registerSite,
  resyncSiteFromNode,
  resyncVaultFromNode,
  rotateSitePassword,
  signPasswordHomeClaim,
  siteAtCounter,
  siteKeysForOrigin,
  unlockIdentity,
  verifyNativeCaller,
  websocketPeerIdentity,
  type AttestedCaller,
  type BridgeRequest,
  type BridgeResult,
  type PasswordAuthRequestPayload,
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
let authWs: WebSocket | null = null;
let authWsTimer: ReturnType<typeof setTimeout> | null = null;
let authWsIdentityKey = "";
let presenceStatus = "offline";

function pinFromStored(s: StoredSite | undefined): SiteCallerPin | null {
  if (!s?.androidPackage) return null;
  return {
    packageName: s.androidPackage,
    sha256CertFingerprints: s.androidCertSha256 || [],
  };
}

/** Resolve local site under siteId or branchPeer (register used to key by branch only). */
function lookupStoredSite(
  sites: Record<string, StoredSite> | undefined,
  siteKey: string
): { key: string; site: StoredSite } | null {
  if (!sites) return null;
  if (sites[siteKey]) return { key: siteKey, site: sites[siteKey]! };
  const norm = normalizeSiteId(siteKey);
  if (norm && sites[norm]) return { key: norm, site: sites[norm]! };
  for (const [k, s] of Object.entries(sites)) {
    if (s.siteId === siteKey || s.siteId === norm || s.branchPeer === siteKey || s.branchPeer === norm) {
      return { key: k, site: s };
    }
  }
  return null;
}

function storeKeyForSite(site: SiteRegistration, fallbackSiteKey: string): string {
  return site.branchPeer || normalizeSiteId(site.siteId || fallbackSiteKey) || fallbackSiteKey;
}

function applyPin(stored: StoredSite, pin: SiteCallerPin | null | undefined): StoredSite {
  if (!pin?.packageName) return stored;
  return {
    ...stored,
    androidPackage: pin.packageName,
    androidCertSha256: pin.sha256CertFingerprints || [],
  };
}

function nativePlatform(): boolean {
  const p = Capacitor.getPlatform();
  return p === "android" || p === "ios";
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

function defaultNodeUrl(): string {
  try {
    if (typeof window !== "undefined" && window.location?.origin) {
      const o = window.location.origin;
      if (o && o !== "null" && o.startsWith("http")) return o.replace(/\/+$/, "");
    }
  } catch {
    /* ignore */
  }
  return "";
}

function isLocalHttpHost(url: string): boolean {
  try {
    const u = new URL(url.includes("://") ? url : `http://${url}`);
    const h = (u.hostname || "").toLowerCase();
    return (
      h === "localhost" ||
      h === "127.0.0.1" ||
      h === "0.0.0.0" ||
      h === "10.0.2.2" ||
      h.startsWith("192.168.") ||
      h.startsWith("10.") ||
      /^172\.(1[6-9]|2\d|3[0-1])\./.test(h)
    );
  } catch {
    return false;
  }
}

/** When the app is served from a node, pin API calls to that origin (local demo). */
function pageServedFromNode(): boolean {
  try {
    const path = window.location?.pathname || "";
    return path.includes("/password-rotation/app");
  } catch {
    return false;
  }
}

function resolveNodeUrl(url: string): string {
  let u = (url || "").trim().replace(/\/+$/, "");
  const origin = defaultNodeUrl();
  // Served from /password-rotation/app on a local node → always use page origin
  // so deterministic home (e.g. pool.yadacoin.io) cannot hijack API traffic.
  if (pageServedFromNode() && origin && isLocalHttpHost(origin)) {
    u = origin;
  } else if (!u) {
    u = origin;
  }
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
  if (pending?.source === "remote") {
    badge.textContent = "Remote session · confirm site origin below";
    badge.className = "mono pm-verify pm-verify--ok";
    callerEl.textContent = "WebView / network handoff";
    certEl.textContent = pending.sessionId || "—";
    approve.disabled = false;
    return;
  }
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
  certEl.textContent = fp
    ? formatCertSha256Display(fp)
    : caller?.packageName
      ? Capacitor.getPlatform() === "ios"
        ? "iOS bundle ID (no cert API)"
        : "—"
      : "—";
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
  $("reqAction").textContent =
    req.source === "remote" ? `${req.action} (remote)` : req.action;
  $("reqSite").textContent = req.site;
  $("reqCallback").textContent =
    req.source === "remote"
      ? `session ${req.sessionId || "—"}`
      : req.callback;
  setVerifyUi(pendingVerify, pendingCaller);
  setTab("request");
  try {
    if (typeof document !== "undefined") {
      document.title = `Yada Password · ${req.action}`;
    }
  } catch {
    /* ignore */
  }
}

function setPresenceUi(status: string) {
  presenceStatus = status;
  const el = document.getElementById("homePresence");
  if (el) el.textContent = status;
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
    setPresenceUi(presenceStatus);
    if (v.inceptionDone) void ensureAuthWs();
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
    if (nativePlatform() && pkg) {
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
  const req = pending;
  if (req?.source === "remote" && req.sessionId && req.resultToken) {
    const v = await loadVault();
    const nodeUrl = resolveNodeUrl(v?.nodeUrl || "");
    if (!nodeUrl) throw new Error("node URL not configured");
    await postAuthSessionResult(nodeUrl, req.sessionId, {
      result_token: req.resultToken,
      ok: result.ok,
      deny: !result.ok,
      action: result.action,
      nonce: result.nonce,
      message: result.message,
      password: result.password,
      nextPasswordHash: result.nextPasswordHash,
      counter: result.counter,
      registered: result.registered,
    });
    await persistPending(null);
    showPending(null);
    alertMsg(
      result.ok
        ? "Approved · result sent to the web session"
        : result.message || "Denied",
      result.ok ? "success" : "error"
    );
    try {
      document.title = "Yada Password";
    } catch {
      /* ignore */
    }
    return;
  }
  const url = buildDemoCallbackUrl(callback, result);
  const pkg = pendingCaller?.packageName || pendingVerify?.pin?.packageName;
  await persistPending(null);
  showPending(null);
  console.info("[yadapass] callback:", url);
  await openCallback(url, pkg);
}

function remotePayloadToRequest(p: PasswordAuthRequestPayload): BridgeRequest {
  let site = (p.site || "").trim();
  if (site.startsWith("http://") || site.startsWith("https://")) {
    site = normalizeSiteId(site);
  }
  return {
    action: p.action,
    site,
    callback: "",
    nonce: p.nonce,
    expectedHash: p.expectedHash || undefined,
    sessionId: p.session_id,
    resultToken: p.result_token,
    source: "remote",
  };
}

async function ingestRemoteAuth(p: PasswordAuthRequestPayload) {
  if (!p?.session_id || !p?.result_token || !p?.site || !p?.nonce) return;
  // Don't clobber an in-progress deeplink request unless idle
  if (pending && pending.source !== "remote") return;
  if (pending?.sessionId === p.session_id) return;
  const req = remotePayloadToRequest(p);
  pendingCaller = null;
  pendingVerify = {
    ok: true,
    reason: "remote-session",
    displayName: "Web handoff",
    pin: { packageName: "webview", sha256CertFingerprints: [] },
  };
  await persistPending(req);
  showPending(req);
  alertMsg(`Remote ${req.action} · ${req.site} — approve in Request tab`, "success");
}

async function publishHomeClaim(v: StoredVault): Promise<void> {
  // Stay on the node the app is using (local origin when served from /app).
  // Do not retarget vault.nodeUrl to network_service_providers (e.g. pool.yadacoin.io).
  const entry = resolveNodeUrl(v.nodeUrl || defaultNodeUrl());
  if (!entry || !v.inceptionDone) return;
  try {
    const id = identityFromVault(v);
    if (resolveNodeUrl(v.nodeUrl || "") !== entry) {
      const next = { ...v, nodeUrl: entry };
      await saveVault(next);
      ($("nodeUrl") as HTMLInputElement).value = entry;
    }
    const ts = Math.floor(Date.now() / 1000);
    const signature = signPasswordHomeClaim(
      entry,
      id.username,
      ts,
      id.k0.privateKey
    );
    await publishPasswordHome(entry, {
      username: id.username,
      node_http_base: entry,
      public_key: id.k0.publicKeyHex,
      timestamp: ts,
      signature,
    });
  } catch (e) {
    console.warn("[yadapass] home claim failed", e);
  }
}

async function drainPendingRemote(v: StoredVault): Promise<void> {
  const nodeUrl = resolveNodeUrl(v.nodeUrl || "");
  if (!nodeUrl || !v.inceptionDone) return;
  try {
    const id = identityFromVault(v);
    const rows = await fetchPendingAuthSessions(nodeUrl, {
      username: id.username,
      username_signature: id.usernameSignature,
      public_key: id.k0.publicKeyHex,
      inception_pkh: id.k0.address,
    });
    for (const row of rows) {
      await ingestRemoteAuth(row);
      break;
    }
  } catch (e) {
    console.warn("[yadapass] pending drain failed", e);
  }
}

function stopAuthWs() {
  if (authWsTimer) {
    clearTimeout(authWsTimer);
    authWsTimer = null;
  }
  if (authWs) {
    try {
      authWs.onclose = null;
      authWs.onerror = null;
      authWs.onmessage = null;
      authWs.close();
    } catch {
      /* ignore */
    }
    authWs = null;
  }
  authWsIdentityKey = "";
  setPresenceUi("offline");
}

let authWsBackoffMs = 4000;
let authWsFailCount = 0;

function scheduleAuthWsReconnect(delayMs?: number) {
  if (authWsTimer) clearTimeout(authWsTimer);
  const wait = delayMs ?? authWsBackoffMs;
  authWsTimer = setTimeout(() => {
    void ensureAuthWs();
  }, wait);
}

async function ensureAuthWs(): Promise<void> {
  let v = await loadVault();
  if (!v) {
    if (authWs) stopAuthWs();
    setPresenceUi("offline · open Vault and save");
    return;
  }
  if (!v.inceptionDone) {
    if (authWs) stopAuthWs();
    setPresenceUi("offline · broadcast inception first");
    return;
  }
  const nodeUrl = resolveNodeUrl(v.nodeUrl || "");
  if (!nodeUrl) {
    if (authWs) stopAuthWs();
    setPresenceUi("offline · set Node URL");
    return;
  }
  // Sync mainDepth to live KEL tip before signing WS identity (depth 0 ⇒ tip≡K0)
  try {
    let idProbe = identityFromVault(v);
    const depth = await fetchKelDepth(
      { baseUrl: nodeUrl },
      idProbe.k0.publicKeyHex
    );
    if (depth >= 1 && depth !== (v.mainDepth || 0)) {
      v = {
        ...v,
        mainDepth: depth,
        tipPrevPkh: v.tipPrevPkh || idProbe.k0.address,
      };
      await saveVault(v);
      console.info("[yadapass] synced mainDepth →", depth);
    }
  } catch (e) {
    console.warn("[yadapass] kel depth sync failed", e);
  }
  let id: VaultIdentity;
  try {
    id = identityFromVault(v);
  } catch (e) {
    if (authWs) stopAuthWs();
    setPresenceUi(
      "offline · " + (e instanceof Error ? e.message : "bad vault")
    );
    return;
  }
  if ((id.mainDepth || 0) < 1) {
    setPresenceUi("offline · KEL depth 0 — resync or broadcast inception");
  }
  const peerId = websocketPeerIdentity(id);
  const identityKey = `${nodeUrl}|${id.username}|${peerId.public_key}|${id.mainDepth}`;
  if (
    authWs &&
    (authWs.readyState === WebSocket.CONNECTING ||
      authWs.readyState === WebSocket.OPEN) &&
    authWsIdentityKey === identityKey
  ) {
    return;
  }
  if (authWs) {
    try {
      authWs.onclose = null;
      authWs.close();
    } catch {
      /* ignore */
    }
    authWs = null;
  }
  const wsUrl = nodeUrlToWebSocketUrl(nodeUrl);
  if (!wsUrl) {
    setPresenceUi("offline · bad Node URL");
    return;
  }
  authWsIdentityKey = identityKey;
  setPresenceUi(`connecting… ${wsUrl}`);
  console.info("[yadapass] ws →", wsUrl);
  try {
    const ws = new WebSocket(wsUrl);
    authWs = ws;
    let rpcId = 1;
    let confirmed = false;
    const send = (method: string, params: Record<string, unknown> = {}) => {
      if (ws.readyState !== WebSocket.OPEN) return;
      ws.send(
        JSON.stringify({
          id: rpcId++,
          jsonrpc: "2.0",
          method,
          params,
        })
      );
    };
    ws.onopen = () => {
      setPresenceUi("connected · authenticating");
      console.info("[yadapass] connect identity (KEL tip)", {
        username: peerId.username,
        public_key: peerId.public_key.slice(0, 18) + "…",
        mainDepth: id.mainDepth,
      });
      send("connect", {
        identity: peerId,
      });
    };
    ws.onmessage = (ev) => {
      let msg: any;
      try {
        msg = JSON.parse(String(ev.data || ""));
      } catch {
        return;
      }
      const method = msg?.method || "";
      const params = msg?.params || msg?.result || {};
      if (method === "connect_confirm") {
        confirmed = true;
        authWsFailCount = 0;
        authWsBackoffMs = 4000;
        setPresenceUi("online");
        send("join_password_auth", {});
        void publishHomeClaim(v);
        void drainPendingRemote(v);
        return;
      }
      if (method === "join_password_auth_confirm") {
        const pendingRows = (params?.pending || []) as PasswordAuthRequestPayload[];
        for (const row of pendingRows) {
          void ingestRemoteAuth(row);
          break;
        }
        return;
      }
      if (method === "password_auth_request") {
        void ingestRemoteAuth(params as PasswordAuthRequestPayload);
      }
    };
    ws.onerror = () => {
      console.warn("[yadapass] ws error", wsUrl);
      setPresenceUi("error · check Node URL / WS");
    };
    ws.onclose = () => {
      authWs = null;
      if (!confirmed) {
        authWsFailCount += 1;
        authWsBackoffMs = Math.min(60000, 4000 * Math.pow(2, Math.min(authWsFailCount, 4)));
        setPresenceUi(
          "offline · identity rejected or WS closed · retry " +
            Math.round(authWsBackoffMs / 1000) +
            "s (use vault seed+password that match this username)"
        );
      } else {
        setPresenceUi("offline · retrying");
        authWsBackoffMs = 4000;
      }
      scheduleAuthWsReconnect();
    };
  } catch (e) {
    console.warn("[yadapass] ws connect failed", e);
    setPresenceUi("offline · retrying");
    scheduleAuthWsReconnect();
  }
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
  if (!nativePlatform()) return null;
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
  let appleAppSiteAssociation = null;
  const site = req.site || "";
  const https = site.startsWith("https://") || site.startsWith("HTTPS://");
  const platform = Capacitor.getPlatform();
  if (https && platform === "android") {
    assetLinks = await fetchAndroidAssetLinks(site);
  }
  if (https && platform === "ios") {
    appleAppSiteAssociation = await fetchAppleAppSiteAssociation(site);
  }
  return verifyNativeCaller({
    platform,
    claimedSite: req.site,
    callback: req.callback,
    caller,
    pin,
    assetLinks,
    appleAppSiteAssociation,
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
    const isRemote = req.source === "remote";
    if (nativePlatform() && !isRemote && !pendingVerify?.ok) {
      alertMsg(`Caller not verified: ${pendingVerify?.reason || "unknown"}`, "error");
      return;
    }
    const pin = !isRemote && pendingVerify?.ok ? pendingVerify.pin : null;
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
      let hit = lookupStoredSite(v.sites, siteKey);
      if (!hit) {
        try {
          const imported = await resyncSiteFromNode(
            { baseUrl: nodeUrl },
            identity,
            siteKey
          );
          const sk = storeKeyForSite(imported, siteKey);
          v.sites[sk] = applyPin(storeSite(imported), pin);
          await saveVault(v);
          hit = { key: sk, site: v.sites[sk]! };
        } catch {
          /* still not on node */
        }
      }
      await respond(
        {
          nonce: req.nonce,
          ok: true,
          action: "status",
          registered: !!hit,
          counter: hit?.site.counter ?? null,
          message: hit ? "registered" : "not registered",
        },
        req.callback
      );
      await refreshHome();
      return;
    }

    if (req.action === "register") {
      const keys = siteKeysForOrigin(identity, siteKey);
      const local = lookupStoredSite(v.sites, siteKey);
      const tipRes = await fetchSiteTip({ baseUrl: nodeUrl }, keys.branchPeer);
      const tipOnNode = !!(tipRes.ok && tipRes.body?.tip);

      // Local and/or node already has this branch — import/sync tip (new device restore).
      if (local || tipOnNode) {
        let live: SiteRegistration;
        if (tipOnNode) {
          live = await resyncSiteFromNode({ baseUrl: nodeUrl }, identity, siteKey);
        } else {
          const counter = Number(local!.site.counter ?? 0);
          live = siteAtCounter(
            identity,
            {
              siteId: keys.branchPeer,
              branchPeer: keys.branchPeer,
              kp0: keys.kp0,
            },
            counter
          );
        }
        const sk = storeKeyForSite(live, siteKey);
        if (local && local.key !== sk) delete v.sites[local.key];
        v.sites[sk] = applyPin(storeSite(live), pinFromStored(local?.site) || pin);
        await saveVault(v);
        await respond(
          {
            nonce: req.nonce,
            ok: true,
            action: "register",
            registered: true,
            counter: live.counter,
            password: live.currentPassword,
            // Hash the RP must check on the next sign-in (= tip prerotated).
            nextPasswordHash: hashPassword(live.currentPassword),
            message: tipOnNode
              ? "branch on node · vault restored from tip"
              : "already registered · tip synced",
          },
          req.callback
        );
        await refreshHome();
        return;
      }

      const result = await registerSite({ baseUrl: nodeUrl }, identity, siteKey);
      v.mainDepth = result.identity.mainDepth;
      v.tipPrevPkh = result.identity.tipPrevPkh;
      const sk = storeKeyForSite(result.site, siteKey);
      v.sites[sk] = applyPin(storeSite(result.site), pin);
      await saveVault(v);
      await respond(
        {
          nonce: req.nonce,
          ok: true,
          action: "register",
          registered: true,
          counter: result.site.counter,
          password: result.site.currentPassword,
          nextPasswordHash: hashPassword(result.site.currentPassword),
          message: `registered · counter ${result.site.counter}`,
        },
        req.callback
      );
      await refreshHome();
      return;
    }

    if (req.action === "signin" || req.action === "operator") {
      // operator = unlock node treasury via approve/reject; site is node origin.
      const local = lookupStoredSite(v.sites, siteKey);
      // Always rebuild from node tip so a restored vault needs no re-register.
      let site: SiteRegistration;
      try {
        site = await resyncSiteFromNode({ baseUrl: nodeUrl }, identity, siteKey);
      } catch (e) {
        if (local) {
          site = siteFromStored(local.site);
        } else if (req.action === "operator") {
          // First operator unlock: register the node-origin branch then rotate.
          const reg = await registerSite({ baseUrl: nodeUrl }, identity, siteKey);
          v.mainDepth = reg.identity.mainDepth;
          v.tipPrevPkh = reg.identity.tipPrevPkh;
          site = reg.site;
        } else {
          throw e instanceof Error
            ? e
            : new Error(String(e) || "site not registered on node");
        }
      }
      const result = await rotateSitePassword(
        { baseUrl: nodeUrl },
        identity,
        site,
        undefined,
        { expectedHash: req.expectedHash }
      );
      const sk = storeKeyForSite(result.site, siteKey);
      if (local && local.key !== sk) delete v.sites[local.key];
      v.sites[sk] = applyPin(
        storeSite(result.site),
        pinFromStored(local?.site) || pin
      );
      await saveVault(v);
      await respond(
        {
          nonce: req.nonce,
          ok: true,
          action: req.action === "operator" ? "operator" : "signin",
          registered: true,
          counter: result.site.counter,
          password: result.password,
          // Hash of the password that will unlock the *next* sign-in (new tip pre).
          nextPasswordHash: hashPassword(result.site.currentPassword),
          message:
            req.action === "operator"
              ? `operator approved · counter ${result.site.counter}`
              : `signed in & rotated · counter ${result.site.counter}`,
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
  const originDefault = defaultNodeUrl();
  if (v0) {
    // Snap stale vault nodeUrl (e.g. pool.yadacoin.io) back to page origin when local
    let nodeField = v0.nodeUrl || originDefault || "";
    if (
      pageServedFromNode() &&
      originDefault &&
      isLocalHttpHost(originDefault) &&
      nodeField &&
      !isLocalHttpHost(nodeField)
    ) {
      nodeField = originDefault;
      await saveVault({ ...v0, nodeUrl: originDefault });
      console.info("[yadapass] nodeUrl pinned to page origin", originDefault);
    }
    ($("nodeUrl") as HTMLInputElement).value = nodeField;
    ($("username") as HTMLInputElement).value = v0.username || "";
    ($("secondFactor") as HTMLInputElement).value = v0.secondFactor || "";
    ($("mnemonic") as HTMLTextAreaElement).value = v0.mnemonic || "";
  } else if (originDefault) {
    ($("nodeUrl") as HTMLInputElement).value = originDefault;
  }

  $("genSeedBtn").addEventListener("click", () => {
    ($("mnemonic") as HTMLTextAreaElement).value = createVaultSeed(128);
    alertMsg("Seed generated — save the vault", "success");
  });

  $("saveVaultBtn").addEventListener("click", async () => {
    alertMsg("");
    try {
      const nodeUrl = resolveNodeUrl(
        ($("nodeUrl") as HTMLInputElement).value || defaultNodeUrl()
      );
      if (nodeUrl) ($("nodeUrl") as HTMLInputElement).value = nodeUrl;
      const username = ($("username") as HTMLInputElement).value.trim();
      const secondFactor = ($("secondFactor") as HTMLInputElement).value;
      const mnemonic = ($("mnemonic") as HTMLTextAreaElement).value.trim();
      const id = unlockIdentity(mnemonic, secondFactor, username);
      const prev = await loadVault();
      const sameIdentity =
        !!prev &&
        prev.mnemonic === mnemonic &&
        prev.secondFactor === secondFactor &&
        prev.username === username;
      let stored: StoredVault = {
        nodeUrl,
        mnemonic,
        secondFactor,
        username,
        identityType: "social",
        mainDepth: sameIdentity ? prev!.mainDepth ?? 0 : 0,
        tipPrevPkh: sameIdentity ? prev!.tipPrevPkh ?? "" : "",
        inceptionDone: sameIdentity ? prev!.inceptionDone ?? false : false,
        // Site material is derived from vault + node tip; keep only when identity matches.
        sites: sameIdentity ? prev!.sites ?? {} : {},
      };
      await saveVault(stored);
      // Auto-detect KEL on node so a restored vault does not need a separate inception tap.
      if (nodeUrl) {
        stored = await ensureIncepted(stored);
        if (!stored.inceptionDone) {
          try {
            let identity = identityFromVault(stored);
            const txn = buildInceptionTxn(identity);
            const res = await broadcastTxns({ baseUrl: nodeUrl }, txn);
            const already = isAlreadyInceptedError(res.body?.message);
            if (res.ok || already || res.body?.status !== false) {
              identity = identityAfterInception(identity);
              stored = {
                ...stored,
                mainDepth: identity.mainDepth,
                tipPrevPkh: identity.tipPrevPkh,
                inceptionDone: true,
              };
              await saveVault(stored);
            }
          } catch {
            /* user can tap Broadcast inception if node unreachable */
          }
        }
      }
      const ready = stored.inceptionDone ? "ready · sign-in will auto-sync sites" : "saved · inception still needed";
      alertMsg(`Vault saved · ${id.k0.address.slice(0, 12)}… · ${ready}`, "success");
      await refreshHome();
      if (stored.inceptionDone) setTab(pending ? "request" : "home");
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
        const prev = v.sites?.[k];
        nextSites[k] = applyPin(storeSite(s), pinFromStored(prev));
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
      if (Object.keys(sites).length === 0) {
        alertMsg(
          `Resync complete · KEL depth ${result.kelDepth} · no local sites yet — use Register or Sign-in once to import the site branch from the node`,
          "success"
        );
        return;
      }
      const bits = [
        `KEL depth ${result.kelDepth}`,
        result.rewoundSites.length ? `rewound ${result.rewoundSites.length} site(s)` : "",
        result.removedSites.length ? `removed ${result.removedSites.length} stale site(s)` : "",
        result.replacedSites.length ? `replaced ${result.replacedSites.length} site(s)` : "",
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
    if (restored.req.source === "remote") {
      pendingVerify = {
        ok: true,
        reason: "remote-session",
        displayName: "Web handoff",
        pin: { packageName: "webview", sha256CertFingerprints: [] },
      };
      showPending(restored.req);
    } else {
      const pin = pinFromStored(vault?.sites?.[restored.req.site]);
      if (!pendingCaller) pendingCaller = await snapshotCaller();
      pendingVerify = await verifyRequest(restored.req, pendingCaller, pin);
      showPending(restored.req);
    }
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
  void ensureAuthWs();

  // Visibility / focus: re-open WS and drain pending
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void ensureAuthWs();
  });
  window.addEventListener("focus", () => {
    void ensureAuthWs();
  });

  // Do NOT overwrite Request tab if a bridge request is pending
  if (pending) {
    setTab("request");
  } else {
    setTab(v0?.inceptionDone ? "home" : "vault");
  }
}

void main();
