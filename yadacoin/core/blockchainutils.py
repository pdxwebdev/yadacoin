"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64
import json
from logging import getLogger
from time import time

# from yadacoin.transactionutils import TU
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey

from yadacoin.core.blockchain import Blockchain
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config

GLOBAL_BU = None


def BU():
    return GLOBAL_BU


def set_BU(BU):
    global GLOBAL_BU
    GLOBAL_BU = BU


class TooManyUTXOsException(Exception):
    pass


class BlockChainUtils(object):
    # Blockchain Utilities

    collection = None
    database = None

    def __init__(self):
        self.config = Config()
        self.mongo = self.config.mongo
        self.latest_block = None
        self.app_log = getLogger("tornado.application")

    def invalidate_latest_block(self):
        self.latest_block = None

    async def get_blocks_async(self, reverse=False):
        if reverse:
            return self.mongo.async_db.blocks.find({}, {"_id": 0}).sort([("index", -1)])
        else:
            return self.mongo.async_db.blocks.find({}, {"_id": 0}).sort([("index", 1)])

    async def get_latest_block(self) -> dict:
        # cached - WARNING : this is a json doc, NOT a block
        if not self.latest_block is None:
            return self.latest_block
        self.latest_block = await self.mongo.async_db.blocks.find_one(
            {}, {"_id": 0}, sort=[("index", -1)]
        )
        # self.app_log.debug("last block " + str(self.latest_block))
        return self.latest_block

    async def insert_genesis(self):
        # insert genesis if it doesn't exist
        genesis_block = await Blockchain.get_genesis_block()
        await genesis_block.save()
        await self.mongo.async_db.consensus.update_one(
            {
                "block": genesis_block.to_dict(),
                "peer": "me",
                "id": genesis_block.signature,
                "index": 0,
            },
            {
                "$set": {
                    "block": genesis_block.to_dict(),
                    "peer": "me",
                    "id": genesis_block.signature,
                    "index": 0,
                }
            },
            upsert=True,
        )
        await self.config.LatestBlock.block_checker()

    def set_latest_block(self, block: dict):
        self.latest_block = block

    async def get_latest_block_async(self, use_cache=True) -> dict:
        # cached, async version
        if self.latest_block is not None and use_cache:
            return self.latest_block
        self.latest_block = await self.mongo.async_db.blocks.find_one(
            {}, {"_id": 0}, sort=[("index", -1)]
        )
        return self.latest_block

    async def get_block_by_index(self, index):
        return await self.mongo.async_db.blocks.find_one({"index": index}, {"_id": 0})

    async def get_unspent_txns(self, unspent_txns_query):
        # Return the cursor directly without awaiting it
        return self.config.mongo.async_db.blocks.aggregate(
            unspent_txns_query, allowDiskUse=True, hint="__to"
        )

    async def get_coinbase_total_output_balance(self, address):
        reverse_public_key = await self.get_reverse_public_key(address)
        coinbase_pipeline = [
            {
                "$match": {
                    "transactions.outputs.to": address,
                    "transactions.public_key": reverse_public_key,
                },
            },
            {"$unwind": "$transactions"},
            {"$unwind": "$transactions.outputs"},
            {
                "$match": {
                    "transactions.outputs.to": address,
                    "transactions.inputs.0": {"$exists": False},
                    "transactions.public_key": reverse_public_key,
                },
            },
            {
                "$group": {
                    "_id": None,
                    "total_balance": {"$sum": "$transactions.outputs.value"},
                }
            },
        ]

        result = await self.mongo.async_db.blocks.aggregate(coinbase_pipeline).to_list(
            length=1
        )
        return result[0]["total_balance"] if result else 0.0

    async def get_total_received_balance(self, address):
        reverse_public_key = await self.get_reverse_public_key(address)
        pipeline = [
            {
                "$match": {
                    "transactions.outputs.to": address,
                },
            },
            {"$unwind": "$transactions"},
            {"$unwind": "$transactions.outputs"},
            {
                "$match": {
                    "transactions.outputs.to": address,
                    "transactions.public_key": {"$ne": reverse_public_key},
                },
            },
            {
                "$group": {
                    "_id": None,
                    "total_balance": {"$sum": "$transactions.outputs.value"},
                }
            },
        ]
        result = await self.mongo.async_db.blocks.aggregate(pipeline).to_list(length=1)
        return result[0]["total_balance"] if result else 0.0

    async def get_spent_balance(self, address):
        reverse_public_key = await self.get_reverse_public_key(address)
        pipeline = [
            {
                "$match": {
                    "transactions.public_key": reverse_public_key,
                },
            },
            {"$unwind": "$transactions"},
            {
                "$match": {
                    "transactions.public_key": reverse_public_key,
                    "transactions.inputs.0": {"$exists": True},
                }
            },
            {"$unwind": "$transactions.outputs"},
            {"$match": {"transactions.outputs.to": {"$ne": address}}},
            {
                "$group": {
                    "_id": None,
                    "spent_balance": {"$sum": "$transactions.outputs.value"},
                    "total_fee": {"$sum": "$transactions.fee"},
                }
            },
            {
                "$project": {
                    "total_spent_balance": {"$add": ["$spent_balance", "$total_fee"]}
                }
            },
        ]
        result = await self.mongo.async_db.blocks.aggregate(pipeline).to_list(length=1)

        if result:
            return result[0]["total_spent_balance"]

        return 0.0

    async def get_final_balance(self, address):
        total_coinbase = await self.get_coinbase_total_output_balance(address)
        total_received = await self.get_total_received_balance(address)
        total_spent = await self.get_spent_balance(address)
        return (total_coinbase + total_received) - total_spent

    async def get_wallet_balance(self, address, amount_needed=None):
        total_balance = await self.get_final_balance(address)
        return total_balance

    async def get_public_key_address_pairs(self, address):
        pipeline = [
            {"$match": {"transactions.outputs.to": address}},
            {"$unwind": "$transactions"},
            {"$unwind": "$transactions.outputs"},
            {"$match": {"transactions.outputs.to": address}},
            {
                "$group": {
                    "_id": None,  # Group all documents together
                    "unique_public_keys": {
                        "$addToSet": "$transactions.public_key"
                    },  # Collect unique public keys
                }
            },
            {
                "$project": {
                    "_id": 0,  # Exclude the _id field
                    "unique_public_keys": 1,  # Only return the list of unique public keys
                }
            },
        ]
        # Return the cursor directly without awaiting it
        public_key_address_pair_list = self.mongo.async_db.blocks.aggregate(
            pipeline, allowDiskUse=True, hint="__to"
        )
        return await public_key_address_pair_list.to_list(length=None)

    async def get_reverse_public_key(self, address):
        reversed_public_key = await self.mongo.async_db.reversed_public_keys.find_one(
            {"address": address}
        )
        if reversed_public_key:
            return reversed_public_key["public_key"]
        public_key_address_pairs = await self.get_public_key_address_pairs(address)

        if not public_key_address_pairs:
            return

        for public_key in public_key_address_pairs[0]["unique_public_keys"]:
            xaddress = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
            if xaddress == address:
                await self.mongo.async_db.reversed_public_keys.update_one(
                    {"address": address, "public_key": public_key},
                    {"$set": {"address": address, "public_key": public_key}},
                    upsert=True,
                )
                return public_key

    def get_wallet_unspent_transactions_for_dusting(self, address, limit=None):
        query = [
            {
                "$match": {
                    "transactions.outputs.to": address,
                },
            },
            {"$unwind": "$transactions"},
            {"$unwind": "$transactions.outputs"},
            {
                "$match": {
                    "transactions.outputs.to": address,
                    "transactions.outputs.value": {"$gt": 0},
                },
            },
            {
                "$group": {
                    "_id": {
                        "transactionId": "$transactions.id",
                        "to": "$transactions.outputs.to",
                    },
                    "totalValue": {"$sum": "$transactions.outputs.value"},
                    "time": {"$first": "$transactions.time"},
                }
            },
            {
                "$group": {
                    "_id": "$_id.transactionId",
                    "id": {"$first": "$_id.transactionId"},
                    "outputs": {"$push": {"to": "$_id.to", "value": "$totalValue"}},
                    "time": {"$first": "$time"},
                }
            },
            {"$sort": {"outputs.time": 1}},
        ]
        return self.get_wallet_unspent_transactions(
            unspent_txns_query=query, address=address, limit=limit
        )

    def get_wallet_unspent_transactions_for_spending(
        self, address, amount_needed=None, inc_mempool=False
    ):
        query = [
            {
                "$match": {
                    "transactions.outputs.to": address,
                    "transactions.outputs.value": {
                        "$gte": self.config.balance_min_utxo
                    },
                },
            },
            {"$unwind": "$transactions"},
            {"$unwind": "$transactions.outputs"},
            {
                "$match": {
                    "transactions.outputs.to": address,
                    "transactions.outputs.value": {
                        "$gte": self.config.balance_min_utxo
                    },
                },
            },
            {
                "$group": {
                    "_id": {
                        "transactionId": "$transactions.id",
                        "to": "$transactions.outputs.to",
                    },
                    "totalValue": {"$sum": "$transactions.outputs.value"},
                }
            },
            {
                "$group": {
                    "_id": "$_id.transactionId",
                    "id": {"$first": "$_id.transactionId"},
                    "outputs": {"$push": {"to": "$_id.to", "value": "$totalValue"}},
                }
            },
            {"$sort": {"outputs.value": -1}},
        ]
        return self.get_wallet_unspent_transactions(
            unspent_txns_query=query,
            address=address,
            inc_mempool=inc_mempool,
            amount_needed=amount_needed,
        )

    async def get_wallet_unspent_transactions(
        self,
        unspent_txns_query,
        address,
        inc_mempool=False,
        amount_needed=None,
        limit=None,
    ):
        public_key = await self.get_reverse_public_key(address)

        # Return the cursor directly without awaiting it
        utxos = await self.get_unspent_txns(unspent_txns_query)
        total = 0
        count = 0
        async for utxo in utxos:
            if not await self.config.BU.is_input_spent(
                utxo["id"], public_key, inc_mempool=inc_mempool
            ):
                count += 1
                if limit and count > limit:
                    raise TooManyUTXOsException(
                        f"The UTXO limit of {limit} has been exceeded"
                    )
                total += sum(
                    [x["value"] for x in utxo["outputs"] if x["to"] == address]
                )
                yield utxo
                if amount_needed is not None and total >= amount_needed:
                    break

        if not inc_mempool:
            return
        mempool_txns = self.config.mongo.async_db.miner_transactions.find(
            {"outputs.to": address}
        )
        pending_used_inputs = {}
        unspent_mempool_txns = {}
        async for mempool_txn in mempool_txns:
            if mempool_txn["id"] in pending_used_inputs:
                continue

            xaddress = str(
                P2PKHBitcoinAddress.from_pubkey(
                    bytes.fromhex(mempool_txn["public_key"])
                )
            )
            if address == xaddress and mempool_txn.get("inputs"):
                for x in mempool_txn.get("inputs"):
                    pending_used_inputs[x["id"]] = mempool_txn
                    if x["id"] in unspent_mempool_txns:
                        del unspent_mempool_txns[x["id"]]

            unspent_mempool_txns[mempool_txn["id"]] = {
                "_id": mempool_txn["id"],
                "id": mempool_txn["id"],
                "outputs": [x for x in mempool_txn["outputs"] if x["to"] == address],
            }
        for x in list(unspent_mempool_txns.values()):
            yield x

    async def get_wallet_masternode_fees_paid_transactions(
        self, public_key, from_block
    ):
        query = [
            {
                "$match": {
                    "index": {"$gte": from_block},
                    "transactions.public_key": public_key,
                },
            },
            {"$unwind": "$transactions"},
            {
                "$match": {
                    "transactions.public_key": public_key,
                    "transactions.masternode_fee": {"$gt": 0},
                },
            },
        ]
        # Return the cursor directly without awaiting it

        txns = self.config.mongo.async_db.blocks.aggregate(query)
        async for txn in txns:
            yield txn

    async def get_wallet_masternode_fees_delegated_transactions(
        self, address, from_block
    ):
        query = [
            {
                "$match": {
                    "index": {"$gte": from_block},
                    "transactions.relationship": address,
                },
            },
            {"$unwind": "$transactions"},
            {
                "$match": {
                    "transactions.relationship": address,
                    "transactions.masternode_fee": {"$gt": 0},
                },
            },
        ]
        # Return the cursor directly without awaiting it

        txns = self.config.mongo.async_db.blocks.aggregate(query)
        async for txn in txns:
            yield txn

    async def get_masternode_fees_paid_sum(self, public_key, from_block):
        sum = 0
        async for txn in self.get_wallet_masternode_fees_paid_transactions(
            public_key, from_block
        ):
            sum += txn["transactions"]["masternode_fee"]

        if sum == 0:
            async for txn in self.get_wallet_masternode_fees_delegated_transactions(
                str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key))),
                from_block,
            ):
                sum += txn["transactions"]["masternode_fee"]

        return sum

    async def get_transactions(
        self, wif, query, queryType, raw=False, both=True, skip=None
    ):
        if not skip:
            skip = []
        # from block import Block
        # from transaction import Transaction
        from yadacoin import Crypt

        get_transactions_cache = (
            await self.mongo.async_db.get_transactions_cache.find_one(
                {
                    "public_key": self.config.public_key,
                    "raw": raw,
                    "both": both,
                    "skip": skip,
                    "queryType": queryType,
                },
                sort=[("height", -1)],
            )
        )
        latest_block = await self.config.LatestBlock.block.copy()
        if get_transactions_cache:
            block_height = get_transactions_cache["height"]
        else:
            block_height = 0

        cipher = None
        transactions = []
        async for block in self.mongo.async_db.blocks.find(
            {
                "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}},
                "index": {"$gt": block_height},
            }
        ):
            for transaction in block.get("transactions"):
                try:
                    if transaction.get("id") in skip:
                        continue
                    if "relationship" not in transaction:
                        continue
                    if not transaction["relationship"]:
                        continue
                    if not raw:
                        if not cipher:
                            cipher = Crypt(wif)
                        decrypted = cipher.decrypt(transaction["relationship"])
                        relationship = json.loads(decrypted.decode("latin1"))
                        transaction["relationship"] = relationship
                    transaction["height"] = block["index"]
                    await self.mongo.async_db.get_transactions_cache.update_many(
                        {
                            "public_key": self.config.public_key,
                            "raw": raw,
                            "both": both,
                            "skip": skip,
                            "height": latest_block.index,
                            "block_hash": latest_block.hash,
                            "queryType": queryType,
                            "id": transaction["id"],
                        },
                        {
                            "public_key": self.config.public_key,
                            "raw": raw,
                            "both": both,
                            "skip": skip,
                            "height": latest_block.index,
                            "block_hash": latest_block.hash,
                            "txn": transaction,
                            "queryType": queryType,
                            "id": transaction["id"],
                            "cache_time": time(),
                        },
                        upsert=True,
                    )
                except:
                    self.app_log.debug(
                        "failed decrypt. block: {}".format(block["index"])
                    )
                    if both:
                        transaction["height"] = block["index"]
                        await self.mongo.async_db.get_transactions_cache.update_many(
                            {
                                "public_key": self.config.public_key,
                                "raw": raw,
                                "both": both,
                                "skip": skip,
                                "height": latest_block.index,
                                "block_hash": latest_block.hash,
                                "queryType": queryType,
                            },
                            {
                                "public_key": self.config.public_key,
                                "raw": raw,
                                "both": both,
                                "skip": skip,
                                "height": latest_block.index,
                                "block_hash": latest_block.hash,
                                "txn": transaction,
                                "queryType": queryType,
                                "cache_time": time(),
                            },
                            upsert=True,
                        )
                    continue

        if not transactions:
            await self.mongo.async_db.get_transactions_cache.insert_one(
                {
                    "public_key": self.config.public_key,
                    "raw": raw,
                    "both": both,
                    "skip": skip,
                    "queryType": queryType,
                    "height": latest_block.index,
                    "block_hash": latest_block.hash,
                    "cache_time": time(),
                }
            )

        search_query = {
            "public_key": self.config.public_key,
            "raw": raw,
            "both": both,
            "skip": skip,
            "queryType": queryType,
            "txn": {"$exists": True},
        }
        search_query.update(query)
        transactions = self.mongo.async_db.get_transactions_cache.find(
            search_query
        ).sort([("height", -1)])

        async for transaction in transactions:
            yield transaction["txn"]

    def generate_signature(self, message, private_key):
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message.encode("utf-8"))
        return base64.b64encode(signature).decode("utf-8")

    async def get_transaction_by_id(
        self,
        id,
        instance=False,
        give_block=False,
        include_fastgraph=False,
        inc_mempool=False,
    ):
        from yadacoin.core.transaction import Transaction

        async for block in self.mongo.async_db.blocks.find({"transactions.id": id}):
            if give_block:
                return block
            for txn in block["transactions"]:
                if txn["id"] == id:
                    if instance:
                        return Transaction.from_dict(txn)
                    else:
                        return txn
        if inc_mempool:
            res2 = await self.mongo.async_db.miner_transactions.find_one({"id": id})
            if res2:
                if give_block:
                    raise Exception("Cannot give block for mempool transaction")
                if instance:
                    return Transaction.from_dict(res2)
                else:
                    return res2
            return None
        else:
            # fix for bug when unspent cache returns an input
            # that has been removed from the chain
            await self.mongo.async_db.unspent_cache.delete_many({})
            return None

    async def is_input_spent(
        self,
        input_ids,
        public_key,
        instance=False,
        give_block=False,
        include_fastgraph=False,
        inc_mempool=False,
        from_index=None,
        extra_blocks=None,
    ):
        if not isinstance(input_ids, list):
            input_ids = [input_ids]
        query = [
            {
                "$match": {
                    "transactions.inputs.id": {"$in": input_ids},
                    "transactions.public_key": public_key,
                }
            },
            {"$unwind": "$transactions"},
            {
                "$match": {
                    "transactions.inputs.id": {"$in": input_ids},
                    "transactions.public_key": public_key,
                }
            },
        ]
        if from_index:
            self.config.app_log.debug(f"from_index {from_index}")
            query.insert(0, {"$match": {"index": {"$lt": from_index}}})
        async for x in self.mongo.async_db.blocks.aggregate(query, allowDiskUse=True):
            if extra_blocks:
                for block in extra_blocks:
                    if block.index == x["index"]:
                        for txn in block.transactions:
                            for txn_input in txn.inputs:
                                for input_id in input_ids:
                                    self.config.app_log.debug(
                                        f"{input_id} {txn_input.id}"
                                    )
                                    if input_id == txn_input.id:
                                        return True
                return False
            return True

        if inc_mempool:
            if await self.get_mempool_transactions(public_key, input_ids):
                return True
        return False

    async def get_mempool_transactions(self, public_key, input_ids):
        return await self.mongo.async_db.miner_transactions.find_one(
            {"inputs.id": {"$in": input_ids}, "public_key": public_key}
        )

    def get_version_for_height_DEPRECATED(self, height: int):
        # TODO: move to CHAIN
        if int(height) <= 14484:
            return 1
        elif int(height) <= CHAIN.POW_FORK_V2:
            return 2
        else:
            return 3

    async def get_block_reward_DEPRECATED(self, block=None):
        # TODO: move to CHAIN
        block_rewards = [
            {"block": "0", "reward": "50"},
            {"block": "210000", "reward": "25"},
            {"block": "420000", "reward": "12.5"},
            {"block": "630000", "reward": "6.25"},
            {"block": "840000", "reward": "3.125"},
            {"block": "1050000", "reward": "1.5625"},
            {"block": "1260000", "reward": "0.78125"},
            {"block": "1470000", "reward": "0.390625"},
            {"block": "1680000", "reward": "0.1953125"},
            {"block": "1890000", "reward": "0.09765625"},
            {"block": "2100000", "reward": "0.04882812"},
            {"block": "2310000", "reward": "0.02441406"},
            {"block": "2520000", "reward": "0.01220703"},
            {"block": "2730000", "reward": "0.00610351"},
            {"block": "2940000", "reward": "0.00305175"},
            {"block": "3150000", "reward": "0.00152587"},
            {"block": "3360000", "reward": "0.00076293"},
            {"block": "3570000", "reward": "0.00038146"},
            {"block": "3780000", "reward": "0.00019073"},
            {"block": "3990000", "reward": "0.00009536"},
            {"block": "4200000", "reward": "0.00004768"},
            {"block": "4410000", "reward": "0.00002384"},
            {"block": "4620000", "reward": "0.00001192"},
            {"block": "4830000", "reward": "0.00000596"},
            {"block": "5040000", "reward": "0.00000298"},
            {"block": "5250000", "reward": "0.00000149"},
            {"block": "5460000", "reward": "0.00000074"},
            {"block": "5670000", "reward": "0.00000037"},
            {"block": "5880000", "reward": "0.00000018"},
            {"block": "6090000", "reward": "0.00000009"},
            {"block": "6300000", "reward": "0.00000004"},
            {"block": "6510000", "reward": "0.00000002"},
            {"block": "6720000", "reward": "0.00000001"},
            {"block": "6930000", "reward": "0"},
        ]

        latest_block = await self.config.LatestBlock.block.copy()
        if latest_block:
            block_count = latest_block.index + 1
        else:
            block_count = 0

        for t, block_reward in enumerate(block_rewards):
            if block:
                if block.index >= int(block_reward["block"]) and block.index < int(
                    block_rewards[t + 1]["block"]
                ):
                    break
            else:
                if block_count == 0:
                    break
                if block_count >= int(block_reward["block"]) and block_count < int(
                    block_rewards[t + 1]["block"]
                ):
                    break

        return float(block_reward["reward"])

    def get_hash_rate(self, blocks):
        sum_time = 0
        sum_work = 0
        max_target = (2**16 - 1) * 2**208
        prev_time = 0
        for block in blocks:
            # calculations from https://bitcoin.stackexchange.com/questions/14086/how-can-i-calculate-network-hashrate-for-a-given-range-of-blocks-where-difficult/30225#30225
            difficulty = max_target / block.target
            sum_work += difficulty * 4295032833
            if prev_time > 0:
                sum_time += prev_time - int(block.time)
            prev_time = int(block.time)

        # total work(number of hashes) over time gives us the hashrate
        return int(sum_work / sum_time) if len(blocks) > 1 else 0
