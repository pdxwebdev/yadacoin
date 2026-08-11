import {
  broadcastTxns,
  buildInceptionTxn,
  createVaultSeed,
  identityAfterInception,
  registerSite,
  unlockIdentity,
} from "@yadacoin/password-core";
import {
  applyTheme,
  resolveTheme,
  type ThemePartial,
} from "@yadacoin/password-shared-ui";

const STORAGE_KEY = "yadaPasswordMobile";

function $(id: string) {
  const el = document.getElementById(id);
  if (!el) throw new Error(id);
  return el;
}

function alertMsg(msg: string, kind: "" | "error" | "success" = "") {
  const el = $("alert");
  if (!msg) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.textContent = msg;
  el.className = `pm-alert${kind ? ` pm-alert--${kind}` : ""}`;
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

async function main() {
  await applyThemeFromForm();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const s = JSON.parse(raw);
      if (s.nodeUrl) ($("nodeUrl") as HTMLInputElement).value = s.nodeUrl;
      if (s.mnemonic) ($("mnemonic") as HTMLTextAreaElement).value = s.mnemonic;
      if (s.username) ($("username") as HTMLInputElement).value = s.username;
    }
  } catch {
    /* ignore */
  }

  $("themeForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await applyThemeFromForm();
    alertMsg("Theme applied", "success");
  });

  $("genSeedBtn").addEventListener("click", () => {
    ($("mnemonic") as HTMLTextAreaElement).value = createVaultSeed(128);
    alertMsg("Seed generated", "success");
  });

  $("inceptionBtn").addEventListener("click", async () => {
    alertMsg("");
    try {
      const nodeUrl = ($("nodeUrl") as HTMLInputElement).value.trim();
      const username = ($("username") as HTMLInputElement).value.trim();
      const secondFactor = ($("secondFactor") as HTMLInputElement).value;
      const mnemonic = ($("mnemonic") as HTMLTextAreaElement).value.trim();
      const id = unlockIdentity(mnemonic, secondFactor, username);
      const txn = buildInceptionTxn(id);
      const res = await broadcastTxns({ baseUrl: nodeUrl }, txn);
      if (!res.ok && res.body?.status === false) {
        throw new Error(res.body?.message || "broadcast failed");
      }
      const after = identityAfterInception(id);
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          nodeUrl,
          mnemonic,
          username,
          secondFactor,
          mainDepth: after.mainDepth,
          tipPrevPkh: after.tipPrevPkh,
        })
      );
      alertMsg("Inception broadcast", "success");
    } catch (e) {
      alertMsg(e instanceof Error ? e.message : String(e), "error");
    }
  });

  $("registerSiteBtn").addEventListener("click", async () => {
    alertMsg("");
    try {
      const nodeUrl = ($("nodeUrl") as HTMLInputElement).value.trim();
      const siteId = ($("siteId") as HTMLInputElement).value.trim();
      const username = ($("username") as HTMLInputElement).value.trim();
      const secondFactor = ($("secondFactor") as HTMLInputElement).value;
      const mnemonic = ($("mnemonic") as HTMLTextAreaElement).value.trim();
      const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      const id = unlockIdentity(mnemonic, secondFactor, username, {
        mainDepth: raw.mainDepth ?? 1,
        tipPrevPkh: raw.tipPrevPkh ?? "",
      });
      const result = await registerSite({ baseUrl: nodeUrl }, id, siteId);
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          ...raw,
          nodeUrl,
          mnemonic,
          username,
          secondFactor,
          mainDepth: result.identity.mainDepth,
          tipPrevPkh: result.identity.tipPrevPkh,
        })
      );
      $("sitePassword").textContent = result.site.currentPassword;
      alertMsg(`Site ${result.site.branchPeer} registered`, "success");
    } catch (e) {
      alertMsg(e instanceof Error ? e.message : String(e), "error");
    }
  });
}

void main();
