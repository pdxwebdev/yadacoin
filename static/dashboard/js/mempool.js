async function loadMempoolData() {
    try {
        const response = await fetch('/get-pending-transaction-ids');
        const data = await response.json();
        const tableBody = document.getElementById('mempool-table');
        tableBody.innerHTML = '';

        if (data.txn_ids.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="2">No pending transactions</td></tr>';
            return;
        }

        data.txn_ids.forEach(txn_id => {
            const truncatedId = txn_id.slice(0, 8) + '...' + txn_id.slice(-8);
            const row = document.createElement('tr');
            row.innerHTML = `
                <td title="${txn_id}" class="txn-id">${truncatedId}</td>
                <td><button class="btn btn-primary btn-sm" onclick="viewTransaction('${txn_id}')">View</button></td>
            `;
            tableBody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading mempool:', error);
    }
}
async function viewTransaction(txn_id) {
    try {
        const response = await fetch(`/get-pending-transaction?id=${txn_id}`);
        const data = await response.json();

        function formatTimestamp(timestamp) {
            const date = new Date(timestamp * 1000);
            return date.toLocaleString();
        }

        let inputsHTML = `<button class="btn btn-secondary btn-sm" onclick="toggleInputs()">Show Inputs</button>`;
        inputsHTML += `<ul id="inputs-list" style="display:none;">`;
        data.inputs.forEach(input => {
            inputsHTML += `<li class="txn-input">${input.id}</li>`;
        });
        inputsHTML += `</ul>`;

        let outputsHTML = '<h5>Outputs</h5>';
        outputsHTML += '<div class="outputs-container">';
        data.outputs.forEach(output => {
            outputsHTML += `
                <div class="output-box">
                    <strong>${output.to}</strong> <br>
                    <span class="badge bg-success">${output.value.toFixed(4)} YDA</span>
                </div>
            `;
        });
        outputsHTML += '</div>';

        document.getElementById('transaction-details').innerHTML = `
            <p><strong>Transaction ID:</strong> <span class="txn-id">${data.id}</span></p>
            <p><strong>Time:</strong> ${formatTimestamp(data.time)}</p>
            <p><strong>Fee:</strong> ${data.fee} YDA</p>
            <p><strong>Hash:</strong> <span class="txn-hash">${data.hash}</span></p>
            <div>${inputsHTML}</div>
            <div>${outputsHTML}</div>
        `;

        const modal = new bootstrap.Modal(document.getElementById('transactionModal'));
        modal.show();
    } catch (error) {
        console.error('Error fetching transaction details:', error);
    }
}

function toggleInputs() {
    const inputsList = document.getElementById('inputs-list');
    if (inputsList.style.display === 'none') {
        inputsList.style.display = 'block';
    } else {
        inputsList.style.display = 'none';
    }
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
}

document.addEventListener("DOMContentLoaded", loadMempoolData);
