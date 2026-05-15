<template>
  <div class="loc-recover">
    <!-- Step: Recovery code entry ────────────────────────────────────────── -->
    <div v-if="step === 'code'">
      <p class="hint">
        Enter your Recovery Code to load the location hints that were stored
        when this wallet was set up. If you don't have the code you can still
        recover by re-pinning your {{ LOCATION_COUNT }} locations without hints.
      </p>
      <input
        v-model="enteredCode"
        class="input"
        placeholder="e.g. 7KMN-2QPR"
        spellcheck="false"
        autocomplete="off"
        @keyup.enter="fetchHints"
      />
      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
      <div class="action-row">
        <button
          class="btn primary"
          :disabled="fetchingHints"
          @click="fetchHints"
        >
          {{ fetchingHints ? "Looking up…" : "Load Hints" }}
        </button>
        <button class="btn secondary" @click="skipCode">
          Continue without a Recovery Code
        </button>
        <button class="btn link" @click="$emit('cancel')">← Back</button>
      </div>
      <div
        v-if="isDev"
        style="margin-top: 12px; border-top: 1px dashed #555; padding-top: 10px"
      >
        <button
          class="btn secondary"
          style="font-size: 11px; opacity: 0.7"
          @click="devPrefill"
        >
          [DEV] Prefill test locations
        </button>
      </div>
    </div>

    <!-- Step: Loading hints ─────────────────────────────────────────────── -->
    <div v-else-if="step === 'loading'" class="loading-state">
      <p>Loading your recovery hints…</p>
    </div>

    <!-- Step: Re-pin locations ──────────────────────────────────────────── -->
    <div v-else-if="step === 'map'" class="step">
      <p class="step-label">
        Location {{ locations.length + 1 }} of {{ LOCATION_COUNT }}
      </p>
      <div v-if="hints[locations.length]" class="hint-card">
        <span class="hint-num">{{ locations.length + 1 }}</span>
        <div class="hint-body">
          <span class="hint-label">Reminder hint from setup</span>
          <span class="hint-text">{{ hints[locations.length] }}</span>
        </div>
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

      <Map
        ref="mapComponent"
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
      <p class="map-hint">
        Tap the map to zoom in. When the grid appears, click a cell to select
        the location.
      </p>

      <div v-if="pendingPin" class="pending-row">
        <span class="pending-label">Confirm this location?</span>
        <button class="btn primary" @click="confirmPin">Yes, add it</button>
        <button class="btn secondary" @click="cancelPin">Move pin</button>
      </div>

      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
      <button class="btn link" @click="$emit('cancel')">← Cancel</button>
    </div>

    <!-- Step: Second factor + restore ───────────────────────────────────── -->
    <div v-else-if="step === 'restore'" class="step">
      <div class="callout">
        <strong>Locations placed</strong>
        <p>
          A zero-knowledge proof will verify your locations against the stored
          commitment. Enter the second-factor password you used when you first
          set up this wallet — it's combined with the recovered seed to
          re-derive your signing key.
        </p>
      </div>
      <div class="field">
        <label>Second Factor Password</label>
        <input
          v-model="secondFactor"
          type="password"
          placeholder="Same password used at setup"
          autocomplete="current-password"
          @keyup.enter="restore"
        />
      </div>
      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
      <div class="action-row">
        <button
          class="btn primary"
          :disabled="restoring || !secondFactor"
          @click="restore"
        >
          {{ restoring ? "Restoring…" : "Restore Wallet" }}
        </button>
        <button class="btn link" @click="$emit('cancel')">Cancel</button>
      </div>
    </div>
    <!-- Step: New Recovery Code (shown after successful fresh-device recovery) -->
    <div v-else-if="step === 'new-code'" class="step">
      <div class="callout callout-warn">
        <strong>Save your new Recovery Code</strong>
        <p>
          Your wallet has been recovered and a new location-recovery vault has
          been set up automatically. Write down the new Recovery Code below —
          you'll need it if you ever recover again from a different device.
        </p>
      </div>
      <div class="code-display">
        <code class="wt-result-val wt-result-highlight">{{
          newRecoveryCode
        }}</code>
      </div>
      <div class="action-row">
        <button class="btn primary" @click="$emit('cancel')">
          Done — I've saved my code
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
// Adapted from plugins/yadacoinwallet/ui/src/views/LocationRecoveryView.vue.
//
// Recovery flow specific to yadaaiagent: there is no PIN-based vault here, so
// the user must also re-enter their second-factor password. The decrypted
// mnemonic is fed through `initClientWallet` + `submitInceptionTransaction`
// (the same path the WalletSetup "Import" tab takes), which advances K_0 and
// is a no-op against the chain when the KEL already exists.
import { ref } from "vue";
import Map from "./Map.vue";
import {
  getLocationHints,
  recoverWithLocations,
  hasLocationVault,
  findRecoveryTip,
  deriveRecoveryProof,
  computeWitnessHashFromLocations,
  buildRecoveryTransitionRelationship,
  setupLocationRecovery,
  LOCATION_COUNT,
} from "../composables/useLocationRecovery.js";
import {
  initClientWallet,
  submitInceptionTransaction,
  generateNewMnemonic,
} from "../composables/useBip39.js";
import {
  hex,
  getPublicKeyHex,
  getP2PKH,
  buildRotationTxn,
  deriveSecurePath,
} from "../composables/useCrypto.js";
import { LS_PRIV, LS_CC, getNodeUrl } from "../composables/useStorage.js";

