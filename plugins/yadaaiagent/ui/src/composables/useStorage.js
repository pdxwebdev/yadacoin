// localStorage key constants shared across the app
export const LS_PRIV = "yadacoin_derived_key";
export const LS_CC = "yadacoin_derived_cc";
export const LS_LLM_PROVIDER = "yadacoin_llm_provider";
export const LS_LLM_MODEL = "yadacoin_llm_model";
export const LS_LLM_API_KEY = "yadacoin_llm_api_key";
export const LS_LLM_OLLAMA_HOST = "yadacoin_llm_ollama_host";
export const LS_LLM_BASE_URL = "yadacoin_llm_base_url";
export const LS_PAYMENT_METHODS = "yadacoin_payment_methods";
export const LS_ACTIVE_AGENT = "yadacoin_active_agent";
export const LS_NODE_URL = "yadacoin_node_url";

export function getNodeUrl() {
  return (localStorage.getItem(LS_NODE_URL) || "").replace(/\/+$/, "");
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
