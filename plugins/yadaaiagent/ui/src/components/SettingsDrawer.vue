<template>
  <div class="settings-drawer" :class="{ open: modelValue }">
    <div class="drawer-inner">
      <h2>Settings</h2>

      <section>
        <h3>YadaCoin Node</h3>
        <div class="field-group">
          <label>Node URL</label>
          <input
            v-model="nodeUrl"
            type="text"
            placeholder="http://localhost:8001"
          />
          <div class="hint">
            Leave empty to use same-origin (Vite proxy in dev, Tornado in prod).
            Set to <code>http://localhost:8001</code> when running the Vite dev
            server to bypass the proxy.
          </div>
        </div>
      </section>

      <section>
        <h3>LLM Provider</h3>
        <div class="field-group">
          <label>Provider</label>
          <select v-model="form.provider" @change="onProviderChange">
            <option value="ollama">Ollama (local)</option>
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="github_models">GitHub Models</option>
            <option value="openai_compat">OpenAI-compatible (custom)</option>
          </select>
        </div>
        <div class="field-group" v-if="form.provider === 'ollama'">
          <label>Ollama host</label>
          <input
            v-model="form.ollama_host"
            type="text"
            placeholder="http://127.0.0.1:11434"
          />
          <div class="hint">
            Use <code>http://127.0.0.1:11434</code> (not
            <code>localhost</code>) to avoid IPv6 resolution issues.<br /><br />
            <strong>⚠ Remote node detected:</strong> if this UI is served from a
            node that is not running on your local machine (e.g. a VPS or
            yadacoin.io), the node cannot reach your local Ollama directly. You
            must expose it with
            <a href="https://ngrok.com/download" target="_blank" rel="noopener"
              >ngrok</a
            >
            (free tier is sufficient) and paste the tunnel URL here.<br /><br />
            <strong>macOS / Linux</strong><br />
            <code>brew install ngrok</code> &nbsp;or&nbsp;
            <code
              >curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo
              tee /etc/apt/trusted.gpg.d/ngrok.asc &gt;/dev/null &amp;&amp; echo
              "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee
              /etc/apt/sources.list.d/ngrok.list &amp;&amp; sudo apt install
              ngrok</code
            ><br />
            Then: <code>ngrok http 11434</code> — copy the
            <code>https://…ngrok-free.app</code> URL into this field.<br /><br />
            <strong>Windows</strong><br />
            Download the installer from
            <a href="https://ngrok.com/download" target="_blank" rel="noopener"
              >ngrok.com/download</a
            >, run it, authenticate with <code>ngrok config add-authtoken
            &lt;token&gt;</code>, then run
            <code>ngrok http 11434</code> in a terminal and paste the HTTPS URL
            here.<br /><br />
            Run <code>ollama list</code> to see available models.
          </div>
        </div>
        <div class="field-group" v-if="form.provider === 'openai_compat'">
          <label>Base URL</label>
          <input
            v-model="form.base_url"
            type="text"
            placeholder="https://api.example.com/v1"
          />
        </div>
        <div class="field-group">
          <label>Model</label>
          <input
            v-model="form.model"
            type="text"
            :placeholder="modelPlaceholder"
          />
          <div class="hint" v-html="modelHint"></div>
        </div>
        <div class="field-group" v-if="form.provider !== 'ollama'">
          <label>API Key</label>
          <input
            v-model="form.api_key"
            type="password"
            :placeholder="
              form.provider === 'github_models'
                ? 'GitHub PAT (github_pat_…)'
                : 'sk-…'
            "
            autocomplete="off"
          />
          <div class="hint" v-if="form.provider === 'github_models'">
            Use a GitHub personal access token with
            <strong>Models</strong> access. Stored in localStorage only — never
            sent to the YadaCoin server.
          </div>
          <div class="hint" v-else>
            Stored in localStorage only — never sent to the YadaCoin server.
          </div>
        </div>
      </section>

      <section>
        <h3>Web Search (Brave)</h3>
        <div class="field-group">
          <label>Brave Search API Key</label>
          <input
            v-model="braveApiKey"
            type="password"
            placeholder="BSA…"
            autocomplete="off"
          />
          <div class="hint">
            Enables real-time web search in the General Chat agent. Get a free
            key at
            <a
              href="https://brave.com/search/api/"
              target="_blank"
              rel="noopener"
              >brave.com/search/api</a
            >. Stored in localStorage.
            <strong
              >⚠ This key is sent to the YadaCoin node with each search
              request</strong
            >
            so the server can call Brave on your behalf. If you are using a
            shared or public node (e.g. yadacoin.io), the node operator can see
            your API key. Use a dedicated key or run your own node if that is a
            concern.
          </div>
        </div>
      </section>

      <section>
        <h3>Wallet Mode</h3>
        <div class="field-group">
          <label>Active mode</label>
          <select v-model="walletMode">
            <option value="node">Node Wallet (server-managed key)</option>
            <option value="client">Personal Wallet (client-side seed)</option>
            <option value="hardware">
              Hardware Wallet (air-gapped device)
            </option>
          </select>
          <div class="hint">
            <strong>Node Wallet</strong> — your node derives and stores your
            key.<br />
            <strong>Personal Wallet</strong> — you hold your own BIP39 seed; all
            rotations happen in the browser.<br />
            <strong>Hardware Wallet</strong> — every approval requires scanning
            QR codes from an air-gapped device. Private keys never touch this
            browser.
          </div>
        </div>
        <div v-if="walletMode === 'client' && hasClientKey" class="pm-list">
          <div class="pm-item">
            <span
              class="pm-label"
              style="font-family: monospace; font-size: 0.8em"
              >{{ clientKeyPreview }}</span
            >
            <span class="pm-action remove" @click="resetClientWallet"
              >reset wallet</span
            >
          </div>
        </div>
        <div v-if="walletMode === 'hardware' && hasHardwarePub" class="pm-list">
          <div class="pm-item">
            <span
              class="pm-label"
              style="font-family: monospace; font-size: 0.8em"
              >📟 {{ hardwarePubPreview }}</span
            >
            <span class="pm-action remove" @click="resetClientWallet"
              >unpair device</span
            >
          </div>
        </div>
        <div
          v-if="walletMode === 'client' && !hasClientKey"
          class="hint"
          style="color: var(--accent2)"
        >
          No key found — click the session pill to set up your personal wallet.
        </div>
        <div
          v-if="walletMode === 'hardware' && !hasHardwarePub"
          class="hint"
          style="color: var(--accent2)"
        >
          No device paired — click the session pill to scan your hardware
          wallet's QR.
        </div>
      </section>

      <section>
        <div class="pm-list">
          <div v-if="!paymentMethods.length" class="pm-empty">
            No payment methods saved.
          </div>
          <div
            v-for="(pm, i) in paymentMethods"
            :key="pm.token"
            class="pm-item"
          >
            <span class="pm-label">{{ pm.label }}</span>
            <span v-if="pm.isDefault" class="pm-badge">default</span>
            <span v-else class="pm-action" @click="setDefault(i)"
              >set default</span
            >
            <span class="pm-action remove" @click="removePm(i)">remove</span>
          </div>
        </div>
        <div class="pm-add-row">
          <input
            v-model="newPmLabel"
            type="text"
            placeholder="e.g. Visa ending in 4242"
            @keydown.enter="addPm"
          />
          <button class="pm-add-btn" @click="addPm">+ Add</button>
        </div>
        <div class="hint">
          A mock token is committed in the VC — raw card details never leave the
          browser.
        </div>
      </section>

      <div class="btn-row">
        <button class="btn-save" @click="save">Save</button>
        <button class="btn-close" @click="close">Close</button>
        <span v-if="savedMsg" class="saved-msg">✓ Saved</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import {
  getLlmSettings,
  saveLlmSettings,
  getPaymentMethods,
  savePaymentMethods,
  getNodeUrl,
  getBraveApiKey,
  saveBraveApiKey,
  LS_NODE_URL,
  LS_PRIV,
  LS_HW_PUB,
  getWalletMode,
  setWalletMode,
  clearClientWallet,
} from "../composables/useStorage.js";
import { getPublicKeyHex, hex } from "../composables/useCrypto.js";

