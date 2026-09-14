"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import hashlib
import time

from yadacoin.core.chain import CHAIN


class TU(object):  # Transaction Utilities
    @classmethod
    def hash(cls, message):
        return hashlib.sha256(message.encode("utf-8")).digest().hex()

    @classmethod
    def generate_rid(cls, config, username_signature):
        username_signatures = sorted(
            [str(config.username_signature), str(username_signature)], key=str.lower
        )
        return (
            hashlib.sha256(
                (str(username_signatures[0]) + str(username_signatures[1])).encode(
                    "utf-8"
                )
            )
            .digest()
            .hex()
        )

    @classmethod
    def _node_has_active_kel(cls, config):
        kel_manager = getattr(config, "kel_manager", None)
        if kel_manager is None:
            return False
        if getattr(kel_manager, "_k0", None):
            return True
        return bool(
            getattr(config, "kel_anchor_private_key", None)
            and getattr(config, "kel_anchor_public_key", None)
            and getattr(config, "kel_anchor_chain_code", None)
        )

    @classmethod
    async def _resolve_kel_spend_tip(cls, config, kel_manager):
        """Return ``(latest_txn, tip_key_dict, tip_pub_hex)`` for operator spend.

        Prefer K0-based tip lookup (on-chain, then mempool). Derive tip key
        material from K0 + counter so we are not tied to a stale kel_anchor.
        """
        from bitcoin.wallet import P2PKHBitcoinAddress
        from coincurve import PrivateKey as CcPrivateKey

        from yadacoin.core.keyeventlog import KeyEventLog
        from yadacoin.core.keyrotation import _read_second_factor, derive_secure_path

        second_factor = (
            getattr(kel_manager, "_second_factor", None) or _read_second_factor()
        )
        k0 = getattr(kel_manager, "_k0", None)

        lookup_keys = []
        if k0 and k0.get("private_key") is not None:
            k0_pub = (
                CcPrivateKey(k0["private_key"]).public_key.format(compressed=True).hex()
            )
            lookup_keys.append(k0_pub)
        inception = getattr(config, "inception", None)
        if inception is not None and getattr(inception, "public_key", None):
            lookup_keys.append(inception.public_key)
        if getattr(config, "kel_anchor_public_key", None):
            lookup_keys.append(config.kel_anchor_public_key)
        if getattr(config, "public_key", None):
            lookup_keys.append(config.public_key)

        # de-dupe preserving order
        seen = set()
        ordered = []
        for pk in lookup_keys:
            if pk and pk not in seen:
                seen.add(pk)
                ordered.append(pk)

        latest = None
        for pk in ordered:
            # Prefer on-chain tip; fall back to mempool so we can extend a tip
            # that is confirmed only in miner_transactions.
            for onchain_only in (True, False):
                try:
                    tip = await KeyEventLog.get_latest(
                        public_key=pk, onchain_only=onchain_only
                    )
                except Exception:
                    tip = None
                if tip is not None and getattr(tip, "public_key_hash", None):
                    latest = tip
                    break
            if latest is not None:
                break

        if latest is None:
            # Last resort: inception tag / config.inception object itself.
            if inception is not None and getattr(inception, "public_key_hash", None):
                latest = inception
            else:
                return None, None, None

        tip_pkh = getattr(latest, "public_key_hash", None) or ""
        tip_pub = getattr(latest, "public_key", None) or ""

        def _addr_of(key_dict):
            return str(
                P2PKHBitcoinAddress.from_pubkey(
                    CcPrivateKey(key_dict["private_key"]).public_key.format(
                        compressed=True
                    )
                )
            )

        def _pub_of(key_dict):
            return (
                CcPrivateKey(key_dict["private_key"])
                .public_key.format(compressed=True)
                .hex()
            )

        # Derive tip key from K0 by walking until address matches tip pkh.
        tip_key = None
        if k0 and k0.get("private_key") is not None and second_factor and tip_pkh:
            cur = {
                "private_key": k0["private_key"],
                "chain_code": k0["chain_code"],
            }
            # Bound walk: KEL depth rarely exceeds a few thousand.
            for _ in range(4096):
                if _addr_of(cur) == tip_pkh:
                    tip_key = cur
                    tip_pub = _pub_of(cur)
                    break
                cur = derive_secure_path(
                    cur["private_key"], cur["chain_code"], second_factor
                )

        if tip_key is None:
            # Fall back to kel_anchor if it matches tip pkh.
            if (
                getattr(config, "kel_anchor_private_key", None)
                and getattr(config, "kel_anchor_chain_code", None)
                and getattr(config, "kel_anchor_address", None) == tip_pkh
            ):
                tip_key = {
                    "private_key": bytes.fromhex(config.kel_anchor_private_key),
                    "chain_code": bytes.fromhex(config.kel_anchor_chain_code),
                }
                tip_pub = config.kel_anchor_public_key or tip_pub

        if tip_key is None:
            return latest, None, tip_pub

        return latest, tip_key, tip_pub

    @classmethod
    async def _broadcast_mempool(cls, config, transaction):
        await config.mongo.async_db.miner_transactions.insert_one(transaction.to_dict())
        if not hasattr(config, "peer") or config.peer is None:
            return
        async for peer_stream in config.peer.get_sync_peers():
            await config.nodeShared.write_params(
                peer_stream, "newtxn", {"transaction": transaction.to_dict()}
            )
            if peer_stream.peer.protocol_version > 1:
                config.nodeClient.retry_messages[
                    (
                        peer_stream.peer.rid,
                        "newtxn",
                        transaction.transaction_signature,
                    )
                ] = {"transaction": transaction.to_dict()}

    @classmethod
    async def send(
        cls,
        config,
        to,
        value,
        from_address=True,
        inputs=None,
        dry_run=False,
        exact_match=False,
        outputs=None,
    ):
        """Node-signed spend for operator / unlock sessions.

        When the node has an active KEL tip, builds an unconfirmed+confirming
        key-event money pair (plain BIP32 transfers fail KeyEvent.verify for
        tip addresses). Otherwise uses legacy BIP32 keys.
        """
        from yadacoin.core.transaction import (
            NotEnoughMoneyException,
            TooManyInputsException,
            Transaction,
        )

        if outputs:
            for output in outputs:
                output["value"] = float(output["value"])
        else:
            outputs = [{"to": to, "value": value}]

        if not inputs:
            inputs = []

        if cls._node_has_active_kel(config):
            try:
                return await cls._send_with_kel(
                    config,
                    to=to,
                    value=value,
                    inputs=inputs,
                    dry_run=dry_run,
                    exact_match=exact_match,
                    outputs=outputs,
                )
            except NotEnoughMoneyException:
                return {"status": "error", "message": "not enough money"}
            except TooManyInputsException as e:
                return {"status": "error", "message": str(e)}
            except Exception as e:
                try:
                    config.app_log.exception("TU.send KEL spend failed: %s", e)
                except Exception:
                    pass
                return {
                    "status": "error",
                    "error": "invalid transaction",
                    "message": str(e),
                }

        public_key = getattr(config, "public_key", None) or ""
        private_key = getattr(config, "private_key", None) or ""
        spend_from = from_address
        if spend_from is True or spend_from is None or spend_from is False:
            spend_from = getattr(config, "address", None)
        if (
            spend_from
            and spend_from != getattr(config, "address", None)
            and hasattr(config, "mongo")
            and config.mongo is not None
        ):
            try:
                child = await config.mongo.async_db.child_keys.find_one(
                    {"address": spend_from}
                )
            except Exception:
                child = None
            if child and child.get("public_key") and child.get("private_key"):
                public_key = child["public_key"]
                private_key = child["private_key"]

        if not public_key or not private_key:
            return {
                "status": "error",
                "message": "node signing keys are not configured",
            }

        try:
            transaction = await Transaction.generate(
                fee=0.00,
                public_key=public_key,
                private_key=private_key,
                inputs=inputs,
                outputs=outputs,
                exact_match=exact_match,
            )
        except NotEnoughMoneyException:
            return {"status": "error", "message": "not enough money"}
        except Exception:
            raise

        check_max_inputs = False
        if config.LatestBlock.block.index > CHAIN.CHECK_MAX_INPUTS_FORK:
            check_max_inputs = True

        check_masternode_fee = False
        if config.LatestBlock.block.index >= CHAIN.CHECK_MASTERNODE_FEE_FORK:
            check_masternode_fee = True

        check_kel = False
        if config.LatestBlock.block.index >= CHAIN.CHECK_KEL_FORK:
            check_kel = True

        try:
            await transaction.verify(
                check_max_inputs=check_max_inputs,
                check_masternode_fee=check_masternode_fee,
                check_kel=check_kel,
                check_input_spent=True,
                mempool=True,
            )
        except TooManyInputsException as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            try:
                config.app_log.exception("TU.send verify failed: %s", e)
            except Exception:
                pass
            return {
                "status": "error",
                "error": "invalid transaction",
                "message": str(e),
            }

        if not dry_run:
            await cls._broadcast_mempool(config, transaction)
        return transaction.to_dict()

    @classmethod
    async def _send_with_kel(
        cls,
        config,
        to,
        value,
        inputs=None,
        dry_run=False,
        exact_match=False,
        outputs=None,
    ):
        """KEL money spend extending the on-chain tip with a complete U/C pair.

        Hash-link rules require the next entry to be signed by the tip's
        *prerotated* key (Kn+1), not the tip key (Kn)::

            tip.public_key_hash      == U.prev_public_key_hash
            tip.prerotated_key_hash  == U.public_key_hash
            tip.twice_prerotated     == U.prerotated_key_hash

        Incomplete or mis-linked pairs are discarded at block time
        (``KELChainDiscard``).
        """
        import time as _time

        from bitcoin.wallet import P2PKHBitcoinAddress
        from coincurve import PrivateKey as CcPrivateKey

        from yadacoin.core.keyeventlog import KeyEventLog, verify_kel_step
        from yadacoin.core.keyrotation import NodeKeyRotationManager, derive_secure_path
        from yadacoin.core.transaction import (
            Input,
            NotEnoughMoneyException,
            Output,
            TooManyInputsException,
            Transaction,
        )

        fee = 0.0
        if not outputs:
            outputs = [{"to": to, "value": float(value)}]
        payment_total = sum(float(o.get("value") or 0) for o in outputs) + float(fee)
        if payment_total <= 0:
            raise ValueError("payment value must be positive")

        kel_manager = config.kel_manager
        second_factor = getattr(kel_manager, "_second_factor", None) or ""
        if not second_factor:
            from yadacoin.core.keyrotation import _read_second_factor

            second_factor = _read_second_factor()
        if not second_factor:
            raise RuntimeError("SECOND_FACTOR required for KEL operator spend")

        # Resolve tip from K0 / inception — kel_anchor_* can lag or jump ahead of
        # the real chain after partial spends and must not be the sole lookup key.
        latest, tip_key, tip_pub = await cls._resolve_kel_spend_tip(config, kel_manager)
        if latest is None:
            raise RuntimeError(
                "no KEL tip found (on-chain or mempool) — cannot build operator spend pair"
            )
        if tip_key is None:
            raise RuntimeError(
                "KEL tip found but could not derive matching tip key material "
                f"(tip pkh={getattr(latest, 'public_key_hash', None)}) — "
                "check SECOND_FACTOR / kel_manager K0"
            )

        tip_pkh = getattr(latest, "public_key_hash", None) or ""
        tip_pre = getattr(latest, "prerotated_key_hash", None) or ""
        tip_twice = getattr(latest, "twice_prerotated_key_hash", None) or ""
        tip_counter = getattr(latest, "counter", None)
        inception = getattr(latest, "inception_public_key_hash", None) or tip_pkh
        if not tip_pkh or not tip_pre or not tip_twice:
            raise RuntimeError("KEL tip missing public_key_hash / prerotated hashes")

        # Verify tip_key material matches tip.public_key_hash.
        tip_addr = str(
            P2PKHBitcoinAddress.from_pubkey(
                CcPrivateKey(tip_key["private_key"]).public_key.format(compressed=True)
            )
        )
        if tip_addr != tip_pkh:
            raise RuntimeError(
                f"derived tip key address {tip_addr} != tip.public_key_hash {tip_pkh}"
            )

        # Kn+1 = tip prerotated (signs unconfirmed), Kn+2 = tip twice (confirming),
        # Kn+3 / Kn+4 derived for confirming pre/twice.
        kn1 = derive_secure_path(
            tip_key["private_key"], tip_key["chain_code"], second_factor
        )
        kn1_obj = CcPrivateKey(kn1["private_key"])
        kn1_pub = kn1_obj.public_key.format(compressed=True).hex()
        kn1_pkh = str(
            P2PKHBitcoinAddress.from_pubkey(kn1_obj.public_key.format(compressed=True))
        )
        if kn1_pkh != tip_pre:
            raise RuntimeError(
                f"derived Kn+1 {kn1_pkh} != tip.prerotated_key_hash {tip_pre} "
                "(SECOND_FACTOR or kel_anchor material out of sync)"
            )

        kn2 = derive_secure_path(kn1["private_key"], kn1["chain_code"], second_factor)
        kn2_obj = CcPrivateKey(kn2["private_key"])
        kn2_pub = kn2_obj.public_key.format(compressed=True).hex()
        kn2_pkh = str(
            P2PKHBitcoinAddress.from_pubkey(kn2_obj.public_key.format(compressed=True))
        )
        if kn2_pkh != tip_twice:
            raise RuntimeError(
                f"derived Kn+2 {kn2_pkh} != tip.twice_prerotated_key_hash {tip_twice}"
            )

        kn3 = derive_secure_path(kn2["private_key"], kn2["chain_code"], second_factor)
        kn3_obj = CcPrivateKey(kn3["private_key"])
        kn3_pkh = str(
            P2PKHBitcoinAddress.from_pubkey(kn3_obj.public_key.format(compressed=True))
        )
        kn4 = derive_secure_path(kn3["private_key"], kn3["chain_code"], second_factor)
        kn4_pkh = str(
            P2PKHBitcoinAddress.from_pubkey(
                CcPrivateKey(kn4["private_key"]).public_key.format(compressed=True)
            )
        )

        # UTXOs across full KEL identity; spend authorized by Kn+1 tip prerotated.
        kel_addresses = await KeyEventLog.get_kel_addresses(
            address=tip_pkh, onchain_only=True
        )
        if not kel_addresses:
            kel_addresses = frozenset({tip_pkh, tip_pre, tip_twice})

        needed = payment_total
        utxo_result = await config.BU.get_unspent_outputs(
            tip_pkh,
            amount_needed=needed,
            min_value=0,
            max_utxos=CHAIN.MAX_INPUTS,
        )
        unspent = list(utxo_result.get("unspent_utxos") or [])
        if inputs:
            unspent = inputs
        if not unspent:
            raise NotEnoughMoneyException("not enough money")

        input_objs = []
        input_sum = 0.0
        for u in unspent:
            uid = u.get("id") or u.get("transaction_signature")
            if not uid:
                continue
            parent = await config.BU.get_transaction_by_id(uid, instance=True)
            if parent is None:
                continue
            credited = 0.0
            for out in parent.outputs or []:
                if float(out.value) <= 0:
                    continue
                if str(out.to) in kel_addresses:
                    credited += float(out.value)
            if credited <= 0:
                continue
            inp = Input(signature=uid)
            inp.input_txn = parent
            input_sum += credited
            input_objs.append(inp)
            if input_sum >= needed:
                break

        if input_sum < needed:
            raise NotEnoughMoneyException("not enough money")
        if len(input_objs) > CHAIN.MAX_INPUTS:
            raise TooManyInputsException(
                f"too many inputs: {len(input_objs)} > {CHAIN.MAX_INPUTS}"
            )

        change = float(input_sum - needed)
        # Change + 0-value link to Kn+2 (U.prerotated must equal tip.twice).
        out_list = [Output(to=kn2_pkh, value=change if change > 0 else 0.0)]
        for o in outputs:
            out_list.append(Output(to=o["to"], value=float(o["value"])))

        txn_time = int(_time.time())
        u_counter = (int(tip_counter) + 1) if tip_counter is not None else None
        c_counter = (int(tip_counter) + 2) if tip_counter is not None else None

        # Unconfirmed: signed by Kn+1, extends tip.
        unconfirmed = Transaction(
            txn_time=txn_time,
            version=7,
            public_key=kn1_pub,
            inputs=input_objs,
            outputs=out_list,
            fee=float(fee),
            masternode_fee=0.0,
            prerotated_key_hash=kn2_pkh,
            twice_prerotated_key_hash=kn3_pkh,
            public_key_hash=kn1_pkh,
            prev_public_key_hash=tip_pkh,
            relationship="",
            relationship_hash="",
            rid="",
            dh_public_key="",
            counter=u_counter,
            inception_public_key_hash=inception,
        )
        unconfirmed.hash = await unconfirmed.generate_hash()
        unconfirmed.transaction_signature = NodeKeyRotationManager._sign(
            kn1["private_key"].hex(), unconfirmed.hash
        )

        # Confirming: signed by Kn+2, single out to Kn+3.
        confirming = Transaction(
            txn_time=txn_time,
            version=7,
            public_key=kn2_pub,
            inputs=[],
            outputs=[Output(to=kn3_pkh, value=0.0)],
            fee=0.0,
            masternode_fee=0.0,
            prerotated_key_hash=kn3_pkh,
            twice_prerotated_key_hash=kn4_pkh,
            public_key_hash=kn2_pkh,
            prev_public_key_hash=kn1_pkh,
            relationship="",
            relationship_hash="",
            rid="",
            dh_public_key="",
            counter=c_counter,
            inception_public_key_hash=inception,
        )
        confirming.hash = await confirming.generate_hash()
        confirming.transaction_signature = NodeKeyRotationManager._sign(
            kn2["private_key"].hex(), confirming.hash
        )

        # Fail fast if pair would be discarded at block selection.
        verify_kel_step(latest, unconfirmed, previous_onchain=True, latest_entry=latest)
        verify_kel_step(
            unconfirmed, confirming, previous_onchain=False, latest_entry=unconfirmed
        )

        check_max_inputs = config.LatestBlock.block.index > CHAIN.CHECK_MAX_INPUTS_FORK
        check_masternode_fee = (
            config.LatestBlock.block.index >= CHAIN.CHECK_MASTERNODE_FEE_FORK
        )
        check_kel = config.LatestBlock.block.index >= CHAIN.CHECK_KEL_FORK

        await unconfirmed.verify(
            check_max_inputs=check_max_inputs,
            check_masternode_fee=check_masternode_fee,
            check_kel=check_kel,
            check_input_spent=True,
            mempool=True,
            batch_txns=[unconfirmed, confirming],
        )
        await confirming.verify(
            check_max_inputs=check_max_inputs,
            check_masternode_fee=check_masternode_fee,
            check_kel=check_kel,
            mempool=True,
            batch_txns=[unconfirmed, confirming],
        )

        if not dry_run:
            await cls._broadcast_mempool(config, unconfirmed)
            await cls._broadcast_mempool(config, confirming)
            # After U/C land on-chain tip becomes Kn+2; keep anchor ahead for next spend.
            try:
                config.kel_anchor_private_key = kn2["private_key"].hex()
                config.kel_anchor_chain_code = kn2["chain_code"].hex()
                config.kel_anchor_public_key = kn2_pub
                config.kel_anchor_address = kn2_pkh
            except Exception:
                pass

        result = unconfirmed.to_dict()
        result["confirming"] = confirming.to_dict()
        result["status"] = "ok"
        return result

    @classmethod
    async def clean_mempool(cls, config):
        if not hasattr(config, "last_mempool_clean"):
            config.last_mempool_clean = 0

        await config.mongo.async_db.failed_transactions.delete_many(
            {"txn.time": {"$lte": time.time() - 60 * 60 * 24 * 30}}
        )

        to_delete = []
        txns_to_clean = config.mongo.async_db.miner_transactions.find(
            {"time": {"$gte": config.last_mempool_clean}}
        )
        async for txn_to_clean in txns_to_clean:
            for x in txn_to_clean.get("inputs"):
                if await config.BU.is_input_spent(x["id"], txn_to_clean["public_key"]):
                    to_delete.append(
                        {
                            "reason": "MempoolCleaner: Input already spent",
                            "txn": txn_to_clean,
                        }
                    )
                    continue
            if await config.mongo.async_db.blocks.find_one(
                {"transactions.id": txn_to_clean["id"]}
            ):
                to_delete.append(
                    {
                        "reason": "MempoolCleaner: Transaction already in blockchain",
                        "txn": txn_to_clean,
                    }
                )

        txns_to_clean = config.mongo.async_db.miner_transactions.find(
            {
                "time": {"$lte": time.time() - 60 * 60 * 24},
                "never_expire": {"$ne": True},
            }
        )
        async for txn_to_clean in txns_to_clean:
            to_delete.append(  # pragma: no cover
                {"reason": "MempoolCleaner: Transaction expired", "txn": txn_to_clean}
            )

        for txn in to_delete:
            await config.mongo.async_db.failed_transactions.insert_one(txn)
            await config.mongo.async_db.miner_transactions.delete_many(
                {"id": txn["txn"]["id"]}
            )

        config.last_mempool_clean = time.time()

    @classmethod
    async def clean_txn_tracking(cls, config):
        """
        Removes old transaction confirmations from `txn_tracking` that are older than 24 hours.

        - Ensures that peers are not storing unnecessary old transaction confirmations.
        - Runs after `clean_mempool` to synchronize data cleanup.
        - If all transactions under a peer (`rid`) are too old, the entry is deleted entirely.
        """

        cutoff_time = int(time.time()) - 60 * 60 * 24

        async for doc in config.mongo.async_db.txn_tracking.find():
            updated_transactions = {
                txn_id: timestamp
                for txn_id, timestamp in doc["transactions"].items()
                if timestamp > cutoff_time
            }

            if updated_transactions:
                await config.mongo.async_db.txn_tracking.update_one(
                    {"rid": doc["rid"]},
                    {"$set": {"transactions": updated_transactions}},
                )
            else:
                await config.mongo.async_db.txn_tracking.delete_one({"rid": doc["rid"]})

        config.app_log.info(f"[CLEANER] Removed old transaction confirmations.")

    @classmethod
    async def rebroadcast_mempool(cls, config, include_zero=False, send_to_all=False):
        """
        Rebroadcasts transactions from the mempool to peers who have not yet confirmed them.

        - Runs every 3 minutes to ensure new peers receive transactions.
        - Uses `txn_tracking` in MongoDB to avoid sending transactions to peers who already confirmed them.
        - Can include zero-value transactions if `include_zero=True`.

        This ensures efficient transaction propagation while minimizing redundant data transfer.
        """

        from yadacoin.core.transaction import Transaction

        query = {"outputs.value": {"$gt": 0}}
        if include_zero:
            query = {}

        async for txn in config.mongo.async_db.miner_transactions.find(query):
            x = Transaction.from_dict(txn)

            confirmed_peers = await config.mongo.async_db.txn_tracking.find(
                {f"transactions.{x.transaction_signature}": {"$exists": True}}
            ).to_list(length=None)

            confirmed_rids = {peer["rid"] for peer in confirmed_peers}

            async for peer_stream in config.peer.get_sync_peers():
                if peer_stream.peer.rid in confirmed_rids and not send_to_all:
                    config.app_log.debug(
                        f"[MEMPOOL] Skipping {peer_stream.peer.rid} - already confirmed."
                    )
                    continue

                await config.nodeShared.write_params(
                    peer_stream, "newtxn", {"transaction": x.to_dict()}
                )

                if peer_stream.peer.protocol_version > 1:
                    config.nodeClient.retry_messages[
                        (peer_stream.peer.rid, "newtxn", x.transaction_signature)
                    ] = {"transaction": x.to_dict()}

                await asyncio.sleep(1)

    @classmethod
    async def rebroadcast_failed(cls, config, id):
        from yadacoin.core.transaction import Transaction

        async for txn in config.mongo.async_db.failed_transactions.find(
            {"txn.id": id.replace(" ", "+")}
        ):
            x = Transaction.from_dict(txn["txn"])
            async for peer_stream in config.peer.get_sync_peers():
                await config.nodeShared.write_params(
                    peer_stream, "newtxn", {"transaction": x.to_dict()}
                )
                if peer_stream.peer.protocol_version > 1:
                    config.nodeClient.retry_messages[
                        (peer_stream.peer.rid, "newtxn", x.transaction_signature)
                    ] = {"transaction": x.to_dict()}
                time.sleep(0.1)

    @classmethod
    async def get_current_smart_contract_txns(cls, config, start_index):
        return config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        "transactions": {
                            "$elemMatch": {
                                "relationship.smart_contract.expiry": {
                                    "$gt": start_index
                                }
                            }
                        }
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        "transactions.relationship.smart_contract.expiry": {
                            "$gt": start_index
                        }
                    }
                },
                {"$sort": {"transactions.time": 1}},
            ]
        )

    @classmethod
    async def get_expired_smart_contract_txns(cls, config, start_index):
        return config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        "transactions.relationship.smart_contract.expiry": start_index
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        "transactions.relationship.smart_contract.expiry": start_index
                    }
                },
                {"$sort": {"index": 1, "transactions.time": 1}},
            ]
        )

    @classmethod
    async def get_trigger_txns(
        cls, config, smart_contract_txn, start_index=None, end_index=None
    ):
        match = {
            "$and": [
                {
                    "transactions": {
                        "$elemMatch": {
                            "relationship.smart_contract": {"$exists": False}
                        }
                    }
                },
                {
                    "transactions": {
                        "$elemMatch": {
                            "public_key": {
                                "$ne": smart_contract_txn.relationship.identity.public_key
                            }
                        }
                    }
                },
            ],
            "transactions.requested_rid": smart_contract_txn.requested_rid,
        }
        if start_index and end_index:
            match["index"] = {"$gte": start_index, "$lt": end_index}
        match2 = {
            "transactions.relationship.smart_contract": {"$exists": False},
            "transactions.requested_rid": smart_contract_txn.requested_rid,
            "transactions.public_key": {
                "$ne": smart_contract_txn.relationship.identity.public_key
            },
        }
        trigger_txn_blocks = config.mongo.async_db.blocks.aggregate(
            [
                {"$match": match},
                {"$unwind": "$transactions"},
                {"$match": match2},
                {"$sort": {"transactions.fee": -1, "transactions.time": 1}},
            ]
        )
        async for x in trigger_txn_blocks:
            yield x

    @classmethod
    def get_transaction_objs_list(cls, transaction_objs):
        return [y for x in list(transaction_objs.values()) for y in x]

    @classmethod
    async def combine_oldest_transactions(cls, config):
        address = config.kel_anchor_address
        combined_address = config.combined_address
        config.app_log.info("Combining oldest transactions process started.")
        total_value = 0
        oldest_transactions = []
        pending_used_inputs = {}

        # Check for transactions already in mempool
        mempool_txns = await config.mongo.async_db.miner_transactions.find(
            {"outputs.to": address}
        ).to_list(None)

        for txn in mempool_txns:
            for input_tx in txn["inputs"]:
                pending_used_inputs[input_tx["id"]] = txn["_id"]

        # Retrieve oldest transactions
        async for txn in config.BU.get_wallet_unspent_transactions_for_dusting(address):
            if txn["id"] not in pending_used_inputs:
                oldest_transactions.append(txn)
                if len(oldest_transactions) >= 100:
                    break

        config.app_log.info(
            "Found {} oldest transactions for combination.".format(
                len(oldest_transactions)
            )
        )

        # Additional check: if the number of transactions is less than 100, do not generate a transaction
        if len(oldest_transactions) < 100:
            config.app_log.info("Insufficient number of transactions to combine.")
            return

        for txn in oldest_transactions:
            for output in txn["outputs"]:
                if output["to"] == address:
                    total_value += float(output["value"])

        config.app_log.info(
            "Total value of oldest transactions: {}.".format(total_value)
        )

        try:
            result = await cls.send(
                config=config,
                to=combined_address,
                value=total_value,
                from_address=address,
                inputs=oldest_transactions,
                exact_match=False,
            )
            if "status" in result and result["status"] == "error":
                config.app_log.error(
                    "Error combining oldest transactions: {}".format(result["message"])
                )
            else:
                config.app_log.info("Successfully combined oldest transactions.")
        except Exception as e:
            config.app_log.error(
                "Error combining oldest transactions: {}".format(str(e))
            )
