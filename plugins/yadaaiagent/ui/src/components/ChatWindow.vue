<template>
  <div class="chat-window" ref="chatEl">
    <div
      v-for="(msg, i) in messages"
      :key="i"
      class="msg-row"
      :class="msg.role"
    >
      <div class="avatar">{{ msg.role === "user" ? "You" : "AI" }}</div>
      <div
        class="bubble"
        :class="{ thinking: msg.thinking }"
        v-html="renderBubble(msg)"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from "vue";
import { marked } from "marked";

marked.setOptions({ breaks: true, gfm: true });

const props = defineProps({ messages: Array });
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
  // Agent messages: if already tagged as raw HTML (from approval flow etc.) use as-is,
  // otherwise run through marked for full markdown support.
  if (msg.html) return msg.html;
  return marked.parse(msg.content || "");
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
  max-width: 72%;
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
</style>
