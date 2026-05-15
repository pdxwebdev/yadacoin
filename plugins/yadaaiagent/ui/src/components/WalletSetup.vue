<template>
  <div class="wallet-setup-overlay" @click.self="close">
    <div class="wallet-setup-modal">
      <div class="ws-header">
        <h2>Wallet Setup</h2>
        <p class="ws-subtitle">
          Choose a setup method and follow the guided walkthrough.
        </p>
      </div>

      <!-- Tab selector + content (sidebar layout) -->
      <div class="ws-layout">
        <div class="ws-tabs">
          <button
            :class="['ws-tab', tab === 'generate' ? 'active' : '']"
            @click="switchTab('generate')"
          >
            Generate New Wallet
          </button>
          <button
            :class="['ws-tab', tab === 'import' ? 'active' : '']"
            @click="switchTab('import')"
          >
            Import Existing Seed
          </button>
          <button
            :class="['ws-tab', tab === 'admin' ? 'active' : '']"
            @click="switchTab('admin')"
          >
            Node Admin Wallet
          </button>
          <button
            :class="['ws-tab', tab === 'hardware' ? 'active' : '']"
            @click="switchTab('hardware')"
          >
            Hardware Wallet
          </button>
          <button
            :class="['ws-tab', tab === 'recover_loc' ? 'active' : '']"
            @click="switchTab('recover_loc')"
          >
            Recover via Locations
          </button>
        </div>

        <div class="ws-content">
          <!-- Step progress dots -->
          <div class="ws-progress">
            <div
              v-for="(_, i) in tabSteps[tab]"
              :key="i"
              :class="[
                'ws-dot',
                i < step ? 'done' : i === step ? 'active' : '',
              ]"
            ></div>
          </div>
          <div class="ws-step-label">
            Step {{ step + 1 }} of {{ tabSteps[tab].length }} —
            {{ tabSteps[tab][step] }}
          </div>

          <!-- ═══════════════════════════════════════════════════════════════════ -->
          <!-- GENERATE TAB                                                        -->
          <!-- ═══════════════════════════════════════════════════════════════════ -->
          <div v-if="tab === 'generate'" class="ws-body">
            <!-- Step 0: Overview -->
            <div v-if="step === 0" class="ws-walkthrough">
              <div class="wt-section wt-highlight">
                <div class="wt-icon">🔑</div>
                <div>
                  <h3>What is a Client-Side Wallet?</h3>
                  <p>
                    This option creates a new wallet
                    <strong>entirely in your browser</strong>. Your seed phrase
                    and keys never leave your device — the node only receives
                    your public key and an on-chain inception transaction.
                  </p>
                </div>
              </div>
              <div class="wt-steps-list">
                <div class="wt-step-item">
                  <span class="wt-num">1</span>
                  <div>
                    <strong>Generate a seed phrase</strong>
                    <p>
                      A random 12-word BIP39 phrase is created locally. It is
                      the master backup for your wallet.
                    </p>
                  </div>
                </div>
                <div class="wt-step-item">
                  <span class="wt-num">2</span>
                  <div>
                    <strong>Back it up</strong>
                    <p>
                      Write the 12 words on paper in order. Anyone with these
                      words can reconstruct your wallet — protect them offline.
                    </p>
                  </div>
                </div>
                <div class="wt-step-item">
                  <span class="wt-num">3</span>
                  <div>
                    <strong>Set a second factor</strong>
                    <p>
                      A password combined with your seed phrase strengthens each
                      key derivation. You'll need both to recover or rotate
                      keys.
                    </p>
                  </div>
                </div>
                <div class="wt-step-item">
                  <span class="wt-num">4</span>
                  <div>
                    <strong>Register on-chain</strong>
                    <p>
                      An inception transaction is submitted to the YadaCoin
                      node, anchoring your key event log to the blockchain.
                    </p>
                  </div>
                </div>
              </div>
              <div class="ws-btn-row">
                <button class="ws-btn primary" @click="step = 1">
                  Get Started →
                </button>
              </div>
            </div>

            <!-- Step 1: Generate seed phrase -->
            <div v-else-if="step === 1" class="ws-walkthrough">
              <div class="wt-callout">
                <strong>Generate your seed phrase</strong>
                <p>
                  Click the button below to create 12 random words. These words
                  are generated locally and never sent anywhere.
                </p>
              </div>
              <div v-if="!mnemonicWords.length">
                <button class="ws-btn primary" @click="doGenerate">
                  Generate Seed Phrase
                </button>
              </div>
              <div v-else>
                <div class="ws-warn">
                  ⚠️ These 12 words ARE your wallet. Write them down now before
                  continuing.
                </div>
                <div class="mnemonic-grid">
                  <div
                    v-for="(word, i) in mnemonicWords"
                    :key="i"
                    class="mnemonic-word"
                  >
                    <span class="word-num">{{ i + 1 }}</span>
                    <span class="word-val">{{ word }}</span>
                  </div>
                </div>
                <div class="ws-btn-row" style="margin-top: 8px">
                  <button class="ws-btn secondary" @click="copyMnemonic">
                    {{ mnemonicCopied ? "✓ Copied!" : "Copy" }}
                  </button>
                  <button class="ws-btn secondary" @click="downloadMnemonic">
                    ⬇ Download
                  </button>
                </div>
                <div class="ws-btn-row">
                  <button class="ws-btn secondary" @click="doGenerate">
                    Regenerate
                  </button>
                  <button class="ws-btn primary" @click="step = 2">
                    I've stored these securely →
                  </button>
                </div>
              </div>
            </div>

            <!-- Step 2: Backup confirmation -->
            <div v-else-if="step === 2" class="ws-walkthrough">
              <div class="wt-callout wt-callout-warn">
                <strong>Confirm your backup</strong>
                <p>
                  Before proceeding, verify you have your seed phrase safely
                  recorded offline. There is no "forgot my seed phrase" option.
                </p>
              </div>
              <div class="wt-checklist">
                <label class="wt-check">
                  <input type="checkbox" v-model="backupChecks[0]" />
                  <span
                    >I have written down all 12 words in the correct
                    order.</span
                  >
                </label>
                <label class="wt-check">
                  <input type="checkbox" v-model="backupChecks[1]" />
                  <span
                    >I understand that losing these words means losing access to
                    my wallet permanently.</span
                  >
                </label>
                <label class="wt-check">
                  <input type="checkbox" v-model="backupChecks[2]" />
                  <span
                    >I will store my backup offline, away from digital
                    devices.</span
                  >
                </label>
              </div>
              <div class="ws-btn-row">
                <button class="ws-btn secondary" @click="step = 1">
                  ← Back
                </button>
                <button
                  class="ws-btn primary"
                  :disabled="!allBackupChecked"
                  @click="step = 3"
                >
                  Continue →
                </button>
              </div>
            </div>

            <!-- Step 3: Set second factor -->
            <div v-else-if="step === 3" class="ws-walkthrough">
              <div class="wt-callout">
                <strong>Set your second factor (password)</strong>
                <p>
                  This password is combined with your seed phrase during key
                  derivation. It protects your wallet even if your seed phrase
                  is exposed. Store it alongside your seed phrase — you'll need
                  it for every key rotation.
                </p>
              </div>
              <div class="ws-field">
                <label>Second Factor Password</label>
                <input
                  v-model="secondFactor"
                  type="password"
                  placeholder="Choose a strong password"
                  autocomplete="new-password"
                />
              </div>
              <div class="ws-field">
                <label>Confirm Password</label>
                <input
                  v-model="secondFactorConfirm"
                  type="password"
                  placeholder="Re-enter password"
                  autocomplete="new-password"
                  @keydown.enter="doSetup"
                />
              </div>
              <div v-if="error" class="ws-error">{{ error }}</div>
              <div class="ws-btn-row">
                <button class="ws-btn secondary" @click="step = 2">
                  ← Back
                </button>
                <button
                  class="ws-btn primary"
                  :disabled="busy || !secondFactor || !secondFactorConfirm"
                  @click="doSetup"
                >
                  {{ busy ? "Setting up…" : "Set Up Wallet" }}
                </button>
              </div>
            </div>

            <!-- Step 4: Location Backup (optional) -->
            <div v-else-if="step === 4" class="ws-walkthrough">
              <div class="wt-section wt-highlight">
                <div class="wt-icon">📍</div>
                <div>
                  <h3>Optional: Back up with three locations</h3>
                  <p>
                    Encrypt your seed phrase with a zero-knowledge key derived
                    from three private locations. You'll get a short Recovery
                    Code that lets you restore the wallet on any device by
                    re-pinning the same locations on a map. Coordinates never
                    leave this device.
                  </p>
                </div>
              </div>
              <LocationRecoverySetup
                v-if="!locationSetupResult"
                :existing-mnemonic="generatedMnemonicPhrase"
                :prev-key-hash="null"
                :second-factor="secondFactor"
                @setup-complete="onLocationSetupComplete"
                @skip="step = 5"
              />
              <div v-else class="wt-section wt-highlight wt-highlight-green">
                <div class="wt-icon">✅</div>
                <div>
                  <h3>Location backup saved</h3>
                  <p>
                    Recovery Code:
                    <code class="wt-result-val wt-result-highlight">{{
                      locationSetupResult.code
                    }}</code>
                  </p>
                  <p>
                    Store this code somewhere safe — together with your three
                    locations it can recover this wallet on a fresh device.
                  </p>
                </div>
              </div>
              <div v-if="locationSetupResult" class="ws-btn-row">
                <button class="ws-btn primary" @click="step = 5">
                  Next: Configure AI →
                </button>
              </div>
            </div>

            <!-- Step 5: Configure AI -->
            <div v-else-if="step === 5" class="ws-walkthrough">
              <div class="wt-section wt-highlight wt-highlight-green">
                <div class="wt-icon">✅</div>
                <div>
                  <h3>Wallet ready — configure your AI provider</h3>
                  <p>
                    Set your LLM provider and model below before continuing.
                    Without this the chat will fail.
                  </p>
                </div>
              </div>
              <div class="llm-form" @submit.prevent>
                <div class="ws-field">
                  <label>Provider</label>
                  <select
                    v-model="llmForm.provider"
                    @change="llmForm.model = ''"
                  >
                    <option value="ollama">Ollama (local, free)</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="github_models">
                      GitHub Models (free tier)
                    </option>
                    <option value="openai_compat">
                      OpenAI-compatible (custom)
                    </option>
                  </select>
                </div>
                <div v-if="llmForm.provider === 'ollama'" class="ws-field">
                  <label>Ollama Host</label>
                  <input
                    v-model="llmForm.ollama_host"
                    type="text"
                    placeholder="http://localhost:11434"
                  />
                  <div class="ws-hint">
                    Run <code>ollama list</code> to see available models.
                    Default host is <code>http://localhost:11434</code>.
                  </div>
                </div>
                <div
                  v-if="llmForm.provider === 'openai_compat'"
                  class="ws-field"
                >
                  <label>Base URL</label>
                  <input
                    v-model="llmForm.base_url"
                    type="text"
                    placeholder="https://api.example.com/v1"
                  />
                </div>
                <div class="ws-field">
                  <label>Model</label>
                  <input
                    v-model="llmForm.model"
                    type="text"
                    :placeholder="llmModelPlaceholder"
                  />
                  <div class="ws-hint" v-html="llmModelHint"></div>
                </div>
                <div v-if="llmForm.provider !== 'ollama'" class="ws-field">
                  <label>API Key</label>
                  <input
                    v-model="llmForm.api_key"
                    type="password"
                    :placeholder="
                      llmForm.provider === 'github_models'
                        ? 'GitHub PAT (github_pat_…)'
                        : 'sk-…'
                    "
                    autocomplete="off"
                  />
                  <div class="ws-hint">
                    Stored in localStorage only — never sent to the YadaCoin
                    server.
                  </div>
                </div>
              </div>
              <div class="wt-callout wt-callout-warn" style="margin-top: 4px">
                <strong>⚠️ Payment Methods — Demo Only</strong>
                <p>
                  The payment methods section in Settings is for
                  <strong>demonstration purposes only</strong>. No real payment
                  processing occurs.
                  <strong
                    >Do not enter real card numbers or financial data.</strong
                  >
                  Use placeholders like <code>Visa ending in 4242</code>.
                </p>
              </div>
              <div class="ws-btn-row">
                <button
                  class="ws-btn primary"
                  :disabled="!llmFormValid"
                  @click="saveLlmAndFinish"
                >
                  Finish &amp; Start Chatting
                </button>
              </div>
            </div>
          </div>

          <!-- ═══════════════════════════════════════════════════════════════════ -->
          <!-- IMPORT TAB                                                           -->
          <!-- ═══════════════════════════════════════════════════════════════════ -->
          <div v-else-if="tab === 'import'" class="ws-body">
            <!-- Step 0: Overview -->
            <div v-if="step === 0" class="ws-walkthrough">
              <div class="wt-section wt-highlight">
                <div class="wt-icon">📥</div>
                <div>
                  <h3>Importing an Existing Wallet</h3>
                  <p>
                    Use this if you already have a YadaCoin seed phrase from a
                    previous setup. Your existing key event log will be detected
                    and reused — no duplicate inception transaction is
                    submitted.
                  </p>
                </div>
              </div>
              <div class="wt-steps-list">
                <div class="wt-step-item">
                  <span class="wt-num">1</span>
                  <div>
                    <strong>Enter your seed phrase</strong>
                    <p>
                      Type or paste all 12 (or 24) words separated by spaces.
                      Spelling must match the original BIP39 wordlist exactly.
                    </p>
                  </div>
                </div>
                <div class="wt-step-item">
                  <span class="wt-num">2</span>
                  <div>
                    <strong>Enter your second factor</strong>
                    <p>
                      Provide the same password you used when the wallet was
                      originally created. If forgotten, you cannot re-derive the
                      correct keys.
                    </p>
                  </div>
                </div>
                <div class="wt-step-item">
                  <span class="wt-num">3</span>
                  <div>
                    <strong>Keys restored, KEL checked</strong>
                    <p>
                      The app re-derives your key material locally, then checks
                      the node for an existing key event log. If found, import
                      completes without a new transaction.
                    </p>
                  </div>
                </div>
              </div>
              <div class="ws-btn-row">
                <button class="ws-btn primary" @click="step = 1">
                  Get Started →
                </button>
              </div>
            </div>

            <!-- Step 1: Enter seed phrase -->
            <div v-else-if="step === 1" class="ws-walkthrough">
              <div class="wt-callout">
                <strong>Enter your 12 or 24-word seed phrase</strong>
                <p>
                  Type each word separated by a single space. Avoid copy-pasting
                  from untrusted sources.
                </p>
              </div>
              <div class="ws-field">
                <label>Seed Phrase</label>
                <textarea
                  v-model="importPhrase"
                  placeholder="word1 word2 word3 … word12"
                  rows="3"
                  autocomplete="off"
                  spellcheck="false"
                ></textarea>
                <div
                  v-if="importPhrase.trim() && !phraseValid"
                  class="ws-error"
                >
                  Invalid seed phrase — check spelling and word count (must be
                  12 or 24 words).
                </div>
                <div v-if="phraseValid" class="ws-ok">✓ Valid seed phrase</div>
              </div>
              <div class="ws-btn-row">
                <button class="ws-btn secondary" @click="step = 0">
                  ← Back
                </button>
                <button
                  class="ws-btn primary"
                  :disabled="!phraseValid"
                  @click="step = 2"
                >
                  Continue →
                </button>
              </div>
            </div>

            <!-- Step 2: Enter second factor -->
            <div v-else-if="step === 2" class="ws-walkthrough">
              <div class="wt-callout">
                <strong>Enter your second factor password</strong>
                <p>
                  This must be the exact same password used when the wallet was
                  first created. A wrong password will derive different keys
                  silently — your addresses will not match.
                </p>
              </div>
              <div class="ws-field">
                <label>Second Factor Password</label>
                <input
                  v-model="secondFactor"
                  type="password"
                  placeholder="Password from original setup"
                  autocomplete="current-password"
                  @keydown.enter="doSetup"
                />
              </div>
              <div v-if="error" class="ws-error">{{ error }}</div>
              <div class="ws-btn-row">
                <button class="ws-btn secondary" @click="step = 1">
                  ← Back
                </button>
                <button
                  class="ws-btn primary"
                  :disabled="busy || !secondFactor"
                  @click="doSetup"
                >
                  {{ busy ? "Importing…" : "Import Wallet" }}
                </button>
              </div>
            </div>

            <!-- Step 3: Configure AI -->
            <div v-else-if="step === 3" class="ws-walkthrough">
              <div class="wt-section wt-highlight wt-highlight-green">
                <div class="wt-icon">✅</div>
                <div>
                  <h3>Wallet restored — configure your AI provider</h3>
                  <p>
                    Set your LLM provider and model below before continuing.
                    Without this the chat will fail.
                  </p>
                </div>
              </div>
              <div class="llm-form" @submit.prevent>
                <div class="ws-field">
                  <label>Provider</label>
                  <select
                    v-model="llmForm.provider"
                    @change="llmForm.model = ''"
                  >
                    <option value="ollama">Ollama (local, free)</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="github_models">
                      GitHub Models (free tier)
                    </option>
                    <option value="openai_compat">
                      OpenAI-compatible (custom)
                    </option>
                  </select>
                </div>
                <div v-if="llmForm.provider === 'ollama'" class="ws-field">
                  <label>Ollama Host</label>
                  <input
                    v-model="llmForm.ollama_host"
                    type="text"
                    placeholder="http://localhost:11434"
                  />
                  <div class="ws-hint">
                    Run <code>ollama list</code> to see available models.
                  </div>
                </div>
                <div
                  v-if="llmForm.provider === 'openai_compat'"
                  class="ws-field"
                >
                  <label>Base URL</label>
                  <input
                    v-model="llmForm.base_url"
                    type="text"
                    placeholder="https://api.example.com/v1"
                  />
                </div>
                <div class="ws-field">
                  <label>Model</label>
                  <input
                    v-model="llmForm.model"
                    type="text"
                    :placeholder="llmModelPlaceholder"
                  />
                  <div class="ws-hint" v-html="llmModelHint"></div>
                </div>
                <div v-if="llmForm.provider !== 'ollama'" class="ws-field">
                  <label>API Key</label>
                  <input
                    v-model="llmForm.api_key"
                    type="password"
                    :placeholder="
                      llmForm.provider === 'github_models'
                        ? 'GitHub PAT (github_pat_…)'
                        : 'sk-…'
                    "
                    autocomplete="off"
                  />
                  <div class="ws-hint">
                    Stored in localStorage only — never sent to the YadaCoin
                    server.
                  </div>
                </div>
              </div>
              <div class="wt-callout wt-callout-warn" style="margin-top: 4px">
                <strong>⚠️ Payment Methods — Demo Only</strong>
                <p>
                  The payment methods section in Settings is for
                  <strong>demonstration purposes only</strong>. No real payment
                  processing occurs.
                  <strong
                    >Do not enter real card numbers or financial data.</strong
                  >
                  Use placeholders like <code>Visa ending in 4242</code>.
                </p>
              </div>
              <div class="ws-btn-row">
                <button
                  class="ws-btn primary"
                  :disabled="!llmFormValid"
                  @click="saveLlmAndFinish"
                >
                  Finish &amp; Start Chatting
                </button>
              </div>
            </div>
          </div>

          <!-- ═══════════════════════════════════════════════════════════════════ -->
          <!-- NODE ADMIN WALLET TAB                                                 -->
          <!-- ═══════════════════════════════════════════════════════════════════ -->
          <div v-else-if="tab === 'admin'" class="ws-body">
            <!-- Step 0: Overview + prerequisites -->
            <div v-if="step === 0" class="ws-walkthrough">
              <div class="wt-auth-warning">
                <span class="wt-auth-warning-icon">🔒</span>
                <div>
                  <strong>Authorized Node Operators Only</strong>
                  <p>
                    This section is restricted to the person who operates this
                    YadaCoin node. It requires the node's private key and
                    directly modifies server-side configuration. Do not proceed
                    unless you are the node operator.
                  </p>
                </div>
              </div>

              <div class="wt-section wt-highlight wt-highlight-amber">
                <div class="wt-icon">🖥️</div>
                <div>
                  <h3>Node Admin Wallet (admin_kel)</h3>
                  <p>
                    This initializes the node's
                    <strong>server-managed key event log</strong>. Key material
                    is derived and stored on the server — not in your browser.
                    This is used for automated signing by the node process
                    itself.
                  </p>
                </div>
              </div>

              <div class="wt-section">
                <h4>Prerequisites</h4>
                <div class="wt-prereq-list">
                  <div class="wt-prereq">
                    <span class="wt-prereq-icon">📄</span>
                    <div>
                      <strong>seed in config.json</strong>
                      <p>
                        The node must have a BIP39 <code>seed</code> field set
                        in its <code>config.json</code>. This is the mnemonic
                        the server uses for key derivation.
                      </p>
                    </div>
                  </div>
                  <div class="wt-prereq">
                    <span class="wt-prereq-icon">🔐</span>
                    <div>
                      <strong>Node private key</strong>
                      <p>
                        You'll need the node's <code>private_key</code> from
                        <code>config.json</code> to authenticate this request.
                        Keep this secret.
                      </p>
                    </div>
                  </div>
                  <div class="wt-prereq">
                    <span class="wt-prereq-icon">🚫</span>
                    <div>
                      <strong>admin_kel must not be set</strong>
                      <p>
                        If <code>admin_kel</code> already exists in
                        <code>config.json</code>, the endpoint will reject the
                        request. Remove it first to re-initialize.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div class="wt-steps-list">
                <div class="wt-step-item">
                  <span class="wt-num">1</span>
                  <div>
                    <strong>Authenticate with node private key</strong>
                    <p>
                      The server verifies this matches its configured key before
                      proceeding.
                    </p>
                  </div>
                </div>
                <div class="wt-step-item">
                  <span class="wt-num">2</span>
                  <div>
                    <strong>Set a second factor</strong>
                    <p>
                      Combined with the node seed to derive the signing key
                      chain. Store it securely — needed for all future key
                      rotations.
                    </p>
                  </div>
                </div>
                <div class="wt-step-item">
                  <span class="wt-num">3</span>
                  <div>
                    <strong>Inception transaction submitted</strong>
                    <p>
                      The server builds and broadcasts the inception
                      transaction, then returns the transaction ID which you
                      must add to
                      <code>config.json</code> as <code>admin_kel</code>.
                    </p>
                  </div>
                </div>
              </div>
              <div class="ws-btn-row">
                <button class="ws-btn primary" @click="step = 1">
                  Get Started →
                </button>
              </div>
            </div>

            <!-- Step 1: Node private key -->
            <div v-else-if="step === 1" class="ws-walkthrough">
              <div class="wt-callout wt-callout-warn">
                <strong>Enter the node's private key</strong>
                <p>
                  This is the <code>private_key</code> value from the node's
                  <code>config.json</code>. It is used only for authentication —
                  it is sent to your own node over the configured node URL and
                  is not stored anywhere in the browser.
                </p>
              </div>
              <div class="ws-field">
                <label>Node Private Key</label>
                <input
                  v-model="adminPrivateKey"
                  type="password"
                  placeholder="Hex-encoded node private key from config.json"
                  autocomplete="off"
                />
              </div>
              <div v-if="error" class="ws-error">{{ error }}</div>
              <div class="ws-btn-row">
                <button class="ws-btn secondary" @click="step = 0">
                  ← Back
                </button>
                <button
                  class="ws-btn primary"
                  :disabled="!adminPrivateKey"
                  @click="step = 2"
                >
                  Continue →
                </button>
              </div>
            </div>

            <!-- Step 2: Second factor -->
            <div v-else-if="step === 2" class="ws-walkthrough">
              <div class="wt-callout">
                <strong>Choose a second factor password</strong>
                <p>
                  This password is combined server-side with the node seed to
                  derive the signing key chain. It is not stored anywhere — you
                  must remember it for future key rotations. Treat it with the
                  same care as the seed phrase.
                </p>
              </div>
              <div class="ws-field">
                <label>Second Factor Password</label>
                <input
                  v-model="secondFactor"
                  type="password"
                  placeholder="Choose a strong password"
                  autocomplete="new-password"
                />
              </div>
              <div class="ws-field">
                <label>Confirm Password</label>
                <input
                  v-model="secondFactorConfirm"
                  type="password"
                  placeholder="Re-enter password"
                  autocomplete="new-password"
                  @keydown.enter="doAdminSetup"
                />
              </div>
              <div v-if="error" class="ws-error">{{ error }}</div>
              <div class="ws-btn-row">
                <button class="ws-btn secondary" @click="step = 1">
                  ← Back
                </button>
                <button
                  class="ws-btn primary"
                  :disabled="busy || !secondFactor || !secondFactorConfirm"
                  @click="doAdminSetup"
                >
                  {{ busy ? "Initializing…" : "Initialize Admin Wallet" }}
                </button>
              </div>
            </div>

            <!-- Step 3: Success -->
            <div v-else-if="step === 3" class="ws-walkthrough">
              <div class="wt-section wt-highlight wt-highlight-green">
                <div class="wt-icon">✅</div>
                <div>
                  <h3>Admin wallet initialized!</h3>
                  <p>
                    The inception transaction has been submitted to the mempool.
                    Once it mines into a block, the key event log is established
                    on-chain.
                  </p>
                </div>
              </div>

              <div class="wt-txid-block">
                <span class="wt-txid-label">Transaction ID (admin_kel)</span>
                <a
                  class="wt-txid-val"
                  :href="`${origin}/explorer?term=${adminResult.transactionId}`"
                  target="_blank"
                  rel="noopener noreferrer"
                  >{{ adminResult.transactionId }}</a
                >
              </div>

              <div class="wt-result-block">
                <div class="wt-result-row">
                  <span class="wt-result-label">Signing Address</span>
                  <code class="wt-result-val">{{ adminResult.address }}</code>
                </div>
                <div class="wt-result-row">
                  <span class="wt-result-label">Prerotated Address</span>
                  <code class="wt-result-val">{{
                    adminResult.prerotatedAddress
                  }}</code>
                </div>
              </div>

              <div class="wt-callout wt-callout-action">
                <strong>Required: Update config.json</strong>
                <p>
                  Add the following line to your node's
                  <code>config.json</code> to designate this as the authorized
                  admin key event log, then restart the node:
                </p>
                <pre class="wt-code-block">
