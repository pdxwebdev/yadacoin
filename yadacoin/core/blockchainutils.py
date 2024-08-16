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

    async def get_wallet_balance(self, address):
        balance = 0
        used_ids = []
        async for txn in self.get_wallet_unspent_transactions(address):
            for output in txn["outputs"]:
                if address == output["to"]:
                    used_ids.append(txn["id"])
                    balance += float(output["value"])
        return balance

    async def get_wallet_unspent_transactions(self, address, ids=None, no_zeros=False):
        #### fine above ####

        ### find public key fast first ###

        public_key_address_pairs = self.mongo.async_db.blocks.aggregate(
            [
                {"$match": {"transactions.outputs.to": address}},
                {"$unwind": "$transactions"},
                {"$match": {"transactions.outputs.to": address}},
                {
                    "$project": {
                        "transaction": "$transactions",
                        "public_key": "$transactions.public_key",
                    }
                },
                {"$unwind": "$transaction.outputs"},
                {"$match": {"transaction.outputs.to": address}},
            ],
            allowDiskUse=True,
            hint="__to",
        )

        reverse_public_key = ""
        async for public_key_address_pair in public_key_address_pairs:
            xaddress = str(
                P2PKHBitcoinAddress.from_pubkey(
                    bytes.fromhex(public_key_address_pair["public_key"])
                )
            )

            if xaddress == address:
                reverse_public_key = public_key_address_pair["public_key"]
                break

        spent_txns_query = []

        if ids:
            spent_txns_query.append({"$match": {"transactions.id": {"$in": ids}}})
        ### end find public key fast first ###
        spent_txns_query.extend(
            [
                {"$match": {"transactions.public_key": reverse_public_key}},
                {"$unwind": "$transactions"},
                {"$project": {"_id": 0, "txn": "$transactions", "height": "$index"}},
                {"$match": {"txn.public_key": reverse_public_key}},
            ]
        )

        if ids:
            spent_txns_query.append({"$match": {"txn.id": {"$in": ids}}})

        spent_txns_query.append(
            {
                "$project": {
                    "_id": 0,
                    "public_key": "$txn.public_key",
                    "txn": "$txn",
                    "height": "$height",
                }
            }
        )

        spent = self.mongo.async_db.blocks.aggregate(
            spent_txns_query, allowDiskUse=True, hint="__txn_public_key"
        )

        # here we're assuming block/transaction validation ensures the inputs used are valid for this address
        spent_ids = set()
        async for x in spent:
            spent_ids.update([i["id"] for i in x["txn"]["inputs"]])

        if ids:
            spent_ids.update(ids)

        unspent_txns_query = [
            {"$match": {"transactions.outputs.to": address}},
            {"$unwind": "$transactions"},
            {"$unwind": "$transactions.outputs"},
            {"$match": {"transactions.outputs.to": address}},
        ]

        if no_zeros:
            unspent_txns_query.append(
                {"$match": {"transactions.outputs.value": {"$gt": 0}}}
            )

        unspent_txns_query.extend(
            [
                {"$match": {"transactions.id": {"$nin": list(spent_ids)}}},
                {"$sort": {"transactions.time": 1}},  # Change sorting on time
            ]
        )

        async for unspent_txn in self.config.mongo.async_db.blocks.aggregate(
            unspent_txns_query, allowDiskUse=True, hint="__to"
        ):
            unspent_txn["transactions"]["height"] = unspent_txn["index"]
            unspent_txn["transactions"]["outputs"] = [
                unspent_txn["transactions"]["outputs"]
            ]
            yield unspent_txn["transactions"]

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
            res2 = await self.mongo.async_db.miner_transactions.find_one(
                {"inputs.id": {"$in": input_ids}, "public_key": public_key}
            )
            if res2:
                return True
        return False

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
