import type { VaultStorageBackend } from "@yadacoin/password-core";
import { createLocalStorageBackend } from "@yadacoin/password-core";

/** Chrome storage.local when available, else localStorage. */
export function createExtensionVaultBackend(): VaultStorageBackend {
  if (typeof chrome !== "undefined" && chrome.storage?.local) {
    return {
      getItem: async (key: string) => {
        const data = await chrome.storage.local.get(key);
        const v = data[key];
        return typeof v === "string" ? v : v != null ? JSON.stringify(v) : null;
      },
      setItem: async (key: string, value: string) => {
        await chrome.storage.local.set({ [key]: value });
      },
      removeItem: async (key: string) => {
        await chrome.storage.local.remove(key);
      },
    };
  }
  return createLocalStorageBackend();
}
