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

    <template v-if="!isRegistration">
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

    <div class="btn-row">
      <button class="btn approve" :disabled="busy" @click="approve">
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
import { getPaymentMethods } from "../composables/useStorage.js";

const props = defineProps({
  agentType: Object,
  scope: Object,
});
const emit = defineEmits(["approve", "deny"]);

const isRegistration = computed(
  () => props.agentType?.id === "agent_registration",
);
const isNodeConfig = computed(() => props.agentType?.id === "node_config");
const isWalletAgent = computed(() => props.agentType?.id === "wallet_agent");
const skipPayment = computed(
  () => isRegistration.value || isNodeConfig.value || isWalletAgent.value,
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
onMounted(() => setTimeout(() => sfInput.value?.focus(), 50));

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

function approve() {
  if (!isRegistration.value && !secondFactor.value) {
    sfInput.value?.focus();
    return;
  }
  const pm = paymentMethods.value[selectedPmIdx.value] || null;
  busy.value = true;
  emit("approve", {
    secondFactor: secondFactor.value,
    paymentMethod: skipPayment.value ? null : pm,
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
</style>
