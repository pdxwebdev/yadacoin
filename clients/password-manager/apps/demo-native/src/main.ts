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
import { OpenPasswordManager } from "./open-password-manager";

const PENDING_KEY = "yadaDemoPendingNonce";
const VERIFY_HASH_KEY = "yadaDemoVerifyHash";
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

function resolveNodeUrl(url: string): string {
  let u = (url || "").trim().replace(/\/+$/, "");
  if (Capacitor.getPlatform() === "android") {
    u = u.replace(/127\.0\.0\.1/g, "10.0.2.2").replace(/localhost/gi, "10.0.2.2");
  }
  return u;
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
      await OpenPasswordManager.open({ url });
      return;
    }
  } catch (e) {
    console.warn("OpenPasswordManager failed, falling back", e);
  }
  try {
    if (Capacitor.isNativePlatform()) {
      const opener = App as unknown as { openUrl: (o: { url: string }) => Promise<void> };
      await opener.openUrl({ url });
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

interface DemoAuth {
  /** Hash of the password expected on the next sign-in (tip prerotated). */
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

/** Tip password hashes from the node (source of truth across devices). */
async function fetchTipPasswordHashes(
  nodeUrl: string
): Promise<{ pre: string; twice: string; counter: number } | null> {
  const origin = siteId();
  const res = await fetch(
    nodeUrl +
      "/password-rotation/offchain/tip?branch_peer=" +
      encodeURIComponent(origin),
    { headers: { Accept: "application/json" } }
  );
  const data = await res.json();
  if (!res.ok || !data.status || !data.tip) return null;
  const pw = data.tip.password || {};
  return {
    pre: String(pw.prerotated_password_hash || ""),
    twice: String(pw.twice_prerotated_password_hash || ""),
    counter: Number(data.tip.counter ?? 0),
  };
}

async function startBridge(action: "signin" | "register" | "status") {
  const nonce = newNonce();
  sessionStorage.setItem(PENDING_KEY, nonce);
  sessionStorage.removeItem(VERIFY_HASH_KEY);

  const nodeUrl = resolveNodeUrl(($("nodeUrl") as HTMLInputElement).value);
  localStorage.setItem(NODE_KEY, nodeUrl);

  let expectedHash: string | undefined;
  if (action === "signin") {
    // Prefer node tip prerotated hash so a fresh device never needs local register state.
    try {
      if (nodeUrl) {
        const tip = await fetchTipPasswordHashes(nodeUrl);
        if (tip?.pre) {
          expectedHash = tip.pre;
          sessionStorage.setItem(VERIFY_HASH_KEY, tip.pre);
        }
      }
    } catch {
      /* fall through to local cache */
    }
    if (!expectedHash) {
      expectedHash = loadAuth()?.nextPasswordHash;
      if (expectedHash) sessionStorage.setItem(VERIFY_HASH_KEY, expectedHash);
    }
  }

  const url = buildPasswordManagerUrl({
    action,
    site: siteId(),
    callback: `${DEMO_HARNESS_SCHEME}://result`,
    nonce,
    expectedHash: action === "signin" ? expectedHash : undefined,
  });
  alertMsg(`Opening Yada Password… (${action})`, "");
  void openManager(url).catch((e) =>
    alertMsg(e instanceof Error ? e.message : String(e), "error")
  );
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
  const verifyHash = sessionStorage.getItem(VERIFY_HASH_KEY) || "";
  sessionStorage.removeItem(VERIFY_HASH_KEY);

  if (result.action === "register" && password && nextHash) {
    // After register, tip.pre is current; next sign-in consumes current then advances.
    // nextPasswordHash from vault is hash(new tip current) after register = hash(next at register).
    // For first sign-in, node tip.pre is authoritative — cache nextHash only as a hint.
    saveAuth({ nextPasswordHash: nextHash });
    pushLog(true, "registered · vault restored/created", result.counter);
    alertMsg("Registered / restored. Sign-in uses the node tip (no local-only gate).", "success");
    void refreshTip();
    return;
  }

  if (result.action === "signin" && password) {
    // Verify against tip.pre captured before rotate (multi-device safe). Local cache is optional.
    if (verifyHash && !verifyPassword(password, verifyHash)) {
      pushLog(false, "password does not match tip prerotated hash", result.counter);
      alertMsg(
        "Auth failed: password does not match node tip. Check vault seed/2FA or re-save vault.",
        "error"
      );
      void refreshTip();
      return;
    }
    if (nextHash) saveAuth({ nextPasswordHash: nextHash });
    pushLog(true, "signed in · tip verified", result.counter);
    alertMsg("Signed in. Password matched node tip; local cache updated.", "success");
    if (nextHash) $("tipTwice").textContent = nextHash;
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

  const nodeUrl = resolveNodeUrl(($("nodeUrl") as HTMLInputElement).value);
  localStorage.setItem(NODE_KEY, nodeUrl);
  if (!nodeUrl) {
    $("statusPill").textContent = "set node URL";
    $("statusPill").className = "pill warn";
    return;
  }

  try {
    const tip = await fetchTipPasswordHashes(nodeUrl);
    if (!tip) {
      $("statusPill").textContent = "not registered";
      $("statusPill").className = "pill warn";
      $("counterPill").textContent = "counter —";
      $("tipPre").textContent = "—";
      $("tipTwice").textContent = "—";
      return;
    }
    $("statusPill").textContent = "registered on node";
    $("statusPill").className = "pill ok";
    $("counterPill").textContent = "counter " + tip.counter;
    $("tipPre").textContent = tip.pre || "—";
    $("tipTwice").textContent = tip.twice || "—";
    // Keep local cache aligned with tip so a cold start can still pass expectedHash.
    if (tip.pre) saveAuth({ nextPasswordHash: tip.pre });
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

  $("registerBtn").addEventListener("click", () => void startBridge("register"));
  $("signinBtn").addEventListener("click", () => void startBridge("signin"));
  $("statusBtn").addEventListener("click", () => void startBridge("status"));
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
