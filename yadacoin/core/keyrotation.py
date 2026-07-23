"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Server-side BIP32-style hardened key derivation and node KEL lifecycle manager.

Provides:
  - derive_secure_path()       — pure function used by this module and
                                 plugins/keyrotation/handlers.py
  - NodeKeyRotationManager     — enforces KEL lifecycle at startup and runs the
                                 periodic background checker

Startup contract
----------------
On every node start the manager:

1. Requires ``seed`` in config.json AND ``SECOND_FACTOR`` environment variable.
   If either is absent the node refuses to start.

2. Derives the inception signing key K0 = derive(BIP32(seed), SECOND_FACTOR).

3. Checks for a KEL inception on-chain or in the mempool for K0.
   Auto-creates one if none exists.

Periodic contract
-----------------
The ``background_kel_checker`` coroutine polls for the inception being confirmed
on-chain and then sets ``config.kel_*`` signing key.

Off-chain auth ratchet (Phase 1)
---------------------------------
P2P challenge signatures use an off-chain ratchet derived from the on-chain
anchor key K_n.  Each auth event:
  1. Derives the next ratchet key K_{n+i} from K_{n+i-1}
  2. Stores a self-certifying entry in ``key_event_log`` (main DB):
       { counter, anchor_public_key, public_key, prev_public_key,
         certification, purpose, timestamp }
  3. Returns K_{n+i} for the caller to sign with

Verifiers fetch GET /kel-offchain-log to walk the chain from the on-chain
anchor to the current signing key without knowing SECOND_FACTOR.

