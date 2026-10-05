import { useEffect, useState, type ReactNode } from "react";
import { convertPublicKey } from "../api";
import {
  asList,
  difficultyFromTarget,
  formatBytes,
  formatCoins,
  formatTime,
  isBlock,
  isCoinbase,
  minerOf,
  outputTotal,
  resultLabel,
  shortId,
  txnMatches,
  txnsOf,
} from "../format";
import type { Block, FeeEstimate, MempoolPage, SearchPayload, Txn } from "../types";

type Props = {
  mode: "chain" | "search" | "mempool";
  block: Block | null;
  term: string;
  search: SearchPayload | null;
  searching: boolean;
  searchError: string;
  mempool: MempoolPage;
  fee: FeeEstimate | null;
  onSearch: (term: string) => void;
  onOpenBlock: (block: Block) => void;
  onMempoolPage: (page: number) => void;
};

function Term({
  value,
  onSearch,
  full = false,
}: {
  value?: string | null;
  onSearch: (term: string) => void;
  full?: boolean;
}) {
  if (!value) {
    return null;
  }
  return (
    <button type="button" className="term" title={value} onClick={() => onSearch(value)}>
      {full || value.length < 42 ? value : shortId(value, 14, 10)}
    </button>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  if (children === null || children === undefined || children === "" || children === false) {
    return null;
  }
  return (
    <div className="field">
      <span>{label}</span>
      <div>{children}</div>
    </div>
  );
}

function SafeHref({ href }: { href?: string }) {
  if (!href) {
    return null;
  }
  if (!/^https?:\/\//i.test(href)) {
    return <span>{href}</span>;
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {href}
    </a>
  );
}

function RawData({ value }: { value: unknown }) {
  return (
    <details className="raw-toggle">
      <summary>Show raw data</summary>
      <pre className="raw">{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}

function TxnBody({
  txn,
  block,
  onSearch,
  failed = false,
}: {
  txn: Txn;
  block?: Block;
  onSearch: (term: string) => void;
  failed?: boolean;
}) {
  const coinbase = isCoinbase(txn, block);
  const identity = txn.relationship?.identity;
  const file = txn.relationship?.file;
  const keywords = Array.isArray(file?.keywords)
    ? file.keywords.join(", ")
    : file?.keywords;
  return (
    <article className="txn">
      <header>
        <strong>{coinbase ? "Coinbase" : failed ? "Failed transaction" : "Transaction"}</strong>
        {txn.hash ? <Term value={txn.hash} onSearch={onSearch} /> : null}
      </header>
      {failed ? (
        <>
          <Field label="Exception">{txn.reason}</Field>
          {txn.error ? <pre className="trace">{txn.error}</pre> : null}
        </>
      ) : null}
      <div className="meta">
        <Field label="Time">{formatTime(txn.time)}</Field>
        <Field label="Version">{txn.version}</Field>
        <Field label="Fee">{txn.fee !== undefined ? formatCoins(txn.fee) : ""}</Field>
        <Field label="Masternode fee">
          {txn.masternode_fee !== undefined ? formatCoins(txn.masternode_fee) : ""}
        </Field>
        <Field label="Private">{txn.private === undefined ? "" : String(txn.private)}</Field>
        <Field label="Never expire">
          {txn.never_expire === undefined ? "" : String(txn.never_expire)}
        </Field>
      </div>
      <Field label="Public key">
        <Term value={txn.public_key} onSearch={onSearch} />
      </Field>
      <Field label="Signature">
        <Term value={txn.id} onSearch={onSearch} />
      </Field>
      <Field label="RID">
        <Term value={txn.rid} onSearch={onSearch} />
      </Field>
      <Field label="DH public key">
        <Term value={txn.dh_public_key} onSearch={onSearch} />
      </Field>
      <Field label="Relationship hash">
        <Term value={txn.relationship_hash} onSearch={onSearch} />
      </Field>
      <Field label="Requester RID">
        <Term value={txn.requester_rid} onSearch={onSearch} />
      </Field>
      <Field label="Requested RID">
        <Term value={txn.requested_rid} onSearch={onSearch} />
      </Field>
      <Field label="Public key hash">
        <Term value={txn.public_key_hash} onSearch={onSearch} />
      </Field>
      <Field label="Prev public key hash">
        <Term value={txn.prev_public_key_hash} onSearch={onSearch} />
      </Field>
      <Field label="Prerotated key hash">
        <Term value={txn.prerotated_key_hash} onSearch={onSearch} />
      </Field>
      <Field label="Twice prerotated key hash">
        <Term value={txn.twice_prerotated_key_hash} onSearch={onSearch} />
      </Field>
      <Field label="Miner signature">
        <Term value={txn.miner_signature} onSearch={onSearch} />
      </Field>
      {identity ? (
        <section className="subcard">
          <h3>Identity</h3>
          <Field label="Username">
            <Term value={identity.username} onSearch={onSearch} full />
          </Field>
          <Field label="Username signature">
            <Term value={identity.username_signature} onSearch={onSearch} />
          </Field>
          <Field label="Type">{identity.identity_type}</Field>
        </section>
      ) : null}
      {file ? (
        <section className="subcard">
          <h3>File announcement</h3>
          <Field label="Title">{file.title}</Field>
          <Field label="Description">{file.description}</Field>
          <Field label="File id">
            <Term value={file.file_id} onSearch={onSearch} />
          </Field>
          <Field label="Filename">
            <Term value={file.filename} onSearch={onSearch} full />
          </Field>
          <Field label="Keywords">{keywords}</Field>
          <Field label="MIME">{file.mime_type}</Field>
          <Field label="Backend">{file.backend}</Field>
          <Field label="Share URL">
            <SafeHref href={file.share_url} />
          </Field>
        </section>
      ) : null}
      <div className="io">
        <section>
          <h3>Inputs</h3>
          {!txn.inputs || txn.inputs.length === 0 ? (
            <p className="muted">No inputs</p>
          ) : (
            <ul>
              {txn.inputs.map((input, index) => (
                <li key={`${input.id}-${index}`}>
                  <Term value={input.id} onSearch={onSearch} />
                </li>
              ))}
            </ul>
          )}
        </section>
        <section>
          <h3>Outputs · {formatCoins(outputTotal(txn))} YDA</h3>
          {!txn.outputs || txn.outputs.length === 0 ? (
            <p className="muted">No outputs</p>
          ) : (
            <ul>
              {txn.outputs.map((output, index) => (
                <li key={`${output.to}-${index}`}>
                  <span className="coins">{formatCoins(output.value)} YDA</span>
                  <Term value={output.to} onSearch={onSearch} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      {txn.relationship ? (
        <details className="fold">
          <summary>Relationship payload</summary>
          <pre>{JSON.stringify(txn.relationship, null, 2)}</pre>
        </details>
      ) : null}
      <RawData value={txn} />
    </article>
  );
}

function BlockBody({
  block,
  term,
  onSearch,
}: {
  block: Block;
  term: string;
  onSearch: (term: string) => void;
}) {
  const [address, setAddress] = useState("");
  const [open, setOpen] = useState<string>("");
  const txns = txnsOf(block);
  const miner = minerOf(block);

  useEffect(() => {
    let stop = false;
    setAddress("");
    if (!block.public_key) {
      return;
    }
    convertPublicKey(block.public_key)
      .then((data) => {
        if (!stop && data.address) {
          setAddress(data.address);
        }
      })
      .catch(() => undefined);
    return () => {
      stop = true;
    };
  }, [block.public_key, block.hash]);

  return (
    <div className="block-pane">
      <div className="meta">
        <Field label="Height">{block.index.toLocaleString()}</Field>
        <Field label="Time">{formatTime(block.time)}</Field>
        <Field label="Transactions">{txns.length.toLocaleString()}</Field>
        <Field label="Payload">{formatBytes(block)}</Field>
        <Field label="Difficulty">{difficultyFromTarget(block.target)}</Field>
        <Field label="Version">{block.version}</Field>
        <Field label="Nonce">{block.nonce}</Field>
        <Field label="Special min">{block.special_min ? "yes" : "no"}</Field>
      </div>
      <Field label="Hash">
        <Term value={block.hash} onSearch={onSearch} full />
      </Field>
      <Field label="Previous">
        <Term value={block.prevHash} onSearch={onSearch} full />
      </Field>
      <Field label="Merkle root">
        <Term value={block.merkleRoot} onSearch={onSearch} full />
      </Field>
      <Field label="Block id">
        <Term value={block.id} onSearch={onSearch} />
      </Field>
      <Field label="Miner pubkey">
        <Term value={block.public_key} onSearch={onSearch} />
      </Field>
      <Field label="Miner address">
        <Term value={address || miner} onSearch={onSearch} full />
      </Field>
      <Field label="Target">{block.target}</Field>
      <h3 className="list-title">Transactions</h3>
      <ul className="txn-list">
        {txns.map((txn, index) => {
          const key = txn.hash || txn.id || String(index);
          const hit = txnMatches(txn, term);
          const total = outputTotal(txn);
          return (
            <li key={key} className={hit ? "hit" : ""}>
              <button type="button" onClick={() => setOpen(open === key ? "" : key)}>
                <span className={`pill${isCoinbase(txn, block) ? " coin" : ""}`}>
                  {isCoinbase(txn, block) ? "coinbase" : "txn"}
                </span>
                <span>{shortId(txn.hash || txn.id, 10, 8)}</span>
                <em>
                  {txn.outputs?.length
                    ? `${formatCoins(total)} YDA`
                    : "0 out"}
                </em>
              </button>
              {open === key || hit ? (
                <TxnBody txn={txn} block={block} onSearch={onSearch} />
              ) : null}
            </li>
          );
        })}
      </ul>
      <RawData value={block} />
    </div>
  );
}

export function Detail({
  mode,
  block,
  term,
  search,
  searching,
  searchError,
  mempool,
  fee,
  onSearch,
  onOpenBlock,
  onMempoolPage,
}: Props) {
  if (mode === "mempool") {
    const pages = Math.max(1, Math.ceil(mempool.total / Math.max(mempool.page_size, 1)));
    return (
      <section className="panel">
        <header className="panel-head">
          <h2>Mempool</h2>
          <p>
            {mempool.total.toLocaleString()} pending
            {fee?.status ? ` · ${fee.status.replaceAll("_", " ")}` : ""}
            {fee?.recommended_fee !== undefined ? ` · suggested ${formatCoins(fee.recommended_fee)}` : ""}
            {fee?.fee_estimate?.median_fee !== undefined
              ? ` · median ${formatCoins(fee.fee_estimate.median_fee)}`
              : ""}
          </p>
        </header>
        {mempool.transactions.length === 0 ? (
          <p className="muted">No pending transactions.</p>
        ) : (
          mempool.transactions.map((txn, index) => (
            <TxnBody
              key={txn.hash || txn.id || index}
              txn={txn}
              onSearch={onSearch}
            />
          ))
        )}
        <div className="pager">
          <button
            type="button"
            className="btn ghost"
            disabled={mempool.page <= 1}
            onClick={() => onMempoolPage(mempool.page - 1)}
          >
            Prev
          </button>
          <span>
            {mempool.page} / {pages}
          </span>
          <button
            type="button"
            className="btn ghost"
            disabled={mempool.page >= pages}
            onClick={() => onMempoolPage(mempool.page + 1)}
          >
            Next
          </button>
        </div>
      </section>
    );
  }

  if (mode === "search") {
    const items = asList(search?.result);
    return (
      <section className="panel">
        <header className="panel-head">
          <h2>Search</h2>
          <p>
            {searching
              ? "Searching…"
              : search?.resultType
                ? resultLabel(search.resultType)
                : searchError || "No match"}
          </p>
        </header>
        {search?.balance ? (
          <div className="balance">
            Balance <strong>{search.balance}</strong> YDA
          </div>
        ) : null}
        {!searching && items.length === 0 ? <p className="muted">No results.</p> : null}
        {items.map((item, index) => {
          if (isBlock(item)) {
            return (
              <article className="hit-card" key={item.hash || index}>
                <button type="button" onClick={() => onOpenBlock(item)}>
                  <span className="pill">block</span>
                  <strong>#{item.index.toLocaleString()}</strong>
                  <span>{shortId(item.hash, 12, 8)}</span>
                  <em>{txnsOf(item).length} tx</em>
                </button>
                <BlockBody block={item} term={term} onSearch={onSearch} />
              </article>
            );
          }
          const txn = item as Txn;
          return (
            <TxnBody
              key={txn.hash || txn.id || index}
              txn={txn}
              onSearch={onSearch}
              failed={Boolean(search?.resultType?.startsWith("failed"))}
            />
          );
        })}
      </section>
    );
  }

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>{block ? `Block ${block.index.toLocaleString()}` : "Chain"}</h2>
        <p>{block ? shortId(block.hash, 18, 12) : "Select a block on the lane."}</p>
      </header>
      {block ? (
        <BlockBody block={block} term={term} onSearch={onSearch} />
      ) : (
        <p className="muted">Waiting for the tip.</p>
      )}
    </section>
  );
}