"admin_kel": "{{ adminResult.transactionId }}"</pre
                >
              </div>

              <div class="wt-callout">
                <strong>Store your second factor</strong>
                <p>
                  Keep your second factor password in a safe place alongside the
                  node seed. It is required for every future key rotation on
                  this admin wallet. There is no recovery path if it is lost.
                </p>
              </div>

              <div class="ws-btn-row">
                <button class="ws-btn primary" @click="step++">
                  Next: Configure AI →
                </button>
              </div>
            </div>

            <!-- Step 4: Configure AI -->
            <div v-else-if="step === 4" class="ws-walkthrough">
              <div class="wt-section wt-highlight wt-highlight-green">
                <div class="wt-icon">✅</div>
                <div>
                  <h3>Admin wallet ready — configure your AI provider</h3>
                  <p>
                    Set your LLM provider and model below before continuing.
                    Without this the chat will fail.
                  </p>
                </div>
              </div>
              <div class="llm-form" @submit.prevent>
                <div class="ws-field">
                  <label>Provider</label>
                  <select
                    v-model="llmForm.provider"
                    @change="llmForm.model = ''"
                  >
                    <option value="ollama">Ollama (local, free)</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="github_models">
                      GitHub Models (free tier)
                    </option>
                    <option value="openai_compat">
                      OpenAI-compatible (custom)
                    </option>
                  </select>
                </div>
                <div v-if="llmForm.provider === 'ollama'" class="ws-field">
                  <label>Ollama Host</label>
                  <input
                    v-model="llmForm.ollama_host"
                    type="text"
                    placeholder="http://localhost:11434"
                  />
                  <div class="ws-hint">
                    Run <code>ollama list</code> to see available models.
                  </div>
                </div>
                <div
                  v-if="llmForm.provider === 'openai_compat'"
                  class="ws-field"
                >
                  <label>Base URL</label>
                  <input
                    v-model="llmForm.base_url"
                    type="text"
                    placeholder="https://api.example.com/v1"
                  />
                </div>
                <div class="ws-field">
                  <label>Model</label>
                  <input
                    v-model="llmForm.model"
                    type="text"
                    :placeholder="llmModelPlaceholder"
                  />
                  <div class="ws-hint" v-html="llmModelHint"></div>
                </div>
                <div v-if="llmForm.provider !== 'ollama'" class="ws-field">
                  <label>API Key</label>
                  <input
                    v-model="llmForm.api_key"
                    type="password"
                    :placeholder="
                      llmForm.provider === 'github_models'
                        ? 'GitHub PAT (github_pat_…)'
                        : 'sk-…'
                    "
                    autocomplete="off"
                  />
                  <div class="ws-hint">
                    Stored in localStorage only — never sent to the YadaCoin
                    server.
                  </div>
                </div>
              </div>
              <div class="wt-callout wt-callout-warn" style="margin-top: 4px">
                <strong>⚠️ Payment Methods — Demo Only</strong>
                <p>
                  The payment methods section in Settings is for
                  <strong>demonstration purposes only</strong>. No real payment
                  processing occurs.
                  <strong
                    >Do not enter real card numbers or financial data.</strong
                  >
                  Use placeholders like <code>Visa ending in 4242</code>.
                </p>
              </div>
              <div class="ws-btn-row">
                <button
                  class="ws-btn primary"
                  :disabled="!llmFormValid"
                  @click="saveLlmAndFinish"
                >
                  Finish &amp; Start Chatting
                </button>
              </div>
            </div>
          </div>

          <!-- ═══════════════════════════════════════════════════════════════════ -->
          <!-- HARDWARE WALLET TAB                                                   -->
          <!-- ═══════════════════════════════════════════════════════════════════ -->
          <div v-else-if="tab === 'hardware'" class="ws-body">
            <!-- Step 0: Overview -->
            <div v-if="step === 0" class="ws-walkthrough">
              <div class="wt-section wt-highlight">
                <div class="wt-icon">📟</div>
                <div>
                  <h3>Air-Gapped Hardware Wallet</h3>
                  <p>
                    In hardware mode, your seed and all key rotations live on a
                    dedicated air-gapped device. The browser never sees a seed —
                    every approval requires scanning a fresh QR code from the
                    device that contains the WIF and pre-committed hashes for
                    exactly that step.
                  </p>
                </div>
              </div>
              <div class="wt-steps-list">
                <div class="wt-step-item">
                  <span class="wt-num">1</span>
                  <div>
                    <strong>Pair the device</strong>
                    <p>
                      Scan the device's current rotation QR so the browser knows
                      which public key represents you on the network.
                    </p>
                  </div>
                </div>
                <div class="wt-step-item">
                  <span class="wt-num">2</span>
                  <div>
                    <strong>Approve actions step-by-step</strong>
                    <p>
                      Each approval will ask you to scan two QR codes: the
                      rotation key and the next confirming key. The browser
                      builds and broadcasts the transactions; your private keys
                      never leave the device.
                    </p>
                  </div>
                </div>
              </div>
              <div class="ws-btn-row">
                <button class="ws-btn primary" @click="step = 1">
                  Pair Device →
                </button>
              </div>
            </div>

            <!-- Step 1: Pair device — TWO scans (inception WIF + active WIF) -->
            <div v-else-if="step === 1" class="ws-walkthrough">
              <div class="wt-callout">
                <strong>Pair your hardware device — two scans required</strong>
                <p>
                  Scan the inception QR (rotation index <code>0</code>) first.
                  The browser will look up the on-chain key event log for that
                  public key and tell you which rotation index to scan next for
                  the active key. The inception WIF is used once (only if no KEL
                  exists yet) and then discarded; the active key is stored
                  locally so the browser can sign the next unconfirmed rotation
                  without prompting you.
                </p>
                <p>
                  QR format:
                  <code
                    >WIF | prerotated_key_hash | twice_prerotated_key_hash |
                    prev_public_key_hash | rotation_index</code
                  >
                </p>
              </div>

              <div
                v-if="!hwPaired"
                class="hw-block"
                style="margin-bottom: 12px"
              >
                <div class="hw-row">
                  <span class="hw-label">Step 1 — inception key (idx 0)</span>
                  <span v-if="hwScan1" class="hw-status ok"
                    >✓ captured (idx {{ hwScan1.rotationIndex }})</span
                  >
                  <span v-else class="hw-status">awaiting scan</span>
                </div>
                <div v-if="hwScan1 && hwKelLoading" class="hw-row">
                  <span class="hw-label"
                    >Looking up on-chain key event log…</span
                  >
                </div>
                <div v-if="hwKelInfo" class="hw-row">
                  <span class="hw-label">
                    <template v-if="hwKelInfo.kel.length === 0">
                      No on-chain KEL yet — pairing will broadcast the inception
                      and store
                      <strong>idx {{ hwKelInfo.expectedActiveIndex }}</strong>
                      as your active key.
                    </template>
                    <template v-else>
                      On-chain KEL has
                      <strong>{{ hwKelInfo.kel.length }}</strong> entries — the
                      active key the host needs is at rotation index
                      <strong>{{ hwKelInfo.expectedActiveIndex }}</strong
                      >. Advance the device until it shows that QR.
                    </template>
                  </span>
                </div>
                <div class="hw-row">
                  <span class="hw-label">
                    Step 2 — active key (idx
                    {{ hwKelInfo ? hwKelInfo.expectedActiveIndex : "?" }})
                  </span>
                  <span v-if="hwScan2" class="hw-status ok"
                    >✓ captured (idx {{ hwScan2.rotationIndex }})</span
                  >
                  <span v-else class="hw-status">awaiting scan</span>
                </div>
                <div class="hw-actions">
                  <button
                    class="ws-btn"
                    :disabled="
                      hwPairing ||
                      !!hwPairScanning ||
                      (!!hwScan1 && hwKelLoading)
                    "
                    @click="openHwScan(hwScan1 ? 'two' : 'one')"
                  >
                    📷
                    {{
                      !hwScan1
                        ? "Scan inception QR"
                        : !hwScan2
                          ? "Scan active-key QR"
                          : "Re-scan"
                    }}
                  </button>
                  <button
                    v-if="hwScan1 || hwScan2"
                    class="ws-btn"
                    :disabled="hwPairing"
                    @click="resetHwPair"
                  >
                    Clear
                  </button>
                </div>
              </div>

              <QrScanner
                v-if="hwPairScanning"
                :title="
                  hwPairScanning === 'one'
                    ? 'Scan inception QR (rotation index 0)'
                    : 'Scan active-key QR (rotation index ' +
                      (hwKelInfo ? hwKelInfo.expectedActiveIndex : '?') +
                      ')'
                "
                :hint="
                  hwPairScanning === 'one'
                    ? 'On your device, display the inception QR. The WIF will be used once to broadcast the inception transaction (only if no KEL exists yet), then discarded.'
                    : hwKelInfo && hwKelInfo.kel.length > 0
                      ? 'Existing on-chain KEL has ' +
                        hwKelInfo.kel.length +
                        ' entries. Advance the device to rotation index ' +
                        hwKelInfo.expectedActiveIndex +
                        ' and display its QR.'
                      : 'Now display the QR for rotation index 1. This key will be stored locally to sign the next unconfirmed rotation.'
                "
                @scanned="onHardwareScan"
                @cancel="hwPairScanning = null"
              />

              <div v-if="!hwPaired && hwScan1 && hwScan2" class="ws-btn-row">
                <button
                  class="ws-btn primary"
                  :disabled="hwPairing || hwKelLoading || !hwKelInfo"
                  @click="pairHardware"
                >
                  {{ hwPairing ? "Pairing…" : "Pair device" }}
                </button>
              </div>

              <div v-if="hwPaired" class="wt-section wt-highlight">
                <div class="wt-icon">✅</div>
                <div>
                  <h3>Device Paired</h3>
                  <p>
                    Active public key:
                    <code style="font-family: monospace; font-size: 0.78rem"
                      >{{ hwPaired.publicKeyHex.slice(0, 24) }}…</code
                    ><br />
                    Rotation index: <strong>{{ hwPaired.rotationIndex }}</strong
                    ><br />
                    <span v-if="hwPaired.inceptionBroadcast"
                      >Inception transaction broadcast.</span
                    >
                    <span v-else
                      >Existing KEL detected — inception was not
                      re-broadcast.</span
                    >
                  </p>
                </div>
              </div>

              <div v-if="error" class="ws-warn">⚠ {{ error }}</div>
              <div class="ws-btn-row">
                <button
                  class="ws-btn primary"
                  :disabled="!hwPaired"
                  @click="step = 2"
                >
                  Next: Configure AI →
                </button>
              </div>
            </div>

            <!-- Step 2: Configure AI -->
            <div v-else-if="step === 2" class="ws-walkthrough">
              <div class="wt-callout">
                <strong>Configure your AI provider</strong>
                <p>
                  Same as the other setup paths — pick a provider and model.
                </p>
              </div>
              <div class="llm-form" @submit.prevent>
                <div class="ws-field">
                  <label>Provider</label>
                  <select
                    v-model="llmForm.provider"
                    @change="llmForm.model = ''"
                  >
                    <option value="ollama">Ollama (local, free)</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="github_models">
                      GitHub Models (free tier)
                    </option>
                    <option value="openai_compat">
                      OpenAI-compatible (custom)
                    </option>
                  </select>
                </div>
                <div v-if="llmForm.provider === 'ollama'" class="ws-field">
                  <label>Ollama Host</label>
                  <input
                    v-model="llmForm.ollama_host"
                    type="text"
                    placeholder="http://localhost:11434"
                  />
                  <div class="ws-hint">
                    Run <code>ollama list</code> to see available models.
                    Default host is <code>http://localhost:11434</code>.
                  </div>
                </div>
                <div
                  v-if="llmForm.provider === 'openai_compat'"
                  class="ws-field"
                >
                  <label>Base URL</label>
                  <input
                    v-model="llmForm.base_url"
                    type="text"
                    placeholder="https://api.example.com/v1"
                  />
                </div>
                <div class="ws-field">
                  <label>Model</label>
                  <input
                    v-model="llmForm.model"
                    type="text"
                    :placeholder="llmModelPlaceholder"
                  />
                  <div class="ws-hint" v-html="llmModelHint"></div>
                </div>
                <div v-if="llmForm.provider !== 'ollama'" class="ws-field">
                  <label>API Key</label>
                  <input
                    v-model="llmForm.api_key"
                    type="password"
                    :placeholder="
                      llmForm.provider === 'github_models'
                        ? 'GitHub PAT (github_pat_…)'
                        : 'sk-…'
                    "
                    autocomplete="off"
                  />
                  <div class="ws-hint">
                    Stored in localStorage only — never sent to the YadaCoin
                    server.
                  </div>
                </div>
              </div>
              <div class="ws-btn-row">
                <button
                  class="ws-btn primary"
                  :disabled="!llmFormValid"
                  @click="saveLlmAndFinish"
                >
                  Finish &amp; Start Chatting
                </button>
              </div>
            </div>
          </div>

          <!-- ═══════════════════════════════════════════════════════════════════ -->
          <!-- RECOVER VIA LOCATIONS TAB                                           -->
          <!-- ═══════════════════════════════════════════════════════════════════ -->
          <div v-else-if="tab === 'recover_loc'" class="ws-body">
            <!-- Step 0: Recover -->
            <div v-if="step === 0" class="ws-walkthrough">
              <div class="wt-section wt-highlight">
                <div class="wt-icon">🗺️</div>
                <div>
                  <h3>Recover Wallet from Locations</h3>
                  <p>
                    Enter your Recovery Code and re-pin the three locations you
                    chose during setup. The seed phrase is decrypted locally —
                    your coordinates are never sent to the server. You'll also
                    need the second-factor password used at setup.
                  </p>
                </div>
              </div>
              <LocationRecoveryRecover
                @recovered="onLocationRecovered"
                @cancel="close"
              />
            </div>

            <!-- Step 1: Configure AI (after successful recovery) -->
            <div v-else-if="step === 1" class="ws-walkthrough">
              <div class="wt-section wt-highlight wt-highlight-green">
                <div class="wt-icon">✅</div>
                <div>
                  <h3>Wallet recovered — configure your AI provider</h3>
                  <p>
                    Set your LLM provider and model below before continuing.
                  </p>
                </div>
              </div>
              <div class="llm-form" @submit.prevent>
                <div class="ws-field">
                  <label>Provider</label>
                  <select
                    v-model="llmForm.provider"
                    @change="llmForm.model = ''"
                  >
                    <option value="ollama">Ollama (local, free)</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="github_models">
                      GitHub Models (free tier)
                    </option>
                    <option value="openai_compat">
                      OpenAI-compatible (custom)
                    </option>
                  </select>
                </div>
                <div v-if="llmForm.provider === 'ollama'" class="ws-field">
                  <label>Ollama Host</label>
                  <input
                    v-model="llmForm.ollama_host"
                    type="text"
                    placeholder="http://localhost:11434"
                  />
                </div>
                <div
                  v-if="llmForm.provider === 'openai_compat'"
                  class="ws-field"
                >
                  <label>Base URL</label>
                  <input
                    v-model="llmForm.base_url"
                    type="text"
                    placeholder="https://api.example.com/v1"
                  />
                </div>
                <div class="ws-field">
                  <label>Model</label>
                  <input
                    v-model="llmForm.model"
                    type="text"
                    :placeholder="llmModelPlaceholder"
                  />
                  <div class="ws-hint" v-html="llmModelHint"></div>
                </div>
                <div v-if="llmForm.provider !== 'ollama'" class="ws-field">
                  <label>API Key</label>
                  <input
                    v-model="llmForm.api_key"
                    type="password"
                    :placeholder="
                      llmForm.provider === 'github_models'
                        ? 'GitHub PAT (github_pat_…)'
                        : 'sk-…'
                    "
                    autocomplete="off"
                  />
                </div>
              </div>
              <div class="ws-btn-row">
                <button
                  class="ws-btn primary"
                  :disabled="!llmFormValid"
                  @click="saveLlmAndFinish"
                >
                  Finish &amp; Start Chatting
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <button class="ws-close" @click="close">✕</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import {
  generateNewMnemonic,
  isValidMnemonic,
  initClientWallet,
  submitInceptionTransaction,
  initAdminServerWallet,
} from "../composables/useBip39.js";
import {
  getLlmSettings,
  saveLlmSettings,
  setWalletMode,
  setHardwareActive,
  getNodeUrl,
  saveBookingCredential,
  LS_HW_PUB,
  LS_HW_QR,
  LS_PRIV,
  LS_CC,
} from "../composables/useStorage.js";
import {
  parseHardwareQrPayload,
  buildRotationTxn,
} from "../composables/useCrypto.js";
import QrScanner from "./QrScanner.vue";
import LocationRecoverySetup from "./LocationRecoverySetup.vue";
import LocationRecoveryRecover from "./LocationRecoveryRecover.vue";
import { clientRotateWithRelationship } from "../composables/useRotation.js";
import { resyncCredentials } from "../composables/useCredentialReceipts.js";

