<template>
  <div class="chat-pane">
    <ChatWindow :messages="messages" ref="chatWindow" />

    <div class="input-area">
      <textarea
        ref="inputEl"
        v-model="userInput"
        :disabled="!sessionReady || busy"
        placeholder="Type a message…"
        rows="1"
        @keydown.enter.exact.prevent="send"
        @input="autoGrow"
      ></textarea>
      <button
        class="send-btn"
        :disabled="!sessionReady || !userInput.trim() || busy"
        @click="send"
      >
        ↑
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from "vue";
import { marked } from "marked";
import ChatWindow from "./ChatWindow.vue";
import {
  LS_PRIV,
  LS_CC,
  LS_WALLET_MODE,
  LS_ACTIVE_AGENT,
  getLlmSettings,
  getNodeUrl,
  saveBookingCredential,
  getWalletMode,
  isClientWallet,
} from "../composables/useStorage.js";
import {
  hex,
  compactSigToDerBase64,
  deriveSecurePath,
  getPublicKeyHex,
  getP2PKH,
  buildRotationTxn,
  secp,
  sha256,
} from "../composables/useCrypto.js";

// ── Props / emit ─────────────────────────────────────────────────────────────
const props = defineProps({
  agents: Array, // all agent types from /api/agents
});
const emit = defineEmits([
  "session-rotated",
  "agent-changed",
  "credential-issued",
  "setup-wallet",
]);

// ── Current agent (auto-detected) ────────────────────────────────────────────
const currentAgentId = ref("general");
const currentAgentType = computed(
  () => props.agents?.find((a) => a.id === currentAgentId.value) || null,
);

// ── State ─────────────────────────────────────────────────────────────────────
const messages = ref([]);
const userInput = ref("");
const busy = ref(false);
const inputEl = ref(null);
const chatWindow = ref(null);

// Per-conversation "extracted" scope (travel details, legal params, etc.)
let extractedScope = null;
let chatHistory = [];

// Vendor follow-up conversation state
// null | { queue, current: {service, vendorName}, vpData, vendorMessages }
const vendorState = ref(null);

// ── Session ──────────────────────────────────────────────────────────────────
// sessionTick is incremented externally (notifyWalletReady) to force the
// computed to re-evaluate, since Vue does not track localStorage reads.
const sessionTick = ref(0);
const sessionReady = computed(() => {
  sessionTick.value; // reactive dependency so we can force re-evaluation
  const p = localStorage.getItem(LS_PRIV);
  const c = localStorage.getItem(LS_CC);
  return !!(p && c);
});

onMounted(() => {
  if (!sessionReady.value) {
    const storedMode = localStorage.getItem(LS_WALLET_MODE);
    if (storedMode === "client") {
      // Client wallet mode but no key yet — prompt setup
      pushAgent(
        "\u26A0 No wallet found. Click the session pill to set up your personal wallet, or switch to Node Wallet mode in Settings.",
        true,
      );
      emit("setup-wallet");
    } else if (storedMode === "node") {
      // Node wallet mode explicitly set but no key derived yet
      pushAgent(
        "\u26A0 No operator key found. " +
          'Please <a href="/key-rotation/derived-keys" target="_blank" style="color:var(--accent)">initialise your key</a> first, then reload.',
        true,
      );
    } else {
      // Completely fresh load — no wallet mode chosen yet
      pushAgent(
        "Welcome! To get started, set up a <strong>Personal Wallet</strong> (generate your own BIP39 seed in the browser) or configure a <strong>Node Wallet</strong> (server-managed key). Open <em>Settings ⚙</em> to choose.",
        true,
      );
    }
  } else {
    pushAgent("Hello! I'm your YadaCoin AI agent. How can I help you today?");
  }
  nextTick(() => inputEl.value?.focus());
});

// Emit initial agent type once agents load
watch(
  () => props.agents,
  (agentList) => {
    if (agentList?.length) {
      const match = agentList.find((a) => a.id === currentAgentId.value);
      emit("agent-changed", match || agentList[0]);
    }
  },
  { immediate: true },
);

// ── Message helpers ───────────────────────────────────────────────────────────
function pushUser(text) {
  messages.value.push({ role: "user", content: text });
}

function pushAgent(html, isHtml = false) {
  const msg = {
    role: "agent",
    content: isHtml ? "" : html,
    html: isHtml ? html : null,
  };
  messages.value.push(msg);
  return msg;
}

function pushThinking() {
  const msg = {
    role: "agent",
    thinking: true,
    html: '<div class="typing"><span></span><span></span><span></span></div>',
  };
  messages.value.push(msg);
  return { index: messages.value.length - 1, msg };
}

