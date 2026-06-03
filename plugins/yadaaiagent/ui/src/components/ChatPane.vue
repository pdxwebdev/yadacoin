<template>
  <div class="chat-pane">
    <ChatWindow
      :messages="messages"
      ref="chatWindow"
      @fields-confirmed="handleFieldsConfirmed"
      @auth-connect="handleAuthConnect"
    />

    <div class="input-area">
      <!-- ── Input row ───────────────────────────────────────────────── -->
      <div class="input-row">
        <button
          class="help-btn"
          title="Integration help"
          @click="showDocs = true"
        >
          ?
        </button>
        <textarea
          ref="inputEl"
          v-model="userInput"
          :disabled="!sessionReady || busy"
          placeholder="Describe a goal for the agent…"
          rows="1"
          @keydown.enter.exact.prevent="runLoop()"
          @input="autoGrow"
        ></textarea>
        <button
          class="send-btn"
          :disabled="!sessionReady || !userInput.trim() || busy"
          @click="runLoop()"
        >
          ⚡
        </button>
      </div>
    </div>

    <!-- ── Integration docs modal ───────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showDocs" class="docs-backdrop" @click.self="showDocs = false">
        <div class="docs-modal">
          <div class="docs-header">
            <span class="docs-title">Integrations &amp; Setup</span>
            <button class="docs-close" @click="showDocs = false">✕</button>
          </div>
          <div class="docs-body">
            <!-- GitHub accordion -->
            <div class="docs-accordion">
              <button
                class="docs-acc-header"
                @click="
                  openSection = openSection === 'github' ? null : 'github'
                "
              >
                <span>🐙 GitHub Integration</span>
                <span
                  class="docs-acc-chevron"
                  :class="{ open: openSection === 'github' }"
                  >›</span
                >
              </button>
              <div v-show="openSection === 'github'" class="docs-acc-body">
                <p>
                  Connect your GitHub account to let the AI agent read issues,
                  pull requests, repositories, and discussions on your behalf.
                </p>
                <h3>Connecting</h3>
                <ol>
                  <li>
                    Switch to the <strong>GitHub</strong> agent type in the
                    agent selector.
                  </li>
                  <li>
                    The agent detects GitHub is not connected and prompts you to
                    authorize.
                  </li>
                  <li>
                    A device code appears — visit
                    <code>https://github.com/login/device</code> and enter it.
                  </li>
                  <li>
                    Once authorized, your token is stored securely in the local
                    database.
                  </li>
                </ol>
                <h3>What it can do</h3>
                <ul>
                  <li>
                    List and search repositories, issues, and pull requests
                  </li>
                  <li>Read issue and PR details, comments, and diffs</li>
                  <li>Search GitHub Discussions</li>
                </ul>
                <h3>🔒 Use Your Own GitHub OAuth App (Better Privacy)</h3>
                <p>
                  By default this app uses a shared OAuth client ID. For better
                  privacy, register your own:
                </p>
                <ol>
                  <li>
                    Go to
                    <strong
                      >GitHub → Settings → Developer settings → OAuth Apps → New
                      OAuth App</strong
                    >
                  </li>
                  <li>
                    Set <em>Authorization callback URL</em> to
                    <code>http://localhost</code> (device flow doesn't use it)
                  </li>
                  <li>Copy the <strong>Client ID</strong></li>
                  <li>
                    Open <code>config/config2.json</code> and set
                    <code>"github_device_client_id"</code> to your Client ID
                  </li>
                  <li>Restart the server and reconnect GitHub</li>
                </ol>
              </div>
            </div>

            <!-- Microsoft accordion -->
            <div class="docs-accordion">
              <button
                class="docs-acc-header"
                @click="
                  openSection = openSection === 'microsoft' ? null : 'microsoft'
                "
              >
                <span>🟦 Microsoft / Outlook Integration</span>
                <span
                  class="docs-acc-chevron"
                  :class="{ open: openSection === 'microsoft' }"
                  >›</span
                >
              </button>
              <div v-show="openSection === 'microsoft'" class="docs-acc-body">
                <p>
                  Connect your Microsoft 365 or Outlook account to read email,
                  send email, manage calendar events, and work with Microsoft To
                  Do.
                </p>
                <h3>Connecting</h3>
                <ol>
                  <li>
                    Switch to the <strong>Microsoft / Outlook</strong> agent
                    type.
                  </li>
                  <li>
                    The agent prompts you to connect — a device code appears.
                  </li>
                  <li>
                    Visit <code>https://microsoft.com/devicelogin</code> and
                    enter the code.
                  </li>
                  <li>
                    Sign in with your Microsoft account and grant the requested
                    permissions.
                  </li>
                </ol>
                <h3>What it can do</h3>
                <ul>
                  <li>
                    <strong>Email:</strong> show inbox, read emails, summarize N
                    emails, send email
                  </li>
                  <li><strong>Calendar:</strong> list upcoming events</li>
                  <li>
                    <strong>Microsoft To Do:</strong> add tasks, complete tasks,
                    delete tasks, push email action items to To Do
                  </li>
                </ul>
                <h3>Permissions requested</h3>
                <p>
                  <code>user.read</code> · <code>Mail.Read</code> ·
                  <code>Mail.Send</code> · <code>Calendars.ReadWrite</code> ·
                  <code>Tasks.ReadWrite</code>
                </p>
                <h3>🔒 Use Your Own Azure AD App (Better Privacy)</h3>
                <p>
                  By default this app uses a shared Azure app registration. To
                  use your own:
                </p>
                <ol>
                  <li>
                    Go to
                    <strong
                      >Azure Portal → Azure Active Directory → App registrations
                      → New registration</strong
                    >
                  </li>
                  <li>
                    Set <em>Supported account types</em> to
                    <strong
                      >Accounts in any org directory and personal Microsoft
                      accounts</strong
                    >
                  </li>
                  <li>
                    Under <strong>Authentication → Advanced settings</strong>,
                    enable <strong>Allow public client flows</strong>
                  </li>
                  <li>
                    Under <strong>API Permissions</strong>, add Delegated:
                    <code>User.Read</code>, <code>Mail.Read</code>,
                    <code>Mail.Send</code>, <code>Calendars.ReadWrite</code>,
                    <code>Tasks.ReadWrite</code>
                  </li>
                  <li>Copy the <strong>Application (client) ID</strong></li>
                  <li>
                    Open <code>config/config2.json</code> and set
                    <code>"microsoft_device_client_id"</code> to your
                    Application ID
                  </li>
                  <li>Restart the server and reconnect Microsoft</li>
                </ol>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from "vue";
import { marked } from "marked";
import ChatWindow from "./ChatWindow.vue";
import {
  LS_PRIV,
  LS_CC,
  LS_HW_PUB,
  LS_WALLET_MODE,
  LS_ACTIVE_AGENT,
  getLlmSettings,
  getBraveApiKey,
  getNodeUrl,
  saveBookingCredential,
  getWalletMode,
  isClientWallet,
  isHardwareWallet,
  getHardwareActive,
  setHardwareActive,
} from "../composables/useStorage.js";
import { postCredentialReceipt } from "../composables/useCredentialReceipts.js";
import { useWeb2Auth } from "../composables/useWeb2Auth.js";
import {
  hex,
  compactSigToDerBase64,
  deriveSecurePath,
  getPublicKeyHex,
  getP2PKH,
  buildRotationTxn,
  secp,
  sha256,
} from "../composables/useCrypto.js";

// ── Props / emit ─────────────────────────────────────────────────────────────
const props = defineProps({
  agents: Array, // all agent types from /api/agents
});
const emit = defineEmits([
  "session-rotated",
  "agent-changed",
  "credential-issued",
  "setup-wallet",
]);

// ── Current agent (auto-detected) ────────────────────────────────────────────
const currentAgentId = ref("general");
const showDocs = ref(false);
const openSection = ref(null);
const currentAgentType = computed(
  () => props.agents?.find((a) => a.id === currentAgentId.value) || null,
);

// ── State ─────────────────────────────────────────────────────────────────────
const messages = ref([]);
const userInput = ref("");
const busy = ref(false);
const inputEl = ref(null);
const chatWindow = ref(null);

// ── Agent Loop mode (always on) ──────────────────────────────────────────────

// Per-conversation "extracted" scope (travel details, legal params, etc.)
let extractedScope = null;
let chatHistory = [];

// Vendor follow-up conversation state
// null | { queue, current: {service, vendorName}, vpData, vendorMessages }
const vendorState = ref(null);

// ── Web 2.0 OAuth sessions ────────────────────────────────────────────────────
const {
  activeSessions: web2Sessions,
  connect: web2Connect,
  disconnectAccount: web2DisconnectAccount,
  disconnect: web2Disconnect,
  rekeyActiveSessions: web2RekeyActiveSessions,
} = useWeb2Auth();

// Prompt that triggered a pending auth (re-sent after connecting)
let pendingAuthPrompt = "";

// ── Session ──────────────────────────────────────────────────────────────────
// sessionTick is incremented externally (notifyWalletReady) to force the
// computed to re-evaluate, since Vue does not track localStorage reads.
const sessionTick = ref(0);
const sessionReady = computed(() => {
  sessionTick.value; // reactive dependency so we can force re-evaluation
  if (isHardwareWallet()) {
    return !!getHardwareActive();
  }
  const p = localStorage.getItem(LS_PRIV);
  const c = localStorage.getItem(LS_CC);
  return !!(p && c);
});

onMounted(() => {
  if (!sessionReady.value) {
    const storedMode = localStorage.getItem(LS_WALLET_MODE);
    if (storedMode === "client") {
      // Client wallet mode but no key yet — prompt setup
      pushAgent(
        "\u26A0 No wallet found. Click the session pill to set up your personal wallet, or switch to Node Wallet mode in Settings.",
        true,
      );
      emit("setup-wallet");
    } else if (storedMode === "hardware") {
      // Hardware wallet mode but device not yet paired
      pushAgent(
        "\u26A0 No hardware wallet paired. Click the session pill to scan your device's QR and pair it.",
        true,
      );
      emit("setup-wallet");
    } else if (storedMode === "node") {
      // Node wallet mode explicitly set but no key derived yet
      pushAgent(
        "\u26A0 No operator key found. " +
          'Please <a href="/key-rotation/derived-keys" target="_blank" style="color:var(--accent)">initialise your key</a> first, then reload.',
        true,
      );
    } else {
      // Completely fresh load — no wallet mode chosen yet
      pushAgent(
        "Welcome! To get started, set up a <strong>Personal Wallet</strong> (generate your own BIP39 seed in the browser) or configure a <strong>Node Wallet</strong> (server-managed key). Open <em>Settings ⚙</em> to choose.",
        true,
      );
    }
  } else {
    pushAgent("Hello! I'm your YadaCoin AI agent. How can I help you today?");
  }
  nextTick(() => inputEl.value?.focus());
});

// Emit initial agent type once agents load
watch(
  () => props.agents,
  (agentList) => {
    if (agentList?.length) {
      const match = agentList.find((a) => a.id === currentAgentId.value);
      emit("agent-changed", match || agentList[0]);
    }
  },
  { immediate: true },
);

// ── Message helpers ───────────────────────────────────────────────────────────
function pushUser(text) {
  messages.value.push({ role: "user", content: text });
}

function pushAgent(html, isHtml = false) {
  const msg = {
    role: "agent",
    content: isHtml ? "" : html,
    html: isHtml ? html : null,
  };
  messages.value.push(msg);
  return msg;
}

function pushThinking() {
  const msg = {
    role: "agent",
    thinking: true,
    html: '<div class="typing"><span></span><span></span><span></span></div>',
  };
  messages.value.push(msg);
  return { index: messages.value.length - 1, msg };
}

function removeMsg(index) {
  messages.value.splice(index, 1);
}

/**
 * Apply UI hint fields from an API response directly onto a message.
 * choices is an array of choice group objects built by the model.
 */
function applyDataFields(msg, data) {
  const groups = Array.isArray(data.choices) ? data.choices : [];
  if (groups.length) {
    msg.choices = groups;
    // Initialize per-group selection state keyed by group.id
    msg.selections = {};
    for (const g of groups) {
      msg.selections[g.id] = g.multi ? [] : "";
    }
  }
}

/** Clear choice form from the most recent agent message that has one. */
function clearLastChoices() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].choices?.length) {
      messages.value[i].choices = [];
      messages.value[i].selections = {};
      break;
    }
  }
}

/** Called when the user confirms a choice (string for radio, array for checkboxes). */
function handleChoice(choice) {
  if (busy.value) return;
  const text = Array.isArray(choice) ? choice.join(", ") : choice;
  userInput.value = text;
  send();
}