const emit = defineEmits(["recovered", "cancel"]);

const step = ref("code"); // 'code' → 'loading' → 'map' → 'restore'
const enteredCode = ref("");
const fetchingHints = ref(false);
const hints = ref([]);
const locations = ref([]);
const pendingPin = ref(null);
const secondFactor = ref("");
const errorMsg = ref("");
const restoring = ref(false);
// New recovery code generated during fresh-device recovery — shown to the
// user before emitting 'recovered' so they can note it down.
const newRecoveryCode = ref("");

const mapComponent = ref(null);
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
  // Simulate the Recovery Code entry step: set up locations + secondFactor
  // so that freshDeviceRecover() can re-derive the witness secret directly.
  locations.value = [
    { lat: 45.5239, lng: -122.6837 },
    { lat: 45.5239, lng: -122.6837 },
    { lat: 45.5239, lng: -122.6837 },
  ];
  hints.value = ["asdf", "asdf2", "asdf3"];
  secondFactor.value = "asdf2";
  step.value = "restore";
  await restore();
}

async function fetchHints() {
  errorMsg.value = "";
  const code = enteredCode.value.trim();
  if (!code) {
    errorMsg.value = "Please enter your Recovery Code.";
    return;
  }
  fetchingHints.value = true;
  try {
    // getLocationHints now resolves to {hints, tip} (decrypted from the
    // on-chain announcement) or null when the code does not match any
    // announcement.  Cipher-decryption failures (wrong code / tampered ct)
    // also return null so the legacy "not found" UX is preserved.
    const result = await getLocationHints(code);
    if (!result) {
      hints.value = [];
      errorMsg.value =
        "Recovery Code not found on-chain. You can still recover by re-pinning your locations.";
    } else if (!result.hints || result.hints.length === 0) {
      hints.value = [];
      errorMsg.value =
        "Announcement found but contains no hints. Continue by re-pinning your locations.";
    } else {
      hints.value = result.hints;
    }
  } catch {
    hints.value = [];
    errorMsg.value = "Could not reach the server. Continuing without hints.";
  } finally {
    fetchingHints.value = false;
  }
  step.value = "map";
}

function skipCode() {
  hints.value = [];
  errorMsg.value = "";
  step.value = "map";
}

function onGridSquareClicked({ lat, lng }) {
  if (locations.value.length >= LOCATION_COUNT) return;
  if (pendingPin.value) return;
  pendingPin.value = { lat, lng };
}

function confirmPin() {
  if (!pendingPin.value) return;
  locations.value.push({ ...pendingPin.value });
  pendingPin.value = null;
  selectedSquareId.value = "";
  selectedLocation.value = { lat: 0, lng: 0, confirmed: false };
  if (locations.value.length === LOCATION_COUNT) {
    step.value = "restore";
  } else {
    mapComponent.value?.reset(initialZoom, { lat: 0, lng: 0 });
  }
}