function removeMsg(index) {
  messages.value.splice(index, 1);
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ── Input auto-grow ──────────────────────────────────────────────────────────
function autoGrow(e) {
  const el = e.target;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

// ── Agent registry discovery ──────────────────────────────────────────────────
/**
 * Search the blockchain agent registry for agents matching the user's intent.
 * Fires silently — if it fails or returns nothing, no message is shown.
 * Only runs once per intent switch (tracked by lastDiscoveredIntent).
 */
let lastDiscoveredIntent = "";

async function discoverAndPushAgents(intent, agentTypeId) {
  const key = `${agentTypeId}:${intent}`;
  if (key === lastDiscoveredIntent) return;
  lastDiscoveredIntent = key;
  try {
    const params = new URLSearchParams({
      intent,
      agent_type: agentTypeId,
      limit: "5",
    });
    const res = await fetch(
      getNodeUrl() + `/ai-agent-auth/api/agents/discover?${params}`,
    );
    if (!res.ok) return;
    const data = await res.json();
    const agents = (data.agents || []).slice(0, 5);
    if (!agents.length) return;

    const rows = agents
      .map(
        (a) =>
          `<div class="disc-agent-card">` +
          `<span class="disc-icon">${escHtml(a.icon || "🤖")}</span>` +
          `<div class="disc-body">` +
          `<a class="disc-label" href="${escHtml(a.endpoint_url)}" target="_blank" rel="noopener">${escHtml(a.label)}</a>` +
          (a.description
            ? `<div class="disc-desc">${escHtml(a.description)}</div>`
            : "") +
          `<div class="disc-caps">${(a.capabilities || []).map((c) => `<span class="disc-chip">${escHtml(c)}</span>`).join("")}</div>` +
          `</div></div>`,
      )
      .join("");

    pushAgent(
      `<div class="disc-header">🔍 Found ${agents.length} registered agent${agents.length > 1 ? "s" : ""} on-chain for <em>${escHtml(agentTypeId)}</em>:</div>` +
        `<div class="disc-list">${rows}</div>`,
      true,
    );
  } catch {
    // silent — discovery is best-effort
  }
}

// ── Main send ────────────────────────────────────────────────────────────────
async function send(overridePrompt) {
  // overridePrompt must be a plain string — DOM events from @click/@keydown are ignored
  const override = typeof overridePrompt === "string" ? overridePrompt : null;
  const prompt = override ?? userInput.value.trim();
  if (!prompt || busy.value || !sessionReady.value) return;
  if (!override) {
    userInput.value = "";
    if (inputEl.value) {
      inputEl.value.style.height = "auto";
    }
  }
  busy.value = true;
  if (!override) pushUser(prompt);

  // Vendor follow-up mode — route to vendor chat instead of LLM
  if (vendorState.value) {
    let result;
    try {
      result = await sendVendorMessage(prompt);
    } finally {
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
    }
    // Vendor signalled exit — re-dispatch through main agent chat
    if (result?.exitVendor) {
      await send(prompt);
    }
    return;
  }

  chatHistory.push({ role: "user", content: prompt });

  const { index: thinkIdx } = pushThinking();

  let data;
  try {
    const llmCfg = getLlmSettings();
    const resp = await fetch(getNodeUrl() + "/ai-agent-auth/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: chatHistory,
        agent_type: currentAgentId.value || "general",
        llm: {
          provider: llmCfg.provider,
          model: llmCfg.model || undefined,
          api_key: llmCfg.api_key || undefined,
          ollama_host: llmCfg.ollama_host || undefined,
          base_url: llmCfg.base_url || undefined,
        },
      }),
    });
    data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.status);
  } catch (e) {
    removeMsg(thinkIdx);
    pushAgent(
      `<span style="color:var(--red2)">⚠ Could not reach AI service: ${escHtml(String(e))}. ` +
        `Check LLM settings (⚙) or make sure Ollama is running (<code>ollama serve</code>).</span>`,
      true,
    );
    chatHistory.pop();
    busy.value = false;
    return;
  }

  removeMsg(thinkIdx);

  // Auto-switch agent type based on detected intent, then re-dispatch to new agent.
  // Loop up to MAX_HOPS to handle chains like therapy→general→travel in one send().
  const MAX_HOPS = 3;
  let hopCount = 0;
  while (
    hopCount < MAX_HOPS &&
    data.detected_agent_type &&
    data.detected_agent_type !== currentAgentId.value
  ) {
    hopCount++;
    const newAgent = props.agents?.find(
      (a) => a.id === data.detected_agent_type,
    );
    if (!newAgent) break;

    currentAgentId.value = data.detected_agent_type;
    localStorage.setItem(LS_ACTIVE_AGENT, currentAgentId.value);
    emit("agent-changed", newAgent);
    extractedScope = null; // reset scope when switching agent type

    // Re-send the user message to the new agent (chatHistory already contains it)
    const { index: redirectIdx } = pushThinking();
    try {
      const llmCfg2 = getLlmSettings();
      const resp2 = await fetch(getNodeUrl() + "/ai-agent-auth/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: chatHistory,
          agent_type: currentAgentId.value,
          llm: {
            provider: llmCfg2.provider,
            model: llmCfg2.model || undefined,
            api_key: llmCfg2.api_key || undefined,
            ollama_host: llmCfg2.ollama_host || undefined,
            base_url: llmCfg2.base_url || undefined,
          },
        }),
      });
      data = await resp2.json();
      if (!resp2.ok) throw new Error(data.error || resp2.status);
    } catch (e) {
      removeMsg(redirectIdx);
      pushAgent(
        `<span style="color:var(--red2)">⚠ Could not reach AI service: ${escHtml(String(e))}.</span>`,
        true,
      );
      busy.value = false;
      return;
    }
    removeMsg(redirectIdx);

    // Search on-chain registry for agents matching this intent
    if (currentAgentId.value !== "general") {
      discoverAndPushAgents(prompt, currentAgentId.value);
    }
  }

  // Merge extracted fields — never allow the LLM to set `confirmed` directly;
  // confirmation must come from the user explicitly in a separate turn.
  if (data.extracted) {
    if (!extractedScope) extractedScope = {};
    for (const [k, v] of Object.entries(data.extracted)) {
      if (k === "confirmed") continue; // strip: LLM cannot self-confirm
      if (v != null && v !== "") extractedScope[k] = v;
    }
  }

  chatHistory.push({ role: "assistant", content: data.reply });

  // For non-general agents, search the on-chain registry in the background.
  // The dedup guard prevents re-running for the same intent.
  if (currentAgentId.value && currentAgentId.value !== "general") {
    discoverAndPushAgents(prompt, currentAgentId.value);
  }

  // ── Wallet agent read-only actions (no approval needed) ──────────────────
  if (
    currentAgentId.value === "wallet_agent" &&
    extractedScope?.action &&
    ["get_balance", "get_transactions", "get_pending"].includes(
      extractedScope.action,
    )
  ) {
    const action = extractedScope.action;
    // Optimistically push the LLM reply first
    pushAgent(data.reply);
    // Then fetch and display the actual data
    const privKey = localStorage.getItem(LS_PRIV);
    if (privKey) {
      try {
        const pubHex = getPublicKeyHex(hex.toBytes(privKey));
        const baseUrl = getNodeUrl();
        if (action === "get_balance") {
          const res = await fetch(
            `${baseUrl}/ai-agent-auth/api/wallet/info?public_key=${encodeURIComponent(pubHex)}`,
          );
          if (res.ok) {
            const d = await res.json();
            pushAgent(
              `<div class="wallet-data-card">` +
                `<div class="wdc-title">💰 Balance</div>` +
                `<div class="wdc-address">Address: <code>${escHtml(d.address)}</code></div>` +
                `<div class="wdc-balance"><span class="wdc-amount">${escHtml(d.balance)}</span> YDA</div>` +
                `</div>`,
              true,
            );
          }
        } else if (action === "get_transactions") {
          // Fetch sent and received from existing wallet endpoints, merge
          const [sentRes, recvRes] = await Promise.all([
            fetch(
              `${baseUrl}/get-past-sent-txns?public_key=${encodeURIComponent(pubHex)}&page=1`,
            ),
            fetch(
              `${baseUrl}/get-past-received-txns?public_key=${encodeURIComponent(pubHex)}&page=1`,
            ),
          ]);
          const sentData = sentRes.ok
            ? await sentRes.json()
            : { past_transactions: [] };
          const recvData = recvRes.ok
            ? await recvRes.json()
            : { past_transactions: [] };
          const sentTxns = (sentData.past_transactions || []).map((t) => ({
            ...t,
            _direction: "sent",
          }));
          const recvTxns = (recvData.past_transactions || []).map((t) => ({
            ...t,
            _direction: "received",
          }));
          const txns = [...sentTxns, ...recvTxns]
            .sort((a, b) => (b.time || 0) - (a.time || 0))
            .slice(0, 10);
          if (!txns.length) {
            pushAgent(
              `<div class="wallet-data-card"><div class="wdc-title">📋 Transactions</div><div class="wdc-empty">No confirmed transactions found.</div></div>`,
              true,
            );
          } else {
            const rows = txns
              .slice(0, 10)
              .map((t) => {
                const dir = t._direction || "?";
                const dirIcon = dir === "sent" ? "↑" : "↓";
                const dirClass = dir === "sent" ? "wdc-sent" : "wdc-recv";
                const outs = (t.outputs || []).filter((o) => o.value > 0);
                const amt = outs.reduce((s, o) => s + (o.value || 0), 0);
                const to = outs.map((o) => o.to).join(", ");
                const ts = t.time
                  ? new Date(t.time * 1000).toLocaleString()
                  : "";
                return (
                  `<div class="wdc-txrow ${dirClass}">` +
                  `<span class="wdc-dir">${dirIcon}</span>` +
                  `<span class="wdc-amt">${amt.toFixed(8)} YDA</span>` +
                  `<span class="wdc-to">${escHtml(to.slice(0, 32))}…</span>` +
                  `<span class="wdc-ts">${escHtml(ts)}</span>` +
                  `</div>`
                );
              })
              .join("");
            pushAgent(
              `<div class="wallet-data-card">` +
                `<div class="wdc-title">📋 Recent Transactions</div>` +
                `${rows}` +
                `</div>`,
              true,
            );
          }
        } else if (action === "get_pending") {
          // Fetch sent and received pending from existing wallet endpoints, merge
          const [sentPendRes, recvPendRes] = await Promise.all([
            fetch(
              `${baseUrl}/get-past-pending-sent-txns?public_key=${encodeURIComponent(pubHex)}`,
            ),
            fetch(
              `${baseUrl}/get-past-pending-received-txns?public_key=${encodeURIComponent(pubHex)}`,
            ),
          ]);
          const sentPendData = sentPendRes.ok
            ? await sentPendRes.json()
            : { past_pending_transactions: [] };
          const recvPendData = recvPendRes.ok
            ? await recvPendRes.json()
            : { past_pending_transactions: [] };
          const sentPend = (sentPendData.past_pending_transactions || []).map(
            (t) => ({ ...t, _direction: "sent" }),
          );
          const recvPend = (recvPendData.past_pending_transactions || []).map(
            (t) => ({ ...t, _direction: "received" }),
          );
          const pending = [...sentPend, ...recvPend]
            .sort((a, b) => (b.time || 0) - (a.time || 0))
            .slice(0, 10);
          if (!pending.length) {
            pushAgent(
              `<div class="wallet-data-card"><div class="wdc-title">⏳ Pending Transactions</div><div class="wdc-empty">No pending transactions in mempool.</div></div>`,
              true,
            );
          } else {
            const rows = pending
              .slice(0, 10)
              .map((t) => {
                const dir = t._direction || "?";
                const dirIcon = dir === "sent" ? "↑" : "↓";
                const dirClass = dir === "sent" ? "wdc-sent" : "wdc-recv";
                const outs = (t.outputs || []).filter((o) => o.value > 0);
                const amt = outs.reduce((s, o) => s + (o.value || 0), 0);
                const to = outs.map((o) => o.to).join(", ");
                return (
                  `<div class="wdc-txrow ${dirClass}">` +
                  `<span class="wdc-dir">${dirIcon}</span>` +
                  `<span class="wdc-amt">${amt.toFixed(8)} YDA</span>` +
                  `<span class="wdc-to">${escHtml(to.slice(0, 32))}…</span>` +
                  `<span class="wdc-ts wdc-pending">pending</span>` +
                  `</div>`
                );
              })
              .join("");
            pushAgent(
              `<div class="wallet-data-card">` +
                `<div class="wdc-title">⏳ Pending Transactions</div>` +
                `${rows}` +
                `</div>`,
              true,
            );
          }
        }
      } catch {
        // silent — display is best-effort
      }
    }
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  if (data.complete && extractedScope && Object.keys(extractedScope).length) {
    // Show the reply + scope summary inline as an HTML message
    const scopeLines = Object.entries(extractedScope)
      .filter(([k]) => k !== "action")
      .map(([k, v]) => {
        const val = Array.isArray(v)
          ? v.map((s) => `<strong>${escHtml(s)}</strong>`).join(", ")
          : `<strong>${escHtml(String(v))}</strong>`;
        return `${escHtml(k.replace(/_/g, " "))}: ${val}`;
      })
      .join("<br>");

    // Build agent-specific approval message
    let approvalPrompt;
    if (currentAgentId.value === "wallet_agent") {
      const amt = extractedScope.amount ?? "";
      const action = extractedScope.action ?? "send";
      if (action === "wrap") {
        const ethAddr = extractedScope.eth_address ?? "";
        approvalPrompt =
          `<br><br>` +
          `<strong>Wrap:</strong> ${escHtml(String(amt))} YDA → bridge → <code>${escHtml(ethAddr)}</code> (Ethereum)<br><br>` +
          `Please enter your second factor to authorize this wrap transaction.`;
      } else {
        const toAddr = extractedScope.to_address ?? "";
        approvalPrompt =
          `<br><br>` +
          `<strong>Send:</strong> ${escHtml(String(amt))} YDA → <code>${escHtml(toAddr)}</code><br><br>` +
          `Please enter your second factor to authorize this transaction.`;
      }
    } else {
      approvalPrompt =
        `<br><br>${scopeLines}<br><br>` +
        `To proceed I'll broadcast a rotation transaction committing this scope on-chain as a ` +
        `W3C Verifiable Credential. Please enter your second factor to approve.`;
    }

    const summaryMsg = pushAgent(escHtml(data.reply) + approvalPrompt, true);

    // Attach approval card state into the message
    summaryMsg.showApproval = true;
    summaryMsg.approvalContext = {
      scope: { ...extractedScope },
      agentType: currentAgentType.value,
    };
    // Replace with final reactive version
    messages.value[messages.value.length - 1] = { ...summaryMsg };
    busy.value = false;
  } else {
    pushAgent(data.reply);
    busy.value = false;
  }
  nextTick(() => inputEl.value?.focus());
}

