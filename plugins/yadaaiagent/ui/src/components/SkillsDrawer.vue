<template>
  <div class="skills-drawer" :class="{ open: modelValue }">
    <div class="drawer-inner">
      <h2>Skills</h2>

      <p class="intro">
        Enable integrations by connecting external services. OAuth client IDs
        are stored only in your browser — the node falls back to its configured
        ID when none is provided here.
      </p>

      <!-- ── GitHub ─────────────────────────────────────────────────── -->
      <section>
        <h3>🐙 GitHub</h3>
        <p class="skill-desc">
          Read repos, issues, PRs, notifications, and discussions.
        </p>
        <div class="field-group">
          <label>Client ID <span class="optional">(optional)</span></label>
          <input
            v-model="form.github_client_id"
            type="text"
            placeholder="Ov23li…"
            autocomplete="off"
            spellcheck="false"
          />
          <div class="hint">
            Register at
            <a
              href="https://github.com/settings/applications/new"
              target="_blank"
              rel="noopener"
              >GitHub → Settings → Developer settings → OAuth Apps</a
            >. No callback URL is needed for the device flow.
          </div>
        </div>
      </section>

      <!-- ── Microsoft ─────────────────────────────────────────────── -->
      <section>
        <h3>🪟 Microsoft</h3>
        <p class="skill-desc">
          Read and send Outlook email, manage Calendar events, and create
          To&#8209;Do tasks.
        </p>
        <div class="field-group">
          <label>Client ID <span class="optional">(optional)</span></label>
          <input
            v-model="form.microsoft_client_id"
            type="text"
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            autocomplete="off"
            spellcheck="false"
          />
          <div class="hint">
            Register a public-client app in
            <a
              href="https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps"
              target="_blank"
              rel="noopener"
              >Azure → App registrations</a
            >. Enable <em>Allow public client flows</em> and add delegated
            permissions: User.Read, Mail.Read, Mail.Send,
            Calendars.ReadWrite, Tasks.ReadWrite.
          </div>
        </div>
      </section>

      <div class="btn-row">
        <button class="btn-save" @click="save">Save</button>
        <button class="btn-close" @click="close">Close</button>
        <span v-if="savedMsg" class="saved-msg">✓ Saved</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { getSkillsSettings, saveSkillsSettings } from "../composables/useStorage.js";

const props = defineProps({ modelValue: Boolean });
const emit = defineEmits(["update:modelValue"]);

const form = ref({ ...getSkillsSettings() });
const savedMsg = ref(false);

watch(
  () => props.modelValue,
  (v) => {
    if (v) form.value = { ...getSkillsSettings() };
  },
);

function save() {
  saveSkillsSettings(form.value);
  savedMsg.value = true;
  setTimeout(() => { savedMsg.value = false; }, 2000);
}

function close() {
  emit("update:modelValue", false);
}
</script>

<style scoped>
.skills-drawer {
  display: none;
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 200;
  background: rgba(0, 0, 0, 0.4);
}
.skills-drawer.open {
  display: block;
}
.drawer-inner {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 340px;
  background: var(--surface);
  border-left: 1px solid var(--border);
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
h2 {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.07em;
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
}
.skill-desc {
  font-size: 0.75rem;
  color: var(--subtext);
  margin: 0;
  line-height: 1.4;
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
.optional {
  font-weight: 400;
  opacity: 0.65;
}
.field-group input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 10px;
  color: var(--text);
  font-size: 0.82rem;
  font-family: monospace;
  outline: none;
  transition: border-color 0.15s;
}
.field-group input:focus {
  border-color: var(--accent);
}
.hint {
  font-size: 0.7rem;
  color: var(--subtext);
  line-height: 1.4;
  opacity: 0.8;
}
.hint a {
  color: var(--accent);
}
.btn-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: auto;
}
.btn-save {
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-weight: 700;
  font-size: 0.84rem;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-save:hover {
  opacity: 0.85;
}
.btn-close {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 16px;
  color: var(--text);
  font-size: 0.84rem;
  cursor: pointer;
  transition: border-color 0.15s;
}
.btn-close:hover {
  border-color: var(--accent);
}
.saved-msg {
  font-size: 0.78rem;
  color: var(--accent);
}
</style>
