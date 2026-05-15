<template>
  <div class="cw-drawer" :class="{ open: modelValue }" @click.self="close">
    <div class="cw-inner">
      <div class="cw-header">
        <h2>&#127760; Credential Wallet</h2>
        <button class="cw-close" @click="close">&#10005;</button>
      </div>

      <div v-if="!credentials.length" class="cw-empty">
        No credentials yet.<br />
        <span class="cw-hint"
          >Credentials are issued automatically when a booking is
          confirmed.</span
        >
      </div>

      <div v-else class="cw-list">
        <div
          v-for="cred in credentials"
          :key="cred.id"
          class="cw-card"
          :class="serviceClass(cred)"
        >
          <div class="cw-card-header">
            <span class="cw-service-badge">{{ serviceLabel(cred) }}</span>
            <span
              v-if="cred.proof"
              class="cw-signed-badge"
              title="Cryptographically signed"
              >✓ signed</span
            >
            <span class="cw-date">{{ formatDate(cred.issuanceDate) }}</span>
            <button class="cw-delete" title="Delete" @click="remove(cred.id)">
              &#128465;
            </button>
          </div>

          <div class="cw-vendor">
            {{ cred.issuer?.name || cred.credentialSubject?.vendor }}
          </div>
          <div class="cw-confirmation">
            <span class="cw-label">Confirmation</span>
            <code>{{ cred.credentialSubject?.confirmation }}</code>
          </div>

          <div class="cw-scope-toggle" @click="toggleExpand(cred.id)">
            {{ expanded.has(cred.id) ? "▲ Hide details" : "▼ Show details" }}
          </div>
          <div v-if="expanded.has(cred.id)" class="cw-scope">
            <template v-if="bookingEntries(cred).length">
              <div
                v-for="[k, v] in bookingEntries(cred)"
                :key="k"
                class="cw-scope-row"
              >
                <span class="cw-scope-key">{{ k.replace(/_/g, " ") }}</span>
                <span class="cw-scope-val">{{ formatVal(v) }}</span>
              </div>
              <div class="cw-scope-section-label">Authorized scope</div>
            </template>
            <div
              v-for="[k, v] in scopeEntries(cred)"
              :key="k"
              class="cw-scope-row cw-scope-muted"
            >
              <span class="cw-scope-key">{{ k.replace(/_/g, " ") }}</span>
              <span class="cw-scope-val">{{ formatVal(v) }}</span>
            </div>
            <div class="cw-credential-id">
              <span class="cw-label">Credential ID</span>
              <code class="cw-id-code">{{ cred.id }}</code>
            </div>
          </div>
        </div>
      </div>

      <div class="cw-footer">
        <button class="cw-resync-btn" :disabled="resyncing" @click="doResync">
          {{ resyncing ? "Syncing\u2026" : "\u21bb Resync from chain" }}
        </button>
        <button
          v-if="credentials.length"
          class="cw-clear-btn"
          @click="clearAll"
        >
          Clear all
        </button>
        <span v-if="resyncMsg" class="cw-resync-msg">{{ resyncMsg }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import {
  getBookingCredentials,
  deleteBookingCredential,
  saveBookingCredential,
  LS_BOOKING_CREDENTIALS,
} from "../composables/useStorage.js";
import { resyncCredentials } from "../composables/useCredentialReceipts.js";

const props = defineProps({ modelValue: Boolean });
const emit = defineEmits(["update:modelValue"]);

// Reactive list — reload from localStorage every time the drawer opens
const credentials = ref([]);
const expanded = ref(new Set());

// Watch for open
import { watch } from "vue";
watch(
  () => props.modelValue,
  (v) => {
    if (v) reload();
  },
  { immediate: true },
);

function reload() {
  credentials.value = getBookingCredentials();
  expanded.value = new Set();
}

function close() {
  emit("update:modelValue", false);
}

function remove(id) {
  deleteBookingCredential(id);
  reload();
}

const resyncing = ref(false);
const resyncMsg = ref("");

async function doResync() {
  resyncing.value = true;
  resyncMsg.value = "";
  try {
    const vcs = await resyncCredentials();
    let added = 0;
    for (const vc of vcs) {
      const before = getBookingCredentials().find((c) => c.id === vc.id);
      saveBookingCredential(vc);
      if (!before) added++;
    }
    reload();
    resyncMsg.value =
      vcs.length === 0
        ? "No receipts found on chain."
        : `Found ${vcs.length} receipt${vcs.length > 1 ? "s" : ""}, ${added} new.`;
  } catch (e) {
    resyncMsg.value = "Resync failed: " + String(e);
  } finally {
    resyncing.value = false;
  }
}

function clearAll() {
  localStorage.removeItem(LS_BOOKING_CREDENTIALS);
  reload();
}

function toggleExpand(id) {
  const s = new Set(expanded.value);
  s.has(id) ? s.delete(id) : s.add(id);
  expanded.value = s;
}

const SERVICE_LABELS = {
  flight: "✈ Flight",
  train: "🚆 Train",
  ship: "🚢 Cruise",
  hotel: "🏨 Hotel",
  car: "🚗 Car Rental",
  legal: "⚖ Legal",
  ecommerce: "🛒 Order",
  therapist: "🧠 Therapy",
};

function serviceLabel(cred) {
  const svc = cred.credentialSubject?.service || "";
  return SERVICE_LABELS[svc] || "📄 " + svc;
}

function serviceClass(cred) {
  return "svc-" + (cred.credentialSubject?.service || "other");
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function scopeEntries(cred) {
  const scope = cred.credentialSubject?.scope || {};
  const skip = new Set(["holder", "services"]);
  return Object.entries(scope).filter(
    ([k, v]) => !skip.has(k) && v != null && v !== "",
  );
}

function bookingEntries(cred) {
  const details = cred.credentialSubject?.bookingDetails || {};
  return Object.entries(details).filter(([, v]) => v != null && v !== "");
}

function formatVal(v) {
  if (Array.isArray(v)) return v.join(", ");
  if (v === null || v === undefined) return "—";
  return String(v);
}
</script>

<style scoped>
.cw-drawer {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  justify-content: flex-end;
  pointer-events: none;
}
.cw-drawer.open {
  pointer-events: all;
  background: rgba(0, 0, 0, 0.45);
}
.cw-inner {
  width: 420px;
  max-width: 100vw;
  background: var(--surface);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 0.25s ease;
  height: 100%;
  overflow: hidden;
}
.cw-drawer.open .cw-inner {
  transform: translateX(0);
}

.cw-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.cw-header h2 {
  font-size: 15px;
  color: var(--text);
}
.cw-close {
  background: none;
  border: none;
  color: var(--subtext);
  font-size: 16px;
  cursor: pointer;
}
.cw-close:hover {
  color: var(--text);
}

.cw-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--subtext);
  font-size: 13px;
  text-align: center;
  padding: 24px;
}
.cw-hint {
  font-size: 11px;
  color: var(--muted);
}