// ── Vendor follow-up conversation helpers ─────────────────────────────────────

/**
 * Build a signed VP from vpBase + a fresh challenge.
 * vpCanonicalBytes must be the pre-computed canonical bytes of vpBase.
 */
async function buildSignedVP(
  vpBase,
  vpCanonicalBytes,
  provPrivBytes,
  provPubHex,
  challenge,
) {
  const challengeBytes = new TextEncoder().encode(challenge);
  const msgBytes = new Uint8Array(
    challengeBytes.length + vpCanonicalBytes.length,
  );
  msgBytes.set(challengeBytes);
  msgBytes.set(vpCanonicalBytes, challengeBytes.length);
  const sigObj = await secp.signAsync(msgBytes, provPrivBytes);
  const proofValue = compactSigToDerBase64(sigObj);
  return {
    ...vpBase,
    proof: {
      type: "EcdsaSecp256k1Signature2019",
      challenge,
      created: new Date().toISOString(),
      proofPurpose: "authentication",
      verificationMethod: `did:yadacoin:${provPubHex}#keys-1`,
      proofValue,
    },
  };
}

/**
 * Call POST /api/vendor/<svc>/chat with a fresh challenge + re-signed VP.
 * Returns the parsed response data object.
 */
async function callVendorChatApi(service, vpData, vendorMessages) {
  const { vpBase, vpCanonicalBytes, provPrivBytes, provPubHex } = vpData;
  const llmCfg = getLlmSettings();

  // Fresh challenge
  const chalRes = await fetch(
    getNodeUrl() +
      `/ai-agent-auth/api/vendor/${service}/challenge?public_key=${encodeURIComponent(provPubHex)}`,
  );
  const chalData = await chalRes.json();
  if (!chalRes.ok || !chalData.challenge) throw new Error("no challenge");

  const vp = await buildSignedVP(
    vpBase,
    vpCanonicalBytes,
    provPrivBytes,
    provPubHex,
    chalData.challenge,
  );

  const chatRes = await fetch(
    getNodeUrl() + `/ai-agent-auth/api/vendor/${service}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        public_key: provPubHex,
        challenge: chalData.challenge,
        vp,
        messages: vendorMessages,
        llm: {
          provider: llmCfg.provider,
          model: llmCfg.model || undefined,
          api_key: llmCfg.api_key || undefined,
          ollama_host: llmCfg.ollama_host || undefined,
          base_url: llmCfg.base_url || undefined,
        },
      }),
    },
  );
  const data = await chatRes.json();
  if (!chatRes.ok) throw new Error(data.message || chatRes.status);
  return data;
}

/** Advance to the next service in the vendor queue, or clear vendorState if done. */
async function advanceVendorQueue() {
  const vs = vendorState.value;
  if (!vs || vs.queue.length === 0) {
    vendorState.value = null;
    return;
  }
  vs.current = vs.queue.shift();
  vs.vendorMessages = [
    { role: "user", content: "Hello, I'm ready to continue my booking." },
  ];

  const { index: thinkIdx } = pushThinking();
  try {
    const data = await callVendorChatApi(
      vs.current.service,
      vs.vpData,
      vs.vendorMessages,
    );
    removeMsg(thinkIdx);
    vs.vendorMessages.push({ role: "assistant", content: data.reply });
    if (data.complete) {
      if (data.credential) {
        saveBookingCredential(data.credential);
        emit("credential-issued");
      }
      pushAgent(
        `<strong>${escHtml(data.vendor)}:</strong><br>${marked.parse(data.reply)}` +
          `Confirmation: <code>${escHtml(data.confirmation)}</code>`,
        true,
      );
      await advanceVendorQueue();
    } else {
      pushAgent(
        `<strong>${escHtml(data.vendor)}:</strong><br>${marked.parse(data.reply)}`,
        true,
      );
    }
  } catch (e) {
    removeMsg(thinkIdx);
    pushAgent(
      `<span style="color:var(--red2)">⚠ ${escHtml(vs.current.vendorName)} error: ${escHtml(String(e))}</span>`,
      true,
    );
    vendorState.value = null;
  }
}

/** Handle one turn of vendor follow-up chat. */
async function sendVendorMessage(text) {
  const vs = vendorState.value;
  const { service, vendorName } = vs.current;

  vs.vendorMessages.push({ role: "user", content: text });

  const { index: thinkIdx } = pushThinking();
  try {
    const data = await callVendorChatApi(service, vs.vpData, vs.vendorMessages);
    removeMsg(thinkIdx);
    vs.vendorMessages.push({ role: "assistant", content: data.reply });
    if (data.exit_vendor) {
      // Vendor signals the user wants a different topic — tear down vendor flow
      // and re-route the same message through the main agent chat
      pushAgent(
        `<strong>${escHtml(data.vendor)}:</strong><br>${marked.parse(data.reply)}`,
        true,
      );
      vendorState.value = null;
      return { exitVendor: true };
    } else if (data.complete) {
      if (data.credential) {
        saveBookingCredential(data.credential);
        emit("credential-issued");
      }
      pushAgent(
        `<strong>${escHtml(data.vendor)}:</strong><br>${marked.parse(data.reply)}` +
          `Confirmation: <code>${escHtml(data.confirmation)}</code>`,
        true,
      );
      await advanceVendorQueue();
    } else {
      pushAgent(
        `<strong>${escHtml(data.vendor)}:</strong><br>${marked.parse(data.reply)}`,
        true,
      );
    }
  } catch (e) {
    removeMsg(thinkIdx);
    pushAgent(
      `<span style="color:var(--red2)">⚠ ${escHtml(vendorName)} error: ${escHtml(String(e))}</span>`,
      true,
    );
    vendorState.value = null;
  }
}

// ── Client-side rotation helper ───────────────────────────────────────────────
// Builds and broadcasts rotation transactions entirely in JS.
// Returns { prevPrivHex, prevCcHex, provPrivBytes, transactionId } on success
// or throws on failure.
async function doClientRotation(privBytes, ccBytes, sf, relationshipB64) {
  const child = deriveSecurePath(privBytes, ccBytes, sf);
  const gc1 = deriveSecurePath(child.priv, child.cc, sf);
  const gc2 = deriveSecurePath(gc1.priv, gc1.cc, sf);
  const gc3 = deriveSecurePath(gc2.priv, gc2.cc, sf);

  const currentPubHex = getPublicKeyHex(privBytes);
  const childPubHex = getPublicKeyHex(child.priv);
  const gc1PubHex = getPublicKeyHex(gc1.priv);
  const gc2PubHex = getPublicKeyHex(gc2.priv);
  const gc3PubHex = getPublicKeyHex(gc3.priv);

  // P2PKH addresses
  const currentPkh = getP2PKH(hex.toBytes(currentPubHex));
  const childPkh = getP2PKH(hex.toBytes(childPubHex));
  const gc1Pkh = getP2PKH(hex.toBytes(gc1PubHex));
  const gc2Pkh = getP2PKH(hex.toBytes(gc2PubHex));
  const gc3Pkh = getP2PKH(hex.toBytes(gc3PubHex));

  // Fetch prev_public_key_hash from the existing /key-event-log endpoint.
  // The last KEL entry's public_key_hash is the address that committed to
  // currentPkh as its prerotated key (i.e. K_{n-1}).  Empty log = inception.
  const kelRes = await fetch(
    getNodeUrl() +
      "/key-event-log?username_signature=asdf&public_key=" +
      encodeURIComponent(currentPubHex),
  );
  const kelData = await kelRes.json();
  if (!kelRes.ok) throw new Error(kelData.message || String(kelRes.status));
  const kel = kelData.key_event_log || [];

  // Use the last KEL entry's public_key_hash — that is the address which
  // pre-committed to the current signing key, i.e. K_{n-1}'s address.
  // The server handler (keyrotation/handlers.py) sets:
  //   prev_public_key_hash = latest.public_key_hash
  const prevPublicKeyHash =
    kel.length > 0 ? (kel[kel.length - 1].public_key_hash ?? "") : "";

  // Invariant: if prevPublicKeyHash === currentPkh the stored key hasn't been
  // advanced past the inception (e.g. wallet re-imported after inception hit
  // mempool but before localStorage was updated).  Advance LS_PRIV silently
  // and re-run with the corrected key — no error surfaced to the user.
  if (prevPublicKeyHash === currentPkh) {
    localStorage.setItem(LS_PRIV, hex.fromBytes(child.priv));
    localStorage.setItem(LS_CC, hex.fromBytes(child.cc));
    return doClientRotation(child.priv, child.cc, sf, relationshipB64);
  }

  // relationship_hash = sha256("") for empty relationship
  const enc = new TextEncoder();
  const relStr = relationshipB64 || "";
  const relHashBytes = sha256(enc.encode(relStr));
  const relHashHex = hex.fromBytes(relHashBytes);

  const txnTime = Math.floor(Date.now() / 1000);

  // Build unconfirmed transaction (signed by current key K_n)
  const unconfirmedTxn = await buildRotationTxn({
    signerPrivBytes: privBytes,
    publicKeyHex: currentPubHex,
    prerotatedPkh: childPkh,
    twicePrerotatedPkh: gc1Pkh,
    publicKeyHash: currentPkh,
    prevPublicKeyHash,
    relationship: relStr,
    relationshipHash: relHashHex,
    txnTime,
    inputs: [],
    outputs: [{ to: childPkh, value: 0.0 }],
  });

  // Build confirming transaction (signed by child key K_{n+1})
  const confirmingTxn = await buildRotationTxn({
    signerPrivBytes: child.priv,
    publicKeyHex: childPubHex,
    prerotatedPkh: gc1Pkh,
    twicePrerotatedPkh: gc2Pkh,
    publicKeyHash: childPkh,
    prevPublicKeyHash: currentPkh,
    relationship: "",
    relationshipHash: "",
    txnTime,
    inputs: [],
    outputs: [{ to: gc1Pkh, value: 0.0 }],
  });

  // Broadcast both transactions directly to the node's /transaction endpoint
  const bcastRes = await fetch(
    getNodeUrl() + "/transaction?username_signature=1",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify([unconfirmedTxn, confirmingTxn]),
    },
  );
  const bcastData = await bcastRes.json();
  if (!bcastRes.ok || bcastData.status === false)
    throw new Error(bcastData.message || String(bcastRes.status));

  return {
    prevPrivHex: hex.fromBytes(child.priv),
    prevCcHex: hex.fromBytes(child.cc),
    provPrivBytes: gc1.priv,
    transactionId: unconfirmedTxn.id,
  };
}

// ── Approval handler (called from App.vue overlay) ────────────────────────────
// Exposed so parent can invoke from ApprovalCard emit
async function runApprovalFlow(
  scope,
  agentType,
  { secondFactor, paymentMethod },
  onStep,
  onDone,
) {
  // ── Node config — key rotation then direct apply call, no vendor chat ────────
  if (agentType?.id === "node_config") {
    if (isClientWallet()) {
      onDone(
        false,
        "⚠ Node config changes are only available for node-wallet mode. Personal wallets cannot modify node settings.",
      );
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }
    const storedPriv0 = localStorage.getItem(LS_PRIV);
    const storedCc0 = localStorage.getItem(LS_CC);
    const sf0 = secondFactor;

    onStep("Deriving pre-committed child key…");
    const privBytes0 = hex.toBytes(storedPriv0);
    const ccBytes0 = hex.toBytes(storedCc0);
    const child0 = deriveSecurePath(privBytes0, ccBytes0, sf0);
    const childPubHex0 = getPublicKeyHex(child0.priv);
    onStep(
      "Pre-committed key derived: " + childPubHex0.slice(0, 20) + "…",
      "done",
    );

    onStep("Broadcasting rotation transaction…");
    let rotateData0;
    try {
      const rotateRes0 = await fetch(
        getNodeUrl() + "/key-rotation/derived-child-key",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            public_key: childPubHex0,
            second_factor: sf0,
            signature: "",
            relationship: "",
          }),
        },
      );
      rotateData0 = await rotateRes0.json();
      if (
        !rotateRes0.ok ||
        !rotateData0.status ||
        !rotateData0.prerotated_private_key
      ) {
        throw new Error(rotateData0.message || String(rotateRes0.status));
      }
    } catch (e) {
      onStep("Rotation failed: " + e.message, "fail");
      onDone(false, "Rotation failed: " + escHtml(e.message));
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }

    localStorage.setItem(LS_PRIV, rotateData0.prev_private_key);
    if (rotateData0.prev_chain_code)
      localStorage.setItem(LS_CC, rotateData0.prev_chain_code);
    emit("session-rotated", rotateData0.prev_private_key);
    onStep(
      "Rotation committed · txid " +
        rotateData0.transaction_id.slice(0, 20) +
        "…",
      "done",
    );

    // Build a minimal VP (no config data) signed by the prerotated key
    onStep("Building Verifiable Presentation…");
    const provPrivBytes0 = hex.toBytes(rotateData0.prerotated_private_key);
    const provPubHex0 = getPublicKeyHex(provPrivBytes0);
    const operatorPubHex0 = getPublicKeyHex(privBytes0);

    const gc1_0 = deriveSecurePath(child0.priv, child0.cc, sf0);
    const gc2_0 = deriveSecurePath(gc1_0.priv, gc1_0.cc, sf0);
    const agentPubHex0 = getPublicKeyHex(gc2_0.priv);

    const vc0 = {
      "@context": [
        "https://www.w3.org/ns/credentials/v2",
        "https://yadacoin.io/contexts/agent-auth/v1",
      ],
      type: ["VerifiableCredential", "AgentAuthorizationCredential"],
      issuer: `did:yadacoin:${operatorPubHex0}`,
      validFrom: new Date().toISOString(),
      credentialStatus: { type: "YadaKELStatus", mode: "rotation" },
      credentialSubject: {
        id: `did:yadacoin:${agentPubHex0}`,
        agentAuthorization: {
          type: "NodeConfigAuthorization",
          services: ["NodeConfigAuthorization"],
        },
      },
    };

    const vpBase0 = {
      "@context": ["https://www.w3.org/ns/credentials/v2"],
      type: ["VerifiablePresentation"],
      holder: `did:yadacoin:${provPubHex0}`,
      verifiableCredential: [vc0],
    };

    function deepSortKeys0(obj) {
      if (Array.isArray(obj)) return obj.map(deepSortKeys0);
      if (obj !== null && typeof obj === "object") {
        const s = {};
        Object.keys(obj)
          .sort()
          .forEach((k) => (s[k] = deepSortKeys0(obj[k])));
        return s;
      }
      return obj;
    }

    const vpCanonicalBytes0 = new TextEncoder().encode(
      JSON.stringify(deepSortKeys0(vpBase0)),
    );

    // Get challenge
    onStep("Fetching challenge…");
    let chalData0;
    try {
      const chalRes0 = await fetch(
        getNodeUrl() +
          `/ai-agent-auth/api/challenge?public_key=${encodeURIComponent(provPubHex0)}`,
      );
      chalData0 = await chalRes0.json();
      if (!chalRes0.ok || !chalData0.challenge) throw new Error("no challenge");
    } catch (e) {
      onStep("Challenge failed: " + e.message, "fail");
      onDone(false, "Challenge failed: " + escHtml(e.message));
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }

    const vp0 = await buildSignedVP(
      vpBase0,
      vpCanonicalBytes0,
      provPrivBytes0,
      provPubHex0,
      chalData0.challenge,
    );

    onStep("Applying config change…");
    try {
      const applyRes = await fetch(
        getNodeUrl() + "/ai-agent-auth/api/node-config/apply",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            public_key: provPubHex0,
            challenge: chalData0.challenge,
            vp: vp0,
            key: scope.config_key,
            value: scope.new_value,
          }),
        },
      );
      const applyData = await applyRes.json();
      if (!applyRes.ok)
        throw new Error(
          applyData.error || applyData.message || String(applyRes.status),
        );
      onStep("Config updated — node restarting", "done");
      onDone(
        true,
        `✅ <strong>Config updated!</strong><br><br>` +
          `<strong>${escHtml(scope.config_key)}</strong> → <code>${escHtml(String(scope.new_value))}</code><br><br>` +
          `The node is restarting to apply the change.<br>` +
          `Scope on-chain: <a href="${origin}/explorer?term=${rotateData0.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${rotateData0.transaction_id.slice(0, 24)}…</a>`,
      );
    } catch (e) {
      onStep("Apply failed: " + e.message, "fail");
      onDone(false, "Config apply failed: " + escHtml(e.message));
    }
    extractedScope = null;
    chatHistory = [];
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  // ── Wallet agent — key rotation then send/wrap transaction ───────────────
  if (agentType?.id === "wallet_agent") {
    const storedPrivW = localStorage.getItem(LS_PRIV);
    const storedCcW = localStorage.getItem(LS_CC);
    const sfW = secondFactor;
    const isWrap = scope.action === "wrap";
    const WRAP_BRIDGE = "16U1gAmHazqqEkbRE9KFPShAperjJreMRA";
    const toAddrW = isWrap ? WRAP_BRIDGE : scope.to_address || "";
    const ethAddrW = isWrap ? scope.eth_address || "" : "";
    const amtW = parseFloat(scope.amount) || 0;

    onStep("Deriving pre-committed child key…");
    const privBytesW = hex.toBytes(storedPrivW);
    const ccBytesW = hex.toBytes(storedCcW);
    const childW = deriveSecurePath(privBytesW, ccBytesW, sfW);
    const childPubHexW = getPublicKeyHex(childW.priv);
    onStep(
      "Pre-committed key derived: " + childPubHexW.slice(0, 20) + "…",
      "done",
    );

    onStep("Broadcasting rotation transaction…");
    let rotateDataW;
    try {
      const gc1W = deriveSecurePath(childW.priv, childW.cc, sfW);
      const gc2W = deriveSecurePath(gc1W.priv, gc1W.cc, sfW);
      const agentPubHexW = getPublicKeyHex(gc2W.priv);
      const operatorPubHexW = getPublicKeyHex(privBytesW);

      const vcW = {
        "@context": [
          "https://www.w3.org/ns/credentials/v2",
          "https://yadacoin.io/contexts/agent-auth/v1",
        ],
        type: ["VerifiableCredential", "AgentAuthorizationCredential"],
        issuer: `did:yadacoin:${operatorPubHexW}`,
        validFrom: new Date().toISOString(),
        credentialStatus: { type: "YadaKELStatus", mode: "rotation" },
        credentialSubject: {
          id: `did:yadacoin:${agentPubHexW}`,
          agentAuthorization: {
            type: "WalletAuthorization",
            services: ["WalletAuthorization"],
            to_address: toAddrW,
            amount: amtW,
            ...(isWrap ? { eth_address: ethAddrW } : {}),
          },
        },
      };

      const relB64W = btoa(unescape(encodeURIComponent(JSON.stringify(vcW))));

      if (isClientWallet()) {
        const clientRot = await doClientRotation(
          privBytesW,
          ccBytesW,
          sfW,
          relB64W,
        );
        rotateDataW = {
          prev_private_key: clientRot.prevPrivHex,
          prev_chain_code: clientRot.prevCcHex,
          prerotated_private_key: hex.fromBytes(clientRot.provPrivBytes),
          transaction_id: clientRot.transactionId,
          status: true,
        };
      } else {
        const rotResW = await fetch(
          getNodeUrl() + "/key-rotation/derived-child-key",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              public_key: childPubHexW,
              second_factor: sfW,
              signature: "",
              relationship: relB64W,
            }),
          },
        );
        rotateDataW = await rotResW.json();
        if (
          !rotResW.ok ||
          !rotateDataW.status ||
          !rotateDataW.prerotated_private_key
        ) {
          throw new Error(rotateDataW.message || String(rotResW.status));
        }
      }
    } catch (e) {
      onStep("Rotation failed: " + e.message, "fail");
      onDone(false, "Rotation failed: " + escHtml(e.message));
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }

    localStorage.setItem(LS_PRIV, rotateDataW.prev_private_key);
    if (rotateDataW.prev_chain_code)
      localStorage.setItem(LS_CC, rotateDataW.prev_chain_code);
    emit("session-rotated", rotateDataW.prev_private_key);
    onStep(
      "Rotation committed · txid " +
        rotateDataW.transaction_id.slice(0, 20) +
        "…",
      "done",
    );

    onStep("Building Verifiable Presentation…");
    const provPrivBytesW = hex.toBytes(rotateDataW.prerotated_private_key);
    const provPubHexW = getPublicKeyHex(provPrivBytesW);
    const operatorPubHexW2 = getPublicKeyHex(privBytesW);

    const gc1W2 = deriveSecurePath(childW.priv, childW.cc, sfW);
    const gc2W2 = deriveSecurePath(gc1W2.priv, gc1W2.cc, sfW);
    const agentPubHexW2 = getPublicKeyHex(gc2W2.priv);

    const vcW2 = {
      "@context": [
        "https://www.w3.org/ns/credentials/v2",
        "https://yadacoin.io/contexts/agent-auth/v1",
      ],
      type: ["VerifiableCredential", "AgentAuthorizationCredential"],
      issuer: `did:yadacoin:${operatorPubHexW2}`,
      validFrom: new Date().toISOString(),
      credentialStatus: { type: "YadaKELStatus", mode: "rotation" },
      credentialSubject: {
        id: `did:yadacoin:${agentPubHexW2}`,
        agentAuthorization: {
          type: "WalletAuthorization",
          services: ["WalletAuthorization"],
          to_address: toAddrW,
          amount: amtW,
          ...(isWrap ? { eth_address: ethAddrW } : {}),
        },
      },
    };

    const vpBaseW = {
      "@context": ["https://www.w3.org/ns/credentials/v2"],
      type: ["VerifiablePresentation"],
      holder: `did:yadacoin:${provPubHexW}`,
      verifiableCredential: [vcW2],
    };

    function deepSortKeysW(obj) {
      if (Array.isArray(obj)) return obj.map(deepSortKeysW);
      if (obj !== null && typeof obj === "object") {
        const s = {};
        Object.keys(obj)
          .sort()
          .forEach((k) => (s[k] = deepSortKeysW(obj[k])));
        return s;
      }
      return obj;
    }

    const vpCanonicalBytesW = new TextEncoder().encode(
      JSON.stringify(deepSortKeysW(vpBaseW)),
    );

    onStep("Fetching challenge…");
    let chalDataW;
    try {
      const chalResW = await fetch(
        getNodeUrl() +
          `/ai-agent-auth/api/challenge?public_key=${encodeURIComponent(provPubHexW)}`,
      );
      chalDataW = await chalResW.json();
      if (!chalResW.ok || !chalDataW.challenge) throw new Error("no challenge");
    } catch (e) {
      onStep("Challenge failed: " + e.message, "fail");
      onDone(false, "Challenge failed: " + escHtml(e.message));
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }

    const vpW = await buildSignedVP(
      vpBaseW,
      vpCanonicalBytesW,
      provPrivBytesW,
      provPubHexW,
      chalDataW.challenge,
    );

    onStep("Submitting transaction…");
    try {
      const sendRes = await fetch(
        getNodeUrl() + "/ai-agent-auth/api/wallet/send",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            public_key: provPubHexW,
            challenge: chalDataW.challenge,
            vp: vpW,
            ...(isWrap
              ? { eth_address: ethAddrW, amount: amtW }
              : { to_address: toAddrW, amount: amtW }),
          }),
        },
      );
      const sendData = await sendRes.json();
      if (!sendRes.ok)
        throw new Error(
          sendData.error || sendData.message || String(sendRes.status),
        );
      onStep("Transaction submitted", "done");
      onDone(
        true,
        isWrap
          ? `✅ <strong>Wrap transaction sent!</strong><br><br>` +
              `<strong>Amount:</strong> ${escHtml(String(amtW))} YDA<br>` +
              `<strong>Ethereum address:</strong> <code>${escHtml(ethAddrW)}</code><br>` +
              (sendData.transaction_id
                ? `<strong>Transaction ID:</strong> <code>${escHtml(String(sendData.transaction_id).slice(0, 32))}…</code><br>`
                : "") +
              `<br>KEL authorization on-chain: <a href="${origin}/explorer?term=${rotateDataW.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${rotateDataW.transaction_id.slice(0, 24)}…</a>`
          : `✅ <strong>Transaction sent!</strong><br><br>` +
              `<strong>To:</strong> <code>${escHtml(toAddrW)}</code><br>` +
              `<strong>Amount:</strong> ${escHtml(String(amtW))} YDA<br>` +
              (sendData.transaction_id
                ? `<strong>Transaction ID:</strong> <code>${escHtml(String(sendData.transaction_id).slice(0, 32))}…</code><br>`
                : "") +
              `<br>KEL authorization on-chain: <a href="${origin}/explorer?term=${rotateDataW.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${rotateDataW.transaction_id.slice(0, 24)}…</a>`,
      );
    } catch (e) {
      onStep("Send failed: " + e.message, "fail");
      onDone(false, "Transaction failed: " + escHtml(e.message));
    }
    extractedScope = null;
    chatHistory = [];
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  // ── Agent registration — server signs, no key rotation needed ──────────────
  if (agentType?.id === "agent_registration") {
    onStep("Broadcasting agent registration to blockchain…");
    try {
      const capabilities = (scope.capabilities || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const res = await fetch(
        getNodeUrl() + "/ai-agent-auth/api/agents/register",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            label: scope.label || "",
            description: scope.description || "",
            agent_type: scope.agent_type || "general",
            capabilities,
            endpoint_url: scope.endpoint_url || "",
            icon: scope.icon || "🤖",
          }),
        },
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || String(res.status));
      onStep("Agent registered · ID " + data.agent_id, "done");
      onDone(
        true,
        `✅ <strong>Agent registered on-chain!</strong><br><br>` +
          `<strong>Label:</strong> ${escHtml(scope.label)}<br>` +
          `<strong>Agent ID:</strong> <code>${escHtml(data.agent_id)}</code><br>` +
          `<strong>Transaction:</strong> <code>${escHtml((data.transaction_signature || "").slice(0, 32))}…</code>`,
      );
    } catch (e) {
      onStep("Registration failed: " + e.message, "fail");
      onDone(false, "Registration failed: " + escHtml(e.message));
    }
    extractedScope = null;
    chatHistory = [];
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  const storedPriv = localStorage.getItem(LS_PRIV);
  const storedCc = localStorage.getItem(LS_CC);
  const sf = secondFactor;

  onStep("Deriving pre-committed child key…");

  const privBytes = hex.toBytes(storedPriv);
  const ccBytes = hex.toBytes(storedCc);
  const child = deriveSecurePath(privBytes, ccBytes, sf);
  const childPubHex = getPublicKeyHex(child.priv);

  // Derive agent key (2 levels deeper) for the VC subject
  const gc1 = deriveSecurePath(child.priv, child.cc, sf);
  const gc2 = deriveSecurePath(gc1.priv, gc1.cc, sf);
  const agentPubHex = getPublicKeyHex(gc2.priv);
  const operatorPubHex = getPublicKeyHex(privBytes);

  const services = scope.services || [];

  const vc = {
    "@context": [
      "https://www.w3.org/ns/credentials/v2",
      "https://yadacoin.io/contexts/agent-auth/v1",
    ],
    type: ["VerifiableCredential", "AgentAuthorizationCredential"],
    issuer: `did:yadacoin:${operatorPubHex}`,
    validFrom: new Date().toISOString(),
    credentialStatus: { type: "YadaKELStatus", mode: "rotation" },
    credentialSubject: {
      id: `did:yadacoin:${agentPubHex}`,
      agentAuthorization: {
        type: agentType?.authorizationType || "AgentAuthorization",
        ...scope,
        ...(paymentMethod
          ? {
              paymentMethod: {
                token: paymentMethod.token,
                label: paymentMethod.label,
              },
            }
          : {}),
      },
    },
  };

  const relationshipB64 = btoa(
    unescape(encodeURIComponent(JSON.stringify(vc))),
  );
  onStep(
    "Pre-committed key derived: " + childPubHex.slice(0, 20) + "…",
    "done",
  );

  // Step 2: Broadcast rotation
  onStep("Broadcasting rotation transaction with scope committed on-chain…");
  let rotateData;
  try {
    if (isClientWallet()) {
      const clientRot = await doClientRotation(
        privBytes,
        ccBytes,
        sf,
        relationshipB64,
      );
      rotateData = {
        prev_private_key: clientRot.prevPrivHex,
        prev_chain_code: clientRot.prevCcHex,
        prerotated_private_key: hex.fromBytes(clientRot.provPrivBytes),
        transaction_id: clientRot.transactionId,
        status: true,
      };
    } else {
      const rotateRes = await fetch(
        getNodeUrl() + "/key-rotation/derived-child-key",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            public_key: childPubHex,
            second_factor: sf,
            signature: "",
            relationship: relationshipB64,
          }),
        },
      );
      rotateData = await rotateRes.json();
      if (
        !rotateRes.ok ||
        !rotateData.status ||
        !rotateData.prerotated_private_key
      ) {
        throw new Error(rotateData.message || String(rotateRes.status));
      }
    }
  } catch (e) {
    onStep("Rotation failed: " + e.message, "fail");
    onDone(false, "Rotation failed: " + e.message);
    // Re-present the approval card once the overlay finishes closing (onDone has a 600ms delay)
    const retryScope = { ...scope };
    const retryAgentType = agentType;
    setTimeout(() => {
      const scopeLines = Object.entries(retryScope)
        .map(([k, v]) => {
          const val = Array.isArray(v)
            ? v.map((s) => `<strong>${escHtml(s)}</strong>`).join(", ")
            : `<strong>${escHtml(String(v))}</strong>`;
          return `${escHtml(k.replace(/_/g, " "))}: ${val}`;
        })
        .join("<br>");
      const retryMsg = {
        role: "agent",
        html:
          `${scopeLines}<br><br>` +
          `To proceed I'll broadcast a rotation transaction committing this scope on-chain as a ` +
          `W3C Verifiable Credential. Please enter your second factor to approve.`,
        content: "",
        showApproval: true,
        approvalContext: { scope: retryScope, agentType: retryAgentType },
      };
      messages.value.push(retryMsg);
      messages.value[messages.value.length - 1] = { ...retryMsg };
    }, 700);
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }
  onStep(
    "Scope committed · txid " + rotateData.transaction_id.slice(0, 20) + "…",
    "done",
  );

  // Update stored keys
  localStorage.setItem(LS_PRIV, rotateData.prev_private_key);
  if (rotateData.prev_chain_code)
    localStorage.setItem(LS_CC, rotateData.prev_chain_code);
  emit("session-rotated", rotateData.prev_private_key);

  // Step 3: Build VP
  onStep("Building Verifiable Presentation…");
  const provPrivBytes = hex.toBytes(rotateData.prerotated_private_key);
  const provPubHex = getPublicKeyHex(provPrivBytes);

  const vpBase = {
    "@context": ["https://www.w3.org/ns/credentials/v2"],
    type: ["VerifiablePresentation"],
    holder: `did:yadacoin:${provPubHex}`,
    verifiableCredential: [vc],
  };

  function deepSortKeys(obj) {
    if (Array.isArray(obj)) return obj.map(deepSortKeys);
    if (obj !== null && typeof obj === "object") {
      const s = {};
      Object.keys(obj)
        .sort()
        .forEach((k) => (s[k] = deepSortKeys(obj[k])));
      return s;
    }
    return obj;
  }

  const vpCanonical = JSON.stringify(deepSortKeys(vpBase));
  const vpCanonicalBytes = new TextEncoder().encode(vpCanonical);
  onStep(`VP built · holder did:yadacoin:${provPubHex.slice(0, 16)}…`, "done");

  // Shared vpData object passed to vendor chat helpers
  const vpData = { vpBase, vpCanonicalBytes, provPrivBytes, provPubHex };

  // Step 4: Per-vendor — start vendor chat (get first question / immediate confirm)
  const confirmedResults = [];
  const pendingVendors = [];
  const errorResults = [];
  const targetServices = services.length ? services : agentType?.services || [];

  for (const service of targetServices) {
    onStep(`[${service}] Initiating vendor conversation…`);
    try {
      // Build an initial greeting that summarises what was already collected
      // so the vendor doesn't re-ask for information the user already provided.
      const scopeSummary =
        scope && Object.keys(scope).length
          ? " The customer has already provided the following details: " +
            Object.entries(scope)
              .map(
                ([k, v]) =>
                  `${k.replace(/_/g, " ")}: ${Array.isArray(v) ? v.join(", ") : v}`,
              )
              .join("; ") +
            ". Please use this information and only ask for anything still missing."
          : "";
      const initGreeting = `Hello, I'm ready to finalize my booking.${scopeSummary}`;
      const initMessages = [{ role: "user", content: initGreeting }];
      const data = await callVendorChatApi(service, vpData, initMessages);
      if (data.complete) {
        onStep(`[${service}] Confirmed: ${data.confirmation}`, "done");
        if (data.credential) {
          saveBookingCredential(data.credential);
          emit("credential-issued");
        }
        confirmedResults.push({
          service,
          status: "ok",
          confirmation: data.confirmation,
          vendor: data.vendor,
        });
      } else {
        onStep(`[${service}] Vendor has follow-up questions`, "done");
        pendingVendors.push({
          service,
          vendorName: data.vendor,
          vendorMessages: [
            { role: "user", content: initGreeting },
            { role: "assistant", content: data.reply },
          ],
        });
      }
    } catch (e) {
      onStep(`[${service}] error: ${e.message}`, "fail");
      errorResults.push({ service, status: "error", message: String(e) });
    }
  }

  // Build summary of immediate confirmations + errors
  const allResults = [...confirmedResults, ...errorResults];
  const txSnippet = rotateData.transaction_id.slice(0, 24) + "…";

  if (pendingVendors.length > 0) {
    // Close the overlay with a partial summary; vendor chat continues in the main chat
    const confirmedLines = confirmedResults
      .map(
        (r) =>
          `✓ <strong>${escHtml(r.service)}</strong> (${escHtml(r.vendor)}): <code>${escHtml(r.confirmation)}</code>`,
      )
      .join("<br>");
    const errorLines = errorResults
      .map(
        (r) =>
          `✗ <strong>${escHtml(r.service)}</strong>: <span style="color:var(--red2)">${escHtml(r.message)}</span>`,
      )
      .join("<br>");
    const summaryHtml =
      (confirmedLines ? confirmedLines + "<br>" : "") +
      (errorLines ? errorLines : "");
    // Push summary directly so it lands in chat BEFORE the first vendor
    // question, which is pushed synchronously right after.  Then call onDone
    // with an empty string to just close the overlay (no duplicate message).
    if (summaryHtml.trim()) pushAgent(summaryHtml.trim(), true);
    // Push scope txid right here — after summary, before first vendor question
    const snip0 = rotateData.transaction_id.slice(0, 24) + "\u2026";
    pushAgent(
      `Scope on-chain: <a href="${origin}/explorer?term=${rotateData.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${snip0}</a>`,
      true,
    );
    onDone(true, ""); // close overlay only

    // Set vendor state — first pending service becomes current, rest go into queue
    const [first, ...rest] = pendingVendors;
    vendorState.value = {
      current: first,
      queue: rest,
      vpData,
      vendorMessages: first.vendorMessages,
    };

    // Post the first vendor question to the main chat
    await nextTick();
    pushAgent(
      `<strong>${escHtml(first.vendorName)}:</strong><br>${marked.parse(first.vendorMessages[first.vendorMessages.length - 1].content)}`,
      true,
    );
  } else {
    // All services resolved immediately — classic done flow
    const resultLines = allResults
      .map((r) =>
        r.status === "ok"
          ? `✓ <strong>${escHtml(r.service)}</strong> (${escHtml(r.vendor)}): <code>${escHtml(r.confirmation)}</code>`
          : `✗ <strong>${escHtml(r.service)}</strong>: <span style="color:var(--red2)">${escHtml(r.message)}</span>`,
      )
      .join("<br>");
    const anyOk = confirmedResults.length > 0;
    const allOk = errorResults.length === 0 && confirmedResults.length > 0;
    if (allOk) {
      onDone(
        true,
        `✅ <strong>All services booked!</strong><br><br>${resultLines}<br><br>Scope on-chain: <a href="${origin}/explorer?term=${rotateData.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${txSnippet}</a>`,
      );
    } else if (anyOk) {
      onDone(
        true,
        `⚠️ <strong>Partial success</strong><br><br>${resultLines}<br><br>Scope on-chain: <a href="${origin}/explorer?term=${rotateData.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${txSnippet}</a>`,
      );
    } else {
      onDone(
        false,
        `❌ <strong>All bookings failed</strong><br><br>${resultLines}`,
      );
    }
  }

  extractedScope = null;
  chatHistory = [];
  busy.value = false;
  nextTick(() => inputEl.value?.focus());
}

