function loadDashboardData() {
    fetch("/pool-info", { cache: "no-store" })
        .then(response => response.json())
        .then(updateDashboard)
        .catch(() => setLive(false));
    loadMiningBlock();
    loadLeaderboard();
}

function updateDashboard(data) {
    setLive(true);
    setText("pool-hash-rate", formatHashrate(data.pool.hashes_per_second));
    const share = Number(data.pool.pool_perecentage);
    setText("pool-percentage", Number.isFinite(share) ? `${share.toFixed(2)}% of network` : "");
    setText("pool-blocks-found", data.pool.blocks_found);
    const avg = data.pool.avg_block_time;
    setText("pool-avg-block-time", Array.isArray(avg) ? avg.join(" ") : avg);

    const blocks = data.pool.blocks || [];
    if (blocks.length > 0) {
        setText("pool-last-block", blocks[0].index);
        setText("pool-last-block-time", formatDate(blocks[0].time || blocks[0].updated_at));
    } else {
        setText("pool-last-block", "—");
        setText("pool-last-block-time", "");
    }

    setText("network-hash-rate", formatHashrate(data.network.avg_hashes_per_second));
    setText("network-difficulty", Number(data.network.difficulty).toFixed(3));
    setText("network-height", data.network.height);
    setText("network-last-block", formatDate(data.network.last_block));

    const blockReward = parseFloat(data.network.reward);
    setText("miners-reward", `${(blockReward * 0.9).toFixed(2)} YDA`);
    setText("master-nodes-reward", `Masternodes ${(blockReward * 0.1).toFixed(2)} YDA`);

    setText("pool-counts", `${data.pool.miner_count} / ${data.pool.worker_count}`);
    setText("pool-fee", `${(data.pool.pool_fee * 100).toFixed(2)}%`);
    setText("pool-min-payout", `${data.pool.min_payout} YDA`);
    setText("pool-payout-scheme", data.pool.payout_scheme);

    let payoutText = `After every ${data.pool.payout_frequency} block`;
    if (data.pool.payout_frequency > 1) payoutText += "s";
    payoutText += " found by pool";
    setText("pool-payout-frequency", payoutText);
}

function loadMiningBlock() {
    fetch("/current-mining-block", { cache: "no-store" })
        .then(response => response.json())
        .then(data => {
            if (!data || data.error || data.height === undefined) {
                setText("mining-height", "No template");
                setText("mining-status", data && data.error ? data.error : "Pool is not serving a block");
                setText("mining-version", "—");
                setText("mining-txns", "—");
                setText("mining-prev", "—");
                setText("mining-special", "—");
                setText("mining-target", "—");
                setText("mining-header", "—");
                renderMiningTxns([]);
                return;
            }
            const txns = Array.isArray(data.transactions) ? data.transactions : [];
            setText("mining-height", `#${data.height}`);
            setText("mining-status", txns.length === 1 ? "1 transaction in template" : `${txns.length} transactions in template`);
            setText("mining-version", data.version ?? "—");
            setText("mining-txns", txns.length);
            setText("mining-prev", data.previous_time ? formatDate(data.previous_time) : "—");
            setText("mining-special", data.special_min ? "yes" : "no");
            setText("mining-target", data.target || "—");
            setText("mining-header", data.header || "—");
            renderMiningTxns(txns);
        })
        .catch(() => {
            setText("mining-height", "Unavailable");
            setText("mining-status", "Could not load /current-mining-block");
            renderMiningTxns([]);
        });
}

let miningTxnKey = "";

function renderMiningTxns(transactions) {
    const list = document.getElementById("mining-txns-list");
    if (!list) return;
    const key = JSON.stringify(transactions || []);
    if (key === miningTxnKey && list.childElementCount) return;
    miningTxnKey = key;
    const open = new Set([...list.querySelectorAll(":scope > details.txn[open]")].map(el => el.dataset.id));
    const rawOpen = new Set([...list.querySelectorAll("details.raw-json[open]")].map(el => el.dataset.id));
    const count = document.getElementById("mining-txn-count");
    if (count) count.textContent = transactions.length ? String(transactions.length) : "";
    if (!transactions.length) {
        list.innerHTML = `<p class="muted">No transactions in the template</p>`;
        return;
    }
    list.innerHTML = transactions.map((txn, index) => miningTxnCard(txn, index, open, rawOpen)).join("");
}

