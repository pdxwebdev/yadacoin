function loadDashboardData() {
    console.log("📡 Fetching /pool-info...");
    fetch("/pool-info")
        .then(response => response.json())
        .then(data => {
            console.log("✅ Data received:", data);
            updateDashboard(data);
        })
        .catch(error => console.error("❌ Fetch error:", error));
}

function updateDashboard(data) {
    setText("pool-hash-rate", formatHashrate(data.pool.hashes_per_second));
    setText("pool-percentage", `${data.pool.pool_perecentage.toFixed(2)}%`);
    setText("pool-blocks-found", data.pool.blocks_found);
    setText("pool-avg-block-time", data.pool.avg_block_time);

    if (data.pool.blocks.length > 0) {
        setText("pool-last-block", data.pool.blocks[0].index);
        setText("pool-last-block-time", formatDate(data.pool.blocks[0].time));
    }

    setText("network-hash-rate", formatHashrate(data.network.avg_hashes_per_second));
    setText("network-difficulty", data.network.difficulty.toFixed(3));
    setText("network-height", data.network.height);
    setText("network-last-block", formatDate(data.network.last_block));

    let blockReward = parseFloat(data.network.reward);
    setText("miners-reward", `${(blockReward * 0.9).toFixed(2)} YDA`);
    setText("master-nodes-reward", `${(blockReward * 0.1).toFixed(2)} YDA`);

    setText("pool-worker-count", data.pool.worker_count);
    setText("pool-miner-count", data.pool.miner_count);
    setText("pool-fee", `${data.pool.pool_fee * 100}%`);
    setText("pool-min-payout", `${data.pool.min_payout} YDA`);
    setText("pool-payout-scheme", data.pool.payout_scheme);

    let payoutText = `After every ${data.pool.payout_frequency} BLOCK`;
    if (data.pool.payout_frequency > 1) {
        payoutText += "S";
    }
    payoutText += " found by pool";
    setText("pool-payout-frequency", payoutText);
}

function setText(id, text) {
    let element = document.getElementById(id);
    if (element) {
        element.innerText = text;
    }
}

function formatHashrate(hashesPerSecond) {
    if (hashesPerSecond < 1000) return `${hashesPerSecond.toFixed(2)} H/sec`;
    if (hashesPerSecond < 1e6) return `${(hashesPerSecond / 1e3).toFixed(2)} KH/sec`;
    return `${(hashesPerSecond / 1e6).toFixed(2)} MH/sec`;
}

function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours} hour${hours !== 1 ? 's' : ''} ${minutes} minute${minutes !== 1 ? 's' : ''}`;
}

function formatDate(timestamp) {
    const date = new Date(timestamp * 1000);
    return `${date.toLocaleDateString()}, ${date.toLocaleTimeString()}`;
}
