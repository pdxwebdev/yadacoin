/**
 * Content script — bridges harness page postMessage ↔ extension background.
 * Page receives password + nextPasswordHash for RP-side verify; never private keys.
 */
const HOST_ID = "yada-password-root";

if (!document.getElementById(HOST_ID)) {
  const host = document.createElement("div");
  host.id = HOST_ID;
  host.style.all = "initial";
  document.documentElement.appendChild(host);
  host.attachShadow({ mode: "open" });
}

window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  const data = event.data;
  if (!data || typeof data !== "object") return;

  if (data.type === "YADA_PASSWORD_REGISTER") {
    const requestId = data.requestId;
    chrome.runtime.sendMessage(
      {
        type: "YADA_REGISTER_SITE",
        origin: window.location.origin.toLowerCase(),
      },
      (response) => {
        const err = chrome.runtime.lastError;
        window.postMessage(
          {
            type: "YADA_PASSWORD_REGISTER_RESULT",
            requestId,
            ...(err
              ? { ok: false, message: err.message }
              : response || { ok: false, message: "no response" }),
          },
          "*"
        );
      }
    );
  }

  if (data.type === "YADA_PASSWORD_SIGNIN") {
    const requestId = data.requestId;
    chrome.runtime.sendMessage(
      {
        type: "YADA_SIGNIN_ROTATE",
        origin: window.location.origin.toLowerCase(),
      },
      (response) => {
        const err = chrome.runtime.lastError;
        window.postMessage(
          {
            type: "YADA_PASSWORD_SIGNIN_RESULT",
            requestId,
            ...(err
              ? { ok: false, message: err.message }
              : response || { ok: false, message: "no response" }),
          },
          "*"
        );
      }
    );
  }

  if (data.type === "YADA_PASSWORD_RESYNC") {
    const requestId = data.requestId;
    chrome.runtime.sendMessage(
      {
        type: "YADA_RESYNC_SITE",
        origin: window.location.origin.toLowerCase(),
      },
      (response) => {
        const err = chrome.runtime.lastError;
        window.postMessage(
          {
            type: "YADA_PASSWORD_RESYNC_RESULT",
            requestId,
            ...(err
              ? { ok: false, message: err.message }
              : response || { ok: false, message: "no response" }),
          },
          "*"
        );
      }
    );
  }

  if (data.type === "YADA_PASSWORD_STATUS") {
    const requestId = data.requestId;
    chrome.runtime.sendMessage(
      {
        type: "YADA_SITE_STATUS",
        origin: window.location.origin.toLowerCase(),
      },
      (response) => {
        const err = chrome.runtime.lastError;
        window.postMessage(
          {
            type: "YADA_PASSWORD_STATUS_RESULT",
            requestId,
            ...(err
              ? { ok: false, message: err.message }
              : response || { ok: false }),
          },
          "*"
        );
      }
    );
  }
});

window.postMessage({ type: "YADA_PASSWORD_READY" }, "*");
