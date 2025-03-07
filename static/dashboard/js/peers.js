async function loadPeersData() {
    try {
        const response = await fetch('/get-monitoring');
        const monitoringData = await response.json();
        
        const ourHeight = monitoringData.node.height;
        const inboundPeers = monitoringData.peers.inbound_peers;
        const outboundPeers = monitoringData.peers.outbound_peers;

        // Inbound Peers Table
        const inboundTable = document.getElementById('inbound-peers');
        inboundTable.innerHTML = `
            <tr>
                <th>Host</th>
                <th>Port</th>
                <th>Height</th>
                <th>Synced</th>
                <th>Type</th>
                <th>Version</th>
                <th>Connected</th>
            </tr>
        `;

        inboundPeers.forEach(peer => {
            const syncedIcon = getSyncedIcon(peer.height, ourHeight);
            inboundTable.innerHTML += `
                <tr>
                    <td>${peer.host}</td>
                    <td>${peer.port}</td>
                    <td>${peer.height}</td>
                    <td>${syncedIcon}</td>
                    <td>${peer.peer_type || "Unknown"}</td>
                    <td>${peer.node_version?.join('.') || "Unknown"}</td>
                    <td>${peer.connection_duration || "N/A"}</td>
                </tr>
            `;
        });

        // Outbound Peers Table
        const outboundTable = document.getElementById('outbound-peers');
        outboundTable.innerHTML = `
            <tr>
                <th>Host</th>
                <th>Port</th>
                <th>Height</th>
                <th>Synced</th>
                <th>Type</th>
                <th>Version</th>
                <th>Connected</th>
            </tr>
        `;

        outboundPeers.forEach(peer => {
            const syncedIcon = getSyncedIcon(peer.height, ourHeight);
            outboundTable.innerHTML += `
                <tr>
                    <td>${peer.host}</td>
                    <td>${peer.port}</td>
                    <td>${peer.height}</td>
                    <td>${syncedIcon}</td>
                    <td>${peer.peer_type || "Unknown"}</td>
                    <td>${peer.node_version?.join('.') || "Unknown"}</td>
                    <td>${peer.connection_duration || "N/A"}</td>
                </tr>
            `;
        });

    } catch (error) {
        console.error("Error loading peers data:", error);
    }
}

function getSyncedIcon(peerHeight, ourHeight) {
    if (peerHeight === "Syncing" || peerHeight === undefined) {
        return "❓";
    } else if (peerHeight >= ourHeight) {
        return "🟢";
    } else {
        return "🔴";
    }
}
