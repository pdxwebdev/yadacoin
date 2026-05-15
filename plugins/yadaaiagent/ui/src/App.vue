<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand">
        <span class="brand-icon">&#11047;</span>
        <span class="name">YadaCoin <strong>AI Agent</strong></span>
      </div>
      <div class="header-center">
        <span class="header-agent-name" v-if="activeAgent">
          {{ activeAgent.icon }} {{ activeAgent.label }}
        </span>
      </div>
      <div class="header-right">
        <div
          class="session-pill"
          :class="sessionPillClass"
          :style="
            !sessionPubHex &&
            (getWalletMode() === 'client' || getWalletMode() === 'hardware')
              ? 'cursor:pointer'
              : ''
          "
          @click="
            !sessionPubHex &&
            (getWalletMode() === 'client' || getWalletMode() === 'hardware')
              ? (showWalletSetup = true)
              : null
          "
        >
          {{ sessionPillText }}
        </div>
        <button
          class="icon-btn"
          title="Credential Wallet"
          @click="showWallet = true"
        >
          &#127760;
          <span v-if="credentialCount" class="wallet-badge">{{
            credentialCount
          }}</span>
        </button>
        <button class="icon-btn" title="Settings" @click="showSettings = true">
          &#9881;
        </button>
      </div>
    </header>

    <div class="body">
      <main class="main">
        <ChatPane
          ref="chatPaneRef"
          :agents="agents"
          @agent-changed="onAgentChanged"
          @session-rotated="onSessionRotated"
          @credential-issued="onCredentialIssued"
          @setup-wallet="showWalletSetup = true"
        />
        <div v-if="approvalState" class="approval-overlay">
          <div class="approval-wrap">
            <ApprovalCard
              :agent-type="approvalState.agentType"
              :scope="approvalState.scope"
              @approve="onApprove"
              @deny="onDeny"
            />
            <div v-if="approvalSteps.length" class="steps">
              <div
                v-for="(step, i) in approvalSteps"
                :key="i"
                class="step"
                :class="step.state"
              >
                {{ step.text }}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>

    <SettingsDrawer
      v-model="showSettings"
      @wallet-mode-changed="onWalletModeChanged"
    />
    <CredentialWallet v-model="showWallet" :key="walletKey" />
    <WalletSetup
      v-if="showWalletSetup"
      @done="onWalletSetupDone"
      @close="onWalletSetupClose"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from "vue";
import ChatPane from "./components/ChatPane.vue";
import ApprovalCard from "./components/ApprovalCard.vue";
import SettingsDrawer from "./components/SettingsDrawer.vue";
import CredentialWallet from "./components/CredentialWallet.vue";
import WalletSetup from "./components/WalletSetup.vue";
import {
  LS_PRIV,
  LS_HW_PUB,
  LS_WALLET_MODE,
  getNodeUrl,
  getBookingCredentials,
  getWalletMode,
  setWalletMode,
} from "./composables/useStorage.js";
import { getPublicKeyHex, hex } from "./composables/useCrypto.js";

// ── Synchronous fresh-start default ──────────────────────────────────────────
// Runs during parent setup(), BEFORE any child component mounts.
// This ensures ChatPane.vue reads the correct mode in its own onMounted.
if (!localStorage.getItem(LS_WALLET_MODE) && !localStorage.getItem(LS_PRIV)) {
  setWalletMode("client");
}

const agents = ref([]);
const activeAgent = ref(null);

onMounted(async () => {
  // Show wallet setup modal when in client mode with no key stored, or in
  // hardware mode with no device paired yet.
  const mode = getWalletMode();
  if (mode === "client" && !localStorage.getItem(LS_PRIV)) {
    showWalletSetup.value = true;
  } else if (mode === "hardware" && !localStorage.getItem(LS_HW_PUB)) {
    showWalletSetup.value = true;
  }

  try {
    const res = await fetch(`${getNodeUrl()}/ai-agent-auth/api/agents`);
    if (res.ok) {
      const data = await res.json();
      agents.value = Array.isArray(data) ? data : [];
    }
  } catch {}
  refreshSessionPill();
});

