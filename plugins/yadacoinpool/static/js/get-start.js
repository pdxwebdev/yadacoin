function loadGetStartData() {
    fetch("/get-start", { cache: "no-store" })
        .then(response => response.json())
        .then(data => {
            const pool = data.pool || {};
            const url = document.getElementById("pool-url");
            if (url) url.textContent = `${pool.pool_url}:${pool.pool_port}`;
            const port = document.getElementById("pool-port");
            if (port) port.textContent = pool.pool_port ?? "—";
            const diff = document.getElementById("pool-diff");
            if (diff) diff.textContent = pool.pool_diff ?? "—";
            const algo = document.getElementById("pool-algorithm");
            if (algo) algo.textContent = pool.algorithm ?? "—";
        })
        .catch(() => {});

    const select = document.getElementById("miner-software");
    if (!select || select.dataset.ready) return;
    ["XMRig", "XMRigCC", "SRB Miner"].forEach(miner => {
        const option = document.createElement("option");
        option.value = miner;
        option.textContent = miner;
        select.appendChild(option);
    });
    select.dataset.ready = "1";
    document.getElementById("generate-config").addEventListener("click", generateConfig);
}

function generateConfig() {
    const wallet = document.getElementById("wallet-address").value.trim();
    const workerId = document.getElementById("worker-id").value.trim();
    const software = document.getElementById("miner-software").value;
    const poolUrl = document.getElementById("pool-url").textContent;
    const result = document.getElementById("config-result");
    if (!wallet || !software) {
        result.hidden = false;
        result.textContent = "Enter a wallet address and choose miner software.";
        return;
    }
    const user = workerId ? `${wallet}.${workerId}` : wallet;
    let text = "";
    if (software === "SRB Miner") {
        text = `./SRBMiner-MULTI --algorithm randomyada --pool ${poolUrl} --wallet ${user} --password x --cpu-threads 0 --disable-gpu --keepalive true`;
    } else {
        text = JSON.stringify({
            algo: "rx/yada",
            coin: null,
            url: poolUrl,
            user,
            pass: "x",
            "rig-id": null,
            nicehash: false,
            keepalive: true,
            enabled: true,
        }, null, 2);
    }
    result.hidden = false;
    result.textContent = text;
}
