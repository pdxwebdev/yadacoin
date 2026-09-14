/** Remote auth session (webview username handoff) HTTP helpers. */

export type RemoteAuthAction = "signin" | "register" | "status" | "operator";

export interface CreateAuthSessionRequest {
  username: string;
  site: string;
  action: RemoteAuthAction;
  expectedHash?: string;
  nonce?: string;
}

export interface AuthSessionView {
  status: boolean;
  session_id?: string;
  session_status?: string;
  username?: string;
  site?: string;
  action?: string;
  nonce?: string;
  expectedHash?: string | null;
  expires_at?: number;
  poll_url?: string;
  message?: string;
  home_node?: string | null;
  delivered?: boolean;
  ok?: boolean;
  password?: string;
  nextPasswordHash?: string;
  counter?: number | null;
  registered?: boolean;
  proxied?: boolean;
  token?: string;
  operator_session?: boolean;
  hint?: string;
}

export interface PasswordAuthRequestPayload {
  session_id: string;
  action: RemoteAuthAction | string;
  site: string;
  nonce: string;
  expectedHash?: string | null;
  username?: string;
  result_token: string;
  expires_at?: number;
  home_node?: string | null;
}

export interface AuthSessionResultBody {
  result_token: string;
  ok: boolean;
  deny?: boolean;
  action?: RemoteAuthAction | string;
  nonce?: string;
  message?: string;
  password?: string;
  nextPasswordHash?: string;
  counter?: number | null;
  registered?: boolean;
}

export interface PasswordHomeClaim {
  username: string;
  node_http_base: string;
  public_key: string;
  timestamp: number;
  signature: string;
}

function base(url: string): string {
  return (url || "").replace(/\/+$/, "");
}

async function jsonFetch(
  url: string,
  init?: RequestInit
): Promise<{ ok: boolean; status: number; body: any }> {
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
  });
  const text = await res.text();
  let body: any;
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text };
  }
  return { ok: res.ok, status: res.status, body };
}

export async function createAuthSession(
  nodeUrl: string,
  req: CreateAuthSessionRequest
): Promise<AuthSessionView> {
  const { body } = await jsonFetch(base(nodeUrl) + "/password-rotation/auth-session", {
    method: "POST",
    body: JSON.stringify({
      username: req.username,
      site: req.site,
      action: req.action,
      expectedHash: req.expectedHash,
      nonce: req.nonce,
    }),
  });
  return body as AuthSessionView;
}

export async function pollAuthSession(
  nodeUrl: string,
  sessionId: string
): Promise<AuthSessionView> {
  const { body } = await jsonFetch(
    base(nodeUrl) + "/password-rotation/auth-session/" + encodeURIComponent(sessionId)
  );
  return body as AuthSessionView;
}

export async function postAuthSessionResult(
  nodeUrl: string,
  sessionId: string,
  result: AuthSessionResultBody
): Promise<AuthSessionView> {
  const { body } = await jsonFetch(
    base(nodeUrl) +
      "/password-rotation/auth-session/" +
      encodeURIComponent(sessionId) +
      "/result",
    {
      method: "POST",
      body: JSON.stringify(result),
    }
  );
  return body as AuthSessionView;
}

export async function fetchPendingAuthSessions(
  nodeUrl: string,
  q: {
    username?: string;
    username_signature?: string;
    public_key?: string;
    inception_pkh?: string;
  }
): Promise<PasswordAuthRequestPayload[]> {
  const params = new URLSearchParams();
  if (q.username) params.set("username", q.username);
  if (q.username_signature) params.set("username_signature", q.username_signature);
  if (q.public_key) params.set("public_key", q.public_key);
  if (q.inception_pkh) params.set("inception_pkh", q.inception_pkh);
  const { body } = await jsonFetch(
    base(nodeUrl) + "/password-rotation/auth-session/pending?" + params.toString()
  );
  return (body?.pending || []) as PasswordAuthRequestPayload[];
}

export async function getPasswordHome(
  nodeUrl: string,
  username: string
): Promise<{
  status: boolean;
  node_http_base?: string;
  claimed?: boolean;
  source?: string;
  is_local?: boolean;
  sp_username_signature?: string;
  sp_host?: string;
  message?: string;
  username_signature?: string;
}> {
  const { body } = await jsonFetch(
    base(nodeUrl) +
      "/password-rotation/home?username=" +
      encodeURIComponent(username)
  );
  return body;
}

/**
 * Resolve the deterministic home SP for a username via any reachable entry node.
 * Password app should connect (WS + tips) to ``node_http_base``.
 */
export async function resolvePasswordHome(
  entryNodeUrl: string,
  username: string
): Promise<{
  status: boolean;
  node_http_base?: string;
  source?: string;
  is_local?: boolean;
  message?: string;
}> {
  return getPasswordHome(entryNodeUrl, username);
}

export async function publishPasswordHome(
  nodeUrl: string,
  claim: PasswordHomeClaim
): Promise<{ status: boolean; message?: string }> {
  const { body } = await jsonFetch(base(nodeUrl) + "/password-rotation/home", {
    method: "POST",
    body: JSON.stringify(claim),
  });
  return body;
}

/** Derive ws(s)://host/websocket from an http(s) node URL. */
export function nodeUrlToWebSocketUrl(nodeUrl: string): string {
  const u = base(nodeUrl);
  if (!u) return "";
  if (u.startsWith("https://")) return "wss://" + u.slice("https://".length) + "/websocket";
  if (u.startsWith("http://")) return "ws://" + u.slice("http://".length) + "/websocket";
  if (u.startsWith("wss://") || u.startsWith("ws://")) {
    return u.endsWith("/websocket") ? u : u + "/websocket";
  }
  return "ws://" + u + "/websocket";
}

export function isTerminalSessionStatus(status: string | undefined): boolean {
  return status === "approved" || status === "denied" || status === "expired";
}

export async function waitForAuthSession(
  nodeUrl: string,
  sessionId: string,
  opts?: { intervalMs?: number; timeoutMs?: number; signal?: AbortSignal }
): Promise<AuthSessionView> {
  const interval = opts?.intervalMs ?? 1500;
  const timeout = opts?.timeoutMs ?? 180_000;
  const start = Date.now();
  while (true) {
    if (opts?.signal?.aborted) throw new Error("aborted");
    const view = await pollAuthSession(nodeUrl, sessionId);
    if (isTerminalSessionStatus(view.session_status)) return view;
    if (Date.now() - start > timeout) {
      throw new Error("auth session timed out");
    }
    await new Promise((r) => setTimeout(r, interval));
  }
}