const props = defineProps({ modelValue: Boolean });
const emit = defineEmits(["update:modelValue", "wallet-mode-changed"]);

const form = ref({ ...getLlmSettings() });
const nodeUrl = ref(getNodeUrl());
const paymentMethods = ref(getPaymentMethods());
const braveApiKey = ref(getBraveApiKey());
const newPmLabel = ref("");
const savedMsg = ref(false);
const walletMode = ref(getWalletMode());

const hasClientKey = computed(() => !!localStorage.getItem(LS_PRIV));
const hasHardwarePub = computed(() => !!localStorage.getItem(LS_HW_PUB));
const hardwarePubPreview = computed(() => {
  const pub = localStorage.getItem(LS_HW_PUB);
  return pub ? pub.slice(0, 20) + "\u2026" : "";
});
const clientKeyPreview = computed(() => {
  const priv = localStorage.getItem(LS_PRIV);
  if (!priv) return "";
  try {
    const pub = getPublicKeyHex(hex.toBytes(priv));
    return "\uD83D\uDD11 " + pub.slice(0, 20) + "…";
  } catch {
    return "(invalid key)";
  }
});

function resetClientWallet() {
  if (
    !confirm(
      "This will delete your local key. Make sure you have your seed phrase. Continue?",
    )
  )
    return;
  clearClientWallet();
  walletMode.value = "node";
  emit("wallet-mode-changed");
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      form.value = { ...getLlmSettings() };
      nodeUrl.value = getNodeUrl();
      paymentMethods.value = getPaymentMethods();
      braveApiKey.value = getBraveApiKey();
      walletMode.value = getWalletMode();
    }
  },
);