/**
 * Called by the parent after wallet setup completes so the chat reactivates
 * without requiring a full page reload.
 */
function notifyWalletReady() {
  sessionTick.value++; // forces sessionReady to re-evaluate
  // Replace any "no wallet" warning messages with the normal greeting
  messages.value = messages.value.filter(
    (m) =>
      !m.html?.includes("No wallet found") &&
      !m.html?.includes("No operator key found") &&
      !m.content?.includes("No wallet found") &&
      !m.content?.includes("No operator key found") &&
      !m.content?.includes("To get started, set up"),
  );
  pushAgent(
    "Wallet ready! I'm your YadaCoin AI agent. How can I help you today?",
  );
  nextTick(() => inputEl.value?.focus());
}

defineExpose({ runApprovalFlow, messages, busy, notifyWalletReady });
</script>

<style scoped>
.chat-pane {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
}
.input-area {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
}
.input-area textarea {
  flex: 1 1 0;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-family: inherit;
  font-size: 0.88rem;
  line-height: 1.5;
  padding: 9px 12px;
  resize: none;
  overflow-y: auto;
  scrollbar-width: thin;
  transition: border-color 0.15s;
}
.input-area textarea:focus {
  outline: none;
  border-color: var(--accent);
}
.input-area textarea:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.send-btn {
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: 8px;
  width: 36px;
  height: 36px;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
  flex-shrink: 0;
}
.send-btn:hover:not(:disabled) {
  background: var(--accent2);
}
.send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>

