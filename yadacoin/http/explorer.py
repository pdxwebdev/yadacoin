"""
Handlers required by the explorer operations
"""

import base64
import re
import time

from yadacoin.core.chain import CHAIN
from yadacoin.core.common import changetime
from yadacoin.http.base import BaseHandler


class HashrateAPIHandler(BaseHandler):
    async def refresh(self):
        from yadacoin.core.block import Block

        blocks = [
            await Block.from_dict(x)
            async for x in self.config.mongo.async_db.blocks.find({})
            .sort([("index", -1)])
            .limit(48)
        ]
        difficulty = int(CHAIN.MAX_TARGET / blocks[0].target)

        hash_rate = self.config.BU.get_hash_rate(blocks)
        self.config.HashRateAPIHandler = {
            "cache": {
                "time": time.time(),
                "circulating": CHAIN.get_circulating_supply(blocks[0].index),
                "height": blocks[0].index,
                "network_hash_rate": hash_rate,
                "difficulty": difficulty,
            }
        }

    async def get(self):
        self.config
        if not hasattr(self.config, "HashRateAPIHandler"):
            await self.refresh()
        elif time.time() - self.config.HashRateAPIHandler["cache"]["time"] > 600:
            await self.refresh()
        self.render_as_json({"stats": self.config.HashRateAPIHandler["cache"]})


class ExplorerHandler(BaseHandler):
    async def get(self):
        """
        :return:
        """
        self.render(
            "explorer/index.html",
            title="YadaCoin - Explorer",
            mixpanel="explorer page",
        )


class ExplorerSearchHandler(BaseHandler):
    
    async def get_wallet_balance(self, term):
        re.search(r"[A-Fa-f0-9]+", term).group(0)
        balance = await self.config.BU.get_wallet_balance(term)
        blocks = await self.config.mongo.async_db.blocks.find(
            {"transactions.outputs.to": term},
            {"_id": 0, "index": 1, "time": 1, "hash": 1, "transactions": 1},
        ).sort("index", -1).to_list(length=None)

        result = [
            {
                "index": block["index"],
                "time": block["time"],
                "hash": block["hash"],
                "transactions": [
                    txn
                    for txn in block.get("transactions", [])
                    if any(output.get("to") == term for output in txn.get("outputs", []))
                ],
            }
            for block in blocks
        ]

        return self.render_as_json(
            {
                "balance": "{0:.8f}".format(balance),
                "resultType": "txn_outputs_to",
                "searchedId": term,
                "result": result,
            }
        )

    async def get(self):
        term = self.get_argument("term", False)
        if not term:
            self.render_as_json({})
            return

        try:
            if re.fullmatch(r"[A-Za-z0-9]{34}", term):
                return await self.search_by_wallet_address(term)

            if term.isdigit():
                return await self.search_by_block_index(int(term))
            
            if re.fullmatch(r"[A-Fa-f0-9]{64}", term):
                return await self.search_by_block_hash(term)

            try:
                base64.b64decode(term.replace(" ", "+"))
                return await self.search_by_base64_id(term.replace(" ", "+"))
            except Exception as e:
                print(f"Error decoding base64: {e}")

            if re.fullmatch(r"[A-Fa-f0-9]+", term):
                return await self.search_by_public_key(term)

        except Exception as e:
            print(f"Error identifying search term: {e}")

        return self.render_as_json({})

    async def search_by_wallet_address(self, wallet_address):
        blocks = await self.config.mongo.async_db.blocks.find(
            {"transactions.outputs.to": wallet_address},
            {"_id": 0, "index": 1, "time": 1, "hash": 1, "transactions": 1}
        ).sort("index", -1).to_list(length=None)

        result = [
            {
                "index": block["index"],
                "time": block["time"],
                "hash": block["hash"],
                "transactions": [
                    txn
                    for txn in block.get("transactions", [])
                    if any(output.get("to") == wallet_address for output in txn.get("outputs", []))
                ],
            }
            for block in blocks
        ]

        if result:
            return self.render_as_json({
                "resultType": "txn_outputs_to",
                "searchedId": wallet_address,
                "result": result,
            })
        else:
            return self.render_as_json({
                "resultType": "txn_outputs_to",
                "searchedId": wallet_address,
                "result": [],
            })

    async def search_by_block_index(self, index):
        blocks = await self.config.mongo.async_db.blocks.find(
            {"index": index}, {"_id": 0}
        ).to_list(length=None)
        
        if blocks:
            return self.render_as_json({
                "resultType": "block_height",
                "result": [changetime(x) for x in blocks],
            })

    async def search_by_block_hash(self, block_hash):
        blocks = await self.config.mongo.async_db.blocks.find(
            {"hash": block_hash}, {"_id": 0}
        ).to_list(length=None)

        if blocks:
            return self.render_as_json({
                "resultType": "block_hash",
                "result": [changetime(x) for x in blocks],
            })

        transactions = await self.config.mongo.async_db.blocks.aggregate(
            [
                {"$match": {"transactions.hash": block_hash}},
                {"$unwind": "$transactions"},
                {"$match": {"transactions.hash": block_hash}},
                {
                    "$project": {
                        "_id": 0,
                        "result": [{
                            "$mergeObjects": ["$transactions", {
                                "blockIndex": "$index",
                                "blockHash": "$hash"
                            }]
                        }],
                    }
                }
            ]
        ).to_list(None)

        if transactions:
            return self.render_as_json({
                "resultType": "txn_hash",
                "searchedId": block_hash,
                "result": transactions[0]["result"],
            })

        mempool_result = await self.search_in_mempool_by_hash(block_hash)
        
        if mempool_result:
            mempool_result["blockHash"] = "MEMPOOL"
            mempool_result["blockIndex"] = "MEMPOOL"

            return self.render_as_json({
                "resultType": "txn_hash",
                "searchedId": block_hash,
                "result": [mempool_result],
            })

        return self.render_as_json({})

    async def search_by_base64_id(self, txn_id):
        blocks = await self.config.mongo.async_db.blocks.find(
            {"id": txn_id}, {"_id": 0}
        ).to_list(length=None)

        if blocks:
            return self.render_as_json({
                "resultType": "block_id",
                "result": [changetime(x) for x in blocks],
            })

        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"transactions.id": txn_id},
                        {"transactions.inputs.id": txn_id},
                    ]
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "blockIndex": "$index",
                    "blockHash": "$hash",
                    "transactions": {
                        "$filter": {
                            "input": "$transactions",
                            "as": "transaction",
                            "cond": {
                                "$or": [
                                    {"$eq": ["$$transaction.id", txn_id]},
                                    {
                                        "$anyElementTrue": {
                                            "$map": {
                                                "input": "$$transaction.inputs",
                                                "as": "input",
                                                "in": {"$eq": ["$$input.id", txn_id]},
                                            }
                                        }
                                    },
                                ]
                            },
                        }
                    },
                },
            },
            {"$unwind": "$transactions"},
            {
                "$project": {
                    "_id": 0,
                    "result": {
                        "$mergeObjects": ["$transactions", {
                            "blockIndex": "$blockIndex",
                            "blockHash": "$blockHash"
                        }]
                    },
                }
            },
        ]

        result = await self.config.mongo.async_db.blocks.aggregate(pipeline).to_list(length=None)
        transactions = [block["result"] for block in result if block.get("result")]

        if transactions:
            return self.render_as_json({
                "resultType": "txn_id",
                "searchedId": txn_id,
                "result": transactions,
            })

        mempool_result = await self.search_in_mempool_by_id(txn_id)

        if mempool_result:
            mempool_result["blockHash"] = "MEMPOOL"
            mempool_result["blockIndex"] = "MEMPOOL"

            return self.render_as_json({
                "resultType": "txn_id",
                "searchedId": txn_id,
                "result": [mempool_result],
            })

        return self.render_as_json({})

    async def search_by_public_key(self, public_key):
        blocks = await self.config.mongo.async_db.blocks.find(
            {"public_key": public_key}, {"_id": 0}
        ).to_list(length=None)
        
        if blocks:
            return self.render_as_json({
                "resultType": "block_height",
                "result": [changetime(x) for x in blocks],
            })

    async def search_in_mempool_by_hash(self, block_hash):
        try:
            result = await self.config.mongo.async_db.miner_transactions.find_one(
                {"hash": block_hash}, {"_id": 0}
            )

            return result if result else None
        except Exception as e:
            print(f"Error searching mempool by hash: {e}")
            return None

    async def search_in_mempool_by_id(self, txn_id):
        try:
            result = await self.config.mongo.async_db.miner_transactions.find_one(
                {"id": txn_id}, {"_id": 0}
            )

            return result if result else None
        except Exception as e:
            print(f"Error searching mempool by ID: {e}")
            return None

