/**
 * MV3 service worker — vault sign-in/rotate for harness pages via content script.
 */
import {
  bytesToHex,
  hashPassword,
  hexToBytes,
  LEGACY_KEYS,
  materialFromPrivCc,
  registerSite,
  resyncSiteFromNode,
  resyncVaultFromNode,
  rotateSitePassword,
  syncInceptionFromNode,
  unlockIdentity,
  vaultIdFromData,
  VaultStore,
  type SiteRegistration,
  type StoredSite,
  type StoredVault,
  type VaultIdentity,
} from "@yadacoin/password-core";
import { createExtensionVaultBackend } from "../shared/vault-backend.js";

const SETTINGS_KEY = "yadaPasswordSettings";
const store = new VaultStore(createExtensionVaultBackend());
let migrated = false;

async function ensureMigrated(): Promise<void> {
  if (migrated) return;
  await store.migrateLegacy(LEGACY_KEYS.extension);
  migrated = true;
}

function storeSite(site: SiteRegistration): StoredSite {
  return {
    siteId: site.siteId,
    branchPeer: site.branchPeer,
    counter: site.counter,
    tipPrevPkh: site.tipPrevPkh,
    branchInceptionPkh: site.branchInceptionPkh,
    tipPriv: bytesToHex(site.tip.privateKey),
    tipCc: bytesToHex(site.tip.chainCode),
    currentPassword: site.currentPassword,
    nextPassword: site.nextPassword,
    kp0Priv: bytesToHex(site.kp0.privateKey),
    kp0Cc: bytesToHex(site.kp0.chainCode),
  };
}

function siteFromStored(s: StoredSite): SiteRegistration {
  return {
    siteId: s.siteId,
    branchPeer: s.branchPeer,
    kp0: materialFromPrivCc(hexToBytes(s.kp0Priv), hexToBytes(s.kp0Cc)),
    tip: materialFromPrivCc(hexToBytes(s.tipPriv), hexToBytes(s.tipCc)),
    counter: s.counter,
    tipPrevPkh: s.tipPrevPkh,
    currentPassword: s.currentPassword,
    nextPassword: s.nextPassword,
    branchInceptionPkh: s.branchInceptionPkh,
  };
}

async function loadVault(): Promise<StoredVault | null> {
  await ensureMigrated();
  const entry = await store.getActiveVault();
  return entry?.data ?? null;
}

async function saveVault(v: StoredVault): Promise<void> {
  await ensureMigrated();
  const id = vaultIdFromData(v);
  await store.updateVaultData(id, v);
  await store.setActiveVaultId(id);
}

async function nodeUrl(): Promise<string> {
  const data = await chrome.storage.sync.get(SETTINGS_KEY);
  const s = (data[SETTINGS_KEY] || {}) as { nodeUrl?: string };
  return (s.nodeUrl || "").replace(/\/+$/, "");
}

async function ensureIncepted(
  v: StoredVault,
  baseUrl: string
): Promise<StoredVault> {
  if (!baseUrl) return v;
  try {
    const identity: VaultIdentity = unlockIdentity(
      v.mnemonic,
      v.secondFactor,
      v.username,
      {
        identityType: v.identityType,
        mainDepth: v.mainDepth,
        tipPrevPkh: v.tipPrevPkh,
      }
    );
    const { identity: nextId, inceptionDone } = await syncInceptionFromNode(
      { baseUrl },
      identity
    );
    if (!inceptionDone) return v;
    const next: StoredVault = {
      ...v,
      inceptionDone: true,
      mainDepth: nextId.mainDepth,
      tipPrevPkh: nextId.tipPrevPkh,
    };
    if (
      next.inceptionDone !== v.inceptionDone ||
      next.mainDepth !== v.mainDepth ||
      next.tipPrevPkh !== v.tipPrevPkh
    ) {
      await saveVault(next);
    }
    return next;
  } catch {
    return v;
  }
}