const emit = defineEmits(["done", "close"]);

// ── Tab & step state ──────────────────────────────────────────────────────────
const tab = ref("generate");
const step = ref(0);

const tabSteps = {
  generate: [
    "Overview",
    "Generate Seed Phrase",
    "Confirm Backup",
    "Set Password",
    "Location Backup (Optional)",
    "Configure AI",
  ],
  import: ["Overview", "Enter Seed Phrase", "Enter Password", "Configure AI"],
  admin: [
    "Overview & Prerequisites",
    "Node Authentication",
    "Set Second Factor",
    "Success",
    "Configure AI",
  ],
  hardware: ["Overview", "Pair Device", "Configure AI"],
  recover_loc: ["Recover with Locations", "Configure AI"],
};

// ── Shared fields ─────────────────────────────────────────────────────────────
const mnemonicWords = ref([]);
const importPhrase = ref("");
const secondFactor = ref("");
const secondFactorConfirm = ref("");
const error = ref("");
const busy = ref(false);

// ── Generate-tab state ────────────────────────────────────────────────────────
const backupChecks = ref([false, false, false]);
const allBackupChecked = computed(() => backupChecks.value.every(Boolean));

// ── Import-tab state ──────────────────────────────────────────────────────────
const phraseValid = computed(() =>
  importPhrase.value.trim()
    ? isValidMnemonic(importPhrase.value.trim())
    : false,
);

