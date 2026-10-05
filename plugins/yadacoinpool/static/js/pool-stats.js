async function loadSection(section) {
    const contentDiv = document.getElementById("content");
    const nav = document.getElementById("nav");
    if (nav) nav.classList.remove("open");
    document.querySelectorAll(".top nav a[data-section]").forEach(link => {
        link.classList.toggle("active", link.dataset.section === section);
    });
    if (window.__poolRefresh) {
        clearInterval(window.__poolRefresh);
        window.__poolRefresh = null;
    }

    try {
        const response = await fetch(`/yadacoinpoolstatic/content/${section}.html`);
        if (!response.ok) throw new Error("Section not found");
        contentDiv.innerHTML = await response.text();
        await loadScript(`/yadacoinpoolstatic/js/${section}.js?t=${Date.now()}`);
        const starters = {
            dashboard: "loadDashboardData",
            "pool-blocks": "loadPoolBlocksData",
            "pool-payouts": "loadPoolPayoutsData",
            "miners-stats": "loadMinerStatsData",
            "get-start": "loadGetStartData",
        };
        const starter = window[starters[section]];
        if (typeof starter === "function") starter();
        if (section === "dashboard") {
            window.__poolRefresh = setInterval(() => {
                if (typeof loadDashboardData === "function") loadDashboardData();
            }, 20000);
        }
    } catch (error) {
        contentDiv.innerHTML = "<section class='panel'><h2>Error loading section.</h2></section>";
    }
}

function loadScript(scriptPath) {
    return new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = scriptPath;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error(scriptPath));
        document.body.appendChild(script);
    });
}

document.addEventListener("DOMContentLoaded", () => loadSection("dashboard"));