/** Called when the user confirms date/text fields. */
function handleFieldsConfirmed(text) {
  if (busy.value) return;
  userInput.value = text;
  send();
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ── GitHub data card renderer ─────────────────────────────────────────────────
function renderGithubData(gd) {
  const { type } = gd;
  if (type === "repos") {
    if (!gd.items?.length)
      return `<div class="gh-card"><div class="gh-title">🐙 Repositories</div><div class="gh-empty">No repositories found.</div></div>`;
    const rows = gd.items
      .map(
        (r) =>
          `<div class="gh-row">` +
          `<a class="gh-name" href="${escHtml(r.url)}" target="_blank" rel="noopener noreferrer">${escHtml(r.full_name)}</a>` +
          (r.private
            ? `<span class="gh-badge gh-private">private</span>`
            : `<span class="gh-badge gh-public">public</span>`) +
          (r.language
            ? `<span class="gh-badge gh-lang">${escHtml(r.language)}</span>`
            : "") +
          `<span class="gh-meta">⭐ ${r.stars}  🐛 ${r.open_issues}</span>` +
          (r.description
            ? `<div class="gh-desc">${escHtml(r.description)}</div>`
            : "") +
          `</div>`,
      )
      .join("");
    return `<div class="gh-card"><div class="gh-title">🐙 Your Repositories (${gd.items.length})</div>${rows}</div>`;
  }
  if (type === "repo") {
    return (
      `<div class="gh-card">` +
      `<div class="gh-title">🐙 <a href="${escHtml(gd.url)}" target="_blank" rel="noopener noreferrer">${escHtml(gd.full_name)}</a></div>` +
      (gd.description
        ? `<div class="gh-desc">${escHtml(gd.description)}</div>`
        : "") +
      `<div class="gh-meta">⭐ ${gd.stars} &nbsp; 🍴 ${gd.forks} &nbsp; 🐛 ${gd.open_issues} open issues &nbsp; 🌿 ${escHtml(gd.default_branch)}</div>` +
      (gd.language
        ? `<span class="gh-badge gh-lang">${escHtml(gd.language)}</span>`
        : "") +
      (gd.topics?.length
        ? `<div class="gh-topics">${gd.topics.map((t) => `<span class="gh-chip">${escHtml(t)}</span>`).join("")}</div>`
        : "") +
      `</div>`
    );
  }
  if (type === "issues") {
    if (!gd.items?.length)
      return `<div class="gh-card"><div class="gh-title">🐛 Issues — ${escHtml(gd.repo)}</div><div class="gh-empty">No ${gd.state} issues found.</div></div>`;
    const rows = gd.items
      .map(
        (i) =>
          `<div class="gh-row">` +
          `<span class="gh-num">#${i.number}</span> ` +
          `<a class="gh-name" href="${escHtml(i.url)}" target="_blank" rel="noopener noreferrer">${escHtml(i.title)}</a>` +
          `<span class="gh-meta">${escHtml(i.author)} · ${escHtml(i.created_at)} · 💬 ${i.comments}</span>` +
          `</div>`,
      )
      .join("");
    return `<div class="gh-card"><div class="gh-title">🐛 Issues — ${escHtml(gd.repo)} (${gd.state})</div>${rows}</div>`;
  }
  if (type === "prs") {
    if (!gd.items?.length)
      return `<div class="gh-card"><div class="gh-title">🔀 Pull Requests — ${escHtml(gd.repo)}</div><div class="gh-empty">No ${gd.state} pull requests found.</div></div>`;
    const rows = gd.items
      .map(
        (p) =>
          `<div class="gh-row">` +
          `<span class="gh-num">#${p.number}</span> ` +
          `<a class="gh-name" href="${escHtml(p.url)}" target="_blank" rel="noopener noreferrer">${escHtml(p.title)}</a>` +
          (p.draft ? `<span class="gh-badge gh-draft">draft</span>` : "") +
          `<span class="gh-meta">${escHtml(p.author)} · ${escHtml(p.created_at)}</span>` +
          `</div>`,
      )
      .join("");
    return `<div class="gh-card"><div class="gh-title">🔀 Pull Requests — ${escHtml(gd.repo)} (${gd.state})</div>${rows}</div>`;
  }
  if (type === "notifications") {
    if (!gd.items?.length)
      return `<div class="gh-card"><div class="gh-title">🔔 Notifications</div><div class="gh-empty">No notifications.</div></div>`;
    const rows = gd.items
      .map(
        (n) =>
          `<div class="gh-row">` +
          (n.unread ? `<span class="gh-unread-dot"></span>` : "") +
          `<span class="gh-name">${escHtml(n.title)}</span>` +
          `<span class="gh-meta">${escHtml(n.repo)} · ${escHtml(n.type)} · ${escHtml(n.reason)}</span>` +
          `</div>`,
      )
      .join("");
    return `<div class="gh-card"><div class="gh-title">🔔 GitHub Notifications</div>${rows}</div>`;
  }
  return "";
}

function renderMicrosoftData(md) {
  const { type } = md;
  if (type === "emails") {
    if (!md.items?.length)
      return `<div class="ms-card"><div class="ms-title">📧 Inbox</div><div class="ms-empty">No emails found.</div></div>`;
    const rows = md.items
      .map(
        (m) =>
          `<div class="ms-row${m.is_read ? "" : " ms-unread"}">` +
          (!m.is_read
            ? `<span class="ms-dot"></span>`
            : `<span class="ms-dot-placeholder"></span>`) +
          `<div class="ms-row-main">` +
          `<div class="ms-row-top">` +
          `<span class="ms-from">${escHtml(m.from_name || m.from)}</span>` +
          `<span class="ms-date">${escHtml(m.received)}</span>` +
          `</div>` +
          `<div class="ms-subject">${escHtml(m.subject)}</div>` +
          (m.preview
            ? `<div class="ms-preview">${escHtml(m.preview)}</div>`
            : "") +
          `</div>` +
          `</div>`,
      )
      .join("");
    return `<div class="ms-card"><div class="ms-title">📧 Inbox (${md.items.length})</div>${rows}</div>`;
  }
  if (type === "email") {
    return (
      `<div class="ms-card">` +
      `<div class="ms-title">📧 ${escHtml(md.subject)}</div>` +
      `<div class="ms-meta">From: <strong>${escHtml(md.from_name || md.from)}</strong> · ${escHtml(md.received)}</div>` +
      `<div class="ms-body">${escHtml(md.body)}</div>` +
      `</div>`
    );
  }
  if (type === "events") {
    if (!md.items?.length)
      return `<div class="ms-card"><div class="ms-title">📅 Calendar</div><div class="ms-empty">No upcoming events.</div></div>`;
    const rows = md.items
      .map(
        (e) =>
          `<div class="ms-row">` +
          `<div class="ms-row-main">` +
          `<div class="ms-row-top">` +
          `<span class="ms-subject">${escHtml(e.subject)}</span>` +
          (e.online ? `<span class="ms-badge ms-online">online</span>` : "") +
          `</div>` +
          `<div class="ms-meta">${escHtml(e.start)} – ${escHtml(e.end.slice(11))}` +
          (e.location ? ` · 📍 ${escHtml(e.location)}` : "") +
          `</div>` +
          `</div>` +
          `</div>`,
      )
      .join("");
    return `<div class="ms-card"><div class="ms-title">📅 Upcoming Events (${md.items.length})</div>${rows}</div>`;
  }
  if (type === "sent") {
    return `<div class="ms-card"><div class="ms-title">✅ Email Sent</div><div class="ms-meta">To: ${escHtml(md.to)} · Subject: ${escHtml(md.subject)}</div></div>`;
  }
  if (type === "email_summary") {
    const subjects = md.subjects || [];
    const rows = subjects
      .map(
        (s, i) =>
          `<div class="ms-row">` +
          `<div class="ms-row-main">` +
          `<div class="ms-row-top">` +
          `<span class="ms-from">${escHtml(s.from_name || s.from)}</span>` +
          `<span class="ms-date">${escHtml(s.received)}</span>` +
          `</div>` +
          `<div class="ms-subject">${escHtml(s.subject)}</div>` +
          `</div>` +
          `</div>`,
      )
      .join("");
    const title =
      md.count === 1
        ? "📧 Summarized Email"
        : `📧 Summarized ${md.count} Emails`;
    return rows
      ? `<div class="ms-card"><div class="ms-title">${title}</div>${rows}</div>`
      : `<div class="ms-card"><div class="ms-title">${title}</div></div>`;
  }
  if (type === "todo_list") {
    const subjects = md.subjects || [];
    const rows = subjects
      .map(
        (s) =>
          `<div class="ms-row">` +
          `<div class="ms-row-main">` +
          `<div class="ms-row-top">` +
          `<span class="ms-from">${escHtml(s.from_name || s.from)}</span>` +
          `<span class="ms-date">${escHtml(s.received)}</span>` +
          `</div>` +
          `<div class="ms-subject">${escHtml(s.subject)}</div>` +
          `</div>` +
          `</div>`,
      )
      .join("");
    const title = `✅ To-Do List (from ${md.count} email${md.count === 1 ? "" : "s"})`;
    return rows
      ? `<div class="ms-card"><div class="ms-title">${title}</div>${rows}</div>`
      : `<div class="ms-card"><div class="ms-title">${title}</div></div>`;
  }
  if (type === "todo_pushed") {
    const tasks = md.tasks || [];
    const listName = md.list_name || "Tasks";
    const rows = tasks
      .map(
        (t) =>
          `<div class="ms-row"><div class="ms-row-main"><div class="ms-subject">☑ ${escHtml(t)}</div></div></div>`,
      )
      .join("");
    const title = `✅ ${tasks.length} Task${tasks.length === 1 ? "" : "s"} added to "${escHtml(listName)}"`;
    return rows
      ? `<div class="ms-card"><div class="ms-title">${title}</div>${rows}</div>`
      : `<div class="ms-card"><div class="ms-title">${title}</div></div>`;
  }
  if (type === "task_added") {
    const listName = md.list_name || "Tasks";
    const task = md.task || "";
    return (
      `<div class="ms-card">` +
      `<div class="ms-title">☑ Task Added to "${escHtml(listName)}"</div>` +
      `<div class="ms-row"><div class="ms-row-main"><div class="ms-subject">${escHtml(task)}</div></div></div>` +
      `</div>`
    );
  }
  if (type === "task_completed") {
    const listName = md.list_name || "Tasks";
    const task = md.task || "";
    return (
      `<div class="ms-card">` +
      `<div class="ms-title">✅ Task Completed in "${escHtml(listName)}"</div>` +
      `<div class="ms-row"><div class="ms-row-main"><div class="ms-subject" style="text-decoration:line-through;opacity:0.7">${escHtml(task)}</div></div></div>` +
      `</div>`
    );
  }
  if (type === "task_deleted") {
    const listName = md.list_name || "Tasks";
    const task = md.task || "";
    return (
      `<div class="ms-card">` +
      `<div class="ms-title">🗑 Task Deleted from "${escHtml(listName)}"</div>` +
      `<div class="ms-row"><div class="ms-row-main"><div class="ms-subject" style="text-decoration:line-through;opacity:0.5">${escHtml(task)}</div></div></div>` +
      `</div>`
    );
  }
  return "";
}

// ── Web2 device auth connect handler (called from ChatWindow via emit) ─────────
async function handleAuthConnect({ provider }) {
  const savedPrompt = pendingAuthPrompt;

  if (provider === "microsoft") {
    const privHex = localStorage.getItem(LS_PRIV) || "";
    const ccHex = localStorage.getItem(LS_CC) || "";
    if (!privHex || !ccHex) {
      messages.value.push({
        role: "agent",
        html: "",
        deviceCode: {
          provider,
          status: "error",
          message:
            "YadaCoin wallet not loaded. Open your wallet and log in before connecting Microsoft.",
        },
      });
      return;
    }

    // The device code card — runApprovalFlow will update this reactively after rotation.
    const deviceCardIdx = messages.value.length;
    messages.value.push({
      role: "agent",
      html: "",
      deviceCode: { provider, status: "starting" },
    });

    // Show the W3C ApprovalCard so the connect rotation is recorded on-chain
    // with an OAuthTokenBinding VC.  Private metadata for runApprovalFlow is
    // stored in agentType._meta (not spread into the VC preview).
    pendingAuthPrompt = "";
    messages.value.push({
      role: "agent",
      html: "",
      showApproval: true,
      approvalContext: {
        scope: {
          type: "OAuthTokenBinding",
          services: ["OAuthTokenBinding"],
          provider: "microsoft",
        },
        agentType: {
          id: "microsoft_connect",
          authorizationType: "OAuthTokenBinding",
          _meta: { deviceCardIdx, savedPrompt },
        },
      },
    });
    // Trigger App.vue watcher by re-assigning the last element
    messages.value[messages.value.length - 1] = {
      ...messages.value[messages.value.length - 1],
    };
    return;
  }

  // ── Non-Microsoft providers: simple connect flow ─────────────────────────
  const idx = messages.value.length;
  messages.value.push({
    role: "agent",
    html: "",
    deviceCode: { provider, status: "starting" },
  });

  try {
    // If the wallet is loaded, derive an encryption key so the server can
    // encrypt the access token before storing it (wallet mode).  Without a
    // wallet the token remains server-side only (plain nonce approach).
    const privHex = localStorage.getItem(LS_PRIV) || "";
    let connectKelOpts = {};
    if (privHex) {
      const buf = await crypto.subtle.digest("SHA-256", hex.toBytes(privHex));
      connectKelOpts.tokenEncKeyHex = hex.fromBytes(new Uint8Array(buf));
    }
    const deviceInfo = await web2Connect(
      provider,
      getNodeUrl(),
      connectKelOpts,
    );
    messages.value[idx].deviceCode = {
      provider,
      status: "pending",
      user_code: deviceInfo.user_code,
      verification_uri: deviceInfo.verification_uri,
      expires_in: deviceInfo.expires_in,
    };
    await deviceInfo.poll();
    messages.value[idx].deviceCode = { provider, status: "authorized" };
    if (savedPrompt) {
      pendingAuthPrompt = "";
      // Remove the stale "Please connect" auth_required exchange from
      // chatHistory so the LLM doesn't see it as context for the re-send.
      // The exchange is always: [..., user(prompt), assistant(auth_required_reply)]
      if (
        chatHistory.length >= 2 &&
        chatHistory[chatHistory.length - 1]?.role === "assistant" &&
        chatHistory[chatHistory.length - 2]?.role === "user"
      ) {
        chatHistory.pop(); // remove auth_required assistant reply
        chatHistory.pop(); // remove the user prompt that triggered it
      }
      await send(savedPrompt);
    }
  } catch (err) {
    messages.value[idx].deviceCode = {
      provider,
      status: "error",
      message: String(err),
    };
  }
}

// Expose handleAuthConnect so ChatWindow can emit up to ChatPane

// ── Input auto-grow ──────────────────────────────────────────────────────────
function autoGrow(e) {
  const el = e.target;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 160) + "px";
}

// ── Agent registry discovery ──────────────────────────────────────────────────
/**
 * Search the blockchain agent registry for agents matching the user's intent.
 * Fires silently — if it fails or returns nothing, no message is shown.
 * Only runs once per intent switch (tracked by lastDiscoveredIntent).
 */
let lastDiscoveredIntent = "";

async function discoverAndPushAgents(intent, agentTypeId) {
  const key = `${agentTypeId}:${intent}`;
  if (key === lastDiscoveredIntent) return;
  lastDiscoveredIntent = key;
  try {
    const params = new URLSearchParams({
      intent,
      agent_type: agentTypeId,
      limit: "5",
    });
    const res = await fetch(
      getNodeUrl() + `/ai-agent-auth/api/agents/discover?${params}`,
    );
    if (!res.ok) return;
    const data = await res.json();
    const agents = (data.agents || []).slice(0, 5);
    if (!agents.length) return;

    const rows = agents
      .map(
        (a) =>
          `<div class="disc-agent-card">` +
          `<span class="disc-icon">${escHtml(a.icon || "🤖")}</span>` +
          `<div class="disc-body">` +
          `<a class="disc-label" href="${escHtml(a.endpoint_url)}" target="_blank" rel="noopener">${escHtml(a.label)}</a>` +
          (a.description
            ? `<div class="disc-desc">${escHtml(a.description)}</div>`
            : "") +
          `<div class="disc-caps">${(a.capabilities || []).map((c) => `<span class="disc-chip">${escHtml(c)}</span>`).join("")}</div>` +
          `</div></div>`,
      )
      .join("");

    pushAgent(
      `<div class="disc-header">🔍 Found ${agents.length} registered agent${agents.length > 1 ? "s" : ""} on-chain for <em>${escHtml(agentTypeId)}</em>:</div>` +
        `<div class="disc-list">${rows}</div>`,
      true,
    );
  } catch {
    // silent — discovery is best-effort
  }
}

