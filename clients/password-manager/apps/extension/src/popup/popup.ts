import {
  broadcastTxns,
  buildInceptionTxn,
  bytesToHex,
  createVaultSeed,
  fetchPendingAuthSessions,
  hashPassword,
  hexToBytes,
  identityAfterInception,
  isAlreadyInceptedError,
  LEGACY_KEYS,
  materialFromPrivCc,
  normalizeNodeBaseUrl,
  normalizeSiteId,
  postAuthSessionResult,
  registerSite,
  rotateSitePassword,
  resyncSiteFromNode,
  resyncVaultFromNode,
  siteAtCounter,
  siteKeysForOrigin,
  syncInceptionFromNode,
  unlockIdentity,
  vaultIdFromData,
  VaultStore,
  type PasswordAuthRequestPayload,
  type SiteRegistration,
  type StoredSite,
  type StoredVault,
  type VaultIdentity,
} from "@yadacoin/password-core";
import { bootTheme } from "../shared/theme-boot.js";
import { resolveHomeApiBase } from "../shared/home.js";
import { loadSettings } from "../shared/settings.js";
import {
  enableSiteAndNode,
  injectBridgeIntoTab,
  requestOriginAccess,
} from "../shared/permissions.js";
import { createExtensionVaultBackend } from "../shared/vault-backend.js";

const store = new VaultStore(createExtensionVaultBackend());

function $(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) throw new Error(`#${id} missing`);
  return el;
}

function showAlert(message: string, kind: "error" | "success" | "" = "") {
  const el = $("alert");
  if (!message) {
    el.hidden = true;
    el.textContent = "";
    el.className = "pm-alert";
    return;
  }
  el.hidden = false;
  el.textContent = message;
  el.className = `pm-alert${kind ? ` pm-alert--${kind}` : ""}`;
}

async function getActiveOrigin(): Promise<string> {
  try {
    if (typeof chrome === "undefined" || !chrome.tabs?.query) return "";
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = tabs[0]?.url;
    if (!url) return "";
    const u = new URL(url);
    if (u.protocol !== "http:" && u.protocol !== "https:") return "";
    return u.origin.toLowerCase();
  } catch {
    return "";
  }
}

async function fillSiteFromOrigin(origin: string, vault: StoredVault | null) {
  if (!origin) return;
  const key = normalizeSiteId(origin);
  const input = $("siteId") as HTMLInputElement;
  input.value = key;
  if (vault?.sites?.[key]) {
    $("sitePassword").textContent = vault.sites[key]!.currentPassword;
  } else {
    $("sitePassword").textContent = "—";
  }
}

async function ensureNodeAccess(nodeUrl: string): Promise<void> {
  const ok = await requestOriginAccess(nodeUrl);
  if (!ok) throw new Error("Permission denied for password home node");
}

async function ensureSiteAccess(siteId: string, nodeUrl: string): Promise<void> {
  const ok = await enableSiteAndNode(siteId, nodeUrl);
  if (!ok) throw new Error("Permission denied for this site or home node");
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  const tabId = tabs[0]?.id;
  if (tabId != null) await injectBridgeIntoTab(tabId);
}

/** Deterministic password-home API base (no user Node URL). */
async function getApiBase(username?: string): Promise<string> {
  const origin = await getActiveOrigin();
  const v = await loadVault();
  const base = await resolveHomeApiBase({
    username: (username || v?.username || "").trim(),
    pageOrigin: origin || undefined,
    cachedHome: v?.nodeUrl,
  });
  await ensureNodeAccess(base);
  return base;
}

async function loadVault(): Promise<StoredVault | null> {
  const entry = await store.getActiveVault();
  return entry?.data ?? null;
}

async function saveActiveVault(v: StoredVault): Promise<void> {
  const id = vaultIdFromData(v);
  await store.updateVaultData(id, v);
  await store.setActiveVaultId(id);
}