<!-- Wallet data card styles — injected into ChatWindow's v-html output -->
<style>
.wallet-data-card {
  background: #0d1117;
  border: 1px solid #1e3a5f;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 0.82rem;
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}
.wdc-title {
  font-weight: 700;
  color: #58a6ff;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 1px solid #1e3a5f;
  padding-bottom: 6px;
  margin-bottom: 2px;
}
.wdc-address {
  color: #8b949e;
  font-size: 0.76rem;
  word-break: break-all;
}
.wdc-balance {
  font-size: 1.1rem;
  font-weight: 700;
  color: #3fb950;
}
.wdc-amount {
  font-size: 1.3rem;
}
.wdc-txrow {
  display: grid;
  grid-template-columns: 1.2rem 6rem 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px solid #1a1e28;
  font-size: 0.78rem;
}
.wdc-txrow:last-child {
  border-bottom: none;
}
.wdc-dir {
  font-weight: 700;
  font-size: 0.9rem;
}
.wdc-sent .wdc-dir {
  color: #f85149;
}
.wdc-recv .wdc-dir {
  color: #3fb950;
}
.wdc-amt {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.wdc-sent .wdc-amt {
  color: #f85149;
}
.wdc-recv .wdc-amt {
  color: #3fb950;
}
.wdc-to {
  color: #8b949e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wdc-ts {
  color: #6e7681;
  font-size: 0.72rem;
  white-space: nowrap;
}
.wdc-pending {
  color: #d29922;
  font-style: italic;
}
.wdc-empty {
  color: #6e7681;
  font-style: italic;
}
</style>
