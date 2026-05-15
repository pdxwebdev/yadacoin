<template>
  <div class="loc-setup">
    <div class="header">
      <h3>
        {{
          existingMnemonic
            ? "Add Location Recovery"
            : "Create Wallet from Locations"
        }}
      </h3>
      <p class="hint">
        Pick {{ LOCATION_COUNT }} meaningful places on the map and give each a
        private hint. Your wallet seed phrase will be encrypted with a key
        derived from these locations — coordinates never leave your device.
      </p>
    </div>

    <div class="progress-row">
      <span
        v-for="i in LOCATION_COUNT"
        :key="i"
        class="dot"
        :class="{
          done: i - 1 < locations.length,
          active: i - 1 === locations.length,
        }"
      />
    </div>

    <p v-if="locations.length < LOCATION_COUNT" class="step-label">
      Location {{ locations.length + 1 }} of {{ LOCATION_COUNT }}: tap the map
      to zoom in, then select a grid cell.
    </p>

    <div v-if="pendingPin" class="hint-row">
      <input
        ref="hintInputEl"
        v-model="pendingHint"
        class="input"
        placeholder="Private hint (only you will see this)"
        maxlength="80"
        @keyup.enter="confirmPin"
      />
      <button class="btn primary" @click="confirmPin">Add</button>
      <button class="btn secondary" @click="cancelPin">Cancel</button>
    </div>

    <Map
      v-if="locations.length < LOCATION_COUNT"
      ref="mapEl"
      :center="mapCenter"
      :zoom="initialZoom"
      :precision="4"
      :map-container-style="{
        width: '100%',
        height: '300px',
        borderRadius: '10px',
        overflow: 'hidden',
        border: '1px solid var(--border, #333)',
      }"
      v-model:selected-location="selectedLocation"
      v-model:selected-square-id="selectedSquareId"
      v-model:hover-index="hoverIndex"
      @grid-square-clicked="onGridSquareClicked"
    />
    <p v-if="locations.length < LOCATION_COUNT" class="map-hint">
      Tap the map to zoom in. When the grid appears, click a cell to pin a
      location.
    </p>

    <ul v-if="locations.length" class="loc-list">
      <li v-for="(loc, i) in locations" :key="i">
        <span class="loc-num">{{ i + 1 }}</span>
        <span class="loc-hint">{{ loc.hint || "(no hint)" }}</span>
        <span class="loc-coord">
          {{ loc.lat.toFixed(4) }}, {{ loc.lng.toFixed(4) }}
        </span>
        <button class="btn-remove" @click="removeLocation(i)">✕</button>
      </li>
    </ul>

    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>

    <div
      v-if="locations.length === LOCATION_COUNT && !saving && !recoveryCode"
      class="action-row"
    >
      <button class="btn primary" @click="save">
        Save &amp; Generate Recovery Code
      </button>
      <button class="btn link" @click="$emit('skip')">
        {{ existingMnemonic ? "Skip — I'll do this later" : "Cancel" }}
      </button>
    </div>

    <div
      v-if="isDev && !saving && !recoveryCode"
      style="margin-top: 12px; border-top: 1px dashed #555; padding-top: 10px"
    >
      <button
        class="btn secondary"
        style="font-size: 11px; opacity: 0.7"
        @click="devPrefill"
      >
        [DEV] Prefill test locations &amp; save
      </button>
    </div>
    <p v-if="saving" class="status">Encrypting seed phrase with locations…</p>

    <div v-if="recoveryCode" class="recovery-code-screen">
      <p class="code-label">Your Recovery Code</p>
      <div class="code-display">{{ recoveryCode }}</div>
      <p class="code-instructions">
        Write this code down and store it safely. To recover your wallet on
        another device, enter this code and re-pin your
        {{ LOCATION_COUNT }} locations — the seed phrase is decrypted locally.
      </p>
      <p class="code-note">
        The code only unlocks your hint labels stored on the node. Your seed is
        encrypted with a zero-knowledge key derived from the 3 locations — it is
        never sent to the server in plaintext.
      </p>
      <button class="btn primary" @click="emitDone">
        I've written it down →
      </button>
    </div>
  </div>
</template>

<script setup>
// Adapted from plugins/yadacoinwallet/ui/src/views/LocationRecoverySetupView.vue
// for the yadaaiagent UI. Captures three locations, encrypts the user's seed
// phrase using a witness derived from them, persists the proof+ciphertext in
// IndexedDB, and uploads short hint labels to the node so they can be looked
// up on a fresh device by recovery code.
import { ref, nextTick } from "vue";
import Map from "./Map.vue";
import {
  setupLocationRecovery,
  LOCATION_COUNT,
} from "../composables/useLocationRecovery.js";

const props = defineProps({
  // If supplied, the existing mnemonic is encrypted under the location key.
  // Otherwise a fresh BIP-39 phrase is generated and returned in `setup-complete`.
  existingMnemonic: { type: String, default: null },
  // Hex hash of the latest key log entry — bound into the Schnorr challenge.
  // Pass null until on-chain announcement/recover txns are wired up.
  prevKeyHash: { type: String, default: null },
  // Second factor password — mixed into the witness HKDF input so an attacker
  // needs both correct locations AND the password to compute the witnessHash.
  secondFactor: { type: String, default: null },
});
const emit = defineEmits(["setup-complete", "skip"]);

const mapEl = ref(null);
const hintInputEl = ref(null);
const locations = ref([]);
const pendingPin = ref(null);
const pendingHint = ref("");
const errorMsg = ref("");
const saving = ref(false);
const recoveryCode = ref("");
const derivedMnemonic = ref("");
const txnData = ref(null);

