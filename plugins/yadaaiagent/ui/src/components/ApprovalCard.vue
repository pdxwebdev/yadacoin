<template>
  <div class="approval-card">
    <div class="title">🔐 Authorisation Required</div>

    <!-- Sensitive-change warning for node_config -->
    <div v-if="isNodeConfig && sensitiveKey" class="warning-banner">
      ⚠️ <strong>Verify before approving.</strong> This will change
      <code>{{ scope.config_key }}</code> to <code>{{ scope.new_value }}</code
      >.
      <span v-if="scope.config_key === 'combined_address'">
        All mining and pool rewards will be sent to this address. Make sure it
        is <em>your</em> wallet address.
      </span>
      <span
        v-else-if="
          scope.config_key === 'peer_host' || scope.config_key === 'peer_port'
        "
      >
        This changes the address your node advertises to the network.
      </span>
      <span
        v-else-if="
          scope.config_key === 'serve_host' || scope.config_key === 'serve_port'
        "
      >
        This changes the address your node listens on for inbound connections.
      </span>
    </div>

    <!-- Scope summary for node_config -->
    <div v-if="isNodeConfig" class="scope-summary">
      <span class="scope-label">Setting:</span>
      <code>{{ scope.config_key }}</code>
      <span class="scope-label">New value:</span>
      <code>{{ scope.new_value }}</code>
    </div>

    <!-- Send/Wrap summary for wallet_agent -->
    <div v-if="isWalletAgent && scope.action !== 'wrap'" class="warning-banner">
      ⚠️ <strong>Verify this transaction before approving.</strong>
      You are authorizing a send of
      <code>{{ scope.amount }} YDA</code> to <code>{{ scope.to_address }}</code
      >.
    </div>
    <div v-if="isWalletAgent && scope.action !== 'wrap'" class="scope-summary">
      <span class="scope-label">To:</span>
      <code>{{ scope.to_address }}</code>
      <span class="scope-label">Amount:</span>
      <code>{{ scope.amount }} YDA</code>
    </div>
    <div v-if="isWalletAgent && scope.action === 'wrap'" class="warning-banner">
      ⚠️ <strong>Verify this wrap before approving.</strong> You are wrapping
      <code>{{ scope.amount }} YDA</code> to Ethereum address
      <code>{{ scope.eth_address }}</code
      >. The YDA will be sent to the bridge address.
    </div>
    <div v-if="isWalletAgent && scope.action === 'wrap'" class="scope-summary">
      <span class="scope-label">Amount:</span>
      <code>{{ scope.amount }} YDA</code>
      <span class="scope-label">Ethereum address:</span>
      <code>{{ scope.eth_address }}</code>
    </div>

    <div class="detail">
      The following W3C Verifiable Credential will be committed on-chain in the
      <code>relationship</code> field of the rotation transaction.
      <pre>{{ previewJson }}</pre>
    </div>

    <template v-if="!skipPayment">
      <div class="field-row">
        <label>Payment Method</label>
        <select v-model="selectedPmIdx" :disabled="!paymentMethods.length">
          <option v-if="!paymentMethods.length" value="-1">
            ⚠ No payment methods — add one in ⚙ Settings
          </option>
          <option v-for="(pm, i) in paymentMethods" :key="pm.token" :value="i">
            {{ pm.label }}{{ pm.isDefault ? " ★" : "" }}
          </option>
        </select>
      </div>
    </template>

    <template v-if="!isRegistration && !isHardware">
      <div class="field-row">
        <label>Second factor</label>
        <input
          ref="sfInput"
          v-model="secondFactor"
          type="password"
          placeholder="Password / second factor"
          autocomplete="current-password"
          @keydown.enter="approve"
        />
      </div>
    </template>

    <!-- Hardware-wallet flow: stored active key signs the unconfirmed tx
         silently; user only scans the confirming + next-active keys. -->
    <template v-if="!isRegistration && isHardware">
      <div class="hw-block">
        <div v-if="!hwActive" class="hw-row">
          <span class="hw-label hw-err">
            ⚠ No active hardware key on file. Re-pair your device in Settings.
          </span>
        </div>
        <div v-else-if="hwStale" class="hw-row">
          <span class="hw-label hw-err">
            ⚠ Stored active hardware key is stale — the on-chain KEL has
            <strong>{{ hwKelLength }}</strong> entries and its tip's
            prerotated_key_hash no longer matches the stored key. Re-pair the
            device from Settings (scan inception + the active key at idx
            <strong>{{ hwKelLength }}</strong>) before approving.
          </span>
        </div>
        <div v-else-if="hwExpectedIndex !== null" class="hw-row">
          <span class="hw-label">
            Stored active key: idx
            <strong>{{ hwActive.rotationIndex }}</strong> — signs unconfirmed
            silently. Device should now show idx
            <strong>{{ hwExpectedIndex }}</strong> (confirming) then
            <strong>{{ hwExpectedIndex + 1 }}</strong> (next active).
          </span>
        </div>
        <div v-else-if="hwIndexLoading" class="hw-row">
          <span class="hw-label">Looking up next rotation index…</span>
        </div>
        <div class="hw-row">
          <span class="hw-label">
            Step 1 — confirming key (idx
            {{ hwExpectedIndex !== null ? hwExpectedIndex : "?" }})
          </span>
          <span v-if="hwScanConfirming" class="hw-status ok"
            >✓ captured (idx {{ hwScanConfirming.rotationIndex }})</span
          >
          <span v-else class="hw-status">awaiting scan</span>
        </div>
        <div class="hw-row">
          <span class="hw-label">
            Step 2 — next active key (idx
            {{ hwExpectedIndex !== null ? hwExpectedIndex + 1 : "?" }})
          </span>
          <span v-if="hwScanNextActive" class="hw-status ok"
            >✓ captured (idx {{ hwScanNextActive.rotationIndex }})</span
          >
          <span v-else class="hw-status">awaiting scan</span>
        </div>
        <div class="hw-actions">
          <button
            class="btn scan"
            :disabled="busy || !!showScanner || !hwActive || hwStale"
            @click="
              openScanner(hwScanConfirming ? 'nextActive' : 'confirming')
            "
          >
            📷
            {{
              !hwScanConfirming
                ? "Scan confirming QR"
                : !hwScanNextActive
                  ? "Scan next-active QR"
                  : "Re-scan"
            }}
          </button>
          <button
            v-if="hwScanConfirming || hwScanNextActive"
            class="btn reset"
            :disabled="busy"
            @click="resetHwScans"
          >
            Clear
          </button>
        </div>
        <div v-if="hwError" class="hw-err">⚠ {{ hwError }}</div>
      </div>

      <QrScanner
        v-if="showScanner"
        :title="
          showScanner === 'confirming'
            ? 'Scan confirming QR (index ' +
              (hwExpectedIndex !== null ? hwExpectedIndex : '?') +
              ')'
            : 'Scan next-active QR (index ' +
              (hwScanConfirming
                ? hwScanConfirming.rotationIndex + 1
                : hwExpectedIndex !== null
                  ? hwExpectedIndex + 1
                  : '?') +
              ')'
        "
        :hint="
          showScanner === 'confirming'
            ? 'On your hardware device, advance to rotation index ' +
              (hwExpectedIndex !== null ? hwExpectedIndex : '?') +
              ' and display its QR.'
            : 'Now advance the device once more and display the QR for index ' +
              (hwScanConfirming
                ? hwScanConfirming.rotationIndex + 1
                : hwExpectedIndex !== null
                  ? hwExpectedIndex + 1
                  : '?') +
              '.'
        "
        @scanned="onQrScanned"
        @cancel="showScanner = null"
      />
    </template>

    <div class="btn-row">
      <button
        class="btn approve"
        :disabled="busy || !canApprove"
        @click="approve"
      >
        {{
          isRegistration
            ? "📡 Broadcast Registration"
            : isNodeConfig
              ? "🔐 Authorise & Apply"
              : isWalletAgent && scope.action === "wrap"
                ? "🔐 Authorise & Wrap"
                : isWalletAgent
                  ? "🔐 Authorise & Send"
                  : "✓ Approve & Book"
        }}
      </button>
      <button class="btn deny" :disabled="busy" @click="$emit('deny')">
        ✗ Deny
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import {
  getPaymentMethods,
  isHardwareWallet,
  getNodeUrl,
  getHardwareActive,
} from "../composables/useStorage.js";
import { parseHardwareQrPayload } from "../composables/useCrypto.js";
import QrScanner from "./QrScanner.vue";