// ── Admin-tab state ───────────────────────────────────────────────────────────
const adminPrivateKey = ref("");
const adminResult = ref(null);
const origin = window.location.origin;

// ── Location-recovery state ───────────────────────────────────────────────────
// Set by the LocationRecoverySetup component on the generate tab once the
// seed phrase has been wrapped in a ZKP location commitment. Keeping the
// recently generated mnemonic phrase here lets the optional location-backup
// step encrypt it without re-prompting the user.
const locationSetupResult = ref(null);
const generatedMnemonicPhrase = computed(() =>
  mnemonicWords.value.length ? mnemonicWords.value.join(" ") : null,
);

function onLocationSetupComplete(result) {
  locationSetupResult.value = result;
  // Fire-and-forget broadcast of the on-chain `{recovery: witnessHash}`
  // announcement.  We don't block the wizard on this — the user can
  // continue past step 4 — but we surface failures via the wizard's
  // generic `error` ref so they aren't silent.
  publishRecoveryAnnouncement(result).catch((e) => {
    error.value =
      "Could not broadcast on-chain recovery announcement: " +
      (e?.message || String(e)) +
      ". You can retry by re-running the location setup.";
  });
}

/**
 * Embed `{recovery: ...}` as the relationship of a fresh KEL rotation
 * signed by the wallet's current active key.  The relationship payload
 * (and its preimage hash) are built by `setupLocationRecovery` so they
 * include the lookup_id + AES-GCM-encrypted hint labels keyed by the
 * user's Recovery Code.  Once mined this announcement is what
 * `find-recovery-tip` looks up at recovery time, so without it a
 * fresh-device recovery cannot delegate authority over this KEL.
 */
