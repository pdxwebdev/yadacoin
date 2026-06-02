<template>
  <div class="loop-panel" :class="{ open: modelValue }">
    <div class="panel-inner">
      <div class="panel-header">
        <h2>&#9889; Agent Loop</h2>
        <button class="close-btn" @click="$emit('update:modelValue', false)">
          &#10005;
        </button>
      </div>

      <p class="intro">
        Describe a goal. The agent will plan multi-step actions using available
        skills, execute each step, and synthesise a final answer.
      </p>

      <!-- ── Goal input ─────────────────────────────────────────────────── -->
      <section>
        <div class="field-group">
          <label>Goal</label>
          <textarea
            v-model="goal"
            :disabled="running"
            placeholder="E.g. Find my open GitHub PRs and draft a status email…"
            rows="3"
            class="goal-input"
          />
        </div>
        <div class="btn-row">
          <button
            class="run-btn"
            :disabled="running || !goal.trim()"
            @click="runLoop"
          >
            {{ running ? "Running\u2026" : "\u26A1 Run" }}
          </button>
          <button
            v-if="events.length && !running"
            class="clear-btn"
            @click="clearOutput"
          >
            Clear
          </button>
        </div>
      </section>

      <!-- ── Available skills ───────────────────────────────────────────── -->
      <section v-if="availableSkills.length">
        <h3>Available skills</h3>
        <div class="skills-pills">
          <span
            v-for="sk in availableSkills"
            :key="sk.id"
            class="skill-pill"
            :title="sk.desc"
          >
            {{ sk.icon }} {{ sk.label }}
          </span>
        </div>
      </section>

      <!-- ── Output ─────────────────────────────────────────────────────── -->
      <section v-if="events.length || running" class="output-section">
        <h3>Output</h3>

        <!-- Status line -->
        <div v-if="statusMsg" class="status-line">
          <span class="spinner">&#9679;</span>
          {{ statusMsg }}
        </div>

        <!-- Plan -->
        <div v-if="plan" class="plan-block">
          <div class="plan-title">&#128203; Plan</div>
          <div v-if="plan.reasoning" class="plan-reasoning">
            {{ plan.reasoning }}
          </div>
          <ol class="plan-steps">
            <li
              v-for="s in plan.steps"
              :key="s.step"
              class="plan-step"
              :class="getStepClass(s.step)"
            >
              <div class="step-header">
                <span class="step-indicator">
                  <span v-if="stepResults[s.step]">&#10003;</span>
                  <span v-else-if="activeSteps.has(s.step)" class="spinner"
                    >&#9679;</span
                  >
                  <span v-else>{{ s.step }}</span>
                </span>
                <span class="step-desc">{{ s.description }}</span>
                <span class="step-badge">{{ s.skill }}/{{ s.action }}</span>
              </div>
              <div v-if="stepResults[s.step]" class="step-result-preview">
                {{ formatResult(stepResults[s.step]) }}
              </div>
            </li>
          </ol>
        </div>

        <!-- Final reply -->
        <div v-if="finalReply" class="final-block">
          <div class="final-title">&#10003; Result</div>
          <div class="final-content" v-html="renderMd(finalReply)"></div>
        </div>

        <!-- Error -->
        <div v-if="errorMsg" class="error-msg">&#9888; {{ errorMsg }}</div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import {
  getLlmSettings,
  getBraveApiKey,
  getNodeUrl,
  getWalletMode,
  LS_PRIV,
  LS_HW_PUB,
} from "../composables/useStorage.js";
import { useWeb2Auth } from "../composables/useWeb2Auth.js";
import { getPublicKeyHex, hex } from "../composables/useCrypto.js";

const props = defineProps({ modelValue: Boolean });
const emit = defineEmits(["update:modelValue"]);

const { activeSessions: web2Sessions } = useWeb2Auth();

// ── Form state ────────────────────────────────────────────────────────────────
const goal = ref("");
const running = ref(false);

// ── Output state ──────────────────────────────────────────────────────────────
const events = ref([]);
const statusMsg = ref("");
const plan = ref(null);
const stepResults = ref({});
const activeSteps = ref(new Set());
const finalReply = ref("");
const errorMsg = ref("");

