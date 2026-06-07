<template>
  <div class="chat-window" ref="chatEl">
    <div
      v-for="(msg, i) in messages"
      :key="i"
      class="msg-row"
      :class="msg.role"
    >
      <div class="avatar">{{ msg.role === "user" ? "You" : "AI" }}</div>
      <div class="bubble-wrap">
        <div
          class="bubble"
          :class="{ thinking: msg.thinking }"
          v-html="renderBubble(msg)"
        ></div>
        <button
          v-if="msg.role === 'user'"
          class="replay-btn"
          title="Edit & resend"
          @click="emit('replay', msg.content)"
        >
          ↩ reuse
        </button>
        <div v-if="msg.choices?.length" class="choice-form">
          <!-- Each element in choices is one input group -->
          <div
            v-for="(group, gi) in msg.choices"
            :key="gi"
            class="choice-group"
          >
            <div class="choice-group-label">{{ group.choice_text }}</div>
            <!-- Option select: radio or checkbox -->
            <template v-if="group.options?.length">
              <label
                v-for="(opt, oi) in group.options"
                :key="oi"
                class="choice-label"
              >
                <input
                  v-if="!group.multi"
                  type="radio"
                  :name="`choice-${i}-${gi}`"
                  :value="opt.id"
                  v-model="msg.selections[group.id]"
                  class="choice-input"
                />
                <input
                  v-else
                  type="checkbox"
                  :value="opt.id"
                  v-model="msg.selections[group.id]"
                  class="choice-input"
                />
                <span>{{ opt.text }}</span>
              </label>
            </template>
            <!-- Free-text or date input -->
            <template v-else-if="group.input_type">
              <input
                :type="group.input_type"
                v-model="msg.selections[group.id]"
                class="date-field-input"
                :placeholder="
                  group.input_type === 'text' ? group.choice_text : ''
                "
              />
            </template>
          </div>
          <!-- Single Confirm for everything -->
          <button
            class="choice-confirm-btn"
            :disabled="!allGroupsFilled(msg)"
            @click="confirmAll(msg)"
          >
            Confirm
          </button>
        </div>
        <!-- Confirmation gate for destructive agent actions -->
        <div v-if="msg.confirmPending" class="confirm-gate">
          <div class="cg-title">⚠ Confirm Actions</div>
          <p class="cg-message">{{ msg.confirmPending.message }}</p>
          <ul class="cg-steps">
            <li
              v-for="s in msg.confirmPending.destructive_steps"
              :key="s.step"
              class="cg-step"
            >
              <span class="cg-step-badge">{{ s.skill }}/{{ s.action }}</span>
              {{ s.description }}
              <div
                v-if="s.params && Object.keys(s.params).length"
                class="cg-params"
              >
                <span v-for="(v, k) in s.params" :key="k" class="cg-param"
                  ><strong>{{ k }}</strong
                  >: {{ v }}</span
                >
              </div>
            </li>
          </ul>
          <div v-if="msg.confirmPending.needs_second_factor" class="cg-sf-row">
            <label class="cg-sf-label">Second factor (passphrase)</label>
            <input
              :id="'cg-sf-' + i"
              type="password"
              class="cg-sf-input"
              placeholder="Enter your second factor…"
              v-model="confirmSecondFactors[i]"
              @keydown.enter.prevent="
                msg.confirmPending.onConfirm(confirmSecondFactors[i])
              "
            />
          </div>
          <div class="cg-buttons">
            <button
              class="cg-confirm-btn"
              @click="
                msg.confirmPending.onConfirm(
                  msg.confirmPending.needs_second_factor
                    ? confirmSecondFactors[i]
                    : undefined,
                )
              "
              :disabled="
                msg.confirmPending.needs_second_factor &&
                !confirmSecondFactors[i]
              "
            >
              Confirm &amp; Run
            </button>
            <button
              class="cg-cancel-btn"
              @click="msg.confirmPending.onCancel()"
            >
              Cancel
            </button>
          </div>
        </div>
        <div v-if="msg.searchSources?.length" class="sources-row">
          <button class="sources-toggle" @click="toggleSources(i)">
            🔍 {{ openSources[i] ? "Hide" : "Show" }}
            {{ msg.searchSources.length }} web source{{
              msg.searchSources.length !== 1 ? "s" : ""
            }}
          </button>
          <div v-if="openSources[i]" class="sources-list">
            <a
              v-for="(src, j) in msg.searchSources"
              :key="j"
              :href="src.url"
              target="_blank"
              rel="noopener noreferrer"
              class="source-item"
              >{{ src.title || src.url }}</a
            >
          </div>
        </div>
        <!-- Web 2.0 auth connect button (triggers device flow) -->
        <div v-if="msg.authRequired?.provider" class="auth-required-row">
          <button
            class="auth-connect-btn"
            @click="
              emit('auth-connect', { provider: msg.authRequired.provider })
            "
          >
            <span class="auth-provider-icon">{{
              providerIcon(msg.authRequired.provider)
            }}</span>
            Connect {{ providerLabel(msg.authRequired.provider) }}
          </button>
        </div>
        <!-- Device Authorization Grant card — shown while user completes auth -->
        <div v-if="msg.deviceCode" class="device-code-card">
          <div class="dc-header">
            <span class="dc-icon">{{
              providerIcon(msg.deviceCode.provider)
            }}</span>
            <span class="dc-title"
              >Connect {{ providerLabel(msg.deviceCode.provider) }}</span
            >
          </div>
          <template v-if="msg.deviceCode.status === 'starting'">
            <div class="dc-status">
              {{ msg.deviceCode.message || "Starting…" }}
            </div>
          </template>
          <template v-else-if="msg.deviceCode.status === 'needs_rotation'">
            <div class="dc-instructions">
              A key rotation is required to bind this account to the YadaCoin
              blockchain. Enter your second factor to proceed.
            </div>
            <input
              :value="msg.deviceCode.sfValue"
              @input="msg.deviceCode.sfValue = $event.target.value"
              @keydown.enter="
                msg.deviceCode.onApprove &&
                msg.deviceCode.onApprove(msg.deviceCode.sfValue)
              "
              type="password"
              class="dc-sf-input"
              placeholder="Second factor"
              autocomplete="current-password"
            />
            <button
              class="dc-connect-btn"
              @click="
                msg.deviceCode.onApprove &&
                msg.deviceCode.onApprove(msg.deviceCode.sfValue)
              "
            >
              🔐 Rotate &amp; Connect
            </button>
          </template>
          <template v-else-if="msg.deviceCode.status === 'pending'">
            <div class="dc-instructions">
              Visit
              <a
                :href="msg.deviceCode.verification_uri"
                target="_blank"
                rel="noopener noreferrer"
                class="dc-link"
                >{{ msg.deviceCode.verification_uri }}</a
              >
              and enter this code:
            </div>
            <div class="dc-code">{{ msg.deviceCode.user_code }}</div>
            <div class="dc-status dc-waiting">
              <span class="dc-spinner">⟳</span> Waiting for authorization…
            </div>
          </template>
          <template v-else-if="msg.deviceCode.status === 'authorized'">
            <div class="dc-status dc-success">✓ Connected successfully</div>
          </template>
          <template v-else-if="msg.deviceCode.status === 'error'">
            <div class="dc-status dc-error">⚠ {{ msg.deviceCode.message }}</div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from "vue";
