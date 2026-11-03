import { setSiaStatus, uploadWithKey } from "./shared/sia.js";

const status = document.getElementById("status");

function say(text: string): void {
  if (status) status.textContent = text;
}

let requestId = "";

async function main(): Promise<void> {
  const port = chrome.runtime.connect({ name: "yada-upload" });
  const job = await chrome.runtime.sendMessage({ type: "YADA_UPLOAD_TAKE" });
  if (!job?.ok) throw new Error(job?.message || "no upload waiting");
  requestId = String(job.requestId || "");
  setSiaStatus((text) => {
    say(text);
    void chrome.runtime.sendMessage({
      type: "YADA_UPLOAD_PROGRESS",
      requestId,
      message: text,
    });
  });
  say("Uploading to Sia…");
  const file = new Blob([Uint8Array.from(atob(job.fileB64), (c) => c.charCodeAt(0))], {
    type: job.mime || "",
  });
  const uploaded = await uploadWithKey(job.appKey, file);
  let thumb: { file_id: string; share_url: string } | null = null;
  if (job.thumbB64) {
    say("Uploading thumbnail…");
    const thumbBlob = new Blob([Uint8Array.from(atob(job.thumbB64), (c) => c.charCodeAt(0))], {
      type: "image/jpeg",
    });
    thumb = await uploadWithKey(job.appKey, thumbBlob);
  }
  await chrome.runtime.sendMessage({
    type: "YADA_UPLOAD_DONE",
    requestId: job.requestId,
    file_id: uploaded.file_id,
    share_url: uploaded.share_url,
    size: uploaded.size,
    thumbnail_file_id: thumb?.file_id || "",
    thumbnail_share_url: thumb?.share_url || "",
  });
  say("Uploaded. You can close this window.");
  port.disconnect();
  setTimeout(() => window.close(), 600);
}

main().catch(async (e) => {
  const message = e instanceof Error ? e.message : String(e);
  say(message);
  await chrome.runtime
    .sendMessage({
      type: "YADA_UPLOAD_DONE",
      requestId,
      ok: false,
      message,
    })
    .catch(() => {});
});
