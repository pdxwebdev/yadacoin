/**
 * useWeb2Auth — OAuth 2.0 Device Authorization Grant composable (RFC 8628).
 *
 * Flow:
 *   1. Call connect(provider, nodeUrl) — POSTs to the server's device/start
 *      endpoint and returns { user_code, verification_uri, expires_in,
 *      interval, poll }.
 *   2. Display user_code + verification_uri to the user (via ChatWindow card).
 *   3. Call poll() — polls the server until authorized or the code expires.
 *      Resolves with the opaque session nonce on success.
 *   4. The nonce is stored in activeSessions and sent as web2_sessions in
 *      every /api/chat body so the server resolves the real access token.
 *
 * Security notes:
 *   - OAuth access tokens NEVER reach the browser; only the opaque nonce is
 *     returned and kept in a Vue ref (not localStorage).
 *   - No popup windows, no callback URLs, no per-node app registration.
 *   - Supported providers: github, google, microsoft (and any future RFC 8628
 *     compliant provider added to the server's _OAUTH_PROVIDERS registry).
 */

import { ref } from "vue";

// In-memory store: { github: "<nonce>", ... }
// Cleared on page reload — real token lives only on the server.
const activeSessions = ref({});

/**
 * Start the device authorization flow for the given provider.
 *
 * @param {string} provider   e.g. "github", "google", "microsoft"
 * @param {string} [nodeUrl]  base URL of the YadaCoin node (default: same origin)
 * @returns {Promise<{user_code, verification_uri, expires_in, interval, poll}>}
 */
async function connect(provider, nodeUrl = "") {
  const resp = await fetch(
    `${nodeUrl}/ai-agent-auth/api/oauth/${encodeURIComponent(provider)}/device/start`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    },
  );
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(
      err.error ||
        `Failed to start ${provider} device flow (HTTP ${resp.status})`,
    );
  }
  const data = await resp.json();
  const { session_nonce, user_code, verification_uri, expires_in, interval } =
    data;
  return {
    user_code,
    verification_uri,
    expires_in: expires_in || 300,
    interval: interval || 5,
    /**
     * Polls the server until the device is authorized or the code expires.
     * @returns {Promise<string>} resolves with the opaque session nonce
     */
    poll: () =>
      _pollUntilAuthorized(
        provider,
        session_nonce,
        nodeUrl,
        interval || 5,
        expires_in || 300,
      ),
  };
}

async function _pollUntilAuthorized(
  provider,
  session_nonce,
  nodeUrl,
  intervalSecs,
  expiresSecs,
) {
  const deadline = Date.now() + expiresSecs * 1000;
  let pollMs = intervalSecs * 1000;

  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, pollMs));

    const resp = await fetch(
      `${nodeUrl}/ai-agent-auth/api/oauth/${encodeURIComponent(provider)}/device/poll`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_nonce }),
      },
    );
    const pollData = await resp.json().catch(() => ({}));

    if (pollData.status === "authorized") {
      activeSessions.value = {
        ...activeSessions.value,
        [provider]: session_nonce,
      };
      return session_nonce;
    } else if (pollData.status === "slow_down") {
      pollMs += 5000; // back off an extra 5 s as required by RFC 8628
    } else if (pollData.status === "error") {
      throw new Error(pollData.message || "Authorization failed");
    }
    // status === "pending" → keep polling
  }
  throw new Error("Device code expired — please try connecting again.");
}

function disconnect(provider) {
  const sessions = { ...activeSessions.value };
  delete sessions[provider];
  activeSessions.value = sessions;
}

function isConnected(provider) {
  return !!activeSessions.value[provider];
}

export function useWeb2Auth() {
  return { activeSessions, connect, disconnect, isConnected };
}