// ── Agent Loop run ────────────────────────────────────────────────────────────
function _loopGetPublicKey() {
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

function _buildLoopHtml(
  loopPlan,
  loopStepResults,
  loopActiveSteps,
  loopFinalReply,
  loopError,
  loopStatus,
  loopWarnings,
) {
  let h = '<div class="loop-result">';
  if (loopWarnings && loopWarnings.length) {
    for (const w of loopWarnings) {
      h += `<div class="loop-warning">${escHtml(w)}</div>`;
    }
  }
  if (loopStatus && !loopFinalReply && !loopError) {
    h += `<div class="loop-status"><span class="loop-spinner"></span>${escHtml(loopStatus)}</div>`;
  }
  if (loopPlan) {
    h += '<div class="loop-plan">';
    if (loopPlan.reasoning)
      h += `<div class="loop-plan-reasoning">${escHtml(loopPlan.reasoning)}</div>`;
    h += '<ol class="loop-steps">';
    for (const s of loopPlan.steps || []) {
      const isDone = s.step in loopStepResults;
      const isActive = loopActiveSteps.has(s.step);
      const cls = isDone ? "lp-done" : isActive ? "lp-active" : "";
      const ind = isDone ? "✓" : isActive ? "●" : String(s.step);
      h += `<li class="loop-step ${cls}">`;
      h += `<span class="ls-num">${escHtml(ind)}</span>`;
      h += `<span class="ls-desc">${escHtml(s.description)}</span>`;
      h += `<span class="ls-badge">${escHtml(s.skill)}/${escHtml(s.action)}</span>`;
      if (isDone) {
        const r = loopStepResults[s.step];
        const rs = typeof r === "string" ? r : JSON.stringify(r, null, 2);
        h += `<div class="ls-result">${escHtml(rs.length > 220 ? rs.slice(0, 220) + "…" : rs)}</div>`;
      }
      h += "</li>";
    }
    h += "</ol></div>";
  }
  if (loopFinalReply) {
    h += `<div class="loop-final"><div class="loop-final-title">✓ Result</div><div class="loop-final-body">${escHtml(loopFinalReply)}</div></div>`;
  }
  if (loopError) {
    h += `<div class="loop-error">⚠ ${escHtml(loopError)}</div>`;
  }
  h += "</div>";
  return h;
}

async function runLoop() {
  const goal = userInput.value.trim();
  if (!goal || busy.value || !sessionReady.value) return;
  userInput.value = "";
  if (inputEl.value) inputEl.value.style.height = "auto";
  busy.value = true;
  pushUser(goal);

  const msgIdx = messages.value.length;
  messages.value.push({
    role: "agent",
    html: _buildLoopHtml(null, {}, new Set(), "", "", "Starting…", []),
  });

  let loopPlan = null;
  const loopStepResults = {};
  const loopActiveSteps = new Set();
  let loopStatus = "Starting…";
  let loopFinalReply = "";
  let loopError = "";
  const loopWarnings = [];

  function updateLoopMsg() {
    if (messages.value[msgIdx]) {
      messages.value[msgIdx] = {
        role: "agent",
        html: _buildLoopHtml(
          loopPlan,
          loopStepResults,
          loopActiveSteps,
          loopFinalReply,
          loopError,
          loopStatus,
          loopWarnings,
        ),
      };
    }
  }

  const llmCfg = getLlmSettings();

  // Derive Microsoft token decryption key (same as in send())
  let loopTokenEncKeyMs;
  if ((web2Sessions.value.microsoft || []).length > 0) {
    const privHex = localStorage.getItem(LS_PRIV) || "";
    if (privHex) {
      const buf = await crypto.subtle.digest("SHA-256", hex.toBytes(privHex));
      loopTokenEncKeyMs = hex.fromBytes(new Uint8Array(buf));
    }
  }

  const body = {
    mode: "loop",
    goal,
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
    token_enc_key_ms: loopTokenEncKeyMs || undefined,
    public_key: _loopGetPublicKey() || undefined,
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
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;
        try {
          const evt = JSON.parse(raw);
          switch (evt.type) {
            case "status":
              loopStatus = evt.message;
              break;
            case "warning":
              loopWarnings.push(evt.message);
              break;
            case "plan":
              loopPlan = { reasoning: evt.reasoning, steps: evt.steps || [] };
              loopStatus = "";
              break;
            case "step_start":
              loopActiveSteps.add(evt.step);
              break;
            case "step_result":
              loopStepResults[evt.step] = evt.output;
              loopActiveSteps.delete(evt.step);
              break;
            case "done":
              loopFinalReply = evt.reply || "";
              loopStatus = "";
              break;
            case "error":
              loopError = evt.message || evt.error || "Unknown error";
              loopStatus = "";
              break;
          }
          updateLoopMsg();
        } catch {
          // skip malformed lines
        }
      }
    }
  } catch (e) {
    loopError = String(e);
    updateLoopMsg();
  } finally {
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
  }
}

