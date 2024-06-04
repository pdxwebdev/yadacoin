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
        try:
            await transaction.verify(check_max_inputs=check_max_inputs)
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
    async def rebroadcast_mempool(cls, config, confirmed_peers, include_zero=False):
        from yadacoin.core.transaction import Transaction

        query = {"outputs.value": {"$gt": 0}}
        if include_zero:
            query = {}

        async for txn in config.mongo.async_db.miner_transactions.find(query):
            x = Transaction.from_dict(txn)
            async for peer_stream in config.peer.get_sync_peers():
                if (
                    peer_stream.peer.rid,
                    "newtxn",
                    x.transaction_signature,
                ) in confirmed_peers:
                    config.app_log.debug(
                        f"Skipping peer {peer_stream.peer.rid} in rebroadcast_mempool as it has already confirmed the transaction."
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
        return

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
