/**
 * Multi-vault storage for the Yada Password client apps.
 *
 * Each vault is keyed by its K0 address (deterministic from mnemonic +
 * second factor). A small registry tracks all vault IDs and which one is
 * active so the app opens on the last-used vault.
 *
 * The store is agnostic to the underlying key-value backend — each app
 * supplies a {@link VaultStorageBackend} (Chrome storage, Capacitor
 * Preferences, or localStorage).
 */
import { unlockIdentity } from "./vault.js";

export interface VaultStorageBackend {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

export interface StoredSite {
  siteId: string;
  branchPeer: string;
  counter: number;
  tipPrevPkh: string;
  branchInceptionPkh: string;
  tipPriv: string;
  tipCc: string;
  currentPassword: string;
  nextPassword: string;
  kp0Priv: string;
  kp0Cc: string;
  androidPackage?: string;
  androidCertSha256?: string[];
}

export interface StoredVault {
  nodeUrl?: string;
  mnemonic: string;
  secondFactor: string;
  username: string;
  identityType: string;
  mainDepth: number;
  tipPrevPkh: string;
  inceptionDone: boolean;
  sites: Record<string, StoredSite>;
  theme?: {
    presetId: string;
    mode: "light" | "dark" | "system";
    primary: string;
    themeUrl: string;
  };
}

export interface VaultEntry {
  id: string;
  name: string;
  data: StoredVault;
  createdAt: number;
  updatedAt: number;
}

interface VaultRegistry {
  activeVaultId: string | null;
  vaultIds: string[];
}

const REGISTRY_KEY = "yadaVaultRegistry";
const VAULT_PREFIX = "yadaVault_";

/** Derive a human-friendly display name from vault data. */
export function defaultVaultName(data: StoredVault): string {
  const username = data.username?.trim();
  if (username) return username;
  return "Vault " + new Date().toLocaleDateString();
}

/** Derive a stable vault ID (K0 address) from vault data. */
export function vaultIdFromData(data: StoredVault): string {
  const id = unlockIdentity(
    data.mnemonic,
    data.secondFactor,
    data.username,
    {
      identityType: data.identityType,
      mainDepth: data.mainDepth,
      tipPrevPkh: data.tipPrevPkh,
    }
  ).k0.address;
  return id;
}

/** Adapter that wraps browser localStorage in the async backend interface. */
export function createLocalStorageBackend(): VaultStorageBackend {
  return {
    getItem: (key: string) => Promise.resolve(localStorage.getItem(key)),
    setItem: (key: string, value: string) => {
      localStorage.setItem(key, value);
      return Promise.resolve();
    },
    removeItem: (key: string) => {
      localStorage.removeItem(key);
      return Promise.resolve();
    },
  };
}

/**
 * Multi-vault store backed by any {@link VaultStorageBackend}.
 *
 * Vaults are persisted individually under `yadaVault_<id>` and tracked in a
 * registry (`yadaVaultRegistry`) that also records the active vault ID.
 */
export class VaultStore {
  private readonly registryKey = REGISTRY_KEY;

  constructor(private readonly backend: VaultStorageBackend) {}

  private vaultKey(id: string): string {
    return `${VAULT_PREFIX}${id}`;
  }

  async listVaults(): Promise<VaultEntry[]> {
    const registry = await this.getRegistry();
    const entries: VaultEntry[] = [];
    for (const id of registry.vaultIds) {
      const entry = await this.getVault(id);
      if (entry) entries.push(entry);
    }
    return entries.sort((a, b) => b.updatedAt - a.updatedAt);
  }

  async getVault(id: string): Promise<VaultEntry | null> {
    const raw = await this.backend.getItem(this.vaultKey(id));
    if (!raw) return null;
    try {
      const entry = JSON.parse(raw) as VaultEntry;
      if (!entry.id || !entry.data || !entry.createdAt || !entry.updatedAt) {
        return null;
      }
      return entry;
    } catch {
      return null;
    }
  }

  async saveVault(
    id: string,
    data: StoredVault,
    opts?: { name?: string }
  ): Promise<VaultEntry> {
    const now = Date.now();
    const existing = await this.getVault(id);
    const entry: VaultEntry = {
      id,
      name: opts?.name ?? existing?.name ?? defaultVaultName(data),
      data,
      createdAt: existing?.createdAt ?? now,
      updatedAt: now,
    };
    await this.backend.setItem(this.vaultKey(id), JSON.stringify(entry));
    await this.addToRegistry(id);
    return entry;
  }

  /** Update the data of an existing vault, preserving its name and createdAt. */
  async updateVaultData(id: string, data: StoredVault): Promise<VaultEntry> {
    const existing = await this.getVault(id);
    if (!existing) {
      return this.saveVault(id, data);
    }
    return this.saveVault(id, data, { name: existing.name });
  }

  async deleteVault(id: string): Promise<void> {
    await this.backend.removeItem(this.vaultKey(id));
    const registry = await this.getRegistry();
    const filtered = registry.vaultIds.filter((v) => v !== id);
    let activeId = registry.activeVaultId;
    if (activeId === id) {
      activeId = filtered[0] ?? null;
    }
    await this.saveRegistry({ activeVaultId: activeId, vaultIds: filtered });
  }

  async getActiveVaultId(): Promise<string | null> {
    return (await this.getRegistry()).activeVaultId;
  }

  async setActiveVaultId(id: string | null): Promise<void> {
    const registry = await this.getRegistry();
    if (id && !registry.vaultIds.includes(id)) {
      registry.vaultIds.push(id);
    }
    registry.activeVaultId = id;
    await this.saveRegistry(registry);
  }

  async getActiveVault(): Promise<VaultEntry | null> {
    const activeId = await this.getActiveVaultId();
    if (!activeId) return null;
    return this.getVault(activeId);
  }

  /**
   * Migrate a legacy single-vault entry from `legacyKey` into the multi-vault
   * store. If the active vault is unset, the migrated vault becomes active.
   * Returns the migrated entry, or null if no legacy data was found.
   */
  async migrateLegacy(legacyKey: string): Promise<VaultEntry | null> {
    const raw = await this.backend.getItem(legacyKey);
    if (!raw) return null;
    let data: StoredVault;
    try {
      data = JSON.parse(raw) as StoredVault;
    } catch {
      return null;
    }
    const id = vaultIdFromData(data);
    const entry = await this.saveVault(id, data, {
      name: data.username || defaultVaultName(data),
    });
    const activeId = await this.getActiveVaultId();
    if (!activeId) {
      await this.setActiveVaultId(id);
    }
    await this.backend.removeItem(legacyKey);
    return entry;
  }

  private async getRegistry(): Promise<VaultRegistry> {
    const raw = await this.backend.getItem(this.registryKey);
    if (!raw) return { activeVaultId: null, vaultIds: [] };
    try {
      return JSON.parse(raw) as VaultRegistry;
    } catch {
      return { activeVaultId: null, vaultIds: [] };
    }
  }

  private async saveRegistry(reg: VaultRegistry): Promise<void> {
    await this.backend.setItem(this.registryKey, JSON.stringify(reg));
  }

  private async addToRegistry(id: string): Promise<void> {
    const registry = await this.getRegistry();
    if (!registry.vaultIds.includes(id)) {
      registry.vaultIds.push(id);
    }
    await this.saveRegistry(registry);
  }
}

/** Legacy storage keys used by single-vault app versions. */
export const LEGACY_KEYS = {
  extension: "yadaPasswordVault",
  native: "yadaPasswordNativeVault",
  mobile: "yadaPasswordMobileVault",
};