// ── Main send ────────────────────────────────────────────────────────────────
async function send(overridePrompt) {
  // overridePrompt must be a plain string — DOM events from @click/@keydown are ignored
  const override = typeof overridePrompt === "string" ? overridePrompt : null;
  const prompt = override ?? userInput.value.trim();
  if (!prompt || busy.value || !sessionReady.value) return;
  clearLastChoices();
  if (!override) {
    userInput.value = "";
    if (inputEl.value) {
      inputEl.value.style.height = "auto";
    }
  }
  busy.value = true;
  if (!override) pushUser(prompt);

  // Vendor follow-up mode — route to vendor chat instead of LLM
  if (vendorState.value) {
    let result;
    try {
      result = await sendVendorMessage(prompt);
    } finally {
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
    }
    // Vendor signalled exit — re-dispatch through main agent chat
    if (result?.exitVendor) {
      await send(prompt);
    }
    return;
  }

  chatHistory.push({ role: "user", content: prompt });

  const { index: thinkIdx } = pushThinking();

  // Derive token encryption key so the server can decrypt the MS access token
  // for inline read operations (list_emails, read_email, etc.).
  let tokenEncKeyMs;
  if ((web2Sessions.value.microsoft || []).length > 0) {
    const privHex = localStorage.getItem(LS_PRIV) || "";
    if (privHex) {
      const buf = await crypto.subtle.digest("SHA-256", hex.toBytes(privHex));
      tokenEncKeyMs = hex.fromBytes(new Uint8Array(buf));
    }
  }

  let data;
  try {
    const llmCfg = getLlmSettings();
    const resp = await fetch(getNodeUrl() + "/ai-agent-auth/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: chatHistory,
        agent_type: currentAgentId.value || "general",
        brave_api_key: getBraveApiKey() || undefined,
        web2_sessions: Object.keys(web2Sessions.value).length
          ? web2Sessions.value
          : undefined,
        token_enc_key_ms: tokenEncKeyMs || undefined,
        llm: {
          provider: llmCfg.provider,
          model: llmCfg.model || undefined,
          api_key: llmCfg.api_key || undefined,
          ollama_host: llmCfg.ollama_host || undefined,
          base_url: llmCfg.base_url || undefined,
        },
      }),
    });
    data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.status);
  } catch (e) {
    removeMsg(thinkIdx);
    pushAgent(
      `<span style="color:var(--red2)">⚠ Could not reach AI service: ${escHtml(String(e))}. ` +
        `Check LLM settings (⚙) or make sure Ollama is running (<code>ollama serve</code>).</span>`,
      true,
    );
    chatHistory.pop();
    busy.value = false;
    return;
  }

  removeMsg(thinkIdx);

  // Auto-switch agent type based on detected intent, then re-dispatch to new agent.
  // Loop up to MAX_HOPS to handle chains like therapy→general→travel in one send().
  const MAX_HOPS = 3;
  let hopCount = 0;
  while (
    hopCount < MAX_HOPS &&
    data.detected_agent_type &&
    data.detected_agent_type !== currentAgentId.value
  ) {
    hopCount++;
    const newAgent = props.agents?.find(
      (a) => a.id === data.detected_agent_type,
    );
    if (!newAgent) break;

    currentAgentId.value = data.detected_agent_type;
    localStorage.setItem(LS_ACTIVE_AGENT, currentAgentId.value);
    emit("agent-changed", newAgent);
    extractedScope = null; // reset scope when switching agent type

    // Re-send the user message to the new agent (chatHistory already contains it)
    const { index: redirectIdx } = pushThinking();
    try {
      const llmCfg2 = getLlmSettings();
      const resp2 = await fetch(getNodeUrl() + "/ai-agent-auth/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: chatHistory,
          agent_type: currentAgentId.value,
          brave_api_key: getBraveApiKey() || undefined,
          web2_sessions: Object.keys(web2Sessions.value).length
            ? web2Sessions.value
            : undefined,
          token_enc_key_ms: tokenEncKeyMs || undefined,
          llm: {
            provider: llmCfg2.provider,
            model: llmCfg2.model || undefined,
            api_key: llmCfg2.api_key || undefined,
            ollama_host: llmCfg2.ollama_host || undefined,
            base_url: llmCfg2.base_url || undefined,
          },
        }),
      });
      data = await resp2.json();
      if (!resp2.ok) throw new Error(data.error || resp2.status);
    } catch (e) {
      removeMsg(redirectIdx);
      pushAgent(
        `<span style="color:var(--red2)">⚠ Could not reach AI service: ${escHtml(String(e))}.</span>`,
        true,
      );
      busy.value = false;
      return;
    }
    removeMsg(redirectIdx);

    // Search on-chain registry for agents matching this intent
    if (currentAgentId.value !== "general") {
      discoverAndPushAgents(prompt, currentAgentId.value);
    }
  }

  // Merge extracted fields — never allow the LLM to set `confirmed` directly;
  // confirmation must come from the user explicitly in a separate turn.
  if (data.extracted) {
    if (!extractedScope) extractedScope = {};
    for (const [k, v] of Object.entries(data.extracted)) {
      if (k === "confirmed") continue; // strip: LLM cannot self-confirm
      if (v != null && v !== "") extractedScope[k] = v;
    }
  }

  chatHistory.push({ role: "assistant", content: data.reply });

  // For non-general agents, search the on-chain registry in the background.
  // The dedup guard prevents re-running for the same intent.
  if (currentAgentId.value && currentAgentId.value !== "general") {
    discoverAndPushAgents(prompt, currentAgentId.value);
  }

  // ── Wallet agent read-only actions (no approval needed) ──────────────────
  if (
    currentAgentId.value === "wallet_agent" &&
    extractedScope?.action &&
    ["get_balance", "get_transactions", "get_pending"].includes(
      extractedScope.action,
    )
  ) {
    const action = extractedScope.action;
    // Optimistically push the LLM reply first
    pushAgent(data.reply);
    // Then fetch and display the actual data
    const privKey = localStorage.getItem(LS_PRIV);
    if (privKey) {
      try {
        const pubHex = getPublicKeyHex(hex.toBytes(privKey));
        const baseUrl = getNodeUrl();
        if (action === "get_balance") {
          const res = await fetch(
            `${baseUrl}/ai-agent-auth/api/wallet/info?public_key=${encodeURIComponent(pubHex)}`,
          );
          if (res.ok) {
            const d = await res.json();
            pushAgent(
              `<div class="wallet-data-card">` +
                `<div class="wdc-title">💰 Balance</div>` +
                `<div class="wdc-address">Address: <code>${escHtml(d.address)}</code></div>` +
                `<div class="wdc-balance"><span class="wdc-amount">${escHtml(d.balance)}</span> YDA</div>` +
                `</div>`,
              true,
            );
          }
        } else if (action === "get_transactions") {
          // Fetch sent and received from existing wallet endpoints, merge
          const [sentRes, recvRes] = await Promise.all([
            fetch(
              `${baseUrl}/get-past-sent-txns?public_key=${encodeURIComponent(pubHex)}&page=1`,
            ),
            fetch(
              `${baseUrl}/get-past-received-txns?public_key=${encodeURIComponent(pubHex)}&page=1`,
            ),
          ]);
          const sentData = sentRes.ok
            ? await sentRes.json()
            : { past_transactions: [] };
          const recvData = recvRes.ok
            ? await recvRes.json()
            : { past_transactions: [] };
          const sentTxns = (sentData.past_transactions || []).map((t) => ({
            ...t,
            _direction: "sent",
          }));
          const recvTxns = (recvData.past_transactions || []).map((t) => ({
            ...t,
            _direction: "received",
          }));
          const txns = [...sentTxns, ...recvTxns]
            .sort((a, b) => (b.time || 0) - (a.time || 0))
            .slice(0, 10);
          if (!txns.length) {
            pushAgent(
              `<div class="wallet-data-card"><div class="wdc-title">📋 Transactions</div><div class="wdc-empty">No confirmed transactions found.</div></div>`,
              true,
            );
          } else {
            const rows = txns
              .slice(0, 10)
              .map((t) => {
                const dir = t._direction || "?";
                const dirIcon = dir === "sent" ? "↑" : "↓";
                const dirClass = dir === "sent" ? "wdc-sent" : "wdc-recv";
                const outs = (t.outputs || []).filter((o) => o.value > 0);
                const amt = outs.reduce((s, o) => s + (o.value || 0), 0);
                const to = outs.map((o) => o.to).join(", ");
                const ts = t.time
                  ? new Date(t.time * 1000).toLocaleString()
                  : "";
                return (
                  `<div class="wdc-txrow ${dirClass}">` +
                  `<span class="wdc-dir">${dirIcon}</span>` +
                  `<span class="wdc-amt">${amt.toFixed(8)} YDA</span>` +
                  `<span class="wdc-to">${escHtml(to.slice(0, 32))}…</span>` +
                  `<span class="wdc-ts">${escHtml(ts)}</span>` +
                  `</div>`
                );
              })
              .join("");
            pushAgent(
              `<div class="wallet-data-card">` +
                `<div class="wdc-title">📋 Recent Transactions</div>` +
                `${rows}` +
                `</div>`,
              true,
            );
          }
        } else if (action === "get_pending") {
          // Fetch sent and received pending from existing wallet endpoints, merge
          const [sentPendRes, recvPendRes] = await Promise.all([
            fetch(
              `${baseUrl}/get-past-pending-sent-txns?public_key=${encodeURIComponent(pubHex)}`,
            ),
            fetch(
              `${baseUrl}/get-past-pending-received-txns?public_key=${encodeURIComponent(pubHex)}`,
            ),
          ]);
          const sentPendData = sentPendRes.ok
            ? await sentPendRes.json()
            : { past_pending_transactions: [] };
          const recvPendData = recvPendRes.ok
            ? await recvPendRes.json()
            : { past_pending_transactions: [] };
          const sentPend = (sentPendData.past_pending_transactions || []).map(
            (t) => ({ ...t, _direction: "sent" }),
          );
          const recvPend = (recvPendData.past_pending_transactions || []).map(
            (t) => ({ ...t, _direction: "received" }),
          );
          const pending = [...sentPend, ...recvPend]
            .sort((a, b) => (b.time || 0) - (a.time || 0))
            .slice(0, 10);
          if (!pending.length) {
            pushAgent(
              `<div class="wallet-data-card"><div class="wdc-title">⏳ Pending Transactions</div><div class="wdc-empty">No pending transactions in mempool.</div></div>`,
              true,
            );
          } else {
            const rows = pending
              .slice(0, 10)
              .map((t) => {
                const dir = t._direction || "?";
                const dirIcon = dir === "sent" ? "↑" : "↓";
                const dirClass = dir === "sent" ? "wdc-sent" : "wdc-recv";
                const outs = (t.outputs || []).filter((o) => o.value > 0);
                const amt = outs.reduce((s, o) => s + (o.value || 0), 0);
                const to = outs.map((o) => o.to).join(", ");
                return (
                  `<div class="wdc-txrow ${dirClass}">` +
                  `<span class="wdc-dir">${dirIcon}</span>` +
                  `<span class="wdc-amt">${amt.toFixed(8)} YDA</span>` +
                  `<span class="wdc-to">${escHtml(to.slice(0, 32))}…</span>` +
                  `<span class="wdc-ts wdc-pending">pending</span>` +
                  `</div>`
                );
              })
              .join("");
            pushAgent(
              `<div class="wallet-data-card">` +
                `<div class="wdc-title">⏳ Pending Transactions</div>` +
                `${rows}` +
                `</div>`,
              true,
            );
          }
        }
      } catch {
        // silent — display is best-effort
      }
    }
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  // ── auth_required — attach connect button to the AI message ──────────────
  if (data.auth_required?.provider) {
    const provider = data.auth_required.provider;
    pendingAuthPrompt = prompt; // re-send after connecting
    const msg = pushAgent(data.reply);
    msg.authRequired = { provider };
    messages.value[messages.value.length - 1] = { ...msg };
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  // ── GitHub inline data card ───────────────────────────────────────────────
  if (data.github_data && data.github_data.type !== "error") {
    pushAgent(data.reply);
    pushAgent(renderGithubData(data.github_data), true);
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }
  if (data.github_data?.type === "error") {
    pushAgent(data.reply);
    pushAgent(
      `<span style="color:var(--red2)">⚠ GitHub API error: ${escHtml(data.github_data.message)}</span>`,
      true,
    );
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  // ── Microsoft inline data card ───────────────────────────────────────────
  if (data.microsoft_data && data.microsoft_data.type !== "error") {
    pushAgent(data.reply);
    pushAgent(renderMicrosoftData(data.microsoft_data), true);
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }
  if (data.microsoft_data?.type === "error") {
    pushAgent(data.reply);
    pushAgent(
      `<span style="color:var(--red2)">⚠ Microsoft API error: ${escHtml(data.microsoft_data.message)}</span>`,
      true,
    );
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  if (data.complete && extractedScope && Object.keys(extractedScope).length) {
    // Show the reply + scope summary inline as an HTML message
    const scopeLines = Object.entries(extractedScope)
      .filter(([k]) => k !== "action")
      .map(([k, v]) => {
        const val = Array.isArray(v)
          ? v.map((s) => `<strong>${escHtml(s)}</strong>`).join(", ")
          : `<strong>${escHtml(String(v))}</strong>`;
        return `${escHtml(k.replace(/_/g, " "))}: ${val}`;
      })
      .join("<br>");

    // Build agent-specific approval message
    let approvalPrompt;
    if (currentAgentId.value === "wallet_agent") {
      const amt = extractedScope.amount ?? "";
      const action = extractedScope.action ?? "send";
      if (action === "wrap") {
        const ethAddr = extractedScope.eth_address ?? "";
        approvalPrompt =
          `<br><br>` +
          `<strong>Wrap:</strong> ${escHtml(String(amt))} YDA → bridge → <code>${escHtml(ethAddr)}</code> (Ethereum)<br><br>` +
          `Please enter your second factor to authorize this wrap transaction.`;
      } else {
        const toAddr = extractedScope.to_address ?? "";
        approvalPrompt =
          `<br><br>` +
          `<strong>Send:</strong> ${escHtml(String(amt))} YDA → <code>${escHtml(toAddr)}</code><br><br>` +
          `Please enter your second factor to authorize this transaction.`;
      }
    } else {
      approvalPrompt =
        `<br><br>${scopeLines}<br><br>` +
        `To proceed I'll broadcast a rotation transaction committing this scope on-chain as a ` +
        `W3C Verifiable Credential. Please enter your second factor to approve.`;
    }

    const summaryMsg = pushAgent(escHtml(data.reply) + approvalPrompt, true);

    // Attach approval card state into the message
    summaryMsg.showApproval = true;
    summaryMsg.approvalContext = {
      scope: { ...extractedScope },
      agentType: currentAgentType.value,
    };
    // Replace with final reactive version
    messages.value[messages.value.length - 1] = { ...summaryMsg };
    busy.value = false;
  } else {
    const msg = pushAgent(data.reply);
    applyDataFields(msg, data);
    if (data.search_sources?.length) {
      msg.searchSources = data.search_sources;
    }
    busy.value = false;
  }
  nextTick(() => inputEl.value?.focus());
}

// ── Vendor follow-up conversation helpers ─────────────────────────────────────

/**
 * Build a signed VP from vpBase + a fresh challenge.
 * vpCanonicalBytes must be the pre-computed canonical bytes of vpBase.
 */
async function buildSignedVP(
  vpBase,
  vpCanonicalBytes,
  provPrivBytes,
  provPubHex,
  challenge,
) {
  const challengeBytes = new TextEncoder().encode(challenge);
  const msgBytes = new Uint8Array(
    challengeBytes.length + vpCanonicalBytes.length,
  );
  msgBytes.set(challengeBytes);
  msgBytes.set(vpCanonicalBytes, challengeBytes.length);
  const sigObj = await secp.signAsync(msgBytes, provPrivBytes);
  const proofValue = compactSigToDerBase64(sigObj);
  return {
    ...vpBase,
    proof: {
      type: "EcdsaSecp256k1Signature2019",
      challenge,
      created: new Date().toISOString(),
      proofPurpose: "authentication",
      verificationMethod: `did:yadacoin:${provPubHex}#keys-1`,
      proofValue,
    },
  };
}

/**
 * Call POST /api/vendor/<svc>/chat with a fresh challenge + re-signed VP.
 * Returns the parsed response data object.
 */
async function callVendorChatApi(service, vpData, vendorMessages) {
  const { vpBase, vpCanonicalBytes, provPrivBytes, provPubHex } = vpData;
  const llmCfg = getLlmSettings();

  // Fresh challenge
  const chalRes = await fetch(
    getNodeUrl() +
      `/ai-agent-auth/api/vendor/${service}/challenge?public_key=${encodeURIComponent(provPubHex)}`,
  );
  const chalData = await chalRes.json();
  if (!chalRes.ok || !chalData.challenge) throw new Error("no challenge");

  const vp = await buildSignedVP(
    vpBase,
    vpCanonicalBytes,
    provPrivBytes,
    provPubHex,
    chalData.challenge,
  );

  const chatRes = await fetch(
    getNodeUrl() + `/ai-agent-auth/api/vendor/${service}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        public_key: provPubHex,
        challenge: chalData.challenge,
        vp,
        messages: vendorMessages,
        llm: {
          provider: llmCfg.provider,
          model: llmCfg.model || undefined,
          api_key: llmCfg.api_key || undefined,
          ollama_host: llmCfg.ollama_host || undefined,
          base_url: llmCfg.base_url || undefined,
        },
      }),
    },
  );
  const data = await chatRes.json();
  if (!chatRes.ok) throw new Error(data.message || chatRes.status);
  return data;
}

/** Advance to the next service in the vendor queue, or clear vendorState if done. */
async function advanceVendorQueue() {
  const vs = vendorState.value;
  if (!vs || vs.queue.length === 0) {
    vendorState.value = null;
    return;
  }
  vs.current = vs.queue.shift();
  vs.vendorMessages = [
    { role: "user", content: "Hello, I'm ready to continue my booking." },
  ];

  const { index: thinkIdx } = pushThinking();
  try {
    const data = await callVendorChatApi(
      vs.current.service,
      vs.vpData,
      vs.vendorMessages,
    );
    removeMsg(thinkIdx);
    vs.vendorMessages.push({ role: "assistant", content: data.reply });
    if (data.complete) {
      if (data.credential) {
        saveBookingCredential(data.credential);
        postCredentialReceipt(data.credential).catch(() => {});
        emit("credential-issued");
      }
      pushAgent(
        `<strong>${escHtml(data.vendor)}:</strong><br>${marked.parse(data.reply)}` +
          `Confirmation: <code>${escHtml(data.confirmation)}</code>`,
        true,
      );
      await advanceVendorQueue();
    } else {
      const msg = pushAgent(
        `<strong>${escHtml(data.vendor)}:</strong><br>${marked.parse(data.reply)}`,
        true,
      );
      applyDataFields(msg, data);
    }
  } catch (e) {
    removeMsg(thinkIdx);
    pushAgent(
      `<span style="color:var(--red2)">⚠ ${escHtml(vs.current.vendorName)} error: ${escHtml(String(e))}</span>`,
      true,
    );
    vendorState.value = null;
  }
}

/** Handle one turn of vendor follow-up chat. */
async function sendVendorMessage(text) {
  const vs = vendorState.value;
  const { service, vendorName } = vs.current;

  vs.vendorMessages.push({ role: "user", content: text });

  const { index: thinkIdx } = pushThinking();
  try {
    const data = await callVendorChatApi(service, vs.vpData, vs.vendorMessages);
    removeMsg(thinkIdx);
    vs.vendorMessages.push({ role: "assistant", content: data.reply });
    if (data.exit_vendor) {
      // Vendor signals the user wants a different topic — tear down vendor flow
      // and re-route the same message through the main agent chat
      pushAgent(
        `<strong>${escHtml(data.vendor)}:</strong><br>${marked.parse(data.reply)}`,
        true,
      );
      vendorState.value = null;
      return { exitVendor: true };
    } else if (data.complete) {
      if (data.credential) {
        saveBookingCredential(data.credential);
        postCredentialReceipt(data.credential).catch(() => {});
        emit("credential-issued");
      }
      pushAgent(
        `<strong>${escHtml(data.vendor)}:</strong><br>${marked.parse(data.reply)}` +
          `Confirmation: <code>${escHtml(data.confirmation)}</code>`,
        true,
      );
      await advanceVendorQueue();
    } else {
      const msg = pushAgent(
        `<strong>${escHtml(data.vendor)}:</strong><br>${marked.parse(data.reply)}`,
        true,
      );
      applyDataFields(msg, data);
    }
  } catch (e) {
    removeMsg(thinkIdx);
    pushAgent(
      `<span style="color:var(--red2)">⚠ ${escHtml(vendorName)} error: ${escHtml(String(e))}</span>`,
      true,
    );
    vendorState.value = null;
  }
}

// ── Client-side rotation helper ───────────────────────────────────────────────
// Builds and broadcasts rotation transactions entirely in JS.
// Returns { prevPrivHex, prevCcHex, provPrivBytes, transactionId } on success
// or throws on failure.
async function doClientRotation(privBytes, ccBytes, sf, relationshipB64) {
  const child = deriveSecurePath(privBytes, ccBytes, sf);
  const gc1 = deriveSecurePath(child.priv, child.cc, sf);
  const gc2 = deriveSecurePath(gc1.priv, gc1.cc, sf);
  const gc3 = deriveSecurePath(gc2.priv, gc2.cc, sf);

  const currentPubHex = getPublicKeyHex(privBytes);
  const childPubHex = getPublicKeyHex(child.priv);
  const gc1PubHex = getPublicKeyHex(gc1.priv);
  const gc2PubHex = getPublicKeyHex(gc2.priv);
  const gc3PubHex = getPublicKeyHex(gc3.priv);

  // P2PKH addresses
  const currentPkh = getP2PKH(hex.toBytes(currentPubHex));
  const childPkh = getP2PKH(hex.toBytes(childPubHex));
  const gc1Pkh = getP2PKH(hex.toBytes(gc1PubHex));
  const gc2Pkh = getP2PKH(hex.toBytes(gc2PubHex));
  const gc3Pkh = getP2PKH(hex.toBytes(gc3PubHex));

  // Fetch prev_public_key_hash from the existing /key-event-log endpoint.
  // The last KEL entry's public_key_hash is the address that committed to
  // currentPkh as its prerotated key (i.e. K_{n-1}).  Empty log = inception.
  const kelRes = await fetch(
    getNodeUrl() +
      "/key-event-log?username_signature=asdf&public_key=" +
      encodeURIComponent(currentPubHex),
  );
  const kelData = await kelRes.json();
  if (!kelRes.ok) throw new Error(kelData.message || String(kelRes.status));
  const kel = kelData.key_event_log || [];

  // Use the last KEL entry's public_key_hash — that is the address which
  // pre-committed to the current signing key, i.e. K_{n-1}'s address.
  // The server handler (keyrotation/handlers.py) sets:
  //   prev_public_key_hash = latest.public_key_hash
  const prevPublicKeyHash =
    kel.length > 0 ? (kel[kel.length - 1].public_key_hash ?? "") : "";

  // Invariant: if prevPublicKeyHash === currentPkh the stored key hasn't been
  // advanced past the inception (e.g. wallet re-imported after inception hit
  // mempool but before localStorage was updated).  Advance LS_PRIV silently
  // and re-run with the corrected key — no error surfaced to the user.
  if (prevPublicKeyHash === currentPkh) {
    localStorage.setItem(LS_PRIV, hex.fromBytes(child.priv));
    localStorage.setItem(LS_CC, hex.fromBytes(child.cc));
    return doClientRotation(child.priv, child.cc, sf, relationshipB64);
  }

  // relationship_hash = sha256("") for empty relationship
  const enc = new TextEncoder();
  const relStr = relationshipB64 || "";
  const relHashBytes = sha256(enc.encode(relStr));
  const relHashHex = hex.fromBytes(relHashBytes);

  const txnTime = Math.floor(Date.now() / 1000);

  // Build unconfirmed transaction (signed by current key K_n)
  const unconfirmedTxn = await buildRotationTxn({
    signerPrivBytes: privBytes,
    publicKeyHex: currentPubHex,
    prerotatedPkh: childPkh,
    twicePrerotatedPkh: gc1Pkh,
    publicKeyHash: currentPkh,
    prevPublicKeyHash,
    relationship: relStr,
    relationshipHash: relHashHex,
    txnTime,
    inputs: [],
    outputs: [{ to: childPkh, value: 0.0 }],
  });

  // Build confirming transaction (signed by child key K_{n+1})
  const confirmingTxn = await buildRotationTxn({
    signerPrivBytes: child.priv,
    publicKeyHex: childPubHex,
    prerotatedPkh: gc1Pkh,
    twicePrerotatedPkh: gc2Pkh,
    publicKeyHash: childPkh,
    prevPublicKeyHash: currentPkh,
    relationship: "",
    relationshipHash: "",
    txnTime,
    inputs: [],
    outputs: [{ to: gc1Pkh, value: 0.0 }],
  });

  // Broadcast both transactions directly to the node's /transaction endpoint
  const bcastRes = await fetch(
    getNodeUrl() + "/transaction?username_signature=1",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify([unconfirmedTxn, confirmingTxn]),
    },
  );
  const bcastData = await bcastRes.json();
  if (!bcastRes.ok || bcastData.status === false)
    throw new Error(bcastData.message || String(bcastRes.status));

  return {
    prevPrivHex: hex.fromBytes(child.priv),
    prevCcHex: hex.fromBytes(child.cc),
    provPrivBytes: gc1.priv,
    transactionId: unconfirmedTxn.id,
  };
}

// ── Hardware-wallet rotation helper ──────────────────────────────────────────
// Active-key model:
//   • `stored`     = K_n  — the locally-persisted active hardware key. Signs
//                            the unconfirmed rotation tx silently (no scan).
//   • `confirming` = K_{n+1} — scanned QR; signs the confirming tx.
//   • `nextActive` = K_{n+2} — scanned QR; becomes the new stored active and
//                              the agent DID for the VP this round.
//
// Returns { provPrivBytes, transactionId, nextPubHex } where provPrivBytes is
// K_{n+2}'s private key (used to sign the VP for the action endpoint).
async function doHardwareRotation(
  stored,
  confirming,
  nextActive,
  relationshipB64,
) {
  if (!stored || !confirming || !nextActive)
    throw new Error(
      "Hardware rotation requires stored active key plus two scanned QRs.",
    );

  async function lookupPrev(address) {
    try {
      const r = await fetch(
        getNodeUrl() +
          "/key-rotation/prev-key-hash?address=" +
          encodeURIComponent(address),
      );
      if (!r.ok) return null;
      const j = await r.json();
      return j.prev_public_key_hash ?? null;
    } catch {
      return null;
    }
  }
  const prevForUnconfirmed =
    (await lookupPrev(stored.publicKeyHash)) ??
    (stored.prevPublicKeyHash || "");

  const enc = new TextEncoder();
  const relStr = relationshipB64 || "";
  const relHashBytes = sha256(enc.encode(relStr));
  const relHashHex = hex.fromBytes(relHashBytes);

  const txnTime = Math.floor(Date.now() / 1000);

  // Unconfirmed tx — signed by K_n (stored), commits scope.
  const unconfirmedTxn = await buildRotationTxn({
    signerPrivBytes: stored.privBytes,
    publicKeyHex: stored.publicKeyHex,
    prerotatedPkh: stored.prerotatedKeyHash,
    twicePrerotatedPkh: stored.twicePrerotatedKeyHash,
    publicKeyHash: stored.publicKeyHash,
    prevPublicKeyHash: prevForUnconfirmed,
    relationship: relStr,
    relationshipHash: relHashHex,
    txnTime,
    inputs: [],
    outputs: [{ to: stored.prerotatedKeyHash, value: 0.0 }],
  });

  // Confirming tx — signed by K_{n+1} (confirming), no relationship payload.
  const confirmingTxn = await buildRotationTxn({
    signerPrivBytes: confirming.privBytes,
    publicKeyHex: confirming.publicKeyHex,
    prerotatedPkh: confirming.prerotatedKeyHash,
    twicePrerotatedPkh: confirming.twicePrerotatedKeyHash,
    publicKeyHash: confirming.publicKeyHash,
    prevPublicKeyHash: stored.publicKeyHash,
    relationship: "",
    relationshipHash: "",
    txnTime,
    inputs: [],
    outputs: [{ to: confirming.prerotatedKeyHash, value: 0.0 }],
  });

  const bcastRes = await fetch(
    getNodeUrl() + "/transaction?username_signature=1",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify([unconfirmedTxn, confirmingTxn]),
    },
  );
  const bcastData = await bcastRes.json();
  if (!bcastRes.ok || bcastData.status === false)
    throw new Error(bcastData.message || String(bcastRes.status));

  // Advance the stored active key to K_{n+2}. This persists nextActive's
  // private key bytes so the next round can sign its unconfirmed tx silently.
  setHardwareActive(nextActive);

  // VP for this action is signed by K_{n+2} — the new active key. Its DID
  // is K_{n+2}'s public key, which is committed in the chain only as the
  // prerotated_key_hash of the confirming tx (so the verifier's revocation
  // check passes — it has not yet appeared as any entry's public_key_hash).
  return {
    provPrivBytes: nextActive.privBytes,
    transactionId: unconfirmedTxn.id,
    nextPubHex: nextActive.publicKeyHex,
  };
}

// ── Approval handler (called from App.vue overlay) ────────────────────────────
// Exposed so parent can invoke from ApprovalCard emit
async function runApprovalFlow(
  scope,
  agentType,
  { secondFactor, paymentMethod, hardware },
  onStep,
  onDone,
) {
  // ── Microsoft OAuth connect — rotation + device flow ──────────────────────
  if (agentType?.id === "microsoft_connect") {
    const sf = secondFactor;
    const { deviceCardIdx, savedPrompt: connectSavedPrompt } =
      agentType._meta || {};
    const storedPriv = localStorage.getItem(LS_PRIV);
    const storedCc = localStorage.getItem(LS_CC);

    const privBytes = hex.toBytes(storedPriv);
    const ccBytes = hex.toBytes(storedCc);
    const child = deriveSecurePath(privBytes, ccBytes, sf);
    const childPubHex = getPublicKeyHex(child.priv);
    const gc1 = deriveSecurePath(child.priv, child.cc, sf);
    const gc2 = deriveSecurePath(gc1.priv, gc1.cc, sf);
    const agentPubHex = getPublicKeyHex(gc2.priv);
    const operatorPubHex = getPublicKeyHex(privBytes);

    const vcBind = {
      "@context": [
        "https://www.w3.org/ns/credentials/v2",
        "https://yadacoin.io/contexts/agent-auth/v1",
      ],
      type: ["VerifiableCredential", "AgentAuthorizationCredential"],
      issuer: `did:yadacoin:${operatorPubHex}`,
      validFrom: new Date().toISOString(),
      credentialStatus: { type: "YadaKELStatus", mode: "rotation" },
      credentialSubject: {
        id: `did:yadacoin:${agentPubHex}`,
        agentAuthorization: {
          type: "OAuthTokenBinding",
          services: ["OAuthTokenBinding"],
          provider: "microsoft",
        },
      },
    };
    const relB64 = btoa(unescape(encodeURIComponent(JSON.stringify(vcBind))));

    onStep("Broadcasting OAuthTokenBinding rotation on-chain…");
    let rotateData;
    try {
      if (isClientWallet()) {
        const clientRot = await doClientRotation(
          privBytes,
          ccBytes,
          sf,
          relB64,
        );
        rotateData = {
          prev_private_key: clientRot.prevPrivHex,
          prev_chain_code: clientRot.prevCcHex,
          transaction_id: clientRot.transactionId,
          status: true,
        };
      } else {
        const rotRes = await fetch(
          getNodeUrl() + "/key-rotation/derived-child-key",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              public_key: childPubHex,
              second_factor: sf,
              signature: "",
              relationship: relB64,
            }),
          },
        );
        rotateData = await rotRes.json();
        if (!rotRes.ok || !rotateData.status) {
          throw new Error(rotateData.message || String(rotRes.status));
        }
      }
    } catch (e) {
      onStep("Rotation failed: " + e.message, "fail");
      onDone(false, "Rotation failed: " + escHtml(e.message));
      if (deviceCardIdx != null && messages.value[deviceCardIdx]) {
        messages.value[deviceCardIdx].deviceCode = {
          provider: "microsoft",
          status: "error",
          message: "Rotation failed: " + e.message,
        };
      }
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }

    // Advance LS_PRIV to the post-rotation key.
    // tokenEncKey is derived from this new key so it matches what runApprovalFlow
    // (execute time) reads as storedPrivMs — i.e. LS_PRIV before the execute rotation.
    await web2RekeyActiveSessions(
      storedPriv,
      rotateData.prev_private_key,
      getNodeUrl(),
      isClientWallet(),
    );
    localStorage.setItem(LS_PRIV, rotateData.prev_private_key);
    if (rotateData.prev_chain_code)
      localStorage.setItem(LS_CC, rotateData.prev_chain_code);
    emit("session-rotated", rotateData.prev_private_key);
    onStep(
      "Rotation committed · txid " +
        (rotateData.transaction_id || "").slice(0, 20) +
        "…",
      "done",
    );

    const tokenEncKeyBuf = await crypto.subtle.digest(
      "SHA-256",
      hex.toBytes(rotateData.prev_private_key),
    );
    const tokenEncKeyHex = hex.fromBytes(new Uint8Array(tokenEncKeyBuf));

    // Dismiss the approval overlay — device card becomes visible
    onDone(true, "");

    // Start device flow
    try {
      const deviceInfo = await web2Connect("microsoft", getNodeUrl(), {
        rootPrivHex: rotateData.prev_private_key,
        rootCcHex: rotateData.prev_chain_code || storedCc,
        tokenEncKeyHex,
      });
      if (deviceCardIdx != null && messages.value[deviceCardIdx]) {
        messages.value[deviceCardIdx].deviceCode = {
          provider: "microsoft",
          status: "pending",
          user_code: deviceInfo.user_code,
          verification_uri: deviceInfo.verification_uri,
          expires_in: deviceInfo.expires_in,
        };
      }
      await deviceInfo.poll();
      if (deviceCardIdx != null && messages.value[deviceCardIdx]) {
        messages.value[deviceCardIdx].deviceCode = {
          provider: "microsoft",
          status: "authorized",
        };
      }
      if (connectSavedPrompt) {
        await send(connectSavedPrompt);
      }
    } catch (err) {
      if (deviceCardIdx != null && messages.value[deviceCardIdx]) {
        messages.value[deviceCardIdx].deviceCode = {
          provider: "microsoft",
          status: "error",
          message: String(err),
        };
      }
    }
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  // ── Node config — key rotation then direct apply call, no vendor chat ────────
  if (agentType?.id === "node_config") {
    if (isClientWallet() || isHardwareWallet()) {
      onDone(
        false,
        "⚠ Node config changes are only available for node-wallet mode. Personal and hardware wallets cannot modify node settings.",
      );
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }
    const storedPriv0 = localStorage.getItem(LS_PRIV);
    const storedCc0 = localStorage.getItem(LS_CC);
    const sf0 = secondFactor;

    onStep("Deriving pre-committed child key…");
    const privBytes0 = hex.toBytes(storedPriv0);
    const ccBytes0 = hex.toBytes(storedCc0);
    const child0 = deriveSecurePath(privBytes0, ccBytes0, sf0);
    const childPubHex0 = getPublicKeyHex(child0.priv);
    onStep(
      "Pre-committed key derived: " + childPubHex0.slice(0, 20) + "…",
      "done",
    );

    onStep("Broadcasting rotation transaction…");
    let rotateData0;
    try {
      const rotateRes0 = await fetch(
        getNodeUrl() + "/key-rotation/derived-child-key",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            public_key: childPubHex0,
            second_factor: sf0,
            signature: "",
            relationship: "",
          }),
        },
      );
      rotateData0 = await rotateRes0.json();
      if (
        !rotateRes0.ok ||
        !rotateData0.status ||
        !rotateData0.prerotated_private_key
      ) {
        throw new Error(rotateData0.message || String(rotateRes0.status));
      }
    } catch (e) {
      onStep("Rotation failed: " + e.message, "fail");
      onDone(false, "Rotation failed: " + escHtml(e.message));
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }

    await web2RekeyActiveSessions(
      storedPriv0,
      rotateData0.prev_private_key,
      getNodeUrl(),
      false,
    );
    localStorage.setItem(LS_PRIV, rotateData0.prev_private_key);
    if (rotateData0.prev_chain_code)
      localStorage.setItem(LS_CC, rotateData0.prev_chain_code);
    emit("session-rotated", rotateData0.prev_private_key);
    onStep(
      "Rotation committed · txid " +
        rotateData0.transaction_id.slice(0, 20) +
        "…",
      "done",
    );

    // Build a minimal VP (no config data) signed by the prerotated key
    onStep("Building Verifiable Presentation…");
    const provPrivBytes0 = hex.toBytes(rotateData0.prerotated_private_key);
    const provPubHex0 = getPublicKeyHex(provPrivBytes0);
    const operatorPubHex0 = getPublicKeyHex(privBytes0);

    const gc1_0 = deriveSecurePath(child0.priv, child0.cc, sf0);
    const gc2_0 = deriveSecurePath(gc1_0.priv, gc1_0.cc, sf0);
    const agentPubHex0 = getPublicKeyHex(gc2_0.priv);

    const vc0 = {
      "@context": [
        "https://www.w3.org/ns/credentials/v2",
        "https://yadacoin.io/contexts/agent-auth/v1",
      ],
      type: ["VerifiableCredential", "AgentAuthorizationCredential"],
      issuer: `did:yadacoin:${operatorPubHex0}`,
      validFrom: new Date().toISOString(),
      credentialStatus: { type: "YadaKELStatus", mode: "rotation" },
      credentialSubject: {
        id: `did:yadacoin:${agentPubHex0}`,
        agentAuthorization: {
          type: "NodeConfigAuthorization",
          services: ["NodeConfigAuthorization"],
        },
      },
    };

    const vpBase0 = {
      "@context": ["https://www.w3.org/ns/credentials/v2"],
      type: ["VerifiablePresentation"],
      holder: `did:yadacoin:${provPubHex0}`,
      verifiableCredential: [vc0],
    };

    function deepSortKeys0(obj) {
      if (Array.isArray(obj)) return obj.map(deepSortKeys0);
      if (obj !== null && typeof obj === "object") {
        const s = {};
        Object.keys(obj)
          .sort()
          .forEach((k) => (s[k] = deepSortKeys0(obj[k])));
        return s;
      }
      return obj;
    }

    const vpCanonicalBytes0 = new TextEncoder().encode(
      JSON.stringify(deepSortKeys0(vpBase0)),
    );

    // Get challenge
    onStep("Fetching challenge…");
    let chalData0;
    try {
      const chalRes0 = await fetch(
        getNodeUrl() +
          `/ai-agent-auth/api/challenge?public_key=${encodeURIComponent(provPubHex0)}`,
      );
      chalData0 = await chalRes0.json();
      if (!chalRes0.ok || !chalData0.challenge) throw new Error("no challenge");
    } catch (e) {
      onStep("Challenge failed: " + e.message, "fail");
      onDone(false, "Challenge failed: " + escHtml(e.message));
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }

    const vp0 = await buildSignedVP(
      vpBase0,
      vpCanonicalBytes0,
      provPrivBytes0,
      provPubHex0,
      chalData0.challenge,
    );

    onStep("Applying config change…");
    try {
      const applyRes = await fetch(
        getNodeUrl() + "/ai-agent-auth/api/node-config/apply",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            public_key: provPubHex0,
            challenge: chalData0.challenge,
            vp: vp0,
            key: scope.config_key,
            value: scope.new_value,
          }),
        },
      );
      const applyData = await applyRes.json();
      if (!applyRes.ok)
        throw new Error(
          applyData.error || applyData.message || String(applyRes.status),
        );
      onStep("Config updated — node restarting", "done");
      onDone(
        true,
        `✅ <strong>Config updated!</strong><br><br>` +
          `<strong>${escHtml(scope.config_key)}</strong> → <code>${escHtml(String(scope.new_value))}</code><br><br>` +
          `The node is restarting to apply the change.<br>` +
          `Scope on-chain: <a href="${origin}/explorer?term=${rotateData0.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${rotateData0.transaction_id.slice(0, 24)}…</a>`,
      );
    } catch (e) {
      onStep("Apply failed: " + e.message, "fail");
      onDone(false, "Config apply failed: " + escHtml(e.message));
    }
    extractedScope = null;
    chatHistory = [];
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  // ── Wallet agent — key rotation then send/wrap transaction ───────────────
  if (agentType?.id === "wallet_agent") {
    const hwMode = isHardwareWallet();
    const sfW = secondFactor;
    const isWrap = scope.action === "wrap";
    const WRAP_BRIDGE = "16U1gAmHazqqEkbRE9KFPShAperjJreMRA";
    const toAddrW = isWrap ? WRAP_BRIDGE : scope.to_address || "";
    const ethAddrW = isWrap ? scope.eth_address || "" : "";
    const amtW = parseFloat(scope.amount) || 0;

    // Resolve operator/agent public keys + signing material based on mode.
    let privBytesW = null;
    let ccBytesW = null;
    let childW = null;
    let childPubHexW = "";
    let operatorPubHexW = "";
    let agentPubHexW = "";
    if (hwMode) {
      if (!hardware?.stored || !hardware?.confirming || !hardware?.nextActive) {
        onDone(
          false,
          "Hardware wallet rotation requires the stored active key plus both QR scans.",
        );
        busy.value = false;
        nextTick(() => inputEl.value?.focus());
        return;
      }
      operatorPubHexW = hardware.stored.publicKeyHex;
      agentPubHexW = hardware.nextActive.publicKeyHex;
      childPubHexW = hardware.stored.publicKeyHex;
    } else {
      const storedPrivW = localStorage.getItem(LS_PRIV);
      const storedCcW = localStorage.getItem(LS_CC);
      onStep("Deriving pre-committed child key…");
      privBytesW = hex.toBytes(storedPrivW);
      ccBytesW = hex.toBytes(storedCcW);
      childW = deriveSecurePath(privBytesW, ccBytesW, sfW);
      childPubHexW = getPublicKeyHex(childW.priv);
      onStep(
        "Pre-committed key derived: " + childPubHexW.slice(0, 20) + "…",
        "done",
      );
    }

    onStep("Broadcasting rotation transaction…");
    let rotateDataW;
    try {
      if (!hwMode) {
        const gc1W = deriveSecurePath(childW.priv, childW.cc, sfW);
        const gc2W = deriveSecurePath(gc1W.priv, gc1W.cc, sfW);
        agentPubHexW = getPublicKeyHex(gc2W.priv);
        operatorPubHexW = getPublicKeyHex(privBytesW);
      }

      const vcW = {
        "@context": [
          "https://www.w3.org/ns/credentials/v2",
          "https://yadacoin.io/contexts/agent-auth/v1",
        ],
        type: ["VerifiableCredential", "AgentAuthorizationCredential"],
        issuer: `did:yadacoin:${operatorPubHexW}`,
        validFrom: new Date().toISOString(),
        credentialStatus: { type: "YadaKELStatus", mode: "rotation" },
        credentialSubject: {
          id: `did:yadacoin:${agentPubHexW}`,
          agentAuthorization: {
            type: "WalletAuthorization",
            services: ["WalletAuthorization"],
            to_address: toAddrW,
            amount: amtW,
            ...(isWrap ? { eth_address: ethAddrW } : {}),
          },
        },
      };

      const relB64W = btoa(unescape(encodeURIComponent(JSON.stringify(vcW))));

      if (hwMode) {
        const hwRot = await doHardwareRotation(
          hardware.stored,
          hardware.confirming,
          hardware.nextActive,
          relB64W,
        );
        rotateDataW = {
          prev_private_key: null,
          prev_chain_code: null,
          prerotated_private_key: hex.fromBytes(hwRot.provPrivBytes),
          transaction_id: hwRot.transactionId,
          status: true,
        };
      } else if (isClientWallet()) {
        const clientRot = await doClientRotation(
          privBytesW,
          ccBytesW,
          sfW,
          relB64W,
        );
        rotateDataW = {
          prev_private_key: clientRot.prevPrivHex,
          prev_chain_code: clientRot.prevCcHex,
          prerotated_private_key: hex.fromBytes(clientRot.provPrivBytes),
          transaction_id: clientRot.transactionId,
          status: true,
        };
      } else {
        const rotResW = await fetch(
          getNodeUrl() + "/key-rotation/derived-child-key",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              public_key: childPubHexW,
              second_factor: sfW,
              signature: "",
              relationship: relB64W,
            }),
          },
        );
        rotateDataW = await rotResW.json();
        if (
          !rotResW.ok ||
          !rotateDataW.status ||
          !rotateDataW.prerotated_private_key
        ) {
          throw new Error(rotateDataW.message || String(rotResW.status));
        }
      }
    } catch (e) {
      onStep("Rotation failed: " + e.message, "fail");
      onDone(false, "Rotation failed: " + escHtml(e.message));
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }

    if (hwMode) {
      // Hardware mode: doHardwareRotation already persisted nextActive as the
      // new stored active key (via setHardwareActive). Mirror the public key
      // for the App.vue session pill.
      emit("session-rotated", hardware.nextActive.publicKeyHex);
    } else {
      await web2RekeyActiveSessions(
        storedPrivW,
        rotateDataW.prev_private_key,
        getNodeUrl(),
        isClientWallet(),
      );
      localStorage.setItem(LS_PRIV, rotateDataW.prev_private_key);
      if (rotateDataW.prev_chain_code)
        localStorage.setItem(LS_CC, rotateDataW.prev_chain_code);
      emit("session-rotated", rotateDataW.prev_private_key);
    }
    onStep(
      "Rotation committed · txid " +
        rotateDataW.transaction_id.slice(0, 20) +
        "…",
      "done",
    );

    onStep("Building Verifiable Presentation…");
    const provPrivBytesW = hex.toBytes(rotateDataW.prerotated_private_key);
    const provPubHexW = getPublicKeyHex(provPrivBytesW);
    // Reuse the operator/agent public keys resolved earlier — they were
    // computed differently for hardware vs. seed-backed wallets.
    const operatorPubHexW2 = operatorPubHexW;
    const agentPubHexW2 = agentPubHexW;

    const vcW2 = {
      "@context": [
        "https://www.w3.org/ns/credentials/v2",
        "https://yadacoin.io/contexts/agent-auth/v1",
      ],
      type: ["VerifiableCredential", "AgentAuthorizationCredential"],
      issuer: `did:yadacoin:${operatorPubHexW2}`,
      validFrom: new Date().toISOString(),
      credentialStatus: { type: "YadaKELStatus", mode: "rotation" },
      credentialSubject: {
        id: `did:yadacoin:${agentPubHexW2}`,
        agentAuthorization: {
          type: "WalletAuthorization",
          services: ["WalletAuthorization"],
          to_address: toAddrW,
          amount: amtW,
          ...(isWrap ? { eth_address: ethAddrW } : {}),
        },
      },
    };

    const vpBaseW = {
      "@context": ["https://www.w3.org/ns/credentials/v2"],
      type: ["VerifiablePresentation"],
      holder: `did:yadacoin:${provPubHexW}`,
      verifiableCredential: [vcW2],
    };

    function deepSortKeysW(obj) {
      if (Array.isArray(obj)) return obj.map(deepSortKeysW);
      if (obj !== null && typeof obj === "object") {
        const s = {};
        Object.keys(obj)
          .sort()
          .forEach((k) => (s[k] = deepSortKeysW(obj[k])));
        return s;
      }
      return obj;
    }

    const vpCanonicalBytesW = new TextEncoder().encode(
      JSON.stringify(deepSortKeysW(vpBaseW)),
    );

    onStep("Fetching challenge…");
    let chalDataW;
    try {
      const chalResW = await fetch(
        getNodeUrl() +
          `/ai-agent-auth/api/challenge?public_key=${encodeURIComponent(provPubHexW)}`,
      );
      chalDataW = await chalResW.json();
      if (!chalResW.ok || !chalDataW.challenge) throw new Error("no challenge");
    } catch (e) {
      onStep("Challenge failed: " + e.message, "fail");
      onDone(false, "Challenge failed: " + escHtml(e.message));
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }

    const vpW = await buildSignedVP(
      vpBaseW,
      vpCanonicalBytesW,
      provPrivBytesW,
      provPubHexW,
      chalDataW.challenge,
    );

    onStep("Submitting transaction…");
    try {
      const sendRes = await fetch(
        getNodeUrl() + "/ai-agent-auth/api/wallet/send",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            public_key: provPubHexW,
            challenge: chalDataW.challenge,
            vp: vpW,
            ...(isWrap
              ? { eth_address: ethAddrW, amount: amtW }
              : { to_address: toAddrW, amount: amtW }),
          }),
        },
      );
      const sendData = await sendRes.json();
      if (!sendRes.ok)
        throw new Error(
          sendData.error || sendData.message || String(sendRes.status),
        );
      onStep("Transaction submitted", "done");
      onDone(
        true,
        isWrap
          ? `✅ <strong>Wrap transaction sent!</strong><br><br>` +
              `<strong>Amount:</strong> ${escHtml(String(amtW))} YDA<br>` +
              `<strong>Ethereum address:</strong> <code>${escHtml(ethAddrW)}</code><br>` +
              (sendData.transaction_id
                ? `<strong>Transaction ID:</strong> <code>${escHtml(String(sendData.transaction_id).slice(0, 32))}…</code><br>`
                : "") +
              `<br>KEL authorization on-chain: <a href="${origin}/explorer?term=${rotateDataW.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${rotateDataW.transaction_id.slice(0, 24)}…</a>`
          : `✅ <strong>Transaction sent!</strong><br><br>` +
              `<strong>To:</strong> <code>${escHtml(toAddrW)}</code><br>` +
              `<strong>Amount:</strong> ${escHtml(String(amtW))} YDA<br>` +
              (sendData.transaction_id
                ? `<strong>Transaction ID:</strong> <code>${escHtml(String(sendData.transaction_id).slice(0, 32))}…</code><br>`
                : "") +
              `<br>KEL authorization on-chain: <a href="${origin}/explorer?term=${rotateDataW.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${rotateDataW.transaction_id.slice(0, 24)}…</a>`,
      );
    } catch (e) {
      onStep("Send failed: " + e.message, "fail");
      onDone(false, "Transaction failed: " + escHtml(e.message));
    }
    extractedScope = null;
    chatHistory = [];
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  // ── Agent registration — server signs, no key rotation needed ──────────────
  if (agentType?.id === "agent_registration") {
    onStep("Broadcasting agent registration to blockchain…");
    try {
      const capabilities = (scope.capabilities || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const res = await fetch(
        getNodeUrl() + "/ai-agent-auth/api/agents/register",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            label: scope.label || "",
            description: scope.description || "",
            agent_type: scope.agent_type || "general",
            capabilities,
            endpoint_url: scope.endpoint_url || "",
            icon: scope.icon || "🤖",
          }),
        },
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || String(res.status));
      onStep("Agent registered · ID " + data.agent_id, "done");
      onDone(
        true,
        `✅ <strong>Agent registered on-chain!</strong><br><br>` +
          `<strong>Label:</strong> ${escHtml(scope.label)}<br>` +
          `<strong>Agent ID:</strong> <code>${escHtml(data.agent_id)}</code><br>` +
          `<strong>Transaction:</strong> <code>${escHtml((data.transaction_signature || "").slice(0, 32))}…</code>`,
      );
    } catch (e) {
      onStep("Registration failed: " + e.message, "fail");
      onDone(false, "Registration failed: " + escHtml(e.message));
    }
    extractedScope = null;
    chatHistory = [];
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  // ── Microsoft write action — rotation then execute ────────────────────────
  if (currentAgentId.value === "microsoft") {
    const sfMs = secondFactor;
    const storedPrivMs = localStorage.getItem(LS_PRIV);
    const storedCcMs = localStorage.getItem(LS_CC);

    // Derive tokenEncKey = sha256(current LS_PRIV) BEFORE the action rotation
    // changes LS_PRIV.  This key was used to encrypt the access_token at
    // connect time.  After the rotation, the old key is gone from the browser,
    // making the token permanently inaccessible without this key.
    const tokenEncKeyBuf = await crypto.subtle.digest(
      "SHA-256",
      hex.toBytes(storedPrivMs),
    );
    const tokenEncKeyHexMs = hex.fromBytes(new Uint8Array(tokenEncKeyBuf));

    // Get the encrypted token and IV from the active session entry.
    const msArr = web2Sessions.value.microsoft || [];
    const msEntry = Array.isArray(msArr) ? msArr[0] || {} : {};
    const msNonce = msEntry.nonce || "";
    const encryptedTokenMs = msEntry.encrypted_token || "";
    const tokenIvMs = msEntry.iv || "";

    onStep("Deriving pre-committed child key…");
    const privBytesMs = hex.toBytes(storedPrivMs);
    const ccBytesMs = hex.toBytes(storedCcMs);
    const childMs = deriveSecurePath(privBytesMs, ccBytesMs, sfMs);
    const childPubHexMs = getPublicKeyHex(childMs.priv);
    const gc1Ms = deriveSecurePath(childMs.priv, childMs.cc, sfMs);
    const gc2Ms = deriveSecurePath(gc1Ms.priv, gc1Ms.cc, sfMs);
    const agentPubHexMs = getPublicKeyHex(gc2Ms.priv);
    const operatorPubHexMs = getPublicKeyHex(privBytesMs);
    onStep(
      "Pre-committed key derived: " + childPubHexMs.slice(0, 20) + "…",
      "done",
    );

    const vcMs = {
      "@context": [
        "https://www.w3.org/ns/credentials/v2",
        "https://yadacoin.io/contexts/agent-auth/v1",
      ],
      type: ["VerifiableCredential", "AgentAuthorizationCredential"],
      issuer: `did:yadacoin:${operatorPubHexMs}`,
      validFrom: new Date().toISOString(),
      credentialStatus: { type: "YadaKELStatus", mode: "rotation" },
      credentialSubject: {
        id: `did:yadacoin:${agentPubHexMs}`,
        agentAuthorization: {
          type: "MicrosoftWriteAction",
          services: ["MicrosoftWriteAction"],
          ...scope,
        },
      },
    };
    const relB64Ms = btoa(unescape(encodeURIComponent(JSON.stringify(vcMs))));

    onStep("Broadcasting rotation transaction with scope committed on-chain…");
    let rotateDataMs;
    try {
      if (isClientWallet()) {
        const clientRot = await doClientRotation(
          privBytesMs,
          ccBytesMs,
          sfMs,
          relB64Ms,
        );
        rotateDataMs = {
          prev_private_key: clientRot.prevPrivHex,
          prev_chain_code: clientRot.prevCcHex,
          prerotated_private_key: hex.fromBytes(clientRot.provPrivBytes),
          transaction_id: clientRot.transactionId,
          status: true,
        };
      } else {
        const rotResMs = await fetch(
          getNodeUrl() + "/key-rotation/derived-child-key",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              public_key: childPubHexMs,
              second_factor: sfMs,
              signature: "",
              relationship: relB64Ms,
            }),
          },
        );
        rotateDataMs = await rotResMs.json();
        if (
          !rotResMs.ok ||
          !rotateDataMs.status ||
          !rotateDataMs.prerotated_private_key
        ) {
          throw new Error(rotateDataMs.message || String(rotResMs.status));
        }
      }
    } catch (e) {
      onStep("Rotation failed: " + e.message, "fail");
      onDone(false, "Rotation failed: " + escHtml(e.message));
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }

    await web2RekeyActiveSessions(
      storedPrivMs,
      rotateDataMs.prev_private_key,
      getNodeUrl(),
      isClientWallet(),
    );
    localStorage.setItem(LS_PRIV, rotateDataMs.prev_private_key);
    if (rotateDataMs.prev_chain_code)
      localStorage.setItem(LS_CC, rotateDataMs.prev_chain_code);
    emit("session-rotated", rotateDataMs.prev_private_key);
    onStep(
      "Rotation committed · txid " +
        rotateDataMs.transaction_id.slice(0, 20) +
        "…",
      "done",
    );

    onStep("Building Verifiable Presentation…");
    const provPrivBytesMs = hex.toBytes(rotateDataMs.prerotated_private_key);
    const provPubHexMs = getPublicKeyHex(provPrivBytesMs);

    function deepSortKeysMs(obj) {
      if (Array.isArray(obj)) return obj.map(deepSortKeysMs);
      if (obj !== null && typeof obj === "object") {
        const s = {};
        Object.keys(obj)
          .sort()
          .forEach((k) => (s[k] = deepSortKeysMs(obj[k])));
        return s;
      }
      return obj;
    }

    // Re-build VC with finalised agent key id (same as vcMs, already correct)
    const vpBaseMs = {
      "@context": ["https://www.w3.org/ns/credentials/v2"],
      type: ["VerifiablePresentation"],
      holder: `did:yadacoin:${provPubHexMs}`,
      verifiableCredential: [vcMs],
    };
    const vpCanonicalBytesMs = new TextEncoder().encode(
      JSON.stringify(deepSortKeysMs(vpBaseMs)),
    );

    onStep("Fetching challenge…");
    let chalDataMs;
    try {
      const chalResMs = await fetch(
        getNodeUrl() +
          `/ai-agent-auth/api/challenge?public_key=${encodeURIComponent(provPubHexMs)}`,
      );
      chalDataMs = await chalResMs.json();
      if (!chalResMs.ok || !chalDataMs.challenge)
        throw new Error("no challenge");
    } catch (e) {
      onStep("Challenge failed: " + e.message, "fail");
      onDone(false, "Challenge failed: " + escHtml(e.message));
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }

    const vpMs = await buildSignedVP(
      vpBaseMs,
      vpCanonicalBytesMs,
      provPrivBytesMs,
      provPubHexMs,
      chalDataMs.challenge,
    );

    onStep("Executing Microsoft action…");
    const llmCfgMs = getLlmSettings();
    try {
      const execRes = await fetch(
        getNodeUrl() + "/ai-agent-auth/api/microsoft/execute",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            public_key: provPubHexMs,
            challenge: chalDataMs.challenge,
            vp: vpMs,
            nonce: msNonce,
            token_enc_key: tokenEncKeyHexMs,
            encrypted_token: encryptedTokenMs,
            iv: tokenIvMs,
            action: scope.action,
            scope,
            llm: {
              provider: llmCfgMs.provider,
              model: llmCfgMs.model || undefined,
              api_key: llmCfgMs.api_key || undefined,
              ollama_host: llmCfgMs.ollama_host || undefined,
              base_url: llmCfgMs.base_url || undefined,
            },
          }),
        },
      );
      const execData = await execRes.json();
      if (!execRes.ok)
        throw new Error(execData.error || String(execRes.status));
      onStep("Action completed", "done");
      // Session is re-keyed — keep it active so the user can continue
      // using Microsoft without reconnecting after a write action.
      onDone(
        true,
        `✅ <strong>${escHtml(execData.reply || execData.message || "Done!")}</strong><br><br>` +
          `KEL authorization on-chain: <a href="${origin}/explorer?term=${rotateDataMs.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${rotateDataMs.transaction_id.slice(0, 24)}…</a>`,
      );
    } catch (e) {
      onStep("Execution failed: " + e.message, "fail");
      onDone(false, "Action failed: " + escHtml(e.message));
    }
    extractedScope = null;
    chatHistory = [];
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }

  const hwModeG = isHardwareWallet();
  const sf = secondFactor;

  let privBytes = null;
  let ccBytes = null;
  let child = null;
  let childPubHex = "";
  let agentPubHex = "";
  let operatorPubHex = "";
  if (hwModeG) {
    if (!hardware?.stored || !hardware?.confirming || !hardware?.nextActive) {
      onStep(
        "Hardware wallet rotation requires the stored active key plus both QR scans.",
        "fail",
      );
      onDone(
        false,
        "Hardware wallet rotation requires the stored active key plus both QR scans.",
      );
      busy.value = false;
      nextTick(() => inputEl.value?.focus());
      return;
    }
    operatorPubHex = hardware.stored.publicKeyHex;
    agentPubHex = hardware.nextActive.publicKeyHex;
    childPubHex = hardware.stored.publicKeyHex;
  } else {
    const storedPriv = localStorage.getItem(LS_PRIV);
    const storedCc = localStorage.getItem(LS_CC);

    onStep("Deriving pre-committed child key…");

    privBytes = hex.toBytes(storedPriv);
    ccBytes = hex.toBytes(storedCc);
    child = deriveSecurePath(privBytes, ccBytes, sf);
    childPubHex = getPublicKeyHex(child.priv);

    // Derive agent key (2 levels deeper) for the VC subject
    const gc1 = deriveSecurePath(child.priv, child.cc, sf);
    const gc2 = deriveSecurePath(gc1.priv, gc1.cc, sf);
    agentPubHex = getPublicKeyHex(gc2.priv);
    operatorPubHex = getPublicKeyHex(privBytes);
  }

  const services = scope.services || [];

  const vc = {
    "@context": [
      "https://www.w3.org/ns/credentials/v2",
      "https://yadacoin.io/contexts/agent-auth/v1",
    ],
    type: ["VerifiableCredential", "AgentAuthorizationCredential"],
    issuer: `did:yadacoin:${operatorPubHex}`,
    validFrom: new Date().toISOString(),
    credentialStatus: { type: "YadaKELStatus", mode: "rotation" },
    credentialSubject: {
      id: `did:yadacoin:${agentPubHex}`,
      agentAuthorization: {
        type: agentType?.authorizationType || "AgentAuthorization",
        ...scope,
        ...(paymentMethod
          ? {
              paymentMethod: {
                token: paymentMethod.token,
                label: paymentMethod.label,
              },
            }
          : {}),
      },
    },
  };

  const relationshipB64 = btoa(
    unescape(encodeURIComponent(JSON.stringify(vc))),
  );
  if (!hwModeG) {
    onStep(
      "Pre-committed key derived: " + childPubHex.slice(0, 20) + "…",
      "done",
    );
  }

  // Step 2: Broadcast rotation
  onStep("Broadcasting rotation transaction with scope committed on-chain…");
  let rotateData;
  try {
    if (hwModeG) {
      const hwRot = await doHardwareRotation(
        hardware.stored,
        hardware.confirming,
        hardware.nextActive,
        relationshipB64,
      );
      rotateData = {
        prev_private_key: null,
        prev_chain_code: null,
        prerotated_private_key: hex.fromBytes(hwRot.provPrivBytes),
        transaction_id: hwRot.transactionId,
        status: true,
      };
    } else if (isClientWallet()) {
      const clientRot = await doClientRotation(
        privBytes,
        ccBytes,
        sf,
        relationshipB64,
      );
      rotateData = {
        prev_private_key: clientRot.prevPrivHex,
        prev_chain_code: clientRot.prevCcHex,
        prerotated_private_key: hex.fromBytes(clientRot.provPrivBytes),
        transaction_id: clientRot.transactionId,
        status: true,
      };
    } else {
      const rotateRes = await fetch(
        getNodeUrl() + "/key-rotation/derived-child-key",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            public_key: childPubHex,
            second_factor: sf,
            signature: "",
            relationship: relationshipB64,
          }),
        },
      );
      rotateData = await rotateRes.json();
      if (
        !rotateRes.ok ||
        !rotateData.status ||
        !rotateData.prerotated_private_key
      ) {
        throw new Error(rotateData.message || String(rotateRes.status));
      }
    }
  } catch (e) {
    onStep("Rotation failed: " + e.message, "fail");
    onDone(false, "Rotation failed: " + e.message);
    // Re-present the approval card once the overlay finishes closing (onDone has a 600ms delay)
    const retryScope = { ...scope };
    const retryAgentType = agentType;
    setTimeout(() => {
      const scopeLines = Object.entries(retryScope)
        .map(([k, v]) => {
          const val = Array.isArray(v)
            ? v.map((s) => `<strong>${escHtml(s)}</strong>`).join(", ")
            : `<strong>${escHtml(String(v))}</strong>`;
          return `${escHtml(k.replace(/_/g, " "))}: ${val}`;
        })
        .join("<br>");
      const retryMsg = {
        role: "agent",
        html:
          `${scopeLines}<br><br>` +
          `To proceed I'll broadcast a rotation transaction committing this scope on-chain as a ` +
          `W3C Verifiable Credential. ` +
          (hwModeG
            ? `Please scan your hardware device's confirming and next-active QR codes to approve.`
            : `Please enter your second factor to approve.`),
        content: "",
        showApproval: true,
        approvalContext: { scope: retryScope, agentType: retryAgentType },
      };
      messages.value.push(retryMsg);
      messages.value[messages.value.length - 1] = { ...retryMsg };
    }, 700);
    busy.value = false;
    nextTick(() => inputEl.value?.focus());
    return;
  }
  onStep(
    "Scope committed · txid " + rotateData.transaction_id.slice(0, 20) + "…",
    "done",
  );

  // Update stored keys
  if (hwModeG) {
    // doHardwareRotation already persisted nextActive as the new stored
    // active key (via setHardwareActive). Mirror the public key for the
    // App.vue session pill.
    emit("session-rotated", hardware.nextActive.publicKeyHex);
  } else {
    localStorage.setItem(LS_PRIV, rotateData.prev_private_key);
    if (rotateData.prev_chain_code)
      localStorage.setItem(LS_CC, rotateData.prev_chain_code);
    emit("session-rotated", rotateData.prev_private_key);
  }

  // Step 3: Build VP
  onStep("Building Verifiable Presentation…");
  const provPrivBytes = hex.toBytes(rotateData.prerotated_private_key);
  const provPubHex = getPublicKeyHex(provPrivBytes);

  const vpBase = {
    "@context": ["https://www.w3.org/ns/credentials/v2"],
    type: ["VerifiablePresentation"],
    holder: `did:yadacoin:${provPubHex}`,
    verifiableCredential: [vc],
  };

  function deepSortKeys(obj) {
    if (Array.isArray(obj)) return obj.map(deepSortKeys);
    if (obj !== null && typeof obj === "object") {
      const s = {};
      Object.keys(obj)
        .sort()
        .forEach((k) => (s[k] = deepSortKeys(obj[k])));
      return s;
    }
    return obj;
  }

  const vpCanonical = JSON.stringify(deepSortKeys(vpBase));
  const vpCanonicalBytes = new TextEncoder().encode(vpCanonical);
  onStep(`VP built · holder did:yadacoin:${provPubHex.slice(0, 16)}…`, "done");

  // Shared vpData object passed to vendor chat helpers
  const vpData = { vpBase, vpCanonicalBytes, provPrivBytes, provPubHex };

  // Step 4: Per-vendor — start vendor chat (get first question / immediate confirm)
  const confirmedResults = [];
  const pendingVendors = [];
  const errorResults = [];
  const targetServices = services.length ? services : agentType?.services || [];

  for (const service of targetServices) {
    onStep(`[${service}] Initiating vendor conversation…`);
    try {
      // Build an initial greeting that summarises what was already collected
      // so the vendor doesn't re-ask for information the user already provided.
      const scopeSummary =
        scope && Object.keys(scope).length
          ? " The customer has already provided the following details: " +
            Object.entries(scope)
              .map(
                ([k, v]) =>
                  `${k.replace(/_/g, " ")}: ${Array.isArray(v) ? v.join(", ") : v}`,
              )
              .join("; ") +
            ". Please use this information and only ask for anything still missing."
          : "";
      const initGreeting = `Hello, I'm ready to finalize my booking.${scopeSummary}`;
      const initMessages = [{ role: "user", content: initGreeting }];
      const data = await callVendorChatApi(service, vpData, initMessages);
      if (data.complete) {
        onStep(`[${service}] Confirmed: ${data.confirmation}`, "done");
        if (data.credential) {
          saveBookingCredential(data.credential);
          postCredentialReceipt(data.credential).catch(() => {});
          emit("credential-issued");
        }
        confirmedResults.push({
          service,
          status: "ok",
          confirmation: data.confirmation,
          vendor: data.vendor,
        });
      } else {
        onStep(`[${service}] Vendor has follow-up questions`, "done");
        pendingVendors.push({
          service,
          vendorName: data.vendor,
          vendorMessages: [
            { role: "user", content: initGreeting },
            { role: "assistant", content: data.reply },
          ],
          choices: Array.isArray(data.choices) ? data.choices : [],
        });
      }
    } catch (e) {
      onStep(`[${service}] error: ${e.message}`, "fail");
      errorResults.push({ service, status: "error", message: String(e) });
    }
  }

  // Build summary of immediate confirmations + errors
  const allResults = [...confirmedResults, ...errorResults];
  const txSnippet = rotateData.transaction_id.slice(0, 24) + "…";

  if (pendingVendors.length > 0) {
    // Close the overlay with a partial summary; vendor chat continues in the main chat
    const confirmedLines = confirmedResults
      .map(
        (r) =>
          `✓ <strong>${escHtml(r.service)}</strong> (${escHtml(r.vendor)}): <code>${escHtml(r.confirmation)}</code>`,
      )
      .join("<br>");
    const errorLines = errorResults
      .map(
        (r) =>
          `✗ <strong>${escHtml(r.service)}</strong>: <span style="color:var(--red2)">${escHtml(r.message)}</span>`,
      )
      .join("<br>");
    const summaryHtml =
      (confirmedLines ? confirmedLines + "<br>" : "") +
      (errorLines ? errorLines : "");
    // Push summary directly so it lands in chat BEFORE the first vendor
    // question, which is pushed synchronously right after.  Then call onDone
    // with an empty string to just close the overlay (no duplicate message).
    if (summaryHtml.trim()) pushAgent(summaryHtml.trim(), true);
    // Push scope txid right here — after summary, before first vendor question
    const snip0 = rotateData.transaction_id.slice(0, 24) + "\u2026";
    pushAgent(
      `Scope on-chain: <a href="${origin}/explorer?term=${rotateData.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${snip0}</a>`,
      true,
    );
    onDone(true, ""); // close overlay only

    // Set vendor state — first pending service becomes current, rest go into queue
    const [first, ...rest] = pendingVendors;
    vendorState.value = {
      current: first,
      queue: rest,
      vpData,
      vendorMessages: first.vendorMessages,
    };

    // Post the first vendor question to the main chat
    await nextTick();
    const firstReply =
      first.vendorMessages[first.vendorMessages.length - 1].content;
    const firstMsg = pushAgent(
      `<strong>${escHtml(first.vendorName)}:</strong><br>${marked.parse(firstReply)}`,
      true,
    );
    applyDataFields(firstMsg, first);
  } else {
    // All services resolved immediately — classic done flow
    const resultLines = allResults
      .map((r) =>
        r.status === "ok"
          ? `✓ <strong>${escHtml(r.service)}</strong> (${escHtml(r.vendor)}): <code>${escHtml(r.confirmation)}</code>`
          : `✗ <strong>${escHtml(r.service)}</strong>: <span style="color:var(--red2)">${escHtml(r.message)}</span>`,
      )
      .join("<br>");
    const anyOk = confirmedResults.length > 0;
    const allOk = errorResults.length === 0 && confirmedResults.length > 0;
    if (allOk) {
      onDone(
        true,
        `✅ <strong>All services booked!</strong><br><br>${resultLines}<br><br>Scope on-chain: <a href="${origin}/explorer?term=${rotateData.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${txSnippet}</a>`,
      );
    } else if (anyOk) {
      onDone(
        true,
        `⚠️ <strong>Partial success</strong><br><br>${resultLines}<br><br>Scope on-chain: <a href="${origin}/explorer?term=${rotateData.transaction_id}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);font-family:monospace;font-size:0.85em">${txSnippet}</a>`,
      );
    } else {
      onDone(
        false,
        `❌ <strong>All bookings failed</strong><br><br>${resultLines}`,
      );
    }
  }

  extractedScope = null;
  chatHistory = [];
  busy.value = false;
  nextTick(() => inputEl.value?.focus());
}

