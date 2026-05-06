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
  LS_ACTIVE_AGENT,
  getLlmSettings,
  getNodeUrl,
  saveBookingCredential,
} from "../composables/useStorage.js";
import {
  hex,
  compactSigToDerBase64,
  deriveSecurePath,
  getPublicKeyHex,
  secp,
} from "../composables/useCrypto.js";

// ── Props / emit ─────────────────────────────────────────────────────────────
const props = defineProps({
  agents: Array, // all agent types from /api/agents
});
const emit = defineEmits([
  "session-rotated",
  "agent-changed",
  "credential-issued",
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
const sessionReady = computed(() => {
  const p = localStorage.getItem(LS_PRIV);
  const c = localStorage.getItem(LS_CC);
  return !!(p && c);
});

onMounted(() => {
  if (!sessionReady.value) {
    pushAgent(
      "⚠ No operator key found. " +
        'Please <a href="/key-rotation/derived-keys" target="_blank" style="color:var(--accent)">initialise your key</a> first, then reload.',
      true,
    );
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

  // Merge extracted fields
  if (data.extracted) {
    if (!extractedScope) extractedScope = {};
    for (const [k, v] of Object.entries(data.extracted)) {
      if (v != null && v !== "") extractedScope[k] = v;
    }
  }

  chatHistory.push({ role: "assistant", content: data.reply });

  // For non-general agents, search the on-chain registry in the background.
  // The dedup guard prevents re-running for the same intent.
  if (currentAgentId.value && currentAgentId.value !== "general") {
    discoverAndPushAgents(prompt, currentAgentId.value);
  }

  if (data.complete && extractedScope && Object.keys(extractedScope).length) {
    // Show the reply + scope summary inline as an HTML message
    const scopeLines = Object.entries(extractedScope)
      .map(([k, v]) => {
        const val = Array.isArray(v)
          ? v.map((s) => `<strong>${escHtml(s)}</strong>`).join(", ")
          : `<strong>${escHtml(String(v))}</strong>`;
        return `${escHtml(k.replace(/_/g, " "))}: ${val}`;
      })
      .join("<br>");

    const summaryMsg = pushAgent(
      escHtml(data.reply) +
        `<br><br>${scopeLines}<br><br>` +
        `To proceed I'll broadcast a rotation transaction committing this scope on-chain as a ` +
        `W3C Verifiable Credential. Please enter your second factor to approve.`,
      true,
    );

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

// ── Approval handler (called from App.vue overlay) ────────────────────────────
// Exposed so parent can invoke from ApprovalCard emit
async function runApprovalFlow(
  scope,
  agentType,
  { secondFactor, paymentMethod },
  onStep,
  onDone,
) {
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
  } catch (e) {
    onStep("Rotation failed: " + e.message, "fail");
    onDone(false, "Rotation failed: " + e.message);
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
      (errorLines ? errorLines + "<br>" : "") +
      `Scope on-chain: <code>${txSnippet}</code>`;
    onDone(true, summaryHtml.trim() || "Scope committed. Continuing below…");

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
        `✅ <strong>All services booked!</strong><br><br>${resultLines}<br><br>Scope on-chain: <code>${txSnippet}</code>`,
      );
    } else if (anyOk) {
      onDone(
        true,
        `⚠️ <strong>Partial success</strong><br><br>${resultLines}<br><br>Scope on-chain: <code>${txSnippet}</code>`,
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

defineExpose({ runApprovalFlow, messages, busy });
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
