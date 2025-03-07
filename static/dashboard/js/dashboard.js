async function loadSection(section) {
    const contentDiv = document.getElementById("content");

    try {
        const response = await fetch(`/yadacoinstatic/dashboard/content/${section}.html`);
        if (!response.ok) throw new Error("Section not found");

        contentDiv.innerHTML = await response.text();

        if (section === "status") {
            await loadScript("/yadacoinstatic/dashboard/js/status.js", () => {
                if (typeof loadStatusData === "function") {
                    loadStatusData();
                } else {
                    console.error("loadStatusData is not defined even after loading script.");
                }
            });
        } 
        else if (section === "peers") {
            await loadScript("/yadacoinstatic/dashboard/js/peers.js", () => {
                if (typeof loadPeersData === "function") {
                    loadPeersData();
                }
            });
        } 
        else if (section === "logs") {
            await loadScript("/yadacoinstatic/dashboard/js/logs.js", () => {
                if (typeof loadLogsData === "function") {
                    loadLogsData();
                }
            });
        }

    } catch (error) {
        contentDiv.innerHTML = "<h2>Error loading section.</h2>";
        console.error(error);
    }
}

async function loadScript(scriptPath, callback) {
    return new Promise((resolve, reject) => {
        let script = document.createElement("script");
        script.src = scriptPath;
        script.onload = () => {
            console.log(`Loaded script: ${scriptPath}`);
            if (callback) callback();
            resolve();
        };
        script.onerror = () => reject(new Error(`Error loading script: ${scriptPath}`));
        document.body.appendChild(script);
    });
}

document.addEventListener("DOMContentLoaded", () => loadSection("status"));