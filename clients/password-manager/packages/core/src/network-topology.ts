/**
 * Network topology / online node discovery for password-home routing.
 * Prefers fast light snapshots; caches aggressively because full crawls are slow.
 */

function base(url: string): string {
  return (url || "").replace(/\/+$/, "");
}

export interface TopologyNode {
  id?: string;
  host?: string;
  port?: number | string;
  http_protocol?: string;
  peer_type?: string;
  username?: string;
  username_signature?: string;
  status?: string;
  height?: number | null;
  source?: string;
}

export interface NetworkTopologySnapshot {
  nodes: TopologyNode[];
  generated_at?: number;
  tested_at?: number | string;
  light?: boolean;
  source?: string;
  fetched_at: number;
  from: string;
}

export interface TopologyCacheStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
}

const CACHE_KEY = "yadaNetworkTopologyV1";
/** Reuse snapshot this long before background refresh is forced. */
export const TOPOLOGY_CACHE_TTL_MS = 6 * 60 * 60 * 1000;
/** Serve stale cache up to this age if all fetchers fail. */
export const TOPOLOGY_STALE_MAX_MS = 7 * 24 * 60 * 60 * 1000;

/** Bootstrap hosts used to pull topology (yadacoin.com first). */
export const TOPOLOGY_ENTRY_NODES = [
  "https://yadacoin.com",
  "https://yadacoin.io",
  "https://centeridentity.com",
];

function nodeHttpBase(n: TopologyNode): string {
  if (n.id && /^https?:\/\//i.test(n.id)) {
    try {
      const u = new URL(n.id);
      if (
        (u.protocol === "https:" && (u.port === "" || u.port === "443")) ||
        (u.protocol === "http:" && (u.port === "" || u.port === "80"))
      ) {
        return `${u.protocol}//${u.hostname}`;
      }
      return u.origin;
    } catch {
      /* fall through */
    }
  }
  const host = (n.host || "").trim();
  if (!host) return "";
  const port = n.port != null ? String(n.port) : "";
  let proto = (n.http_protocol || "").toLowerCase();
  if (!proto) proto = port === "443" || port === "8443" ? "https" : "http";
  if (!proto.includes("://")) proto = proto.replace(/:$/, "");
  if (
    (proto === "https" && (!port || port === "443")) ||
    (proto === "http" && (!port || port === "80"))
  ) {
    return `${proto}://${host}`;
  }
  return `${proto}://${host}:${port || (proto === "https" ? "443" : "80")}`;
}

function isPoolHost(url: string): boolean {
  try {
    const h = new URL(url).hostname.toLowerCase();
    return h.includes("pool.yadacoin") || h.startsWith("pool.") || h.endsWith(".pool");
  } catch {
    return false;
  }
}

/** Prefer online SPs, then other masternode tiers. */
export function topologyHttpBases(
  snap: NetworkTopologySnapshot | null | undefined
): string[] {
  if (!snap?.nodes?.length) return [];
  const scored: { score: number; base: string }[] = [];
  const seen = new Set<string>();
  for (const n of snap.nodes) {
    const b = nodeHttpBase(n);
    if (!b || isPoolHost(b) || seen.has(b.toLowerCase())) continue;
    const st = (n.status || "").toLowerCase();
    if (st === "unreachable" || st === "offline" || st === "dead") continue;
    const pt = (n.peer_type || "").toLowerCase();
    let score = 5;
    if (pt === "service_provider") score = 0;
    else if (pt === "seed_gateway") score = 1;
    else if (pt === "seed") score = 2;
    else if (pt === "pool") continue;
    if (st === "online" || st === "ok") score -= 0.5;
    seen.add(b.toLowerCase());
    scored.push({ score, base: b });
  }
  scored.sort((a, b) => a.score - b.score);
  return scored.map((x) => x.base);
}

async function fetchJson(url: string, timeoutMs: number): Promise<any> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "GET",
      credentials: "omit",
      signal: ctrl.signal,
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(t);
  }
}

function snapshotFromPayload(body: any, from: string): NetworkTopologySnapshot | null {
  if (!body || typeof body !== "object") return null;
  let nodes: TopologyNode[] = [];
  if (Array.isArray(body.nodes)) nodes = body.nodes;
  else if (Array.isArray(body.successful_nodes)) {
    nodes = body.successful_nodes.map((n: any) => ({
      host: n.http_host || n.host,
      port: n.http_port || n.port,
      http_protocol: n.http_protocol,
      peer_type: n.peer_type,
      username: n.identity?.username || n.username,
      username_signature: n.identity?.username_signature,
      status: "online",
      source: "tested_nodes",
    }));
  } else return null;
  if (!nodes.length) return null;
  return {
    nodes,
    generated_at: typeof body.generated_at === "number" ? body.generated_at : undefined,
    tested_at: body.tested_at ?? body.timestamp,
    light: Boolean(body.light) || body.source === "tested_nodes",
    source: body.source || (body.light ? "light" : "topology"),
    fetched_at: Date.now(),
    from,
  };
}

/**
 * Pull a light topology snapshot from the first reachable entry host.
 * Tries get-tested-nodes then network-topology?format=json&light=1.
 */
export async function fetchNetworkTopologyLight(
  entryNodes: string[] = TOPOLOGY_ENTRY_NODES,
  opts?: { timeoutMs?: number }
): Promise<NetworkTopologySnapshot | null> {
  const timeout = opts?.timeoutMs ?? 12_000;
  for (const raw of entryNodes) {
    const entry = base(raw);
    if (!entry) continue;
    const paths = [
      "/get-tested-nodes",
      "/network-topology?format=json&light=1",
    ];
    for (const path of paths) {
      try {
        const body = await fetchJson(entry + path, timeout);
        const snap = snapshotFromPayload(body, entry + path);
        if (snap) return snap;
      } catch {
        /* next */
      }
    }
  }
  return null;
}

export async function loadCachedTopology(
  store: TopologyCacheStore
): Promise<NetworkTopologySnapshot | null> {
  try {
    const raw = await store.get(CACHE_KEY);
    if (!raw) return null;
    const snap = JSON.parse(raw) as NetworkTopologySnapshot;
    if (!snap?.nodes?.length || !snap.fetched_at) return null;
    return snap;
  } catch {
    return null;
  }
}

export async function saveCachedTopology(
  store: TopologyCacheStore,
  snap: NetworkTopologySnapshot
): Promise<void> {
  await store.set(CACHE_KEY, JSON.stringify(snap));
}

/**
 * Cached topology: return fresh cache, else fetch light snapshot, else stale cache.
 */
export async function getNetworkTopologyCached(
  store: TopologyCacheStore,
  opts?: {
    entryNodes?: string[];
    ttlMs?: number;
    staleMaxMs?: number;
    forceRefresh?: boolean;
  }
): Promise<NetworkTopologySnapshot | null> {
  const ttl = opts?.ttlMs ?? TOPOLOGY_CACHE_TTL_MS;
  const staleMax = opts?.staleMaxMs ?? TOPOLOGY_STALE_MAX_MS;
  const cached = await loadCachedTopology(store);
  const age = cached ? Date.now() - cached.fetched_at : Infinity;

  if (!opts?.forceRefresh && cached && age < ttl) {
    return cached;
  }

  const fresh = await fetchNetworkTopologyLight(opts?.entryNodes);
  if (fresh) {
    await saveCachedTopology(store, fresh);
    return fresh;
  }

  if (cached && age < staleMax) return cached;
  return null;
}