// ── Available skills (derived from configured services) ───────────────────────
const SKILL_META = {
  web_fetch: {
    id: "web_fetch",
    icon: "&#127760;",
    label: "Web Fetch",
    desc: "Fetch and read any public URL",
  },
  brave_search: {
    id: "brave_search",
    icon: "&#128269;",
    label: "Web Search",
    desc: "Live web search via Brave",
  },
  github: {
    id: "github",
    icon: "&#128008;",
    label: "GitHub",
    desc: "Read repos, issues, PRs",
  },
  microsoft: {
    id: "microsoft",
    icon: "&#129138;",
    label: "Microsoft",
    desc: "Outlook email, Calendar, To Do",
  },
  wallet: {
    id: "wallet",
    icon: "&#128176;",
    label: "Wallet",
    desc: "YadaCoin wallet balance & transactions",
  },
};

const availableSkills = computed(() => {
  const out = [SKILL_META.web_fetch];
  if (getBraveApiKey()) out.push(SKILL_META.brave_search);
  if (web2Sessions.value?.github) out.push(SKILL_META.github);
  if ((web2Sessions.value?.microsoft || []).length)
    out.push(SKILL_META.microsoft);
  out.push(SKILL_META.wallet);
  return out;
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function getPublicKey() {
  const mode = getWalletMode();
  if (mode === "hardware") return localStorage.getItem(LS_HW_PUB) || "";
  const priv = localStorage.getItem(LS_PRIV);
  if (!priv) return "";
  try {
    return getPublicKeyHex(hex.toBytes(priv));
  } catch {
    return "";
  }
}

function getStepClass(stepNum) {
  if (stepResults.value[stepNum]) return "done";
  if (activeSteps.value.has(stepNum)) return "active";
  return "";
}

function formatResult(result) {
  const s =
    typeof result === "string" ? result : JSON.stringify(result, null, 2);
  return s.length > 300 ? s.slice(0, 300) + "…" : s;
}

function renderMd(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

function clearOutput() {
  events.value = [];
  statusMsg.value = "";
  plan.value = null;
  stepResults.value = {};
  activeSteps.value = new Set();
  finalReply.value = "";
  errorMsg.value = "";
}

// ── SSE event handler ─────────────────────────────────────────────────────────
function handleEvent(evt) {
  switch (evt.type) {
    case "status":
      statusMsg.value = evt.message;
      break;
    case "plan":
      plan.value = { reasoning: evt.reasoning, steps: evt.steps || [] };
      break;
    case "step_start":
      activeSteps.value = new Set([...activeSteps.value, evt.step]);
      break;
    case "step_result":
      stepResults.value = { ...stepResults.value, [evt.step]: evt.output };
      activeSteps.value = new Set(
        [...activeSteps.value].filter((s) => s !== evt.step),
      );
      break;
    case "done":
      finalReply.value = evt.reply || "";
      break;
    case "error":
      errorMsg.value = evt.message || evt.error || "Unknown error";
      break;
  }
}

// ── Run the loop ──────────────────────────────────────────────────────────────
async function runLoop() {
  if (!goal.value.trim() || running.value) return;
  clearOutput();
  running.value = true;

  const llmCfg = getLlmSettings();
  const body = {
    mode: "loop",
    goal: goal.value.trim(),
    llm: {
      provider: llmCfg.provider,
      model: llmCfg.model || undefined,
      api_key: llmCfg.api_key || undefined,
      ollama_host: llmCfg.ollama_host || undefined,
      base_url: llmCfg.base_url || undefined,
    },
    brave_api_key: getBraveApiKey() || undefined,
    web2_sessions: Object.keys(web2Sessions.value || {}).length
      ? web2Sessions.value
      : undefined,
    public_key: getPublicKey() || undefined,
  };

  try {
    const resp = await fetch(getNodeUrl() + "/ai-agent-auth/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${resp.status}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep incomplete last line
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;
        try {
          const evt = JSON.parse(raw);
          events.value.push(evt);
          handleEvent(evt);
        } catch {
          // skip malformed lines
        }
      }
    }
  } catch (e) {
    errorMsg.value = String(e);
  } finally {
    running.value = false;
    statusMsg.value = "";
  }
}
</script>

<style scoped>
.loop-panel {
  display: none;
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.4);
}
.loop-panel.open {
  display: block;
}
.panel-inner {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 480px;
  background: var(--surface);
  border-left: 1px solid var(--border);
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
h2 {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  margin: 0;
}
.close-btn {
  background: transparent;
  border: none;
  color: var(--subtext);
  font-size: 1rem;
  cursor: pointer;
  padding: 2px 6px;
  line-height: 1;
  transition: color 0.15s;
}
.close-btn:hover {
  color: var(--text);
}
.intro {
  font-size: 0.75rem;
  color: var(--subtext);
  line-height: 1.5;
  margin: 0;
}
section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
section h3 {
  font-size: 0.78rem;
  color: var(--subtext);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border);
  padding-bottom: 4px;
  margin: 0;
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
}
.goal-input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
  color: var(--text);
  font-size: 0.84rem;
  font-family: inherit;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
  min-height: 70px;
}
.goal-input:focus {
  border-color: var(--accent);
}
.goal-input:disabled {
  opacity: 0.6;
}
.btn-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.run-btn {
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: 6px;
  padding: 8px 18px;
  font-weight: 700;
  font-size: 0.84rem;
  cursor: pointer;
  transition: opacity 0.15s;
}
.run-btn:hover:not(:disabled) {
  opacity: 0.85;
}
.run-btn:disabled {
  opacity: 0.45;
  cursor: default;
}
.clear-btn {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 14px;
  color: var(--text);
  font-size: 0.84rem;
  cursor: pointer;
  transition: border-color 0.15s;
}
.clear-btn:hover {
  border-color: var(--accent);
}
.skills-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.skill-pill {
  font-size: 0.72rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 3px 10px;
  color: var(--subtext);
}
.output-section {
  flex: 1;
}
.status-line {
  font-size: 0.78rem;
  color: var(--accent);
  display: flex;
  align-items: center;
  gap: 6px;
}
.spinner {
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}
.plan-block {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.plan-title {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.plan-reasoning {
  font-size: 0.75rem;
  color: var(--subtext);
  line-height: 1.5;
  font-style: italic;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}
.plan-steps {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.plan-step {
  border-radius: 6px;
  padding: 8px;
  border: 1px solid var(--border);
  background: var(--surface);
  transition: border-color 0.2s;
}
.plan-step.active {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 8%, var(--surface));
}
.plan-step.done {
  border-color: var(--border);
  opacity: 0.85;
}
.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.step-indicator {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--bg);
  border: 1px solid var(--border);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--accent);
  flex-shrink: 0;
}
.plan-step.done .step-indicator {
  background: var(--accent);
  color: var(--bg);
  border-color: var(--accent);
}
.step-desc {
  font-size: 0.78rem;
  color: var(--text);
  flex: 1;
}
.step-badge {
  font-size: 0.65rem;
  font-family: monospace;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
  color: var(--subtext);
  white-space: nowrap;
}
.step-result-preview {
  font-size: 0.7rem;
  font-family: monospace;
  color: var(--subtext);
  margin-top: 6px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 80px;
  overflow: hidden;
  background: var(--bg);
  border-radius: 4px;
  padding: 4px 6px;
}
.final-block {
  margin-top: 12px;
  background: color-mix(in srgb, var(--accent) 6%, var(--surface));
  border: 1px solid var(--accent);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.final-title {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.final-content {
  font-size: 0.82rem;
  color: var(--text);
  line-height: 1.6;
}
.final-content code {
  background: var(--bg);
  border-radius: 3px;
  padding: 1px 4px;
  font-size: 0.78rem;
}
.error-msg {
  margin-top: 8px;
  font-size: 0.78rem;
  color: #e06c75;
  background: rgba(224, 108, 117, 0.1);
  border: 1px solid rgba(224, 108, 117, 0.3);
  border-radius: 6px;
  padding: 8px 10px;
}
</style>
