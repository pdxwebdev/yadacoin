import {
  broadcastTxns,
  buildInceptionTxn,
  bytesToHex,
  createVaultSeed,
  hexToBytes,
  identityAfterInception,
  materialFromPrivCc,
  normalizeSiteId,
  registerSite,
  rotateSitePassword,
  unlockIdentity,
  type SiteRegistration,
  type VaultIdentity,
} from "@yadacoin/password-core";
import { bootTheme } from "../shared/theme-boot.js";
import { loadSettings, saveSettings } from "../shared/settings.js";

const VAULT_KEY = "yadaPasswordVault";

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
}

interface StoredVault {
  mnemonic: string;
  secondFactor: string;
  username: string;
  identityType: string;
  mainDepth: number;
  tipPrevPkh: string;
  inceptionDone: boolean;
  sites: Record<string, StoredSite>;
}

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


/** Active tab origin: scheme + FQDN + port (e.g. http://localhost:8101). */
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

async function loadVault(): Promise<StoredVault | null> {
  if (typeof chrome !== "undefined" && chrome.storage?.local) {
    const data = await chrome.storage.local.get(VAULT_KEY);
    return (data[VAULT_KEY] as StoredVault) || null;
  }
  const raw = localStorage.getItem(VAULT_KEY);
  return raw ? (JSON.parse(raw) as StoredVault) : null;
}

async function saveVault(v: StoredVault): Promise<void> {
  if (typeof chrome !== "undefined" && chrome.storage?.local) {
    await chrome.storage.local.set({ [VAULT_KEY]: v });
    return;
  }
  localStorage.setItem(VAULT_KEY, JSON.stringify(v));
}

function identityFromStored(v: StoredVault): VaultIdentity {
  return unlockIdentity(v.mnemonic, v.secondFactor, v.username, {
    identityType: v.identityType,
    mainDepth: v.mainDepth,
    tipPrevPkh: v.tipPrevPkh,
  });
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
  $("panel-setup").hidden = name !== "setup";
  $("panel-site").hidden = name !== "site";
  $("panel-status").hidden = name !== "status";
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
  const settings = await loadSettings();
  ($("nodeUrl") as HTMLInputElement).value = settings.nodeUrl;

  const vault = await loadVault();
  if (vault) {
    ($("username") as HTMLInputElement).value = vault.username;
    ($("secondFactor") as HTMLInputElement).value = vault.secondFactor;
    ($("mnemonic") as HTMLTextAreaElement).value = vault.mnemonic;
  }

  const activeOrigin = await getActiveOrigin();
  await fillSiteFromOrigin(activeOrigin, vault);

  // After inception, Site is the primary tab (current page origin prefilled).
  setTab(vault?.inceptionDone ? "site" : "setup");
  if (vault?.inceptionDone) {
    // ensure status cache warm when switching later
  }

  for (const btn of document.querySelectorAll<HTMLButtonElement>(".pm-tab")) {
    btn.addEventListener("click", () => {
      void (async () => {
        const tab = btn.dataset.tab || "setup";
        setTab(tab);
        if (tab === "status") await refreshStatus();
        if (tab === "site") {
          const origin = (await getActiveOrigin()) || activeOrigin;
          const v = await loadVault();
          await fillSiteFromOrigin(origin, v);
        }
      })();
    });
  }

  $("genSeedBtn").addEventListener("click", () => {
    ($("mnemonic") as HTMLTextAreaElement).value = createVaultSeed(128);
    showAlert("New seed generated — write it down, then Save vault", "success");
  });

  $("saveVaultBtn").addEventListener("click", async () => {
    showAlert("");
    try {
      const nodeUrl = ($("nodeUrl") as HTMLInputElement).value.trim();
      const username = ($("username") as HTMLInputElement).value.trim();
      const secondFactor = ($("secondFactor") as HTMLInputElement).value;
      const mnemonic = ($("mnemonic") as HTMLTextAreaElement).value.trim();
      const id = unlockIdentity(mnemonic, secondFactor, username);
      const prev = await loadVault();
      const stored: StoredVault = {
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
      await saveSettings({ ...settings, nodeUrl });
      showAlert(`Vault saved · K0 ${id.k0.address.slice(0, 12)}…`, "success");
    } catch (e) {
      showAlert(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("inceptionBtn").addEventListener("click", async () => {
    showAlert("");
    try {
      const nodeUrl = ($("nodeUrl") as HTMLInputElement).value.trim();
      if (!nodeUrl) throw new Error("Node URL required");
      let v = await loadVault();
      if (!v) throw new Error("Save vault first");
      if (v.inceptionDone) throw new Error("Inception already done for this vault");
      let identity = identityFromStored(v);
      const txn = buildInceptionTxn(identity);
      const res = await broadcastTxns({ baseUrl: nodeUrl }, txn);
      if (!res.ok && res.body?.status === false) {
        throw new Error(res.body?.message || `broadcast failed (${res.status})`);
      }
      identity = identityAfterInception(identity);
      v = {
        ...v,
        mainDepth: identity.mainDepth,
        tipPrevPkh: identity.tipPrevPkh,
        inceptionDone: true,
      };
      await saveVault(v);
      await saveSettings({ ...settings, nodeUrl });
      showAlert("Inception broadcast · identity on mempool/chain", "success");
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
      const nodeUrl = ($("nodeUrl") as HTMLInputElement).value.trim();
      const siteId = ($("siteId") as HTMLInputElement).value.trim();
      if (!nodeUrl || !siteId) throw new Error("Node URL and site required");
      let v = await loadVault();
      if (!v?.inceptionDone) throw new Error("Broadcast inception first");
      const identity = identityFromStored(v);
      const result = await registerSite({ baseUrl: nodeUrl }, identity, siteId);
      v = {
        ...v,
        mainDepth: result.identity.mainDepth,
        tipPrevPkh: result.identity.tipPrevPkh,
        sites: {
          ...v.sites,
          [result.site.branchPeer]: storeSite(result.site),
        },
      };
      await saveVault(v);
      $("sitePassword").textContent = result.site.currentPassword;
      showAlert(
        `Registered ${result.site.branchPeer} · counter ${result.site.counter}`,
        "success"
      );
    } catch (e) {
      showAlert(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("rotateSiteBtn").addEventListener("click", async () => {
    showAlert("");
    try {
      const nodeUrl = ($("nodeUrl") as HTMLInputElement).value.trim();
      const siteId = ($("siteId") as HTMLInputElement).value.trim();
      if (!nodeUrl || !siteId) throw new Error("Node URL and site required");
      let v = await loadVault();
      if (!v) throw new Error("No vault");
      const key = normalizeSiteId(siteId);
      const stored = v.sites[key];
      if (!stored) throw new Error("Site not registered — register first");
      const identity = identityFromStored(v);
      const site = siteFromStored(stored);
      const result = await rotateSitePassword({ baseUrl: nodeUrl }, identity, site);
      v = {
        ...v,
        sites: { ...v.sites, [key]: storeSite(result.site) },
      };
      await saveVault(v);
      $("sitePassword").textContent = result.site.currentPassword;
      showAlert(
        `Signed in & rotated · counter ${result.site.counter} · next password ready`,
        "success"
      );
    } catch (e) {
      showAlert(e instanceof Error ? e.message : String(e), "error");
    }
  });

  await refreshStatus();
}

void main();
