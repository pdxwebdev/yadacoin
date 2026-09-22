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
import { requestOriginAccess, toOriginPattern } from "./permissions.js";

const homeCache = new Map<string, { base: string; at: number }>();
const HOME_CACHE_MS = 60 * 1000;

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

async function hasAccess(baseUrl: string): Promise<boolean> {
  if (typeof chrome === "undefined" || !chrome.permissions?.contains) return true;
  const origin = toOriginPattern(baseUrl);
  if (!origin) return true;
  try {
    return await chrome.permissions.contains({ origins: [origin] });
  } catch {
    return true;
  }
}

export async function probeNodeAlive(
  baseUrl: string,
  timeoutMs = 3500
): Promise<boolean> {
  const base = normalizeNodeBaseUrl(baseUrl);
  if (!base || isLoopback(base)) return false;
  const paths = ["/get-status", "/password-rotation/theme.json"];
  for (const path of paths) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(base + path, {
        method: "GET",
        credentials: "omit",
        signal: ctrl.signal,
        headers: { Accept: "application/json" },
      });
      clearTimeout(timer);
      if (res.status > 0 && res.status < 500) return true;
    } catch {
      clearTimeout(timer);
    }
  }
  return false;
}

/**
 * Entry hosts for home discovery: page origin, topology SPs, then well-known.
 */
export async function entryCandidates(pageOrigin?: string): Promise<string[]> {
  const out: string[] = [];
  const add = (u: string) => {
    const n = normalizeNodeBaseUrl(u);
    if (!n || isLoopback(n) || out.includes(n)) return;
    out.push(n);
  };

  add(pageOrigin || "");

  try {
    const topo = await getNetworkTopologyCached(chromeTopologyStore, {
      entryNodes: [
        ...TOPOLOGY_ENTRY_NODES,
        normalizeNodeBaseUrl(pageOrigin || ""),
      ].filter(Boolean),
    });
    for (const b of topologyHttpBases(topo)) add(b);
  } catch {
    /* topology optional */
  }

  for (const e of TOPOLOGY_ENTRY_NODES) add(e);
  return out;
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
    const home = normalizeNodeBaseUrl(raw || "");
    if (!home || isLoopback(home) || dead.has(home.toLowerCase())) return null;
    if (!(await ensureAccess(home, wantPerm))) {
      dead.add(home.toLowerCase());
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
    if (hit && Date.now() - hit.at < HOME_CACHE_MS) {
      const ok = await accept(hit.base);
      if (ok) return ok;
      homeCache.delete(username.toLowerCase());
    }
  }

  const entries = await entryCandidates(opts.pageOrigin);
  const cachedHome = normalizeNodeBaseUrl(opts.cachedHome || "");

  for (const entry of entries) {
    try {
      if (!(await ensureAccess(entry, wantPerm))) continue;
      if (!(await probeNodeAlive(entry))) {
        dead.add(entry.toLowerCase());
        continue;
      }

      if (!username) {
        return entry;
      }

      const route = await resolvePasswordHome(entry, username);
      if (!route.status) {
        const asEntry = await accept(entry);
        if (asEntry) return asEntry;
        continue;
      }

      const primary = await accept(route.node_http_base);
      if (primary) return primary;

      for (const t of route.tried || []) {
        dead.add(normalizeNodeBaseUrl(t).toLowerCase());
      }

      const det = await accept(route.deterministic_node_http_base);
      if (det) return det;

      const asEntry = await accept(entry);
      if (asEntry) return asEntry;
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
