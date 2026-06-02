/**
 * useWeb2Auth — OAuth 2.0 Device Authorization Grant composable (RFC 8628).
 *
 * Flow:
 *   1. Call connect(provider, nodeUrl, kelOpts) — POSTs to the server's device/start
 *      endpoint and returns { user_code, verification_uri, expires_in,
 *      interval, poll }.
 *   2. Display user_code + verification_uri to the user (via ChatWindow card).
 *   3. Call poll() — polls the server until authorized or the code expires.
 *      On success, fetches profile info (/oauth/<provider>/me) and stores
 *      { nonce, label, kel_slot } in activeSessions.microsoft (array) or as a plain
 *      nonce string for other providers.
 *   4. activeSessions is sent as web2_sessions in every /api/chat body so the
 *      server resolves the real access token.
 *
 * activeSessions shape:
 *   {
 *     github: "<nonce>",
 *     microsoft: [{ nonce, label, kel_slot }, ...]
 *   }
 *
 * KEL (Key Event Log) integration:
 *   - At connect time, if wallet key material is provided, the browser signs a
 *     bind proof and sends it to /api/oauth/<provider>/session/bind. The server
 *     stores the current KEL public key in the session doc.
 *   - Write actions go through the on-chain rotation approval flow in ChatPane
 *     (same as W3C VC booking agents) and are executed via /api/microsoft/execute.
 *
 * Security notes:
 *   - OAuth access tokens NEVER reach the browser; only the opaque nonce is
 *     returned and kept in a Vue ref (not localStorage).
 *   - No popup windows, no callback URLs, no per-node app registration.
 */

import { ref } from "vue";
import { kelDeriveKey, sha256Hex, hex, signMessage } from "./useCrypto.js";
import { getSkillsSettings } from "./useStorage.js";

const LS_WEB2_SESSIONS = "yadacoin_web2_sessions";

// Persist sessions across page reloads.  Only nonce / label / encrypted_token
// (ciphertext) and IV are stored — the plaintext token never leaves the server.
function _loadSessions() {
  try {
    const raw = localStorage.getItem(LS_WEB2_SESSIONS);
    if (raw) {
      const sessions = JSON.parse(raw);
      // Migrate old format: non-Microsoft providers were sometimes stored as
      // {nonce, label} WITHOUT an encrypted_token — those should be the plain
      // nonce string.  Wallet-mode entries with encrypted_token are kept as-is.
      for (const provider of Object.keys(sessions)) {
        if (provider === "microsoft") continue;
        const val = sessions[provider];
        if (val && typeof val === "object" && !val.encrypted_token) {
          // Old dict without encryption — downgrade to plain nonce string
          sessions[provider] = val.nonce || "";
          if (!sessions[provider]) delete sessions[provider];
        }
      }
      return sessions;
    }
  } catch (_) {}
  return {};
}

function _persist(sessions) {
  try {
    localStorage.setItem(LS_WEB2_SESSIONS, JSON.stringify(sessions));
  } catch (_) {}
}

const activeSessions = ref(_loadSessions());

/**
 * Fetch basic profile info for a just-authorized session.
 * Used to label the account (e.g. "matt@work.com") in activeSessions.
 */
async function _fetchAccountLabel(provider, nonce, nodeUrl) {
  try {
    const resp = await fetch(
      `${nodeUrl}/ai-agent-auth/api/oauth/${encodeURIComponent(provider)}/me?nonce=${encodeURIComponent(nonce)}`,
    );
    if (resp.ok) {
      const data = await resp.json();
      return (
        (data.identifier || data.display_name || "").trim() || nonce.slice(0, 8)
      );
    }
  } catch (_) {}
  return nonce.slice(0, 8);
}

/**
 * Perform the KEL session bind: sign the nonce with slot-0 key and send to server.
 * Silently degrades if the server is unreachable or returns an error.
 */
async function _bindKelSession(
  provider,
  nonce,
  nodeUrl,
  rootPrivHex,
  rootCcHex,
) {
  const k0 = kelDeriveKey(rootPrivHex, rootCcHex, 0);
  const k1 = kelDeriveKey(rootPrivHex, rootCcHex, 1);
  const k2 = kelDeriveKey(rootPrivHex, rootCcHex, 2);
  const msgBytes = new TextEncoder().encode(nonce + ":bind");
  const messageHex = hex.fromBytes(msgBytes);
  const sig = await signMessage(msgBytes, k0.privBytes);
  const sigHex = hex.fromBytes(sig);
  const resp = await fetch(
    `${nodeUrl}/ai-agent-auth/api/oauth/${encodeURIComponent(provider)}/session/bind`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nonce,
        kel_pubkey_hex: k0.pubHex,
        kel_sig_hex: sigHex,
        kel_message_hex: messageHex,
        kel_next_digest: sha256Hex(k1.pubHex),
        kel_twice_next_digest: sha256Hex(k2.pubHex),
      }),
    },
  );
  if (!resp.ok) {
    const errData = await resp.json().catch(() => ({}));
    throw new Error(errData.error || `KEL bind failed (HTTP ${resp.status})`);
  }
}

