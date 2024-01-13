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
            shares_query = {"address": address}
        else:
            hashrate_query["$or"] = [{"address": address}, {"address_only": address}]
            shares_query = {
                "$or": [
                    {"address": address},
                    {"address_only": address},
                    {"address": {"$regex": f"^{address}\..*"}}
                ]
            }

        hashrate_cursor = self.config.mongo.async_db.shares.aggregate([
            {"$match": hashrate_query},
            {"$group": {
                "_id": {"address": "$address", "worker": {"$ifNull": [{"$arrayElemAt": [{"$split": ["$address", "."]}, 1]}, "No worker"]}},
                "total_weight": {"$sum": "$weight"},
            }}
        ])

        worker_hashrate = {}
        total_hashrate = 0
        total_share = 0
        total_hash = 0

        async for doc in hashrate_cursor:
            worker_name = doc["_id"]["worker"]
            total_weight = doc["total_weight"]

            worker_hashrate_individual = total_weight // miner_hashrate_seconds
            total_hashrate += worker_hashrate_individual

            if worker_name not in worker_hashrate:
                worker_hashrate[worker_name] = {
                    "worker_hashrate": 0,
                    "worker_share": 0,
                    "worker_hash": 0
                }

            worker_hashrate[worker_name]["worker_hashrate"] += worker_hashrate_individual
            worker_hashrate[worker_name]["worker_hash"] += total_weight

        shares_cursor = self.config.mongo.async_db.shares.aggregate([
            {"$match": shares_query},
            {"$group": {
                "_id": {"address": "$address", "worker": {"$ifNull": ["$worker", "No worker"]}},
                "worker_share": {"$sum": 1},
            }}
        ])

        worker_shares = {}

        async for doc in shares_cursor:
            worker_name = doc["_id"]["worker"]

            if "." in doc["_id"]["address"]:
                worker_name = doc["_id"]["address"].split(".")[-1]

            if worker_name not in worker_shares:
                worker_shares[worker_name] = {
                    "worker_share": 0,
                }

            worker_shares[worker_name]["worker_share"] += doc["worker_share"]
            total_share += doc["worker_share"]

        total_hash = sum(worker_hash_val["worker_hash"] for worker_hash_val in worker_hashrate.values())

        miner_stats = []
        for worker_name in set(worker_hashrate.keys()) | set(worker_shares.keys()):
            worker_hashrate_val = worker_hashrate.get(worker_name, {}).get("worker_hashrate", 0)
            worker_share_val = worker_shares.get(worker_name, {}).get("worker_share", 0)
            worker_hash_val = worker_hashrate.get(worker_name, {}).get("worker_hash", 0)
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
            "total_hash": int(total_hash)
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

class PoolBlocksHandler(BaseHandler):
    async def get(self):
        thirty_days_ago_timestamp = time.time() - (30 * 24 * 60 * 60)

        pool_blocks = (
            await self.config.mongo.async_db.pool_blocks
            .find(
                {"found_time": {"$gte": thirty_days_ago_timestamp}},
                {"_id": 0, "index": 1, "time": 1, "found_time": 1, "target": 1, "transactions": 1, "status": 1, "hash": 1, "effort": 1, "miner_address": 1}
            )
            .sort("index", -1)
            .to_list(None)
        )

        total_effort = 0
        valid_effort_count = 0

        formatted_blocks = []
        for block in pool_blocks:
            if "effort" in block:
                total_effort += block["effort"]
                valid_effort_count += 1
            miner_address = block.get("miner_address", "unknown")

            formatted_blocks.append({
                "index": block["index"],
                "time": block["time"],
                "found_time": block["found_time"],
                "target": block["target"],
                "transactions": block["transactions"],
                "status": block["status"],
                "hash": block["hash"],
                "effort": block["effort"] if "effort" in block else "N/A",
                "miner_address": miner_address
            })

        average_effort = total_effort / valid_effort_count if valid_effort_count > 0 else "N/A"
        block_confirmation = self.config.block_confirmation

        pool_info = {
            "pool_address": self.config.address,
            "average_effort": average_effort,
            "block_confirmation": block_confirmation,
        }

        self.render_as_json({"pool": pool_info, "blocks": formatted_blocks})

class PoolScanMissedPayoutsHandler(BaseHandler):
    async def get(self):
        start_index = self.get_query_argument("start_index")
        await self.config.pp.do_payout({"index": int(start_index)})
        self.render_as_json({"status": True})


POOL_HANDLERS = [
    (r"/miner-stats-for-address", MinerStatsHandler),
    (r"/payouts-for-address", PoolPayoutsHandler),
    (r"/pool-blocks", PoolBlocksHandler),
    (r"/scan-missed-payouts", PoolScanMissedPayoutsHandler),
]
