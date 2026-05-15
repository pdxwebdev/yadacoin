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
        <div v-if="msg.choices?.length" class="choice-form">
          <!-- Single-select: radio buttons -->
          <template v-if="!msg.choicesMulti">
            <label
              v-for="(choice, ci) in msg.choices"
              :key="ci"
              class="choice-label"
            >
              <input
                type="radio"
                :name="`choice-${i}`"
                :value="choice"
                v-model="msg.radioSelected"
                class="choice-input"
              />
              <span>{{ choice }}</span>
            </label>
            <button
              class="choice-confirm-btn"
              :disabled="!msg.radioSelected"
              @click="confirmRadio(msg)"
            >
              Confirm
            </button>
          </template>
          <!-- Multi-select: checkboxes -->
          <template v-else>
            <label
              v-for="(choice, ci) in msg.choices"
              :key="ci"
              class="choice-label"
            >
              <input
                type="checkbox"
                :value="choice"
                v-model="msg.checkSelected"
                class="choice-input"
              />
              <span>{{ choice }}</span>
            </label>
            <button
              class="choice-confirm-btn"
              :disabled="!msg.checkSelected?.length"
              @click="confirmCheckbox(msg)"
            >
              Confirm
            </button>
          </template>
        </div>
        <div v-if="msg.dateFields?.length" class="date-form">
          <div
            v-for="(field, fi) in msg.dateFields"
            :key="fi"
            class="date-field-row"
          >
            <label class="date-field-label">{{ field.label }}</label>
            <input
              :type="field.type"
              v-model="field.value"
              class="date-field-input"
            />
          </div>
          <button
            class="choice-confirm-btn"
            :disabled="msg.dateFields.some((f) => !f.value)"
            @click="confirmFields(msg)"
          >
            Confirm
          </button>
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
const emit = defineEmits(["choice-selected", "fields-confirmed"]);

function confirmRadio(msg) {
  if (!msg.radioSelected) return;
  emit("choice-selected", msg.radioSelected);
}

function confirmCheckbox(msg) {
  if (!msg.checkSelected?.length) return;
  emit("choice-selected", [...msg.checkSelected]);
}

function confirmFields(msg) {
  const parts = msg.dateFields
    .filter((f) => f.value)
    .map((f) => `${f.label}: ${f.value}`);
  emit("fields-confirmed", parts.join(", "));
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
  gap: 6px;
  margin-top: 8px;
  padding: 10px 14px;
  background: var(--agent-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
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
</style>
