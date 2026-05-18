// localStorage key constants shared across the app
export const LS_PRIV = "yadacoin_derived_key";
export const LS_CC = "yadacoin_derived_cc";
// Public key (hex, compressed) of the hardware wallet's current active key.
// Mirrors LS_HW_QR.publicKeyHex for fast UI access.
export const LS_HW_PUB = "yadacoin_hw_pub";
// Full parsed QR for the current active key (the one that will sign the next
// unconfirmed rotation tx). JSON-serialised; privBytes stored as hex string.
// On each approval round the active key is replaced with the freshly-scanned
// "next active" QR (K_{n+2}).
export const LS_HW_QR = "yadacoin_hw_qr";
// Wallet mode: "node" (server-managed key), "client" (browser-side BIP39 seed),
// or "hardware" (air-gapped device — every step's key material arrives via QR).
export const LS_WALLET_MODE = "yadacoin_wallet_mode";
export const LS_LLM_PROVIDER = "yadacoin_llm_provider";
export const LS_LLM_MODEL = "yadacoin_llm_model";
export const LS_LLM_API_KEY = "yadacoin_llm_api_key";
export const LS_LLM_OLLAMA_HOST = "yadacoin_llm_ollama_host";
export const LS_LLM_BASE_URL = "yadacoin_llm_base_url";
export const LS_PAYMENT_METHODS = "yadacoin_payment_methods";
export const LS_ACTIVE_AGENT = "yadacoin_active_agent";
export const LS_NODE_URL = "yadacoin_node_url";
export const LS_BOOKING_CREDENTIALS = "yadacoin_booking_credentials";
export const LS_BRAVE_API_KEY = "yadacoin_brave_api_key";

export function getBraveApiKey() {
  return localStorage.getItem(LS_BRAVE_API_KEY) || "";
}

export function saveBraveApiKey(key) {
  localStorage.setItem(LS_BRAVE_API_KEY, key.trim());
}

export function getNodeUrl() {
  return (localStorage.getItem(LS_NODE_URL) || window.location.origin).replace(
    /\/+$/,
    "",
  );
}

export function getLlmSettings() {
  return {
    provider: localStorage.getItem(LS_LLM_PROVIDER) || "ollama",
    model: localStorage.getItem(LS_LLM_MODEL) || "",
    api_key: localStorage.getItem(LS_LLM_API_KEY) || "",
    ollama_host: localStorage.getItem(LS_LLM_OLLAMA_HOST) || "",
    base_url: localStorage.getItem(LS_LLM_BASE_URL) || "",
  };
}

export function saveLlmSettings(s) {
  localStorage.setItem(LS_LLM_PROVIDER, s.provider);
  localStorage.setItem(LS_LLM_MODEL, s.model.trim());
  localStorage.setItem(LS_LLM_API_KEY, s.api_key.trim());
  localStorage.setItem(LS_LLM_OLLAMA_HOST, s.ollama_host.trim());
  localStorage.setItem(LS_LLM_BASE_URL, s.base_url.trim());
}

export function getPaymentMethods() {
  try {
    return JSON.parse(localStorage.getItem(LS_PAYMENT_METHODS) || "[]");
  } catch {
    return [];
  }
}

export function savePaymentMethods(methods) {
  localStorage.setItem(LS_PAYMENT_METHODS, JSON.stringify(methods));
}

export function getDefaultPaymentMethod() {
  const methods = getPaymentMethods();
  return methods.find((m) => m.isDefault) || methods[0] || null;
}

// ── Booking credentials ───────────────────────────────────────────────────────

export function getBookingCredentials() {
  try {
    return JSON.parse(localStorage.getItem(LS_BOOKING_CREDENTIALS) || "[]");
  } catch {
    return [];
  }
}

export function saveBookingCredential(credential) {
  const existing = getBookingCredentials();
  // Deduplicate by credential id
  const deduped = existing.filter((c) => c.id !== credential.id);
  deduped.unshift(credential); // newest first
  localStorage.setItem(LS_BOOKING_CREDENTIALS, JSON.stringify(deduped));
}

export function deleteBookingCredential(credentialId) {
  const updated = getBookingCredentials().filter((c) => c.id !== credentialId);
  localStorage.setItem(LS_BOOKING_CREDENTIALS, JSON.stringify(updated));
}

// ── Wallet mode ───────────────────────────────────────────────────────────────

export function getWalletMode() {
  return localStorage.getItem(LS_WALLET_MODE) || "client";
}

export function setWalletMode(mode) {
  const valid = mode === "client" || mode === "hardware" ? mode : "node";
  localStorage.setItem(LS_WALLET_MODE, valid);
}

export function isClientWallet() {
  return getWalletMode() === "client";
}

export function isHardwareWallet() {
  return getWalletMode() === "hardware";
}

/** Clear all client-side key material and reset to node-wallet mode. */
export function clearClientWallet() {
  localStorage.removeItem(LS_PRIV);
  localStorage.removeItem(LS_CC);
  localStorage.removeItem(LS_HW_PUB);
  localStorage.removeItem(LS_HW_QR);
  localStorage.removeItem(LS_WALLET_MODE);
  // Clear the witness secret so a stale value from a previous wallet session
  // cannot produce a mismatched lookup_key for credential receipt queries.
  localStorage.removeItem("yadacoin_witness_secret");
}

// ── Hardware-wallet active key (full parsed QR) ───────────────────────────────

/**
 * Persist the parsed hardware-wallet QR as the current active key.
 * `parsed` is the object returned by parseHardwareQrPayload() — its privBytes
 * (Uint8Array) is hex-encoded for storage.
 */
export function setHardwareActive(parsed) {
  if (!parsed) return;
  const out = { ...parsed };
  if (parsed.privBytes && parsed.privBytes.length !== undefined) {
    out.privBytes = Array.from(parsed.privBytes)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }
  localStorage.setItem(LS_HW_QR, JSON.stringify(out));
  if (parsed.publicKeyHex) localStorage.setItem(LS_HW_PUB, parsed.publicKeyHex);
}

/** Return the current hardware-wallet active key (parsed QR), or null. */
export function getHardwareActive() {
  const raw = localStorage.getItem(LS_HW_QR);
  if (!raw) return null;
  try {
    const obj = JSON.parse(raw);
    if (typeof obj.privBytes === "string") {
      const hexStr = obj.privBytes;
      const bytes = new Uint8Array(hexStr.length / 2);
      for (let i = 0; i < bytes.length; i++) {
        bytes[i] = parseInt(hexStr.substr(i * 2, 2), 16);
      }
      obj.privBytes = bytes;
    }
    return obj;
  } catch {
    return null;
  }
}