const initialZoom = 2;
const mapCenter = ref({ lat: 0, lng: 0 });
const selectedLocation = ref({ lat: 0, lng: 0, confirmed: false });
const selectedSquareId = ref("");
const hoverIndex = ref(-1);

const isDev =
  import.meta.env.DEV ||
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1";

async function devPrefill() {
  locations.value = [
    { lat: 45.5239, lng: -122.6837, hint: "asdf" },
    { lat: 45.5239, lng: -122.6837, hint: "asdf2" },
    { lat: 45.5239, lng: -122.6837, hint: "asdf3" },
  ];
  await save();
}

function onGridSquareClicked({ lat, lng }) {
  if (locations.value.length >= LOCATION_COUNT) return;
  if (pendingPin.value) return;
  pendingPin.value = { lat, lng };
  pendingHint.value = "";
  // The hint input renders just below the map; once mounted, focus it and
  // scroll it into view so the user immediately sees the prompt.
  nextTick(() => {
    const el = hintInputEl.value;
    if (el) {
      el.focus();
      try {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      } catch {
        /* no-op */
      }
    }
  });
}

function confirmPin() {
  if (!pendingPin.value) return;
  const loc = { ...pendingPin.value, hint: pendingHint.value.trim() };
  locations.value.push(loc);
  pendingPin.value = null;
  pendingHint.value = "";
  selectedSquareId.value = "";
  selectedLocation.value = { lat: 0, lng: 0, confirmed: false };
  mapEl.value?.reset(initialZoom, { lat: 0, lng: 0 });
}

function cancelPin() {
  pendingPin.value = null;
  pendingHint.value = "";
  selectedSquareId.value = "";
  selectedLocation.value = { lat: 0, lng: 0, confirmed: false };
  mapEl.value?.reset(initialZoom, { lat: 0, lng: 0 });
}

function removeLocation(idx) {
  locations.value.splice(idx, 1);
}

async function save() {
  errorMsg.value = "";
  saving.value = true;
  try {
    const result = await setupLocationRecovery(
      locations.value,
      props.existingMnemonic ?? null,
      props.prevKeyHash ?? null,
      props.secondFactor ?? null,
    );
    derivedMnemonic.value = result.mnemonic;
    recoveryCode.value = result.code;
    txnData.value = result.txnData;
  } catch (e) {
    errorMsg.value = e.message || String(e);
  } finally {
    saving.value = false;
  }
}

function emitDone() {
  emit("setup-complete", {
    mnemonic: derivedMnemonic.value,
    code: recoveryCode.value,
    txnData: txnData.value,
  });
}
</script>

<style scoped>
.loc-setup {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.header h3 {
  margin: 0 0 4px;
  font-size: 1rem;
  color: var(--text, #e0e0e0);
}
.hint {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text2, #999);
  line-height: 1.5;
}
.progress-row {
  display: flex;
  gap: 6px;
}
.dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: transparent;
  border: 2px solid var(--text2, #888);
  transition:
    background 0.2s,
    border-color 0.2s;
}
.dot.done {
  background: var(--accent, #7c6af7);
  border-color: var(--accent, #7c6af7);
}
.dot.active {
  background: transparent;
  border-color: var(--accent, #7c6af7);
}
.step-label {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text, #e0e0e0);
}
.map-hint {
  margin: -0.25rem 0 0;
  font-size: 0.78rem;
  color: var(--text3, #777);
  text-align: center;
}
.hint-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.input {
  flex: 1;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border, #333);
  border-radius: 8px;
  background: var(--input-bg, #12121e);
  color: var(--text, #e0e0e0);
  font-size: 0.9rem;
  outline: none;
}
.input:focus {
  border-color: var(--accent, #7c6af7);
}
.loc-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.loc-list li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--surface3, #2a2a3e);
  border: 1px solid var(--border, #333);
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
  font-size: 0.82rem;
  color: var(--text, #e0e0e0);
}
.loc-num {
  font-weight: 700;
  color: var(--accent, #7c6af7);
  min-width: 1.2rem;
}
.loc-hint {
  flex: 1;
}
.loc-coord {
  color: var(--text3, #777);
  font-size: 0.72rem;
  font-family: monospace;
}
.btn-remove {
  background: none;
  border: none;
  color: var(--red2, #f87171);
  cursor: pointer;
  font-size: 0.9rem;
  padding: 0;
}
.btn {
  padding: 0.55rem 1rem;
  border-radius: 6px;
  border: none;
  font-size: 0.88rem;
  font-weight: 500;
  cursor: pointer;
}
.btn.primary {
  background: var(--accent, #7c6af7);
  color: #fff;
}
.btn.secondary {
  background: var(--surface3, #2a2a3e);
  color: var(--text, #e0e0e0);
  border: 1px solid var(--border, #444);
}
.btn.link {
  background: none;
  color: var(--text2, #aaa);
  text-decoration: underline;
}
.action-row {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.error {
  margin: 0;
  color: var(--red2, #f87171);
  font-size: 0.82rem;
  padding: 6px 10px;
  background: rgba(224, 96, 96, 0.1);
  border-radius: 4px;
}
.status {
  margin: 0;
  color: var(--text2, #999);
  font-size: 0.82rem;
}
.recovery-code-screen {
  background: rgba(224, 160, 96, 0.08);
  border: 1px solid rgba(224, 160, 96, 0.4);
  border-radius: 10px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.code-label {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #e0a060;
}
.code-display {
  font-family: monospace;
  font-size: 1.8rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-align: center;
  color: var(--text, #e0e0e0);
  background: var(--surface2, #1e1e2e);
  border-radius: 8px;
  padding: 0.5rem 1rem;
  border: 1px solid var(--border, #333);
}
.code-instructions {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--text, #e0e0e0);
}
.code-note {
  margin: 0;
  font-size: 0.75rem;
  color: var(--text3, #888);
}
</style>
