function loadLogsData() {
    activeLogType = "app";
    activeLogFile = 0;

    const defaultLogTab = document.getElementById("log-file-0");
    defaultLogTab.classList.add("active");
    fetchLogs();
}

function switchLogTab(type) {
    activeLogType = type;

    document.getElementById("app-log-tab").classList.remove("active");
    document.getElementById("access-log-tab").classList.remove("active");
    document.getElementById(`${type}-log-tab`).classList.add("active");

    activeLogFile = 0;
    document.querySelectorAll("#logFileTabs .nav-link").forEach(tab => tab.classList.remove("active"));
    document.getElementById("log-file-0").classList.add("active");

    fetchLogs();
}

function changeLogFile(fileIndex) {
    activeLogFile = fileIndex;

    document.querySelectorAll("#logFileTabs .nav-link").forEach(tab => tab.classList.remove("active"));
    document.getElementById(`log-file-${fileIndex}`).classList.add("active");

    fetchLogs();
}

async function fetchLogs() {
    const filter = document.getElementById("log-filter").value;
    const logContainer = document.getElementById("log-container");
    const logFileName = activeLogFile === 0 ? `yada_${activeLogType}.log` : `yada_${activeLogType}.log.${activeLogFile}`;

    try {
        const response = await fetch(`/yadacoinstatic/dashboard/log/${logFileName}`);
        if (!response.ok) throw new Error("Log file not found");

        const logs = await response.text();
        const logLines = logs.split("\n").filter(line => 
            filter === "ALL" || line.includes(filter)
        );

        logContainer.innerHTML = logLines.map(line => {
            if (line.includes("INFO")) return `<span class="log-info">${line}</span>`;
            if (line.includes("WARNING")) return `<span class="log-warning">${line}</span>`;
            if (line.includes("ERROR")) return `<span class="log-error">${line}</span>`;
            if (line.includes("DEBUG")) return `<span class="log-debug">${line}</span>`;
            return line;
        }).join("\n");

        if (document.getElementById("auto-scroll").checked) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    } catch (error) {
        logContainer.innerHTML = "Error loading logs...";
        console.error(error);
    }
}

let autoRefreshInterval = null;

function toggleAutoRefresh() {
    if (document.getElementById("auto-refresh").checked) {
        autoRefreshInterval = setInterval(fetchLogs, 30000);
    } else {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}