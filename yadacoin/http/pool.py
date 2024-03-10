"""
Handlers required by the pool operations
"""

import time

from yadacoin.http.base import BaseHandler

class MinerStatsHandler(BaseHandler):

    async def get(self):
        address = self.get_query_argument("address")

        miner_hashrate_seconds = 1200
        current_time = time.time()

        miner_stats_document = await self.config.mongo.async_db.miner_stats.find_one({"address": address})

        last_updated = 0
        existing_workers = set()
        worker_stats = {}

        if miner_stats_document:
            last_updated = miner_stats_document.get("last_updated", 0)
            worker_stats = miner_stats_document.get("workers", {})
            existing_workers = set(worker_stats.keys())

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

            worker_hashrate[worker_name] = {
                "worker_hashrate": worker_hashrate_individual,
                "worker_share": 0,
                "last_share_time": last_share_time
            }

        shares_query = {
            "$or": [
                {"address": address},
                {"address_only": address},
                {"address": {"$regex": f"^{address}\..*"}},
            ],
            "time": {"$gt": last_updated}
        }

        shares_aggregation = [
            {"$match": shares_query},
            {"$group": {
                "_id": {
                    "address": "$address",
                    "worker": {"$ifNull": ["$worker", "No worker"]}
                },
                "worker_share": {"$sum": 1},
                "total_weight": {"$sum": "$weight"},
                "last_share_time": {"$max": "$time"}
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
                    "worker_share": 0,
                    "last_share_time": 0
                }

            worker_shares[worker_name]["worker_share"] += doc["worker_share"]
            total_share += doc["worker_share"]
            worker_shares[worker_name]["last_share_time"] = max(
                worker_shares[worker_name]["last_share_time"],
                doc["last_share_time"]
            )

        for worker_name, worker_share_stats in worker_shares.items():
            if worker_name not in worker_stats:
                worker_stats[worker_name] = {
                    "worker_share": 0,
                    "last_share_time": 0,
                    "worker_hashrate": 0
                }

            worker_stats[worker_name]["worker_share"] += worker_share_stats["worker_share"]
            worker_stats[worker_name]["last_share_time"] = max(
                worker_stats[worker_name]["last_share_time"],
                worker_share_stats["last_share_time"]
            )

            worker_stats[worker_name]["worker_hashrate"] = worker_hashrate.get(worker_name, {}).get("worker_hashrate", 0)

        for missing_worker in existing_workers - set(worker_shares.keys()):
            worker_stats[missing_worker] = miner_stats_document.get("workers", {}).get(missing_worker, {})

        total_share += sum(worker_stats[worker_name]["worker_share"] for worker_name in worker_stats)

        await self.config.mongo.async_db.miner_stats.update_one(
            {"address": address},
            {"$set": {"last_updated": current_time, "workers": worker_stats}},
            upsert=True
        )

        miner_stats_response = [
            {
                "worker_name": worker_name,
                "worker_hashrate": worker_stats["worker_hashrate"],
                "worker_share": worker_stats["worker_share"],
                "status": "Offline" if worker_stats["worker_hashrate"] == 0 else "Online",
                "last_share_time": worker_stats["last_share_time"]
            }
            for worker_name, worker_stats in worker_stats.items()
        ]

        self.render_as_json({
            "miner_stats": miner_stats_response,
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


class PoolScanMissingTxnHandler(BaseHandler):
    async def get(self):
        pool_public_key = (
            self.config.pool_public_key
            if hasattr(self.config, "pool_public_key")
            else self.config.public_key
        )

        coinbase_transactions = self.config.mongo.async_db.blocks.find(
            {"transactions.outputs.to": pool_public_key, "transactions.inputs": []},
            {"_id": 0, "transactions": 1}
        )

        missing_payouts = []

        used_transactions = set()

        async for block in coinbase_transactions:
            for coinbase_txn in block["transactions"]:
                if not coinbase_txn.get("inputs"):
                    if coinbase_txn["public_key"] == pool_public_key:
                        missing_payouts.append(coinbase_txn)

                        used_transactions.add(coinbase_txn["id"])

        async for block in self.config.mongo.async_db.blocks.find():
            for txn in block["transactions"]:
                if txn.get("inputs"):
                    for input_txn in txn["inputs"]:
                        used_transactions.add(input_txn["id"])

        missing_payouts = [txn for txn in missing_payouts if txn["id"] not in used_transactions]

        self.render_as_json({"missing_payouts": missing_payouts})

POOL_HANDLERS = [
    (r"/miner-stats-for-address", MinerStatsHandler),
    (r"/payouts-for-address", PoolPayoutsHandler),
    (r"/pool-blocks", PoolBlocksHandler),
    (r"/scan-missed-payouts", PoolScanMissedPayoutsHandler),
    (r"/scan-missed-txn", PoolScanMissingTxnHandler),
]
