async function loadSection(section) {
    const contentDiv = document.getElementById("content");

    try {
        console.log(`📡 Loading section: ${section}`);
        const response = await fetch(`/yadacoinpoolstatic/content/${section}.html`);
        if (!response.ok) throw new Error("Section not found");

        contentDiv.innerHTML = await response.text();
        console.log(`✅ Section ${section} loaded.`);

        await loadScript(`/yadacoinpoolstatic/js/${section}.js`, () => {
            console.log(`✅ Script for ${section} loaded.`);

            setTimeout(() => {
                if (section === "dashboard" && typeof loadDashboardData === "function") {
                    loadDashboardData();
                } 
                else if (section === "pool-blocks" && typeof loadPoolBlocksData === "function") {
                    loadPoolBlocksData();
                } 
                else if (section === "pool-payouts" && typeof loadPoolPayoutsData === "function") {
                    loadPoolPayoutsData();
                } 
                else if (section === "miners-stats" && typeof loadMinerStatsData === "function") {
                    console.log("🟢 Calling loadMinerStatsData()...");
                    loadMinerStatsData();
                } 
                else if (section === "get-start" && typeof loadGetStartData === "function") { 
                    console.log("🟢 Calling loadGetStartData()...");
                    loadGetStartData();
                }
                else {
                    console.warn(`⚠ No load function defined for ${section}`);
                }
            }, 100);

        });

    } catch (error) {
        contentDiv.innerHTML = "<h2>Error loading section.</h2>";
        console.error(`❌ Error loading section ${section}:`, error);
    }
}

async function loadScript(scriptPath, callback) {
    return new Promise((resolve, reject) => {
        let script = document.createElement("script");
        script.src = scriptPath;
        script.onload = () => {
            console.log(`✅ Loaded script: ${scriptPath}`);
            if (callback) callback();
            resolve();
        };
        script.onerror = () => reject(new Error(`❌ Error loading script: ${scriptPath}`));
        document.body.appendChild(script);
    });
}

document.addEventListener("DOMContentLoaded", () => loadSection("dashboard"));