async function publishRecoveryAnnouncement(result) {
  const announcement = result?.txnData?.announcementData;
  if (!announcement?.relationship || !announcement?.relationshipHash) {
    throw new Error("location setup did not return a recovery announcement");
  }
  await clientRotateWithRelationship(
    secondFactor.value,
    announcement.relationship,
    announcement.relationshipHash,
  );
}

function onLocationRecovered() {
  // Recovery view already called initClientWallet + submitInceptionTransaction
  // and stored the witness secret.  Restore previously issued credentials from
  // on-chain encrypted receipts.  Non-fatal if the node is unreachable.
  resyncCredentials()
    .then((vcs) => vcs.forEach(saveBookingCredential))
    .catch(() => {});
  // Continue the wizard into the LLM-config step.
  step.value = 1;
}

// ── Hardware-tab state ────────────────────────────────────────────────────────// Pairing requires TWO scans:
//   • scan 1 = inception WIF (K_0) — used once to broadcast the inception tx
//              if no KEL exists yet for this device, then discarded.
//   • scan 2 = active WIF   (K_1) — persisted as LS_HW_QR. This is the key
//              that will sign the next unconfirmed rotation tx.
const hwScan1 = ref(null);
const hwScan2 = ref(null);
const hwPairScanning = ref(null); // null | 'one' | 'two'
const hwPaired = ref(null);
const hwPairing = ref(false);
// After scan 1, we query the KEL for K_0's pubkey to figure out where the
// device's chain actually is on-chain. The active key the host must hold is
// the next prerotation past the chain tip — i.e. its rotation_index equals
// the existing KEL length (or 1 for a fresh device with no KEL yet).
const hwKelInfo = ref(null); // { kel, expectedActiveIndex, expectedActivePkh }
const hwKelLoading = ref(false);