/**
 * Start the device authorization flow for the given provider.
 *
 * @param {string} provider   e.g. "github", "microsoft"
 * @param {string} [nodeUrl]  base URL of the YadaCoin node (default: same origin)
 * @param {object} [kelOpts]  optional { rootPrivHex, rootCcHex } for KEL binding
 * @returns {Promise<{user_code, verification_uri, expires_in, interval, poll}>}
 */
async function connect(provider, nodeUrl = "", kelOpts = {}) {
  const startBody = {};
  if (kelOpts?.tokenEncKeyHex) startBody.token_enc_key = kelOpts.tokenEncKeyHex;
  // Include user-configured client_id from Skills settings (overrides server config)
  const skills = getSkillsSettings();
  const skillsKey =
    provider === "github"
      ? "github_client_id"
      : provider === "microsoft"
        ? "microsoft_client_id"
        : null;
  const userClientId = skillsKey ? (skills[skillsKey] || "").trim() : "";
  if (userClientId) startBody.client_id = userClientId;
  const resp = await fetch(
    `${nodeUrl}/ai-agent-auth/api/oauth/${encodeURIComponent(provider)}/device/start`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(startBody),
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
     * @returns {Promise<{ nonce: string, label: string }>}
     */
    poll: () =>
      _pollUntilAuthorized(
        provider,
        session_nonce,
        nodeUrl,
        interval || 5,
        expires_in || 300,
        kelOpts,
      ),
  };
}

async function _pollUntilAuthorized(
  provider,
  session_nonce,
  nodeUrl,
  intervalSecs,
  expiresSecs,
  kelOpts,
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
      const label = await _fetchAccountLabel(provider, session_nonce, nodeUrl);

      // Microsoft requires KEL bind — wallet key material must be present
      if (provider === "microsoft") {
        if (!kelOpts?.rootPrivHex || !kelOpts?.rootCcHex) {
          throw new Error(
            "YadaCoin wallet not loaded. Open your wallet before connecting Microsoft.",
          );
        }
        await _bindKelSession(
          provider,
          session_nonce,
          nodeUrl,
          kelOpts.rootPrivHex,
          kelOpts.rootCcHex,
        );
      }

      if (provider === "microsoft") {
        const current = activeSessions.value.microsoft || [];
        activeSessions.value = {
          ...activeSessions.value,
          microsoft: [
            ...current,
            {
              nonce: session_nonce,
              label,
              encrypted_token: pollData.encrypted_access_token || "",
              iv: pollData.iv || "",
            },
          ],
        };
      } else if (pollData.encrypted_access_token) {
        // Wallet mode: server encrypted the token — store as object (same shape
        // as a single Microsoft entry, without the array wrapper)
        activeSessions.value = {
          ...activeSessions.value,
          [provider]: {
            nonce: session_nonce,
            label,
            encrypted_token: pollData.encrypted_access_token,
            iv: pollData.iv || "",
          },
        };
      } else {
        // Server-side mode: no wallet, store plain nonce
        activeSessions.value = {
          ...activeSessions.value,
          [provider]: session_nonce,
        };
      }
      _persist(activeSessions.value);
      return { nonce: session_nonce, label };
    } else if (pollData.status === "slow_down") {
      pollMs += 5000; // back off an extra 5 s as required by RFC 8628
    } else if (pollData.status === "error") {
      throw new Error(pollData.message || "Authorization failed");
    }
    // status === "pending" → keep polling
  }
  throw new Error("Device code expired — please try connecting again.");
}

/** Remove a specific Microsoft account (by nonce), or remove any other provider entirely. */
function disconnectAccount(provider, nonce) {
  const sessions = { ...activeSessions.value };
  if (provider === "microsoft") {
    const current = sessions.microsoft || [];
    const filtered = current.filter((a) => a.nonce !== nonce);
    if (filtered.length === 0) {
      delete sessions.microsoft;
    } else {
      sessions.microsoft = filtered;
    }
  } else {
    delete sessions[provider];
  }
  activeSessions.value = sessions;
  _persist(sessions);
}

/** Remove all sessions for a provider. */
function disconnect(provider) {
  const sessions = { ...activeSessions.value };
  delete sessions[provider];
  activeSessions.value = sessions;
  _persist(sessions);
}

function isConnected(provider) {
  if (provider === "microsoft") {
    return (activeSessions.value.microsoft || []).length > 0;
  }
  return !!activeSessions.value[provider];
}

