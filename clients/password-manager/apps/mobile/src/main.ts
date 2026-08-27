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
  resyncVaultFromNode,
  unlockIdentity,
  type SiteRegistration,
  type VaultIdentity,
} from "@yadacoin/password-core";
import {
  applyTheme,
  resolveTheme,
  type ThemePartial,
} from "@yadacoin/password-shared-ui";

const STORAGE_KEY = "yadaPasswordMobileVault";

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
  nodeUrl: string;
  mnemonic: string;
  secondFactor: string;
  username: string;
  identityType: string;
  mainDepth: number;
  tipPrevPkh: string;
  inceptionDone: boolean;
  sites: Record<string, StoredSite>;
  theme?: {
    presetId: string;
    mode: "light" | "dark" | "system";
    primary: string;
    themeUrl: string;
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

function loadVault(): StoredVault | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredVault) : null;
  } catch {
    return null;
  }
}

function saveVault(v: StoredVault) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(v));
}

function appOrigin(): string {
  // Prefer real page origin (http://ip:port or capacitor://localhost)
  try {
    if (location.protocol === "http:" || location.protocol === "https:") {
      return location.origin.toLowerCase();
    }
  } catch {
    /* ignore */
  }
  // Capacitor / file fallback — stable demo app id
  return "yada-password-mobile-demo";
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

function setTab(name: string) {
  for (const btn of document.querySelectorAll<HTMLButtonElement>(".mobile-tab")) {
    btn.setAttribute("aria-selected", btn.dataset.tab === name ? "true" : "false");
  }
  $("panel-auth").hidden = name !== "auth";
  $("panel-vault").hidden = name !== "vault";
  $("panel-theme").hidden = name !== "theme";
}

function pushLog(ok: boolean, note: string, counter?: number | null) {
  const box = $("authLog");
  if (box.textContent === "No attempts yet") box.textContent = "";
  const row = document.createElement("div");
  row.className = "log-entry " + (ok ? "log-ok" : "log-bad");
  const t = new Date().toLocaleTimeString();
  row.textContent = `${t} · ${ok ? "OK" : "FAIL"} · c=${counter ?? "—"} · ${note}`;
  box.insertBefore(row, box.firstChild);
}

async function applyThemeFromForm() {
  const remoteUrl = ($("themeUrl") as HTMLInputElement).value.trim();
  let remote: ThemePartial | null = null;
  if (remoteUrl) {
    try {
      const r = await fetch(remoteUrl);
      if (r.ok) remote = (await r.json()) as ThemePartial;
    } catch {
      /* ignore */
    }
  }
  const theme = resolveTheme({
    preset: ($("preset") as HTMLSelectElement).value,
    remote,
    user: {
      mode: ($("mode") as HTMLSelectElement).value as "light" | "dark" | "system",
      colors: { primary: ($("primary") as HTMLInputElement).value },
    },
  });
  applyTheme(theme);
  const brand = document.getElementById("brandName");
  if (brand && theme.brand?.name) brand.textContent = theme.brand.name;
}

function refreshVaultStatus() {
  const v = loadVault();
  if (!v) {
    $("k0Addr").textContent = "no vault";
    $("vaultStatus").textContent = "Create a vault first";
    $("sitePasswordDisplay").textContent = "—";
    return;
  }
  try {
    const id = identityFromVault(v);
    $("k0Addr").textContent = id.k0.address;
    $("vaultStatus").textContent = v.inceptionDone
      ? `incepted · main depth ${v.mainDepth}`
      : "saved · inception pending";
    const origin = normalizeSiteId(appOrigin());
    const site = v.sites?.[origin];
    $("sitePasswordDisplay").textContent = site?.currentPassword || "— not registered —";
  } catch (e) {
    $("k0Addr").textContent = e instanceof Error ? e.message : String(e);
  }
}

async function refreshTip() {
  const origin = normalizeSiteId(appOrigin());
  $("appOrigin").textContent = origin;
  $("statusPill").textContent = "checking…";
  $("statusPill").className = "pill";

  const v = loadVault();
  const nodeUrl = (v?.nodeUrl || ($("nodeUrl") as HTMLInputElement).value || "").replace(
    /\/+$/,
    ""
  );
  if (!nodeUrl) {
    $("statusPill").textContent = "set node URL";
    $("statusPill").className = "pill warn";
    return;
  }

  try {
    const res = await fetch(
      nodeUrl +
        "/password-rotation/offchain/tip?branch_peer=" +
        encodeURIComponent(origin),
      { headers: { Accept: "application/json" } }
    );
    const data = await res.json();
    if (!res.ok || !data.status) {
      $("statusPill").textContent = "not registered";
      $("statusPill").className = "pill warn";
      $("counterPill").textContent = "counter —";
      $("tipPre").textContent = "—";
      $("tipTwice").textContent = "—";
      return;
    }
    const tip = data.tip || {};
    const pw = tip.password || {};
    $("statusPill").textContent = "registered";
    $("statusPill").className = "pill ok";
    $("counterPill").textContent = "counter " + (tip.counter ?? "—");
    $("tipPre").textContent = pw.prerotated_password_hash || "—";
    $("tipTwice").textContent = pw.twice_prerotated_password_hash || "—";
  } catch (e) {
    $("statusPill").textContent = "unreachable";
    $("statusPill").className = "pill bad";
    alertMsg(e instanceof Error ? e.message : String(e), "error");
  }
}

async function main() {
  const origin = normalizeSiteId(appOrigin());
  $("appOrigin").textContent = origin;

  const v0 = loadVault();
  if (v0) {
    ($("nodeUrl") as HTMLInputElement).value = v0.nodeUrl || "";
    ($("username") as HTMLInputElement).value = v0.username || "";
    ($("secondFactor") as HTMLInputElement).value = v0.secondFactor || "";
    ($("mnemonic") as HTMLTextAreaElement).value = v0.mnemonic || "";
    if (v0.theme) {
      ($("preset") as HTMLSelectElement).value = v0.theme.presetId || "dark";
      ($("mode") as HTMLSelectElement).value = v0.theme.mode || "dark";
      if (v0.theme.primary) ($("primary") as HTMLInputElement).value = v0.theme.primary;
      ($("themeUrl") as HTMLInputElement).value = v0.theme.themeUrl || "";
    } else if (v0.nodeUrl) {
      ($("themeUrl") as HTMLInputElement).value =
        v0.nodeUrl.replace(/\/+$/, "") + "/password-rotation/theme.json";
    }
  }

  // Default node URL to same host when served from the node
  if (!($("nodeUrl") as HTMLInputElement).value) {
    if (location.protocol === "http:" || location.protocol === "https:") {
      ($("nodeUrl") as HTMLInputElement).value = location.origin;
      ($("themeUrl") as HTMLInputElement).value =
        location.origin + "/password-rotation/theme.json";
    }
  }

  await applyThemeFromForm();
  refreshVaultStatus();

  setTab(v0?.inceptionDone ? "auth" : "vault");
  await refreshTip();

  for (const btn of document.querySelectorAll<HTMLButtonElement>(".mobile-tab")) {
    btn.addEventListener("click", () => {
      setTab(btn.dataset.tab || "auth");
      if (btn.dataset.tab === "auth") {
        refreshVaultStatus();
        void refreshTip();
      }
      if (btn.dataset.tab === "vault") refreshVaultStatus();
    });
  }

  $("themeForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await applyThemeFromForm();
    const v = loadVault();
    if (v) {
      v.theme = {
        presetId: ($("preset") as HTMLSelectElement).value,
        mode: ($("mode") as HTMLSelectElement).value as "light" | "dark" | "system",
        primary: ($("primary") as HTMLInputElement).value,
        themeUrl: ($("themeUrl") as HTMLInputElement).value.trim(),
      };
      saveVault(v);
    }
    alertMsg("Theme applied", "success");
  });

  $("genSeedBtn").addEventListener("click", () => {
    ($("mnemonic") as HTMLTextAreaElement).value = createVaultSeed(128);
    alertMsg("Seed generated — write it down, then Save vault", "success");
  });

  $("saveVaultBtn").addEventListener("click", () => {
    alertMsg("");
    try {
      const nodeUrl = ($("nodeUrl") as HTMLInputElement).value.trim().replace(/\/+$/, "");
      const username = ($("username") as HTMLInputElement).value.trim();
      const secondFactor = ($("secondFactor") as HTMLInputElement).value;
      const mnemonic = ($("mnemonic") as HTMLTextAreaElement).value.trim();
      const id = unlockIdentity(mnemonic, secondFactor, username);
      const prev = loadVault();
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
        theme: prev?.theme,
      };
      if (!prev || prev.mnemonic !== mnemonic) {
        stored.mainDepth = 0;
        stored.tipPrevPkh = "";
        stored.inceptionDone = false;
        stored.sites = {};
      }
      saveVault(stored);
      refreshVaultStatus();
      alertMsg(`Vault saved · K0 ${id.k0.address.slice(0, 12)}…`, "success");
    } catch (e) {
      alertMsg(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("inceptionBtn").addEventListener("click", async () => {
    alertMsg("");
    try {
      let v = loadVault();
      if (!v) throw new Error("Save vault first");
      if (v.inceptionDone) throw new Error("Inception already done");
      const nodeUrl = ($("nodeUrl") as HTMLInputElement).value.trim().replace(/\/+$/, "");
      if (!nodeUrl) throw new Error("Node URL required");
      v.nodeUrl = nodeUrl;
      let identity = identityFromVault(v);
      const txn = buildInceptionTxn(identity);
      const res = await broadcastTxns({ baseUrl: nodeUrl }, txn);
      if (!res.ok && res.body?.status === false) {
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
      saveVault(v);
      refreshVaultStatus();
      alertMsg("Inception broadcast", "success");
      setTab("auth");
      await refreshTip();
    } catch (e) {
      alertMsg(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("refreshTipBtn").addEventListener("click", () => {
    alertMsg("");
    void refreshTip();
  });

  $("resyncBtn").addEventListener("click", async () => {
    alertMsg("");
    try {
      let v = loadVault();
      if (!v) throw new Error("No vault");
      const nodeUrl = (v.nodeUrl || ($("nodeUrl") as HTMLInputElement).value || "").replace(
        /\/+$/,
        ""
      );
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
        mainDepth: result.identity.mainDepth,
        tipPrevPkh: result.identity.tipPrevPkh,
        inceptionDone: result.kelDepth > 0,
        sites: nextSites,
      };
      saveVault(v);
      refreshVaultStatus();
      await refreshTip();
      const bits = [
        `KEL depth ${result.kelDepth}`,
        result.rewoundSites.length ? `rewound ${result.rewoundSites.length}` : "",
        result.removedSites.length ? `removed ${result.removedSites.length}` : "",
      ].filter(Boolean);
      alertMsg("Resync complete · " + bits.join(" · "), "success");
    } catch (e) {
      alertMsg(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("registerSiteBtn").addEventListener("click", async () => {
    alertMsg("");
    try {
      let v = loadVault();
      if (!v?.inceptionDone) throw new Error("Broadcast inception first (Vault tab)");
      const nodeUrl = (v.nodeUrl || ($("nodeUrl") as HTMLInputElement).value)
        .trim()
        .replace(/\/+$/, "");
      if (!nodeUrl) throw new Error("Node URL required");
      const origin = normalizeSiteId(appOrigin());
      if (v.sites[origin]) {
        alertMsg("Already registered — use Sign in & rotate", "success");
        $("sitePasswordDisplay").textContent = v.sites[origin]!.currentPassword;
        return;
      }
      const identity = identityFromVault(v);
      const result = await registerSite({ baseUrl: nodeUrl }, identity, origin);
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
      saveVault(v);
      $("sitePasswordDisplay").textContent = result.site.currentPassword;
      alertMsg(
        `Registered ${result.site.branchPeer} · counter ${result.site.counter}`,
        "success"
      );
      pushLog(true, "registered", result.site.counter);
      await refreshTip();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      alertMsg(msg, "error");
      pushLog(false, msg, null);
    }
  });

  $("signinRotateBtn").addEventListener("click", async () => {
    alertMsg("");
    const btn = $("signinRotateBtn") as HTMLButtonElement;
    btn.disabled = true;
    try {
      let v = loadVault();
      if (!v?.inceptionDone) throw new Error("Vault not incepted");
      const nodeUrl = (v.nodeUrl || "").replace(/\/+$/, "");
      if (!nodeUrl) throw new Error("Node URL required");
      const origin = normalizeSiteId(appOrigin());
      const stored = v.sites[origin];
      if (!stored) throw new Error("Register this app first");
      const identity = identityFromVault(v);
      const site = siteFromStored(stored);
      const result = await rotateSitePassword({ baseUrl: nodeUrl }, identity, site);
      v = {
        ...v,
        sites: { ...v.sites, [origin]: storeSite(result.site) },
      };
      saveVault(v);
      $("sitePasswordDisplay").textContent = result.site.currentPassword;
      alertMsg(
        `Signed in & rotated · counter ${result.site.counter}`,
        "success"
      );
      pushLog(true, "signed in & rotated", result.site.counter);
      await refreshTip();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      alertMsg(msg, "error");
      pushLog(false, msg, null);
    } finally {
      btn.disabled = false;
    }
  });
}

void main();