function identityFromStored(v: StoredVault): VaultIdentity {
  return unlockIdentity(v.mnemonic, v.secondFactor, v.username, {
    identityType: v.identityType,
    mainDepth: v.mainDepth,
    tipPrevPkh: v.tipPrevPkh,
  });
}

async function ensureIncepted(
  v: StoredVault,
  nodeUrl: string,
  opts?: { silent?: boolean }
): Promise<StoredVault> {
  const base = normalizeNodeBaseUrl(nodeUrl);
  if (!base) return v;
  try {
    await ensureNodeAccess(base);
    const id = identityFromStored(v);
    const { identity, inceptionDone } = await syncInceptionFromNode(
      { baseUrl: base },
      id
    );
    // Not on node yet — keep local vault so caller can broadcast inception.
    if (!inceptionDone) return v;
    const next: StoredVault = {
      ...v,
      nodeUrl: base,
      inceptionDone: true,
      mainDepth: identity.mainDepth,
      tipPrevPkh: identity.tipPrevPkh,
    };
    if (
      next.inceptionDone !== v.inceptionDone ||
      next.mainDepth !== v.mainDepth ||
      next.tipPrevPkh !== v.tipPrevPkh ||
      next.nodeUrl !== v.nodeUrl
    ) {
      await saveActiveVault(next);
    }
    return next;
  } catch (e) {
    if (opts?.silent) return v;
    throw e;
  }
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

function storeSite(site: SiteRegistration): StoredSite {
  return {
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
  };
}

function setTab(name: string) {
  for (const btn of document.querySelectorAll<HTMLButtonElement>(".pm-tab")) {
    btn.setAttribute("aria-selected", btn.dataset.tab === name ? "true" : "false");
  }
  $("panel-request").hidden = name !== "request";
  $("panel-setup").hidden = name !== "setup";
  $("panel-site").hidden = name !== "site";
  $("panel-status").hidden = name !== "status";
}

function fillFormFromVault(v: StoredVault | null) {
  if (!v) {
    ($("username") as HTMLInputElement).value = "";
    ($("secondFactor") as HTMLInputElement).value = "";
    ($("mnemonic") as HTMLTextAreaElement).value = "";
    return;
  }
  ($("username") as HTMLInputElement).value = v.username || "";
  ($("secondFactor") as HTMLInputElement).value = v.secondFactor || "";
  ($("mnemonic") as HTMLTextAreaElement).value = v.mnemonic || "";
}

async function refreshVaultSelect(selectedId?: string | null) {
  const sel = $("vaultSelect") as HTMLSelectElement;
  const vaults = await store.listVaults();
  const activeId =
    selectedId !== undefined ? selectedId : await store.getActiveVaultId();
  sel.innerHTML = "";
  if (!vaults.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "— no vault —";
    sel.appendChild(opt);
    return;
  }
  for (const e of vaults) {
    const opt = document.createElement("option");
    opt.value = e.id;
    const label = e.name || e.data.username || e.id.slice(0, 12);
    opt.textContent = `${label} · ${e.id.slice(0, 10)}…`;
    if (e.id === activeId) opt.selected = true;
    sel.appendChild(opt);
  }
}

async function switchToVault(id: string) {
  if (!id) return;
  const entry = await store.getVault(id);
  if (!entry) throw new Error("vault not found");
  await store.setActiveVaultId(id);
  fillFormFromVault(entry.data);
  await refreshVaultSelect(id);
  await fillSiteFromOrigin(await getActiveOrigin(), entry.data);
  setTab(entry.data.inceptionDone ? "request" : "setup");
  await refreshStatus();
}

let pendingRemote: PasswordAuthRequestPayload | null = null;

function renderPendingRequest(p: PasswordAuthRequestPayload | null) {
  pendingRemote = p;
  const summary = $("requestSummary");
  const approve = $("approveRequestBtn") as HTMLButtonElement;
  const deny = $("denyRequestBtn") as HTMLButtonElement;
  if (!p) {
    summary.textContent = "No pending request";
    approve.disabled = true;
    deny.disabled = true;
    return;
  }
  summary.textContent = [
    `action: ${p.action}`,
    `site: ${p.site}`,
    `user: ${p.username || "—"}`,
    `session: ${p.session_id}`,
    p.home_node ? `home: ${p.home_node}` : "",
  ]
    .filter(Boolean)
    .join("\n");
  approve.disabled = false;
  deny.disabled = false;
}

async function drainPendingRequests(): Promise<void> {
  const v = await loadVault();
  if (!v || !v.inceptionDone) {
    renderPendingRequest(null);
    showAlert("Save vault and broadcast inception first.", "error");
    return;
  }
  const nodeUrl = await getApiBase(v.username);
  const id = identityFromStored(v);
  const rows = await fetchPendingAuthSessions(nodeUrl, {
    username: id.username,
    username_signature: id.usernameSignature,
    public_key: id.k0.publicKeyHex,
    inception_pkh: id.k0.address,
  });
  const first = rows && rows.length ? rows[0]! : null;
  renderPendingRequest(first);
  if (first) {
    showAlert(`Pending ${first.action} for ${first.site}`, "success");
    setTab("request");
  } else {
    showAlert("No pending auth requests on this node.", "success");
  }
}

async function approvePendingRequest(): Promise<void> {
  if (!pendingRemote) return;
  const p = pendingRemote;
  const v = await loadVault();
  if (!v) throw new Error("no vault");
  const nodeUrl = await getApiBase(v.username);
  const identity = identityFromStored(v);
  let siteKey = p.site || "";
  if (siteKey.startsWith("http://") || siteKey.startsWith("https://")) {
    siteKey = normalizeSiteId(siteKey);
  }
  const action = (p.action || "signin").toLowerCase();
  let password = "";
  let counter: number | null = null;

  if (action === "status") {
    await postAuthSessionResult(nodeUrl, p.session_id, {
      result_token: p.result_token,
      ok: true,
      action: "status",
      nonce: p.nonce,
      message: "status ok",
      registered: !!v.sites?.[siteKey],
      counter: v.sites?.[siteKey]?.counter ?? null,
    });
    renderPendingRequest(null);
    showAlert("Status approved", "success");
    return;
  }

  let siteReg: SiteRegistration;
  const local = v.sites?.[siteKey];
  try {
    siteReg = await resyncSiteFromNode({ baseUrl: nodeUrl }, identity, siteKey);
  } catch {
    if (local) {
      siteReg = siteFromStored(local);
    } else {
      const reg = await registerSite({ baseUrl: nodeUrl }, identity, siteKey);
      v.mainDepth = reg.identity.mainDepth;
      v.tipPrevPkh = reg.identity.tipPrevPkh;
      siteReg = reg.site;
    }
  }
  const rotated = await rotateSitePassword(
    { baseUrl: nodeUrl },
    identity,
    siteReg,
    undefined,
    { expectedHash: p.expectedHash || undefined }
  );
  v.sites[siteKey] = storeSite(rotated.site);
  await saveActiveVault(v);
  password = rotated.password;
  counter = rotated.site.counter;
  const nextHash = hashPassword(
    rotated.nextPassword || rotated.site.currentPassword || password
  );

  await postAuthSessionResult(nodeUrl, p.session_id, {
    result_token: p.result_token,
    ok: true,
    action: action === "operator" ? "operator" : action === "register" ? "register" : "signin",
    nonce: p.nonce,
    password,
    nextPasswordHash: nextHash,
    counter,
    registered: true,
    message:
      action === "operator"
        ? `operator approved · counter ${counter}`
        : `approved · counter ${counter}`,
  });
  renderPendingRequest(null);
  await fillSiteFromOrigin(siteKey, v);
  showAlert(
    action === "operator"
      ? "Operator request approved — wallet can finish unlock"
      : "Request approved",
    "success"
  );
}

async function denyPendingRequest(): Promise<void> {
  if (!pendingRemote) return;
  const p = pendingRemote;
  const v = await loadVault();
  const nodeUrl = await getApiBase(v?.username);
  await postAuthSessionResult(nodeUrl, p.session_id, {
    result_token: p.result_token,
    ok: false,
    deny: true,
    action: p.action,
    nonce: p.nonce,
    message: "denied by user",
  });
  renderPendingRequest(null);
  showAlert("Request denied", "success");
}

async function refreshStatus() {
  const v = await loadVault();
  if (!v) {
    $("k0Addr").textContent = "no vault";
    $("mainDepth").textContent = "—";
    $("siteList").textContent = "—";
    return;
  }
  try {
    const id = identityFromStored(v);
    $("k0Addr").textContent = id.k0.address;
    $("mainDepth").textContent =
      String(v.mainDepth) + (v.inceptionDone ? " (incepted)" : " (pending inception)");
    $("siteList").textContent =
      Object.keys(v.sites || {}).join("\n") || "(none registered)";
  } catch (e) {
    $("k0Addr").textContent = e instanceof Error ? e.message : String(e);
  }
}

async function main() {
  await bootTheme();
  await loadSettings();

  await store.migrateLegacy(LEGACY_KEYS.extension);

  const vault = await loadVault();
  fillFormFromVault(vault);
  await refreshVaultSelect();

  const activeOrigin = await getActiveOrigin();
  await fillSiteFromOrigin(activeOrigin, vault);

  setTab(vault?.inceptionDone ? "request" : "setup");
  if (vault?.inceptionDone) {
    void drainPendingRequests().catch(() => {
      /* ignore drain errors on open */
    });
  }

  ($("vaultSelect") as HTMLSelectElement).addEventListener("change", () => {
    void (async () => {
      const id = ($("vaultSelect") as HTMLSelectElement).value;
      if (!id) return;
      try {
        await switchToVault(id);
        showAlert("Switched vault", "success");
      } catch (e) {
        showAlert(e instanceof Error ? e.message : String(e), "error");
      }
    })();
  });

  $("newVaultBtn").addEventListener("click", () => {
    fillFormFromVault(null);
    $("sitePassword").textContent = "—";
    setTab("setup");
    showAlert("Enter a new seed (or Generate), then Save vault", "success");
  });

  $("deleteVaultBtn").addEventListener("click", () => {
    void (async () => {
      const id = await store.getActiveVaultId();
      if (!id) {
        showAlert("No vault to delete", "error");
        return;
      }
      if (!confirm("Delete the active vault from this device? This cannot be undone.")) {
        return;
      }
      await store.deleteVault(id);
      const next = await store.getActiveVault();
      fillFormFromVault(next?.data ?? null);
      await refreshVaultSelect();
      await fillSiteFromOrigin(await getActiveOrigin(), next?.data ?? null);
      setTab(next?.data?.inceptionDone ? "request" : "setup");
      showAlert("Vault deleted", "success");
      await refreshStatus();
    })();
  });

  for (const btn of document.querySelectorAll<HTMLButtonElement>(".pm-tab")) {
    btn.addEventListener("click", () => {
      void (async () => {
        const tab = btn.dataset.tab || "setup";
        setTab(tab);
        if (tab === "status") await refreshStatus();
        if (tab === "request") await drainPendingRequests();
        if (tab === "site") {
          const origin = (await getActiveOrigin()) || activeOrigin;
          const v = await loadVault();
          await fillSiteFromOrigin(origin, v);
        }
      })();
    });
  }

  $("refreshRequestBtn").addEventListener("click", () => {
    void drainPendingRequests().catch((e) =>
      showAlert(e instanceof Error ? e.message : String(e), "error")
    );
  });
  $("approveRequestBtn").addEventListener("click", () => {
    void approvePendingRequest().catch((e) =>
      showAlert(e instanceof Error ? e.message : String(e), "error")
    );
  });
  $("denyRequestBtn").addEventListener("click", () => {
    void denyPendingRequest().catch((e) =>
      showAlert(e instanceof Error ? e.message : String(e), "error")
    );
  });

  $("allowSiteBtn").addEventListener("click", async () => {
    showAlert("");
    try {
      const origin = await getActiveOrigin();
      if (!origin) throw new Error("This tab has no http(s) origin");
      const home = await getApiBase();
      await ensureSiteAccess(origin, home);
      showAlert("This page can talk to Yada Password. Register or Sign in here.", "success");
    } catch (e) {
      showAlert(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("genSeedBtn").addEventListener("click", () => {
    ($("mnemonic") as HTMLTextAreaElement).value = createVaultSeed(128);
    showAlert("New seed generated — write it down, then Save vault", "success");
  });

  $("saveVaultBtn").addEventListener("click", async () => {
    showAlert("");
    try {
      const username = ($("username") as HTMLInputElement).value.trim();
      const secondFactor = ($("secondFactor") as HTMLInputElement).value;
      const mnemonic = ($("mnemonic") as HTMLTextAreaElement).value.trim();
      const id = unlockIdentity(mnemonic, secondFactor, username);
      const vaultId = id.k0.address;
      const existing = await store.getVault(vaultId);
      const prev = existing?.data ?? null;
      let stored: StoredVault = {
        mnemonic,
        secondFactor,
        username,
        identityType: "social",
        mainDepth: prev?.mainDepth ?? 0,
        tipPrevPkh: prev?.tipPrevPkh ?? "",
        inceptionDone: prev?.inceptionDone ?? false,
        sites: prev?.sites ?? {},
        nodeUrl: prev?.nodeUrl,
      };
      await store.saveVault(vaultId, stored, {
        name: username || existing?.name,
      });
      await store.setActiveVaultId(vaultId);
      try {
        const home = await getApiBase(username);
        stored = await ensureIncepted(stored, home, { silent: true });
        if (stored.nodeUrl !== home) {
          stored = { ...stored, nodeUrl: home };
          await saveActiveVault(stored);
        }
      } catch {
        /* home resolve optional until inception */
      }
      await refreshVaultSelect(vaultId);
      const ready = stored.inceptionDone
        ? "incepted on home SP"
        : "inception still needed";
      showAlert(
        `Vault saved · K0 ${id.k0.address.slice(0, 12)}… · ${ready}`,
        "success"
      );
      if (stored.inceptionDone) {
        setTab("request");
        await refreshStatus();
      }
    } catch (e) {
      showAlert(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("inceptionBtn").addEventListener("click", async () => {
    showAlert("");
    try {
      let v = await loadVault();
      if (!v) throw new Error("Save vault first");
      const nodeUrl = await getApiBase(v.username);
      v = await ensureIncepted(v, nodeUrl);
      if (v.inceptionDone) {
        showAlert("Already incepted on home SP — vault updated", "success");
        const origin = await getActiveOrigin();
        await fillSiteFromOrigin(origin, v);
        setTab("site");
        return;
      }
      let identity = identityFromStored(v);
      const txn = buildInceptionTxn(identity);
      const res = await broadcastTxns({ baseUrl: nodeUrl }, txn);
      const already = isAlreadyInceptedError(res.body?.message);
      if (!res.ok && res.body?.status === false && !already) {
        v = await ensureIncepted(v, nodeUrl);
        if (v.inceptionDone) {
          showAlert("Already incepted on home SP — vault updated", "success");
          const origin = await getActiveOrigin();
          await fillSiteFromOrigin(origin, v);
          setTab("site");
          return;
        }
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
      await saveActiveVault(v);
      showAlert(
        already
          ? "Inception already on chain — vault updated"
          : "Inception broadcast · identity on mempool/chain",
        "success"
      );
      const origin = await getActiveOrigin();
      await fillSiteFromOrigin(origin, v);
      setTab("site");
    } catch (e) {
      showAlert(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("registerSiteBtn").addEventListener("click", async () => {
    showAlert("");
    try {
      const siteId = ($("siteId") as HTMLInputElement).value.trim();
      if (!siteId) throw new Error("Site origin required");
      let v = await loadVault();
      if (!v?.inceptionDone) throw new Error("Broadcast inception first");
      const nodeUrl = await getApiBase(v.username);
      await ensureSiteAccess(siteId, nodeUrl);
      const identity = identityFromStored(v);
      const result = await registerSite({ baseUrl: nodeUrl }, identity, siteId);
      v = {
        ...v,
        nodeUrl,
        mainDepth: result.identity.mainDepth,
        tipPrevPkh: result.identity.tipPrevPkh,
        sites: {
          ...v.sites,
          [result.site.branchPeer]: storeSite(result.site),
        },
      };
      await saveActiveVault(v);
      $("sitePassword").textContent = result.site.currentPassword;
      showAlert(
        `Registered ${result.site.branchPeer} · counter ${result.site.counter}`,
        "success"
      );
    } catch (e) {
      showAlert(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("resyncBtn").addEventListener("click", async () => {
    showAlert("");
    try {
      let v = await loadVault();
      if (!v) throw new Error("No vault");
      const nodeUrl = await getApiBase(v.username);
      const identity = identityFromStored(v);
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
      await saveActiveVault(v);
      await refreshStatus();
      const origin = await getActiveOrigin();
      await fillSiteFromOrigin(origin, v);
      const bits = [
        `KEL depth ${result.kelDepth}`,
        result.rewoundSites.length
          ? `rewound ${result.rewoundSites.length} site(s)`
          : "",
        result.replacedSites.length
          ? `rebuilt ${result.replacedSites.length} site branch(es)`
          : "",
        result.removedSites.length
          ? `removed ${result.removedSites.length} stale site(s)`
          : "",
      ].filter(Boolean);
      showAlert("Resync complete · " + bits.join(" · "), "success");
    } catch (e) {
      showAlert(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("rotateSiteBtn").addEventListener("click", async () => {
    showAlert("");
    try {
      const siteId = ($("siteId") as HTMLInputElement).value.trim();
      if (!siteId) throw new Error("Site origin required");
      let v = await loadVault();
      if (!v) throw new Error("No vault");
      const nodeUrl = await getApiBase(v.username);
      await ensureSiteAccess(siteId, nodeUrl);
      const key = normalizeSiteId(siteId);
      const identity = identityFromStored(v);
      let site;
      const stored = v.sites[key];
      if (stored) {
        site = siteFromStored(stored);
      } else {
        const { branchPeer, kp0 } = siteKeysForOrigin(identity, siteId);
        const tipRes = await fetch(
          nodeUrl.replace(/\/+$/, "") +
            "/password-rotation/offchain/tip?branch_peer=" +
            encodeURIComponent(branchPeer)
        );
        const tipData = await tipRes.json();
        if (!tipRes.ok || !tipData.status || !tipData.tip) {
          throw new Error("Site not registered — register first");
        }
        site = siteAtCounter(
          identity,
          { siteId, branchPeer, kp0 },
          Number(tipData.tip.counter ?? 0)
        );
      }
      const result = await rotateSitePassword({ baseUrl: nodeUrl }, identity, site);
      v = {
        ...v,
        nodeUrl,
        sites: { ...v.sites, [key]: storeSite(result.site) },
      };
      await saveActiveVault(v);
      $("sitePassword").textContent = result.site.currentPassword;
      showAlert(
        `Signed in & rotated · counter ${result.site.counter} · next password ready`,
        "success"
      );
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab?.id) await chrome.tabs.reload(tab.id);
    } catch (e) {
      showAlert(e instanceof Error ? e.message : String(e), "error");
    }
  });

  await refreshStatus();
}

void main();
