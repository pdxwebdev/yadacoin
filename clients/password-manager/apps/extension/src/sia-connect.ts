import { vaultIdFromData, VaultStore, type StoredVault } from "@yadacoin/password-core";
import { createExtensionVaultBackend } from "./shared/vault-backend.js";
import { connectSia } from "./shared/sia.js";

chrome.runtime.connect({ name: "yada-keepalive" });

const status = document.getElementById("status");

function say(text: string) {
  if (status) status.textContent = text;
}

async function main() {
  const store = new VaultStore(createExtensionVaultBackend());
  const entry = await store.getActiveVault();
  const v = entry?.data;
  if (!v) throw new Error("no vault");
  if (!v.siaAppKey) {
    say("Approve Sia in the other window. Leave this one open.");
    v.siaAppKey = await connectSia();
    const id = vaultIdFromData(v);
    await store.updateVaultData(id, v as StoredVault);
    await store.setActiveVaultId(id);
  }
  say("Sia key saved. You can close this tab.");
  await chrome.runtime.sendMessage({ type: "YADA_SIA_KEY_READY", ok: true });
}

main().catch(async (err) => {
  const message = err instanceof Error ? err.message : String(err);
  say(message);
  await chrome.runtime.sendMessage({ type: "YADA_SIA_KEY_READY", ok: false, message });
});