function cancelPin() {
  pendingPin.value = null;
  selectedSquareId.value = "";
  selectedLocation.value = { lat: 0, lng: 0, confirmed: false };
  mapComponent.value?.reset(initialZoom, { lat: 0, lng: 0 });
}

async function restore() {
  errorMsg.value = "";
  if (!secondFactor.value) {
    errorMsg.value = "Second factor password is required.";
    return;
  }
  restoring.value = true;
  try {
    const haveLocalVault = await hasLocationVault();
    if (haveLocalVault) {
      // Same-device fast path: decrypt the local vault and re-init the
      // wallet from the original mnemonic.  recoverWithLocations also
      // re-stores the witness secret so credential receipts work immediately.
      const mnemonic = await recoverWithLocations(
        locations.value,
        secondFactor.value,
      );
      const k0 = await initClientWallet(mnemonic, secondFactor.value);
      await submitInceptionTransaction(k0, secondFactor.value);
      emit("recovered", { mnemonic });
    } else {
      // Fresh-device path: there is NO mnemonic on this device. Mint a
      // new BIP-39 phrase, derive K_0, and broadcast a recovers-inception
      // transaction whose `prev_public_key_hash` points at the lost KEL
      // tip and whose `relationship` carries the Schnorr proof bound to
      // that tip. Consensus (locationrecovery.verify_proof + KEL recovery
      // checks) accepts it iff the witnessHash matches the one announced
      // on-chain at setup time.
      await freshDeviceRecover();
    }
  } catch (e) {
    errorMsg.value = e.message || String(e);
    if (/locations|proof/i.test(errorMsg.value)) {
      // Locations were wrong — let user re-pin
      locations.value = [];
      step.value = "map";
      mapComponent.value?.reset(initialZoom, { lat: 0, lng: 0 });
    }
  } finally {
    restoring.value = false;
  }
}

async function freshDeviceRecover() {
  // 1. Find the on-chain announcement for these locations.
  const witnessHash = computeWitnessHashFromLocations(
    locations.value,
    secondFactor.value,
  );
  const tip = await findRecoveryTip(witnessHash);
  if (!tip) {
    throw new Error(
      "No on-chain recovery announcement matches these locations. Either the locations are wrong, or the announcement has not been mined yet.",
    );
  }

  // 2. Build the Schnorr proof that authorises the recovery (bound to the
  //    lost KEL tip's pkh).
  const proof = deriveRecoveryProof(
    locations.value,
    tip.public_key_hash,
    secondFactor.value,
  );

  // 3. Generate a fresh seed + K_0 on this device and persist it.
  const newMnemonic = generateNewMnemonic();
  const k0 = await initClientWallet(newMnemonic, secondFactor.value);
  const k1 = deriveSecurePath(k0.priv, k0.cc, secondFactor.value);
  const k2 = deriveSecurePath(k1.priv, k1.cc, secondFactor.value);

  const k0PubHex = getPublicKeyHex(k0.priv);
  const k0Pkh = getP2PKH(hex.toBytes(k0PubHex));
  const k1Pkh = getP2PKH(hex.toBytes(getPublicKeyHex(k1.priv)));
  const k2Pkh = getP2PKH(hex.toBytes(getPublicKeyHex(k2.priv)));

  // 4. Set up a new recovery vault for the freshly-minted KEL (bound to
  //    k0Pkh as prevKeyHash) and generate a new Recovery Code.  setupLocationRecovery
  //    also stores the witness secret so credential receipts work from this device.
  //    Attach hints from the old Recovery Code to the re-pinned locations so
  //    the new announcement carries the same labels.
  const locationsWithHints = locations.value.map((loc, i) => ({
    ...loc,
    hint: hints.value[i] || "",
  }));
  const newSetup = await setupLocationRecovery(
    locationsWithHints,
    newMnemonic,
    k0Pkh,
    secondFactor.value,
  );

  // 5. Combine the recovers proof and the new recovery announcement into a
  //    single relationship so the recovers-inception atomically proves
  //    recovery eligibility and re-establishes the location-recovery vault.
  const recoveryInner = newSetup.txnData.announcementData.relationship.recovery;
  const { relationship, relationshipHash } =
    buildRecoveryTransitionRelationship(proof, recoveryInner);

  // 6. Build and submit the recovers-inception transaction.
  const txnTime = Math.floor(Date.now() / 1000);
  const recoversTxn = await buildRotationTxn({
    signerPrivBytes: k0.priv,
    publicKeyHex: k0PubHex,
    prerotatedPkh: k1Pkh,
    twicePrerotatedPkh: k2Pkh,
    publicKeyHash: k0Pkh,
    prevPublicKeyHash: tip.public_key_hash,
    relationship,
    relationshipHash,
    txnTime,
    inputs: [],
    outputs: [{ to: k1Pkh, value: 0.0 }],
  });

  const res = await fetch(`${getNodeUrl()}/transaction?username_signature=1`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify([recoversTxn]),
  });
  const data = await res.json();
  if (!res.ok || data.status === false) {
    throw new Error(data.message || `HTTP ${res.status}`);
  }

  // After the recovers-inception is accepted the next signer is K_1.
  localStorage.setItem(LS_PRIV, hex.fromBytes(k1.priv));
  localStorage.setItem(LS_CC, hex.fromBytes(k1.cc));

  // Show the new Recovery Code before completing — the user must save it
  // to be able to recover from a fresh device next time.
  newRecoveryCode.value = newSetup.code;
  step.value = "new-code";
  // Emit with the new code so the parent can record it if needed.
  emit("recovered", {
    mnemonic: newMnemonic,
    fresh: true,
    newRecoveryCode: newSetup.code,
  });
}
</script>

