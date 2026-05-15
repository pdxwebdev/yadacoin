/**
 * useRotation.js
 *
 * Shared client-side KEL rotation helper.  Mirrors the local rotation logic
 * in ChatPane.vue but is exported so other flows (e.g. the location-recovery
 * announcement) can broadcast a rotation that carries a custom `relationship`
 * payload without duplicating the rotation/sigchain bookkeeping.
 *
 * `clientRotateWithRelationship` reads K_n from localStorage, derives the
 * next four child keys, builds an unconfirmed (K_n→K_{n+1}) transaction with
 * the supplied relationship + relationship_hash and a confirming
 * (K_{n+1}→K_{n+2}) transaction with an empty relationship, broadcasts both
 * to /transaction, and advances LS_PRIV/LS_CC to K_{n+1}.
 */

import {
  deriveSecurePath,
  hex,
  getPublicKeyHex,
  getP2PKH,
  buildRotationTxn,
} from "./useCrypto.js";
import { LS_PRIV, LS_CC, getNodeUrl } from "./useStorage.js";

/**
 * Rotate the client wallet's KEL by one step, embedding a structured
 * `relationship` payload on the unconfirmed transaction.
 *
 * The caller supplies BOTH the relationship value (string OR dict — the
 * latter for class-typed announcements like RecoveryAnnouncement) AND the
 * matching relationship_hash.  We do not recompute the hash here because
 * for class-typed relationships the hash is sha256(<class>.to_string()),
 * not sha256(JSON.stringify(<dict>)).
 *
 * @param {string} sf - second factor used by deriveSecurePath
 * @param {string|object} relationship - on-wire relationship value
 * @param {string} relationshipHash - hex sha256 over to_string() preimage
 * @returns {Promise<{ transactionId: string }>}
 */
export async function clientRotateWithRelationship(
  sf,
  relationship,
  relationshipHash,
) {
  const privHex = localStorage.getItem(LS_PRIV);
  const ccHex = localStorage.getItem(LS_CC);
  if (!privHex || !ccHex) {
    throw new Error("Client wallet not initialised (missing LS_PRIV/LS_CC).");
  }
  const privBytes = hex.toBytes(privHex);
  const ccBytes = hex.toBytes(ccHex);

  const child = deriveSecurePath(privBytes, ccBytes, sf);
  const gc1 = deriveSecurePath(child.priv, child.cc, sf);
  const gc2 = deriveSecurePath(gc1.priv, gc1.cc, sf);

  const currentPubHex = getPublicKeyHex(privBytes);
  const childPubHex = getPublicKeyHex(child.priv);
  const gc1PubHex = getPublicKeyHex(gc1.priv);
  const gc2PubHex = getPublicKeyHex(gc2.priv);

  const currentPkh = getP2PKH(hex.toBytes(currentPubHex));
  const childPkh = getP2PKH(hex.toBytes(childPubHex));
  const gc1Pkh = getP2PKH(hex.toBytes(gc1PubHex));
  const gc2Pkh = getP2PKH(hex.toBytes(gc2PubHex));

  // Resolve prev_public_key_hash from the existing on-chain/mempool KEL.
  const kelRes = await fetch(
    getNodeUrl() +
      "/key-event-log?username_signature=asdf&public_key=" +
      encodeURIComponent(currentPubHex),
  );
  const kelData = await kelRes.json();
  if (!kelRes.ok) throw new Error(kelData.message || String(kelRes.status));
  const kel = kelData.key_event_log || [];
  const prevPublicKeyHash =
    kel.length > 0 ? (kel[kel.length - 1].public_key_hash ?? "") : "";

  // localStorage may still hold K_{n-1} immediately after inception.  Detect
  // that and silently advance before signing.
  if (prevPublicKeyHash === currentPkh) {
    localStorage.setItem(LS_PRIV, hex.fromBytes(child.priv));
    localStorage.setItem(LS_CC, hex.fromBytes(child.cc));
    return clientRotateWithRelationship(sf, relationship, relationshipHash);
  }

  const relValue = relationship ?? "";
  const relHashHex = relationshipHash || "";

  const txnTime = Math.floor(Date.now() / 1000);

  const unconfirmedTxn = await buildRotationTxn({
    signerPrivBytes: privBytes,
    publicKeyHex: currentPubHex,
    prerotatedPkh: childPkh,
    twicePrerotatedPkh: gc1Pkh,
    publicKeyHash: currentPkh,
    prevPublicKeyHash,
    relationship: relValue,
    relationshipHash: relHashHex,
    txnTime,
    inputs: [],
    outputs: [{ to: childPkh, value: 0.0 }],
  });

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

  const bcastRes = await fetch(
    getNodeUrl() + "/transaction?username_signature=1",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify([unconfirmedTxn, confirmingTxn]),
    },
  );
  const bcastData = await bcastRes.json();
  if (!bcastRes.ok || bcastData.status === false) {
    throw new Error(bcastData.message || String(bcastRes.status));
  }

  // Advance LS to the new active key (K_{n+1} = `child`).
  localStorage.setItem(LS_PRIV, hex.fromBytes(child.priv));
  localStorage.setItem(LS_CC, hex.fromBytes(child.cc));

  return { transactionId: unconfirmedTxn.id };
}
