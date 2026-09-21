import {
  broadcastTxns,
  buildInceptionTxn,
  bytesToHex,
  createLocalStorageBackend,
  createVaultSeed,
  hexToBytes,
  identityAfterInception,
  isAlreadyInceptedError,
  LEGACY_KEYS,
  materialFromPrivCc,
  normalizeSiteId,
  registerSite,
  rotateSitePassword,
  resyncVaultFromNode,
  syncInceptionFromNode,
  unlockIdentity,
  vaultIdFromData,
  VaultStore,
  type SiteRegistration,
  type StoredSite,
  type StoredVault,
  type VaultIdentity,
} from "@yadacoin/password-core";
import {
  applyTheme,
  resolveTheme,
  type ThemePartial,
} from "@yadacoin/password-shared-ui";

const store = new VaultStore(createLocalStorageBackend());

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

async function loadVault(): Promise<StoredVault | null> {
  const entry = await store.getActiveVault();
  return entry?.data ?? null;
}

async function saveVault(v: StoredVault): Promise<void> {
  const id = vaultIdFromData(v);
  await store.updateVaultData(id, v);
  await store.setActiveVaultId(id);
}

function fillFormFromVault(v: StoredVault | null) {
  if (!v) {
    ($("username") as HTMLInputElement).value = "";
    ($("secondFactor") as HTMLInputElement).value = "";
    ($("mnemonic") as HTMLTextAreaElement).value = "";
    return;
  }
  if (v.nodeUrl) ($("nodeUrl") as HTMLInputElement).value = v.nodeUrl || "";
  ($("username") as HTMLInputElement).value = v.username || "";
  ($("secondFactor") as HTMLInputElement).value = v.secondFactor || "";
  ($("mnemonic") as HTMLTextAreaElement).value = v.mnemonic || "";
  if (v.theme) {
    ($("preset") as HTMLSelectElement).value = v.theme.presetId || "dark";
    ($("mode") as HTMLSelectElement).value = v.theme.mode || "dark";
    if (v.theme.primary) ($("primary") as HTMLInputElement).value = v.theme.primary;
    ($("themeUrl") as HTMLInputElement).value = v.theme.themeUrl || "";
  }
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
  refreshVaultStatus();
  await refreshTip();
}

