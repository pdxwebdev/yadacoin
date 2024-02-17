"""
Handlers required by the pool operations
"""
import time

from yadacoin.http.base import BaseHandler


class PoolSharesHandler(BaseHandler):
    async def get(self):
        address = self.get_query_argument("address")
        query = {"address": address}
        if "." not in address:
            query = {
                "$or": [
                    {"address": address},
                    {"address_only": address},
                ]
            }
        total_share = await self.config.mongo.async_db.shares.count_documents(query)
        total_hash = total_share * self.config.pool_diff
        self.render_as_json({"total_hash": int(total_hash)})


class PoolPayoutsHandler(BaseHandler):
    async def get(self):
        address = self.get_query_argument("address")
        query = {"address": address}
        if "." in address:
            query = {"address": address.split(".")[0]}
        out = []
        results = self.config.mongo.async_db.share_payout.find(
            {"txn.outputs.to": address}, {"_id": 0}
        ).sort([("index", -1)])
        async for result in results:
            if (
                await self.config.mongo.async_db.blocks.count_documents(
                    {"transactions.id": result["txn"]["id"]}
                )
                > 0
            ):
                out.append(result)
        self.render_as_json({"results": out})


class PoolHashRateHandler(BaseHandler):
    async def get(self):
        address = self.get_query_argument("address")

        if "." in address:
            query = {"address": address}
        else:
            query = {"address_only": address}

        last_share = await self.config.mongo.async_db.shares.find_one(
            query, {"_id": 0}, sort=[("time", -1)]
        )

        if not last_share:
            return self.render_as_json({"result": 0})

        mining_time_interval = 600

        pipeline = [
            {
                "$match": {
                    **query,
                    "time": {"$gte": time.time() - mining_time_interval}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_weight": {"$sum": "$weight"}
                }
            }
        ]

        result = await self.config.mongo.async_db.shares.aggregate(pipeline).to_list(1)

        if result and len(result) > 0:
            total_weight = result[0]["total_weight"]
            miner_hash_rate = total_weight / mining_time_interval
        else:
            miner_hash_rate = 0

        self.render_as_json({"miner_hashrate": int(miner_hash_rate)})


class PoolScanMissedPayoutsHandler(BaseHandler):
    async def get(self):
        start_index = self.get_query_argument("start_index")
        await self.config.pp.do_payout({"index": int(start_index)})
        self.render_as_json({"status": True})


POOL_HANDLERS = [
    (r"/shares-for-address", PoolSharesHandler),
    (r"/payouts-for-address", PoolPayoutsHandler),
    (r"/hashrate-for-address", PoolHashRateHandler),
    (r"/scan-missed-payouts", PoolScanMissedPayoutsHandler),
]