class ExplorerGetBalance(BaseHandler):
    async def get(self):
        address = self.get_argument("address", False)
        if not address:
            self.render_as_json({})
            return
        balance = await self.config.BU.get_wallet_balance(address)
        return self.render_as_json({"balance": "{0:.8f}".format(balance)})


class ExplorerLatestHandler(BaseHandler):
    async def get(self):
        """Returns abstract of the latest 10 blocks"""
        res = (
            self.config.mongo.async_db.blocks.find({}, {"_id": 0})
            .sort("index", -1)
            .limit(10)
        )
        res = await res.to_list(length=10)
        print(res[0])
        return self.render_as_json(
            {"resultType": "blocks", "result": res}
        )


class ExplorerLast50(BaseHandler):
    async def get(self):
        """Returns abstract of the latest 50 blocks miners"""
        latest = self.config.LatestBlock.block
        pipeline = [
            {"$match": {"index": {"$gte": latest["index"] - 50}}},
            {
                "$project": {
                    "outputs": 1,
                    "transaction": {"$arrayElemAt": ["$transactions", -1]},
                }
            },
            {
                "$project": {
                    "outputs": 1,
                    "output": {"$arrayElemAt": ["$transaction.outputs", 0]},
                }
            },
            {"$project": {"outputs": 1, "to": "$output.to"}},
            {"$group": {"_id": "$to", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]

        miners = []
        async for doc in self.config.mongo.async_db.blocks.aggregate(pipeline):
            miners.append(doc)

        return self.render_as_json(miners)

class ExplorerMempoolHandler(BaseHandler):
    async def get(self):
        """Returns mempool data from miner_transactions collection"""
        res = await self.config.mongo.async_db.miner_transactions.find({}).to_list(None)
        return self.render_as_json(
            {"resultType": "mempool", "result": res}
        )

EXPLORER_HANDLERS = [
    (r"/api-stats", HashrateAPIHandler),
    (r"/explorer", ExplorerHandler),
    (r"/explorer-search", ExplorerSearchHandler),
    (r"/explorer-get-balance", ExplorerGetBalance),
    (r"/explorer-latest", ExplorerLatestHandler),
    (r"/explorer-last50", ExplorerLast50),
    (r"/explorer-mempool", ExplorerMempoolHandler),
]
