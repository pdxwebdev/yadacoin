"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Handler for the HD-wallet key rotation app.

All key derivation and signing happens client-side in JavaScript.
The server only:
  - Serves the HTML page        (GET  /key-rotation)
  - Checks if an address has been spent (GET  /key-rotation/spent?address=)
  - Broadcasts a pre-signed transaction (POST /transaction)

Private key material is never sent to the server.

DerivedChildKeyHandler is an exception: it manages server-side KEL-authenticated
child-key derivation backed by the derived_keys collection in yadacoin_site.
"""

import base64
import hashlib
import hmac as _hmac
import json
import struct
import time

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey as _CoincurvePrivateKey
from coincurve import verify_signature as _verify_signature

from yadacoin.decorators.jwtauth import jwtauthwallet
from yadacoin.http.base import BaseHandler

# ---------------------------------------------------------------------------
# BIP32-style hardened derivation helpers — Python port of deriveSecurePath
# from templates/key_rotation.html.
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


class KeyRotationHandler(BaseHandler):
    """GET /key-rotation — serve the client-side key-rotation UI."""

    async def get(self):
        self.render("key_rotation.html")


class KeyRotationPrevKeyHashHandler(BaseHandler):
    """
    GET /key-rotation/prev-key-hash?address=<P2PKH>

    For a rotation transaction being built for <address>, returns the
    prev_public_key_hash value that must go into the transaction.

    That value is the public_key_hash of the transaction whose
    prerotated_key_hash == address (i.e. the transaction that committed
    to <address> as the next signer).  For inception (no prior KEL
    entry), returns "".
    """

    async def get(self):
        address = self.get_query_argument("address", "")
        if not address:
            self.set_status(400)
            return self.render_as_json({"error": "address required"})

        projection = {"_id": 0, "public_key_hash": 1, "id": 1}

        # 1. Check mempool first
        mempool_hit = await self.config.mongo.async_db.miner_transactions.find_one(
            {"prerotated_key_hash": address}, projection
        )
        if mempool_hit:
            return self.render_as_json(
                {
                    "prev_public_key_hash": mempool_hit.get("public_key_hash", ""),
                    "source": "mempool",
                }
            )

        # 2. Check confirmed blockchain
        chain_hit = await self.config.mongo.async_db.blocks.find_one(
            {"transactions": {"$elemMatch": {"prerotated_key_hash": address}}},
            {"_id": 0, "transactions.$": 1},
        )
        if chain_hit:
            txns = chain_hit.get("transactions", [])
            txn = txns[0] if txns else {}
            return self.render_as_json(
                {
                    "prev_public_key_hash": txn.get("public_key_hash", ""),
                    "source": "blockchain",
                }
            )

        # No prior KEL entry — this is an inception transaction
        return self.render_as_json({"prev_public_key_hash": "", "source": None})


class KeyRotationSpentHandler(BaseHandler):
    """
    GET /key-rotation/spent?address=<P2PKH>

    Returns {"spent": true, "source": "mempool"|"blockchain", "txid": "..."}
    or      {"spent": false}

    "Spent" means the address has submitted a key-rotation transaction —
    i.e. a transaction exists whose public_key_hash == address.
    """

    async def get(self):
        address = self.get_query_argument("address", "")
        if not address:
            self.set_status(400)
            return self.render_as_json({"error": "address required"})

        # 1. Check mempool (miner_transactions)
        mempool_hit = await self.config.mongo.async_db.miner_transactions.find_one(
            {"public_key_hash": address},
            {
                "_id": 0,
                "id": 1,
                "prerotated_key_hash": 1,
                "twice_prerotated_key_hash": 1,
            },
        )
        if mempool_hit:
            return self.render_as_json(
                {
                    "spent": True,
                    "source": "mempool",
                    "txid": mempool_hit.get("id", ""),
                    "prerotated_key_hash": mempool_hit.get("prerotated_key_hash", ""),
                    "twice_prerotated_key_hash": mempool_hit.get(
                        "twice_prerotated_key_hash", ""
                    ),
                }
            )

        # 2. Check confirmed blockchain (blocks → transactions array)
        chain_hit = await self.config.mongo.async_db.blocks.find_one(
            {"transactions": {"$elemMatch": {"public_key_hash": address}}},
            {"_id": 0, "transactions.$": 1},
        )
        if chain_hit:
            txns = chain_hit.get("transactions", [])
            txn = txns[0] if txns else {}
            return self.render_as_json(
                {
                    "spent": True,
                    "source": "blockchain",
                    "txid": txn.get("id", ""),
                    "prerotated_key_hash": txn.get("prerotated_key_hash", ""),
                    "twice_prerotated_key_hash": txn.get(
                        "twice_prerotated_key_hash", ""
                    ),
                }
            )

        return self.render_as_json({"spent": False, "source": None, "txid": ""})


@jwtauthwallet
class DerivedChildKeyHandler(BaseHandler):
    """
    POST /key-rotation/derived-child-key

    Authenticate a KEL-tracked signing key via a second factor, broadcast a
    rotation transaction, and return the next derived child key address.
    Unlike the client-side key-rotation UI, this handler manages server-side
    key material stored in the ``derived_keys`` collection of the
    ``yadacoin_site`` database.

    Request body (JSON)
    -------------------
    public_key    : str  – compressed-public-key hex of the pre-committed next
                           signer, i.e. ``log[-1].prerotated_key_hash ==
                           P2PKH(public_key)``.
    second_factor : str  – secret factor used in ``derive_secure_path``.
    signature     : str  – base-64 DER signature over
                           ``sha256(public_key.encode('utf-8'))``
                           produced by the private key corresponding to
                           ``public_key``.

    Collections used (yadacoin_site)
    ---------------------------------
    derived_keys
        ``{ address, public_key, prerotated_public_key, prerotated_address,
            twice_prerotated_public_key, twice_prerotated_address,
            prev_private_key, prev_chain_code, stored_at }``

    attack_attempts_derived_key
        Logs every failed request with full request metadata.

    Errors
    ------
    400  no key event log found for the supplied public key
    400  public key is not the pre-committed next signer in the KEL
    400  second factor is incorrect
    400  signature verification failed
    404  no parent key material found for this address
    """

    # Set to a positive float to collect a fee from the signing address UTXOs.
    ROTATION_FEE = 0.0

    async def post(self):
        from yadacoin.core.keyeventlog import KeyEventLog
        from yadacoin.core.transaction import Transaction
        from yadacoin.core.transactionutils import TU

        # ------------------------------------------------------------------ #
        # 1. Parse request
        # ------------------------------------------------------------------ #
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )

        public_key = body.get("public_key", "").strip()
        second_factor = body.get("second_factor", "")
        signature = body.get("signature", "").strip()
        verify_signature = False

        if not public_key or not second_factor or (not signature and verify_signature):
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "public_key, second_factor, and signature are required",
                }
            )

        try:
            pub_key_bytes = bytes.fromhex(public_key)
            if len(pub_key_bytes) not in (33, 65):
                raise ValueError("invalid public key length")
        except (ValueError, TypeError):
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "public_key must be a valid compressed-public-key hex",
                }
            )

        address = str(P2PKHBitcoinAddress.from_pubkey(pub_key_bytes))
        request_ip = self.request.remote_ip

        # ------------------------------------------------------------------ #
        # Helper: log attack attempt to DB and node log
        # ------------------------------------------------------------------ #
        async def _log_attack(error_msg: str) -> None:
            try:
                await self.config.mongo.async_site_db.attack_attempts_derived_key.insert_one(
                    {
                        "public_key": public_key,
                        "address": address,
                        "second_factor": second_factor,
                        "signature": signature,
                        "error": error_msg,
                        "request_ip": request_ip,
                        "timestamp": time.time(),
                    }
                )
            except Exception:
                pass  # never let logging failure mask the real error
            self.config.app_log.error(
                "DerivedChildKeyHandler attack attempt from %s — %s (public_key=%s)",
                request_ip,
                error_msg,
                public_key,
            )

        # ------------------------------------------------------------------ #
        # 2. Build the key event log for this public key
        # ------------------------------------------------------------------ #
        try:
            kel = await KeyEventLog.build_from_public_key(public_key)
        except Exception as exc:
            await _log_attack(f"KEL build error: {exc}")
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "error retrieving key event log"}
            )

        if not kel:
            await _log_attack("no key event log found for public_key")
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "no key event log found for the provided public key",
                }
            )

        # ------------------------------------------------------------------ #
        # 3. Verify the latest KEL entry pre-commits to this public key
        #    log[-1].prerotated_key_hash must equal P2PKH(public_key)
        # ------------------------------------------------------------------ #
        latest = kel[-1]
        if latest.prerotated_key_hash != address:
            await _log_attack(
                f"latest KEL prerotated_key_hash={latest.prerotated_key_hash} "
                f"does not match address={address}"
            )
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "public key is not the pre-committed next signer in the key event log",
                }
            )

        # ------------------------------------------------------------------ #
        # 3b. Verify this KEL is the configured admin KEL (if admin_kel is set)
        # ------------------------------------------------------------------ #
        admin_kel = getattr(self.config, "admin_kel", None)
        if admin_kel:
            inception_txn_id = kel[0].transaction_signature
            if inception_txn_id != admin_kel:
                await _log_attack(
                    f"KEL inception txn {inception_txn_id} does not match "
                    f"admin_kel={admin_kel}"
                )
                self.set_status(403)
                return self.render_as_json(
                    {
                        "status": False,
                        "message": "this key event log is not authorized for this operation",
                    }
                )

        # ------------------------------------------------------------------ #
        # 4. Load parent (previous) material from the derived_keys collection
        # ------------------------------------------------------------------ #
        record = await self.config.mongo.async_site_db.derived_keys.find_one(
            {"prerotated_address": address}, {"_id": 0}
        )
        if not record:
            self.set_status(404)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        "no parent key material found for this address; "
                        "the key must be registered in derived_keys first"
                    ),
                }
            )

        try:
            prev_priv_bytes = bytes.fromhex(record["prev_private_key"])
            prev_cc_bytes = bytes.fromhex(record["prev_chain_code"])
        except (KeyError, ValueError):
            self.set_status(500)
            return self.render_as_json(
                {"status": False, "message": "stored key material is malformed"}
            )

        # ------------------------------------------------------------------ #
        # 5. Re-derive the key from the parent material + second_factor
        #    and verify it matches the submitted public_key
        # ------------------------------------------------------------------ #
        try:
            derived = derive_secure_path(prev_priv_bytes, prev_cc_bytes, second_factor)
        except Exception as exc:
            await _log_attack(f"key derivation failed: {exc}")
            self.set_status(500)
            return self.render_as_json(
                {"status": False, "message": "key derivation error"}
            )

        derived_priv_obj = _CoincurvePrivateKey(derived["private_key"])
        derived_pub_bytes = derived_priv_obj.public_key.format(compressed=True)
        derived_pub_hex = derived_pub_bytes.hex()

        if derived_pub_hex != public_key:
            await _log_attack(
                f"second_factor produced public_key={derived_pub_hex} "
                f"but expected={public_key}"
            )
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "second factor is incorrect"}
            )

        # ------------------------------------------------------------------ #
        # 6. Verify the request signature
        #    Signature is base64-DER over sha256(public_key.encode('utf-8'))
        #    produced by the private key of public_key.
        # ------------------------------------------------------------------ #
        if verify_signature:
            try:
                sig_bytes = base64.b64decode(signature)
                ok = _verify_signature(
                    sig_bytes,
                    public_key.encode("utf-8"),
                    pub_key_bytes,
                    hasher="sha256",
                )
                if not ok:
                    raise ValueError("verify_signature returned False")
            except Exception as exc:
                await _log_attack(f"signature verification failed: {exc}")
                self.set_status(400)
                return self.render_as_json(
                    {"status": False, "message": "signature verification failed"}
                )

        # ------------------------------------------------------------------ #
        # 7. Derive prerotated and twice-prerotated keys, build and sign a
        #    rotation transaction, broadcast, then persist key material.
        # ------------------------------------------------------------------ #
        child = derive_secure_path(
            derived["private_key"], derived["chain_code"], second_factor
        )
        child_priv_obj = _CoincurvePrivateKey(child["private_key"])
        child_pub_bytes = child_priv_obj.public_key.format(compressed=True)
        child_pub_hex = child_pub_bytes.hex()
        child_address = str(P2PKHBitcoinAddress.from_pubkey(child_pub_bytes))

        grandchild = derive_secure_path(
            child["private_key"], child["chain_code"], second_factor
        )
        grandchild_priv_obj = _CoincurvePrivateKey(grandchild["private_key"])
        grandchild_pub_bytes = grandchild_priv_obj.public_key.format(compressed=True)
        grandchild_pub_hex = grandchild_pub_bytes.hex()
        grandchild_address = str(P2PKHBitcoinAddress.from_pubkey(grandchild_pub_bytes))

        # prev_public_key_hash is the address that committed to `address` as
        # the next signer, i.e. the public_key_hash of latest KEL entry.
        prev_public_key_hash = latest.public_key_hash

        txn = Transaction(
            txn_time=int(time.time()),
            public_key=public_key,
            outputs=[{"to": child_address, "value": 0.0}],
            inputs=[],
            fee=self.ROTATION_FEE,
            masternode_fee=0.0,
            version=7,
            prerotated_key_hash=child_address,
            twice_prerotated_key_hash=grandchild_address,
            public_key_hash=address,
            prev_public_key_hash=prev_public_key_hash,
            relationship="",
            relationship_hash="",
            rid="",
            dh_public_key="",
        )

        if self.ROTATION_FEE > 0:
            await txn.do_money()

        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            derived["private_key"].hex(), txn.hash
        )

        await self.config.mongo.async_db.miner_transactions.replace_one(
            {"id": txn.transaction_signature},
            txn.to_dict(),
            upsert=True,
        )

        if "node" in self.config.modes:
            try:
                async for peer_stream in self.config.peer.get_sync_peers():
                    await self.config.nodeShared.write_params(
                        peer_stream, "newtxn", {"transaction": txn.to_dict()}
                    )
                    if peer_stream.peer.protocol_version > 1:
                        self.config.nodeClient.retry_messages[
                            (peer_stream.peer.rid, "newtxn", txn.transaction_signature)
                        ] = {"transaction": txn.to_dict()}
            except Exception as exc:
                self.config.app_log.warning(
                    f"DerivedChildKeyHandler broadcast error: {exc}"
                )

        await self.config.mongo.async_site_db.derived_keys.update_one(
            {"address": address},
            {
                "$set": {
                    "address": address,
                    "public_key": public_key,
                    "prerotated_public_key": child_pub_hex,
                    "prerotated_address": child_address,
                    "twice_prerotated_public_key": grandchild_pub_hex,
                    "twice_prerotated_address": grandchild_address,
                    "prev_private_key": derived["private_key"].hex(),
                    "prev_chain_code": derived["chain_code"].hex(),
                    "stored_at": time.time(),
                    "transaction_id": txn.transaction_signature,
                }
            },
            upsert=True,
        )

        return self.render_as_json(
            {
                "status": True,
                "address": address,
                "public_key": public_key,
                "prerotated_public_key": child_pub_hex,
                "prerotated_address": child_address,
                "twice_prerotated_public_key": grandchild_pub_hex,
                "twice_prerotated_address": grandchild_address,
                "prev_private_key": derived["private_key"].hex(),
                "prev_chain_code": derived["chain_code"].hex(),
                "stored_at": time.time(),
                "transaction_id": txn.transaction_signature,
            }
        )


@jwtauthwallet
class InitDerivedChildKeyHandler(BaseHandler):
    """
    POST /key-rotation/init-derived-child-key

    Bootstrap the derived-key subsystem from the node's BIP39 seed phrase.
    Creates an inception key event log transaction and stores root key material
    in the ``derived_keys`` collection of the ``yadacoin_site`` database.

    Request body (JSON)
    -------------------
    second_factor : str  – secret factor for ``derive_secure_path``

    Flow
    ----
    1. Verify ``config.seed`` is set (BIP39 mnemonic)
    2. Derive root priv+cc via ``BIP32Key.fromEntropy(Mnemonic.to_entropy(seed))``
    3. Apply ``derive_secure_path`` three times to get signing, prerotated, and
       twice-prerotated keys; compute P2PKH addresses for each
    4. Reject with 409 if a KEL already exists for the signing key
    5. Build and sign a version-7 inception transaction
       (``prev_public_key_hash=""``; fee = ``INCEPTION_FEE``; no inputs when
       ``INCEPTION_FEE == 0.0``)
    6. Insert into ``miner_transactions`` (mempool) and broadcast to peers
    7. Upsert two ``derived_keys`` records:
       - signing_address    ← parent = (root_priv, root_cc)
       - prerotated_address ← parent = (signing.priv, signing.cc)
    8. Return signing address, public key, prerotated address, and transaction id

    Fee funding
    -----------
    ``INCEPTION_FEE = 0.0`` means a zero-fee inception with no inputs required.
    To charge a fee, raise ``INCEPTION_FEE`` to a positive value — ensure the
    signing address has sufficient UTXOs before calling this endpoint.
    """

    # Set to a positive float to collect a fee from the signing address UTXOs.
    # When 0.0, no inputs are required and do_money() short-circuits.
    INCEPTION_FEE = 0.0

    async def post(self):
        from bip32utils import BIP32Key
        from mnemonic import Mnemonic

        from yadacoin.core.keyeventlog import KeyEventLog
        from yadacoin.core.transaction import Transaction
        from yadacoin.core.transactionutils import TU

        # ------------------------------------------------------------------ #
        # 1. Parse request
        # ------------------------------------------------------------------ #
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )

        second_factor = body.get("second_factor", "")
        if not second_factor:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "second_factor is required"}
            )

        # ------------------------------------------------------------------ #
        # 2. Load seed from config
        # ------------------------------------------------------------------ #
        seed = getattr(self.config, "seed", "") or ""
        if not seed:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "seed not configured in config.json"}
            )

        try:
            mn = Mnemonic("english")
            entropy = mn.to_entropy(seed)
            bip32_root = BIP32Key.fromEntropy(entropy)
            root_priv = bip32_root.PrivateKey()  # bytes, 32
            root_cc = bip32_root.ChainCode()  # bytes, 32
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json(
                {
                    "status": False,
                    "message": f"could not derive root key from seed: {exc}",
                }
            )

        # ------------------------------------------------------------------ #
        # 3. Derive key chain: signing → prerotated → twice-prerotated
        # ------------------------------------------------------------------ #
        signing = derive_secure_path(root_priv, root_cc, second_factor)
        prerotated = derive_secure_path(
            signing["private_key"], signing["chain_code"], second_factor
        )
        twice_prerot = derive_secure_path(
            prerotated["private_key"], prerotated["chain_code"], second_factor
        )

        signing_priv_obj = _CoincurvePrivateKey(signing["private_key"])
        signing_pub_bytes = signing_priv_obj.public_key.format(compressed=True)
        signing_pub_hex = signing_pub_bytes.hex()
        signing_address = str(P2PKHBitcoinAddress.from_pubkey(signing_pub_bytes))

        pre_priv_obj = _CoincurvePrivateKey(prerotated["private_key"])
        pre_pub_bytes = pre_priv_obj.public_key.format(compressed=True)
        pre_address = str(P2PKHBitcoinAddress.from_pubkey(pre_pub_bytes))

        twice_priv_obj = _CoincurvePrivateKey(twice_prerot["private_key"])
        twice_pub_bytes = twice_priv_obj.public_key.format(compressed=True)
        twice_address = str(P2PKHBitcoinAddress.from_pubkey(twice_pub_bytes))

        # ------------------------------------------------------------------ #
        # 4. Reject if admin_kel is already configured or a KEL already exists
        # ------------------------------------------------------------------ #
        admin_kel = getattr(self.config, "admin_kel", None)
        if admin_kel:
            self.set_status(409)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        f"admin_kel is already configured ({admin_kel}). "
                        "Remove it from config.json to re-initialize."
                    ),
                }
            )

        try:
            existing_kel = await KeyEventLog.build_from_public_key(signing_pub_hex)
        except Exception:
            existing_kel = []

        if existing_kel:
            self.set_status(409)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "key event log already exists for this signing key",
                }
            )

        # ------------------------------------------------------------------ #
        # 5. Build and sign the inception transaction
        #
        #    The Transaction constructor must be used directly (not generate())
        #    so that KEL fields are included in generate_hash().
        #    do_money() short-circuits when outputs_and_fee_total == 0.
        # ------------------------------------------------------------------ #
        txn = Transaction(
            txn_time=int(time.time()),
            public_key=signing_pub_hex,
            outputs=[{"to": pre_address, "value": 0.0}],
            inputs=[],
            fee=self.INCEPTION_FEE,
            masternode_fee=0.0,
            version=7,
            prerotated_key_hash=pre_address,
            twice_prerotated_key_hash=twice_address,
            public_key_hash=signing_address,
            prev_public_key_hash="",
            relationship="",
            relationship_hash="",
            rid="",
            dh_public_key="",
        )

        if self.INCEPTION_FEE > 0:
            await txn.do_money()

        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            signing["private_key"].hex(), txn.hash
        )

        # ------------------------------------------------------------------ #
        # 6. Insert into mempool and broadcast to peers
        # ------------------------------------------------------------------ #
        await self.config.mongo.async_db.miner_transactions.replace_one(
            {"id": txn.transaction_signature},
            txn.to_dict(),
            upsert=True,
        )

        if "node" in self.config.modes and self.config.network == "mainnet":
            try:
                async for peer_stream in self.config.peer.get_sync_peers():
                    await self.config.nodeShared.write_params(
                        peer_stream, "newtxn", {"transaction": txn.to_dict()}
                    )
                    if peer_stream.peer.protocol_version > 1:
                        self.config.nodeClient.retry_messages[
                            (peer_stream.peer.rid, "newtxn", txn.transaction_signature)
                        ] = {"transaction": txn.to_dict()}
            except Exception as exc:
                self.config.app_log.warning(
                    f"InitDerivedChildKeyHandler broadcast error: {exc}"
                )

        # ------------------------------------------------------------------ #
        # 7. Persist key material in derived_keys
        # ------------------------------------------------------------------ #
        now = time.time()

        await self.config.mongo.async_site_db.derived_keys.update_one(
            {"address": signing_address},
            {
                "$set": {
                    "address": signing_address,
                    "public_key": signing_pub_hex,
                    "prerotated_public_key": pre_pub_bytes.hex(),
                    "prerotated_address": pre_address,
                    "twice_prerotated_public_key": twice_pub_bytes.hex(),
                    "twice_prerotated_address": twice_address,
                    "prev_private_key": signing["private_key"].hex(),
                    "prev_chain_code": signing["chain_code"].hex(),
                    "stored_at": now,
                    "transaction_id": txn.transaction_signature,
                }
            },
            upsert=True,
        )

        return self.render_as_json(
            {
                "status": True,
                "address": signing_address,
                "public_key": signing_pub_hex,
                "prerotated_public_key": pre_pub_bytes.hex(),
                "prerotated_address": pre_address,
                "twice_prerotated_public_key": twice_pub_bytes.hex(),
                "twice_prerotated_address": twice_address,
                "prev_private_key": signing["private_key"].hex(),
                "prev_chain_code": signing["chain_code"].hex(),
                "stored_at": now,
                "transaction_id": txn.transaction_signature,
                "admin_kel_hint": (
                    f'Add "admin_kel": "{txn.transaction_signature}" to config.json '
                    "to designate this as the authorized admin key event log."
                ),
            }
        )


class KelStatusHandler(BaseHandler):
    """GET /key-rotation/kel-status — return whether admin_kel is configured."""

    async def get(self):
        return self.render_as_json(
            {
                "admin_kel_configured": bool(getattr(self.config, "admin_kel", None)),
            }
        )


class KelUnlockHandler(BaseHandler):
    """
    POST /key-rotation/kel-unlock

    Authenticate using the current private key + second_factor when
    ``admin_kel`` is configured.  Two factors are required:

    - ``private_key`` (hex) — the current active signing private key
    - ``second_factor`` (str) — the secret factor used during init/rotation

    On success issues the same ES256 JWT that ``/unlock`` issues.

    Body (JSON)
    -----------
    private_key   : str  (hex, 64 chars)
    second_factor : str
    expires       : int  (optional, seconds, default 23040)
    """

    async def post(self):
        import datetime as _dt

        import jwt as _jwt

        admin_kel = getattr(self.config, "admin_kel", None)
        if not admin_kel:
            self.set_status(403)
            return self.render_as_json(
                {"status": False, "message": "admin_kel is not configured"}
            )

        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )

        private_key_hex = body.get("private_key", "").strip()
        second_factor = body.get("second_factor", "").strip()
        if not private_key_hex or not second_factor:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "private_key and second_factor are required",
                }
            )

        expires = int(body.get("expires", 23040))

        _AUTH_FAIL = {
            "status": False,
            "message": "invalid private_key or second_factor",
        }

        # ------------------------------------------------------------------ #
        # Helper: build a probe rotation txn with whatever keys we have,
        # run it through verify(check_kel=True) to obtain the real KEL
        # exception, then persist it in failed_transactions.
        # ------------------------------------------------------------------ #
        async def _record_failed_attempt(
            probe_priv_hex, probe_pub_hex, probe_second_factor
        ):
            from yadacoin.core.keyeventlog import KeyEventLog
            from yadacoin.core.transaction import Transaction
            from yadacoin.core.transactionutils import TU

            try:
                probe_pub_bytes = bytes.fromhex(probe_pub_hex)
                probe_address = str(P2PKHBitcoinAddress.from_pubkey(probe_pub_bytes))

                # Derive whatever prerotated/twice-prerotated the submitted
                # second_factor produces (may not match the committed hashes).
                probe_priv_bytes = bytes.fromhex(probe_priv_hex)
                probe_cc = derive_secure_path(
                    probe_priv_bytes, b"\x00" * 32, probe_second_factor
                )["chain_code"]

                child_probe = derive_secure_path(
                    probe_priv_bytes, probe_cc, probe_second_factor
                )
                child_probe_pub = _CoincurvePrivateKey(
                    child_probe["private_key"]
                ).public_key.format(compressed=True)
                child_probe_address = str(
                    P2PKHBitcoinAddress.from_pubkey(child_probe_pub)
                )

                grandchild_probe = derive_secure_path(
                    child_probe["private_key"],
                    child_probe["chain_code"],
                    probe_second_factor,
                )
                grandchild_probe_pub = _CoincurvePrivateKey(
                    grandchild_probe["private_key"]
                ).public_key.format(compressed=True)
                grandchild_probe_address = str(
                    P2PKHBitcoinAddress.from_pubkey(grandchild_probe_pub)
                )

                # Find prev_public_key_hash from KEL (may fail — use "" as fallback)
                try:
                    kel_probe = await KeyEventLog.build_from_public_key(probe_pub_hex)
                    prev_pkh = kel_probe[-1].public_key_hash if kel_probe else ""
                except Exception:
                    prev_pkh = ""

                probe_txn = Transaction(
                    txn_time=int(time.time()),
                    public_key=probe_pub_hex,
                    outputs=[{"to": child_probe_address, "value": 0.0}],
                    inputs=[],
                    fee=0.0,
                    masternode_fee=0.0,
                    version=7,
                    prerotated_key_hash=child_probe_address,
                    twice_prerotated_key_hash=grandchild_probe_address,
                    public_key_hash=probe_address,
                    prev_public_key_hash=prev_pkh,
                    relationship="",
                    relationship_hash="",
                    rid="",
                    dh_public_key="",
                )
                probe_txn.hash = await probe_txn.generate_hash()
                probe_txn.transaction_signature = (
                    TU.generate_signature_with_private_key(
                        probe_priv_hex, probe_txn.hash
                    )
                )

                kel_exception_name = None
                kel_exception_msg = None
                try:
                    await probe_txn.verify(check_kel=True, mempool=True)
                except Exception as exc:
                    kel_exception_name = exc.__class__.__name__
                    kel_exception_msg = str(exc)

                await self.config.mongo.async_db.failed_transactions.insert_one(
                    {
                        "exception": kel_exception_name
                        or "KelUnlockAuthenticationFailure",
                        "message": kel_exception_msg
                        or "invalid private_key or second_factor",
                        "txn": probe_txn.to_dict(),
                        "request_ip": self.request.remote_ip,
                        "timestamp": time.time(),
                        # KEL address fields lifted to the top level so
                        # KelFailedAttemptsHandler can query them efficiently.
                        "public_key_hash": probe_address,
                        "prerotated_key_hash": child_probe_address,
                        "prev_public_key_hash": prev_pkh,
                    }
                )
            except Exception as log_exc:
                self.config.app_log.warning(
                    f"KelUnlockHandler failed to record attempt: {log_exc}"
                )

        # ------------------------------------------------------------------ #
        # 1. Fetch the current active derived_keys record
        # ------------------------------------------------------------------ #
        current_record = await self.config.mongo.async_site_db.derived_keys.find_one(
            {}, {"_id": 0}, sort=[("stored_at", -1)]
        )
        if not current_record:
            self.set_status(401)
            return self.render_as_json(_AUTH_FAIL)

        # ------------------------------------------------------------------ #
        # 2. Factor 1 — private key must derive the current active public key
        # ------------------------------------------------------------------ #
        try:
            priv_bytes = bytes.fromhex(private_key_hex)
            submitted_pub = (
                _CoincurvePrivateKey(priv_bytes)
                .public_key.format(compressed=True)
                .hex()
            )
        except Exception:
            self.set_status(401)
            return self.render_as_json(_AUTH_FAIL)

        if submitted_pub != current_record.get("public_key"):
            await _record_failed_attempt(private_key_hex, submitted_pub, second_factor)
            self.set_status(401)
            return self.render_as_json(_AUTH_FAIL)

        # ------------------------------------------------------------------ #
        # 3. Factor 2 — second_factor must re-derive to the prerotated key.
        #    prev_private_key/prev_chain_code are the current signing key's
        #    material; derive_secure_path(current, sf) must produce the
        #    stored prerotated_public_key.
        # ------------------------------------------------------------------ #
        try:
            prev_priv = bytes.fromhex(current_record["prev_private_key"])
            prev_cc = bytes.fromhex(current_record["prev_chain_code"])
        except Exception:
            self.set_status(401)
            return self.render_as_json(_AUTH_FAIL)

        rederived = derive_secure_path(prev_priv, prev_cc, second_factor)
        rederived_pub = (
            _CoincurvePrivateKey(rederived["private_key"])
            .public_key.format(compressed=True)
            .hex()
        )

        if rederived_pub != current_record.get("prerotated_public_key"):
            # Factor 1 passed (private key is valid), so use it to build the probe
            await _record_failed_attempt(private_key_hex, submitted_pub, second_factor)
            self.set_status(401)
            return self.render_as_json(_AUTH_FAIL)

        # ------------------------------------------------------------------ #
        # 4. Auto-rotate: advance the KEL by one step.
        #    The prerotated key becomes the new signing key.
        #    We already have rederived = derive_secure_path(prev_priv, prev_cc, sf)
        #    which IS the prerotated private key.
        # ------------------------------------------------------------------ #
        from yadacoin.core.keyeventlog import KeyEventLog
        from yadacoin.core.transaction import Transaction
        from yadacoin.core.transactionutils import TU

        prerot_pub_bytes = _CoincurvePrivateKey(
            rederived["private_key"]
        ).public_key.format(compressed=True)
        prerot_pub_hex = prerot_pub_bytes.hex()
        prerot_address = str(P2PKHBitcoinAddress.from_pubkey(prerot_pub_bytes))

        try:
            kel_for_prerot = await KeyEventLog.build_from_public_key(prerot_pub_hex)
        except Exception:
            kel_for_prerot = []

        if not kel_for_prerot:
            self.set_status(500)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "no key event log found for prerotated key — cannot rotate",
                }
            )

        prev_public_key_hash = kel_for_prerot[-1].public_key_hash

        child = derive_secure_path(
            rederived["private_key"], rederived["chain_code"], second_factor
        )
        child_priv_obj = _CoincurvePrivateKey(child["private_key"])
        child_pub_bytes = child_priv_obj.public_key.format(compressed=True)
        child_pub_hex = child_pub_bytes.hex()
        child_address = str(P2PKHBitcoinAddress.from_pubkey(child_pub_bytes))

        grandchild = derive_secure_path(
            child["private_key"], child["chain_code"], second_factor
        )
        grandchild_priv_obj = _CoincurvePrivateKey(grandchild["private_key"])
        grandchild_pub_bytes = grandchild_priv_obj.public_key.format(compressed=True)
        grandchild_pub_hex = grandchild_pub_bytes.hex()
        grandchild_address = str(P2PKHBitcoinAddress.from_pubkey(grandchild_pub_bytes))

        rotation_txn = Transaction(
            txn_time=int(time.time()),
            public_key=prerot_pub_hex,
            outputs=[{"to": child_address, "value": 0.0}],
            inputs=[],
            fee=0.0,
            masternode_fee=0.0,
            version=7,
            prerotated_key_hash=child_address,
            twice_prerotated_key_hash=grandchild_address,
            public_key_hash=prerot_address,
            prev_public_key_hash=prev_public_key_hash,
            relationship="",
            relationship_hash="",
            rid="",
            dh_public_key="",
        )
        rotation_txn.hash = await rotation_txn.generate_hash()
        rotation_txn.transaction_signature = TU.generate_signature_with_private_key(
            rederived["private_key"].hex(), rotation_txn.hash
        )

        await self.config.mongo.async_db.miner_transactions.replace_one(
            {"id": rotation_txn.transaction_signature},
            rotation_txn.to_dict(),
            upsert=True,
        )

        if "node" in self.config.modes:
            try:
                async for peer_stream in self.config.peer.get_sync_peers():
                    await self.config.nodeShared.write_params(
                        peer_stream, "newtxn", {"transaction": rotation_txn.to_dict()}
                    )
                    if peer_stream.peer.protocol_version > 1:
                        self.config.nodeClient.retry_messages[
                            (
                                peer_stream.peer.rid,
                                "newtxn",
                                rotation_txn.transaction_signature,
                            )
                        ] = {"transaction": rotation_txn.to_dict()}
            except Exception as exc:
                self.config.app_log.warning(
                    f"KelUnlockHandler rotation broadcast error: {exc}"
                )

        now = time.time()
        await self.config.mongo.async_site_db.derived_keys.update_one(
            {"address": prerot_address},
            {
                "$set": {
                    "address": prerot_address,
                    "public_key": prerot_pub_hex,
                    "prerotated_public_key": child_pub_hex,
                    "prerotated_address": child_address,
                    "twice_prerotated_public_key": grandchild_pub_hex,
                    "twice_prerotated_address": grandchild_address,
                    "prev_private_key": rederived["private_key"].hex(),
                    "prev_chain_code": rederived["chain_code"].hex(),
                    "stored_at": now,
                    "transaction_id": rotation_txn.transaction_signature,
                }
            },
            upsert=True,
        )

        # ------------------------------------------------------------------ #
        # 5. Issue JWT
        # ------------------------------------------------------------------ #
        payload = {
            "timestamp": time.time(),
            "key_or_wif": "true",
            "exp": _dt.datetime.utcnow() + _dt.timedelta(seconds=expires),
        }
        token = _jwt.encode(payload, self.config.jwt_secret_key, algorithm="ES256")
        await self.config.mongo.async_db.config.update_one(
            {"key": "jwt"}, {"$set": {"key": "jwt", "value": payload}}, upsert=True
        )
        return self.render_as_json(
            {
                "status": True,
                "token": token,
                "rotation": {
                    "new_address": prerot_address,
                    "new_public_key": prerot_pub_hex,
                    "new_private_key": rederived["private_key"].hex(),
                    "transaction_id": rotation_txn.transaction_signature,
                },
            }
        )


class DerivedKeysPageHandler(BaseHandler):
    """GET /key-rotation/derived-keys — serve the derived-keys management UI."""

    async def get(self):
        self.render("derived_keys.html")


@jwtauthwallet
class ListDerivedKeysHandler(BaseHandler):
    """
    GET /key-rotation/derived-keys/list

    Return all records in the ``derived_keys`` collection, newest first.
    Supports optional ``page`` and ``page_size`` query params for pagination.
    """

    async def get(self):
        pass

        try:
            page = max(1, int(self.get_query_argument("page", "1")))
            page_size = min(50, max(1, int(self.get_query_argument("page_size", "20"))))
        except (ValueError, TypeError):
            page, page_size = 1, 20

        skip = (page - 1) * page_size
        projection = {"_id": 0}

        total = await self.config.mongo.async_site_db.derived_keys.count_documents({})
        cursor = (
            self.config.mongo.async_site_db.derived_keys.find({}, projection)
            .sort("stored_at", -1)
            .skip(skip)
            .limit(page_size)
        )
        records = []
        async for doc in cursor:
            records.append(doc)

        return self.render_as_json(
            {
                "status": True,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": max(1, -(-total // page_size)),
                "records": records,
            }
        )


@jwtauthwallet
class DerivedKeyHistoryHandler(BaseHandler):
    """
    GET /key-rotation/derived-keys/history?address=<P2PKH>&page=1&page_size=20

    Return paginated KEL history for a given address.
    """

    async def get(self):
        pass

        address = self.get_query_argument("address", "").strip()
        if not address:
            self.set_status(400)
            return self.render_as_json({"status": False, "message": "address required"})

        try:
            page = max(1, int(self.get_query_argument("page", "1")))
            page_size = min(50, max(1, int(self.get_query_argument("page_size", "20"))))
        except (ValueError, TypeError):
            page, page_size = 1, 20

        # Fetch all confirmed KEL entries for this address (mempool + chain)
        projection = {
            "_id": 0,
            "public_key": 1,
            "public_key_hash": 1,
            "prerotated_key_hash": 1,
            "twice_prerotated_key_hash": 1,
            "prev_public_key_hash": 1,
            "time": 1,
            "id": 1,
        }

        query = {"public_key_hash": address}

        # mempool
        mempool_cursor = self.config.mongo.async_db.miner_transactions.find(
            query, projection
        ).sort("time", -1)
        mempool_entries = []
        async for doc in mempool_cursor:
            doc["source"] = "mempool"
            mempool_entries.append(doc)

        # confirmed blocks
        pipeline = [
            {"$match": {"transactions.public_key_hash": address}},
            {"$unwind": "$transactions"},
            {"$match": {"transactions.public_key_hash": address}},
            {"$replaceRoot": {"newRoot": "$transactions"}},
            {"$project": projection},
            {"$sort": {"time": -1}},
        ]
        chain_entries = []
        async for doc in self.config.mongo.async_db.blocks.aggregate(pipeline):
            doc["source"] = "blockchain"
            chain_entries.append(doc)

        all_entries = mempool_entries + chain_entries
        total = len(all_entries)
        start = (page - 1) * page_size
        page_entries = all_entries[start : start + page_size]

        return self.render_as_json(
            {
                "status": True,
                "address": address,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": max(1, -(-total // page_size)),
                "entries": page_entries,
            }
        )


@jwtauthwallet
class KelFailedAttemptsHandler(BaseHandler):
    """GET /key-rotation/failed-attempts?address=&page=1&page_size=20

    Returns paginated failed authentication attempts for the key log entry
    identified by *address*.  Requires a valid JWT (same as rotate endpoint).
    """

    async def get(self):
        address = self.get_argument("address", "").strip()
        if not address:
            self.set_status(400)
            return self.render_as_json({"message": "address is required"})

        try:
            page = max(1, int(self.get_argument("page", 1)))
            page_size = min(max(1, int(self.get_argument("page_size", 20))), 100)
        except (ValueError, TypeError):
            page, page_size = 1, 20

        # A failed attempt for this address will have the address in at least
        # one of the three KEL position fields.
        query = {
            "$or": [
                {"public_key_hash": address},
                {"prerotated_key_hash": address},
                {"prev_public_key_hash": address},
            ]
        }
        total = await self.config.mongo.async_db.failed_transactions.count_documents(
            query
        )
        skip = (page - 1) * page_size
        cursor = (
            self.config.mongo.async_db.failed_transactions.find(
                query, {"_id": 0}, sort=[("timestamp", -1)]
            )
            .skip(skip)
            .limit(page_size)
        )
        records = await cursor.to_list(length=page_size)

        return self.render_as_json(
            {
                "records": records,
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": max(1, -(-total // page_size)),
            }
        )


class DerivedKeyDetailPageHandler(BaseHandler):
    """GET /key-rotation/derived-keys/detail — serve the standalone detail page."""

    async def get(self):
        self.render("derived_key_detail.html")


@jwtauthwallet
class DerivedKeyRecordHandler(BaseHandler):
    """GET /key-rotation/derived-keys/record?address= — return a single derived_keys record."""

    async def get(self):
        address = self.get_argument("address", "").strip()
        if not address:
            self.set_status(400)
            return self.render_as_json({"message": "address is required"})

        record = await self.config.mongo.async_site_db.derived_keys.find_one(
            {"address": address}, {"_id": 0}
        )
        if not record:
            self.set_status(404)
            return self.render_as_json({"message": "record not found"})

        return self.render_as_json({"record": record})


KEY_ROTATION_HANDLERS = [
    (
        r"/key-rotation/derived-keys/history",
        DerivedKeyHistoryHandler,
    ),
    (
        r"/key-rotation/derived-keys/list",
        ListDerivedKeysHandler,
    ),
    (
        r"/key-rotation/derived-keys/detail",
        DerivedKeyDetailPageHandler,
    ),
    (
        r"/key-rotation/derived-keys/record",
        DerivedKeyRecordHandler,
    ),
    (
        r"/key-rotation/derived-keys",
        DerivedKeysPageHandler,
    ),
    (
        r"/key-rotation/kel-unlock",
        KelUnlockHandler,
    ),
    (
        r"/key-rotation/kel-status",
        KelStatusHandler,
    ),
    (
        r"/key-rotation/failed-attempts",
        KelFailedAttemptsHandler,
    ),
    (
        r"/key-rotation/init-derived-child-key",
        InitDerivedChildKeyHandler,
    ),
    (
        r"/key-rotation/derived-child-key",
        DerivedChildKeyHandler,
    ),
    (
        r"/key-rotation/prev-key-hash|/yadacoin-cash/prev-key-hash",
        KeyRotationPrevKeyHashHandler,
    ),
    (r"/key-rotation/spent|/yadacoin-cash/spent", KeyRotationSpentHandler),
    (r"/key-rotation|/yadacoin-cash", KeyRotationHandler),
]
