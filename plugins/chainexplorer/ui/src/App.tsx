import { FormEvent, useEffect, useRef, useState } from "react";
import {
  getBlocks,
  getFeeEstimate,
  getHeight,
  getMempool,
  getStats,
  search,
} from "./api";
import { BlockRail } from "./components/BlockRail";
import { Detail } from "./components/Detail";
import { formatNumber, formatRate, isBlock } from "./format";
import type { Block, FeeEstimate, MempoolPage, Panel, SearchPayload, Stats } from "./types";

const WINDOW = 36;
const PAGE = 50;
const EMPTY_MEMPOOL: MempoolPage = {
  transactions: [],
  total: 0,
  page: 1,
  page_size: PAGE,
};

function readTerm() {
  return new URLSearchParams(window.location.search).get("term") || "";
}

function writeTerm(term: string) {
  const url = new URL(window.location.href);
  if (term) {
    url.searchParams.set("term", term);
  } else {
    url.searchParams.delete("term");
  }
  window.history.pushState({}, "", url);
}

export function App() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [selected, setSelected] = useState<Block | null>(null);
  const [fresh, setFresh] = useState<number[]>([]);
  const [mempool, setMempool] = useState<MempoolPage>(EMPTY_MEMPOOL);
  const [fee, setFee] = useState<FeeEstimate | null>(null);
  const [panel, setPanel] = useState<Panel>("chain");
  const [term, setTerm] = useState(readTerm);
  const [draft, setDraft] = useState(readTerm);
  const [searching, setSearching] = useState(false);
  const [payload, setPayload] = useState<SearchPayload | null>(null);
  const [searchError, setSearchError] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingEarlier, setLoadingEarlier] = useState(false);
  const [error, setError] = useState("");
  const [live, setLive] = useState(false);
  const tipRef = useRef(0);
  const [oldest, setOldest] = useState(0);
  const [height, setHeight] = useState<number | null>(null);

  async function loadWindow(height: number) {
    const start = Math.max(0, height - WINDOW + 1);
    const list = await getBlocks(start, height);
    const rows = Array.isArray(list) ? list : [];
    setBlocks(rows);
    const first = rows[0]?.index ?? start;
    setOldest(first);
    tipRef.current = rows[rows.length - 1]?.index ?? height;
    setHeight(tipRef.current);
    setSelected((current) => {
      if (current && rows.some((block) => block.index === current.index)) {
        return current;
      }
      return rows[rows.length - 1] || null;
    });
  }

  async function runSearch(next: string, push = true) {
    const value = next.trim();
    setTerm(value);
    setDraft(value);
    if (push) {
      writeTerm(value);
    }
    if (!value) {
      setPayload(null);
      setPanel("chain");
      return;
    }
    setPanel("search");
    setSearching(true);
    setSearchError("");
    try {
      const data = await search(value);
      setPayload(data);
      const first = Array.isArray(data.result) ? data.result[0] : data.result;
      if (isBlock(first)) {
        setSelected(first);
      }
    } catch (err) {
      setPayload(null);
      setSearchError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  async function boot() {
    setLoading(true);
    setError("");
    try {
      const [statsRes, heightRes, memRes, feeRes] = await Promise.all([
        getStats().catch(() => ({ stats: undefined })),
        getHeight(),
        getMempool(1, PAGE).catch(() => EMPTY_MEMPOOL),
        getFeeEstimate().catch(() => null),
      ]);
      setStats(statsRes.stats || null);
      setMempool({ ...EMPTY_MEMPOOL, ...memRes, transactions: memRes.transactions || [] });
      setFee(feeRes);
      const nextHeight = heightRes.height ?? statsRes.stats?.height ?? 0;
      setHeight(nextHeight);
      await loadWindow(nextHeight);
      setLive(true);
      if (readTerm()) {
        await runSearch(readTerm(), false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chain unavailable");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void boot();
    const onPop = () => {
      const next = readTerm();
      setDraft(next);
      void runSearch(next, false);
    };
    window.addEventListener("popstate", onPop);
    const timer = window.setInterval(() => {
      void refresh();
    }, 15000);
    return () => {
      window.removeEventListener("popstate", onPop);
      window.clearInterval(timer);
    };
  }, []);

  async function refresh() {
    try {
      const [heightRes, statsRes, memRes] = await Promise.all([
        getHeight(),
        getStats().catch(() => ({ stats: undefined })),
        getMempool(1, PAGE).catch(() => null),
      ]);
      if (statsRes.stats) {
        setStats(statsRes.stats);
      }
      if (memRes) {
        setMempool((current) =>
          current.page === 1
            ? { ...EMPTY_MEMPOOL, ...memRes, transactions: memRes.transactions || [] }
            : current,
        );
      }
      const nextHeight = heightRes.height ?? tipRef.current;
      setHeight(nextHeight);
      if (nextHeight > tipRef.current) {
        const incoming = await getBlocks(tipRef.current + 1, nextHeight);
        const rows = Array.isArray(incoming) ? incoming : [];
        if (rows.length) {
          setFresh(rows.map((block) => block.index));
          setBlocks((prev) => {
            const seen = new Set(prev.map((block) => block.index));
            return [...prev, ...rows.filter((block) => !seen.has(block.index))];
          });
          tipRef.current = rows[rows.length - 1].index;
          window.setTimeout(() => setFresh([]), 1600);
        }
      }
      setLive(true);
    } catch {
      setLive(false);
    }
  }

  async function earlier() {
    if (loadingEarlier || oldest <= 0) {
      return;
    }
    setLoadingEarlier(true);
    try {
      const end = oldest - 1;
      const start = Math.max(0, end - 99);
      const incoming = await getBlocks(start, end);
      const rows = Array.isArray(incoming) ? incoming : [];
      if (rows.length) {
        setOldest(rows[0].index);
        setBlocks((prev) => {
          const seen = new Set(prev.map((block) => block.index));
          return [...rows.filter((block) => !seen.has(block.index)), ...prev];
        });
      } else {
        setOldest(0);
      }
    } finally {
      setLoadingEarlier(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void runSearch(draft);
  }

  function selectBlock(block: Block) {
    setSelected(block);
    setPanel("chain");
    setTerm(String(block.index));
    setDraft(String(block.index));
    writeTerm(String(block.index));
  }

  async function openSearched(block: Block) {
    selectBlock(block);
    if (!blocks.some((row) => row.index === block.index)) {
      try {
        await loadWindow(block.index);
        setSelected(block);
      } catch {
        setSelected(block);
      }
    }
  }

  return (
    <>
      <header className="top">
        <a className="brand" href="/">
          <img src="/yadacoinstatic/yadalogo200.png" alt="" />
          <span>
            <strong>YadaCoin</strong>
            <em>Explorer</em>
          </span>
        </a>
        <nav>
          <a href="/">Dashboard</a>
          <a href="/holders">Holders</a>
          <span className={live ? "live on" : "live"}>
            {live ? "live" : "offline"}
          </span>
        </nav>
      </header>
      <main>
        {error ? (
          <div className="banner">
            {error}
            <button type="button" onClick={() => void boot()}>
              Retry
            </button>
          </div>
        ) : null}
        <section className="stats">
          <div>
            <span>Height</span>
            <strong>{formatNumber(height ?? stats?.height)}</strong>
          </div>
          <div>
            <span>Circulating</span>
            <strong>{formatNumber(stats?.circulating)}</strong>
          </div>
          <div>
            <span>Max supply</span>
            <strong>21,000,000</strong>
          </div>
          <div>
            <span>Hash rate</span>
            <strong>{formatRate(stats?.network_hash_rate)}</strong>
          </div>
          <div>
            <span>Difficulty</span>
            <strong>{formatNumber(stats?.difficulty)}</strong>
          </div>
          <div>
            <span>Algorithm</span>
            <strong>RandomX</strong>
          </div>
        </section>
        <form className="search" onSubmit={onSubmit}>
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Username, wallet address, txn id, block height, file title…"
            aria-label="Search the chain"
          />
          <button className="btn" type="submit">
            Search
          </button>
        </form>
        <BlockRail
          blocks={blocks}
          selected={panel === "chain" ? selected?.index ?? null : null}
          fresh={fresh}
          mempool={mempool.transactions}
          mempoolTotal={mempool.total}
          feeStatus={fee?.status}
          loading={loading}
          loadingEarlier={loadingEarlier}
          canEarlier={oldest > 0}
          mempoolActive={panel === "mempool"}
          onSelect={selectBlock}
          onEarlier={() => void earlier()}
          onMempool={() => setPanel("mempool")}
        />
        <nav className="tabs">
          <button
            type="button"
            className={panel === "chain" ? "active" : ""}
            onClick={() => setPanel("chain")}
          >
            Block
          </button>
          <button
            type="button"
            className={panel === "search" ? "active" : ""}
            onClick={() => setPanel("search")}
          >
            Search
          </button>
          <button
            type="button"
            className={panel === "mempool" ? "active" : ""}
            onClick={() => setPanel("mempool")}
          >
            Mempool
          </button>
        </nav>
        <Detail
          mode={panel}
          block={selected}
          term={term}
          search={payload}
          searching={searching}
          searchError={searchError}
          mempool={mempool}
          fee={fee}
          onSearch={(value) => void runSearch(value)}
          onOpenBlock={(block) => void openSearched(block)}
          onMempoolPage={(page) => {
            void getMempool(page, PAGE).then((data) =>
              setMempool({ ...EMPTY_MEMPOOL, ...data, transactions: data.transactions || [] }),
            );
          }}
        />
      </main>
    </>
  );
}