const props = defineProps({
  agentType: Object,
  scope: Object,
});
const emit = defineEmits(["approve", "deny"]);

const isHardware = computed(() => isHardwareWallet());
// Stored "active" hardware key (parsed QR) — the K_n that will sign the
// upcoming unconfirmed rotation tx. Loaded once on mount.
const hwActive = ref(null);
// User-scanned keys for THIS approval round.
//   hwScanConfirming = K_{n+1} → signs the confirming tx
//   hwScanNextActive = K_{n+2} → becomes the new stored active and the
//                                agent DID for the VC/VP this round.
const hwScanConfirming = ref(null);
const hwScanNextActive = ref(null);
const showScanner = ref(null); // null | 'confirming' | 'nextActive'
const hwError = ref("");
// Index resolved from on-chain KEL on mount.
const hwExpectedIndex = ref(null);
const hwIndexLoading = ref(false);
// True when the locally-stored active key no longer matches the chain tip's
// prerotated_key_hash — happens if the device rotated out-of-band or the
// device was paired before the WalletSetup chain-aware fix. We block all
// scans in that case and tell the user to re-pair.
const hwStale = ref(false);
const hwTipPkh = ref(null);
const hwKelLength = ref(null);

async function loadExpectedIndex() {
  if (!isHardware.value) return;
  hwActive.value = getHardwareActive();
  if (!hwActive.value) return;
  hwIndexLoading.value = true;
  hwStale.value = false;
  try {
    const r = await fetch(
      getNodeUrl() +
        "/key-event-log?username_signature=asdf&public_key=" +
        encodeURIComponent(hwActive.value.publicKeyHex),
    );
    if (r.ok) {
      const j = await r.json();
      const kel = j.key_event_log || [];
      hwKelLength.value = kel.length;
      if (kel.length === 0) {
        // Stored active is K_1 (committed by an inception that hasn't been
        // mined yet, or by no chain at all). Confirming index will be 1.
        hwExpectedIndex.value = 1;
        hwTipPkh.value = null;
      } else {
        const tip = kel[kel.length - 1];
        const tipPrerotated =
          tip.prerotated_key_hash || tip.prerotatedKeyHash || null;
        hwTipPkh.value = tip.public_key_hash || tip.publicKeyHash || null;
        // Stale check: the tip's prerotated_key_hash must equal the stored
        // active key's public_key_hash. If not, the chain advanced beyond
        // the stored key.
        if (
          tipPrerotated &&
          tipPrerotated !== hwActive.value.publicKeyHash
        ) {
          hwStale.value = true;
        }
        // The KEL has kel.length entries (rotation_indexes 0..kel.length-1).
        // The tip commits K_{kel.length} as the active key — that is the
        // device's stored active key. Confirming will therefore be at
        // rotation_index kel.length + 1, and next-active at kel.length + 2.
        hwExpectedIndex.value = kel.length + 1;
      }
    } else {
      hwExpectedIndex.value = (hwActive.value.rotationIndex ?? 0) + 1;
    }
  } catch {
    hwExpectedIndex.value = (hwActive.value.rotationIndex ?? 0) + 1;
  } finally {
    hwIndexLoading.value = false;
  }
}