import { marked } from "marked";
import DOMPurify from "dompurify";

marked.setOptions({ breaks: true, gfm: true });

const openSources = ref({});
function toggleSources(i) {
  openSources.value[i] = !openSources.value[i];
}

// Keyed by message index — stores the second-factor value entered by the user
// in the confirm gate when needs_second_factor is true.
const confirmSecondFactors = ref({});

const PURIFY_CONFIG = {
  ALLOWED_TAGS: [
    "p",
    "br",
    "strong",
    "em",
    "b",
    "i",
    "s",
    "del",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "blockquote",
    "hr",
    "pre",
    "code",
    "a",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "span",
    "div",
  ],
  ALLOWED_ATTR: ["href", "target", "rel", "class", "style"],
  ALLOW_DATA_ATTR: false,
  FORCE_BODY: false,
};

function sanitize(html) {
  return DOMPurify.sanitize(html, PURIFY_CONFIG);
}

marked.setOptions({ breaks: true, gfm: true });

const props = defineProps({ messages: Array });
const emit = defineEmits(["fields-confirmed", "auth-connect", "replay"]);

const _PROVIDER_META = {
  github: { label: "GitHub", icon: "🐙" },
  microsoft: { label: "Microsoft", icon: "🟦" },
};
function providerLabel(p) {
  return (_PROVIDER_META[p] || {}).label || p;
}
function providerIcon(p) {
  return (_PROVIDER_META[p] || {}).icon || "🔑";
}