chrome.runtime.onInstalled.addListener(() => {
  console.info("Yada Password extension installed");
  void ensureMigrated();
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  if (message.type === "YADA_REGISTER_SITE") {
    void (async () => {
      try {
        const origin = String(message.origin || "").toLowerCase();
        if (!origin.startsWith("http")) {
          sendResponse({ ok: false, message: "invalid origin" });
          return;
        }
        const baseUrl = await nodeUrl();
        if (!baseUrl) {
          sendResponse({ ok: false, message: "set Node URL in extension options" });
          return;
        }
        let v = await loadVault();
        if (!v) {
          sendResponse({ ok: false, message: "no vault" });
          return;
        }
        v = await ensureIncepted(v, baseUrl);
        if (!v.inceptionDone) {
          sendResponse({ ok: false, message: "vault not incepted" });
          return;
        }
        const identity: VaultIdentity = unlockIdentity(
          v.mnemonic,
          v.secondFactor,
          v.username,
          {
            identityType: v.identityType,
            mainDepth: v.mainDepth,
            tipPrevPkh: v.tipPrevPkh,
          }
        );
        const result = await registerSite({ baseUrl }, identity, origin);
        v.mainDepth = result.identity.mainDepth;
        v.tipPrevPkh = result.identity.tipPrevPkh;
        v.sites[result.site.branchPeer] = storeSite(result.site);
        await saveVault(v);
        sendResponse({
          ok: true,
          registered: true,
          counter: result.site.counter,
          password: result.site.currentPassword,
          passwordHash: hashPassword(result.site.currentPassword),
          nextPasswordHash: hashPassword(result.site.nextPassword),
          message: `registered · counter ${result.site.counter}`,
        });
      } catch (e) {
        sendResponse({
          ok: false,
          message: e instanceof Error ? e.message : String(e),
        });
      }
    })();
    return true;
  }

  if (message.type === "YADA_SIGNIN_ROTATE") {
    void (async () => {
      try {
        const origin = String(message.origin || "").toLowerCase();
        if (!origin.startsWith("http")) {
          sendResponse({ ok: false, message: "invalid origin" });
          return;
        }
        const baseUrl = await nodeUrl();
        if (!baseUrl) {
          sendResponse({
            ok: false,
            message: "set Node URL in extension options",
          });
          return;
        }
        let v = await loadVault();
        if (!v) {
          sendResponse({ ok: false, message: "no vault" });
          return;
        }
        v = await ensureIncepted(v, baseUrl);
        if (!v.inceptionDone) {
          sendResponse({ ok: false, message: "vault not incepted" });
          return;
        }
        const identity: VaultIdentity = unlockIdentity(
          v.mnemonic,
          v.secondFactor,
          v.username,
          {
            identityType: v.identityType,
            mainDepth: v.mainDepth,
            tipPrevPkh: v.tipPrevPkh,
          }
        );
        let stored = v.sites[origin];
        let site: SiteRegistration;
        if (!stored) {
          site = await resyncSiteFromNode({ baseUrl }, identity, origin);
        } else {
          site = siteFromStored(stored);
        }
        const result = await rotateSitePassword({ baseUrl }, identity, site);
        v.sites[origin] = storeSite(result.site);
        await saveVault(v);
        sendResponse({
          ok: true,
          authenticated: true,
          rotated: true,
          counter: result.site.counter,
          password: result.site.currentPassword,
          passwordHash: hashPassword(result.site.currentPassword),
          nextPasswordHash: hashPassword(result.site.nextPassword),
          message: `signed in & rotated to counter ${result.site.counter}`,
        });
      } catch (e) {
        sendResponse({
          ok: false,
          message: e instanceof Error ? e.message : String(e),
        });
      }
    })();
    return true;
  }

  if (message.type === "YADA_RESYNC_SITE") {
    void (async () => {
      try {
        const origin = String(message.origin || "").toLowerCase();
        if (!origin.startsWith("http")) {
          sendResponse({ ok: false, message: "invalid origin" });
          return;
        }
        const baseUrl = await nodeUrl();
        if (!baseUrl) {
          sendResponse({ ok: false, message: "set Node URL in extension options" });
          return;
        }
        let v = await loadVault();
        if (!v) {
          sendResponse({ ok: false, message: "no vault" });
          return;
        }
        v = await ensureIncepted(v, baseUrl);
        if (!v.inceptionDone) {
          sendResponse({ ok: false, message: "vault not incepted" });
          return;
        }
        const identity: VaultIdentity = unlockIdentity(
          v.mnemonic,
          v.secondFactor,
          v.username,
          {
            identityType: v.identityType,
            mainDepth: v.mainDepth,
            tipPrevPkh: v.tipPrevPkh,
          }
        );
        const sites: Record<string, SiteRegistration> = {};
        for (const [k, s] of Object.entries(v.sites || {})) {
          sites[k] = siteFromStored(s);
        }
        const full = await resyncVaultFromNode({ baseUrl }, identity, sites);
        let site = full.sites[origin];
        if (!site) {
          site = await resyncSiteFromNode({ baseUrl }, full.identity, origin);
          full.sites[origin] = site;
        }
        const nextSites: Record<string, StoredSite> = {};
        for (const [k, s] of Object.entries(full.sites)) {
          nextSites[k] = storeSite(s);
        }
        const nextVault: StoredVault = {
          ...v,
          mainDepth: full.identity.mainDepth,
          tipPrevPkh: full.identity.tipPrevPkh,
          inceptionDone: full.kelDepth > 0,
          sites: nextSites,
        };
        await saveVault(nextVault);
        sendResponse({
          ok: true,
          resynced: true,
          counter: site.counter,
          message: `resynced · counter ${site.counter}`,
        });
      } catch (e) {
        sendResponse({
          ok: false,
          message: e instanceof Error ? e.message : String(e),
        });
      }
    })();
    return true;
  }

  if (message.type === "YADA_SITE_STATUS") {
    void (async () => {
      const origin = String(message.origin || "").toLowerCase();
      const v = await loadVault();
      const stored = v?.sites?.[origin];
      sendResponse({
        ok: true,
        registered: !!stored,
        counter: stored?.counter ?? null,
      });
    })();
    return true;
  }

  return false;
});