function openScanner(which) {
  hwError.value = "";
  showScanner.value = which;
}
function resetHwScans() {
  hwScanConfirming.value = null;
  hwScanNextActive.value = null;
  hwError.value = "";
}
function onQrScanned(raw) {
  hwError.value = "";
  if (hwStale.value) {
    hwError.value =
      "Stored active hardware key is stale (chain advanced past it). Re-pair your device from Settings before approving.";
    return;
  }
  let parsed;
  try {
    parsed = parseHardwareQrPayload(raw);
  } catch (e) {
    hwError.value = "Invalid QR payload: " + (e?.message || String(e));
    return;
  }
  const stored = hwActive.value;
  // Use the chain-derived expected confirming index when available — it is
  // authoritative. Fall back to stored.rotationIndex+1 only if the KEL
  // lookup failed.
  const expectedConfirmingIdx =
    hwExpectedIndex.value !== null
      ? hwExpectedIndex.value
      : (stored?.rotationIndex ?? 0) + 1;
  if (showScanner.value === "confirming") {
    if (!stored) {
      hwError.value =
        "No stored active hardware key — re-pair your device first.";
      return;
    }
    if (parsed.rotationIndex !== expectedConfirmingIdx) {
      hwError.value =
        "Confirming QR rotation_index must be " +
        expectedConfirmingIdx +
        " (got " +
        parsed.rotationIndex +
        ").";
      return;
    }
    if (parsed.publicKeyHash !== stored.prerotatedKeyHash) {
      hwError.value =
        "Confirming QR's public key hash does not match the prerotated_key_hash committed by the stored active key.";
      return;
    }
    if (parsed.prevPublicKeyHash !== stored.publicKeyHash) {
      hwError.value =
        "Confirming QR's prev_public_key_hash does not match the stored active key's public key hash.";
      return;
    }
    hwScanConfirming.value = parsed;
  } else if (showScanner.value === "nextActive") {
    const conf = hwScanConfirming.value;
    if (!conf) {
      hwError.value = "Scan the confirming key first.";
      return;
    }
    if (parsed.rotationIndex !== conf.rotationIndex + 1) {
      hwError.value =
        "Next-active QR rotation_index must be " +
        (conf.rotationIndex + 1) +
        " (got " +
        parsed.rotationIndex +
        ").";
      return;
    }
    if (parsed.publicKeyHash !== conf.prerotatedKeyHash) {
      hwError.value =
        "Next-active QR's public key hash does not match the prerotated_key_hash committed by the confirming key.";
      return;
    }
    if (parsed.prevPublicKeyHash !== conf.publicKeyHash) {
      hwError.value =
        "Next-active QR's prev_public_key_hash does not match the confirming key's public key hash.";
      return;
    }
    hwScanNextActive.value = parsed;
  }
  showScanner.value = null;
}