Every OFFCHAIN_ANCHOR_INTERVAL auth events the manager automatically queues a
new on-chain UNCONFIRMED+CONFIRMING re-anchor pair that jumps the on-chain
KEL forward by OFFCHAIN_ANCHOR_INTERVAL steps.
"""

import base64
import hashlib
import hmac as _hmac
import os
import struct
import sys
import time
from dataclasses import dataclass

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey as _CoincurvePrivateKey
from coincurve._libsecp256k1 import ffi as _ffi
from coincurve.keys import PrivateKey

from yadacoin.core.config import Config
from yadacoin.core.keyeventlog import KeyEventLog
from yadacoin.enums.peertypes import PEER_TYPES

# ---------------------------------------------------------------------------
# Re-anchor triplet — produced by _queue_reanchor for the block mining path.
# Collects the three transactions (unconfirmed, confirming, coinbase) that
# together form the on-chain KEL anchor step, plus the key material needed
# to sign the coinbase and populate its KEL fields.
# ---------------------------------------------------------------------------


@dataclass
class ReanchorTriplet:
    """On-chain KEL re-anchor package built by ``_queue_reanchor`` when mining."""

    unconfirmed: object  # Transaction
    confirming: object  # Transaction
    signer_private_key: str  # hex — key that signs the coinbase (== kn private)
    signer_public_key: str  # hex — block public key (== kn public)
    coinbase_prerotated: str  # address — coinbase's prerotated_key_hash
    coinbase_twice_prerotated: str  # address — coinbase's twice_prerotated_key_hash
    coinbase_public_key_hash: str  # address — coinbase's public_key_hash
    coinbase_prev_public_key_hash: str  # address — coinbase's prev_public_key_hash


# ---------------------------------------------------------------------------
# BIP32-style hardened derivation helpers — server-side Python equivalent of
# deriveSecurePath() from templates/key_rotation.html.
# ---------------------------------------------------------------------------

_CURVE_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def _bip32_hardened_child(
    parent_priv: bytes, parent_chain_code: bytes, index: int
) -> dict:
    """HMAC-SHA512(key=chainCode, data=0x00||privKey||hardIndex_BE4)
    child_priv = (IL + parent_priv) mod CURVE_ORDER
    """
    hard_index = (0x80000000 + index) & 0xFFFFFFFF
    data = b"\x00" + parent_priv + struct.pack(">I", hard_index)
    I = _hmac.new(parent_chain_code, data, hashlib.sha512).digest()
    IL, IR = I[:32], I[32:]
    child_int = (
        int.from_bytes(IL, "big") + int.from_bytes(parent_priv, "big")
    ) % _CURVE_ORDER
    return {"private_key": child_int.to_bytes(32, "big"), "chain_code": IR}


def _derive_index(factor: str, level: int) -> int:
    """index = SHA256(factor + str(level)) mod 2147483647"""
    data = (factor + str(level)).encode("utf-8")
    h = int.from_bytes(hashlib.sha256(data).digest(), "big")
    return h % 2147483647


def derive_secure_path(
    priv_key_bytes: bytes, chain_code: bytes, second_factor: str
) -> dict:
    """Derive a key via 4 sequential hardened BIP32 children.

    Exact Python equivalent of deriveSecurePath() in key_rotation.html.
    Returns a dict with keys 'private_key' (bytes, 32) and 'chain_code' (bytes, 32).
    """
    cur = {"private_key": priv_key_bytes, "chain_code": chain_code}
    for level in range(4):
        idx = _derive_index(second_factor, level)
        cur = _bip32_hardened_child(cur["private_key"], cur["chain_code"], idx)
    return cur


# ---------------------------------------------------------------------------
# Config persistence helper
# ---------------------------------------------------------------------------


def _read_second_factor() -> str:
    """Resolve SECOND_FACTOR from file or env var.

    Priority: SECOND_FACTOR_FILE > SECOND_FACTOR env var.
    Returns an empty string if neither is set (caller decides how to handle it).
    """
    sf_file = os.environ.get("SECOND_FACTOR_FILE", "")
    if sf_file:
        try:
            with open(sf_file, "r") as _f:
                return _f.read().strip()
        except Exception:
            return ""
    return os.environ.get("SECOND_FACTOR", "")


# ---------------------------------------------------------------------------
# Node KEL lifecycle manager
# ---------------------------------------------------------------------------


class NodeKeyRotationManager:
    """Manages the mandatory KEL lifecycle for a running node.

    Usage in app.py:
        1. Call ``NodeKeyRotationManager.startup_check(config)`` (via run_sync)
           after Mongo is initialised.
        2. Register ``manager.background_kel_checker`` as a PeriodicCallback.
    """

    # How often (seconds) to poll for the inception being confirmed.
    POLL_INTERVAL_SECONDS = 30

    # Number of off-chain auth events before an on-chain re-anchor is queued.
    OFFCHAIN_ANCHOR_INTERVAL = 100

    def __init__(self, config):
        self.config = config
        self._inception_txn_id = None  # set by startup_check or _create_inception
        self._inception_complete = False  # True once inception is confirmed on-chain
        # {address: {"utxos": [...], "block_height": int, "block_hash": str}}
        self._kel_balance_cache: dict = {}
        # Cached after first derivation so background_kel_checker avoids repeating it
        self._k0: dict | None = None
        self._second_factor: str = ""
        # Off-chain auth ratchet state.
        # _auth_ratchet_key: the last key written to key_event_log (init from K_n)
        self._auth_ratchet_key: dict | None = None  # {private_key, chain_code}
        self._auth_ratchet_pub: str = ""  # hex pub key of current ratchet tip
        self._auth_counter: int = 0  # off-chain events since last re-anchor
        # prev_public_key_hash for the next ratchet transaction (set when KEL is activated)
        self._auth_ratchet_prev_pkh: str = ""
        # Mutex ensuring advance_auth_ratchet is never entered concurrently.
        # Without this, two coroutines could both read self._auth_ratchet_key
        # before either writes the next key back, signing two different messages
        # with the same key.

        # Per-peer off-chain auth ratchet branches.
        #
        # Instead of a single global off-chain chain shared by every P2P peer
        # (which forces every handshake to replay/send the *entire* auth
        # history — including history that has nothing to do with the peer on
        # the other end of this specific connection — each peer relationship
        # gets its own independent branch, keyed by the peer's
        # ``username_signature`` (from their own K0/identity announcement).
        #
        # Branch root: Kp0 = derive_secure_path(K0, SECOND_FACTOR + peer_username_signature)
        #
        # Kp0 is deterministic and reproducible from K0 alone (no extra state
        # to persist beyond key_event_log), and is unique per peer since
        # username_signature is unique per identity.  The transition from K0
        # to Kp0 is recorded as an explicit signed KEL "bridge" entry — a
        # normal rotation transaction (public_key_hash=K0 address,
        # prerotated_key_hash=Kp0 address) signed by K0 — so any peer holding
        # our on-chain K0 (from our identity announcement) can verify the
        # branch is authorized by our real identity, without ever seeing the
        # off-chain history we use with anyone else.
        #
        # {peer_username_signature: {"ratchet_key", "ratchet_pub", "counter",
        #                             "prev_pkh", "branch_inception_public_key_hash", "inception_public_key_hash"}}
        self._peer_branches: dict = {}

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    async def startup_check(self):
        """Run mandatory KEL startup checks.

        Called via ``IOLoop.run_sync`` from ``init_config_properties``.
        Exits the process with a fatal message if prerequisites are not met.
        """
        config = self.config

        # 1. Require seed
        seed = getattr(config, "seed", "") or ""
        if not seed:
            _fatal(
                "\n"
                "═══════════════════════════════════════════════════════════════\n"
                "  FATAL: config.json is missing the 'seed' (BIP39 mnemonic).\n"
                "\n"
                "  Your node private key may have been compromised.\n"
                "  Please transfer ALL funds from address {} to a new wallet\n"
                "  before restarting, then add a 'seed' to config.json.\n"
                "═══════════════════════════════════════════════════════════════\n".format(
                    getattr(config, "address", "<unknown>")
                )
            )

        # 1b. Require non-empty username
        username = getattr(config, "username", "") or ""
        if not username.strip():
            _fatal(
                "\n"
                "═══════════════════════════════════════════════════════════════\n"
                "  FATAL: config.json is missing a 'username'.\n"
                "\n"
                "  Every node must have a unique username so that its identity\n"
                "  can be announced on-chain via the KEL inception transaction.\n"
                "  Add a non-blank 'username' to config.json and restart.\n"
                "═══════════════════════════════════════════════════════════════\n"
            )

        # 2. Require SECOND_FACTOR — via env var or file path
        #
        # Priority:
        #   1. SECOND_FACTOR_FILE  — path to a file containing the secret
        #                            (Docker secrets, Kubernetes, systemd credentials)
        #   2. SECOND_FACTOR       — plain environment variable
        #
        second_factor = ""
        sf_file = os.environ.get("SECOND_FACTOR_FILE", "")
        if sf_file:
            try:
                with open(sf_file, "r") as _f:
                    second_factor = _f.read().strip()
            except Exception as exc:
                _fatal(
                    "\n"
                    "═══════════════════════════════════════════════════════════════\n"
                    "  FATAL: could not read SECOND_FACTOR_FILE '{}':\n"
                    "  {}\n"
                    "═══════════════════════════════════════════════════════════════\n".format(
                        sf_file, exc
                    )
                )
        else:
            second_factor = os.environ.get("SECOND_FACTOR", "")

        if not second_factor:
            _fatal(
                "\n"
                "═══════════════════════════════════════════════════════════════\n"
                "  FATAL: no second factor provided.\n"
                "\n"
                "  Set one of the following before starting the node:\n"
                "\n"
                "    SECOND_FACTOR_FILE=/path/to/secret/file  (recommended)\n"
                "    SECOND_FACTOR=your_secret                 (env var fallback)\n"
                "\n"
                "  SECOND_FACTOR_FILE is preferred — it keeps the secret out of\n"
                "  the process environment, docker inspect, and shell history.\n"
                "  Use a file with mode 400 owned by the node's service account.\n"
                "═══════════════════════════════════════════════════════════════\n"
            )

        # 3. Derive K0 — inception signing key
        try:
            from bip32utils import BIP32Key
            from mnemonic import Mnemonic

            mn = Mnemonic("english")
            entropy = mn.to_entropy(seed)
            bip32_root = BIP32Key.fromEntropy(entropy)
            root_priv = bip32_root.PrivateKey()
            root_cc = bip32_root.ChainCode()
        except Exception as exc:
            _fatal("FATAL: could not derive root BIP32 key from seed: {}".format(exc))

        k0 = derive_secure_path(root_priv, root_cc, second_factor)
        k0_priv_obj = _CoincurvePrivateKey(k0["private_key"])
        k0_pub_bytes = k0_priv_obj.public_key.format(compressed=True)
        k0_pub_hex = k0_pub_bytes.hex()

        # Cache for reuse in background_kel_checker
        self._k0 = k0
        self._second_factor = second_factor

        # 3b. If a username-based identity announcement already exists on-chain,
        #     verify its public_key matches K0.  A mismatch means the
        #     seed/SECOND_FACTOR combination does not belong to this node.
        username = getattr(config, "username", "") or ""
        if username.strip():
            from yadacoin.core.identityannouncement import IdentityAnnouncement

            existing_identity = await IdentityAnnouncement.get_by_username(
                username, include_mempool=True
            )
            if existing_identity and existing_identity.get("public_key") != k0_pub_hex:
                _fatal(
                    "\n"
                    "═══════════════════════════════════════════════════════════════\n"
                    "  FATAL: on-chain identity for username '{}' has\n"
                    "  public_key {} but derived K0 is {}.\n"
                    "\n"
                    "  The seed + SECOND_FACTOR combination does not match\n"
                    "  the on-chain identity announcement.  Verify your\n"
                    "  credentials or re-initialise.\n"
                    "═══════════════════════════════════════════════════════════════\n".format(
                        username, existing_identity["public_key"], k0_pub_hex
                    )
                )
            elif existing_identity:
                config.app_log.info(
                    "NodeKeyRotationManager: on-chain identity for '%s' verified (K0=%s).",
                    username,
                    k0_pub_hex,
                )

        # 4. Check for an existing KEL inception (on-chain or mempool)
        from yadacoin.core.keyeventlog import KeyEventLog

        try:
            inception = await KeyEventLog.get_inception(k0_pub_hex)
            latest = (
                await KeyEventLog.get_latest(k0_pub_hex)
                if inception is not None
                else None
            )
        except Exception as exc:
            config.app_log.error("NodeKeyRotationManager: error checking KEL: %s", exc)
            inception = None
            latest = None

        if inception is not None:
            self.config.inception = inception
            depth = (latest.counter + 1) if latest is not None else 1
            latest_pkh = (
                latest.public_key_hash
                if latest is not None
                else inception.public_key_hash
            )
            config.app_log.info(
                "NodeKeyRotationManager: KEL inception found (depth=%d, inception_id=%s)",
                depth,
                inception.transaction_signature,
            )
            self._inception_txn_id = inception.transaction_signature

            self.config.username = inception.relationship.username
            self.config.username_signature = inception.relationship.username_signature

            # If already on-chain, finalise immediately
            inception_onchain = not getattr(inception, "mempool", False)
            if inception_onchain:
                await self._try_finalise(depth, latest_pkh, k0, second_factor)
            else:
                # Inception is mempool-only; derive K_n from depth-0 so
                # the node can start signing with it immediately.
                self._update_active_kel_key(depth, latest_pkh, k0, second_factor)
        else:
            config.app_log.warning(
                "NodeKeyRotationManager: no KEL inception found for derived key %s; "
                "creating inception transaction automatically.",
                k0_pub_hex,
            )
            inception = await self._create_inception(k0, second_factor, k0_pub_hex)
            self.config.inception = inception

    async def background_kel_checker(self):
        """Periodic callback: poll for inception on-chain and finalise config."""
        config = self.config
        k0 = self._k0
        second_factor = self._second_factor
        if not k0 or not second_factor:
            return  # startup_check hasn't run yet

        k0_pub_hex = (
            _CoincurvePrivateKey(k0["private_key"])
            .public_key.format(compressed=True)
            .hex()
        )

        from yadacoin.core.keyeventlog import KeyEventLog

        if not self._inception_complete:
            # Still waiting for inception to confirm on-chain
            try:
                latest = await KeyEventLog.get_latest(k0_pub_hex, onchain_only=True)
            except Exception as exc:
                config.app_log.debug(
                    "NodeKeyRotationManager: checker KEL error: %s", exc
                )
                return

            if latest is None:
                return  # inception not yet mined

            await self._try_finalise(
                latest.counter + 1, latest.public_key_hash, k0, second_factor
            )
            await self._check_and_sweep_legacy_funds(latest)
        else:
            # Inception confirmed — skip the expensive KEL build;
            # only check for legacy funds to sweep.
            try:
                latest = await KeyEventLog.get_latest(k0_pub_hex, onchain_only=True)
            except Exception as exc:
                config.app_log.debug(
                    "NodeKeyRotationManager: checker KEL error: %s", exc
                )
                return
            if latest is not None:
                await self._check_and_sweep_legacy_funds(latest)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Off-chain auth ratchet
    # ------------------------------------------------------------------

    async def _ensure_ratchet_ready(self):
        """Verify prerequisites and initialise the ratchet from the on-chain
        anchor + key_event_log tip if not yet set.

        Called once on the first call to either ``advance_auth_ratchet`` or
        ``advance_block_ratchet``.

        Returns (second_factor, prev_key dict, prev_pub_hex, prev_address).
        """
        config = self.config

        kel_priv = getattr(config, "kel_anchor_private_key", None)
        kel_pub = getattr(config, "kel_anchor_public_key", None)
        if not kel_priv or not kel_pub:
            _fatal(
                "\n"
                "═══════════════════════════════════════════════════════════════\n"
                "  FATAL: KEL signing key is not yet active.\n"
                "  The node cannot authenticate P2P connections without a KEL\n"
                "  inception confirmed on-chain or in the mempool.\n"
                "  Wait for startup_check to complete before connections are\n"
                "  accepted, or ensure SECOND_FACTOR is set correctly.\n"
                "═══════════════════════════════════════════════════════════════\n"
            )

        second_factor = self._second_factor or _read_second_factor()
        if not second_factor:
            _fatal(
                "\n"
                "═══════════════════════════════════════════════════════════════\n"
                "  FATAL: SECOND_FACTOR is required for P2P authentication but\n"
                "  is no longer available (was it unset after startup?).\n"
                "\n"
                "  Set SECOND_FACTOR or SECOND_FACTOR_FILE and restart.\n"
                "═══════════════════════════════════════════════════════════════\n"
            )

        if self._auth_ratchet_key is None:
            kel_cc = getattr(config, "kel_anchor_chain_code", None)
            if kel_cc:
                _base_ratchet = {
                    "private_key": bytes.fromhex(kel_priv),
                    "chain_code": bytes.fromhex(kel_cc),
                }
            else:
                _fatal(
                    "\n"
                    "═══════════════════════════════════════════════════════════\n"
                    "  FATAL: kel_anchor_chain_code missing. Cannot initialise ratchet.\n"
                    "═══════════════════════════════════════════════════════════\n"
                )
            _k0_pub_hex = (
                (
                    _CoincurvePrivateKey(self._k0["private_key"])
                    .public_key.format(compressed=True)
                    .hex()
                )
                if self._k0
                else kel_pub
            )
            _tip = await config.mongo.async_db.key_event_log.find_one(
                {"anchor_public_key": _k0_pub_hex},
                sort=[("counter", -1)],
            )
            _tip_counter = _tip.get("counter", 0) if _tip else 0
            _tip_pkh = _tip.get("public_key_hash", "") if _tip else ""
            _cur = _base_ratchet
            for _ in range(_tip_counter):
                _cur = derive_secure_path(
                    _cur["private_key"], _cur["chain_code"], second_factor
                )
            self._auth_ratchet_key = _cur
            self._auth_ratchet_pub = (
                kel_pub
                if not _tip_counter
                else (
                    _CoincurvePrivateKey(_cur["private_key"])
                    .public_key.format(compressed=True)
                    .hex()
                )
            )
            self._auth_counter = _tip_counter
            self._auth_ratchet_prev_pkh = _tip_pkh

        prev_key = self._auth_ratchet_key
        prev_pub_hex = self._auth_ratchet_pub
        prev_priv_obj = _CoincurvePrivateKey(prev_key["private_key"])
        prev_pub_bytes = prev_priv_obj.public_key.format(compressed=True)
        prev_address = str(P2PKHBitcoinAddress.from_pubkey(prev_pub_bytes))

        return second_factor, prev_key, prev_pub_hex, prev_address

    async def advance_auth_ratchet(self):
        """Advance the off-chain signing ratchet by one step for P2P
        authentication and return
        ``(current_priv_hex, current_pub_hex, next_priv_hex, next_pub_hex, twice_prerotated_key_hash)``.

        The caller must produce TWO signatures for authentication:
          1. current key signs the challenge  — proves possession of K_{n+i}
          2. next key signs the challenge     — proves knowledge of K_{n+i+1}

        An attacker who steals only K_{n+i} cannot produce the confirming
        signature without the SECOND_FACTOR needed to derive K_{n+i+1}.

        Each step:
        1. Derives K_{n+i+1} from K_{n+i} via ``derive_secure_path``
        2. Creates a zero-value KEL rotation transaction, stores it in
           ``key_event_log`` (off-chain record) and broadcasts to sync peers.
           These are NOT mined — only the periodic re-anchor transactions
           (every OFFCHAIN_ANCHOR_INTERVAL steps) go into ``miner_transactions``.
        3. Increments the counter; triggers re-anchor at interval boundaries.
        """
        config = self.config
        (
            second_factor,
            prev_key,
            prev_pub_hex,
            prev_address,
        ) = await self._ensure_ratchet_ready()

        next_key = derive_secure_path(
            prev_key["private_key"], prev_key["chain_code"], second_factor
        )
        next_priv_obj = _CoincurvePrivateKey(next_key["private_key"])
        next_pub_hex = next_priv_obj.public_key.format(compressed=True).hex()
        next_pub_bytes = next_priv_obj.public_key.format(compressed=True)
        next_address = str(P2PKHBitcoinAddress.from_pubkey(next_pub_bytes))

        two_ahead = derive_secure_path(
            next_key["private_key"], next_key["chain_code"], second_factor
        )
        two_ahead_pub = _CoincurvePrivateKey(
            two_ahead["private_key"]
        ).public_key.format(compressed=True)
        two_ahead_address = str(P2PKHBitcoinAddress.from_pubkey(two_ahead_pub))

        from yadacoin.core.transaction import Transaction

        anchor_pub = (
            (
                _CoincurvePrivateKey(self._k0["private_key"])
                .public_key.format(compressed=True)
                .hex()
            )
            if self._k0
            else (getattr(config, "kel_anchor_public_key", None) or prev_pub_hex)
        )

        ratchet_txn = Transaction(
            txn_time=int(time.time()),
            public_key=prev_pub_hex,
            outputs=[{"to": next_address, "value": 0.0}],
            inputs=[],
            fee=0.0,
            masternode_fee=0.0,
            version=7,
            prerotated_key_hash=next_address,
            twice_prerotated_key_hash=two_ahead_address,
            public_key_hash=prev_address,
            prev_public_key_hash=self._auth_ratchet_prev_pkh or "",
            relationship="",
            relationship_hash="",
            rid="",
            dh_public_key="",
        )
        # Self-sign the rotation with the key it rotates *from* — without
        # this, txn.hash stays "" and any peer that receives this entry in a
        # ratchet_chain fails verify() (verify_hash != self.hash) on every
        # single off-chain entry, which is fatal in _process_ratchet_auth.
        ratchet_txn.hash = await ratchet_txn.generate_hash()
        ratchet_txn.transaction_signature = NodeKeyRotationManager._sign(
            prev_key["private_key"].hex(), ratchet_txn.hash
        )

        self._auth_counter += 1

        try:
            await config.mongo.async_db.key_event_log.replace_one(
                {"public_key_hash": prev_address},
                {
                    "counter": self._auth_counter,
                    "anchor_public_key": anchor_pub,
                    "id": ratchet_txn.transaction_signature,
                    "public_key": prev_pub_hex,
                    "public_key_hash": prev_address,
                    "prerotated_key_hash": next_address,
                    "txn": ratchet_txn.to_dict(),
                    "timestamp": time.time(),
                },
                upsert=True,
            )
        except Exception as exc:
            config.app_log.debug(
                "NodeKeyRotationManager: key_event_log write error: %s", exc
            )

        self._auth_ratchet_key = next_key
        self._auth_ratchet_pub = next_pub_hex
        self._auth_ratchet_prev_pkh = prev_address

        await self._maybe_reanchor()

        return (
            prev_key["private_key"].hex(),
            prev_pub_hex,
            next_key["private_key"].hex(),
            next_pub_hex,
            two_ahead_address,
        )

    # ------------------------------------------------------------------
    # Per-peer off-chain auth ratchet branches
    # ------------------------------------------------------------------

    def peer_branch_factor(self, peer_username_signature: str) -> str:
        """Return the per-peer derivation factor: SECOND_FACTOR + the peer's
        username_signature (unique per remote identity, taken from their own
        K0/identity announcement)."""
        second_factor = self._second_factor or _read_second_factor()
        return second_factor + (peer_username_signature or "")

    async def _resolve_latest_kel_anchor(self):
        """Return ``({"private_key","chain_code"}, depth)`` for the most
        recent on-chain OR mempool KEL entry for our own identity (K0).

        Freshly resolved from the actual KEL every call — *not* the
        ``config.kel_anchor_*`` snapshot, which is only ever refreshed at
        startup/inception-confirmation and otherwise goes stale as later
        on-chain re-anchors get mined during a long-running process.  New
        peer branches must always root at our truly current position.
        ``depth`` is the number of derivation steps from K0 (i.e. the KEL
        length), recorded on the bridge entry so a *resumed* branch can
        reproduce this exact same root later without depending on whatever
        the "latest" anchor happens to be at resume time.
        """
        if not self._k0:
            return None, 0
        second_factor = self._second_factor or _read_second_factor()
        if not second_factor:
            return None, 0

        k0_pub_hex = (
            _CoincurvePrivateKey(self._k0["private_key"])
            .public_key.format(compressed=True)
            .hex()
        )

        from yadacoin.core.keyeventlog import KeyEventLog

        try:
            latest = await KeyEventLog.get_latest(k0_pub_hex, onchain_only=False)
        except Exception as exc:
            self.config.app_log.debug(
                "NodeKeyRotationManager: latest KEL anchor lookup error: %s", exc
            )
            latest = None

        depth = (latest.counter + 1) if latest is not None else 0
        cur = self._k0
        for _ in range(depth):
            cur = derive_secure_path(
                cur["private_key"], cur["chain_code"], second_factor
            )
        return cur, depth

    async def peer_branch_inception_public_key_hash(
        self, identity_announcement: str
    ) -> str:
        """Return addr(Kp0) for *peer_username_signature*, if a branch has
        already been established — read-only, never mints.  Checks the
        in-memory cache first, then the persistent ``branch_peer`` marker in
        ``key_event_log``.  Returns "" if this peer has no branch yet.

        ``branch_inception_public_key_hash`` is the P2PKH of the first public
        branch signer (Kp0), not the full public key.
        """
        cached = self._peer_branches.get(identity_announcement)
        if cached:
            return cached.get("branch_inception_public_key_hash") or ""
        if not identity_announcement:
            return ""
        bridge = await self.config.mongo.async_db.key_event_log.find_one(
            {"branch_peer": identity_announcement, "counter": 0}
        )
        if not bridge:
            return ""
        # Prefer new field; fall back to legacy full-pubkey anchor via pkh on doc
        return (
            bridge.get("branch_inception_public_key_hash")
            or bridge.get("public_key_hash")
            or ""
        )

    # Back-compat alias used by older call sites / tests during rollout
    async def peer_branch_anchor_pub(self, identity_announcement: str) -> str:
        return await self.peer_branch_inception_public_key_hash(identity_announcement)

    async def _ensure_peer_branch_ready(self, identity_announcement: str) -> dict:
        """Return (initialising/resuming if needed) this peer's branch state.

        On first contact with a peer, roots the branch at our *current*
        on-chain/mempool KEL anchor (see ``_resolve_latest_kel_anchor``),
        submits a main-KEL BranchAnnouncement unconfirmed + confirming pair
        to the mempool (pre=addr(Kp0), twice=addr(Kp1)), and seeds local
        ``key_event_log`` with a Kp0-anchored branch root.  On
        subsequent calls (including across restarts), resumes from whatever
        this branch's current tip already is in ``key_event_log``,
        reproducing the *original* root exactly rather than re-resolving
        "latest" again (which may have moved on since the branch was created).

        Returns ``(state, is_new_branch)`` — ``is_new_branch`` is True only
        on the exact call that mints the on-chain announcement (i.e. genuinely
        the first-ever contact with this peer, not merely a process restart
        resuming an existing branch), so callers know whether the peer also
        needs the single KEL entry that establishes K_n alongside the
        branch/ratchet_chain.
        """
        if identity_announcement in self._peer_branches:
            return self._peer_branches[identity_announcement], False

        if not identity_announcement:
            # Without a peer-specific suffix, peer_factor degrades to the
            # plain SECOND_FACTOR, which would collide with the global chain.
            _fatal(
                "\n"
                "═══════════════════════════════════════════════════════════════\n"
                "  FATAL: cannot start a peer KEL branch without the peer's\n"
                "  username_signature.\n"
                "═══════════════════════════════════════════════════════════════\n"
            )

        config = self.config
        peer_factor = self.peer_branch_factor(identity_announcement)
        second_factor = self._second_factor or _read_second_factor()

        # The bridge entry (counter 0) is the stable, permanent identifier
        # for this peer's branch — look it up by the branch_peer marker
        # (not by anchor_public_key, which we don't know yet without first
        # knowing which root produced it).
        bridge_doc = await config.mongo.async_db.key_event_log.find_one(
            {"branch_peer": identity_announcement, "counter": 0}
        )

        if bridge_doc is None:
            # First contact with this peer — root at our current on-chain/
            # mempool anchor.  Dual-commit (Kp0/Kp1) on-chain via BranchAnnouncement;
            # local off-chain branch state starts at Kp0.
            kn, root_depth = await self._resolve_latest_kel_anchor()
            if not kn:
                _fatal(
                    "\n"
                    "═══════════════════════════════════════════════════════════════\n"
                    "  FATAL: cannot start a peer KEL branch — KEL signing key is\n"
                    "  not yet active.  Wait for startup_check to complete before\n"
                    "  accepting connections.\n"
                    "═══════════════════════════════════════════════════════════════\n"
                )

            kn_pub_bytes = _CoincurvePrivateKey(kn["private_key"]).public_key.format(
                compressed=True
            )
            kn_pub_hex = kn_pub_bytes.hex()
            kn_address = str(P2PKHBitcoinAddress.from_pubkey(kn_pub_bytes))

            # Main-line next keys (announcement consumes one main rotation)
            kn1 = derive_secure_path(kn["private_key"], kn["chain_code"], second_factor)
            kn1_pub_bytes = _CoincurvePrivateKey(kn1["private_key"]).public_key.format(
                compressed=True
            )
            kn1_pub_hex = kn1_pub_bytes.hex()
            kn1_address = str(P2PKHBitcoinAddress.from_pubkey(kn1_pub_bytes))

            kn2 = derive_secure_path(
                kn1["private_key"], kn1["chain_code"], second_factor
            )
            kn2_address = str(
                P2PKHBitcoinAddress.from_pubkey(
                    _CoincurvePrivateKey(kn2["private_key"]).public_key.format(
                        compressed=True
                    )
                )
            )
            kn3 = derive_secure_path(
                kn2["private_key"], kn2["chain_code"], second_factor
            )
            kn3_address = str(
                P2PKHBitcoinAddress.from_pubkey(
                    _CoincurvePrivateKey(kn3["private_key"]).public_key.format(
                        compressed=True
                    )
                )
            )

            # Peer factor: Kp0 = first public signer; Kp1 = next hop commit
            kp0 = derive_secure_path(kn["private_key"], kn["chain_code"], peer_factor)
            kp0_pub_bytes = _CoincurvePrivateKey(kp0["private_key"]).public_key.format(
                compressed=True
            )
            kp0_pub_hex = kp0_pub_bytes.hex()
            kp0_address = str(P2PKHBitcoinAddress.from_pubkey(kp0_pub_bytes))

            kp1 = derive_secure_path(kp0["private_key"], kp0["chain_code"], peer_factor)
            kp1_address = str(
                P2PKHBitcoinAddress.from_pubkey(
                    _CoincurvePrivateKey(kp1["private_key"]).public_key.format(
                        compressed=True
                    )
                )
            )

            kp2 = derive_secure_path(kp1["private_key"], kp1["chain_code"], peer_factor)
            kp2_address = str(
                P2PKHBitcoinAddress.from_pubkey(
                    _CoincurvePrivateKey(kp2["private_key"]).public_key.format(
                        compressed=True
                    )
                )
            )

            from yadacoin.core.branchannouncement import BranchAnnouncement
            from yadacoin.core.transaction import Transaction

            latest_kel = await KeyEventLog.get_latest(
                self.config.inception.public_key, onchain_only=False
            )
            prev_pkh = (
                latest_kel.public_key_hash if latest_kel is not None else kn_address
            )

            # Main-chain inception pkh — tag mempool announce/confirm so peers
            # can select our main KEL via inception_public_key_hash without
            # dumping every branch announcement in the mempool.
            main_inception_pkh = None
            if latest_kel is not None:
                main_inception_pkh = getattr(
                    latest_kel, "inception_public_key_hash", None
                )
            if not main_inception_pkh:
                try:
                    inception_pub = getattr(
                        getattr(self.config, "inception", None), "public_key", None
                    )
                    if inception_pub:
                        main_inception_pkh = str(
                            P2PKHBitcoinAddress.from_pubkey(
                                bytes.fromhex(inception_pub)
                            )
                        )
                except Exception:
                    main_inception_pkh = None
            if not main_inception_pkh:
                main_inception_pkh = kn_address

            branch_rel = BranchAnnouncement(
                prerotated_key_hash=kp0_address,
                twice_prerotated_key_hash=kp1_address,
            )
            branch_rel_str = branch_rel.to_string()

            # Main unconfirmed (BranchAnnouncement) signed by K_n
            unconfirmed_txn = Transaction(
                txn_time=int(time.time()),
                public_key=kn_pub_hex,
                outputs=[{"to": kn1_address, "value": 0.0}],
                inputs=[],
                fee=0.0,
                masternode_fee=0.0,
                version=7,
                prerotated_key_hash=kn1_address,
                twice_prerotated_key_hash=kn2_address,
                public_key_hash=kn_address,
                prev_public_key_hash=prev_pkh,
                relationship=branch_rel,
                relationship_hash=hashlib.sha256(branch_rel_str.encode("utf-8"))
                .digest()
                .hex(),
                rid="",
                dh_public_key="",
            )
            unconfirmed_txn.hash = await unconfirmed_txn.generate_hash()
            unconfirmed_txn.transaction_signature = NodeKeyRotationManager._sign(
                kn["private_key"].hex(), unconfirmed_txn.hash
            )

            # Main confirming signed by K_n+1
            confirming_txn = Transaction(
                txn_time=int(time.time()),
                public_key=kn1_pub_hex,
                outputs=[{"to": kn2_address, "value": 0.0}],
                inputs=[],
                fee=0.0,
                masternode_fee=0.0,
                version=7,
                prerotated_key_hash=kn2_address,
                twice_prerotated_key_hash=kn3_address,
                public_key_hash=kn1_address,
                prev_public_key_hash=kn_address,
                relationship="",
                relationship_hash="",
                rid="",
                dh_public_key="",
            )
            confirming_txn.hash = await confirming_txn.generate_hash()
            confirming_txn.transaction_signature = NodeKeyRotationManager._sign(
                kn1["private_key"].hex(), confirming_txn.hash
            )

            # Submit announce+confirm to mempool (on-chain source of truth).
            # Upsert by transaction id only — NOT by pkh/pre/twice $or.
            # Confirming.public_key_hash == unconfirmed.prerotated_key_hash, so
            # an $or filter would replace the BranchAnnouncement with the
            # confirming sibling and drop the on-chain commit from the mempool.
            for txn in (unconfirmed_txn, confirming_txn):
                try:
                    doc = txn.to_dict()
                    doc["inception_public_key_hash"] = main_inception_pkh
                    await config.mongo.async_db.miner_transactions.replace_one(
                        {"id": txn.transaction_signature},
                        doc,
                        upsert=True,
                    )
                except Exception as exc:
                    config.app_log.warning(
                        "NodeKeyRotationManager: branch announcement mempool "
                        "write error: %s",
                        exc,
                    )

            config.app_log.info(
                "NodeKeyRotationManager: branch announcement queued "
                "(unconfirmed=%s, confirming=%s, commit=%s, commit_next=%s)",
                unconfirmed_txn.transaction_signature,
                confirming_txn.transaction_signature,
                kp0_address,
                kp1_address,
            )

            if "node" in getattr(config, "modes", []):
                try:
                    async for peer_stream in config.peer.get_sync_peers():
                        for txn in (unconfirmed_txn, confirming_txn):
                            await config.nodeShared.write_params(
                                peer_stream, "newtxn", {"transaction": txn.to_dict()}
                            )
                except Exception as exc:
                    config.app_log.debug(
                        "NodeKeyRotationManager: branch announcement broadcast "
                        "error: %s",
                        exc,
                    )

            # Off-chain first branch entry: pkh=addr(Kp0), pre=addr(Kp1)
            # Continuity:
            #   relationship.pre   == first.public_key_hash
            #   relationship.twice == first.prerotated_key_hash
            #   first.prev         == confirming.public_key_hash
            root_txn = Transaction(
                txn_time=int(time.time()),
                public_key=kp0_pub_hex,
                outputs=[{"to": kp1_address, "value": 0.0}],
                inputs=[],
                fee=0.0,
                masternode_fee=0.0,
                version=7,
                prerotated_key_hash=kp1_address,
                twice_prerotated_key_hash=kp2_address,
                public_key_hash=kp0_address,
                prev_public_key_hash=confirming_txn.public_key_hash,
                relationship="",
                relationship_hash="",
                rid="",
                dh_public_key="",
            )
            root_txn.hash = await root_txn.generate_hash()
            root_txn.transaction_signature = NodeKeyRotationManager._sign(
                kp0["private_key"].hex(), root_txn.hash
            )

            # main_inception_pkh already resolved above for mempool tagging.
            try:
                await config.mongo.async_db.key_event_log.replace_one(
                    {
                        "branch_peer": identity_announcement,
                        "counter": 0,
                    },
                    {
                        "counter": 0,
                        "branch_inception_public_key_hash": kp0_address,
                        "inception_public_key_hash": main_inception_pkh,
                        "branch_peer": identity_announcement,
                        "root_depth": root_depth,
                        "branch_commit": kp0_address,
                        "branch_commit_next": kp1_address,
                        "confirming_public_key_hash": confirming_txn.public_key_hash,
                        "id": root_txn.transaction_signature,
                        "public_key": kp0_pub_hex,
                        "public_key_hash": kp0_address,
                        "prerotated_key_hash": kp1_address,
                        "txn": root_txn.to_dict(),
                        "announcement_txn": unconfirmed_txn.to_dict(),
                        "confirming_txn": confirming_txn.to_dict(),
                        "timestamp": time.time(),
                    },
                    upsert=True,
                )
            except Exception as exc:
                config.app_log.debug(
                    "NodeKeyRotationManager: peer branch root write error: %s", exc
                )

            # Local state starts at Kp0; first advance_peer_auth_ratchet signs as Kp0
            state = {
                "ratchet_key": kp0,
                "ratchet_pub": kp0_pub_hex,
                "counter": 0,
                "prev_pkh": confirming_txn.public_key_hash,
                "branch_inception_public_key_hash": kp0_address,
                "inception_public_key_hash": main_inception_pkh,
            }
        else:
            # Resume: reproduce the *original* root exactly — replay
            # root_depth steps from K0 with the plain factor (not "latest",
            # which may have advanced since this branch was created) — then
            # re-derive Kp0 and fast-forward to the branch's current tip.
            root_depth = bridge_doc.get("root_depth", 0) or 0
            branch_inception_pkh = (
                bridge_doc.get("branch_inception_public_key_hash")
                or bridge_doc.get("public_key_hash")
                or bridge_doc.get("branch_commit")
                or ""
            )
            main_inception_pkh = bridge_doc.get("inception_public_key_hash") or ""

            cur_root = self._k0
            for _ in range(root_depth):
                cur_root = derive_secure_path(
                    cur_root["private_key"], cur_root["chain_code"], second_factor
                )
            kp0 = derive_secure_path(
                cur_root["private_key"], cur_root["chain_code"], peer_factor
            )
            kp0_pub_hex = (
                _CoincurvePrivateKey(kp0["private_key"])
                .public_key.format(compressed=True)
                .hex()
            )
            kp0_address = str(
                P2PKHBitcoinAddress.from_pubkey(
                    _CoincurvePrivateKey(kp0["private_key"]).public_key.format(
                        compressed=True
                    )
                )
            )
            if not branch_inception_pkh:
                branch_inception_pkh = kp0_address

            tip = await config.mongo.async_db.key_event_log.find_one(
                {"branch_inception_public_key_hash": branch_inception_pkh},
                sort=[("counter", -1)],
            )
            # Legacy resume: docs written with anchor_public_key = full pub
            if tip is None and bridge_doc.get("anchor_public_key"):
                tip = await config.mongo.async_db.key_event_log.find_one(
                    {"anchor_public_key": bridge_doc["anchor_public_key"]},
                    sort=[("counter", -1)],
                )
            counter = tip.get("counter", 0) if tip else 0
            if tip and not main_inception_pkh:
                main_inception_pkh = tip.get("inception_public_key_hash") or ""
            cur = kp0
            for _ in range(counter):
                cur = derive_secure_path(
                    cur["private_key"], cur["chain_code"], peer_factor
                )
            cur_pub_hex = (
                _CoincurvePrivateKey(cur["private_key"])
                .public_key.format(compressed=True)
                .hex()
            )
            state = {
                "ratchet_key": cur,
                "ratchet_pub": cur_pub_hex,
                "counter": counter,
                "prev_pkh": (tip or {}).get("public_key_hash", kp0_address),
                "branch_inception_public_key_hash": branch_inception_pkh,
                "inception_public_key_hash": main_inception_pkh,
            }

        is_new_branch = bridge_doc is None
        self._peer_branches[identity_announcement] = state
        return state, is_new_branch

    async def advance_peer_auth_ratchet(self, identity_announcement: str):
        """Advance the off-chain signing ratchet by one step *within this
        peer's own branch* and return a 6-tuple:
        ``(current_priv_hex, current_pub_hex, next_priv_hex, next_pub_hex, twice_prerotated_key_hash, is_new_branch)``.

        Unlike ``advance_auth_ratchet`` (one global chain shared by every
        peer), each peer gets an isolated branch rooted at
        ``Kp0 = derive(K_n, peer_factor)`` (first public signer; Kp1 is the next hop), so
        the ratchet_chain delta sent to a given peer only ever contains
        entries that were generated for connections with *that* peer —
        never the history accumulated talking to anyone else.

        ``is_new_branch`` is True only on the very first call ever made for
        this peer (the one that mints the BranchAnnouncement) — callers should
        use it to decide whether the peer also needs the single KEL entry that
        establishes K_n (see NodeRPC._get_kel_anchor_chain in
        tcpsocket/node.py), since a brand-new peer relationship has no other
        way to validate the announcement's on-chain parent before block sync
        has even started.
        """
        config = self.config
        peer_factor = self.peer_branch_factor(identity_announcement)
        state, is_new_branch = await self._ensure_peer_branch_ready(
            identity_announcement
        )

        prev_key = state["ratchet_key"]
        prev_pub_hex = state["ratchet_pub"]
        prev_priv_obj = _CoincurvePrivateKey(prev_key["private_key"])
        prev_pub_bytes = prev_priv_obj.public_key.format(compressed=True)
        prev_address = str(P2PKHBitcoinAddress.from_pubkey(prev_pub_bytes))

        next_key = derive_secure_path(
            prev_key["private_key"], prev_key["chain_code"], peer_factor
        )
        next_priv_obj = _CoincurvePrivateKey(next_key["private_key"])
        next_pub_hex = next_priv_obj.public_key.format(compressed=True).hex()
        next_pub_bytes = next_priv_obj.public_key.format(compressed=True)
        next_address = str(P2PKHBitcoinAddress.from_pubkey(next_pub_bytes))

        two_ahead = derive_secure_path(
            next_key["private_key"], next_key["chain_code"], peer_factor
        )
        two_ahead_pub = _CoincurvePrivateKey(
            two_ahead["private_key"]
        ).public_key.format(compressed=True)
        two_ahead_address = str(P2PKHBitcoinAddress.from_pubkey(two_ahead_pub))

        from yadacoin.core.transaction import Transaction

        ratchet_txn = Transaction(
            txn_time=int(time.time()),
            public_key=prev_pub_hex,
            outputs=[{"to": next_address, "value": 0.0}],
            inputs=[],
            fee=0.0,
            masternode_fee=0.0,
            version=7,
            prerotated_key_hash=next_address,
            twice_prerotated_key_hash=two_ahead_address,
            public_key_hash=prev_address,
            prev_public_key_hash=state.get("prev_pkh") or "",
            relationship="",
            relationship_hash="",
            rid="",
            dh_public_key="",
        )
        ratchet_txn.hash = await ratchet_txn.generate_hash()
        ratchet_txn.transaction_signature = NodeKeyRotationManager._sign(
            prev_key["private_key"].hex(), ratchet_txn.hash
        )

        next_counter = state["counter"] + 1
        branch_inception_pkh = state["branch_inception_public_key_hash"]
        main_inception_pkh = state.get("inception_public_key_hash") or ""

        try:
            # Include counter so the Kp0 root (counter 0) is not overwritten when
            # the first advance also signs as addr(Kp0).
            await config.mongo.async_db.key_event_log.replace_one(
                {
                    "branch_inception_public_key_hash": branch_inception_pkh,
                    "counter": next_counter,
                },
                {
                    "counter": next_counter,
                    "branch_inception_public_key_hash": branch_inception_pkh,
                    "inception_public_key_hash": main_inception_pkh,
                    "branch_peer": identity_announcement,
                    "id": ratchet_txn.transaction_signature,
                    "public_key": prev_pub_hex,
                    "public_key_hash": prev_address,
                    "prerotated_key_hash": next_address,
                    "txn": ratchet_txn.to_dict(),
                    "timestamp": time.time(),
                },
                upsert=True,
            )
        except Exception as exc:
            config.app_log.debug(
                "NodeKeyRotationManager: peer branch key_event_log write error: %s",
                exc,
            )

        self._peer_branches[identity_announcement] = {
            "ratchet_key": next_key,
            "ratchet_pub": next_pub_hex,
            "counter": next_counter,
            "prev_pkh": prev_address,
            "branch_inception_public_key_hash": branch_inception_pkh,
            "inception_public_key_hash": main_inception_pkh,
        }

        return (
            prev_key["private_key"].hex(),
            prev_pub_hex,
            next_key["private_key"].hex(),
            next_pub_hex,
            two_ahead_address,
            is_new_branch,
        )

    async def advance_block_ratchet(self, block):
        """Advance the ratchet for block generation.

        Sets ``block.public_key`` / ``block.private_key`` to the current
        ratchet key, queues a re-anchor tx pair (which goes into
        ``miner_transactions`` so the miner includes the on-chain anchor),
        and returns a :class:`ReanchorTriplet` with key material and the
        anchor transactions.
        """
        (
            second_factor,
            prev_key,
            prev_pub_hex,
            prev_address,
        ) = await self._ensure_ratchet_ready()

        _CoincurvePrivateKey(prev_key["private_key"])

        triplet = await self._queue_reanchor(
            block=block,
            signer_private_key=prev_key["private_key"].hex(),
            signer_public_key=prev_pub_hex,
            relationship="block reanchor",
        )

        self._auth_counter += 1

        return triplet

    async def _maybe_reanchor(self):
        """Trigger a re-anchor if the off-chain counter has reached the interval."""
        if self._auth_counter % self.OFFCHAIN_ANCHOR_INTERVAL == 0:
            try:
                await self._queue_reanchor(
                    block=None, relationship="reanchor 100 interval"
                )
            except Exception as exc:
                self.config.app_log.warning(
                    "NodeKeyRotationManager: re-anchor error: %s", exc
                )

    async def _queue_reanchor(
        self,
        block=None,
        signer_private_key=None,
        signer_public_key=None,
        relationship=None,
        coinbase_prerotated=None,
        coinbase_twice_prerotated=None,
        coinbase_public_key_hash=None,
        coinbase_prev_public_key_hash=None,
    ):
        """Queue an on-chain UNCONFIRMED+CONFIRMING re-anchor pair.

        When ``block`` is passed (mining path), returns a
        :class:`ReanchorTriplet`.  Otherwise (auth-triggered re-anchor)
        writes into ``miner_transactions`` and broadcasts.

        The caller (``advance_block_ratchet``) derives the coinbase KEL
        fields once and passes them here so no derivation is duplicated.
        """
        config = self.config
        k0 = self._k0
        second_factor = self._second_factor or _read_second_factor()
        if not k0 or not second_factor:
            if block:
                return ReanchorTriplet(
                    unconfirmed=None,
                    confirming=None,
                    signer_private_key=signer_private_key,
                    signer_public_key=signer_public_key,
                    coinbase_prerotated=coinbase_prerotated,
                    coinbase_twice_prerotated=coinbase_twice_prerotated,
                    coinbase_public_key_hash=coinbase_public_key_hash,
                    coinbase_prev_public_key_hash=coinbase_prev_public_key_hash,
                )
            return

        from yadacoin.core.keyeventlog import KeyEventLog
        from yadacoin.core.transaction import Transaction

        kel_pub = getattr(config, "kel_anchor_public_key", None)
        if not kel_pub:
            if block:
                return ReanchorTriplet(
                    unconfirmed=None,
                    confirming=None,
                    signer_private_key=signer_private_key,
                    signer_public_key=signer_public_key,
                    coinbase_prerotated=coinbase_prerotated,
                    coinbase_twice_prerotated=coinbase_twice_prerotated,
                    coinbase_public_key_hash=coinbase_public_key_hash,
                    coinbase_prev_public_key_hash=coinbase_prev_public_key_hash,
                )
            return

        k0_pub_hex = (
            _CoincurvePrivateKey(k0["private_key"])
            .public_key.format(compressed=True)
            .hex()
        )
        try:
            latest = await KeyEventLog.get_latest(k0_pub_hex, onchain_only=False)
        except Exception:
            if block:
                return ReanchorTriplet(
                    unconfirmed=None,
                    confirming=None,
                    signer_private_key=signer_private_key,
                    signer_public_key=signer_public_key,
                    coinbase_prerotated=coinbase_prerotated,
                    coinbase_twice_prerotated=coinbase_twice_prerotated,
                    coinbase_public_key_hash=coinbase_public_key_hash,
                    coinbase_prev_public_key_hash=coinbase_prev_public_key_hash,
                )
            return
        if not latest:
            if block:
                return ReanchorTriplet(
                    unconfirmed=None,
                    confirming=None,
                    signer_private_key=signer_private_key,
                    signer_public_key=signer_public_key,
                    coinbase_prerotated=coinbase_prerotated,
                    coinbase_twice_prerotated=coinbase_twice_prerotated,
                    coinbase_public_key_hash=coinbase_public_key_hash,
                    coinbase_prev_public_key_hash=coinbase_prev_public_key_hash,
                )
            return

        # Walk the on-chain KEL to find the current anchor tip (K_n).
        # This determines where the UNCONFIRMED entry signs from.
        cur = k0

        cur = derive_secure_path(cur["private_key"], cur["chain_code"], second_factor)
        cur_priv_obj = _CoincurvePrivateKey(cur["private_key"])
        cur_pub_bytes = cur_priv_obj.public_key.format(compressed=True)
        cur_address = str(P2PKHBitcoinAddress.from_pubkey(cur_pub_bytes))
        while latest.prerotated_key_hash != cur_address:
            cur = derive_secure_path(
                cur["private_key"], cur["chain_code"], second_factor
            )
            cur_priv_obj = _CoincurvePrivateKey(cur["private_key"])
            cur_pub_bytes = cur_priv_obj.public_key.format(compressed=True)
            cur_address = str(P2PKHBitcoinAddress.from_pubkey(cur_pub_bytes))
            if latest.prerotated_key_hash == cur_address:
                break
        kn = cur

        kn1 = derive_secure_path(kn["private_key"], kn["chain_code"], second_factor)
        kn1_priv_obj = _CoincurvePrivateKey(kn1["private_key"])
        kn1_pub_bytes = kn1_priv_obj.public_key.format(compressed=True)
        kn1_pub_hex = kn1_pub_bytes.hex()
        kn1_address = str(P2PKHBitcoinAddress.from_pubkey(kn1_pub_bytes))

        kn_priv_obj = _CoincurvePrivateKey(kn["private_key"])
        kn_pub_bytes = kn_priv_obj.public_key.format(compressed=True)
        kn_pub_hex = kn_pub_bytes.hex()
        kn_address = str(P2PKHBitcoinAddress.from_pubkey(kn_pub_bytes))

        search_address = kn_address
        jump_cur = kn1
        curr_priv_obj = _CoincurvePrivateKey(jump_cur["private_key"])
        curr_pub_bytes = curr_priv_obj.public_key.format(compressed=True)
        curr_address = str(P2PKHBitcoinAddress.from_pubkey(curr_pub_bytes))

        txn_doc = await self.config.mongo.async_db.key_event_log.find_one(
            {"txn.prev_public_key_hash": search_address}
        )
        if txn_doc:
            txn_doc = await self.config.mongo.async_db.key_event_log.find_one(
                {"anchor_public_key": txn_doc["anchor_public_key"]},
                sort=[("counter", -1)],
            )
            i = latest.counter - 1
            while (
                curr_address != txn_doc["prerotated_key_hash"]
                and curr_address != latest.prerotated_key_hash
                and i < txn_doc["counter"]
            ):
                jump_cur = derive_secure_path(
                    jump_cur["private_key"], jump_cur["chain_code"], second_factor
                )
                curr_priv_obj = _CoincurvePrivateKey(jump_cur["private_key"])
                curr_pub_bytes = curr_priv_obj.public_key.format(compressed=True)
                curr_address = str(P2PKHBitcoinAddress.from_pubkey(curr_pub_bytes))
                i += 1
        else:
            jump_cur = derive_secure_path(
                jump_cur["private_key"], jump_cur["chain_code"], second_factor
            )

        jump_priv_obj = _CoincurvePrivateKey(jump_cur["private_key"])
        jump_pub_bytes = jump_priv_obj.public_key.format(compressed=True)
        jump_address = str(P2PKHBitcoinAddress.from_pubkey(jump_pub_bytes))

        jump2 = derive_secure_path(
            jump_cur["private_key"], jump_cur["chain_code"], second_factor
        )
        jump2_priv_obj = _CoincurvePrivateKey(jump2["private_key"])
        jump2_pub_bytes = jump2_priv_obj.public_key.format(compressed=True)
        jump2_address = str(P2PKHBitcoinAddress.from_pubkey(jump2_pub_bytes))

        jump3 = derive_secure_path(
            jump2["private_key"], jump2["chain_code"], second_factor
        )
        jump3_priv_obj = _CoincurvePrivateKey(jump3["private_key"])
        jump3_pub_bytes = jump3_priv_obj.public_key.format(compressed=True)
        jump3_address = str(P2PKHBitcoinAddress.from_pubkey(jump3_pub_bytes))

        jump4 = derive_secure_path(
            jump3["private_key"], jump3["chain_code"], second_factor
        )
        jump4_priv_obj = _CoincurvePrivateKey(jump4["private_key"])
        jump4_pub_bytes = jump4_priv_obj.public_key.format(compressed=True)
        jump4_address = str(P2PKHBitcoinAddress.from_pubkey(jump4_pub_bytes))

        prev_pkh = latest.public_key_hash

        # --- UNCONFIRMED ---
        unconfirmed_txn = Transaction(
            txn_time=int(time.time()),
            public_key=kn_pub_hex,
            outputs=[{"to": kn1_address, "value": 0.0}],
            inputs=[],
            fee=0.0,
            masternode_fee=0.0,
            version=7,
            prerotated_key_hash=kn1_address,
            twice_prerotated_key_hash=jump_address,
            public_key_hash=kn_address,
            prev_public_key_hash=prev_pkh,
            relationship=relationship or "",
            relationship_hash=hashlib.sha256((relationship or "").encode("utf-8"))
            .digest()
            .hex(),
            rid="",
            dh_public_key="",
        )
        unconfirmed_txn.hash = await unconfirmed_txn.generate_hash()
        unconfirmed_txn.transaction_signature = NodeKeyRotationManager._sign(
            kn["private_key"].hex(), unconfirmed_txn.hash
        )

        # --- CONFIRMING ---
        confirming_txn = Transaction(
            txn_time=int(time.time()),
            public_key=kn1_pub_hex,
            outputs=[{"to": jump_address, "value": 0.0}],
            inputs=[],
            fee=0.0,
            masternode_fee=0.0,
            version=7,
            prerotated_key_hash=jump_address,
            twice_prerotated_key_hash=jump2_address,
            public_key_hash=kn1_address,
            prev_public_key_hash=kn_address,
            relationship="",
            relationship_hash="",
            rid="",
            dh_public_key="",
        )

        mempool_txns = [unconfirmed_txn, confirming_txn]
        confirming_txn.hash = await confirming_txn.generate_hash()
        confirming_txn.transaction_signature = NodeKeyRotationManager._sign(
            kn1["private_key"].hex(), confirming_txn.hash
        )
        if block:
            # --- CONFIRMING ---
            coinbase_confirming_txn = Transaction(
                txn_time=int(time.time()),
                public_key=jump2_pub_bytes.hex(),
                outputs=[{"to": jump3_address, "value": 0.0}],
                inputs=[],
                fee=0.0,
                masternode_fee=0.0,
                version=7,
                prerotated_key_hash=jump3_address,
                twice_prerotated_key_hash=jump4_address,
                public_key_hash=jump2_address,
                prev_public_key_hash=jump_address,
                relationship="",
                relationship_hash="",
                rid="",
                dh_public_key="",
            )
            coinbase_confirming_txn.hash = await coinbase_confirming_txn.generate_hash()
            coinbase_confirming_txn.transaction_signature = (
                NodeKeyRotationManager._sign(
                    jump2["private_key"].hex(), coinbase_confirming_txn.hash
                )
            )
            mempool_txns.append(coinbase_confirming_txn)

        for txn in mempool_txns:
            await config.mongo.async_db.miner_transactions.replace_one(
                {
                    "$or": [
                        {"public_key_hash": txn.public_key_hash},
                        {"prerotated_key_hash": txn.prerotated_key_hash},
                        {"twice_prerotated_key_hash": txn.twice_prerotated_key_hash},
                    ],
                },
                txn.to_dict(),
                upsert=True,
            )

        if block:
            block.private_key = jump_cur["private_key"].hex()
            block.public_key = jump_pub_bytes.hex()
            signer_pub = jump_pub_bytes.hex()
            signer_pub_bytes = bytes.fromhex(signer_pub)
            signer_address = str(P2PKHBitcoinAddress.from_pubkey(signer_pub_bytes))
            return ReanchorTriplet(
                unconfirmed=unconfirmed_txn,
                confirming=confirming_txn,
                signer_private_key=jump_cur["private_key"].hex(),
                signer_public_key=signer_pub,
                coinbase_prerotated=jump2_address,
                coinbase_twice_prerotated=jump3_address,
                coinbase_public_key_hash=signer_address,
                coinbase_prev_public_key_hash=confirming_txn.public_key_hash,
            )

        config.app_log.info(
            "NodeKeyRotationManager: re-anchor queued (unconfirmed=%s, confirming=%s, "
            "jump_target=%s)",
            unconfirmed_txn.transaction_signature,
            confirming_txn.transaction_signature,
            jump_address,
        )

        if "node" in config.modes:
            try:
                async for peer_stream in config.peer.get_sync_peers():
                    for txn in (unconfirmed_txn, confirming_txn):
                        await config.nodeShared.write_params(
                            peer_stream, "newtxn", {"transaction": txn.to_dict()}
                        )
                        if peer_stream.peer.protocol_version > 1:
                            config.nodeClient.retry_messages[
                                (
                                    peer_stream.peer.rid,
                                    "newtxn",
                                    txn.transaction_signature,
                                )
                            ] = {"transaction": txn.to_dict()}
            except Exception as exc:
                config.app_log.warning(
                    "NodeKeyRotationManager: re-anchor broadcast error: %s", exc
                )

    async def _create_inception(self, k0: dict, second_factor: str, k0_pub_hex: str):
        """Build and broadcast a zero-fee KEL inception transaction for K0.

        The node's identity (username, username_signature, host, port, peer_type)
        is embedded in the relationship field as an IdentityAnnouncement so that
        other nodes can resolve ``username → K0 public_key`` from the chain.
        """
        from yadacoin.core.identityannouncement import IdentityAnnouncement
        from yadacoin.core.transaction import Transaction

        config = self.config

        k0_priv_obj = _CoincurvePrivateKey(k0["private_key"])
        k0_pub_bytes = k0_priv_obj.public_key.format(compressed=True)
        k0_address = str(P2PKHBitcoinAddress.from_pubkey(k0_pub_bytes))

        # Anchor the active KEL signing key to K0 at inception time so all
        # signing operations and my_peer() present K0 immediately.
        config.kel_anchor_private_key = k0["private_key"].hex()
        config.kel_anchor_chain_code = k0["chain_code"].hex()
        config.kel_anchor_public_key = k0_pub_bytes.hex()
        config.kel_anchor_address = k0_address

        prerotated = derive_secure_path(
            k0["private_key"], k0["chain_code"], second_factor
        )
        pre_priv_obj = _CoincurvePrivateKey(prerotated["private_key"])
        pre_pub_bytes = pre_priv_obj.public_key.format(compressed=True)
        pre_address = str(P2PKHBitcoinAddress.from_pubkey(pre_pub_bytes))

        twice_prerot = derive_secure_path(
            prerotated["private_key"], prerotated["chain_code"], second_factor
        )
        twice_priv_obj = _CoincurvePrivateKey(twice_prerot["private_key"])
        twice_pub_bytes = twice_priv_obj.public_key.format(compressed=True)
        twice_address = str(P2PKHBitcoinAddress.from_pubkey(twice_pub_bytes))

        # Build the identity announcement to embed in the relationship field.
        # username_signature is computed once here with K0 and stored on-chain.
        config = self.config
        username = getattr(config, "username", "") or ""
        identity_rel_hash = ""
        announcement = None
        if username.strip():
            username_sig = NodeKeyRotationManager.generate_deterministic_signature(
                username
            )
            peer_type = (
                getattr(config, "peer_type", "service_provider") or "service_provider"
            )
            getattr(config, "serve_port", 443)
            http_protocol = (
                "https"
                if getattr(config, "ssl", None) and getattr(config.ssl, "port", None)
                else "http"
            )
            try:
                announcement = IdentityAnnouncement(
                    username=username,
                    username_signature=username_sig,
                )
                identity_rel_str = announcement.to_string()
                identity_rel_hash = (
                    hashlib.sha256(identity_rel_str.encode("utf-8")).digest().hex()
                )
            except Exception as exc:
                config.app_log.warning(
                    "NodeKeyRotationManager: could not build identity announcement: %s",
                    exc,
                )

        txn = Transaction(
            txn_time=int(time.time()),
            public_key=k0_pub_hex,
            outputs=[{"to": pre_address, "value": 0.0}],
            inputs=[],
            fee=0.0,
            masternode_fee=0.0,
            version=7,
            prerotated_key_hash=pre_address,
            twice_prerotated_key_hash=twice_address,
            public_key_hash=k0_address,
            prev_public_key_hash="",
            relationship=announcement or "",
            relationship_hash=identity_rel_hash,
            rid="",
            dh_public_key="",
        )
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = NodeKeyRotationManager._sign(
            k0["private_key"].hex(), txn.hash
        )

        await config.mongo.async_db.miner_transactions.replace_one(
            {"id": txn.transaction_signature},
            txn.to_dict(),
            upsert=True,
        )

        self._inception_txn_id = txn.transaction_signature
        config.app_log.info(
            "NodeKeyRotationManager: inception transaction created and submitted to mempool "
            "(txn_id=%s, signing_address=%s).",
            txn.transaction_signature,
            k0_address,
        )

        if "node" in config.modes and getattr(config, "peer", None):
            try:
                async for peer_stream in config.peer.get_sync_peers():
                    await config.nodeShared.write_params(
                        peer_stream, "newtxn", {"transaction": txn.to_dict()}
                    )
                    if peer_stream.peer.protocol_version > 1:
                        config.nodeClient.retry_messages[
                            (peer_stream.peer.rid, "newtxn", txn.transaction_signature)
                        ] = {"transaction": txn.to_dict()}
            except Exception as exc:
                config.app_log.warning(
                    "NodeKeyRotationManager: inception broadcast error: %s", exc
                )
        return txn

    async def _try_finalise(
        self, depth: int, latest_pkh: str, k0: dict, second_factor: str
    ):
        """Update the active KEL signing key on config once the inception is
        confirmed on-chain.  The on-chain identity announcement is the
        canonical anchor.
        """
        self._update_active_kel_key(depth, latest_pkh, k0, second_factor)
        self._inception_complete = True

    def _update_active_kel_key(
        self, depth: int, latest_pkh: str, k0: dict, second_factor: str
    ):
        """Derive K_n (one step past the last on-chain KEL entry) and store it
        on config so all signing operations can use it immediately.

        *depth* is the total number of entries in the KEL (i.e. what
        ``len(kel)`` used to be — now derived from the tagged ``counter`` via
        ``get_latest`` without walking the whole chain), and *latest_pkh* is
        the latest entry's own ``public_key_hash`` (what ``kel[-1].public_key_hash``
        used to be).
        """
        config = self.config
        cur = k0
        for _ in range(depth):
            cur = derive_secure_path(
                cur["private_key"], cur["chain_code"], second_factor
            )

        kn_priv_obj = _CoincurvePrivateKey(cur["private_key"])
        kn_pub_bytes = kn_priv_obj.public_key.format(compressed=True)
        kn_pub_hex = kn_pub_bytes.hex()
        kn_address = str(P2PKHBitcoinAddress.from_pubkey(kn_pub_bytes))

        config.kel_anchor_private_key = cur["private_key"].hex()
        config.kel_anchor_chain_code = cur["chain_code"].hex()
        config.kel_anchor_public_key = kn_pub_hex
        config.kel_anchor_address = kn_address

        # Compute the KEL username_signature signed with K_n's private key so
        # that my_peer() can present the KEL key as the authoritative identity.
        # This must be recomputed each time K_n advances (re-anchor).
        username = getattr(config, "username", "") or ""
        if username.strip():
            try:
                config.kel_username_signature = (
                    NodeKeyRotationManager.generate_deterministic_signature(username)
                )
            except Exception as _exc:
                config.app_log.debug(
                    "NodeKeyRotationManager: could not compute kel_username_signature: %s",
                    _exc,
                )

        # Track the previous KEL entry's public_key_hash so ratchet
        # transactions can set prev_public_key_hash correctly.
        if latest_pkh:
            self._auth_ratchet_prev_pkh = latest_pkh

        config.app_log.info(
            "NodeKeyRotationManager: active KEL signing key updated "
            "(depth=%d, address=%s)",
            depth,
            kn_address,
        )

    async def _check_and_sweep_legacy_funds(self, latest):
        """Sweep UTXOs at the legacy node address (P2PKH of config.public_key)
        to ``latest.prerotated_key_hash``.

        This transitions funds from the potentially compromised WIF-derived
        address to the KEL-protected address.  The balance cache is keyed by
        block height + hash so we only query the chain when the tip advances.
        """
        config = self.config
        legacy_address = config.address
        sweep_target = latest.prerotated_key_hash

        if legacy_address == sweep_target:
            return  # nothing to move

        try:
            current_height = config.LatestBlock.block.index
            current_hash = config.LatestBlock.block.hash
        except Exception:
            return

        cached = self._kel_balance_cache.get(legacy_address)
        cache_valid = (
            cached is not None
            and cached["block_height"] == current_height
            and cached["block_hash"] == current_hash
        )

        if not cache_valid:
            utxos = []
            try:
                async for utxo in config.BU.get_wallet_unspent_transactions_for_spending(
                    legacy_address
                ):
                    utxos.append(utxo)
                    if len(utxos) >= 100:
                        break  # obey the 100-input chain limit; remainder swept next poll
            except Exception as exc:
                config.app_log.debug(
                    "NodeKeyRotationManager: legacy UTXO fetch error: %s", exc
                )
            self._kel_balance_cache[legacy_address] = {
                "utxos": utxos,
                "block_height": current_height,
                "block_hash": current_hash,
            }
        else:
            utxos = cached["utxos"]

        total = sum(
            sum(o["value"] for o in u["outputs"] if o["to"] == legacy_address)
            for u in utxos
        )

        if total <= 0:
            return

        if config.peer_type == PEER_TYPES.POOL.value:
            config.app_log.info(
                "NodeKeyRotationManager: skipping legacy sweep for pool node."
            )
            return

        config.app_log.info(
            "NodeKeyRotationManager: sweeping %.8f YDA from legacy address %s to KEL address %s",
            total,
            legacy_address,
            sweep_target,
        )
        await self._sweep_legacy_to_kel(sweep_target=sweep_target, total=total)
        self._kel_balance_cache.pop(legacy_address, None)

    async def _sweep_legacy_to_kel(self, sweep_target: str, total: float):
        """Build and broadcast a transaction sweeping legacy address UTXOs to
        ``sweep_target``, signed by ``config.private_key``.
        """
        from yadacoin.core.transaction import Transaction

        config = self.config
        try:
            txn = Transaction(
                txn_time=int(time.time()),
                public_key=config.public_key,
                outputs=[{"to": sweep_target, "value": total}],
                inputs=[],
                fee=0.0,
                masternode_fee=0.0,
                version=7,
                prerotated_key_hash="",
                twice_prerotated_key_hash="",
                public_key_hash="",
                prev_public_key_hash="",
                relationship="",
                relationship_hash="",
                rid="",
                dh_public_key="",
            )
            await txn.do_money()

            txn.hash = await txn.generate_hash()
            txn.transaction_signature = NodeKeyRotationManager._sign(
                config.private_key, txn.hash
            )

            await config.mongo.async_db.miner_transactions.replace_one(
                {"id": txn.transaction_signature},
                txn.to_dict(),
                upsert=True,
            )

            config.app_log.info(
                "NodeKeyRotationManager: legacy sweep txn submitted (id=%s, to=%s, amount=%.8f)",
                txn.transaction_signature,
                sweep_target,
                total,
            )

            if "node" in config.modes:
                try:
                    async for peer_stream in config.peer.get_sync_peers():
                        await config.nodeShared.write_params(
                            peer_stream, "newtxn", {"transaction": txn.to_dict()}
                        )
                        if peer_stream.peer.protocol_version > 1:
                            config.nodeClient.retry_messages[
                                (
                                    peer_stream.peer.rid,
                                    "newtxn",
                                    txn.transaction_signature,
                                )
                            ] = {"transaction": txn.to_dict()}
                except Exception as exc:
                    config.app_log.warning(
                        "NodeKeyRotationManager: legacy sweep broadcast error: %s", exc
                    )
        except Exception as exc:
            config.app_log.error("NodeKeyRotationManager: legacy sweep failed: %s", exc)

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    @classmethod
    def generate_deterministic_signature(cls, message: str):
        config = Config()
        if not hasattr(config, "kel_anchor_private_key"):
            return ""
        key = PrivateKey.from_hex(config.kel_anchor_private_key)
        signature = key.sign(message.encode("utf-8"))
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def _sign(private_key: str, message: str) -> str:
        """Raw signing primitive — hedged RFC 6979 with 32 bytes of OS entropy.

        Use only when the exact key position has already been derived by the
        caller (e.g. rotation logic signing with a specific K_n).  For all
        other node-level signing use ``await manager.generate_signature(message)``.
        """
        nonce_data = _ffi.from_buffer(os.urandom(32))
        key = _CoincurvePrivateKey.from_hex(private_key)
        signature = key.sign(
            message.encode("utf-8"), custom_nonce=(_ffi.NULL, nonce_data)
        )
        return base64.b64encode(signature).decode("utf-8")

    async def generate_signature(self, message: str) -> str:
        """Sign *message* with the node's current KEL tip key.

        Delegates to ``advance_auth_ratchet``, which already maintains
        ``self._auth_ratchet_key`` as the authoritative next-unused key by
        tracking all three collections (blocks, miner_transactions,
        key_event_log) at init time and advancing in memory from there.
        No redundant DB derivation needed here.
        """
        priv, _pub, _conf_priv, _conf_pub, tpkh = await self.advance_auth_ratchet()
        return _pub, self._sign(priv, message)


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _fatal(message: str) -> None:
    """Print message to stderr and exit the process.

    If NodeKeyRotationManager._TEST_MODE is set, raises RuntimeError
    instead of exiting so test harnesses can assert on the message.
    """
    print(message, file=sys.stderr)
    if getattr(NodeKeyRotationManager, "_TEST_MODE", False):
        raise RuntimeError(message)
    sys.exit(1)