function miningTxnCard(txn, index, open, rawOpen) {
    const id = String(txn.id || txn.hash || index);
    const inputs = Array.isArray(txn.inputs) ? txn.inputs : [];
    const outputs = Array.isArray(txn.outputs) ? txn.outputs : [];
    const coinbase = inputs.length === 0;
    const total = outputs.reduce((sum, output) => sum + (Number(output.value) || 0), 0);
    const expanded = open.has(id);
    const raw = rawOpen.has(id);
    return `<details class="txn" data-id="${esc(id)}"${expanded ? " open" : ""}>
        <summary>
            <span class="pill${coinbase ? " coin" : ""}">${coinbase ? "Coinbase" : "Transaction"}</span>
            <span class="mono">${esc(shortId(txn.hash || txn.id || ""))}</span>
            <em>${formatCoins(total)} YDA</em>
        </summary>
        <div class="txn-body">
            ${fieldLink("Id", txn.id)}
            ${fieldLink("Hash", txn.hash)}
            ${fieldText("Version", txn.version)}
            ${fieldLink("Public key", txn.public_key)}
            ${fieldLink("Public key hash", txn.public_key_hash)}
            ${fieldLink("Prev public key hash", txn.prev_public_key_hash)}
            ${fieldLink("Prerotated key hash", txn.prerotated_key_hash)}
            ${fieldLink("Twice prerotated key hash", txn.twice_prerotated_key_hash)}
            <div class="io">
                <section>
                    <h3>Inputs</h3>
                    ${inputs.length ? `<ul>${inputs.map(input => `<li>${explorerLink(input.id)}</li>`).join("")}</ul>` : `<p class="muted">No inputs</p>`}
                </section>
                <section>
                    <h3>Outputs · ${formatCoins(total)} YDA</h3>
                    ${outputs.length ? `<ul>${outputs.map(output => `<li><span class="coins">${formatCoins(output.value)} YDA</span>${explorerLink(output.to)}</li>`).join("")}</ul>` : `<p class="muted">No outputs</p>`}
                </section>
            </div>
            ${relationshipBlock(txn.relationship)}
            <details class="fold raw-json" data-id="${esc(id)}"${raw ? " open" : ""}>
                <summary>Raw JSON</summary>
                <pre>${esc(JSON.stringify(txn, null, 2))}</pre>
            </details>
        </div>
    </details>`;
}

function fieldText(label, value) {
    if (value === undefined || value === null || value === "") return "";
    return `<div class="field"><span>${esc(label)}</span><div>${esc(value)}</div></div>`;
}

function fieldLink(label, value) {
    if (!value) return "";
    return `<div class="field"><span>${esc(label)}</span><div>${explorerLink(value)}</div></div>`;
}

function explorerLink(value) {
    if (!value) return "";
    return `<a class="mono" href="/explorer?term=${encodeURIComponent(value)}">${esc(value)}</a>`;
}

function relationshipBlock(relationship) {
    if (!relationship || typeof relationship !== "object") return "";
    const filled = Object.entries(relationship).filter(([, value]) => value);
    if (!filled.length) return "";
    const identity = relationship.identity || {};
    const file = relationship.file || {};
    const bits = [
        fieldText("Username", identity.username || relationship.their_username || relationship.my_username),
        fieldLink("Address", relationship.their_address),
        fieldText("Topic", relationship.topic),
        fieldText("File", file.title || file.filename),
    ].join("");
    return `<section class="subcard">
        <h3>Relationship</h3>
        ${bits}
        <details class="fold">
            <summary>Payload</summary>
            <pre>${esc(JSON.stringify(relationship, null, 2))}</pre>
        </details>
    </section>`;
}

function esc(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function shortId(value) {
    const text = String(value || "");
    if (text.length <= 22) return text || "—";
    return `${text.slice(0, 10)}…${text.slice(-8)}`;
}

function formatCoins(value) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return "—";
    return amount.toLocaleString(undefined, { maximumFractionDigits: 8 });
}

function loadLeaderboard() {
    const body = document.getElementById("leaderboard-body");
    if (!body) return;
    fetch("/pool-leaderboard", { cache: "no-store" })
        .then(response => response.json())
        .then(data => {
            const miners = data.miners || [];
            if (!miners.length) {
                body.innerHTML = `<tr><td colspan="6" class="muted">No shares in the last 20 minutes</td></tr>`;
                return;
            }
            body.innerHTML = miners.map((miner, index) => {
                const rank = index + 1;
                const ago = Math.max(0, Math.floor(Date.now() / 1000 - miner.last_share));
                return `<tr class="rank-${rank}">
                    <td>${rank}</td>
                    <td class="mono"><a href="/explorer?term=${encodeURIComponent(miner.address)}">${miner.address}</a></td>
                    <td class="right">${formatHashrate(miner.hashrate)}</td>
                    <td class="right">${miner.shares}</td>
                    <td class="right">${miner.workers}</td>
                    <td>${ago}s ago</td>
                </tr>`;
            }).join("");
        })
        .catch(() => {
            body.innerHTML = `<tr><td colspan="6" class="bad">Could not load leaderboard</td></tr>`;
        });
}

function setLive(on) {
    const el = document.getElementById("live");
    if (!el) return;
    el.textContent = on ? "live" : "offline";
    el.classList.toggle("on", on);
}

function setText(id, text) {
    const element = document.getElementById(id);
    if (element) element.textContent = text;
}

function formatHashrate(hashesPerSecond) {
    const value = Number(hashesPerSecond) || 0;
    const units = ["H/s", "KH/s", "MH/s", "GH/s", "TH/s", "PH/s"];
    let amount = value;
    let index = 0;
    while (amount >= 1000 && index < units.length - 1) {
        amount /= 1000;
        index++;
    }
    const digits = amount >= 100 || index === 0 ? 0 : 2;
    return `${amount.toLocaleString(undefined, { maximumFractionDigits: digits })} ${units[index]}`;
}

function formatDate(timestamp) {
    const date = new Date(Number(timestamp) * 1000);
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleString();
}