const isRegistration = computed(
  () => props.agentType?.id === "agent_registration",
);
const isNodeConfig = computed(() => props.agentType?.id === "node_config");
const isWalletAgent = computed(() => props.agentType?.id === "wallet_agent");
const skipPayment = computed(
  () => isRegistration.value || isNodeConfig.value || isWalletAgent.value ||
    props.agentType?.id === "microsoft_connect",
);

// Keys that warrant an explicit "verify this value" warning
const SENSITIVE_KEYS = new Set([
  "combined_address",
  "peer_host",
  "peer_port",
  "serve_host",
  "serve_port",
]);
const sensitiveKey = computed(
  () => isNodeConfig.value && SENSITIVE_KEYS.has(props.scope?.config_key),
);

const secondFactor = ref("");
const busy = ref(false);
const paymentMethods = ref(getPaymentMethods());
const defIdx = computed(() => {
  const i = paymentMethods.value.findIndex((m) => m.isDefault);
  return i >= 0 ? i : paymentMethods.value.length ? 0 : -1;
});
const selectedPmIdx = ref(defIdx.value);

const sfInput = ref(null);
onMounted(() => {
  setTimeout(() => {
    if (!isHardware.value) sfInput.value?.focus();
  }, 50);
  loadExpectedIndex();
});

const previewJson = computed(() => {
  const pm = paymentMethods.value[selectedPmIdx.value];
  if (isNodeConfig.value) {
    return JSON.stringify(
      {
        type: "NodeConfigAuthorization",
        note: "Config change details are not committed on-chain for security.",
      },
      null,
      2,
    );
  }
  if (isWalletAgent.value) {
    return JSON.stringify(
      {
        type: "WalletAuthorization",
        services: ["WalletAuthorization"],
        to_address:
          props.scope?.action === "wrap"
            ? "16U1gAmHazqqEkbRE9KFPShAperjJreMRA"
            : props.scope?.to_address || "",
        amount: props.scope?.amount ?? null,
        ...(props.scope?.action === "wrap"
          ? { eth_address: props.scope?.eth_address || "" }
          : {}),
      },
      null,
      2,
    );
  }
  return JSON.stringify(
    {
      "@context": [
        "https://www.w3.org/ns/credentials/v2",
        "https://yadacoin.io/contexts/agent-auth/v1",
      ],
      type: ["VerifiableCredential", "AgentAuthorizationCredential"],
      issuer: "did:yadacoin:<operator_public_key>",
      validFrom: new Date().toISOString(),
      credentialStatus: { type: "YadaKELStatus", mode: "rotation" },
      credentialSubject: {
        id: "did:yadacoin:<agent_key_derived_on_approval>",
        agentAuthorization: {
          type: props.agentType?.authorizationType || "AgentAuthorization",
          ...props.scope,
          paymentMethod: pm ? { token: pm.token, label: pm.label } : "<none>",
        },
      },
    },
    null,
    2,
  );
});