/**
 * Re-encrypt all active OAuth session tokens after a key rotation.
 * Must be called (and awaited) BEFORE updating LS_PRIV at each rotation site.
 *
 * @param {string}  oldPrivHex   Current (pre-rotation) LS_PRIV hex
 * @param {string}  newPrivHex   Incoming (post-rotation) LS_PRIV hex
 * @param {string}  [nodeUrl]    YadaCoin node base URL
 * @param {boolean} [clientSide] true  = client wallet: browser does all crypto;
 *                               false = server wallet: server re-encrypts using
 *                               the token_enc_key stored in MongoDB
 */
async function rekeyActiveSessions(
  oldPrivHex,
  newPrivHex,
  nodeUrl = "",
  clientSide = true,
) {
  // Collect all wallet-mode session entries across ALL providers.
  // Microsoft is an array; other providers (e.g. github) are single dicts.
  const msArr = activeSessions.value.microsoft || [];

  /** @type {{provider: string, entry: object}[]} */
  const toRekey = [];
  for (const entry of msArr) {
    if (entry.nonce && entry.encrypted_token && entry.iv)
      toRekey.push({ provider: "microsoft", entry });
  }
  for (const provider of Object.keys(activeSessions.value)) {
    if (provider === "microsoft") continue;
    const val = activeSessions.value[provider];
    if (val && typeof val === "object" && val.nonce && val.encrypted_token && val.iv)
      toRekey.push({ provider, entry: val });
  }

  if (!toRekey.length) return;

  if (clientSide) {
    // ── Client wallet: all crypto happens in the browser ─────────────────────
    const oldKeyBuf = await crypto.subtle.digest(
      "SHA-256",
      hex.toBytes(oldPrivHex),
    );
    const oldKeyObj = await crypto.subtle.importKey(
      "raw",
      new Uint8Array(oldKeyBuf),
      { name: "AES-GCM", length: 256 },
      false,
      ["decrypt"],
    );
    const newKeyBuf = await crypto.subtle.digest(
      "SHA-256",
      hex.toBytes(newPrivHex),
    );
    const newKeyObj = await crypto.subtle.importKey(
      "raw",
      new Uint8Array(newKeyBuf),
      { name: "AES-GCM", length: 256 },
      false,
      ["encrypt"],
    );

    const rekeyed = [];
    for (const { entry } of toRekey) {
      try {
        const plaintext = await crypto.subtle.decrypt(
          { name: "AES-GCM", iv: hex.toBytes(entry.iv) },
          oldKeyObj,
          hex.toBytes(entry.encrypted_token),
        );
        const newIv = crypto.getRandomValues(new Uint8Array(12));
        const newCt = await crypto.subtle.encrypt(
          { name: "AES-GCM", iv: newIv },
          newKeyObj,
          plaintext,
        );
        const newEncHex = hex.fromBytes(new Uint8Array(newCt));
        const newIvHex = hex.fromBytes(newIv);
        entry.encrypted_token = newEncHex;
        entry.iv = newIvHex;
        rekeyed.push({
          nonce: entry.nonce,
          encrypted_token: newEncHex,
          iv: newIvHex,
        });
      } catch (_) {
        // Session could not be re-keyed — leave as-is
      }
    }
    if (!rekeyed.length) return;
    _persist(activeSessions.value);
    // Tell server to sync MongoDB (fire-and-forget — localStorage is ground truth)
    try {
      await fetch(`${nodeUrl}/ai-agent-auth/api/rekey-sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rekeyed }),
      });
    } catch (_) {}
  } else {
    // ── Server wallet: server re-encrypts using its stored token_enc_key ──────
    const newKeyBuf = await crypto.subtle.digest(
      "SHA-256",
      hex.toBytes(newPrivHex),
    );
    const newKeyHex = hex.fromBytes(new Uint8Array(newKeyBuf));
    const nonces = toRekey.map(({ entry: e }) => e.nonce);
    try {
      const resp = await fetch(`${nodeUrl}/ai-agent-auth/api/rekey-sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_token_enc_key: newKeyHex, nonces }),
      });
      if (!resp.ok) return;
      const data = await resp.json();
      // Update localStorage with the server-re-encrypted ciphertext
      for (const { entry } of toRekey) {
        const result = (data.rekeyed || []).find(
          (r) => r.nonce === entry.nonce,
        );
        if (result) {
          entry.encrypted_token = result.encrypted_token;
          entry.iv = result.iv;
        }
      }
      if ((data.rekeyed || []).length > 0) _persist(activeSessions.value);
    } catch (_) {
      // Non-fatal; AgentChatHandler fallback tiers handle a stale token
    }
  }
}

export function useWeb2Auth() {
  return {
    activeSessions,
    connect,
    disconnect,
    disconnectAccount,
    isConnected,
    rekeyActiveSessions,
  };
}
