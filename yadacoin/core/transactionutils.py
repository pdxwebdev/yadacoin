"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import base64
import hashlib
import random
import sys
import time

from coincurve._libsecp256k1 import ffi
from coincurve.keys import PrivateKey

from yadacoin.core.chain import CHAIN


class TU(object):  # Transaction Utilities
    @classmethod
    def hash(cls, message):
        return hashlib.sha256(message.encode("utf-8")).digest().hex()

    @classmethod
    def generate_deterministic_signature(cls, config, message: str, private_key=None):
        if not private_key:
            private_key = config.private_key
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message.encode("utf-8"))
        return base64.b64encode(signature).decode("utf-8")

    @classmethod
    def generate_signature_with_private_key(cls, private_key, message):
        x = ffi.new("long long *")
        x[0] = random.SystemRandom().randint(0, sys.maxsize)
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message.encode("utf-8"), custom_nonce=(ffi.NULL, x))
        return base64.b64encode(signature).decode("utf-8")

    @classmethod
    def generate_signature(cls, message, private_key):
        x = ffi.new("long long *")
        x[0] = random.SystemRandom().randint(0, sys.maxsize)
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message.encode("utf-8"), custom_nonce=(ffi.NULL, x))
        return base64.b64encode(signature).decode("utf-8")

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
        from yadacoin.core.transaction import (
            NotEnoughMoneyException,
            TooManyInputsException,
            Transaction,
        )

        if from_address == config.address:
            public_key = config.public_key
            private_key = config.private_key
        else:
            child_key = await config.mongo.async_db.child_keys.find_one(
                {"address": from_address}
            )
            if child_key:
                public_key = child_key["public_key"]
                private_key = child_key["private_key"]
            else:
                return {"status": "error", "message": "no wallet matching from address"}

        if outputs:
            for output in outputs:
                output["value"] = float(output["value"])
        else:
            outputs = [{"to": to, "value": value}]

        if not inputs:
            inputs = []

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
        except:
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
            )
        except TooManyInputsException as e:
            return {"status": "error", "message": e}
        except:
            return {"error": "invalid transaction"}

        if not dry_run:
            await config.mongo.async_db.miner_transactions.insert_one(
                transaction.to_dict()
            )
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
        return transaction.to_dict()

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
            to_delete.append(
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
            "transactions": {
                "$elemMatch": {"relationship.smart_contract": {"$exists": False}}
            },
            "transactions.requested_rid": smart_contract_txn.requested_rid,
            "transactions": {
                "$elemMatch": {
                    "public_key": {
                        "$ne": smart_contract_txn.relationship.identity.public_key
                    }
                }
            },
        }
        if start_index and end_index:
            match["index"]["$gte"] = start_index
            match["index"]["$lt"] = end_index
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
        address = config.address
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
