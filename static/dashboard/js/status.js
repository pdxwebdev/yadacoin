async function loadStatusData() {
    const response = await fetch('/get-status');
    const nodeStatus = await response.json();

    // Node Info
    const nodeInfoTable = document.getElementById('node-info');
    nodeInfoTable.innerHTML = `
        <tr><th>Version</th><td>${nodeStatus.version}</td></tr>
        <tr><th>Protocol</th><td>${nodeStatus.protocol_version}</td></tr>
        <tr><th>Network</th><td>${nodeStatus.network}</td></tr>
        <tr><th>Uptime</th><td>${nodeStatus.uptime}</td></tr>
        <tr><th>Block Height</th><td>${nodeStatus.height}</td></tr>
        <tr><th>Synced</th><td>${nodeStatus.synced ? "✅ Yes" : "❌ No"}</td></tr>
    `;

    // Performance Metrics
    const performanceTable = document.getElementById('performance-info');
    performanceTable.innerHTML = `
        <tr><th>Queue</th><th>Items in Queue</th><th>Avg Processing Time</th><th>Processed Items</th></tr>
    `;
    
    for (const [key, value] of Object.entries(nodeStatus.processing_queues)) {
        performanceTable.innerHTML += `
            <tr>
                <td>${key}</td>
                <td>${value.queue_item_count}</td>
                <td>${value.average_processing_time} sec</td>
                <td>${value.num_items_processed}</td>
            </tr>
        `;
    }

    // Health Status
    const healthTable = document.getElementById('health-status');
    healthTable.innerHTML = `<tr><th>Service</th><th>Status</th><th>Time Until Fail</th><th>Ignored</th></tr>`;
    for (const [key, value] of Object.entries(nodeStatus.health)) {
        if (typeof value === 'object') {
            const cleanKeys = Object.keys(value).reduce((acc, k) => {
                acc[k.trim()] = value[k];
                return acc;
            }, {});

            const status = cleanKeys["status"];
            const ignored = cleanKeys["ignore"];
            const displayStatus = ignored ? '⚠️ Ignored' : (status ? "✅ OK" : "❌ Failed");

            healthTable.innerHTML += `
                <tr>
                    <td>${key}</td>
                    <td class="${status ? 'status-ok' : (ignored ? 'status-ignored' : 'status-fail')}">${displayStatus}</td>
                    <td>${cleanKeys["time_until_fail"]} sec</td>
                    <td>${ignored ? 'Yes' : 'No'}</td>
                </tr>
            `;
        }
    }

    // Peer Connections
    document.getElementById('peer-connections').innerHTML = `
        <tr><th>Inbound Peers</th><td>${nodeStatus.inbound_peers}</td></tr>
        <tr><th>Outbound Peers</th><td>${nodeStatus.outbound_peers}</td></tr>
        <tr><th>Ignored Peers</th><td>${nodeStatus.outbound_ignore}</td></tr>
    `;

    // Message Activity
    document.getElementById('message-activity').innerHTML = `
        <tr><th>Messages Sent</th><td>${nodeStatus.message_sender.nodeServer.num_messages}</td></tr>
        <tr><th>Messages Received</th><td>${nodeStatus.message_sender.nodeClient.num_messages}</td></tr>
    `;

    // Transaction Tracker
    const transactionTable = document.getElementById('transaction-tracker');
    transactionTable.innerHTML = `<tr><th>Host</th><th>Transactions</th></tr>`;
    const topTxHosts = Object.entries(nodeStatus.transaction_tracker.nodeClient.by_host)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);
    topTxHosts.forEach(([host, txCount]) => {
        transactionTable.innerHTML += `<tr><td>${host}</td><td>${txCount}</td></tr>`;
    });

    // Disconnect Tracker
    const disconnectTable = document.getElementById('disconnect-tracker');
    disconnectTable.innerHTML = `<tr><th>Host</th><th>Disconnects</th></tr>`;
    const topDiscHosts = Object.entries(nodeStatus.disconnect_tracker.nodeClient.by_host)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);
    topDiscHosts.forEach(([host, discCount]) => {
        disconnectTable.innerHTML += `<tr><td>${host}</td><td>${discCount}</td></tr>`;
    });
}
