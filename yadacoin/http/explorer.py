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
        res = await self.config.mongo.async_db.blocks.count_documents(
            {"transactions.outputs.to": term}
        )
        if res:
            balance = await self.config.BU.get_wallet_balance(term)
            blocks = await self.config.mongo.async_db.blocks.find(
                {"transactions.outputs.to": term},
                {"_id": 0, "index": 1, "time": 1, "hash": 1, "transactions": 1},
            ).sort("index", -1).limit(25).to_list(length=25)

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

        result_type = self.get_argument("result_type", False)
        if result_type == "get_wallet_balance":
            try:
                return await self.get_wallet_balance(term)
            except Exception:
                raise

        try:
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"index": int(term)}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "block_height",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"index": int(term)}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass
        try:
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"public_key": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "block_height",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"public_key": term}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass
        try:
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"transactions.public_key": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "block_height",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"transactions.public_key": term}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass
        try:
            re.search(r"[A-Fa-f0-9]{64}", term).group(0)
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"hash": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "block_hash",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"hash": term}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            base64.b64decode(term.replace(" ", "+"))
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"id": term.replace(" ", "+")}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "block_id",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"id": term.replace(" ", "+")}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            re.search(r"[A-Fa-f0-9]{64}", term).group(0)

            transactions = await self.config.mongo.async_db.blocks.aggregate(
                [
                    {
                        "$match": {
                            "transactions.hash": term,
                        }
                    },
                    {
                        "$unwind": "$transactions"
                    },
                    {
                        "$match": {
                            "transactions.hash": term
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "transactions": {
                                "$push": "$transactions"
                            }
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "transactions": 1
                        }
                    }
                ]
            ).to_list(None)

            return self.render_as_json(
                {
                    "resultType": "txn_hash",
                    "searchedHash": term,
                    "result": transactions[0]["transactions"],
                }
            )

        except Exception as e:
            print(f"Error processing transaction hash: {e}")
            pass

        try:
            re.search(r"[A-Fa-f0-9]{64}", term).group(0)
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"transactions.rid": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "txn_rid",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"transactions.rid": term}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            base64.b64decode(term.replace(" ", "+"))
            res = await self.config.mongo.async_db.blocks.count_documents(
                {
                    "$or": [
                        {"transactions.id": term.replace(" ", "+")},
                        {"transactions.inputs.id": term.replace(" ", "+")},
                    ]
                }
            )
            if res:
                transactions = []
                async for block in self.config.mongo.async_db.blocks.find(
                    {
                        "$or": [
                            {"transactions.id": term.replace(" ", "+")},
                            {"transactions.inputs.id": term.replace(" ", "+")},
                        ]
                    },
                    {"_id": 0, "transactions": 1},
                ):
                    if isinstance(block.get("transactions"), list):
                        for transaction in block.get("transactions"):
                            if transaction.get("id") == term.replace(" ", "+"):
                                transactions.append(transaction)
                            elif transaction.get("inputs") and any(inp.get("id") == term.replace(" ", "+") for inp in transaction["inputs"]):
                                transactions.append(transaction)
                    else:
                        if block.get("transactions").get("id") == term.replace(" ", "+"):
                            transactions.append(block.get("transactions"))
                        elif block.get("transactions").get("inputs") and any(inp.get("id") == term.replace(" ", "+") for inp in block["transactions"]["inputs"]):
                            transactions.append(block.get("transactions"))

                return self.render_as_json(
                    {
                        "resultType": "txn_id",
                        "searchedId": term.replace(" ", "+"),
                        "result": transactions,
                    }
                )
        except Exception as e:
            print(f"Error processing transaction ID: {e}")
            pass

        try:
            res = await self.get_wallet_balance(term)
            if res:
                return res
        except Exception:
            pass

        try:
            base64.b64decode(term.replace(" ", "+"))
            res = await self.config.mongo.async_db.miner_transactions.count_documents(
                {"id": term.replace(" ", "+")}
            )
            if res:
                results = [
                    changetime(x)
                    async for x in self.config.mongo.async_db.miner_transactions.find(
                        {"id": term.replace(" ", "+")}, {"_id": 0}
                    )
                ]
                return self.render_as_json(
                    {
                        "resultType": "mempool_id",
                        "searchedId": term.replace(" ", "+"),
                        "result": results,
                    }
                )
        except:
            pass

        try:
            match = re.search(r"[A-Fa-f0-9]{64}", term)
            if match:
                res = await self.config.mongo.async_db.miner_transactions.count_documents(
                    {"hash": term}
                )
                if res:
                    results = [
                        changetime(x)
                        async for x in self.config.mongo.async_db.miner_transactions.find(
                            {"hash": term}, {"_id": 0}
                        )
                    ]
                    return self.render_as_json(
                        {
                            "resultType": "mempool_hash",
                            "searchedId": term,
                            "result": results,
                        }
                    )
        except:
            pass

        try:
            re.search(r"[A-Fa-f0-9]+", term).group(0)
            res = await self.config.mongo.async_db.miner_transactions.count_documents(
                {"outputs.to": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "mempool_outputs_to",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.miner_transactions.find(
                                {"outputs.to": term}, {"_id": 0}
                            )
                            .sort("index", -1)
                            .limit(10)
                        ],
                    }
                )
        except:
            pass

        try:
            res = await self.config.mongo.async_db.miner_transactions.count_documents(
                {"public_key": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "mempool_public_key",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.miner_transactions.find(
                                {"public_key": term}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            res = await self.config.mongo.async_db.miner_transactions.count_documents(
                {"rid": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "mempool_rid",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.miner_transactions.find(
                                {"rid": term}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            base64.b64decode(term.replace(" ", "+"))
            res = await self.config.mongo.async_db.failed_transactions.count_documents(
                {"txn.id": term.replace(" ", "+")}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "failed_id",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.failed_transactions.find(
                                {"txn.id": term.replace(" ", "+")},
                                {"_id": 0, "txn._id": 0},
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            re.search(r"[A-Fa-f0-9]{64}", term).group(0)
            res = await self.config.mongo.async_db.failed_transactions.count_documents(
                {"txn.hash": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "failed_hash",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.failed_transactions.find(
                                {"txn.hash": term},
                                {"_id": 0, "txn._id": 0},
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            re.search(r"[A-Fa-f0-9]+", term).group(0)
            res = await self.config.mongo.async_db.failed_transactions.count_documents(
                {"txn.outputs.to": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "failed_outputs_to",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.failed_transactions.find(
                                {"txn.outputs.to": term},
                                {"_id": 0, "txn._id": 0},
                            )
                            .sort("index", -1)
                            .limit(10)
                        ],
                    }
                )
        except:
            pass

        try:
            res = await self.config.mongo.async_db.failed_transactions.count_documents(
                {"txn.public_key": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "failed_public_key",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.failed_transactions.find(
                                {"txn.public_key": term},
                                {"_id": 0, "txn._id": 0},
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            res = await self.config.mongo.async_db.failed_transactions.count_documents(
                {"txn.rid": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "failed_rid",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.failed_transactions.find(
                                {"txn.rid": term},
                                {"_id": 0, "txn._id": 0},
                            )
                        ],
                    }
                )
        except:
            pass

        return self.render_as_json({})


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