/**
 * Called by the parent after wallet setup completes so the chat reactivates
 * without requiring a full page reload.
 */
function notifyWalletReady() {
  sessionTick.value++; // forces sessionReady to re-evaluate
  // Replace any "no wallet" warning messages with the normal greeting
  messages.value = messages.value.filter(
    (m) =>
      !m.html?.includes("No wallet found") &&
      !m.html?.includes("No operator key found") &&
      !m.content?.includes("No wallet found") &&
      !m.content?.includes("No operator key found") &&
      !m.content?.includes("To get started, set up"),
  );
  pushAgent(
    "Wallet ready! I'm your YadaCoin AI agent. How can I help you today?",
  );
  nextTick(() => inputEl.value?.focus());
}

defineExpose({
  runApprovalFlow,
  messages,
  busy,
  notifyWalletReady,
  handleAuthConnect,
});
</script>

<style scoped>
.chat-pane {
  display: flex;
  flex-direction: column;
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
}
.input-area {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 16px 12px;
  border-top: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
}
.input-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.input-area textarea {
  flex: 1 1 0;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-family: inherit;
  font-size: 0.88rem;
  line-height: 1.5;
  padding: 9px 12px;
  resize: none;
  overflow-y: auto;
  scrollbar-width: thin;
  transition: border-color 0.15s;
}
.input-area textarea:focus {
  outline: none;
  border-color: var(--accent);
}
.input-area textarea:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.send-btn {
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: 8px;
  width: 36px;
  height: 36px;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
  flex-shrink: 0;
}
.send-btn:hover:not(:disabled) {
  background: var(--accent2);
}
.send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>

