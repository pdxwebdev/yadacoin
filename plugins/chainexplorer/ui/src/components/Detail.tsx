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
import type {
  AnnouncementHit,
  Block,
  FeeEstimate,
  IdentityProfile,
  MempoolPage,
  SearchPayload,
  Txn,
} from "../types";

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

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function textOf(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).join(", ");
  }
  return String(value);
}

function kindLabel(kind: string, relationship?: Txn["relationship"]): string {
  if (kind === "branch" && textOf(asRecord(relationship?.branch)?.type) === "livestream") {
    return "Livestream";
  }
  const labels: Record<string, string> = {
    identity: "Identity",
    node: "Node",
    agent: "Agent",
    file: "File",
    credential: "Credential",
    branch: "Branch",
    rotation: "Rotation",
    recovery: "Recovery",
    recovers: "Recovery proof",
    content_takedown: "Takedown",
  };
  return labels[kind] || kind.replaceAll("_", " ");
}

const KIND_ORDER = [
  "identity",
  "node",
  "agent",
  "file",
  "credential",
  "branch",
  "rotation",
  "recovery",
  "recovers",
  "content_takedown",
];

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
      <RelationshipFacts txn={txn} onSearch={onSearch} />
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

function RelationshipFacts({
  txn,
  onSearch,
}: {
  txn: Txn;
  onSearch: (term: string) => void;
}) {
  const rel = txn.relationship || {};
  const node = asRecord(rel.node);
  const agent = asRecord(rel.agent);
  const credential = asRecord(rel.credential);
  const branch = asRecord(rel.branch);
  const rotation = asRecord(rel.rotation);
  const recovery = rel.recovery;
  const recovers = asRecord(rel.recovers);
  const takedown = asRecord(rel.content_takedown);
  const nodeIdentity = asRecord(node?.identity);
  const agentIdentity = asRecord(agent?.identity);
  if (!node && !agent && !credential && !branch && !rotation && recovery == null && !recovers && !takedown) {
    return null;
  }
  return (
    <>
      {node ? (
        <section className="subcard">
          <h3>Node</h3>
          <Field label="Host">{textOf(node.host)}</Field>
          <Field label="Port">{textOf(node.port)}</Field>
          <Field label="HTTP">{textOf(node.http_host)}</Field>
          <Field label="HTTP port">{textOf(node.http_port)}</Field>
          <Field label="Identity announcement">
            <Term value={textOf(node.identity_announcement)} onSearch={onSearch} />
          </Field>
          <Field label="Username">
            <Term value={textOf(nodeIdentity?.username)} onSearch={onSearch} full />
          </Field>
        </section>
      ) : null}
      {agent ? (
        <section className="subcard">
          <h3>Agent</h3>
          <Field label="Label">{textOf(agent.label)}</Field>
          <Field label="Type">{textOf(agent.agent_type)}</Field>
          <Field label="Description">{textOf(agent.description)}</Field>
          <Field label="Capabilities">{textOf(agent.capabilities)}</Field>
          <Field label="Endpoint">
            <SafeHref href={textOf(agent.endpoint_url)} />
          </Field>
          <Field label="Username">
            <Term value={textOf(agentIdentity?.username)} onSearch={onSearch} full />
          </Field>
        </section>
      ) : null}
      {credential ? (
        <section className="subcard">
          <h3>Credential</h3>
          <Field label="Claim">{textOf(credential.claim)}</Field>
          <Field label="Expires">{textOf(credential.expires)}</Field>
          <Field label="Subject">
            <Term value={textOf(credential.subject_username_signature)} onSearch={onSearch} />
          </Field>
          <Field label="Issuer">
            <Term value={textOf(credential.issuer_username_signature)} onSearch={onSearch} />
          </Field>
        </section>
      ) : null}
      {branch ? (
        <section className="subcard">
          <h3>{textOf(branch.type) === "livestream" ? "Livestream" : "Branch"}</h3>
          <Field label="Type">{textOf(branch.type) || "peer"}</Field>
          <Field label="Identity announcement">
            <Term value={textOf(branch.identity_announcement)} onSearch={onSearch} />
          </Field>
          <Field label="Prerotated key hash">
            <Term value={textOf(branch.prerotated_key_hash)} onSearch={onSearch} />
          </Field>
        </section>
      ) : null}
      {rotation ? (
        <section className="subcard">
          <h3>Rotation</h3>
          <Field label="Curve">{textOf(rotation.curve)}</Field>
          <Field label="Key hash">
            <Term value={textOf(rotation.key_hash)} onSearch={onSearch} />
          </Field>
          <Field label="DTLS">{textOf(rotation.dtls_fingerprint)}</Field>
        </section>
      ) : null}
      {recovery != null ? (
        <section className="subcard">
          <h3>Recovery</h3>
          <Field label="Witness">
            {typeof recovery === "string" ? (
              <Term value={recovery} onSearch={onSearch} />
            ) : (
              <Term value={textOf(asRecord(recovery)?.witness_hash)} onSearch={onSearch} />
            )}
          </Field>
        </section>
      ) : null}
      {recovers ? (
        <section className="subcard">
          <h3>Recovery proof</h3>
          <Field label="Commitment">
            <Term value={textOf(recovers.commitment)} onSearch={onSearch} />
          </Field>
        </section>
      ) : null}
      {takedown ? (
        <section className="subcard">
          <h3>Takedown</h3>
          <Field label="Reason">{textOf(takedown.reason_code)}</Field>
          <Field label="Transaction">
            <Term value={textOf(takedown.transaction_id)} onSearch={onSearch} />
          </Field>
        </section>
      ) : null}
    </>
  );
}

