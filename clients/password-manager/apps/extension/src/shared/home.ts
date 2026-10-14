/**
 * Password home SP resolution — no user-facing Node URL.
 * Uses cached network topology (yadacoin.com light snapshot) + live probes.
 */
import {
  getNetworkTopologyCached,
  normalizeNodeBaseUrl,
  resolvePasswordHome,
  topologyHttpBases,
  TOPOLOGY_ENTRY_NODES,
  type TopologyCacheStore,
} from "@yadacoin/password-core";
import { requestOriginAccess } from "./permissions.js";

const homeCache = new Map<string, { base: string; at: number }>();
const HOME_CACHE_MS = 5 * 60 * 1000;
/** Do not walk the full topology. One entry node resolves the home SP. */
const TOPOLOGY_FAILOVER_CAP = 4;

const chromeTopologyStore: TopologyCacheStore = {
  async get(key) {
    if (typeof chrome === "undefined" || !chrome.storage?.local) return null;
    const data = await chrome.storage.local.get(key);
    const v = data[key];
    return typeof v === "string" ? v : null;
  },
  async set(key, value) {
    if (typeof chrome === "undefined" || !chrome.storage?.local) return;
    await chrome.storage.local.set({ [key]: value });
  },
};

function isLoopback(url: string): boolean {
  try {
    const h = new URL(url).hostname.toLowerCase();
    return h === "localhost" || h === "127.0.0.1" || h === "[::1]" || h === "::1";
  } catch {
    return false;
  }
}

async function hasAccess(_baseUrl: string): Promise<boolean> {
  return true;
}