const MODEL_HINTS = {
  ollama: "Default: llama3.2",
  openai: "e.g. gpt-4o, gpt-4o-mini, gpt-3.5-turbo",
  anthropic: "e.g. claude-3-5-sonnet-20241022, claude-3-haiku-20240307",
  openai_compat: "Enter the model name your provider expects.",
  github_models:
    "⚠️ GitHub Models is rate-limited to ~2 req/min regardless of your Copilot subscription — " +
    "not suitable for demos. For reliable demos use <strong>OpenAI</strong> (gpt-4o-mini) " +
    "or <strong>Ollama</strong> locally. If you must use GitHub Models, try: " +
    "<code>gpt-4.1-mini</code>, <code>Meta-Llama-3.1-70B-Instruct</code>, <code>Mistral-Nemo</code>.",
};
const MODEL_PLACEHOLDERS = {
  ollama: "llama3.2",
  openai: "gpt-4o-mini",
  anthropic: "claude-3-haiku-20240307",
  openai_compat: "gpt-3.5-turbo",
  github_models: "gpt-4.1-mini",
};
const modelHint = computed(() => MODEL_HINTS[form.value.provider] || "");
const modelPlaceholder = computed(
  () => MODEL_PLACEHOLDERS[form.value.provider] || "",
);

function onProviderChange() {
  form.value.model = "";
}
function close() {
  emit("update:modelValue", false);
}

function save() {
  saveLlmSettings(form.value);
  localStorage.setItem(LS_NODE_URL, nodeUrl.value.trim().replace(/\/+$/, ""));
  saveBraveApiKey(braveApiKey.value);
  setWalletMode(walletMode.value);
  emit("wallet-mode-changed");
  savedMsg.value = true;
  setTimeout(() => {
    savedMsg.value = false;
  }, 2000);
}

function addPm() {
  const label = newPmLabel.value.trim();
  if (!label) return;
  const token = "demo_tok_" + Math.random().toString(36).slice(2, 10);
  const methods = getPaymentMethods();
  methods.push({ id: token, label, token, isDefault: methods.length === 0 });
  savePaymentMethods(methods);
  paymentMethods.value = getPaymentMethods();
  newPmLabel.value = "";
}

function setDefault(idx) {
  const methods = getPaymentMethods().map((pm, i) => ({
    ...pm,
    isDefault: i === idx,
  }));
  savePaymentMethods(methods);
  paymentMethods.value = getPaymentMethods();
}

function removePm(idx) {
  let methods = getPaymentMethods().filter((_, i) => i !== idx);
  if (methods.length && !methods.some((p) => p.isDefault))
    methods[0].isDefault = true;
  savePaymentMethods(methods);
  paymentMethods.value = getPaymentMethods();
}
</script>

<style scoped>
.settings-drawer {
  display: none;
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.4);
}
.settings-drawer.open {
  display: block;
}
.drawer-inner {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 340px;
  background: var(--surface);
  border-left: 1px solid var(--border);
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
h2 {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.07em;
}
section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
section h3 {
  font-size: 0.78rem;
  color: var(--subtext);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border);
  padding-bottom: 4px;
}
.field-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field-group label {
  font-size: 0.75rem;
  color: var(--subtext);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.field-group select,
.field-group input {
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 10px;
  font-size: 0.84rem;
  font-family: inherit;
  width: 100%;
}
.field-group select:focus,
.field-group input:focus {
  outline: none;
  border-color: var(--accent);
}
.hint {
  font-size: 0.72rem;
  color: var(--muted);
  line-height: 1.4;
}
.pm-list {
  display: flex;
  flex-direction: column;
}
.pm-empty {
  font-size: 0.8rem;
  color: var(--muted);
  padding: 4px 0;
}
.pm-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.82rem;
}
.pm-item:last-child {
  border-bottom: none;
}
.pm-label {
  flex: 1;
  color: var(--text);
}
.pm-badge {
  font-size: 0.68rem;
  padding: 1px 6px;
  border-radius: 999px;
  background: #1e3a1e;
  color: var(--green2);
  border: 1px solid #16a34a;
  white-space: nowrap;
}
.pm-action {
  cursor: pointer;
  font-size: 0.72rem;
  text-decoration: underline;
  color: var(--subtext);
}
.pm-action.remove {
  color: var(--red2);
}
.pm-add-row {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}
.pm-add-row input {
  flex: 1;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 0.82rem;
}
.pm-add-btn {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 0.82rem;
  cursor: pointer;
  white-space: nowrap;
}
.pm-add-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.btn-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: auto;
}
.btn-save {
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-weight: 700;
  font-size: 0.84rem;
  cursor: pointer;
}
.btn-save:hover {
  background: var(--accent2);
}
.btn-close {
  background: none;
  border: 1px solid var(--border);
  color: var(--subtext);
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 0.84rem;
  cursor: pointer;
}
.btn-close:hover {
  border-color: var(--red);
  color: var(--red2);
}
.saved-msg {
  font-size: 0.78rem;
  color: var(--green2);
}
</style>