function UsernameDossier({
  search,
  onSearch,
}: {
  search: SearchPayload;
  onSearch: (term: string) => void;
}) {
  const identity: IdentityProfile = search.identity || {};
  const announcements = search.announcements || [];
  const counts = search.counts || {};
  const grouped = KIND_ORDER.map((kind) => ({
    kind,
    items: announcements.filter((hit) => hit.kind === kind),
  })).filter((group) => group.items.length > 0);
  const extra = announcements.filter((hit) => !KIND_ORDER.includes(hit.kind));
  if (extra.length) {
    grouped.push({ kind: "other", items: extra });
  }
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>{identity.username || search.username || "Username"}</h2>
        <p>
          {announcements.length.toLocaleString()} announcement
          {announcements.length === 1 ? "" : "s"}
          {identity.identity_type ? ` · ${identity.identity_type}` : ""}
          {identity.source ? ` · ${identity.source}` : ""}
        </p>
      </header>
      {search.balance ? (
        <div className="balance">
          Balance <strong>{search.balance}</strong> YDA
        </div>
      ) : null}
      <div className="count-row">
        {Object.entries(counts).map(([kind, count]) => (
          <span className="pill" key={kind}>
            {kindLabel(kind)} {count}
          </span>
        ))}
      </div>
      <div className="meta">
        <Field label="Username signature">
          <Term value={identity.username_signature} onSearch={onSearch} />
        </Field>
        <Field label="Public key">
          <Term value={identity.public_key} onSearch={onSearch} />
        </Field>
        <Field label="Address">
          <Term value={identity.addresses?.[0]} onSearch={onSearch} full />
        </Field>
        <Field label="Identity txn">
          <Term value={identity.transaction_id} onSearch={onSearch} />
        </Field>
        <Field label="Block">
          {identity.block_hash ? (
            <Term value={identity.block_hash} onSearch={onSearch} />
          ) : identity.block_index != null ? (
            String(identity.block_index)
          ) : (
            ""
          )}
        </Field>
      </div>
      {(identity.public_keys || []).length > 1 ? (
        <Field label="Known keys">
          <ul className="key-list">
            {identity.public_keys?.map((key) => (
              <li key={key}>
                <Term value={key} onSearch={onSearch} />
              </li>
            ))}
          </ul>
        </Field>
      ) : null}
      {grouped.map((group) => (
        <section key={group.kind}>
          <h3 className="list-title">{kindLabel(group.kind, group.items[0]?.txn?.relationship)}</h3>
          {group.items.map((hit, index) => (
            <AnnouncementCard key={`${hit.kind}-${hit.txn?.id || hit.txn?.hash || index}`} hit={hit} onSearch={onSearch} />
          ))}
        </section>
      ))}
    </section>
  );
}

function AnnouncementCard({
  hit,
  onSearch,
}: {
  hit: AnnouncementHit;
  onSearch: (term: string) => void;
}) {
  if (!hit.txn) {
    return null;
  }
  return (
    <article className="hit-card">
      <div className="card-kicker">
        <span className="pill">{kindLabel(hit.kind, hit.txn.relationship)}</span>
        {hit.source ? <span className="pill ghost">{hit.source}</span> : null}
        {hit.block_index != null ? <span>#{hit.block_index.toLocaleString()}</span> : null}
        {hit.block_hash ? <Term value={hit.block_hash} onSearch={onSearch} /> : null}
      </div>
      <TxnBody
        txn={hit.txn}
        onSearch={onSearch}
        failed={hit.source === "failed"}
      />
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

  if (mode === "search" && search?.resultType === "username_profile" && !searching) {
    return <UsernameDossier search={search} onSearch={onSearch} />;
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
