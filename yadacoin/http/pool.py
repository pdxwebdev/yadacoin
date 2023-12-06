"""
Handlers required by the pool operations
"""

import time

from yadacoin.http.base import BaseHandler

class MinerStatsHandler(BaseHandler):
    async def get(self):
        address = self.get_query_argument("address")
        query = {
            "$or": [
                {"address": address},
                {"address_only": address},
                {"address": {"$regex": f"^{address}\..*"}}
            ]
        }

        miner_hashrate_seconds = 1200
        hashrate_query = {"time": {"$gt": time.time() - miner_hashrate_seconds}}
        
        if "." in address:
            hashrate_query["address"] = address
        else:
            hashrate_query["$or"] = [
                {"address": address},
                {"address_only": address},
            ]

        hashrate_cursor = self.config.mongo.async_db.shares.aggregate([
            {"$match": hashrate_query},
            {"$group": {
                "_id": {"address": "$address", "worker": {"$ifNull": [{"$arrayElemAt": [{"$split": ["$address", "."]}, 1]}, "No worker"]}},
                "number_of_shares": {"$sum": 1}
            }}
        ])

        worker_hashrate = {}
        total_hashrate = 0
        total_share = 0

        async for doc in hashrate_cursor:
            worker_name = doc["_id"]["worker"]
            number_of_shares = doc["number_of_shares"]

            worker_hashrate_individual = number_of_shares * self.config.pool_diff // miner_hashrate_seconds
            total_hashrate += worker_hashrate_individual

            if worker_name not in worker_hashrate:
                worker_hashrate[worker_name] = {
                    "worker_hashrate": 0,
                    "worker_share": 0
                }

            worker_hashrate[worker_name]["worker_hashrate"] += worker_hashrate_individual

        shares_query = {
            "$or": [
                {"address": address},
                {"address_only": address},
                {"address": {"$regex": f"^{address}\..*"}}
            ]
        }

        shares_cursor = self.config.mongo.async_db.shares.aggregate([
            {"$match": shares_query},
            {"$group": {
                "_id": {"address": "$address", "worker": {"$ifNull": ["$worker", ""]}},
                "total_share": {"$sum": 1},
                "total_hash": {"$sum": {"$multiply": ["$difficulty", "$height"]}}
            }}
        ])

        worker_shares = {}

        async for doc in shares_cursor:
            worker_name = doc["_id"]["worker"] if doc["_id"]["worker"] else "No worker"

            if "." in doc["_id"]["address"]:
                worker_name = doc["_id"]["address"].split(".")[-1]

            if worker_name not in worker_shares:
                worker_shares[worker_name] = {
                    "worker_share": 0,
                    "worker_hash": 0
                }

            worker_shares[worker_name]["worker_share"] += doc["total_share"]
            worker_shares[worker_name]["worker_hash"] += doc["total_share"] * self.config.pool_diff
            total_share += doc["total_share"]

        miner_stats = []
        for worker_name in set(worker_hashrate.keys()) | set(worker_shares.keys()):
            worker_hashrate_val = worker_hashrate.get(worker_name, {}).get("worker_hashrate", 0)
            worker_share_val = worker_shares.get(worker_name, {}).get("worker_share", 0)
            worker_hash_val = worker_shares.get(worker_name, {}).get("worker_hash", 0)
            status = "Offline" if worker_hashrate_val == 0 else "Online"

            stats = {
                "worker_name": worker_name,
                "worker_hashrate": worker_hashrate_val,
                "worker_share": worker_share_val,
                "worker_hash": worker_hash_val,
                "status": status
            }
            miner_stats.append(stats)

        self.render_as_json({
            "miner_stats": miner_stats,
            "total_hashrate": int(total_hashrate),
            "total_share": int(total_share),
            "total_hash": int(total_share * self.config.pool_diff)
        })

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

class PoolScanMissedPayoutsHandler(BaseHandler):
    async def get(self):
        start_index = self.get_query_argument("start_index")
        await self.config.pp.do_payout({"index": int(start_index)})
        self.render_as_json({"status": True})


POOL_HANDLERS = [
    (r"/miner-stats-for-address", MinerStatsHandler),
    (r"/payouts-for-address", PoolPayoutsHandler),
    (r"/scan-missed-payouts", PoolScanMissedPayoutsHandler),
]
