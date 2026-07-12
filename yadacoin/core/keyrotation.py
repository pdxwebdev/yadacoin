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

import asyncio
import base64
import hashlib
import hmac as _hmac
import os
import struct
import sys
import time

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey as _CoincurvePrivateKey
from coincurve._libsecp256k1 import ffi as _ffi
from coincurve.keys import PrivateKey

from yadacoin.core.config import Config

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
        self._ratchet_lock: asyncio.Lock = asyncio.Lock()

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
            kel = await KeyEventLog.build_from_public_key(k0_pub_hex)
        except Exception as exc:
            config.app_log.error("NodeKeyRotationManager: error checking KEL: %s", exc)
            kel = []

        if kel:
            config.app_log.info(
                "NodeKeyRotationManager: KEL inception found (depth=%d, inception_id=%s)",
                len(kel),
                kel[0].transaction_signature,
            )
            self._inception_txn_id = kel[0].transaction_signature

            self.config.username = kel[0].relationship.username
            self.config.username_signature = kel[0].relationship.username_signature

            # If already on-chain, finalise immediately
            inception_onchain = not getattr(kel[0], "mempool", False)
            if inception_onchain:
                await self._try_finalise(kel, k0, second_factor)
            else:
                # Inception is mempool-only; derive K_n from depth-0 so
                # the node can start signing with it immediately.
                self._update_active_kel_key(kel, k0, second_factor)
        else:
            config.app_log.warning(
                "NodeKeyRotationManager: no KEL inception found for derived key %s; "
                "creating inception transaction automatically.",
                k0_pub_hex,
            )
            await self._create_inception(k0, second_factor, k0_pub_hex)

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
                kel = await KeyEventLog.build_from_public_key(
                    k0_pub_hex, onchain_only=True
                )
            except Exception as exc:
                config.app_log.debug(
                    "NodeKeyRotationManager: checker KEL error: %s", exc
                )
                return

            if not kel:
                return  # inception not yet mined

            await self._try_finalise(kel, k0, second_factor)
            await self._check_and_sweep_legacy_funds(kel)
        else:
            # Inception confirmed — skip the expensive KEL build;
            # only check for legacy funds to sweep.
            try:
                kel = await KeyEventLog.build_from_public_key(
                    k0_pub_hex, onchain_only=True
                )
            except Exception as exc:
                config.app_log.debug(
                    "NodeKeyRotationManager: checker KEL error: %s", exc
                )
                return
            if kel:
                await self._check_and_sweep_legacy_funds(kel)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Off-chain auth ratchet
    # ------------------------------------------------------------------

    async def advance_auth_ratchet(
        self, block=None, txn=None, self_output=None
    ) -> tuple:
        """Advance the off-chain signing ratchet by one step and return
        ``(current_priv_hex, current_pub_hex, next_priv_hex, next_pub_hex)``.

        The caller must produce TWO signatures for authentication:
          1. current key signs the challenge  — proves possession of K_{n+i}
          2. next key signs the challenge     — proves knowledge of K_{n+i+1}

        An attacker who steals only K_{n+i} cannot produce the confirming
        signature without the SECOND_FACTOR needed to derive K_{n+i+1}.

        Each step:
        1. Derives K_{n+i+1} from K_{n+i} using ``derive_secure_path``
        2. Creates a zero-value KEL rotation transaction and submits it to the
           mempool.  These transactions propagate via normal newtxn gossip and
           are available for verifiers to look up by public_key.  Over time
           miners pick them up and they become on-chain confirmations.
        3. Increments the counter; triggers ``_queue_reanchor``
           every OFFCHAIN_ANCHOR_INTERVAL events

        A mutex (``self._ratchet_lock``) ensures this method is never entered
        concurrently, preventing two coroutines from reading the same
        ``self._auth_ratchet_key`` before either has written the next key back.
        """
        async with self._ratchet_lock:
            config = self.config

            # KEL keys are required — the WIF key is considered compromised.
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

            # Initialise ratchet from current on-chain anchor key if not yet set
            if self._auth_ratchet_key is None:
                kel_cc = getattr(config, "kel_anchor_chain_code", None)
                if kel_cc:
                    # Use the BIP32 chain code stored alongside the anchor private key.
                    _base_ratchet = {
                        "private_key": bytes.fromhex(kel_priv),
                        "chain_code": bytes.fromhex(kel_cc),
                    }
                else:
                    _fatal(
                        "\n"
                        "═══════════════════════════════════════════════════════════════\n"
                        "  FATAL: kel_anchor_chain_code missing. Cannot initialise ratchet.\n"
                        "═══════════════════════════════════════════════════════════════\n"
                    )
                # Restore position from key_event_log tip so restarts pick up where
                # they left off instead of starting over from K_n.
                # Use K0 pubkey as the stable root identifier — it never changes.
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
                # Unconditional init: fast-forward from _base_ratchet by however
                # many steps are in the tip (0 on first start = fresh anchor).
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

            # Derive next ratchet key (the "confirming" key)
            next_key = derive_secure_path(
                prev_key["private_key"], prev_key["chain_code"], second_factor
            )
            next_priv_obj = _CoincurvePrivateKey(next_key["private_key"])
            next_pub_hex = next_priv_obj.public_key.format(compressed=True).hex()
            next_pub_bytes = next_priv_obj.public_key.format(compressed=True)
            next_address = str(P2PKHBitcoinAddress.from_pubkey(next_pub_bytes))

            # Derive two-steps-ahead for twice_prerotated_key_hash
            two_ahead = derive_secure_path(
                next_key["private_key"], next_key["chain_code"], second_factor
            )
            two_ahead_pub = _CoincurvePrivateKey(
                two_ahead["private_key"]
            ).public_key.format(compressed=True)
            two_ahead_address = str(P2PKHBitcoinAddress.from_pubkey(two_ahead_pub))

            from yadacoin.core.transaction import Transaction

            # anchor_public_key is always K0 — the stable inception key that
            # identifies this node's entire KEL chain across all re-anchors.
            anchor_pub = (
                (
                    _CoincurvePrivateKey(self._k0["private_key"])
                    .public_key.format(compressed=True)
                    .hex()
                )
                if self._k0
                else (getattr(config, "kel_anchor_public_key", None) or prev_pub_hex)
            )

            if txn:
                ratchet_txn = txn
                ratchet_txn.prerotated_key_hash = next_address
                ratchet_txn.twice_prerotated_key_hash = two_ahead_address
                ratchet_txn.public_key_hash = prev_address
                ratchet_txn.prev_public_key_hash = self._auth_ratchet_prev_pkh or ""
            else:
                ratchet_txn = Transaction(
                    public_key=prev_pub_hex,
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
            if self_output:
                self_output["to"] = two_ahead_address
            ratchet_txn.hash = await ratchet_txn.generate_hash()
            ratchet_txn.transaction_signature = NodeKeyRotationManager._sign(
                prev_key["private_key"].hex(), ratchet_txn.hash
            )
            if block:
                try:
                    await self._queue_reanchor(block=block)
                except Exception as exc:
                    config.app_log.warning(
                        "NodeKeyRotationManager: re-anchor error: %s", exc
                    )
                block.hash = await ratchet_txn.generate_hash()
                block.signature = NodeKeyRotationManager._sign(
                    prev_key["private_key"].hex(), ratchet_txn.hash
                )

            self._auth_counter += 1

            try:
                # Store in key_event_log (off-chain record) — NOT miner_transactions.
                # Individual ratchet steps are verified but not mined; only the
                # periodic anchor transactions (every OFFCHAIN_ANCHOR_INTERVAL steps,
                # from _queue_reanchor) go into the mempool to be mined.
                await config.mongo.async_db.key_event_log.replace_one(
                    # Filter by public_key_hash — uniquely identifies this key
                    # position in the chain.  Using the transaction id/signature
                    # would create a new document on every advance because the
                    # signature changes (it's time-stamped).
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

            # Advance ratchet state
            self._auth_ratchet_key = next_key
            self._auth_ratchet_pub = next_pub_hex
            self._auth_ratchet_prev_pkh = prev_address

            if block is None:
                # Trigger re-anchor when interval is reached
                if self._auth_counter % self.OFFCHAIN_ANCHOR_INTERVAL == 0:
                    try:
                        await self._queue_reanchor(block=block)
                    except Exception as exc:
                        config.app_log.warning(
                            "NodeKeyRotationManager: re-anchor error: %s", exc
                        )

            # Return both current (signing) and next (confirming) keys
            return (
                prev_key["private_key"].hex(),
                prev_pub_hex,
                next_key["private_key"].hex(),
                next_pub_hex,
                two_ahead_address,
            )

    async def _queue_reanchor(self, block=None):
        """Queue an on-chain UNCONFIRMED+CONFIRMING re-anchor pair.

        Uses the current ``kel[-1].prerotated_key_hash`` key as the UNCONFIRMED
        signer and jumps ``twice_prerotated_key_hash`` forward by
        OFFCHAIN_ANCHOR_INTERVAL + 1 steps, setting up the next off-chain cycle.
        """
        config = self.config
        k0 = self._k0
        second_factor = self._second_factor or _read_second_factor()
        if not k0 or not second_factor:
            return

        from yadacoin.core.keyeventlog import KeyEventLog
        from yadacoin.core.transaction import Transaction

        # Resolve current on-chain KEL tail
        kel_pub = getattr(config, "kel_anchor_public_key", None)
        if not kel_pub:
            return

        # Find the inception K0 pub key to build from (walk from k0)
        k0_pub_hex = (
            _CoincurvePrivateKey(k0["private_key"])
            .public_key.format(compressed=True)
            .hex()
        )
        try:
            kel = await KeyEventLog.build_from_public_key(k0_pub_hex, onchain_only=True)
        except Exception:
            return
        if not kel:
            return

        # KEL depth n; next expected on-chain signer is K_n
        n = len(kel)

        # Derive K_n (UNCONFIRMED signer) and K_{n+1} (CONFIRMING signer)
        cur = k0
        for _ in range(n):
            cur = derive_secure_path(
                cur["private_key"], cur["chain_code"], second_factor
            )
        kn = cur  # UNCONFIRMED signer

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
        txn = True
        while txn:
            txn = await self.config.mongo.async_db.key_event_log.find_one(
                {"prev_public_key_hash": search_address}
            )
            if txn:
                # Derive the JUMP target: K_{n + INTERVAL + 1} for UNCONFIRMED.twice_prerotated
                # and CONFIRMING.prerotated.  K_{n + INTERVAL + 2} for CONFIRMING.twice_prerotated.
                jump_cur = kn1
                for _ in range(prev_txn["counter"]):
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

        prev_pkh = kel[-1].public_key_hash

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
            twice_prerotated_key_hash=jump_address,  # JUMP
            public_key_hash=kn_address,
            prev_public_key_hash=prev_pkh,
            relationship="reanchor",
            relationship_hash=hashlib.sha256(b"reanchor").digest().hex(),
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
            prerotated_key_hash=jump_address,  # matches UNCONFIRMED.twice_prerotated ✓
            twice_prerotated_key_hash=jump2_address,
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
        if block:
            block.transactions.extend([unconfirmed_txn, confirming_txn])
        else:
            for txn in (unconfirmed_txn, confirming_txn):
                await config.mongo.async_db.miner_transactions.replace_one(
                    {"id": txn.transaction_signature}, txn.to_dict(), upsert=True
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

    async def _try_finalise(self, kel, k0: dict, second_factor: str):
        """Update the active KEL signing key on config once the inception is
        confirmed on-chain.  The on-chain identity announcement is the
        canonical anchor.
        """
        self._update_active_kel_key(kel, k0, second_factor)
        self._inception_complete = True

    def _update_active_kel_key(self, kel, k0: dict, second_factor: str):
        """Derive K_n (one step past the last on-chain KEL entry) and store it
        on config so all signing operations can use it immediately."""
        config = self.config
        cur = k0
        for _ in range(len(kel)):
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
        if kel:
            self._auth_ratchet_prev_pkh = kel[-1].public_key_hash

        config.app_log.info(
            "NodeKeyRotationManager: active KEL signing key updated "
            "(depth=%d, address=%s)",
            len(kel),
            kn_address,
        )

    async def _check_and_sweep_legacy_funds(self, kel):
        """Sweep UTXOs at the legacy node address (P2PKH of config.public_key)
        to ``kel[-1].prerotated_key_hash``.

        This transitions funds from the potentially compromised WIF-derived
        address to the KEL-protected address.  The balance cache is keyed by
        block height + hash so we only query the chain when the tip advances.
        """
        config = self.config
        legacy_address = config.address
        sweep_target = kel[-1].prerotated_key_hash

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

        config.app_log.info(
            "NodeKeyRotationManager: sweeping %.8f YDA from legacy address %s → KEL address %s",
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
    """Print message to stderr and exit the process."""
    print(message, file=sys.stderr)
    sys.exit(1)
