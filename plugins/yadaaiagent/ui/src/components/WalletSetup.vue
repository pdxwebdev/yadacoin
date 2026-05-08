<template>
  <div class="wallet-setup-overlay" @click.self="close">
    <div class="wallet-setup-modal">
      <div class="ws-header">
        <h2>Personal Wallet Setup</h2>
        <p class="ws-subtitle">
          Your seed phrase never leaves this browser. All key rotations happen
          client-side.
        </p>
      </div>

      <!-- Tab selector -->
      <div class="ws-tabs">
        <button
          :class="['ws-tab', tab === 'generate' ? 'active' : '']"
          @click="
            tab = 'generate';
            resetState();
          "
        >
          Generate New Wallet
        </button>
        <button
          :class="['ws-tab', tab === 'import' ? 'active' : '']"
          @click="
            tab = 'import';
            resetState();
          "
        >
          Import Existing Seed
        </button>
      </div>

      <!-- Generate tab -->
      <div v-if="tab === 'generate'" class="ws-body">
        <div v-if="!mnemonicWords.length">
          <p class="ws-info">
            Click <strong>Generate</strong> to create a new 12-word seed phrase.
            Write it down and keep it safe — it cannot be recovered if lost.
          </p>
          <button class="ws-btn primary" @click="doGenerate">
            Generate Seed Phrase
          </button>
        </div>

        <div v-else>
          <p class="ws-warn">
            ⚠️ Write these words down in order and store them securely.
          </p>
          <div class="mnemonic-grid">
            <div
              v-for="(word, i) in mnemonicWords"
              :key="i"
              class="mnemonic-word"
            >
              <span class="word-num">{{ i + 1 }}</span>
              <span class="word-val">{{ word }}</span>
            </div>
          </div>

          <div class="ws-field">
            <label>Second Factor (password)</label>
            <input
              v-model="secondFactor"
              type="password"
              placeholder="Choose a strong password"
              autocomplete="new-password"
            />
            <div class="ws-hint">
              This password is required for every key rotation. Store it
              alongside your seed phrase.
            </div>
          </div>
          <div class="ws-field">
            <label>Confirm Second Factor</label>
            <input
              v-model="secondFactorConfirm"
              type="password"
              placeholder="Re-enter password"
              autocomplete="new-password"
              @keydown.enter="doSetup"
            />
          </div>

          <div v-if="error" class="ws-error">{{ error }}</div>

          <div class="ws-btn-row">
            <button class="ws-btn secondary" @click="mnemonicWords = []">
              Regenerate
            </button>
            <button class="ws-btn primary" :disabled="busy" @click="doSetup">
              {{ busy ? "Setting up…" : "Set Up Wallet" }}
            </button>
          </div>
        </div>
      </div>

      <!-- Import tab -->
      <div v-else class="ws-body">
        <div class="ws-field">
          <label>Seed Phrase (12 or 24 words)</label>
          <textarea
            v-model="importPhrase"
            placeholder="Enter your seed phrase words separated by spaces"
            rows="3"
            autocomplete="off"
            spellcheck="false"
          ></textarea>
          <div v-if="importPhrase.trim() && !phraseValid" class="ws-error">
            Invalid seed phrase — check spelling and word count.
          </div>
        </div>

        <div class="ws-field">
          <label>Second Factor (password)</label>
          <input
            v-model="secondFactor"
            type="password"
            placeholder="Password used when this wallet was created"
            autocomplete="current-password"
            @keydown.enter="doSetup"
          />
        </div>

        <div v-if="error" class="ws-error">{{ error }}</div>

        <div class="ws-btn-row">
          <button
            class="ws-btn primary"
            :disabled="busy || !phraseValid || !secondFactor"
            @click="doSetup"
          >
            {{ busy ? "Importing…" : "Import Wallet" }}
          </button>
        </div>
      </div>

      <button class="ws-close" @click="close">✕</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import {
  generateNewMnemonic,
  isValidMnemonic,
  initClientWallet,
  submitInceptionTransaction,
} from "../composables/useBip39.js";

const emit = defineEmits(["done", "close"]);

const tab = ref("generate");
const mnemonicWords = ref([]);
const importPhrase = ref("");
const secondFactor = ref("");
const secondFactorConfirm = ref("");
const error = ref("");
const busy = ref(false);

const phraseValid = computed(() =>
  importPhrase.value.trim()
    ? isValidMnemonic(importPhrase.value.trim())
    : false,
);