function allGroupsFilled(msg) {
  if (!msg.choices?.length) return false;
  return msg.choices.every((group) => {
    const val = msg.selections?.[group.id];
    if (group.options?.length) {
      // radio: non-empty string; checkbox: non-empty array
      return group.multi ? Array.isArray(val) && val.length > 0 : !!val;
    }
    // text/date input
    return typeof val === "string" && val.trim() !== "";
  });
}

function confirmAll(msg) {
  const parts = [];
  for (const group of msg.choices || []) {
    const val = msg.selections?.[group.id];
    if (group.options?.length) {
      if (group.multi && Array.isArray(val) && val.length)
        parts.push(`${group.choice_text}: ${val.join(", ")}`);
      else if (!group.multi && val) parts.push(`${group.choice_text}: ${val}`);
    } else if (val?.trim()) {
      parts.push(`${group.choice_text}: ${val.trim()}`);
    }
  }
  if (parts.length) emit("fields-confirmed", parts.join(" | "));
}
const chatEl = ref(null);

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderBubble(msg) {
  if (msg.thinking) return msg.html;
  if (msg.role === "user") return msg.html || escHtml(msg.content);
  // Agent messages: sanitize everything through DOMPurify regardless of source.
  if (msg.html) return sanitize(msg.html);
  return sanitize(marked.parse(msg.content || ""));
}

watch(
  () => props.messages.length,
  () =>
    nextTick(() => {
      if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight;
    }),
);

defineExpose({ chatEl, escHtml });
</script>

