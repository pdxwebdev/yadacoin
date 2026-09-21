import assert from "node:assert/strict";
import { test } from "node:test";
import {
  createVaultSeed,
  defaultVaultName,
  unlockIdentity,
  VaultStore,
  vaultIdFromData,
} from "../dist/index.js";

function memoryBackend() {
  const map = new Map();
  return {
    getItem: async (key) => (map.has(key) ? map.get(key) : null),
    setItem: async (key, value) => {
      map.set(key, value);
    },
    removeItem: async (key) => {
      map.delete(key);
    },
    _map: map,
  };
}

function sampleVault(username = "alice") {
  const mnemonic = createVaultSeed(128);
  const secondFactor = "test-sf";
  const id = unlockIdentity(mnemonic, secondFactor, username);
  return {
    mnemonic,
    secondFactor,
    username,
    identityType: "social",
    mainDepth: 0,
    tipPrevPkh: "",
    inceptionDone: false,
    sites: {},
    _k0: id.k0.address,
  };
}

test("vaultIdFromData matches K0 address", () => {
  const v = sampleVault();
  assert.equal(vaultIdFromData(v), v._k0);
});

test("defaultVaultName uses username", () => {
  assert.equal(defaultVaultName(sampleVault("bob")), "bob");
});

test("VaultStore save, list, active, switch, delete", async () => {
  const backend = memoryBackend();
  const store = new VaultStore(backend);

  const a = sampleVault("alice");
  const b = sampleVault("bob");
  const idA = vaultIdFromData(a);
  const idB = vaultIdFromData(b);

  await store.saveVault(idA, a, { name: "alice" });
  await store.setActiveVaultId(idA);
  await store.saveVault(idB, b, { name: "bob" });

  const list = await store.listVaults();
  assert.equal(list.length, 2);

  let active = await store.getActiveVault();
  assert.equal(active?.id, idA);
  assert.equal(active?.data.username, "alice");

  await store.setActiveVaultId(idB);
  active = await store.getActiveVault();
  assert.equal(active?.id, idB);
  assert.equal(active?.data.username, "bob");

  await store.deleteVault(idB);
  active = await store.getActiveVault();
  assert.equal(active?.id, idA);
  assert.equal((await store.listVaults()).length, 1);
});

test("migrateLegacy imports single vault and sets active", async () => {
  const backend = memoryBackend();
  const v = sampleVault("carol");
  await backend.setItem("legacyKey", JSON.stringify(v));
  const store = new VaultStore(backend);
  const entry = await store.migrateLegacy("legacyKey");
  assert.ok(entry);
  assert.equal(entry.data.username, "carol");
  assert.equal(await store.getActiveVaultId(), entry.id);
  assert.equal(await backend.getItem("legacyKey"), null);
});