function onAgentChanged(agentObj) {
  activeAgent.value = agentObj;
}

const showSettings = ref(false);
const showWallet = ref(false);
const showWalletSetup = ref(false);
const walletKey = ref(0); // force reload when credential-issued
const credentialCount = ref(getBookingCredentials().length);

function onCredentialIssued() {
  credentialCount.value = getBookingCredentials().length;
  walletKey.value++;
}

const sessionPubHex = ref("");
function refreshSessionPill() {
  const mode = getWalletMode();
  if (mode === "hardware") {
    sessionPubHex.value = localStorage.getItem(LS_HW_PUB) || "";
    return;
  }
  const priv = localStorage.getItem(LS_PRIV);
  if (!priv) {
    sessionPubHex.value = "";
    return;
  }
  try {
    sessionPubHex.value = getPublicKeyHex(hex.toBytes(priv));
  } catch {
    sessionPubHex.value = "error";
  }
}
function onSessionRotated() {
  refreshSessionPill();
}

const sessionPillClass = computed(() => (sessionPubHex.value ? "ok" : "bad"));
const sessionPillText = computed(() => {
  const mode = getWalletMode();
  if (sessionPubHex.value) {
    const prefix =
      mode === "client"
        ? "\uD83D\uDC64"
        : mode === "hardware"
          ? "\uD83D\uDCDF"
          : "\uD83D\uDD13";
    return prefix + " " + sessionPubHex.value.slice(0, 16) + "...";
  }
  if (mode === "client") return "Setup wallet";
  if (mode === "hardware") return "Pair hardware wallet";
  return "No key \u2014 /key-rotation";
});

const approvalState = ref(null);
const approvalSteps = ref([]);
const chatPaneRef = ref(null);

watch(
  () => chatPaneRef.value?.messages,
  (msgs) => {
    if (!msgs) return;
    const pending = msgs.find((m) => m.showApproval && !m._approvalHandled);
    if (pending) {
      pending._approvalHandled = true;
      approvalState.value = pending.approvalContext;
    }
  },
  { deep: true },
);

async function onApprove(payload) {
  if (!approvalState.value || !chatPaneRef.value) return;
  const { scope, agentType } = approvalState.value;
  approvalSteps.value = [];

  function onStep(text, state) {
    state = state || "pending";
    if (
      approvalSteps.value.length &&
      approvalSteps.value[approvalSteps.value.length - 1].state === "pending"
    ) {
      approvalSteps.value[approvalSteps.value.length - 1].state = state;
    }
    approvalSteps.value.push({ text: text, state: "pending" });
  }

  function onDone(success, html) {
    if (approvalSteps.value.length) {
      approvalSteps.value[approvalSteps.value.length - 1].state = success
        ? "done"
        : "fail";
    }
    setTimeout(function () {
      approvalState.value = null;
      approvalSteps.value = [];
      if (chatPaneRef.value && html)
        chatPaneRef.value.messages.push({
          role: "agent",
          html: html,
          content: "",
        });
    }, 600);
  }

  await chatPaneRef.value.runApprovalFlow(
    scope,
    agentType,
    payload,
    onStep,
    onDone,
  );
}

function onWalletModeChanged() {
  refreshSessionPill();
}

function onWalletSetupDone() {
  showWalletSetup.value = false;
  refreshSessionPill();
  chatPaneRef.value?.notifyWalletReady();
}

function onWalletSetupClose() {
  showWalletSetup.value = false;
  // If the user dismissed the modal *after* a wallet was actually set up
  // (e.g. they completed Generate/Import/Recover but skipped LLM config),
  // refresh the session pill and notify ChatPane so the "No wallet found"
  // warning is replaced with the normal greeting.
  refreshSessionPill();
  const mode = getWalletMode();
  const hasKey =
    (mode === "client" && !!localStorage.getItem(LS_PRIV)) ||
    (mode === "hardware" && !!localStorage.getItem(LS_HW_PUB));
  if (hasKey) chatPaneRef.value?.notifyWalletReady();
}