export async function probeNodeAlive(
  baseUrl: string,
  timeoutMs = 2000
): Promise<boolean> {
  const base = normalizeNodeBaseUrl(baseUrl);
  if (!base || isLoopback(base)) return false;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(base + "/get-status", {
      method: "GET",
      credentials: "omit",
      signal: ctrl.signal,
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return false;
    const data = await res.json().catch(() => null);
    if (data && (data.peer_type || data.version || data.network)) return true;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
  return false;
}

function pushUnique(out: string[], raw: string): void {
  const n = normalizeNodeBaseUrl(raw);
  if (!n || isLoopback(n) || out.includes(n)) return;
  out.push(n);
}

/**
 * Entry hosts only. The home SP is resolved by that node — do not walk
 * every topology peer from the browser.
 */
export async function entryCandidates(pageOrigin?: string): Promise<string[]> {
  const out: string[] = [];
  pushUnique(out, pageOrigin || "");
  for (const e of TOPOLOGY_ENTRY_NODES) pushUnique(out, e);
  return out;
}

async function topologyFailover(pageOrigin?: string): Promise<string[]> {
  try {
    const topo = await getNetworkTopologyCached(chromeTopologyStore, {
      entryNodes: [
        ...TOPOLOGY_ENTRY_NODES,
        normalizeNodeBaseUrl(pageOrigin || ""),
      ].filter(Boolean),
    });
    return topologyHttpBases(topo).slice(0, TOPOLOGY_FAILOVER_CAP);
  } catch {
    return [];
  }
}

async function ensureAccess(
  base: string,
  requestPermission: boolean
): Promise<boolean> {
  if (requestPermission) {
    try {
      return await requestOriginAccess(base);
    } catch {
      return false;
    }
  }
  return hasAccess(base);
}

/**
 * Resolve a live password-home API base for the vault username.
 */
export async function resolveHomeApiBase(opts: {
  username: string;
  pageOrigin?: string;
  cachedHome?: string;
  requestPermission?: boolean;
}): Promise<string> {
  const username = (opts.username || "").trim();
  const wantPerm = opts.requestPermission !== false;
  const dead = new Set<string>();

  const accept = async (raw: string | undefined): Promise<string | null> => {
    let home = normalizeNodeBaseUrl(raw || "");
    if (home.startsWith("http://")) {
      try {
        const host = new URL(home).hostname;
        const secure = normalizeNodeBaseUrl(`https://${host}`);
        if (secure && (await probeNodeAlive(secure))) home = secure;
      } catch {
        /* keep http */
      }
    }
    if (!home || isLoopback(home) || dead.has(home.toLowerCase())) return null;
    if (!(await ensureAccess(home, wantPerm))) {
      return null;
    }
    if (!(await probeNodeAlive(home))) {
      dead.add(home.toLowerCase());
      return null;
    }
    if (username) {
      homeCache.set(username.toLowerCase(), { base: home, at: Date.now() });
    }
    return home;
  };

  if (username) {
    const hit = homeCache.get(username.toLowerCase());
    const page = normalizeNodeBaseUrl(opts.pageOrigin || "");
    const cachedIsPage =
      !!hit && !!page && hit.base.toLowerCase() === page.toLowerCase();
    if (hit && !cachedIsPage && Date.now() - hit.at < HOME_CACHE_MS) {
      const ok = await accept(hit.base);
      if (ok) return ok;
      homeCache.delete(username.toLowerCase());
    } else if (cachedIsPage) {
      homeCache.delete(username.toLowerCase());
    }
  }

  const entries = await entryCandidates(opts.pageOrigin);
  const cachedHome = normalizeNodeBaseUrl(opts.cachedHome || "");

  const useEntry = async (entry: string): Promise<string | null> => {
    if (!username) return entry;
    const route = await resolvePasswordHome(entry, username);
    if (!route.status) return accept(entry);
    const primary = await accept(route.node_http_base);
    if (primary) return primary;
    const resolved = normalizeNodeBaseUrl(route.node_http_base || "");
    if (resolved && !isLoopback(resolved) && !(await hasAccess(resolved))) {
      return resolved;
    }
    for (const t of route.tried || []) {
      dead.add(normalizeNodeBaseUrl(t).toLowerCase());
    }
    return (await accept(route.deterministic_node_http_base)) || null;
  };

  const permitted: string[] = [];
  const needsPerm: string[] = [];
  for (const entry of entries) {
    if (await hasAccess(entry)) permitted.push(entry);
    else needsPerm.push(entry);
  }
  const livePermitted = (
    await Promise.all(
      permitted.map(async (entry) => ((await probeNodeAlive(entry)) ? entry : ""))
    )
  ).filter(Boolean);
  for (const entry of livePermitted) {
    try {
      const home = await useEntry(entry);
      if (home) return home;
    } catch {
      /* next */
    }
  }
  if (wantPerm) {
    for (const entry of needsPerm) {
      try {
        if (!(await ensureAccess(entry, true))) continue;
        if (!(await probeNodeAlive(entry))) continue;
        const home = await useEntry(entry);
        if (home) return home;
      } catch {
        /* next */
      }
    }
  }

  for (const entry of await topologyFailover(opts.pageOrigin)) {
    try {
      if (!(await hasAccess(entry))) continue;
      if (!(await probeNodeAlive(entry))) continue;
      const home = await useEntry(entry);
      if (home) return home;
    } catch {
      /* next */
    }
  }

  const stale = await accept(cachedHome);
  if (stale) return stale;

  for (const entry of entries) {
    const ok = await accept(entry);
    if (ok) return ok;
  }

  throw new Error(
    "no live password home SP — refresh network topology (yadacoin.com) and retry"
  );
}

export function clearHomeCache(username?: string): void {
  if (username) homeCache.delete(username.trim().toLowerCase());
  else homeCache.clear();
}

/** Force-refresh topology cache (e.g. after user opens popup). */
export async function refreshTopologyCache(pageOrigin?: string): Promise<number> {
  const snap = await getNetworkTopologyCached(chromeTopologyStore, {
    entryNodes: [
      ...TOPOLOGY_ENTRY_NODES,
      normalizeNodeBaseUrl(pageOrigin || ""),
    ].filter(Boolean),
    forceRefresh: true,
  });
  return snap?.nodes?.length ?? 0;
}
