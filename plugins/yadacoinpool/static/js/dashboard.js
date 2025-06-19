function loadDashboardData() {
    console.log("📡 Fetching /pool-info...");
    Promise.all([
        fetch("/pool-info").then(response => response.json()),
        fetch("/pool-hashrate-stats").then(response => response.json())
    ])
    .then(([poolData, hashrateData]) => {
        console.log("✅ Data received:", poolData, hashrateData);
        updateDashboard(poolData);
        updateDashboardCharts(hashrateData.stats);
    })
    .catch(error => console.error("❌ Fetch error:", error));
}

function updateDashboardCharts(stats) {
    if (!stats || stats.length === 0) {
        console.warn("⚠️ No hashrate stats available.");
        return;
    }

    drawPoolHashrateChart(stats);
    drawNetworkHashrateChart(stats);
}

function updateDashboard(data) {
    setText("pool-hash-rate", formatHashrate(data.pool.hashes_per_second));
    setText("pool-percentage", `${data.pool.pool_percentage.toFixed(2)}%`);
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

    let minerReward = parseFloat(data.network.latest_block_reward.miner_reward);
    let mnTotalReward = parseFloat(data.network.latest_block_reward.masternodes_total);
    let mnSingleReward = parseFloat(data.network.latest_block_reward.masternode_per_node);

    setText("miners-reward", `${minerReward.toFixed(6)} YDA`);
    setText("master-nodes-reward", `${mnTotalReward.toFixed(6)} YDA`);
    setText("single-mn-reward", `${mnSingleReward.toFixed(6)} YDA`);

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


function drawPoolHashrateChart(stats) {
    const times = [];
    const poolHashRates = [];
    const minersCount = [];
    const workersCount = [];

    stats.forEach(entry => {
        const timePoint = new Date(entry.time * 1000);
        const formattedTime = timePoint.getHours() + ':' + String(timePoint.getMinutes()).padStart(2, '0');

        times.push(formattedTime);
        poolHashRates.push(entry.pool_hash_rate || 0);
        minersCount.push(entry.miners || 0);
        workersCount.push(entry.workers || 0);
    });

    const ctx = document.getElementById('hashrate-chart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: times.reverse(),
            datasets: [
                {
                    label: 'Miners Count',
                    data: minersCount.reverse(),
                    type: 'line',
                    borderColor: '#007bff',
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'count'
                },
                {
                    label: 'Workers Count',
                    data: workersCount.reverse(),
                    type: 'line',
                    borderColor: '#FF7F00',
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'count'
                },
                {
                    label: 'Pool Hashrate',
                    data: poolHashRates.reverse(),
                    backgroundColor: '#333',
                    yAxisID: 'hashrate'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { display: false },
                hashrate: {
                    position: 'right',
                    beginAtZero: true,
                    ticks: { 
                        callback: value => formatHashrate(value),
                        font: { size: 10 }
                    },
                    title: { display: true, text: 'Pool Hashrate', color: '#007bff' }
                },
                count: {
                    position: 'left',
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1, callback: value => value.toFixed(0),
                        font: { size: 10 }
                    },
                    title: { display: true, text: 'Count (Miners / Workers)', color: '#007bff' }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    labels: {
                        usePointStyle: true,
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        title: function(tooltipItems) {
                            return `Time: ${tooltipItems[0].label}`
                        },
                        label: function(tooltipItem) {
                            let datasetLabel = tooltipItem.dataset.label || ''
                            let value = tooltipItem.raw
                            if (tooltipItem.datasetIndex === 2) {
                                value = formatHashrate(value)
                            }
                            return `${datasetLabel}: ${value}`
                        }
                    }
                },
            }
        }
    });
}

function drawNetworkHashrateChart(stats) {
    const times = [];
    const networkHashRates = [];
    const avgDifficulties = [];
    const difficulties = [];

    stats.forEach(entry => {
        const timePoint = new Date(entry.time * 1000);
        const formattedTime = timePoint.getHours() + ':' + String(timePoint.getMinutes()).padStart(2, '0');

        times.push(formattedTime);
        networkHashRates.push(entry.avg_network_hash_rate || 0);
        difficulties.push(entry.net_difficulty || 0);
    });

    const ctx = document.getElementById('network-hashrate-chart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: times.reverse(),
            datasets: [
                {
                    label: 'Difficulty',
                    data: difficulties.reverse(),
                    type: 'line',
                    borderColor: '#007bff',
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'difficulty'
                },
                {
                    label: 'Network Hashrate',
                    data: networkHashRates.reverse(),
                    backgroundColor: '#333',
                    yAxisID: 'hashrate'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { display: false },
                hashrate: {
                    position: 'right',
                    beginAtZero: true,
                    ticks: { 
                        callback: value => formatHashrate(value),
                        font: { size: 10 }
                    },
                    title: { display: true, text: 'Network Hashrate', color: '#007bff' }
                },
                difficulty: {
                    position: 'left',
                    beginAtZero: true,
                    ticks: {
                        callback: value => value.toFixed(2),
                        font: { size: 10 }
                    },
                    title: { display: true, text: 'Network Difficulty', color: '#007bff' }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    labels: {
                        usePointStyle: true,
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        title: function(tooltipItems) {
                            return `Time: ${tooltipItems[0].label}`
                        },
                        label: function(tooltipItem) {
                            let datasetLabel = tooltipItem.dataset.label || ''
                            let value = tooltipItem.raw

                            if (tooltipItem.datasetIndex === 1) { 
                                value = formatHashrate(value);
                            } else if (tooltipItem.datasetIndex === 0) { 
                                value = value.toFixed(2);
                            }

                            return `${datasetLabel}: ${value}`
                        }
                    }
                },
            }
        }
    });
}
