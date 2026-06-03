<template>
  <div class="skills-drawer" :class="{ open: modelValue }">
    <div class="drawer-inner">
      <h2>Skills</h2>

      <p class="intro">
        Connect external services to give the agent access to your accounts.
        OAuth client IDs are optional — stored only in your browser.
      </p>

      <input
        v-model="filterText"
        type="search"
        class="skills-filter"
        placeholder="Filter skills…"
      />

      <!-- ── GitHub ─────────────────────────────────────────────────── -->
      <section v-show="isSectionVisible('github')">
        <button class="section-header" @click="toggleSection('github')">
          <span class="section-title">🐙 GitHub</span>
          <span class="chevron" :class="{ open: openSections.github }">›</span>
        </button>
        <div class="section-body" v-show="openSections.github">
          <p class="skill-desc">
            Read repos, issues, PRs, notifications, and discussions.
          </p>

          <!-- Connected state -->
          <div v-if="web2Sessions.github" class="connected-row">
            <span class="acct-pill acct-github">🐙 GitHub connected</span>
            <button class="btn-disconnect" @click="web2Disconnect('github')">
              Disconnect
            </button>
          </div>

          <!-- Device flow in progress -->
          <div
            v-else-if="githubFlow.status === 'pending'"
            class="device-flow-box"
          >
            <p class="dc-label">Open the URL and enter the code:</p>
            <a
              :href="githubFlow.verification_uri"
              target="_blank"
              rel="noopener"
              class="dc-link"
            >
              {{ githubFlow.verification_uri }}
            </a>
            <div class="dc-code">{{ githubFlow.user_code }}</div>
            <p class="dc-hint">Waiting for authorization…</p>
          </div>
          <div
            v-else-if="githubFlow.status === 'starting'"
            class="device-flow-box"
          >
            <p class="dc-hint">Starting GitHub authorization…</p>
          </div>
          <div
            v-else-if="githubFlow.status === 'error'"
            class="device-flow-box dc-error"
          >
            <p>{{ githubFlow.message }}</p>
            <button class="btn-connect" @click="connectGitHub">Retry</button>
          </div>

          <!-- Not connected -->
          <div v-else class="connect-row">
            <button class="btn-connect" @click="connectGitHub">
              Connect GitHub
            </button>
          </div>

          <!-- Client ID override -->
          <div class="field-group">
            <label
              >Client ID
              <span class="optional">(optional override)</span></label
            >
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
        </div>
      </section>

      <!-- ── Microsoft ─────────────────────────────────────────────── -->
      <section v-show="isSectionVisible('microsoft')">
        <button class="section-header" @click="toggleSection('microsoft')">
          <span class="section-title">🪟 Microsoft</span>
          <span class="chevron" :class="{ open: openSections.microsoft }"
            >›</span
          >
        </button>
        <div class="section-body" v-show="openSections.microsoft">
          <p class="skill-desc">
            Read and send Outlook email, manage Calendar events, and create
            To&#8209;Do tasks.
          </p>

          <!-- Connected accounts -->
          <div
            v-if="(web2Sessions.microsoft || []).length"
            class="connected-accounts"
          >
            <div
              v-for="acct in web2Sessions.microsoft"
              :key="acct.nonce"
              class="connected-row"
            >
              <span class="acct-pill acct-microsoft"
                >🟦 {{ accountDisplayName(acct) }}</span
              >
              <button
                class="btn-disconnect"
                @click="web2DisconnectAccount('microsoft', acct.nonce)"
              >
                Disconnect
              </button>
            </div>
            <button class="btn-connect" @click="connectMicrosoft">
              + Add account
            </button>
          </div>
          <div v-else class="connect-row">
            <button class="btn-connect" @click="connectMicrosoft">
              Connect Microsoft
            </button>
          </div>

          <!-- Client ID override -->
          <div class="field-group">
            <label
              >Client ID
              <span class="optional">(optional override)</span></label
            >
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
              permissions: User.Read, Mail.Read, Mail.Send, Calendars.ReadWrite,
              Tasks.ReadWrite.
            </div>
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
import { ref, computed, watch } from "vue";
import {
  getSkillsSettings,
  saveSkillsSettings,
  getNodeUrl,
} from "../composables/useStorage.js";
import { useWeb2Auth } from "../composables/useWeb2Auth.js";

const props = defineProps({ modelValue: Boolean });
const emit = defineEmits(["update:modelValue", "auth-connect"]);

const form = ref({ ...getSkillsSettings() });
const savedMsg = ref(false);

// ── Accordion + filter ────────────────────────────────────────────────────
const SKILLS = [
  {
    id: "github",
    keywords: "github repos issues prs pull requests notifications discussions",
  },
  { id: "microsoft", keywords: "microsoft outlook email calendar todo tasks" },
];

const filterText = ref("");
const openSections = ref({ github: false, microsoft: false });
const manuallyOpen = ref({ github: false, microsoft: false });

function isSectionVisible(id) {
  const q = filterText.value.trim().toLowerCase();
  if (!q) return true;
  const skill = SKILLS.find((s) => s.id === id);
  return skill ? skill.keywords.includes(q) : true;
}

function toggleSection(id) {
  openSections.value[id] = !openSections.value[id];
  manuallyOpen.value[id] = openSections.value[id];
}

watch(filterText, (q) => {
  if (!q.trim()) {
    // Filter cleared — restore only sections the user explicitly opened
    for (const skill of SKILLS) {
      openSections.value[skill.id] = !!manuallyOpen.value[skill.id];
    }
  }
  // When filtering, sections are shown/hidden but stay collapsed until manually opened
});