function openHwScan(which) {
  error.value = "";
  hwPairScanning.value = which;
}

async function lookupKelForScan1(s1) {
  hwKelLoading.value = true;
  hwKelInfo.value = null;
  try {
    const nodeUrl = getNodeUrl();
    const r = await fetch(
      `${nodeUrl}/key-event-log?username_signature=asdf&public_key=${encodeURIComponent(s1.publicKeyHex)}`,
    );
    const j = await r.json();
    const kel = j.key_event_log || [];
    let expectedActiveIndex;
    let expectedActivePkh;
    if (kel.length === 0) {
      // Fresh device — host's active key will be K_1, committed by scan 1.
      expectedActiveIndex = 1;
      expectedActivePkh = s1.prerotatedKeyHash;
    } else {
      // Chain has L entries (idx 0..L-1). Latest entry committed K_L as its
      // prerotated_key_hash; that K_L is the active key the host must hold.
      expectedActiveIndex = kel.length;
      const tip = kel[kel.length - 1];
      expectedActivePkh =
        tip.prerotated_key_hash ||
        tip.prerotatedKeyHash ||
        s1.prerotatedKeyHash;
    }
    hwKelInfo.value = { kel, expectedActiveIndex, expectedActivePkh };
  } catch (e) {
    error.value =
      "Could not look up key event log: " + (e?.message || String(e));
  } finally {
    hwKelLoading.value = false;
  }
}

function onHardwareScan(raw) {
  error.value = "";
  let parsed;
  try {
    parsed = parseHardwareQrPayload(raw);
  } catch (e) {
    error.value = "Invalid QR payload: " + (e?.message || String(e));
    return;
  }
  if (hwPairScanning.value === "one") {
    hwScan1.value = parsed;
    // Kick off KEL lookup so we can tell the user which rotation_index to
    // scan for the active key (K_0 + 1 for a fresh device, or K_L if the
    // chain has already advanced to length L).
    lookupKelForScan1(parsed);
  } else if (hwPairScanning.value === "two") {
    const info = hwKelInfo.value;
    if (!info) {
      error.value =
        "Still looking up the on-chain key event log — try again in a moment.";
      return;
    }
    if (parsed.rotationIndex !== info.expectedActiveIndex) {
      error.value =
        "Active-key QR rotation_index must be " +
        info.expectedActiveIndex +
        " (got " +
        parsed.rotationIndex +
        "). On-chain KEL length is " +
        info.kel.length +
        " — advance the device until it shows the QR for index " +
        info.expectedActiveIndex +
        ".";
      return;
    }
    if (parsed.publicKeyHash !== info.expectedActivePkh) {
      error.value =
        "Active-key QR's public key hash does not match the prerotated_key_hash committed by the chain tip. The device may belong to a different KEL.";
      return;
    }
    hwScan2.value = parsed;
  }
  hwPairScanning.value = null;
}

function resetHwPair() {
  hwScan1.value = null;
  hwScan2.value = null;
  hwPaired.value = null;
  hwKelInfo.value = null;
  error.value = "";
}

