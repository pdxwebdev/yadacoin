import { Capacitor } from "@capacitor/core";
import {
  createAuthSession,
  DEMO_APP_SITE_ID,
  normalizeSiteId,
  pollAuthSession,
  type AuthSessionView,
} from "@yadacoin/password-core";
import { applyTheme, resolveTheme } from "@yadacoin/password-shared-ui";

const USER_KEY = "yadaDemoUsername";
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

let pollAbort: AbortController | null = null;

function setBusy(busy: boolean) {
  for (const id of ["registerBtn", "signinBtn", "statusBtn"]) {
    ($(id) as HTMLButtonElement).disabled = busy;
  }
  const cancel = $("cancelBtn") as HTMLButtonElement;
  if (cancel) cancel.disabled = !busy;
}

function applySession(action: string, view: AuthSessionView) {
  if (view.session_status === "denied" || view.session_status === "expired" || !view.ok) {
    pushLog(false, view.message || view.session_status || "failed", view.counter);
    alertMsg(view.message || view.session_status || "Failed", "error");
    return;
  }
  if (action === "signin" && !view.authenticated) {
    pushLog(false, "node did not verify the sealed password", view.counter);
    alertMsg("Auth failed: node did not verify the sealed password.", "error");
    return;
  }
  if (view.nextPasswordHash) saveAuth({ nextPasswordHash: view.nextPasswordHash });
  pushLog(true, view.message || action, view.counter);
  alertMsg(
    action === "signin"
      ? "Signed in. Node verified the sealed password against the tip."
      : view.message || "Approved",
    "success"
  );
}

async function startBridge(action: "signin" | "register" | "status") {
  if (pollAbort) pollAbort.abort();
  const username = (($("username") as HTMLInputElement).value || "").trim();
  const nodeUrl = resolveNodeUrl(($("nodeUrl") as HTMLInputElement).value);
  localStorage.setItem(NODE_KEY, nodeUrl);
  localStorage.setItem(USER_KEY, username);
  if (!nodeUrl) {
    alertMsg("Set the node URL first.", "error");
    return;
  }
  if (!username) {
    alertMsg("Enter your Yada username.", "error");
    return;
  }

  let expectedHash: string | undefined;
  if (action === "signin") {
    try {
      const tip = await fetchTipPasswordHashes(nodeUrl);
      expectedHash = tip?.pre || loadAuth()?.nextPasswordHash;
    } catch {
      expectedHash = loadAuth()?.nextPasswordHash;
    }
  }

  pollAbort = new AbortController();
  const signal = pollAbort.signal;
  setBusy(true);
  alertMsg("Creating session…", "");
  try {
    const created = await createAuthSession(nodeUrl, {
      username,
      site: siteId(),
      action,
      expectedHash,
    });
    if (!created.status || !created.session_id) {
      throw new Error(created.message || "failed to create auth session");
    }
    alertMsg(
      created.delivered
        ? "Delivered. Approve in Yada Password."
        : "Open Yada Password so it can connect, then Approve.",
      ""
    );
    const started = Date.now();
    while (!signal.aborted) {
      if (Date.now() - started > 180000) throw new Error("timed out waiting for approval");
      await new Promise((r) => setTimeout(r, 1500));
      if (signal.aborted) throw new Error("cancelled");
      const view = await pollAuthSession(nodeUrl, created.session_id);
      const st = view.session_status;
      if (st === "pending" || st === "delivered" || st === "proxied") continue;
      applySession(action, view);
      void refreshTip();
      return;
    }
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    if (message !== "cancelled") alertMsg(message, "error");
    else alertMsg("Cancelled", "error");
  } finally {
    setBusy(false);
    pollAbort = null;
  }
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
  ($("username") as HTMLInputElement).value = localStorage.getItem(USER_KEY) || "";

  $("registerBtn").addEventListener("click", () => void startBridge("register"));
  $("signinBtn").addEventListener("click", () => void startBridge("signin"));
  $("statusBtn").addEventListener("click", () => void startBridge("status"));
  $("cancelBtn").addEventListener("click", () => pollAbort?.abort());
  $("refreshBtn").addEventListener("click", () => {
    alertMsg("");
    void refreshTip();
  });

  await refreshTip();
}

void main();