function appOrigin(): string {
  try {
    if (location.protocol === "http:" || location.protocol === "https:") {
      return location.origin.toLowerCase();
    }
  } catch {
    /* ignore */
  }
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

async function ensureIncepted(v: StoredVault): Promise<StoredVault> {
  const nodeUrl = (v.nodeUrl || "").replace(/\/+$/, "");
  if (!nodeUrl) return v;
  try {
    const id = identityFromVault(v);
    const { identity, inceptionDone } = await syncInceptionFromNode(
      { baseUrl: nodeUrl },
      id
    );
    if (!inceptionDone) return v;
    const next: StoredVault = {
      ...v,
      nodeUrl,
      inceptionDone: true,
      mainDepth: identity.mainDepth,
      tipPrevPkh: identity.tipPrevPkh,
    };
    if (
      next.inceptionDone !== v.inceptionDone ||
      next.mainDepth !== v.mainDepth ||
      next.tipPrevPkh !== v.tipPrevPkh
    ) {
      await saveVault(next);
    }
    return next;
  } catch {
    return v;
  }
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

async function refreshVaultStatus() {
  const v = await loadVault();
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

  const v = await loadVault();
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

  await store.migrateLegacy(LEGACY_KEYS.mobile);

  const v0 = await loadVault();
  if (v0) {
    fillFormFromVault(v0);
    if (!v0.theme && v0.nodeUrl) {
      ($("themeUrl") as HTMLInputElement).value =
        v0.nodeUrl.replace(/\/+$/, "") + "/password-rotation/theme.json";
    }
  }

  if (!($("nodeUrl") as HTMLInputElement).value) {
    if (location.protocol === "http:" || location.protocol === "https:") {
      ($("nodeUrl") as HTMLInputElement).value = location.origin;
      ($("themeUrl") as HTMLInputElement).value =
        location.origin + "/password-rotation/theme.json";
    }
  }

  await refreshVaultSelect();
  await applyThemeFromForm();
  await refreshVaultStatus();

  setTab(v0?.inceptionDone ? "auth" : "vault");
  await refreshTip();

  ($("vaultSelect") as HTMLSelectElement).addEventListener("change", () => {
    void (async () => {
      const id = ($("vaultSelect") as HTMLSelectElement).value;
      if (!id) return;
      try {
        await switchToVault(id);
        alertMsg("Switched vault", "success");
      } catch (e) {
        alertMsg(e instanceof Error ? e.message : String(e), "error");
      }
    })();
  });

  $("newVaultBtn").addEventListener("click", () => {
    fillFormFromVault(null);
    setTab("vault");
    alertMsg("Enter a new seed (or Generate), then Save vault", "success");
  });

  $("deleteVaultBtn").addEventListener("click", () => {
    void (async () => {
      const id = await store.getActiveVaultId();
      if (!id) {
        alertMsg("No vault to delete", "error");
        return;
      }
      if (!confirm("Delete the active vault from this device? This cannot be undone.")) {
        return;
      }
      await store.deleteVault(id);
      const next = await store.getActiveVault();
      fillFormFromVault(next?.data ?? null);
      await refreshVaultSelect();
      await refreshVaultStatus();
      await refreshTip();
      alertMsg("Vault deleted", "success");
    })();
  });

  for (const btn of document.querySelectorAll<HTMLButtonElement>(".mobile-tab")) {
    btn.addEventListener("click", () => {
      setTab(btn.dataset.tab || "auth");
      if (btn.dataset.tab === "auth") {
        void refreshVaultStatus();
        void refreshTip();
      }
      if (btn.dataset.tab === "vault") void refreshVaultStatus();
    });
  }

  $("themeForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await applyThemeFromForm();
    const v = await loadVault();
    if (v) {
      v.theme = {
        presetId: ($("preset") as HTMLSelectElement).value,
        mode: ($("mode") as HTMLSelectElement).value as "light" | "dark" | "system",
        primary: ($("primary") as HTMLInputElement).value,
        themeUrl: ($("themeUrl") as HTMLInputElement).value.trim(),
      };
      await saveVault(v);
    }
    alertMsg("Theme applied", "success");
  });

  $("genSeedBtn").addEventListener("click", () => {
    ($("mnemonic") as HTMLTextAreaElement).value = createVaultSeed(128);
    alertMsg("Seed generated — write it down, then Save vault", "success");
  });

  $("saveVaultBtn").addEventListener("click", () => {
    void (async () => {
      alertMsg("");
      try {
        const nodeUrl = ($("nodeUrl") as HTMLInputElement).value.trim().replace(/\/+$/, "");
        const username = ($("username") as HTMLInputElement).value.trim();
        const secondFactor = ($("secondFactor") as HTMLInputElement).value;
        const mnemonic = ($("mnemonic") as HTMLTextAreaElement).value.trim();
        const id = unlockIdentity(mnemonic, secondFactor, username);
        const vaultId = id.k0.address;
        const existing = await store.getVault(vaultId);
        const prev = existing?.data ?? null;
        let stored: StoredVault = {
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
        await store.saveVault(vaultId, stored, {
          name: username || existing?.name,
        });
        await store.setActiveVaultId(vaultId);
        if (nodeUrl) stored = await ensureIncepted(stored);
        await refreshVaultSelect(vaultId);
        await refreshVaultStatus();
        const ready = stored.inceptionDone
          ? "incepted on node"
          : "inception still needed";
        alertMsg(
          `Vault saved · K0 ${id.k0.address.slice(0, 12)}… · ${ready}`,
          "success"
        );
        if (stored.inceptionDone) setTab("auth");
      } catch (e) {
        alertMsg(e instanceof Error ? e.message : String(e), "error");
      }
    })();
  });

  $("inceptionBtn").addEventListener("click", async () => {
    alertMsg("");
    try {
      let v = await loadVault();
      if (!v) throw new Error("Save vault first");
      const nodeUrl = ($("nodeUrl") as HTMLInputElement).value.trim().replace(/\/+$/, "");
      if (!nodeUrl) throw new Error("Node URL required");
      v = await ensureIncepted({ ...v, nodeUrl });
      if (v.inceptionDone) {
        await refreshVaultStatus();
        alertMsg("Already incepted on node — vault updated", "success");
        setTab("auth");
        await refreshTip();
        return;
      }
      let identity = identityFromVault(v);
      const txn = buildInceptionTxn(identity);
      const res = await broadcastTxns({ baseUrl: nodeUrl }, txn);
      const already = isAlreadyInceptedError(res.body?.message);
      if (!res.ok && res.body?.status === false && !already) {
        v = await ensureIncepted(v);
        if (v.inceptionDone) {
          await refreshVaultStatus();
          alertMsg("Already incepted on node — vault updated", "success");
          setTab("auth");
          await refreshTip();
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
      await saveVault(v);
      await refreshVaultStatus();
      alertMsg(already ? "Inception already on chain — vault updated" : "Inception broadcast", "success");
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
      let v = await loadVault();
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
      await saveVault(v);
      await refreshVaultStatus();
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
      let v = await loadVault();
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
      await saveVault(v);
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
      let v = await loadVault();
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
      await saveVault(v);
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