// ── Web2 auth ──────────────────────────────────────────────────────────────
const { activeSessions, connect, disconnect, disconnectAccount } =
  useWeb2Auth();

const web2Sessions = computed(() => activeSessions.value || {});

function web2Disconnect(provider) {
  disconnect(provider);
}
function web2DisconnectAccount(provider, nonce) {
  disconnectAccount(provider, nonce);
}

// ── GitHub device flow (inline in drawer) ─────────────────────────────────
const githubFlow = ref({ status: "idle" }); // idle | starting | pending | error

async function connectGitHub() {
  githubFlow.value = { status: "starting" };
  try {
    const deviceInfo = await connect("github", getNodeUrl(), {});
    githubFlow.value = {
      status: "pending",
      user_code: deviceInfo.user_code,
      verification_uri: deviceInfo.verification_uri,
    };
    await deviceInfo.poll();
    githubFlow.value = { status: "idle" };
  } catch (err) {
    githubFlow.value = { status: "error", message: String(err) };
  }
}

// ── Microsoft — delegate to App.vue → ChatPane (needs on-chain approval) ──
function connectMicrosoft() {
  emit("auth-connect", "microsoft");
  emit("update:modelValue", false); // close drawer so overlay is visible
}

/** Return a display-friendly name for a Microsoft account entry. */
function accountDisplayName(acct) {
  const lbl = (acct.label || "").trim();
  // If label is empty or looks like a raw nonce slice (8 hex chars), use
  // a human-readable fallback and queue a background refresh.
  if (!lbl || /^[0-9a-f]{8}$/i.test(lbl)) return "Microsoft Account";
  return lbl;
}

/** Re-fetch labels from the server for accounts that still have a raw nonce slice. */
async function refreshMicrosoftLabels() {
  const msArr = activeSessions.value.microsoft || [];
  const nodeUrl = getNodeUrl();
  for (const acct of msArr) {
    const lbl = (acct.label || "").trim();
    if (lbl && !/^[0-9a-f]{8}$/i.test(lbl)) continue; // already has a real label
    try {
      const resp = await fetch(
        `${nodeUrl}/ai-agent-auth/api/oauth/microsoft/me?nonce=${encodeURIComponent(acct.nonce)}`,
      );
      if (resp.ok) {
        const data = await resp.json();
        const newLabel = (data.identifier || data.display_name || "").trim();
        if (newLabel) acct.label = newLabel;
      }
    } catch (_) {}
  }
}

// ── Settings save/close ────────────────────────────────────────────────────
watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      form.value = { ...getSkillsSettings() };
      githubFlow.value = { status: "idle" };
      filterText.value = "";
      openSections.value = { github: false, microsoft: false };
      manuallyOpen.value = { github: false, microsoft: false };
      refreshMicrosoftLabels();
    }
  },
);

function save() {
  saveSkillsSettings(form.value);
  savedMsg.value = true;
  setTimeout(() => {
    savedMsg.value = false;
  }, 2000);
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
/* section h3 replaced by .section-header button */
.skills-filter {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 10px;
  color: var(--text);
  font-size: 0.82rem;
  outline: none;
  width: 100%;
  box-sizing: border-box;
  transition: border-color 0.15s;
}
.skills-filter:focus {
  border-color: var(--accent);
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--border);
  padding: 0 0 4px 0;
  cursor: pointer;
  color: inherit;
  text-align: left;
  margin: 0;
}
.section-title {
  font-size: 0.78rem;
  color: var(--subtext);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}
.chevron {
  font-size: 1rem;
  color: var(--subtext);
  transition: transform 0.2s;
  transform: rotate(0deg);
  display: inline-block;
  line-height: 1;
}
.chevron.open {
  transform: rotate(90deg);
}
.section-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 8px;
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

/* ── Account connection UI ─────────────────────────────────────────────── */
.connected-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.connected-accounts {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.connect-row {
  display: flex;
  align-items: center;
}
.acct-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.74rem;
  padding: 3px 10px;
  border-radius: 12px;
  font-weight: 500;
  white-space: nowrap;
}
.acct-github {
  background: rgba(88, 166, 255, 0.1);
  color: #79c0ff;
  border: 1px solid rgba(88, 166, 255, 0.2);
}
.acct-microsoft {
  background: rgba(0, 120, 212, 0.12);
  color: #60a5fa;
  border: 1px solid rgba(0, 120, 212, 0.25);
}
.btn-connect {
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-connect:hover {
  opacity: 0.85;
}
.btn-disconnect {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 3px 10px;
  color: var(--text-muted, #888);
  font-size: 0.74rem;
  cursor: pointer;
  transition:
    border-color 0.15s,
    color 0.15s;
}
.btn-disconnect:hover {
  border-color: #f85149;
  color: #f85149;
}
.device-flow-box {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.dc-label {
  font-size: 0.74rem;
  color: var(--subtext);
  margin: 0;
}
.dc-link {
  font-size: 0.78rem;
  color: var(--accent);
  word-break: break-all;
}
.dc-code {
  font-family: monospace;
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--text);
  letter-spacing: 0.12em;
  text-align: center;
  padding: 4px 0;
}
.dc-hint {
  font-size: 0.72rem;
  color: var(--subtext);
  margin: 0;
  font-style: italic;
}
.dc-error {
  border-color: rgba(248, 81, 73, 0.35);
  color: #f85149;
  font-size: 0.75rem;
}
</style>
