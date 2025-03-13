function loadMinerStatsData() {
    const addressInput = document.getElementById("miner-address");
    let address = addressInput.value.trim();

    if (!address) {
        address = localStorage.getItem("minerAddress");
    }

    if (!address) {
        alert("Please enter a valid address!");
        return;
    }

    document.getElementById("miner-address-text").innerText = address;
    document.getElementById("miner-address-display").style.display = "block";

    localStorage.setItem("minerAddress", address);

    console.log(`🔍 Fetching stats and payouts for ${address}...`);
    minerStats_fetchStats(address);
    minerStats_fetchPayouts(address);
}

async function minerStats_fetchStats(address) {
    try {
        const response = await fetch(`/miner-stats?address=${address}`);
        const data = await response.json();

        console.log("🔍 Miner stats received:", data);

        if (!data.workers || !Array.isArray(data.workers)) {
            document.getElementById("miner-stats-table-body").innerHTML =
                `<tr><td colspan="4" class="text-center text-danger">No worker stats found</td></tr>`;
            return;
        }

        minerStats_updateStatsTable(data.workers, data.total_hashrate);
    } catch (error) {
        console.error("❌ Error fetching miner stats:", error);
        document.getElementById("miner-stats-table-body").innerHTML =
            `<tr><td colspan="4" class="text-center text-danger">Error loading miner stats</td></tr>`;
    }
}

async function minerStats_fetchPayouts(address) {
    try {
        const response = await fetch(`/miner-payouts?address=${address}`);
        const data = await response.json();

        if (data.error) {
            document.getElementById("miner-payouts-table-body").innerHTML =
                `<tr><td colspan="6" class="text-center text-danger">${data.error}</td></tr>`;
            return;
        }

        minerPayoutsData = data.payouts;
        updateMinerPayoutPagination();
        minerStats_updatePayoutsTable(minerPayoutsData);
    } catch (error) {
        console.error("❌ Error fetching payouts:", error);
        document.getElementById("miner-payouts-table-body").innerHTML =
            `<tr><td colspan="6" class="text-center text-danger">Error loading payout data</td></tr>`;
    }
}

function minerStats_updateStatsTable(stats, totalHashrate) {
    const tableBody = document.getElementById("miner-stats-table-body");
    tableBody.innerHTML = "";

    if (!stats.length) {
        tableBody.innerHTML = `<tr><td colspan="4" class="text-center">No miner stats found</td></tr>`;
        return;
    }

    stats.forEach(stat => {
        const row = document.createElement("tr");
        const now = Math.floor(Date.now() / 1000);
        const timeAgo = now - stat.last_share_time;

        row.innerHTML = `
            <td>${stat.worker_name}</td>
            <td>${formatHashrate(stat.worker_hashrate)}</td>
            <td>${timeAgo} sec ago</td>
            <td>${stat.status === "Online" ? "✅ Online" : "⚠️ Offline"}</td>
        `;
        tableBody.appendChild(row);
    });

    const totalRow = document.createElement("tr");
    totalRow.innerHTML = `
        <td><b>Total Hashrate</b></td>
        <td><b>${formatHashrate(totalHashrate)}</b></td>
        <td colspan="2"></td>
    `;
    tableBody.appendChild(totalRow);
}


function formatHashrate(hashrate) {
    const units = ["H/s", "KH/s", "MH/s", "GH/s", "TH/s", "PH/s"];
    let index = 0;

    while (hashrate >= 1000 && index < units.length - 1) {
        hashrate /= 1000;
        index++;
    }

    return `${hashrate.toFixed(2)} ${units[index]}`;
}

if (typeof minerPayoutsData === "undefined") {
    var minerPayoutsData = [];
}
if (typeof minerDisplayedPayouts === "undefined") {
    var minerDisplayedPayouts = 0;
}
if (typeof minerPayoutsPerPage === "undefined") {
    var minerPayoutsPerPage = 10;
}

function minerStats_updatePayoutsTable(payouts) {
    const tableBody = document.getElementById("miner-payouts-table-body");
    tableBody.innerHTML = "";

    if (!payouts.length) {
        tableBody.innerHTML = `<tr><td colspan="6" class="text-center">No payouts found</td></tr>`;
        return;
    }

    let shownPayouts = payouts.slice(minerDisplayedPayouts, minerDisplayedPayouts + minerPayoutsPerPage);

    shownPayouts.forEach(payout => {
        const row = document.createElement("tr");

        let statusIcon = payout.status === "Confirmed"
            ? '<span style="color: green;">✅</span>'
            : payout.status === "Pending"
            ? '<span style="color: orange;">⏳</span>'
            : payout.status === "Failed"
            ? '<span style="color: red;">❌</span>'
            : '<span style="color: gray;">❓</span>';

        let blockText = payout.block_height !== "N/A" ? `${payout.block_height}` : "N/A";
        let forBlockText = payout.for_block !== "N/A" ? `${payout.for_block}` : "N/A";

        row.innerHTML = `
            <td>${new Date(payout.time * 1000).toLocaleString()}</td>
            <td class="text-start"><a href="http://testnode.yadaminers.pl/explorer?term=${payout.hash}" target="_blank">
                ${payout.hash.substring(0, 36)}...</a></td>
            <td>${payout.amount.toFixed(6)} YDA</td>
            <td>${forBlockText}</td>
            <td>${blockText}</td>
            <td class="text-center">${statusIcon} ${payout.status}</td>
        `;
        tableBody.appendChild(row);
    });
}

function updateMinerPayoutPagination() {
    const paginationDiv = document.getElementById("payout-pagination");
    paginationDiv.innerHTML = ""; 

    let totalPages = Math.ceil(minerPayoutsData.length / minerPayoutsPerPage);
    if (totalPages === 0) totalPages = 1;

    for (let i = 1; i <= totalPages; i++) {
        let tab = document.createElement("button");
        tab.className = `btn btn-outline-dark mx-1 ${i === 1 ? "active" : ""}`;
        tab.innerText = `Page ${i}`;
        tab.onclick = () => changeMinerPayoutPage(i);
        paginationDiv.appendChild(tab);
    }
}

function changeMinerPayoutPage(page) {
    minerDisplayedPayouts = (page - 1) * minerPayoutsPerPage;
    minerStats_updatePayoutsTable(minerPayoutsData);

    document.querySelectorAll("#payout-pagination button").forEach((btn, index) => {
        btn.classList.toggle("active", index + 1 === page);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    const savedAddress = localStorage.getItem("minerAddress");

    if (savedAddress) {
        console.log(`🔄 Loading stats for saved address: ${savedAddress}`);
        document.getElementById("miner-address").value = savedAddress;
        loadMinerStatsData();
    }
});

document.getElementById("miner-address").addEventListener("keypress", function(event) {
    if (event.key === "Enter") {
        loadMinerStatsData();
    }
});