function resetState() {
  mnemonicWords.value = [];
  importPhrase.value = "";
  secondFactor.value = "";
  secondFactorConfirm.value = "";
  error.value = "";
}

function doGenerate() {
  const phrase = generateNewMnemonic();
  mnemonicWords.value = phrase.split(" ");
  secondFactor.value = "";
  secondFactorConfirm.value = "";
  error.value = "";
}

async function doSetup() {
  error.value = "";
  const phrase =
    tab.value === "generate"
      ? mnemonicWords.value.join(" ")
      : importPhrase.value.trim();

  if (!phrase) {
    error.value = "No seed phrase provided.";
    return;
  }
  if (!isValidMnemonic(phrase)) {
    error.value = "Invalid seed phrase.";
    return;
  }
  if (!secondFactor.value) {
    error.value = "Second factor is required.";
    return;
  }
  if (
    tab.value === "generate" &&
    secondFactor.value !== secondFactorConfirm.value
  ) {
    error.value = "Passwords do not match.";
    return;
  }

  busy.value = true;
  try {
    const k0 = await initClientWallet(phrase, secondFactor.value);
    await submitInceptionTransaction(k0, secondFactor.value);
    emit("done");
  } catch (e) {
    error.value = "Setup failed: " + String(e);
  } finally {
    busy.value = false;
  }
}

function close() {
  emit("close");
}
</script>

<style scoped>
.wallet-setup-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.wallet-setup-modal {
  position: relative;
  background: var(--surface2, #1e1e2e);
  border: 1px solid var(--border, #333);
  border-radius: 12px;
  padding: 32px;
  max-width: 520px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.6);
}

.ws-header h2 {
  margin: 0 0 6px;
  font-size: 1.3rem;
  color: var(--text, #e0e0e0);
}

.ws-subtitle {
  margin: 0 0 20px;
  font-size: 0.85rem;
  color: var(--text2, #999);
}

.ws-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.ws-tab {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border, #444);
  background: transparent;
  color: var(--text2, #aaa);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.15s;
}

.ws-tab.active,
.ws-tab:hover {
  background: var(--accent, #7c6af7);
  color: #fff;
  border-color: var(--accent, #7c6af7);
}

.ws-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ws-info {
  color: var(--text2, #aaa);
  font-size: 0.9rem;
  line-height: 1.5;
}

.ws-warn {
  color: #e0a060;
  font-size: 0.85rem;
  padding: 8px 12px;
  background: rgba(224, 160, 96, 0.1);
  border: 1px solid rgba(224, 160, 96, 0.3);
  border-radius: 6px;
}

.mnemonic-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 12px 0;
}

.mnemonic-word {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--surface3, #2a2a3e);
  border: 1px solid var(--border, #333);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 0.85rem;
}

.word-num {
  color: var(--text3, #666);
  font-size: 0.75rem;
  min-width: 18px;
}

.word-val {
  color: var(--text, #e0e0e0);
  font-family: monospace;
}

.ws-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ws-field label {
  font-size: 0.8rem;
  color: var(--text2, #999);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.ws-field input,
.ws-field textarea {
  background: var(--input-bg, #12121e);
  border: 1px solid var(--border, #333);
  border-radius: 6px;
  color: var(--text, #e0e0e0);
  padding: 8px 12px;
  font-size: 0.9rem;
  font-family: inherit;
  resize: vertical;
  outline: none;
}

.ws-field input:focus,
.ws-field textarea:focus {
  border-color: var(--accent, #7c6af7);
}

.ws-hint {
  font-size: 0.78rem;
  color: var(--text3, #666);
  line-height: 1.4;
}

.ws-error {
  color: var(--red2, #e06060);
  font-size: 0.85rem;
  padding: 6px 10px;
  background: rgba(224, 96, 96, 0.1);
  border-radius: 4px;
}

.ws-btn-row {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 8px;
}

.ws-btn {
  padding: 8px 20px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: opacity 0.15s;
}

.ws-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.ws-btn.primary {
  background: var(--accent, #7c6af7);
  color: #fff;
}

.ws-btn.secondary {
  background: var(--surface3, #2a2a3e);
  color: var(--text, #e0e0e0);
  border: 1px solid var(--border, #444);
}

.ws-close {
  position: absolute;
  top: 16px;
  right: 16px;
  background: transparent;
  border: none;
  color: var(--text2, #aaa);
  font-size: 1rem;
  cursor: pointer;
  padding: 4px;
  line-height: 1;
}

.ws-close:hover {
  color: var(--text, #e0e0e0);
}
</style>
