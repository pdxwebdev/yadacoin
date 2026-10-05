import { useEffect, useRef } from "react";
import type { Block, Txn } from "../types";
import { age, feeTone, txnsOf, txnTone } from "../format";

type Props = {
  blocks: Block[];
  selected: number | null;
  fresh: number[];
  mempool: Txn[];
  mempoolTotal: number;
  feeStatus?: string;
  loading: boolean;
  loadingEarlier: boolean;
  canEarlier: boolean;
  mempoolActive: boolean;
  onSelect: (block: Block) => void;
  onEarlier: () => void;
  onMempool: () => void;
};

function Pixels({ colors, columns = 8 }: { colors: string[]; columns?: number }) {
  if (colors.length === 0) {
    return <div className="pixels empty" />;
  }
  return (
    <div
      className="pixels"
      style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}
    >
      {colors.map((color, index) => (
        <span key={`${color}-${index}`} style={{ background: color }} />
      ))}
    </div>
  );
}

export function BlockRail({
  blocks,
  selected,
  fresh,
  mempool,
  mempoolTotal,
  feeStatus,
  loading,
  loadingEarlier,
  canEarlier,
  mempoolActive,
  onSelect,
  onEarlier,
  onMempool,
}: Props) {
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const anchor = useRef({ index: -1, width: 0 });
  const tip = blocks.length ? blocks[blocks.length - 1].index : null;
  const first = blocks[0]?.index ?? -1;

  useEffect(() => {
    const el = scroller.current;
    if (!el) {
      return;
    }
    if (anchor.current.index >= 0 && first >= 0 && first < anchor.current.index) {
      el.scrollLeft += el.scrollWidth - anchor.current.width;
      stick.current = false;
    } else if (stick.current) {
      el.scrollLeft = el.scrollWidth;
    }
    anchor.current = { index: first, width: el.scrollWidth };
  }, [first, tip, blocks.length]);

  function onScroll() {
    const el = scroller.current;
    if (!el) {
      return;
    }
    stick.current = el.scrollWidth - el.scrollLeft - el.clientWidth < 64;
  }

  const maxFee = mempool.reduce((max, txn) => Math.max(max, txn.fee || 0), 0);
  const pendingColors = mempool
    .slice(0, 64)
    .map((txn) => feeTone(txn.fee || 0, maxFee));
  const slabs = Math.min(3, Math.max(1, Math.ceil(mempoolTotal / 48) || 1));

  return (
    <section className="lane" aria-label="Block lane">
      <div className="lane-head">
        <div>
          <h2>Block lane</h2>
          <p>Confirmed chain on the track. Unconfirmed work sits in the dock.</p>
        </div>
        <div className="legend">
          <span><i className="swatch" style={{ background: "#58a6ff" }} /> txn</span>
          <span><i className="swatch" style={{ background: "#3fb950" }} /> coinbase</span>
          <span><i className="swatch" style={{ background: "#d2a8ff" }} /> identity</span>
          <span><i className="swatch" style={{ background: "#ffa657" }} /> file</span>
          <span><i className="swatch" style={{ background: "#ff2bd6" }} /> high fee</span>
        </div>
      </div>
      <div className="lane-body">
        <div className="lane-scroll" ref={scroller} onScroll={onScroll}>
          <button
            type="button"
            className="earlier"
            onClick={() => {
              stick.current = false;
              onEarlier();
            }}
            disabled={!canEarlier || loadingEarlier}
          >
            {loadingEarlier ? "Loading" : "Earlier"}
          </button>
          {loading && blocks.length === 0
            ? Array.from({ length: 8 }, (_, index) => (
                <div className="tile ghost" key={index} />
              ))
            : null}
          {blocks.map((block, index) => {
            const txns = txnsOf(block);
            const colors = txns.slice(0, 48).map((txn) => txnTone(txn, block));
            const bulk = Math.min(txns.length, 40) / 40;
            const active = selected === block.index;
            const isTip = index === blocks.length - 1;
            return (
              <button
                type="button"
                key={block.hash}
                className={`tile${active ? " active" : ""}${isTip ? " tip" : ""}${fresh.includes(block.index) ? " fresh" : ""}`}
                style={{ ["--bulk" as string]: String(bulk) }}
                onClick={() => onSelect(block)}
              >
                <span className="tile-height">#{block.index.toLocaleString()}</span>
                <Pixels colors={colors} />
                <span className="tile-meta">
                  {txns.length} tx
                  <em>{age(block.time)}</em>
                </span>
              </button>
            );
          })}
        </div>
        <aside className={`dock${mempoolActive ? " active" : ""}`}>
          <button type="button" className="dock-hit" onClick={onMempool}>
            <span className="dock-kicker">Mempool</span>
            <strong>{mempoolTotal.toLocaleString()}</strong>
            <span className="dock-sub">
              {feeStatus === "congested" ? "congested" : feeStatus ? "clear" : "—"}
            </span>
            <div className="dock-slabs">
              {Array.from({ length: slabs }, (_, slab) => (
                <div className="pending" key={slab}>
                  <Pixels
                    colors={pendingColors.slice(slab * 21, slab * 21 + 21)}
                    columns={7}
                  />
                </div>
              ))}
            </div>
            <span className="dock-note">
              {mempoolTotal > mempool.length
                ? `${(mempoolTotal - mempool.length).toLocaleString()} more queued`
                : "projected next work"}
            </span>
          </button>
        </aside>
      </div>
    </section>
  );
}