.cw-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cw-card {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  border-left: 3px solid var(--accent2);
}
.cw-card.svc-flight {
  border-left-color: #38bdf8;
}
.cw-card.svc-train {
  border-left-color: #facc15;
}
.cw-card.svc-ship {
  border-left-color: #2dd4bf;
}
.cw-card.svc-hotel {
  border-left-color: #fb923c;
}
.cw-card.svc-car {
  border-left-color: #4ade80;
}
.cw-card.svc-legal {
  border-left-color: #a78bfa;
}
.cw-card.svc-ecommerce {
  border-left-color: #f472b6;
}
.cw-card.svc-therapist {
  border-left-color: #67e8f9;
}

.cw-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.cw-service-badge {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent2);
  flex: 1;
}
.cw-signed-badge {
  font-size: 10px;
  font-weight: 600;
  color: #22c55e;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 4px;
  padding: 1px 5px;
  margin-right: 6px;
}
.cw-date {
  font-size: 11px;
  color: var(--muted);
}
.cw-delete {
  background: none;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 13px;
  padding: 0 2px;
}
.cw-delete:hover {
  color: var(--red2);
}

.cw-vendor {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 6px;
}
.cw-confirmation {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.cw-label {
  font-size: 11px;
  color: var(--subtext);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.cw-confirmation code {
  font-size: 13px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
  color: var(--green2);
  letter-spacing: 0.08em;
}

.cw-scope-toggle {
  font-size: 11px;
  color: var(--accent2);
  cursor: pointer;
  user-select: none;
}
.cw-scope-toggle:hover {
  text-decoration: underline;
}

.cw-scope {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cw-scope-row {
  display: flex;
  gap: 8px;
  font-size: 12px;
}
.cw-scope-key {
  color: var(--subtext);
  text-transform: capitalize;
  min-width: 100px;
  flex-shrink: 0;
}
.cw-scope-val {
  color: var(--text);
  word-break: break-word;
}

.cw-scope-section-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--muted);
  margin: 6px 0 2px;
}
.cw-scope-row.cw-scope-muted .cw-scope-key,
.cw-scope-row.cw-scope-muted .cw-scope-val {
  color: var(--muted);
  font-size: 11px;
}

.cw-credential-id {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cw-id-code {
  font-size: 10px;
  color: var(--muted);
  word-break: break-all;
}

.cw-footer {
  padding: 10px 12px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}
.cw-clear-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--subtext);
  border-radius: 6px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
}
.cw-clear-btn:hover {
  border-color: var(--red);
  color: var(--red2);
}
.cw-resync-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--subtext);
  border-radius: 6px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
}
.cw-resync-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.cw-resync-btn:not(:disabled):hover {
  border-color: var(--accent);
  color: var(--accent);
}
.cw-resync-msg {
  font-size: 11px;
  color: var(--subtext);
  margin-left: 6px;
}
</style>
