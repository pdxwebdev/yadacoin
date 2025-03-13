function loadGetStartData() {
    console.log("🔄 Fetching pool connection details...");

    fetch('/get-start')
        .then(response => response.json())
        .then(data => {
            document.getElementById("pool-url").textContent = `${data.pool.pool_url}:${data.pool.pool_port}`;
            document.getElementById("pool-port").textContent = data.pool.pool_port;
            document.getElementById("pool-diff").textContent = data.pool.pool_diff;
            document.getElementById("pool-algorithm").textContent = data.pool.algorithm;
        })
        .catch(error => {
            console.error("❌ Error fetching pool details:", error);
        });

    setupMinerSoftwareDropdown()
}

function setupMinerSoftwareDropdown() {
    console.log("🔧 Setting up miner software dropdown...");

    const miners = ["XMRig", "XMRigCC", "SRB Miner"];
    const minerMenu = document.getElementById("minerSoftwareMenu");
    const minerDropdownButton = document.getElementById("minerSoftwareDropdown");

    minerMenu.innerHTML = ""

    miners.forEach(miner => {
        let listItem = document.createElement("li");
        let link = document.createElement("a");
        link.classList.add("dropdown-item");
        link.href = "#";
        link.setAttribute("data-software", miner);
        link.textContent = miner;

        link.addEventListener("click", function (event) {
            event.preventDefault();
            console.log(`🟢 Selected miner software: ${miner}`);
            selectedSoftware = miner;
            minerDropdownButton.textContent = miner;
        });

        listItem.appendChild(link);
        minerMenu.appendChild(listItem);
    });

    console.log("✅ Miner software dropdown is ready.");
}

let selectedSoftware = ""

document.getElementById("generate-config").addEventListener("click", function () {
    const wallet = document.getElementById("wallet-address").value.trim();
    const workerId = document.getElementById("worker-id").value.trim();
    const poolUrl = document.getElementById("pool-url").textContent

    if (!wallet) {
        alert("❌ Please enter your wallet address.");
        return;
    }
    if (!selectedSoftware) {
        alert("❌ Please select miner software.");
        return;
    }

    let userConfig = wallet;
    if (workerId) userConfig += `.${workerId}`;

    let configResult = "";

    if (selectedSoftware === "SRB Miner") {
        configResult = `
<pre>
./SRBMiner-MULTI --algorithm randomyada --pool ${poolUrl} --wallet ${userConfig} --password x --cpu-threads 0 --disable-gpu --keepalive true
</pre>`;
    } else if (selectedSoftware === "XMRig" || selectedSoftware === "XMRigCC") {
        configResult = `
<pre>
{
"algo": "rx/yada",
"coin": null,
"url": "${poolUrl}",
"user": "${userConfig}",
"pass": "x",
"rig-id": null,
"nicehash": false,
"keepalive": true,
"enabled": true
}
</pre>`;
    }

    console.log(`✅ Generated config for ${selectedSoftware}:`, configResult);
    document.getElementById("config-result").innerHTML = configResult;
    document.getElementById("config-result").classList.remove("d-none");
});