import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";
import {
  buildPasswordManagerUrl,
  DEMO_APP_SITE_ID,
  DEMO_HARNESS_SCHEME,
  newNonce,
  normalizeSiteId,
  parseBridgeResult,
  verifyPassword,
  type BridgeResult,
} from "@yadacoin/password-core";
import { applyTheme, resolveTheme } from "@yadacoin/password-shared-ui";

const PENDING_KEY = "yadaDemoPendingNonce";
const NODE_KEY = "yadaDemoNodeUrl";
const AUTH_KEY = "yadaDemoAuth";

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

function siteId(): string {
  return normalizeSiteId(DEMO_APP_SITE_ID);
}

function pushLog(ok: boolean, note: string, counter?: number | null) {
  const box = $("log");
  if (box.textContent === "No events yet") box.textContent = "";
  const row = document.createElement("div");
  row.className = "log-entry " + (ok ? "log-ok" : "log-bad");
  row.textContent = `${new Date().toLocaleTimeString()} · ${ok ? "OK" : "FAIL"} · c=${counter ?? "—"} · ${note}`;
  box.insertBefore(row, box.firstChild);
}

async function openManager(url: string) {
  console.info("[yadademo] open manager:", url);
  try {
    if (Capacitor.isNativePlatform()) {
      // Capacitor App.openUrl → Android ACTION_VIEW / iOS openURL
      await App.openUrl({ url });
      return;
    }
  } catch (e) {
    console.warn("App.openUrl failed, falling back", e);
  }
  try {
    window.open(url, "_system");
  } catch {
    /* ignore */
  }
  window.location.href = url;
}

function startBridge(action: "signin" | "register" | "status") {
  const nonce = newNonce();
  sessionStorage.setItem(PENDING_KEY, nonce);
  const url = buildPasswordManagerUrl({
    action,
    site: siteId(),
    callback: `${DEMO_HARNESS_SCHEME}://result`,
    nonce,
  });
  alertMsg(`Opening Yada Password… (${action})`, "");
  void openManager(url).catch((e) =>
    alertMsg(e instanceof Error ? e.message : String(e), "error")
  );
}

interface DemoAuth {
  nextPasswordHash: string;
}

function loadAuth(): DemoAuth | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    return raw ? (JSON.parse(raw) as DemoAuth) : null;
  } catch {
    return null;
  }
}

function saveAuth(auth: DemoAuth) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
}

function handleResult(result: BridgeResult) {
  const expected = sessionStorage.getItem(PENDING_KEY);
  if (expected && result.nonce !== expected) {
    pushLog(false, `ignored result (nonce mismatch)`, result.counter);
    return;
  }
  sessionStorage.removeItem(PENDING_KEY);
  if (!result.ok) {
    pushLog(false, result.message || "failed", result.counter);
    alertMsg(result.message || "Failed", "error");
    void refreshTip();
    return;
  }

  const nextHash = result.nextPasswordHash || "";
  const password = result.password || "";

  if (result.action === "register" && password && nextHash) {
    saveAuth({ nextPasswordHash: nextHash });
    pushLog(true, "registered · stored next password hash", result.counter);
    alertMsg("Registered. Next password hash stored locally.", "success");
    $("tipPre").textContent = "(local) current password received";
    $("tipTwice").textContent = nextHash;
    void refreshTip();
    return;
  }

  if (result.action === "signin" && password && nextHash) {
    const auth = loadAuth();
    if (!auth?.nextPasswordHash) {
      pushLog(false, "no stored next hash — register first", result.counter);
      alertMsg("No stored next password hash — register first", "error");
      return;
    }
    if (!verifyPassword(password, auth.nextPasswordHash)) {
      pushLog(false, "password does not match stored next hash", result.counter);
      alertMsg("Auth failed: password does not match stored next hash", "error");
      return;
    }
    saveAuth({ nextPasswordHash: nextHash });
    pushLog(true, "signed in · next hash rotated", result.counter);
    alertMsg("Signed in. Password matched; next hash updated.", "success");
    $("tipTwice").textContent = nextHash;
    void refreshTip();
    return;
  }

  pushLog(true, result.message || "ok", result.counter);
  alertMsg(result.message || "Success", "success");
  void refreshTip();
}

async function handleDeepLink(url: string) {
  const result = parseBridgeResult(url);
  if (!result) return;
  handleResult(result);
}

async function refreshTip() {
  const origin = siteId();
  $("siteId").textContent = origin;
  $("statusPill").textContent = "checking…";
  $("statusPill").className = "pill";

  const nodeUrl = ($("nodeUrl") as HTMLInputElement).value.trim().replace(/\/+$/, "");
  localStorage.setItem(NODE_KEY, nodeUrl);
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
    $("statusPill").textContent = "registered on node";
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
  applyTheme(resolveTheme({ preset: "dark", user: { mode: "dark" } }));
  $("siteId").textContent = siteId();
  ($("nodeUrl") as HTMLInputElement).value = localStorage.getItem(NODE_KEY) || "";

  $("registerBtn").addEventListener("click", () => startBridge("register"));
  $("signinBtn").addEventListener("click", () => startBridge("signin"));
  $("statusBtn").addEventListener("click", () => startBridge("status"));
  $("refreshBtn").addEventListener("click", () => {
    alertMsg("");
    void refreshTip();
  });

  if (Capacitor.isNativePlatform()) {
    App.addListener("appUrlOpen", ({ url }) => {
      void handleDeepLink(url);
    });
    const launch = await App.getLaunchUrl();
    if (launch?.url) void handleDeepLink(launch.url);
  } else {
    const params = new URLSearchParams(location.search);
    const dl = params.get("dl");
    if (dl) void handleDeepLink(dl);
  }

  await refreshTip();
}

void main();
