import type {
  Block,
  FeeEstimate,
  MempoolPage,
  SearchPayload,
  Stats,
} from "./types";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    throw new Error(`${res.status} ${path}`);
  }
  const text = await res.text();
  if (!text) {
    return {} as T;
  }
  return JSON.parse(text) as T;
}

export function getStats() {
  return getJSON<{ stats?: Stats }>("/api-stats");
}

export function getHeight() {
  return getJSON<{ height?: number; hash?: string }>("/get-height");
}

export function getBlocks(start: number, end: number) {
  const query = new URLSearchParams({
    start_index: String(start),
    end_index: String(end),
  });
  return getJSON<Block[]>(`/get-blocks?${query}`);
}

export function search(term: string) {
  return getJSON<SearchPayload>(
    `/explorer-search?term=${encodeURIComponent(term)}`,
  );
}

export function getMempool(page: number, pageSize: number) {
  const query = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  return getJSON<MempoolPage>(`/get-mempool?${query}`);
}

export function getFeeEstimate() {
  return getJSON<FeeEstimate>("/fee-estimate");
}

export function convertPublicKey(publicKey: string) {
  return getJSON<{ address?: string; public_key?: string }>(
    `/convert-public-key-to-address?public_key=${encodeURIComponent(publicKey)}`,
  );
}