const canApprove = computed(() => {
  if (isRegistration.value) return true;
  if (isHardware.value)
    return (
      !!hwActive.value &&
      !hwStale.value &&
      !!hwScanConfirming.value &&
      !!hwScanNextActive.value
    );
  return !!secondFactor.value;
});

function approve() {
  if (isHardware.value && !isRegistration.value) {
    if (!hwActive.value) {
      hwError.value =
        "No active hardware key on file. Re-pair your device first.";
      return;
    }
    if (!hwScanConfirming.value || !hwScanNextActive.value) {
      hwError.value = "Both QR codes must be scanned before approving.";
      return;
    }
  } else if (!isRegistration.value && !secondFactor.value) {
    sfInput.value?.focus();
    return;
  }
  const pm = paymentMethods.value[selectedPmIdx.value] || null;
  busy.value = true;
  emit("approve", {
    secondFactor: secondFactor.value,
    paymentMethod: skipPayment.value ? null : pm,
    hardware:
      isHardware.value && !isRegistration.value
        ? {
            stored: hwActive.value,
            confirming: hwScanConfirming.value,
            nextActive: hwScanNextActive.value,
          }
        : null,
  });
}
</script>

<style scoped>
.approval-card {
  background: var(--surface);
  border: 1px solid var(--accent);
  border-radius: 10px;
  padding: 14px 16px;
  margin-top: 10px;
  font-size: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.title {
  font-weight: 700;
  color: var(--accent);
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.detail {
  color: var(--subtext);
  font-size: 0.82rem;
  line-height: 1.5;
}
.detail pre {
  background: #0a0c12;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px;
  font-size: 0.76rem;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 140px;
  overflow: auto;
  margin-top: 6px;
}
.field-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field-row label {
  font-size: 0.75rem;
  color: var(--subtext);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.field-row select,
.field-row input {
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 10px;
  font-size: 0.84rem;
  font-family: inherit;
}
.field-row select:focus,
.field-row input:focus {
  outline: none;
  border-color: var(--accent);
}
.btn-row {
  display: flex;
  gap: 8px;
}
.btn {
  border: none;
  border-radius: 6px;
  padding: 7px 16px;
  font-weight: 700;
  font-size: 0.82rem;
  cursor: pointer;
}
.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.btn.approve {
  background: var(--green);
  color: #0a0c12;
}
.btn.approve:hover:not(:disabled) {
  background: var(--green2);
}
.btn.deny {
  background: var(--red);
  color: #fff;
}
.btn.deny:hover:not(:disabled) {
  background: var(--red2);
}
.warning-banner {
  background: rgba(255, 160, 0, 0.12);
  border: 1px solid #ffaa00;
  border-radius: 6px;
  padding: 9px 12px;
  color: #ffcc55;
  font-size: 0.82rem;
  line-height: 1.5;
}
.warning-banner code {
  background: rgba(255, 255, 255, 0.08);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 0.8rem;
  word-break: break-all;
}
.scope-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  color: var(--text);
}
.scope-label {
  color: var(--subtext);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.scope-summary code {
  background: #0a0c12;
  border: 1px solid var(--border);
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 0.8rem;
  word-break: break-all;
}

/* ── Hardware-wallet block ── */
.hw-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: #0a0c12;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 12px;
}
.hw-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
}
.hw-label {
  color: var(--subtext);
}
.hw-status {
  font-size: 0.74rem;
  color: var(--subtext);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.hw-status.ok {
  color: var(--accent);
}
.hw-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
.btn.scan {
  background: var(--accent);
  color: #fff;
}
.btn.reset {
  background: transparent;
  color: var(--subtext);
  border: 1px solid var(--border);
}
.hw-err {
  color: var(--red2, #ff7676);
  font-size: 0.78rem;
}
.btn.approve:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