<style scoped>
.loc-recover {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.25rem 0.1rem;
}
.step {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.hint {
  margin: 0 0 0.6rem;
  font-size: 0.85rem;
  color: var(--text2, #999);
  line-height: 1.5;
}
.input,
.field input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border, #333);
  border-radius: 8px;
  background: var(--input-bg, #12121e);
  color: var(--text, #e0e0e0);
  font-size: 0.9rem;
  outline: none;
}
.input:focus,
.field input:focus {
  border-color: var(--accent, #7c6af7);
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field label {
  font-size: 0.78rem;
  color: var(--text2, #999);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.action-row {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.75rem;
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
.btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
.error {
  color: var(--red2, #f87171);
  font-size: 0.82rem;
  padding: 6px 10px;
  background: rgba(224, 96, 96, 0.1);
  border-radius: 4px;
  margin: 0;
}
.loading-state {
  text-align: center;
  padding: 1rem;
  color: var(--text2, #aaa);
}
.step-label {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text, #e0e0e0);
}
.hint-card {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  background: rgba(124, 106, 247, 0.08);
  border: 1px solid rgba(124, 106, 247, 0.3);
  border-radius: 10px;
  padding: 0.6rem 0.85rem;
  font-size: 0.88rem;
  color: var(--text, #e0e0e0);
}
.hint-card.empty {
  background: transparent;
  border-style: dashed;
  border-color: var(--border, #444);
  color: var(--text2, #888);
}
.hint-num {
  font-weight: 700;
  color: var(--accent, #7c6af7);
  font-size: 1.05rem;
  min-width: 1.4rem;
}
.hint-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  gap: 0.1rem;
}
.hint-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text2, #888);
}
.hint-text {
  flex: 1;
}
.hint-note {
  margin: 0.25rem 0 0;
  font-size: 0.78rem;
  color: var(--text2, #888);
  font-style: italic;
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
.map-hint {
  margin: 0;
  font-size: 0.78rem;
  color: var(--text3, #777);
  text-align: center;
}
.pending-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  background: var(--surface3, #2a2a3e);
  border: 1px solid var(--border, #333);
  border-radius: 8px;
  padding: 0.5rem 0.7rem;
}
.pending-label {
  font-size: 0.85rem;
  color: var(--text, #e0e0e0);
  flex: 1;
}
.callout {
  background: var(--surface3, #2a2a3e);
  border: 1px solid var(--border, #333);
  border-radius: 6px;
  padding: 12px 14px;
}
.callout strong {
  display: block;
  font-size: 0.88rem;
  color: var(--text, #e0e0e0);
  margin-bottom: 4px;
}
.callout p {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text2, #999);
  line-height: 1.5;
}
</style>
