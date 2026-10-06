document.addEventListener("DOMContentLoaded", loadPoolPayoutsData);

if (typeof payoutsData === "undefined") {
  var payoutsData = [];
}
if (typeof displayedPayouts === "undefined") {
  var displayedPayouts = 0;
}
if (typeof payoutsPerPage === "undefined") {
  var payoutsPerPage = 10;
}

async function loadPoolPayoutsData() {
  console.log("📡 Fetching /pool-payouts...");
  try {
    const response = await fetch("/pool-payouts", { cache: "no-store" });
    const data = await response.json();
    console.log("✅ Payouts data received:", data);
    payoutsData = data.payouts;
    displayedPayouts = 0;
    updatePayoutsTable();
  } catch (error) {
    console.error("❌ Error fetching payouts:", error);
    document.getElementById("payouts-table-body").innerHTML =
      `<tr><td colspan="6" class="text-center text-danger">Error loading payouts</td></tr>`;
  }
}

function updatePayoutsTable(payouts) {
  const tableBody = document.getElementById("payouts-table-body");

  if (!tableBody) {
    console.error("❌ Table body element not found!");
    return;
  }

  if (displayedPayouts === 0) tableBody.innerHTML = "";

  const newPayouts = payoutsData.slice(
    displayedPayouts,
    displayedPayouts + payoutsPerPage,
  );
  displayedPayouts += newPayouts.length;

  if (newPayouts.length === 0) {
    const loadMore = document.getElementById("load-more-payouts");
    if (loadMore) loadMore.style.display = "none";
    if (displayedPayouts === 0) {
      tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No payouts found</td></tr>`;
    }
    return;
  }

  newPayouts.forEach((payout) => {
    let payoutStatus = payout.status || "Pending";

    let blockLink =
      payout.block_height && payout.block_height !== "N/A"
        ? `<a href="/explorer?term=${payout.block_height}">${payout.block_height}</a>`
        : "N/A";

    const row = document.createElement("tr");
    row.innerHTML = `
            <td>${new Date(payout.time * 1000).toLocaleString()}</td>
            <td class="mono hash-cell"><a href="/explorer?term=${payout.hash}">${(payout.hash || "N/A").toString().substring(0, 18)}…</a></td>
            <td class="right">${payout.amount ? payout.amount.toFixed(6) : "0.000000"} YDA</td>
            <td class="right">${payout.fee ? payout.fee.toFixed(6) : "0.000000"} YDA</td>
            <td class="right">${payout.payees || "N/A"}</td>
            <td>${blockLink}</td>
            <td>${payoutStatus}</td>
        `;
    tableBody.appendChild(row);
  });
}

function getStatusIcon(payout) {
  return payout.amount > 0 ? "✅" : "❌";
}

document
  .getElementById("load-more-payouts")
  .addEventListener("click", updatePayoutsTable);
