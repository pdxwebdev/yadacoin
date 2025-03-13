"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Handlers required by the pool operations
"""

import time

from yadacoin.http.base import BaseHandler


class MinerStatsHandler(BaseHandler):
    async def get(self):
        address = self.get_query_argument("address", None)
        if not address:
            return self.render_as_json({"error": "No address provided"})

        current_time = time.time()
        miner_hashrate_seconds = 1200

        hashrate_aggregation = [
            {
                "$match": {
                    "time": {"$gt": current_time - miner_hashrate_seconds},
                    "$or": [{"address": address}, {"address_only": address}]
                }
            },
            {
                "$group": {
                    "_id": {
                        "worker": {
                            "$ifNull": [
                                {"$arrayElemAt": [{"$split": ["$address", "."]}, 1]},
                                "No worker"
                            ]
                        }
                    },
                    "total_shares": {"$sum": 1},
                    "total_weight": {"$sum": "$weight"},
                    "last_share_time": {"$max": "$time"}
                }
            }
        ]

        hashrate_cursor = self.config.mongo.async_db.shares.aggregate(hashrate_aggregation)
        hashrate_result = await hashrate_cursor.to_list(None)

        workers = []
        total_hashrate = 0
        total_shares = 0

        for doc in hashrate_result:
            worker_name = doc["_id"]["worker"]
            worker_hashrate = (doc["total_shares"] * self.config.pool_diff) / miner_hashrate_seconds

            workers.append({
                "worker_name": worker_name,
                "worker_hashrate": int(worker_hashrate),
                "worker_shares": doc["total_shares"],
                "last_share_time": doc["last_share_time"],
                "status": "Offline" if worker_hashrate == 0 else "Online"
            })

            total_hashrate += worker_hashrate
            total_shares += doc["total_shares"]

        self.render_as_json({
            "miner_address": address,
            "total_hashrate": int(total_hashrate),
            "total_shares": total_shares,
            "workers": workers
        })


class MinerPayoutsHandler(BaseHandler):
    async def get(self):
        address = self.get_query_argument("address", None)
        if not address:
            return self.render_as_json({"error": "No address provided"})

        query = {"txn.outputs.to": address}
        payouts_cursor = (
            self.config.mongo.async_db.share_payout.find(query, {"_id": 0})
            .sort([("index", -1)])
            .limit(50)
        )

        payouts = []
        async for payout in payouts_cursor:
            txn = payout.get("txn", {})
            tx_hash = txn.get("hash", "N/A")
            tx_time = txn.get("time", 0)

            block = await self.config.mongo.async_db.blocks.find_one(
                {"transactions.hash": tx_hash}, {"index": 1}
            )
            in_mempool = await self.config.mongo.async_db.miner_transactions.count_documents(
                {"hash": tx_hash}
            )
            in_failed = await self.config.mongo.async_db.failed_transactions.count_documents(
                {"txn.hash": tx_hash}
            )

            if block:
                status = "Confirmed"
                block_index = block["index"]
            elif in_mempool:
                status = "Pending"
                block_index = "N/A"
            elif in_failed:
                status = "Failed"
                block_index = "N/A"
            else:
                status = "Unknown"
                block_index = "N/A"

            payout_amount = next((o["value"] for o in txn.get("outputs", []) if o["to"] == address), 0)

            for_blocks = []
            for inp in txn.get("inputs", []):
                input_txid = inp.get("id")
                if input_txid:
                    source_blocks = self.config.mongo.async_db.blocks.find(
                        {"transactions.id": input_txid},
                        {"index": 1, "transactions": 1}
                    )
                    async for source_block in source_blocks:
                        last_tx = source_block["transactions"][-1]
                        if last_tx["id"] == input_txid:
                            for_blocks.append(str(source_block["index"]))

            for_blocks_str = ", ".join(for_blocks) if for_blocks else "N/A"

            payouts.append({
                "time": tx_time,
                "hash": tx_hash,
                "amount": payout_amount,
                "block_height": block_index,
                "for_block": for_blocks_str,
                "status": status
            })

        self.render_as_json({"payouts": payouts})


class PoolScanMissedPayoutsHandler(BaseHandler):
    async def get(self):
        start_index = self.get_query_argument("start_index")
        await self.config.pp.do_payout({"index": int(start_index)})
        self.render_as_json({"status": True})


# class PoolForceRefresh(BaseHandler):
#     async def get(self):
#         await self.config.mp.refresh()


POOL_HANDLERS = [
    (r"/miner-stats", MinerStatsHandler),
    (r"/miner-payouts", MinerPayoutsHandler),
    (r"/scan-missed-payouts", PoolScanMissedPayoutsHandler),
    # (r"/force-refresh", PoolForceRefresh),
]