<style scoped>
.chat-window {
  flex: 1 1 0;
  overflow-y: auto;
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
.msg-row {
  display: flex;
  padding: 6px 20px;
  gap: 12px;
  align-items: flex-start;
}
.msg-row.user {
  flex-direction: row-reverse;
}
.msg-row.agent {
  flex-direction: row;
}
.bubble-wrap {
  display: flex;
  flex-direction: column;
  max-width: 72%;
  gap: 4px;
}
.sources-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sources-toggle {
  align-self: flex-start;
  background: none;
  border: 1px solid var(--border);
  border-radius: 20px;
  color: var(--subtext);
  cursor: pointer;
  font-size: 0.75rem;
  padding: 2px 10px;
  font-family: inherit;
  transition:
    border-color 0.15s,
    color 0.15s;
}
.sources-toggle:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.sources-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 4px 0 2px 4px;
}
.source-item {
  font-size: 0.76rem;
  color: var(--accent);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 340px;
}
.source-item:hover {
  text-decoration: underline;
}
.choice-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 8px;
  padding: 10px 14px;
  background: var(--agent-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.choice-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.choice-group-label {
  font-size: 0.8rem;
  color: var(--subtext);
  font-weight: 600;
  letter-spacing: 0.02em;
  margin-bottom: 2px;
}
.choice-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: var(--text);
  cursor: pointer;
  padding: 3px 0;
}
.choice-label:hover span {
  color: var(--accent);
}
.choice-input[type="radio"],
.choice-input[type="checkbox"] {
  appearance: none;
  -webkit-appearance: none;
  width: 15px;
  height: 15px;
  border: 1.5px solid var(--border);
  background: transparent;
  cursor: pointer;
  flex-shrink: 0;
  position: relative;
  transition: border-color 0.15s;
}
.choice-input[type="radio"] {
  border-radius: 50%;
}
.choice-input[type="checkbox"] {
  border-radius: 3px;
}
.choice-input:checked {
  border-color: var(--accent);
  background: var(--accent);
}
.choice-input[type="radio"]:checked::after {
  content: "";
  position: absolute;
  inset: 3px;
  background: #0d111a;
  border-radius: 50%;
}
.choice-input[type="checkbox"]:checked::after {
  content: "✓";
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #0d111a;
  font-weight: 700;
  line-height: 1;
  padding-left: 1px;
}
.choice-confirm-btn {
  align-self: flex-start;
  margin-top: 4px;
  background: var(--accent);
  border: none;
  border-radius: 6px;
  color: #0d111a;
  cursor: pointer;
  font-size: 0.82rem;
  font-family: inherit;
  font-weight: 600;
  padding: 5px 16px;
  transition: opacity 0.15s;
}
.choice-confirm-btn:disabled {
  opacity: 0.35;
  cursor: default;
}
.choice-confirm-btn:not(:disabled):hover {
  opacity: 0.85;
}
/* ── Confirmation gate ────────────────────────────────────────────────── */
.confirm-gate {
  margin-top: 10px;
  border: 1px solid #e07b00;
  border-radius: 8px;
  padding: 12px 14px;
  background: rgba(224, 123, 0, 0.08);
}
.cg-title {
  font-weight: 700;
  font-size: 0.9rem;
  color: #e07b00;
  margin-bottom: 6px;
}
.cg-message {
  font-size: 0.82rem;
  margin: 0 0 8px;
  color: var(--fg, #e0e0e0);
}
.cg-steps {
  list-style: none;
  padding: 0;
  margin: 0 0 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cg-step {
  font-size: 0.82rem;
  color: var(--fg, #e0e0e0);
}
.cg-step-badge {
  display: inline-block;
  background: rgba(224, 123, 0, 0.2);
  border-radius: 4px;
  padding: 1px 6px;
  font-family: monospace;
  font-size: 0.78rem;
  margin-right: 6px;
  color: #e07b00;
}
.cg-params {
  margin-top: 3px;
  padding-left: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.cg-param {
  font-size: 0.77rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  padding: 1px 6px;
  font-family: monospace;
}
.cg-sf-row {
  margin: 8px 0 4px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cg-sf-label {
  font-size: 0.75rem;
  color: var(--text-muted, #8b949e);
}
.cg-sf-input {
  background: var(--bg, #0d1117);
  border: 1px solid var(--border, #30363d);
  border-radius: 6px;
  color: var(--text, #e6edf3);
  font-family: inherit;
  font-size: 0.82rem;
  padding: 5px 10px;
  width: 100%;
  box-sizing: border-box;
}
.cg-sf-input:focus {
  outline: none;
  border-color: var(--accent, #1f6feb);
}
.cg-buttons {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
.cg-confirm-btn {
  background: #e07b00;
  border: none;
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
  font-size: 0.82rem;
  font-family: inherit;
  font-weight: 600;
  padding: 5px 16px;
  transition: opacity 0.15s;
}
.cg-confirm-btn:hover {
  opacity: 0.85;
}
.cg-cancel-btn {
  background: transparent;
  border: 1px solid #888;
  border-radius: 6px;
  color: #aaa;
  cursor: pointer;
  font-size: 0.82rem;
  font-family: inherit;
  padding: 5px 14px;
  transition: opacity 0.15s;
}
.cg-cancel-btn:hover {
  opacity: 0.7;
}
/* ── Replay button ────────────────────────────────────────────────────── */
.replay-btn {
  align-self: flex-end;
  background: none;
  border: 1px solid var(--border);
  border-radius: 20px;
  color: var(--subtext);
  cursor: pointer;
  font-size: 0.7rem;
  font-family: inherit;
  padding: 1px 8px;
  margin-top: 2px;
  transition:
    border-color 0.15s,
    color 0.15s;
  line-height: 1.6;
}
.replay-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.date-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
  padding: 10px 14px;
  background: var(--agent-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.date-field-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.date-field-label {
  font-size: 0.78rem;
  color: var(--subtext);
  font-weight: 600;
  letter-spacing: 0.02em;
}
.date-field-input {
  background: var(--input-bg, #0d111a);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-family: inherit;
  font-size: 0.85rem;
  padding: 5px 10px;
  outline: none;
  transition: border-color 0.15s;
  color-scheme: dark;
}
.date-field-input:focus {
  border-color: var(--accent);
}
.avatar {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 700;
}
.user .avatar {
  background: #553c9a;
  color: var(--accent2);
}
.agent .avatar {
  background: #1e293b;
  color: var(--accent);
  border: 1px solid var(--border);
}
.bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 0.88rem;
  line-height: 1.55;
  word-break: break-word;
}
.user .bubble {
  background: var(--user-bg);
  color: var(--accent2);
  border-radius: 12px 2px 12px 12px;
}
.agent .bubble {
  background: var(--agent-bg);
  color: var(--text);
  border-radius: 2px 12px 12px 12px;
  border: 1px solid var(--border);
}
.bubble.thinking {
  color: var(--subtext);
  font-style: italic;
}
.bubble :deep(code) {
  font-family: "SF Mono", Consolas, monospace;
  font-size: 0.82em;
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 4px;
  border-radius: 3px;
}
.bubble :deep(pre) {
  background: #0a0c12;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px;
  font-size: 0.78rem;
  white-space: pre-wrap;
  word-break: break-all;
  margin-top: 8px;
  max-height: 260px;
  overflow: auto;
}
.bubble :deep(.steps) {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.bubble :deep(.step) {
  font-size: 0.78rem;
  color: var(--subtext);
  padding: 2px 0 2px 10px;
  border-left: 2px solid var(--border);
}
.bubble :deep(.step.done) {
  color: var(--green2);
  border-color: #16a34a;
}
.bubble :deep(.step.fail) {
  color: var(--red2);
  border-color: #dc2626;
}

/* Markdown prose inside agent bubbles */
.agent .bubble :deep(p) {
  margin: 0 0 0.5em;
}
.agent .bubble :deep(p:last-child) {
  margin-bottom: 0;
}
.agent .bubble :deep(ul),
.agent .bubble :deep(ol) {
  margin: 0.25em 0 0.5em;
  padding-left: 1.4em;
}
.agent .bubble :deep(li) {
  margin-bottom: 0.15em;
}
.agent .bubble :deep(h1),
.agent .bubble :deep(h2),
.agent .bubble :deep(h3),
.agent .bubble :deep(h4) {
  margin: 0.6em 0 0.25em;
  font-weight: 700;
  line-height: 1.25;
}
.agent .bubble :deep(h1) {
  font-size: 1.1em;
}
.agent .bubble :deep(h2) {
  font-size: 1em;
}
.agent .bubble :deep(h3) {
  font-size: 0.95em;
}
.agent .bubble :deep(blockquote) {
  margin: 0.4em 0;
  padding-left: 0.75em;
  border-left: 3px solid var(--border);
  color: var(--subtext);
}
.agent .bubble :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 0.5em 0;
}
.agent .bubble :deep(a) {
  color: var(--accent);
  text-decoration: underline;
}

/* Agent discovery cards injected inline into chat */
.agent .bubble :deep(.disc-header) {
  font-size: 0.8rem;
  color: var(--subtext);
  margin-bottom: 8px;
}
.agent .bubble :deep(.disc-list) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.agent .bubble :deep(.disc-agent-card) {
  display: flex;
  gap: 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
}
.agent .bubble :deep(.disc-icon) {
  font-size: 1.4rem;
  flex-shrink: 0;
  line-height: 1;
}
.agent .bubble :deep(.disc-body) {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.agent .bubble :deep(.disc-label) {
  font-weight: 700;
  font-size: 0.88rem;
  color: var(--accent);
  text-decoration: none;
}
.agent .bubble :deep(.disc-label:hover) {
  text-decoration: underline;
}
.agent .bubble :deep(.disc-desc) {
  font-size: 0.78rem;
  color: var(--subtext);
}
.agent .bubble :deep(.disc-caps) {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}
.agent .bubble :deep(.disc-chip) {
  font-size: 0.68rem;
  background: rgba(99, 179, 237, 0.12);
  color: var(--accent);
  border: 1px solid rgba(99, 179, 237, 0.25);
  border-radius: 4px;
  padding: 1px 6px;
}

/* ── Web 2.0 auth connect button ─────────────────────────────── */
.auth-required-row {
  margin-top: 10px;
}
.auth-connect-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  color: #e6edf3;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.84rem;
  font-weight: 600;
  padding: 7px 14px;
  transition:
    background 0.15s,
    border-color 0.15s;
}
.auth-connect-btn:hover {
  background: #21262d;
  border-color: #58a6ff;
}
.auth-provider-icon {
  font-size: 1.1em;
  line-height: 1;
}

/* ── Device Authorization Grant card ─────────────────────────── */
.device-code-card {
  background: rgba(22, 27, 34, 0.95);
  border: 1px solid #30363d;
  border-radius: 10px;
  padding: 14px 16px;
  margin-top: 8px;
  font-size: 0.86rem;
  max-width: 380px;
}
.dc-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.dc-icon {
  font-size: 1.3rem;
}
.dc-title {
  font-weight: 700;
  font-size: 0.95rem;
  color: #e6edf3;
}
.dc-instructions {
  color: #8b949e;
  margin-bottom: 8px;
  line-height: 1.5;
}
.dc-link {
  color: #58a6ff;
  text-decoration: none;
  word-break: break-all;
}
.dc-link:hover {
  text-decoration: underline;
}
.dc-code {
  font-family: ui-monospace, monospace;
  font-size: 1.55rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #e6edf3;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 8px 14px;
  display: inline-block;
  margin-bottom: 10px;
  user-select: all;
}
.dc-status {
  font-size: 0.82rem;
  color: #8b949e;
}
.dc-waiting {
  display: flex;
  align-items: center;
  gap: 6px;
}
.dc-spinner {
  display: inline-block;
  animation: dc-spin 1.2s linear infinite;
}
@keyframes dc-spin {
  to {
    transform: rotate(360deg);
  }
}
.dc-success {
  color: #3fb950;
  font-weight: 600;
  font-size: 0.9rem;
}
.dc-error {
  color: #f85149;
}
.dc-sf-input {
  width: 100%;
  box-sizing: border-box;
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  color: #e6edf3;
  font-family: inherit;
  font-size: 0.87rem;
  padding: 7px 10px;
  margin-bottom: 10px;
  outline: none;
}
.dc-sf-input:focus {
  border-color: #58a6ff;
}
.dc-connect-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #1f6feb;
  border: 1px solid #388bfd;
  border-radius: 6px;
  color: #fff;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.87rem;
  font-weight: 600;
  padding: 7px 14px;
  transition: background 0.15s;
}
.dc-connect-btn:hover {
  background: #388bfd;
}

/* ── GitHub data cards ────────────────────────────────────────── */
.agent .bubble :deep(.gh-card) {
  background: rgba(22, 27, 34, 0.9);
  border: 1px solid #30363d;
  border-radius: 10px;
  padding: 12px 14px;
  margin-top: 6px;
  font-size: 0.84rem;
}
.agent .bubble :deep(.gh-title) {
  font-weight: 700;
  font-size: 0.9rem;
  margin-bottom: 10px;
  color: #e6edf3;
}
.agent .bubble :deep(.gh-title a) {
  color: #58a6ff;
  text-decoration: none;
}
.agent .bubble :deep(.gh-title a:hover) {
  text-decoration: underline;
}
.agent .bubble :deep(.gh-row) {
  padding: 7px 0;
  border-bottom: 1px solid #21262d;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
}
.agent .bubble :deep(.gh-row:last-child) {
  border-bottom: none;
}
.agent .bubble :deep(.gh-name) {
  font-weight: 600;
  color: #58a6ff;
  text-decoration: none;
  flex: 1 1 180px;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.agent .bubble :deep(.gh-name:hover) {
  text-decoration: underline;
}
.agent .bubble :deep(.gh-num) {
  color: #8b949e;
  font-size: 0.8rem;
  flex-shrink: 0;
}
.agent .bubble :deep(.gh-desc) {
  color: #8b949e;
  font-size: 0.78rem;
  width: 100%;
  margin-top: 2px;
}
.agent .bubble :deep(.gh-meta) {
  color: #8b949e;
  font-size: 0.75rem;
  white-space: nowrap;
}
.agent .bubble :deep(.gh-badge) {
  font-size: 0.68rem;
  border-radius: 4px;
  padding: 1px 6px;
  font-weight: 600;
  white-space: nowrap;
}
.agent .bubble :deep(.gh-public) {
  background: rgba(63, 185, 80, 0.15);
  color: #3fb950;
  border: 1px solid rgba(63, 185, 80, 0.3);
}
.agent .bubble :deep(.gh-private) {
  background: rgba(248, 81, 73, 0.12);
  color: #f85149;
  border: 1px solid rgba(248, 81, 73, 0.3);
}
.agent .bubble :deep(.gh-lang) {
  background: rgba(99, 179, 237, 0.12);
  color: #79c0ff;
  border: 1px solid rgba(99, 179, 237, 0.25);
}
.agent .bubble :deep(.gh-draft) {
  background: rgba(188, 140, 82, 0.15);
  color: #d29922;
  border: 1px solid rgba(188, 140, 82, 0.3);
}
.agent .bubble :deep(.gh-topics) {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 6px;
}
.agent .bubble :deep(.gh-chip) {
  font-size: 0.68rem;
  background: rgba(56, 139, 253, 0.1);
  color: #388bfd;
  border: 1px solid rgba(56, 139, 253, 0.25);
  border-radius: 4px;
  padding: 1px 7px;
}
.agent .bubble :deep(.gh-empty) {
  color: #8b949e;
  font-style: italic;
}
.agent .bubble :deep(.gh-unread-dot) {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #58a6ff;
  flex-shrink: 0;
  margin-right: 2px;
}
</style>