async function pairHardware() {
  if (!hwScan1.value || !hwScan2.value) {
    error.value = "Both QR codes must be scanned before pairing.";
    return;
  }
  if (!hwKelInfo.value) {
    error.value = "Key event log lookup has not finished yet.";
    return;
  }
  hwPairing.value = true;
  error.value = "";
  try {
    const s1 = hwScan1.value;
    const s2 = hwScan2.value;
    const nodeUrl = getNodeUrl();
    const kelEmpty = hwKelInfo.value.kel.length === 0;

    // Only broadcast the inception when the chain has no KEL for K_0 yet.
    if (kelEmpty) {
      const txnTime = Math.floor(Date.now() / 1000);
      const inceptionTxn = await buildRotationTxn({
        signerPrivBytes: s1.privBytes,
        publicKeyHex: s1.publicKeyHex,
        prerotatedPkh: s1.prerotatedKeyHash,
        twicePrerotatedPkh: s1.twicePrerotatedKeyHash,
        publicKeyHash: s1.publicKeyHash,
        prevPublicKeyHash: "",
        relationship: "",
        relationshipHash: "",
        txnTime,
        inputs: [],
        outputs: [{ to: s1.prerotatedKeyHash, value: 0.0 }],
      });
      const bres = await fetch(`${nodeUrl}/transaction?username_signature=1`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify([inceptionTxn]),
      });
      const bdata = await bres.json();
      if (!bres.ok || bdata.status === false) {
        throw new Error(bdata.message || `HTTP ${bres.status}`);
      }
    }

    // Persist scan 2 as the active hardware key.
    setHardwareActive(s2);
    localStorage.removeItem(LS_PRIV);
    localStorage.removeItem(LS_CC);
    setWalletMode("hardware");
    hwPaired.value = {
      publicKeyHex: s2.publicKeyHex,
      rotationIndex: s2.rotationIndex,
      inceptionBroadcast: kelEmpty,
      kelLength: hwKelInfo.value.kel.length,
    };
  } catch (e) {
    error.value = "Pairing failed: " + (e?.message || String(e));
  } finally {
    hwPairing.value = false;
  }
}

// ── LLM config form (Configure AI step) ──────────────────────────────────────
const llmForm = ref({ ...getLlmSettings() });

