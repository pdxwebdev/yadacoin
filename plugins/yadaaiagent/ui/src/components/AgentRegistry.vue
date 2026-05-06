<template>
  <div class="registry-shell">
    <!-- ── Tab bar ─────────────────────────────────────── -->
    <div class="tab-bar">
      <button
        :class="['tab-btn', { active: tab === 'discover' }]"
        @click="tab = 'discover'"
      >
        🔍 Discover Agents
      </button>
      <button
        :class="['tab-btn', { active: tab === 'register' }]"
        @click="tab = 'register'"
      >
        📡 Register Agent
      </button>
    </div>

    <!-- ── Discover ─────────────────────────────────────── -->
    <div v-if="tab === 'discover'" class="panel">
      <p class="panel-hint">
        Search the blockchain for AI agents that can handle your intent. Agents
        are registered on-chain with their capabilities and endpoint URLs.
      </p>

      <div class="search-row">
        <input
          v-model="intent"
          class="input"
          placeholder="Describe what you need… e.g. book a hotel in Paris"
          @keyup.enter="discover"
        />
        <select v-model="discoverTypeFilter" class="input select-sm">
          <option value="">All types</option>
          <option v-for="at in agentTypes" :key="at.id" :value="at.id">
            {{ at.icon }} {{ at.label }}
          </option>
        </select>
        <button class="btn-primary" :disabled="discovering" @click="discover">
          {{ discovering ? "Searching…" : "Search" }}
        </button>
      </div>

      <div v-if="discoverError" class="error-box">{{ discoverError }}</div>

      <div v-if="discovered.length === 0 && discoverRan" class="empty-state">
        No agents found for that intent.
      </div>

      <div class="agent-grid">
        <div
          v-for="agent in discovered"
          :key="agent.agent_id"
          class="agent-card"
        >
          <div class="card-icon">{{ agent.icon || "🤖" }}</div>
          <div class="card-body">
            <div class="card-label">{{ agent.label }}</div>
            <div class="card-desc">{{ agent.description }}</div>
            <div class="card-caps">
              <span
                v-for="cap in agent.capabilities"
                :key="cap"
                class="cap-chip"
                >{{ cap }}</span
              >
            </div>
            <div class="card-meta">
              <span class="meta-item"
                >🌐
                <a :href="agent.endpoint_url" target="_blank" rel="noopener">{{
                  agent.endpoint_url
                }}</a></span
              >
              <span class="meta-item">⛓ block {{ agent.block_height }}</span>
            </div>
            <div
              class="card-identity"
              v-if="agent.identity && agent.identity.username"
            >
              Registered by: <strong>{{ agent.identity.username }}</strong>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Register ─────────────────────────────────────── -->
    <div v-if="tab === 'register'" class="panel">
      <p class="panel-hint">
        Register your AI agent on the YadaCoin blockchain. The node's KEL
        identity signs the transaction — other nodes will discover it when
        searching for agents that match your declared capabilities.
      </p>

      <form class="reg-form" @submit.prevent="registerAgent">
        <label class="field">
          <span class="field-label"
            >Agent Label <span class="req">*</span></span
          >
          <input
            v-model="form.label"
            class="input"
            placeholder="e.g. My Travel Agent"
            required
          />
        </label>

        <label class="field">
          <span class="field-label">Description</span>
          <textarea
            v-model="form.description"
            class="input textarea"
            placeholder="What does this agent do?"
            rows="2"
          />
        </label>

        <label class="field">
          <span class="field-label">Agent Type</span>
          <select v-model="form.agent_type" class="input">
            <option v-for="at in agentTypes" :key="at.id" :value="at.id">
              {{ at.icon }} {{ at.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <span class="field-label">
            Capabilities
            <span class="field-hint">(comma-separated intent keywords)</span>
          </span>
          <input
            v-model="capsInput"
            class="input"
            placeholder="e.g. travel, flight, hotel, car"
          />
        </label>

        <label class="field">
          <span class="field-label"
            >Endpoint URL <span class="req">*</span></span
          >
          <input
            v-model="form.endpoint_url"
            class="input"
            placeholder="https://your-node.example.com/ai-agent-auth"
            type="url"
            required
          />
        </label>

        <label class="field">
          <span class="field-label"
            >Icon <span class="field-hint">(emoji)</span></span
          >
          <input
            v-model="form.icon"
            class="input input-sm"
            placeholder="🤖"
            maxlength="8"
          />
        </label>

        <div v-if="regError" class="error-box">{{ regError }}</div>
        <div v-if="regSuccess" class="success-box">
          <strong>✅ Agent registered!</strong><br />
          Agent ID: <code>{{ regResult.agent_id }}</code
          ><br />
          Transaction:
          <code>{{ regResult.transaction_signature?.slice(0, 32) }}…</code>
        </div>

        <button class="btn-primary" type="submit" :disabled="registering">
          {{ registering ? "Broadcasting…" : "📡 Register on Blockchain" }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import { getNodeUrl } from "../composables/useStorage.js";

const props = defineProps({
  agentTypes: { type: Array, default: () => [] },
});

const tab = ref("discover");

// ── Discover state ────────────────────────────────────────────────────────────
const intent = ref("");
const discoverTypeFilter = ref("");
const discovered = ref([]);
const discovering = ref(false);
const discoverError = ref("");
const discoverRan = ref(false);

async function discover() {
  discoverError.value = "";
  discovering.value = true;
  discoverRan.value = false;
  try {
    const params = new URLSearchParams({ intent: intent.value, limit: "20" });
    if (discoverTypeFilter.value)
      params.set("agent_type", discoverTypeFilter.value);
    const res = await fetch(
      `${getNodeUrl()}/ai-agent-auth/api/agents/discover?${params}`,
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    const data = await res.json();
    discovered.value = data.agents || [];
    discoverRan.value = true;
  } catch (e) {
    discoverError.value = e.message;
  } finally {
    discovering.value = false;
  }
}

// ── Register state ────────────────────────────────────────────────────────────
const form = ref({
  label: "",
  description: "",
  agent_type: "general",
  endpoint_url: "",
  icon: "🤖",
});
const capsInput = ref("");
const registering = ref(false);
const regError = ref("");
const regSuccess = ref(false);
const regResult = ref({});

async function registerAgent() {
  regError.value = "";
  regSuccess.value = false;
  registering.value = true;
  try {
    const capabilities = capsInput.value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const res = await fetch(
      `${getNodeUrl()}/ai-agent-auth/api/agents/register`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form.value, capabilities }),
      },
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    regResult.value = data;
    regSuccess.value = true;
  } catch (e) {
    regError.value = e.message;
  } finally {
    registering.value = false;
  }
}
</script>

<style scoped>
.registry-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.tab-btn {
  flex: 1;
  padding: 10px 16px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--subtext);
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.15s;
}
.tab-btn.active {
  color: var(--accent2);
  border-bottom-color: var(--accent2);
}
.tab-btn:hover:not(.active) {
  color: var(--text);
}

.panel {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-hint {
  font-size: 0.8rem;
  color: var(--subtext);
  line-height: 1.5;
  margin: 0;
}

.search-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.search-row .input {
  flex: 1;
}
.select-sm {
  flex: 0 0 160px;
}

.input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  padding: 8px 10px;
  font-size: 0.85rem;
  outline: none;
}
.input:focus {
  border-color: var(--accent);
}
.textarea {
  resize: vertical;
  min-height: 52px;
}
.input-sm {
  max-width: 80px;
}

.btn-primary {
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 0.85rem;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}
.btn-primary:hover:not(:disabled) {
  background: var(--accent2);
  color: var(--bg);
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: default;
}

.error-box {
  background: rgba(220, 38, 38, 0.1);
  border: 1px solid var(--red);
  border-radius: 6px;
  color: var(--red2);
  padding: 8px 12px;
  font-size: 0.82rem;
}
.success-box {
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid var(--green);
  border-radius: 6px;
  color: var(--green2);
  padding: 8px 12px;
  font-size: 0.82rem;
  line-height: 1.6;
}
.success-box code {
  font-family: monospace;
  font-size: 0.78rem;
}

.empty-state {
  text-align: center;
  color: var(--subtext);
  padding: 32px 0;
  font-size: 0.85rem;
}

.agent-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.agent-card {
  display: flex;
  gap: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
}
.card-icon {
  font-size: 1.6rem;
  flex-shrink: 0;
  line-height: 1;
  padding-top: 2px;
}
.card-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.card-label {
  font-weight: 600;
  color: var(--text);
  font-size: 0.9rem;
}
.card-desc {
  font-size: 0.8rem;
  color: var(--subtext);
  line-height: 1.4;
}
.card-caps {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}
.cap-chip {
  background: rgba(124, 58, 237, 0.18);
  border: 1px solid rgba(124, 58, 237, 0.35);
  color: var(--accent2);
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 0.73rem;
}
.card-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 2px;
}
.meta-item {
  font-size: 0.75rem;
  color: var(--muted);
}
.meta-item a {
  color: var(--accent2);
  text-decoration: none;
}
.meta-item a:hover {
  text-decoration: underline;
}
.card-identity {
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: 2px;
}

/* Register form */
.reg-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field-label {
  font-size: 0.8rem;
  color: var(--subtext);
  font-weight: 500;
}
.field-hint {
  font-weight: 400;
  color: var(--muted);
}
.req {
  color: var(--red2);
}
</style>