<!-- Wallet data card styles — injected into ChatWindow's v-html output -->
<style>
.wallet-data-card {
  background: #0d1117;
  border: 1px solid #1e3a5f;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 0.82rem;
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}
.wdc-title {
  font-weight: 700;
  color: #58a6ff;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 1px solid #1e3a5f;
  padding-bottom: 6px;
  margin-bottom: 2px;
}
.wdc-address {
  color: #8b949e;
  font-size: 0.76rem;
  word-break: break-all;
}
.wdc-balance {
  font-size: 1.1rem;
  font-weight: 700;
  color: #3fb950;
}
.wdc-amount {
  font-size: 1.3rem;
}
.wdc-txrow {
  display: grid;
  grid-template-columns: 1.2rem 6rem 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px solid #1a1e28;
  font-size: 0.78rem;
}
.wdc-txrow:last-child {
  border-bottom: none;
}
.wdc-dir {
  font-weight: 700;
  font-size: 0.9rem;
}
.wdc-sent .wdc-dir {
  color: #f85149;
}
.wdc-recv .wdc-dir {
  color: #3fb950;
}
.wdc-amt {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.wdc-sent .wdc-amt {
  color: #f85149;
}
.wdc-recv .wdc-amt {
  color: #3fb950;
}
.wdc-to {
  color: #8b949e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wdc-ts {
  color: #6e7681;
  font-size: 0.72rem;
  white-space: nowrap;
}
.wdc-pending {
  color: #d29922;
  font-style: italic;
}
.wdc-empty {
  color: #6e7681;
  font-style: italic;
}

/* GitHub data cards — injected via renderGithubData() v-html output */
.gh-card {
  background: rgba(22, 27, 34, 0.9);
  border: 1px solid #30363d;
  border-radius: 10px;
  padding: 12px 14px;
  margin-top: 6px;
  font-size: 0.84rem;
}
.gh-title {
  font-weight: 700;
  font-size: 0.9rem;
  margin-bottom: 10px;
  color: #e6edf3;
}
.gh-title a {
  color: #58a6ff;
  text-decoration: none;
}
.gh-title a:hover {
  text-decoration: underline;
}
.gh-row {
  padding: 7px 0;
  border-bottom: 1px solid #21262d;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
}
.gh-row:last-child {
  border-bottom: none;
}
.gh-name {
  font-weight: 600;
  color: #58a6ff;
  text-decoration: none;
  flex: 1 1 180px;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.gh-name:hover {
  text-decoration: underline;
}
.gh-num {
  color: #8b949e;
  font-size: 0.8rem;
  flex-shrink: 0;
}
.gh-desc {
  color: #8b949e;
  font-size: 0.78rem;
  width: 100%;
  margin-top: 2px;
}
.gh-meta {
  color: #8b949e;
  font-size: 0.75rem;
  white-space: nowrap;
}
.gh-badge {
  font-size: 0.68rem;
  border-radius: 4px;
  padding: 1px 6px;
  font-weight: 600;
  white-space: nowrap;
}
.gh-public {
  background: rgba(63, 185, 80, 0.15);
  color: #3fb950;
  border: 1px solid rgba(63, 185, 80, 0.3);
}
.gh-private {
  background: rgba(248, 81, 73, 0.12);
  color: #f85149;
  border: 1px solid rgba(248, 81, 73, 0.3);
}
.gh-lang {
  background: rgba(99, 179, 237, 0.12);
  color: #79c0ff;
  border: 1px solid rgba(99, 179, 237, 0.25);
}
.gh-draft {
  background: rgba(188, 140, 82, 0.15);
  color: #d29922;
  border: 1px solid rgba(188, 140, 82, 0.3);
}
.gh-topics {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 6px;
}
.gh-chip {
  font-size: 0.68rem;
  background: rgba(56, 139, 253, 0.1);
  color: #388bfd;
  border: 1px solid rgba(56, 139, 253, 0.25);
  border-radius: 4px;
  padding: 1px 7px;
}
.gh-empty {
  color: #8b949e;
  font-style: italic;
}
.gh-unread-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #58a6ff;
  flex-shrink: 0;
  margin-right: 2px;
}

/* Microsoft data cards — injected via renderMicrosoftData() */
.ms-card {
  background: rgba(0, 120, 212, 0.06);
  border: 1px solid rgba(0, 120, 212, 0.25);
  border-radius: 10px;
  padding: 12px 14px;
  margin-top: 6px;
  font-size: 0.84rem;
}
.ms-title {
  font-weight: 700;
  font-size: 0.9rem;
  margin-bottom: 10px;
  color: #e6edf3;
}
.ms-row {
  padding: 8px 0;
  border-bottom: 1px solid rgba(0, 120, 212, 0.12);
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.ms-row:last-child {
  border-bottom: none;
}
.ms-unread .ms-subject {
  font-weight: 700;
  color: #e6edf3;
}
.ms-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #0078d4;
  flex-shrink: 0;
  margin-top: 5px;
}
.ms-dot-placeholder {
  display: inline-block;
  width: 8px;
  flex-shrink: 0;
}
.ms-row-main {
  flex: 1;
  min-width: 0;
}
.ms-row-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: baseline;
}
.ms-from {
  font-weight: 600;
  color: #cdd9e5;
  font-size: 0.82rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.ms-subject {
  color: #cdd9e5;
  font-size: 0.82rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ms-date {
  color: #8b949e;
  font-size: 0.73rem;
  white-space: nowrap;
  flex-shrink: 0;
}
.ms-preview {
  color: #8b949e;
  font-size: 0.76rem;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ms-meta {
  color: #8b949e;
  font-size: 0.76rem;
  margin-top: 3px;
}
.ms-body {
  color: #cdd9e5;
  font-size: 0.8rem;
  margin-top: 8px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow-y: auto;
}
.ms-badge {
  font-size: 0.68rem;
  border-radius: 4px;
  padding: 1px 6px;
  font-weight: 600;
  white-space: nowrap;
}
.ms-online {
  background: rgba(0, 120, 212, 0.15);
  color: #60a5fa;
  border: 1px solid rgba(0, 120, 212, 0.3);
}
.ms-empty {
  color: #8b949e;
  font-style: italic;
}

/* ── Help button ───────────────────────────────────────────────────────────── */
.help-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-muted, #8b949e);
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    background 0.15s,
    color 0.15s;
}
.help-btn:hover {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

/* ── Docs modal ────────────────────────────────────────────────────────────── */
.docs-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.docs-modal {
  background: var(--surface, #161b22);
  border: 1px solid var(--border, #30363d);
  border-radius: 12px;
  width: min(700px, 96vw);
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
}
.docs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 14px;
  border-bottom: 1px solid var(--border, #30363d);
  flex-shrink: 0;
}
.docs-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text, #e6edf3);
}
.docs-close {
  background: none;
  border: none;
  color: var(--text-muted, #8b949e);
  font-size: 1rem;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.docs-close:hover {
  background: var(--border, #30363d);
  color: var(--text, #e6edf3);
}
.docs-body {
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 0.87rem;
  color: var(--text, #e6edf3);
  line-height: 1.6;
}

/* ── Accordion ─────────────────────────────────────────────────────────────── */
.docs-accordion {
  border: 1px solid var(--border, #30363d);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg, #0d1117);
}
.docs-acc-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 16px;
  background: var(--surface, #161b22);
  border: none;
  color: var(--text, #e6edf3);
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s;
}
.docs-acc-header:hover {
  background: var(--border, #30363d);
}
.docs-acc-chevron {
  font-size: 1.1rem;
  transition: transform 0.2s;
  display: inline-block;
}
.docs-acc-chevron.open {
  transform: rotate(90deg);
}
.docs-acc-body {
  padding: 14px 18px 16px;
  border-top: 1px solid var(--border, #30363d);
}
.docs-acc-body h3 {
  margin: 12px 0 5px;
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent, #58a6ff);
}
.docs-acc-body p {
  margin: 0 0 6px;
  color: #8b949e;
}
.docs-acc-body ol,
.docs-acc-body ul {
  margin: 0 0 6px;
  padding-left: 20px;
  color: #8b949e;
}
.docs-acc-body li {
  margin-bottom: 4px;
}
.docs-acc-body code {
  background: rgba(88, 166, 255, 0.1);
  border: 1px solid rgba(88, 166, 255, 0.2);
  border-radius: 3px;
  padding: 1px 5px;
  font-family: monospace;
  font-size: 0.82rem;
  color: #79c0ff;
}
.docs-acc-body strong {
  color: var(--text, #e6edf3);
}

/* ── Agent Loop inline result ──────────────────────────────────────────────── */
.loop-result {
  font-size: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.loop-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #8b949e;
  font-style: italic;
}
.loop-spinner {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent, #58a6ff);
  animation: lp-pulse 1s ease-in-out infinite;
}
@keyframes lp-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.2;
  }
}
.loop-plan {
  border: 1px solid var(--border, #30363d);
  border-radius: 8px;
  overflow: hidden;
}
.loop-plan-reasoning {
  padding: 8px 12px;
  font-size: 0.82rem;
  color: #8b949e;
  background: var(--bg, #0d1117);
  border-bottom: 1px solid var(--border, #30363d);
}
.loop-steps {
  list-style: none;
  margin: 0;
  padding: 0;
}
.loop-step {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  padding: 7px 12px;
  border-bottom: 1px solid var(--border, #30363d);
  font-size: 0.82rem;
  color: #8b949e;
}
.loop-step:last-child {
  border-bottom: none;
}
.loop-step.lp-done {
  color: var(--text, #e6edf3);
}
.loop-step.lp-active {
  color: var(--accent, #58a6ff);
}
.ls-num {
  width: 20px;
  text-align: center;
  font-weight: 700;
  flex-shrink: 0;
}
.ls-desc {
  flex: 1 1 0;
}
.ls-badge {
  font-size: 0.72rem;
  background: rgba(88, 166, 255, 0.08);
  border: 1px solid rgba(88, 166, 255, 0.18);
  border-radius: 4px;
  padding: 1px 5px;
  color: #79c0ff;
  white-space: nowrap;
}
.ls-result {
  width: 100%;
  font-size: 0.78rem;
  color: #8b949e;
  background: var(--bg, #0d1117);
  border-radius: 4px;
  padding: 5px 8px;
  white-space: pre-wrap;
  word-break: break-word;
  margin-top: 2px;
}
.loop-final {
  border: 1px solid rgba(63, 185, 80, 0.25);
  border-radius: 8px;
  overflow: hidden;
}
.loop-final-title {
  background: rgba(63, 185, 80, 0.08);
  padding: 5px 12px;
  font-size: 0.78rem;
  font-weight: 600;
  color: #3fb950;
  border-bottom: 1px solid rgba(63, 185, 80, 0.2);
}
.loop-final-body {
  padding: 10px 12px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text, #e6edf3);
  line-height: 1.6;
}
.loop-error {
  color: #f85149;
  font-size: 0.83rem;
  padding: 6px 10px;
  background: rgba(248, 81, 73, 0.08);
  border: 1px solid rgba(248, 81, 73, 0.2);
  border-radius: 6px;
}
.loop-warning {
  color: #e3b341;
  font-size: 0.83rem;
  padding: 6px 10px;
  margin-bottom: 6px;
  background: rgba(227, 179, 65, 0.08);
  border: 1px solid rgba(227, 179, 65, 0.25);
  border-radius: 6px;
}
</style>