const LLM_MODEL_HINTS = {
  ollama:
    "Default: <code>llama3.2</code>. Run <code>ollama list</code> to see installed models.",
  openai: "e.g. <code>gpt-4o-mini</code>, <code>gpt-4o</code>",
  anthropic:
    "e.g. <code>claude-3-5-haiku-20241022</code>, <code>claude-3-5-sonnet-20241022</code>",
  openai_compat: "Enter the model name your provider expects.",
  github_models:
    "\u26a0\ufe0f Rate-limited to ~2 req/min. Try <code>gpt-4.1-mini</code> or <code>Meta-Llama-3.1-70B-Instruct</code>.",
};
const LLM_MODEL_PLACEHOLDERS = {
  ollama: "llama3.2",
  openai: "gpt-4o-mini",
  anthropic: "claude-3-haiku-20240307",
  openai_compat: "gpt-3.5-turbo",
  github_models: "gpt-4.1-mini",
};
const llmModelHint = computed(
  () => LLM_MODEL_HINTS[llmForm.value.provider] || "",
);
const llmModelPlaceholder = computed(
  () => LLM_MODEL_PLACEHOLDERS[llmForm.value.provider] || "",
);
const llmFormValid = computed(() => {
  const { provider, model, api_key } = llmForm.value;
  if (!model.trim()) return false;
  if (provider !== "ollama" && !api_key.trim()) return false;
  return true;
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function switchTab(t) {
  tab.value = t;
  step.value = 0;
  mnemonicWords.value = [];
  importPhrase.value = "";
  secondFactor.value = "";
  secondFactorConfirm.value = "";
  error.value = "";
  backupChecks.value = [false, false, false];
  adminPrivateKey.value = "";
  adminResult.value = null;
  hwPaired.value = null;
  locationSetupResult.value = null;
}

function doGenerate() {
  const phrase = generateNewMnemonic();
  mnemonicWords.value = phrase.split(" ");
  mnemonicCopied.value = false;
}

const mnemonicCopied = ref(false);
async function copyMnemonic() {
  try {
    await navigator.clipboard.writeText(mnemonicWords.value.join(" "));
    mnemonicCopied.value = true;
    setTimeout(() => (mnemonicCopied.value = false), 2000);
  } catch {
    // fallback for older browsers
    const ta = document.createElement("textarea");
    ta.value = mnemonicWords.value.join(" ");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    mnemonicCopied.value = true;
    setTimeout(() => (mnemonicCopied.value = false), 2000);
  }
}

function downloadMnemonic() {
  const text = mnemonicWords.value.join(" ");
  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "yadacoin-seed-phrase.txt";
  a.click();
  URL.revokeObjectURL(url);
}

// ── Generate / Import submit ──────────────────────────────────────────────────
async function doSetup() {
  error.value = "";
  const phrase =
    tab.value === "generate"
      ? mnemonicWords.value.join(" ")
      : importPhrase.value.trim();

  if (!phrase) {
    error.value = "No seed phrase provided.";
    return;
  }
  if (!isValidMnemonic(phrase)) {
    error.value = "Invalid seed phrase.";
    return;
  }
  if (!secondFactor.value) {
    error.value = "Second factor is required.";
    return;
  }
  if (
    tab.value === "generate" &&
    secondFactor.value !== secondFactorConfirm.value
  ) {
    error.value = "Passwords do not match.";
    return;
  }

  busy.value = true;
  try {
    const k0 = await initClientWallet(phrase, secondFactor.value);
    if (tab.value === "import") {
      // Fire-and-forget: restore any previously issued credentials from
      // on-chain encrypted receipts. Non-fatal if the node is unreachable.
      resyncCredentials()
        .then((vcs) => vcs.forEach(saveBookingCredential))
        .catch(() => {});
    }
    await submitInceptionTransaction(k0, secondFactor.value);
    step.value++; // advance to Configure AI step
  } catch (e) {
    error.value = "Setup failed: " + String(e);
  } finally {
    busy.value = false;
  }
}

// ── Admin server wallet submit ────────────────────────────────────────────────
async function doAdminSetup() {
  error.value = "";
  if (!adminPrivateKey.value) {
    error.value = "Node private key is required.";
    return;
  }
  if (!secondFactor.value) {
    error.value = "Second factor is required.";
    return;
  }
  if (secondFactor.value !== secondFactorConfirm.value) {
    error.value = "Passwords do not match.";
    return;
  }

  busy.value = true;
  try {
    const result = await initAdminServerWallet(
      adminPrivateKey.value,
      secondFactor.value,
    );
    adminResult.value = result;
    step.value = 3;
  } catch (e) {
    error.value = "Initialization failed: " + String(e);
  } finally {
    busy.value = false;
  }
}

function close() {
  emit("close");
}

function saveLlmAndFinish() {
  saveLlmSettings(llmForm.value);
  emit("done");
}
</script>

<style scoped>
.wallet-setup-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.wallet-setup-modal {
  position: relative;
  background: var(--surface2, #1e1e2e);
  border: 1px solid var(--border, #333);
  border-radius: 12px;
  padding: 32px;
  max-width: 820px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.6);
}

.ws-header h2 {
  margin: 0 0 6px;
  font-size: 1.3rem;
  color: var(--text, #e0e0e0);
}

.ws-subtitle {
  margin: 0 0 20px;
  font-size: 0.85rem;
  color: var(--text2, #999);
}

/* ── Sidebar layout ── */
.ws-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.ws-content {
  flex: 1;
  min-width: 0;
}

/* ── Tabs ── */
.ws-tabs {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 0;
  flex: 0 0 180px;
  width: 180px;
}

.ws-tab {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border, #444);
  background: transparent;
  color: var(--text2, #aaa);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.78rem;
  transition: all 0.15s;
  text-align: left;
  white-space: normal;
}

.ws-tab.active,
.ws-tab:hover {
  background: var(--accent, #7c6af7);
  color: #fff;
  border-color: var(--accent, #7c6af7);
}

@media (max-width: 640px) {
  .ws-layout {
    flex-direction: column;
  }
  .ws-tabs {
    flex: 0 0 auto;
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
  }
  .ws-tab {
    flex: 1 1 auto;
    text-align: center;
  }
}

/* ── Progress dots ── */
.ws-progress {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-bottom: 6px;
}

.ws-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--border, #444);
  transition: background 0.2s;
}
.ws-dot.done {
  background: var(--accent, #7c6af7);
  opacity: 0.5;
}
.ws-dot.active {
  background: var(--accent, #7c6af7);
}

.ws-step-label {
  text-align: center;
  font-size: 0.75rem;
  color: var(--text3, #666);
  margin-bottom: 20px;
}

/* ── Body ── */
.ws-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── Walkthrough container ── */
.ws-walkthrough {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── wt-section / highlight block ── */
.wt-section {
  border-radius: 8px;
  padding: 14px 16px;
  border: 1px solid var(--border, #333);
}

.wt-section h3 {
  margin: 0 0 6px;
  font-size: 1rem;
  color: var(--text, #e0e0e0);
}
.wt-section h4 {
  margin: 0 0 10px;
  font-size: 0.85rem;
  color: var(--text2, #aaa);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.wt-section p {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text2, #999);
  line-height: 1.5;
}

.wt-highlight {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  background: rgba(124, 106, 247, 0.08);
  border-color: rgba(124, 106, 247, 0.3);
}
.wt-highlight-amber {
  background: rgba(224, 160, 96, 0.08);
  border-color: rgba(224, 160, 96, 0.3);
}
.wt-highlight-green {
  background: rgba(80, 200, 120, 0.08);
  border-color: rgba(80, 200, 120, 0.3);
}
.wt-highlight-green h3 {
  color: #6dd08a;
}

.wt-icon {
  font-size: 1.6rem;
  line-height: 1;
  flex-shrink: 0;
  padding-top: 2px;
}

/* ── Step list ── */
.wt-steps-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.wt-step-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.wt-step-item strong {
  font-size: 0.88rem;
  color: var(--text, #e0e0e0);
}
.wt-step-item p {
  margin: 3px 0 0;
  font-size: 0.82rem;
  color: var(--text2, #999);
  line-height: 1.45;
}

.wt-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--accent, #7c6af7);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

/* ── Prerequisites ── */
.wt-prereq-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.wt-prereq {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.wt-prereq-icon {
  font-size: 1.1rem;
  flex-shrink: 0;
  padding-top: 1px;
}
.wt-prereq strong {
  font-size: 0.85rem;
  color: var(--text, #e0e0e0);
}
.wt-prereq p {
  margin: 2px 0 0;
  font-size: 0.8rem;
  color: var(--text2, #999);
  line-height: 1.4;
}
.wt-prereq code {
  font-size: 0.78rem;
  background: var(--surface3, #2a2a3e);
  padding: 1px 4px;
  border-radius: 3px;
  color: var(--text, #ccc);
}

/* ── Callout blocks ── */
.wt-callout {
  background: var(--surface3, #2a2a3e);
  border: 1px solid var(--border, #333);
  border-radius: 6px;
  padding: 12px 14px;
}
.wt-callout strong {
  font-size: 0.88rem;
  color: var(--text, #e0e0e0);
  display: block;
  margin-bottom: 4px;
}
.wt-callout p {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text2, #999);
  line-height: 1.45;
}
.wt-callout code {
  font-size: 0.78rem;
  background: rgba(255, 255, 255, 0.07);
  padding: 1px 4px;
  border-radius: 3px;
  color: var(--text, #ccc);
}

.wt-callout-warn {
  border-color: rgba(224, 160, 96, 0.4);
  background: rgba(224, 160, 96, 0.06);
}
.wt-callout-action {
  border-color: rgba(124, 106, 247, 0.4);
  background: rgba(124, 106, 247, 0.06);
}

/* ── Node operator authorization warning ── */
.wt-auth-warning {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  background: rgba(220, 53, 69, 0.1);
  border: 1px solid rgba(220, 53, 69, 0.45);
  border-radius: 8px;
  padding: 14px 16px;
}
.wt-auth-warning-icon {
  font-size: 1.3rem;
  flex-shrink: 0;
  padding-top: 1px;
}
.wt-auth-warning strong {
  display: block;
  font-size: 0.88rem;
  color: #f08080;
  margin-bottom: 4px;
}
.wt-auth-warning p {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text2, #aaa);
  line-height: 1.45;
}

/* ── Checklist ── */
.wt-checklist {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.wt-check {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--text, #e0e0e0);
  line-height: 1.45;
}
.wt-check input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--accent, #7c6af7);
  flex-shrink: 0;
  margin-top: 2px;
  cursor: pointer;
}

/* ── Result block ── */
.wt-result-block {
  background: var(--surface3, #2a2a3e);
  border: 1px solid var(--border, #333);
  border-radius: 6px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.wt-result-row {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.wt-result-label {
  font-size: 0.73rem;
  color: var(--text3, #666);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.wt-result-val {
  font-family: monospace;
  font-size: 0.78rem;
  color: var(--text, #e0e0e0);
  word-break: break-all;
  background: rgba(255, 255, 255, 0.04);
  padding: 4px 6px;
  border-radius: 4px;
}
.wt-result-highlight {
  color: #6dd08a;
  background: rgba(80, 200, 120, 0.08);
}

/* ── Transaction ID prominent block ── */
.wt-txid-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: rgba(80, 200, 120, 0.07);
  border: 1px solid rgba(80, 200, 120, 0.25);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 2px;
}
.wt-txid-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #6dd08a;
  opacity: 0.8;
}
.wt-txid-val {
  font-family: monospace;
  font-size: 0.82rem;
  color: #6dd08a;
  word-break: break-all;
  text-decoration: none;
  border-bottom: 1px dashed rgba(109, 208, 138, 0.5);
}
.wt-txid-val:hover {
  border-bottom-style: solid;
  opacity: 0.85;
}

/* ── Code block ── */
.wt-code-block {
  margin: 8px 0 0;
  background: var(--surface2, #1e1e2e);
  border: 1px solid var(--border, #333);
  border-radius: 4px;
  padding: 8px 10px;
  font-family: monospace;
  font-size: 0.82rem;
  color: #6dd08a;
  overflow-x: auto;
  white-space: pre;
}

/* ── Mnemonic grid ── */
.mnemonic-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 4px 0;
}
.mnemonic-word {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--surface3, #2a2a3e);
  border: 1px solid var(--border, #333);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 0.85rem;
}
.word-num {
  color: var(--text3, #666);
  font-size: 0.75rem;
  min-width: 18px;
}
.word-val {
  color: var(--text, #e0e0e0);
  font-family: monospace;
}

/* ── Form fields ── */
.ws-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ws-field label {
  font-size: 0.8rem;
  color: var(--text2, #999);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.ws-field input,
.ws-field textarea {
  background: var(--input-bg, #12121e);
  border: 1px solid var(--border, #333);
  border-radius: 6px;
  color: var(--text, #e0e0e0);
  padding: 8px 12px;
  font-size: 0.9rem;
  font-family: inherit;
  resize: vertical;
  outline: none;
}
.ws-field input:focus,
.ws-field textarea:focus {
  border-color: var(--accent, #7c6af7);
}

/* ── Warn / error / ok banners ── */
.ws-warn {
  color: #e0a060;
  font-size: 0.85rem;
  padding: 8px 12px;
  background: rgba(224, 160, 96, 0.1);
  border: 1px solid rgba(224, 160, 96, 0.3);
  border-radius: 6px;
}
.ws-error {
  color: var(--red2, #e06060);
  font-size: 0.85rem;
  padding: 6px 10px;
  background: rgba(224, 96, 96, 0.1);
  border-radius: 4px;
}
.ws-ok {
  color: #6dd08a;
  font-size: 0.82rem;
  padding: 4px 8px;
  background: rgba(80, 200, 120, 0.08);
  border-radius: 4px;
}

/* ── Buttons ── */
.ws-btn-row {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 8px;
}
.ws-btn {
  padding: 8px 20px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: opacity 0.15s;
}
.ws-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.ws-btn.primary {
  background: var(--accent, #7c6af7);
  color: #fff;
}
.ws-btn.secondary {
  background: var(--surface3, #2a2a3e);
  color: var(--text, #e0e0e0);
  border: 1px solid var(--border, #444);
}

/* ── Close ── */
.ws-close {
  position: absolute;
  top: 16px;
  right: 16px;
  background: transparent;
  border: none;
  color: var(--text2, #aaa);
  font-size: 1rem;
  cursor: pointer;
  padding: 4px;
  line-height: 1;
}
.ws-close:hover {
  color: var(--text, #e0e0e0);
}

/* ── LLM config form (inline in Configure AI step) ── */
.llm-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.ws-hint {
  font-size: 0.78rem;
  color: var(--text3, #666);
  line-height: 1.45;
  margin-top: 3px;
}
.ws-hint code {
  font-size: 0.76rem;
  background: rgba(255, 255, 255, 0.07);
  padding: 1px 4px;
  border-radius: 3px;
  color: var(--text, #ccc);
}
.ws-field select {
  background: var(--input-bg, #12121e);
  border: 1px solid var(--border, #333);
  border-radius: 6px;
  color: var(--text, #e0e0e0);
  padding: 8px 12px;
  font-size: 0.9rem;
  font-family: inherit;
  outline: none;
  width: 100%;
  cursor: pointer;
}
.ws-field select:focus {
  border-color: var(--accent, #7c6af7);
}
</style>