function onDeny() {
  approvalState.value = null;
  approvalSteps.value = [];
  if (chatPaneRef.value) {
    chatPaneRef.value.messages.push({
      role: "agent",
      content: "Booking cancelled.",
    });
    chatPaneRef.value.busy = false;
  }
}
</script>

<style>
:root {
  --bg: #0a0c12;
  --surface: #111420;
  --border: #1e2133;
  --text: #d1d5db;
  --subtext: #6b7280;
  --muted: #4b5563;
  --accent: #7c3aed;
  --accent2: #a78bfa;
  --user-bg: #2e1a4a;
  --agent-bg: #111420;
  --green: #22c55e;
  --green2: #4ade80;
  --red: #dc2626;
  --red2: #f87171;
}
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}
html,
body {
  height: 100%;
  overflow: hidden;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
}
#app {
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.typing {
  display: flex;
  gap: 5px;
  align-items: center;
  padding: 2px 0;
}
.typing span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent2);
  animation: bounce 1.2s infinite;
  display: inline-block;
}
.typing span:nth-child(2) {
  animation-delay: 0.2s;
}
.typing span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes bounce {
  0%,
  80%,
  100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1.2);
    opacity: 1;
  }
}
</style>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}
.app-header {
  display: flex;
  align-items: center;
  padding: 0 16px;
  height: 52px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  gap: 12px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.brand-icon {
  font-size: 1.4rem;
  color: var(--accent);
}
.name {
  font-size: 0.88rem;
  color: var(--subtext);
  white-space: nowrap;
}
.name strong {
  color: var(--accent2);
}
.header-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.top-nav {
  display: flex;
  gap: 4px;
}
.top-nav-btn {
  background: none;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--subtext);
  cursor: pointer;
  font-size: 0.78rem;
  padding: 3px 10px;
  transition: all 0.15s;
}
.top-nav-btn.active {
  background: rgba(124, 58, 237, 0.18);
  border-color: rgba(124, 58, 237, 0.4);
  color: var(--accent2);
}
.top-nav-btn:hover:not(.active) {
  color: var(--text);
  border-color: var(--border);
}
.header-agent-name {
  font-size: 0.88rem;
  color: var(--subtext);
  font-weight: 500;
}
.header-agent-name:empty {
  display: none;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.session-pill {
  font-size: 0.72rem;
  padding: 3px 10px;
  border-radius: 999px;
  font-weight: 600;
  white-space: nowrap;
}
.session-pill.ok {
  background: #1a2e1a;
  color: var(--green2);
  border: 1px solid #16a34a;
}
.session-pill.bad {
  background: #2e1a1a;
  color: var(--red2);
  border: 1px solid var(--red);
}
.icon-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--subtext);
  border-radius: 6px;
  width: 32px;
  height: 32px;
  font-size: 1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.icon-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.wallet-badge {
  position: absolute;
  top: -5px;
  right: -5px;
  background: var(--accent);
  color: #fff;
  border-radius: 999px;
  font-size: 9px;
  min-width: 16px;
  height: 16px;
  line-height: 16px;
  text-align: center;
  padding: 0 3px;
  pointer-events: none;
}
.body {
  display: flex;
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
}
.sidebar {
  display: none;
}
.main {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  position: relative;
}
.approval-overlay {
  position: absolute;
  inset: 0;
  background: rgba(10, 12, 18, 0.85);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 16px;
  z-index: 50;
}
.approval-wrap {
  background: var(--surface);
  border: 1px solid var(--accent);
  border-radius: 12px;
  padding: 16px;
  width: 100%;
  max-width: 540px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 80vh;
  overflow-y: auto;
}
.steps {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
}
.step {
  font-size: 0.77rem;
  color: var(--subtext);
  padding: 2px 0 2px 10px;
  border-left: 2px solid var(--border);
}
.step.done {
  color: var(--green2);
  border-color: #16a34a;
}
.step.fail {
  color: var(--red2);
  border-color: var(--red);
}
.step.pending {
  color: var(--accent2);
  border-color: var(--accent);
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
