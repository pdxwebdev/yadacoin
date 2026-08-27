/** Native app ↔ app bridge (mirrors web harness ↔ extension postMessage). */

export const PASSWORD_MANAGER_SCHEME = "yadapass";
export const DEMO_HARNESS_SCHEME = "yadademo";

export type BridgeAction = "signin" | "register" | "status";

export interface BridgeRequest {
  action: BridgeAction;
  /** Full origin / site id (scheme + FQDN + port or app id) */
  site: string;
  /** Callback URL base, e.g. yadademo://result */
  callback: string;
  nonce: string;
}

export interface BridgeResult {
  nonce: string;
  ok: boolean;
  action?: BridgeAction;
  counter?: number | null;
  registered?: boolean;
  message?: string;
  /** Current site password for the relying app to verify. */
  password?: string;
  /** PHC (or hex) of the next password. */
  nextPasswordHash?: string;
}

const ACTIONS = new Set<BridgeAction>(["signin", "register", "status"]);

function isAction(v: string | null | undefined): v is BridgeAction {
  return !!v && ACTIONS.has(v as BridgeAction);
}

/**
 * Build deep link into the password manager.
 * Uses host "auth" + action query param (most reliable across Android/iOS URL parsers).
 * Also accepted: yadapass://register?... (host = action).
 */
export function buildPasswordManagerUrl(req: BridgeRequest): string {
  // Manual construction avoids URL() quirks with custom schemes on some WebViews
  const q = new URLSearchParams();
  q.set("action", req.action);
  q.set("site", req.site);
  q.set("callback", req.callback);
  q.set("nonce", req.nonce);
  return `${PASSWORD_MANAGER_SCHEME}://auth?${q.toString()}`;
}

export function buildDemoCallbackUrl(
  callbackBase: string,
  result: BridgeResult
): string {
  const base = callbackBase.includes("://")
    ? callbackBase
    : `${DEMO_HARNESS_SCHEME}://${callbackBase}`;
  // Prefer manual query append so we don't lose custom-scheme base
  const q = new URLSearchParams();
  q.set("nonce", result.nonce);
  q.set("ok", result.ok ? "1" : "0");
  if (result.action) q.set("action", result.action);
  if (result.counter != null && !Number.isNaN(result.counter)) {
    q.set("counter", String(result.counter));
  }
  if (result.registered != null) {
    q.set("registered", result.registered ? "1" : "0");
  }
  if (result.message) q.set("message", result.message);
  if (result.password) q.set("password", result.password);
  if (result.nextPasswordHash) q.set("nextPasswordHash", result.nextPasswordHash);

  const join = base.includes("?") ? "&" : "?";
  // If base already has path like yadademo://result, keep it
  return `${base}${join}${q.toString()}`;
}

/** Parse query string from a custom-scheme URL without relying on URL.host. */
export function parseQueryFromUrl(url: string): URLSearchParams {
  const qIndex = url.indexOf("?");
  if (qIndex < 0) return new URLSearchParams();
  // strip hash
  let qs = url.slice(qIndex + 1);
  const h = qs.indexOf("#");
  if (h >= 0) qs = qs.slice(0, h);
  return new URLSearchParams(qs);
}

export function schemeOf(url: string): string {
  const m = /^([a-zA-Z][a-zA-Z0-9+.-]*):/.exec(url);
  return m ? m[1]!.toLowerCase() : "";
}

/** Host/path action segment: yadapass://register or yadapass://auth or yadapass:///register */
export function pathActionOf(url: string): string {
  // strip scheme://
  const withoutScheme = url.replace(/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//, "");
  const beforeQuery = withoutScheme.split("?")[0] || "";
  const parts = beforeQuery.split("/").filter(Boolean);
  return (parts[0] || "").toLowerCase();
}

export function parseBridgeRequest(url: string): BridgeRequest | null {
  if (!url || typeof url !== "string") return null;
  const scheme = schemeOf(url);
  if (scheme !== PASSWORD_MANAGER_SCHEME) return null;

  const params = parseQueryFromUrl(url);
  const pathAct = pathActionOf(url);
  const actionRaw = params.get("action") || pathAct;
  if (!isAction(actionRaw)) return null;

  const site = (params.get("site") || "").trim();
  const callback = (params.get("callback") || "").trim();
  const nonce = (params.get("nonce") || "").trim();
  if (!site || !callback || !nonce) return null;

  return { action: actionRaw, site, callback, nonce };
}

export function parseBridgeResult(url: string): BridgeResult | null {
  if (!url || typeof url !== "string") return null;
  const params = parseQueryFromUrl(url);
  const nonce = params.get("nonce");
  if (!nonce) return null;
  // Require ok= so random URLs aren't treated as results
  if (!params.has("ok")) return null;

  const ok = params.get("ok") === "1";
  const counterRaw = params.get("counter");
  const actionRaw = params.get("action");
  return {
    nonce,
    ok,
    action: isAction(actionRaw) ? actionRaw : undefined,
    counter:
      counterRaw != null && counterRaw !== "" ? Number(counterRaw) : null,
    registered: params.has("registered")
      ? params.get("registered") === "1"
      : undefined,
    message: params.get("message") || undefined,
    password: params.get("password") || undefined,
    nextPasswordHash: params.get("nextPasswordHash") || undefined,
  };
}

export function newNonce(): string {
  return `n_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

/** Stable site id for the native demo harness app. */
export const DEMO_APP_SITE_ID = "yadademo://app";
