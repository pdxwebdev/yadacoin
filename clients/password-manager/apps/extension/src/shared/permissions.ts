/** Optional host access: request per node and per site origin. */

export function toOriginPattern(urlOrOrigin: string): string | null {
  try {
    const raw = urlOrOrigin.trim();
    if (!raw) return null;
    const u = new URL(raw.includes("://") ? raw : `https://${raw}`);
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    return `${u.origin}/*`;
  } catch {
    return null;
  }
}

function scriptIdFor(origin: string): string {
  let h = 0;
  for (let i = 0; i < origin.length; i++) h = (h * 31 + origin.charCodeAt(i)) | 0;
  return "yada_bridge_" + (h >>> 0).toString(16);
}

export async function requestOriginAccess(..._urls: string[]): Promise<boolean> {
  return true;
}

export async function enableBridgeOnOrigin(origin: string): Promise<void> {
  if (typeof chrome === "undefined" || !chrome.scripting?.registerContentScripts) {
    return;
  }
  const matches = toOriginPattern(origin);
  if (!matches) return;
  const id = scriptIdFor(origin);
  try {
    await chrome.scripting.unregisterContentScripts({ ids: [id] }).catch(() => {});
    await chrome.scripting.registerContentScripts([
      {
        id,
        js: ["content.js"],
        matches: [matches],
        persistAcrossSessions: true,
        runAt: "document_idle",
      },
    ]);
  } catch {
    /* already registered or unsupported */
  }
}

export async function injectBridgeIntoTab(tabId: number): Promise<void> {
  if (typeof chrome === "undefined" || !chrome.scripting?.executeScript) return;
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content.js"],
    });
  } catch {
    /* no access yet */
  }
}

export async function enableSiteAndNode(
  siteUrl: string,
  nodeUrl: string
): Promise<boolean> {
  const ok = await requestOriginAccess(siteUrl, nodeUrl);
  if (!ok) return false;
  try {
    const href = siteUrl.includes("://") ? siteUrl : `https://${siteUrl}`;
    await enableBridgeOnOrigin(new URL(href).origin);
  } catch {
    /* ignore */
  }
  return true;
}
