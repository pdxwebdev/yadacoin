"""
Handlers required by the pool operations
"""

import time

from yadacoin.http.base import BaseHandler

class MinerStatsHandler(BaseHandler):
    async def get(self):
        address = self.get_query_argument("address")

        miner_hashrate_seconds = 1200
        hide_worker_after_seconds = 3600  # jedna godzina w sekundach

        current_time = time.time()

        hashrate_query = {
            "time": {"$gt": current_time - miner_hashrate_seconds},
            "$or": [{"address": address}, {"address_only": address}]
        }
        hashrate_aggregation = [
            {"$match": hashrate_query},
            {"$group": {
                "_id": {
                    "address": "$address",
                    "worker": {"$ifNull": [{"$arrayElemAt": [{"$split": ["$address", "."]}, 1]}, "No worker"]}
                },
                "total_weight": {"$sum": "$weight"},
                "last_share_time": {"$max": "$time"}
            }}
        ]

        hashrate_cursor = self.config.mongo.async_db.shares.aggregate(hashrate_aggregation)
        hashrate_result = await hashrate_cursor.to_list(None)

        worker_hashrate = {}
        total_hashrate = 0

        for doc in hashrate_result:
            worker_name = doc["_id"]["worker"]
            total_weight = doc["total_weight"]
            last_share_time = doc["last_share_time"]

            worker_hashrate_individual = total_weight // miner_hashrate_seconds
            total_hashrate += worker_hashrate_individual

            if worker_name not in worker_hashrate:
                worker_hashrate[worker_name] = {
                    "worker_hashrate": 0,
                    "worker_share": 0,
                    "last_share_time": 0
                }

            worker_hashrate[worker_name]["worker_hashrate"] += worker_hashrate_individual
            worker_hashrate[worker_name]["last_share_time"] = max(
                worker_hashrate[worker_name]["last_share_time"],
                last_share_time
            )

        shares_query = {
            "$or": [
                {"address": address},
                {"address_only": address},
                {"address": {"$regex": f"^{address}\..*"}}
            ]
        }
        shares_aggregation = [
            {"$match": shares_query},
            {"$group": {
                "_id": {
                    "address": "$address",
                    "worker": {"$ifNull": ["$worker", "No worker"]}
                },
                "worker_share": {"$sum": 1}
            }}
        ]

        shares_cursor = self.config.mongo.async_db.shares.aggregate(shares_aggregation)
        shares_result = await shares_cursor.to_list(None)

        worker_shares = {}
        total_share = 0

        for doc in shares_result:
            worker_name = doc["_id"]["worker"]

            if "." in doc["_id"]["address"]:
                worker_name = doc["_id"]["address"].split(".")[-1]

            if worker_name not in worker_shares:
                worker_shares[worker_name] = {
                    "worker_share": 0
                }

            worker_shares[worker_name]["worker_share"] += doc["worker_share"]
            total_share += doc["worker_share"]

        miner_stats = []
        for worker_name in set(worker_hashrate.keys()) | set(worker_shares.keys()):
            worker_hashrate_val = worker_hashrate.get(worker_name, {}).get("worker_hashrate", 0)
            worker_share_val = worker_shares.get(worker_name, {}).get("worker_share", 0)
            last_share_time = worker_hashrate.get(worker_name, {}).get("last_share_time", 0)
            if time.time() - last_share_time > hide_worker_after_seconds:
                continue
            status = "Offline" if worker_hashrate_val == 0 else "Online"

            stats = {
                "worker_name": worker_name,
                "worker_hashrate": worker_hashrate_val,
                "worker_share": worker_share_val,
                "status": status,
                "last_share_time": last_share_time
            }
            miner_stats.append(stats)

        self.render_as_json({
            "miner_stats": miner_stats,
            "total_hashrate": int(total_hashrate),
            "total_share": int(total_share)
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
        ).sort([("index", -1)]).limit(150)
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
