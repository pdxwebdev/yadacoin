"""wallet_handlers.py — Wallet info, transaction, send, recovery, and credential handlers."""
import json

from yadacoin_agent_auth import AgentAuthValidator, AuthError

from yadacoin.http.base import BaseHandler

from ..core.auth import _validator


class WalletInfoHandler(BaseHandler):
    """
    GET /ai-agent-auth/api/wallet/info?public_key=<hex>

    Returns balance and address for the given public key.
    Read-only — no authentication required.
    """

    async def get(self):
        from bitcoin.wallet import P2PKHBitcoinAddress

        public_key = (self.get_argument("public_key", "") or "").strip()
        if not public_key:
            self.set_status(400)
            return self.render_as_json({"error": "public_key is required"})
        try:
            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid public_key"})
        try:
            balance = await self.config.BU.get_wallet_balance(address)
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json({"error": f"balance lookup failed: {exc}"})
        return self.render_as_json(
            {
                "address": address,
                "public_key": public_key,
                "balance": "{0:.8f}".format(balance),
            }
        )


class WalletTransactionsHandler(BaseHandler):
    """
    GET /ai-agent-auth/api/wallet/transactions?public_key=<hex>&direction=all|sent|received&page=1

    Returns confirmed on-chain transactions (sent and/or received).
    Read-only — no authentication required.
    """

    async def get(self):
        from bitcoin.wallet import P2PKHBitcoinAddress

        public_key = (self.get_argument("public_key", "") or "").strip()
        direction = (self.get_argument("direction", "all") or "all").strip().lower()
        page = max(int(self.get_argument("page", "1") or "1"), 1) - 1
        if not public_key:
            self.set_status(400)
            return self.render_as_json({"error": "public_key is required"})
        try:
            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid public_key"})

        results = []
        try:
            if direction in ("all", "sent"):
                sent_q = [
                    {
                        "$match": {
                            "transactions.inputs.0": {"$exists": True},
                            "transactions.public_key": public_key,
                            "transactions.outputs.value": {"$gt": 0},
                        }
                    },
                    {"$unwind": "$transactions"},
                    {
                        "$match": {
                            "transactions.inputs.0": {"$exists": True},
                            "transactions.public_key": public_key,
                            "transactions.outputs.value": {"$gt": 0},
                        }
                    },
                    {"$sort": {"transactions.time": -1}},
                    {"$skip": page * 10},
                    {"$limit": 10},
                ]
                async for doc in self.config.mongo.async_db.blocks.aggregate(sent_q):
                    txn = doc["transactions"]
                    txn["_direction"] = "sent"
                    results.append(txn)

            if direction in ("all", "received"):
                recv_q = [
                    {
                        "$match": {
                            "transactions.outputs.to": address,
                            "transactions.outputs.value": {"$gt": 0},
                        }
                    },
                    {"$unwind": "$transactions"},
                    {
                        "$match": {
                            "transactions.outputs.to": address,
                            "transactions.outputs.value": {"$gt": 0},
                            "transactions.public_key": {"$ne": public_key},
                        }
                    },
                    {"$sort": {"transactions.time": -1}},
                    {"$skip": page * 10},
                    {"$limit": 10},
                ]
                async for doc in self.config.mongo.async_db.blocks.aggregate(recv_q):
                    txn = doc["transactions"]
                    txn["_direction"] = "received"
                    results.append(txn)
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json({"error": f"query failed: {exc}"})

        # Sort merged results newest-first
        results.sort(key=lambda t: t.get("time", 0), reverse=True)
        return self.render_as_json({"transactions": results[:10], "page": page + 1})


class WalletSendHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/wallet/send

    Send or wrap a YDA transaction, authorised via a KEL-backed VP.

    Body (JSON)
    -----------
    public_key : hex compressed secp256k1 key (the prerotated agent key)
    challenge  : hex string from GET /ai-agent-auth/api/challenge
    vp         : W3C VP object {type, holder, verifiableCredential, proof}
    to_address : recipient YadaCoin address (ignored for wrap — bridge address used)
    amount     : float — YDA amount to send/wrap
    fee        : float — optional transaction fee (default 0.0)
    eth_address: str  — Ethereum 0x address (required for wrap; omit for plain send)

    Response (JSON)
    ---------------
    {"status": "ok", "transaction_id": "...", "to": ..., "amount": ..., "fee": ...}
    """

    WRAP_BRIDGE_ADDRESS = "16U1gAmHazqqEkbRE9KFPShAperjJreMRA"

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid json body"})

        public_key = (body.get("public_key") or "").strip()
        challenge = (body.get("challenge") or "").strip()
        vp = body.get("vp")
        eth_address = (body.get("eth_address") or "").strip()
        amount = body.get("amount")
        fee = float(body.get("fee", 0.0))

        # Wrap: to_address is always the bridge; relationship is the ETH address
        is_wrap = bool(eth_address)
        if is_wrap:
            to_address = self.WRAP_BRIDGE_ADDRESS
            if not eth_address.startswith("0x") or len(eth_address) != 42:
                self.set_status(400)
                return self.render_as_json(
                    {
                        "error": "eth_address must be a valid 0x Ethereum address (42 chars)"
                    }
                )
        else:
            to_address = (body.get("to_address") or "").strip()

        if not public_key or not challenge or not vp:
            self.set_status(400)
            return self.render_as_json(
                {"error": "public_key, challenge, and vp are required"}
            )
        if not to_address:
            self.set_status(400)
            return self.render_as_json(
                {"error": "to_address or eth_address is required"}
            )
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError("amount must be positive")
        except (TypeError, ValueError) as exc:
            self.set_status(400)
            return self.render_as_json({"error": f"invalid amount: {exc}"})

        # ── KEL / VP validation ─────────────────────────────────────────────
        try:
            auth = await _validator.validate_vp(public_key, challenge, vp)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"status": False, "message": str(exc)})

        try:
            AgentAuthValidator.enforce_scope(auth, services=["WalletAuthorization"])
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json(
                {"status": False, "message": str(exc), "scope": auth.scope}
            )

        # Verify the VP scope matches what the user approved in chat
        scope = auth.scope or {}
        scope_to = (scope.get("to_address") or "").strip()
        scope_amt = scope.get("amount")
        scope_eth = (scope.get("eth_address") or "").strip()
        if scope_to and scope_to != to_address:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        f"Scope mismatch: VP authorised send to '{scope_to}' "
                        f"but request targets '{to_address}'"
                    ),
                }
            )
        if scope_eth and scope_eth != eth_address:
            self.set_status(403)
            return self.render_as_json(
                {
                    "status": False,
                    "message": (
                        f"Scope mismatch: VP authorised wrap to '{scope_eth}' "
                        f"but request specifies '{eth_address}'"
                    ),
                }
            )
        if scope_amt is not None:
            try:
                if abs(float(scope_amt) - amount) > 1e-8:
                    raise ValueError(
                        f"VP authorised {scope_amt} YDA but request sends {amount} YDA"
                    )
            except (TypeError, ValueError) as exc:
                self.set_status(403)
                return self.render_as_json({"status": False, "message": str(exc)})

        # ── Build and submit the transaction (same pipeline as GraphTransactionHandler) ─
        from yadacoin.core.transaction import (
            NotEnoughMoneyException,
            TooManyInputsException,
            Transaction,
        )

        try:
            transaction = await Transaction.generate(
                fee=fee,
                public_key=self.config.public_key,
                private_key=self.config.private_key,
                inputs=[],
                outputs=[{"to": to_address, "value": amount}],
                relationship=eth_address if is_wrap else "",
            )
        except NotEnoughMoneyException:
            self.set_status(400)
            return self.render_as_json({"error": "not enough funds"})
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json(
                {"error": f"transaction generation failed: {exc}"}
            )

        try:
            await transaction.verify(
                check_input_spent=True,
                check_masternode_fee=True,
                check_max_inputs=True,
                check_kel=True,
                mempool=True,
            )
        except TooManyInputsException as exc:
            self.set_status(400)
            return self.render_as_json({"error": f"too many inputs: {exc}"})
        except Exception as exc:
            self.set_status(400)
            return self.render_as_json({"error": f"transaction invalid: {exc}"})

        await self.config.mongo.async_db.miner_transactions.insert_one(
            transaction.to_dict()
        )
        if "node" in self.config.modes:
            async for peer_stream in self.config.peer.get_sync_peers():
                await self.config.nodeShared.write_params(
                    peer_stream, "newtxn", {"transaction": transaction.to_dict()}
                )
                if peer_stream.peer.protocol_version > 1:
                    self.config.nodeClient.retry_messages[
                        (
                            peer_stream.peer.rid,
                            "newtxn",
                            transaction.transaction_signature,
                        )
                    ] = {"transaction": transaction.to_dict()}

        return self.render_as_json(
            {
                "status": "ok",
                "transaction_id": transaction.transaction_signature,
                "to": to_address,
                "amount": amount,
                "fee": fee,
                "authorized_address": auth.address,
                "kel_depth": len(auth.kel),
                "kel_txid": auth.kel_txid,
            }
        )


# ── Dynamically generate a VendorHandler subclass for every registered service ─
# Adding a new entry to VENDOR_REGISTRY automatically creates its handler.


class FindRecoveryTipHandler(BaseHandler):
    """
    GET /ai-agent-auth/api/find-recovery-tip?witness_hash=<hex>
    GET /ai-agent-auth/api/find-recovery-tip?lookup_id=<hex>

    Locate an on-chain `{"recovery": ...}` announcement and follow its KEL
    forward to the current tip. Returns the tip's public key + pkh so a
    recovers-inception can be built that points at it. When the matching
    announcement carries encrypted hints (the new shape introduced when we
    moved the hint storage on-chain), the ciphertext + IV are returned too
    so the recovering client can decrypt them with the user's Recovery Code.

    Either `witness_hash` (legacy / re-pin path) or `lookup_id` (Recovery
    Code lookup path) is accepted; `lookup_id` is the sha256 of the
    normalised Recovery Code and is what a fresh device queries with first
    so it can show hint labels before the user re-pins anything.
    """

    async def get(self):
        witness_hash = (self.get_argument("witness_hash", "") or "").strip().lower()
        lookup_id = (self.get_argument("lookup_id", "") or "").strip().lower()
        if not witness_hash and not lookup_id:
            self.set_status(400)
            return self.write({"error": "witness_hash or lookup_id required"})

        # Match either:
        #   • the legacy flat string form: relationship.recovery == witness_hash
        #   • the extended dict form:      relationship.recovery.witness_hash
        #                                  / relationship.recovery.lookup_id
        if lookup_id:
            match_clause = {
                "relationship.recovery.lookup_id": lookup_id,
            }
            inner_match = {
                "transactions.relationship.recovery.lookup_id": lookup_id,
            }
        else:
            match_clause = {
                "$or": [
                    {"relationship.recovery": witness_hash},
                    {"relationship.recovery.witness_hash": witness_hash},
                ]
            }
            inner_match = {
                "$or": [
                    {"transactions.relationship.recovery": witness_hash},
                    {"transactions.relationship.recovery.witness_hash": witness_hash},
                ]
            }

        cursor = self.config.mongo.async_db.blocks.aggregate(
            [
                {"$match": {"transactions": {"$elemMatch": match_clause}}},
                {"$unwind": "$transactions"},
                {"$match": inner_match},
                {"$sort": {"index": 1}},
                {"$limit": 1},
            ]
        )
        rows = await cursor.to_list(length=1)

        from_mempool = False
        if rows:
            announce_doc = rows[0]["transactions"]
        else:
            # Fall back to the mempool so a freshly-broadcast announcement
            # is discoverable before it has been mined.  miner_transactions
            # docs are flat transaction dicts, so the un-prefixed
            # `match_clause` matches directly.
            mempool_doc = await self.config.mongo.async_db.miner_transactions.find_one(
                match_clause
            )
            if not mempool_doc:
                self.set_status(404)
                return self.write(
                    {
                        "error": "no on-chain or mempool announcement matches the supplied identifier"
                    }
                )
            announce_doc = mempool_doc
            from_mempool = True

        from yadacoin.core.keyeventlog import KeyEventLog
        from yadacoin.core.recoveryannouncement import (
            RecoveryAnnouncement,
            RecoveryTransition,
        )
        from yadacoin.core.transaction import Transaction

        announce_txn = Transaction.from_dict(announce_doc)

        # Walk forward from the announcement's signing pubkey to the tip.
        # follow_recovery=False so we don't cross any prior recovery boundary
        # (we want the CURRENT delegator KEL, not its successor).  When the
        # announcement itself is still in the mempool the chain alone won't
        # see it, so we let the KEL builder include mempool entries in that
        # case — the recovering client typically waits for confirmation
        # before issuing the recovers-inception, but it can already decrypt
        # + display the hint labels embedded in the announcement and see
        # the announced tip.
        log = await KeyEventLog.build_from_public_key(
            announce_txn.public_key,
            onchain_only=not from_mempool,
            follow_recovery=False,
        )
        if not log:
            self.set_status(404)
            return self.write({"error": "could not reconstruct delegator KEL"})

        tip = log[-1]
        response = {
            "public_key": tip.public_key,
            "public_key_hash": tip.public_key_hash,
            "prerotated_key_hash": tip.prerotated_key_hash,
            "twice_prerotated_key_hash": tip.twice_prerotated_key_hash,
            "depth": len(log),
            "mempool": from_mempool,
        }

        # Surface witness_hash + encrypted hints from the announcement so the
        # client can decrypt with the Recovery Code.  Tolerate either wire
        # shape on the announcement txn, including the combined
        # RecoveryTransition form where the recovery announcement is nested
        # inside a recovers-inception.
        ann = None
        if isinstance(announce_txn.relationship, RecoveryAnnouncement):
            ann = announce_txn.relationship
        elif isinstance(announce_txn.relationship, RecoveryTransition):
            ann = announce_txn.relationship.announcement
        if ann:
            response["witness_hash"] = ann.witness_hash
            if ann.has_hints():
                response["hints_iv"] = ann.hints_iv
                response["hints_ct"] = ann.hints_ct
            if ann.lookup_id:
                response["lookup_id"] = ann.lookup_id

        return self.render_as_json(response)


class CredentialReceiptResyncHandler(BaseHandler):
    """
    GET /ai-agent-auth/api/resync-credentials?lookup_key=<hex>

    Return all on-chain and mempool credential_receipt transactions whose
    ``relationship.credential_receipt.lookup_key`` matches the supplied
    value.  The lookup_key is a sha256-HKDF fingerprint derived from the
    user's mnemonic (stable across KEL rotations; not reversible to the
    mnemonic).

    The server returns the raw ``{iv, ct}`` ciphertexts — only the wallet
    owner (who holds the mnemonic) can decrypt them.  The endpoint is
    intentionally unauthenticated: the lookup_key itself is a secret
    derived from the mnemonic, and the ciphertexts are opaque without the
    matching AES key.

    Response
    --------
    {"receipts": [
        {"iv": "<hex>", "ct": "<base64>",
         "txn_id": "...", "block_height": <int|null>, "mempool": <bool>},
        ...
    ]}
    """

    async def get(self):
        lookup_key = (self.get_argument("lookup_key", "") or "").strip().lower()
        if not lookup_key:
            self.set_status(400)
            return self.write({"error": "lookup_key is required"})

        match_clause = {
            "relationship.credential_receipt.lookup_key": lookup_key,
        }
        inner_match = {
            "transactions.relationship.credential_receipt.lookup_key": lookup_key,
        }

        receipts = []

        # ── Confirmed blocks ────────────────────────────────────────────────
        cursor = self.config.mongo.async_db.blocks.aggregate(
            [
                {"$match": {"transactions": {"$elemMatch": match_clause}}},
                {"$unwind": "$transactions"},
                {"$match": inner_match},
                {"$sort": {"index": 1}},
            ]
        )
        async for row in cursor:
            txn = row["transactions"]
            cr = txn.get("relationship", {}).get("credential_receipt", {})
            receipts.append(
                {
                    "iv": cr.get("iv", ""),
                    "ct": cr.get("ct", ""),
                    "txn_id": txn.get("id", ""),
                    "block_height": row.get("index"),
                    "mempool": False,
                }
            )

        # ── Mempool ─────────────────────────────────────────────────────────
        async for txn in self.config.mongo.async_db.miner_transactions.find(
            match_clause
        ):
            cr = txn.get("relationship", {}).get("credential_receipt", {})
            receipts.append(
                {
                    "iv": cr.get("iv", ""),
                    "ct": cr.get("ct", ""),
                    "txn_id": txn.get("id", ""),
                    "block_height": None,
                    "mempool": True,
                }
            )

        return self.render_as_json({"receipts": receipts})


# ── OAuth2 Device Authorization Grant handlers (RFC 8628) ─────────────────────
