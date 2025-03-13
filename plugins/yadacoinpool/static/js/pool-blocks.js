document.addEventListener("DOMContentLoaded", loadPoolBlocksData);

if (typeof blocksData === "undefined") {
    var blocksData = [];
}
if (typeof displayedBlocks === "undefined") {
    var displayedBlocks = 0;
}
if (typeof blocksPerPage === "undefined") {
    var blocksPerPage = 10;
}

async function loadPoolBlocksData() {
    console.log("📡 Fetching /pool-blocks...");
    try {
        const response = await fetch("/pool-blocks");
        const data = await response.json();
        console.log("✅ Blocks data received:", data);
        blocksData = data.blocks;
        displayedBlocks = 0;
        updateBlocksTable();
    } catch (error) {
        console.error("❌ Error fetching blocks:", error);
        document.getElementById("blocks-table-body").innerHTML =
            `<tr><td colspan="5" class="text-center text-danger">Error loading blocks</td></tr>`;
    }
}

function updateBlocksTable() {
    const tableBody = document.getElementById("blocks-table-body");

    if (displayedBlocks === 0) tableBody.innerHTML = "";

    const newBlocks = blocksData.slice(displayedBlocks, displayedBlocks + blocksPerPage);
    displayedBlocks += newBlocks.length;

    if (newBlocks.length === 0) {
        document.getElementById("load-more").style.display = "none";
        return;
    }

    newBlocks.forEach(block => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${block.height}</td>
            <td>${new Date(block.time * 1000).toLocaleString()}</td>
            <td>${block.difficulty.toFixed(3)}</td>
            <td class="text-start hash-cell"><a href="http://testnode.yadaminers.pl/explorer?term=${block.hash}" target="_blank">${block.hash}</a></td>
            <td>${block.txn_count}</td>
            <td>${block.reward.toFixed(4)} YDA</td>
        `;
        tableBody.appendChild(row);
    });
}

document.getElementById("load-more").addEventListener("click", updateBlocksTable);
