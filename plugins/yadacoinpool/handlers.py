import os
import time

import requests
from tornado.web import StaticFileHandler

from yadacoin import version
from yadacoin.core.chain import CHAIN
from yadacoin.http.base import BaseHandler


class BaseWebHandler(BaseHandler):
    async def prepare(self):
        await super().prepare(exceptions=["/pool-info"])

    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")


class PoolStatsInterfaceHandler(BaseWebHandler):
    async def get(self):
        self.render(
            "pool-stats.html",
            yadacoin=self.yadacoin_vars,
            username_signature=self.get_secure_cookie("username_signature"),
            username=self.get_secure_cookie("username"),
            rid=self.get_secure_cookie("rid"),
            title="YadaCoin - Pool Stats",
            mixpanel="pool stats page",
        )


cache = {"market_data": None}
last_refresh = time.time()


class MarketInfoHandler(BaseWebHandler):
    async def get(self):
        market_data = cache.get("market_data")

        if market_data is None or time.time() - last_refresh > 3600:
            market_data = await self.fetch_market_data()
            cache["market_data"] = market_data

        self.render_as_json(market_data)

    async def fetch_market_data(self):
        symbols = ["YDA_USDT", "YDA_BTC"]
        market_data = {}

        for symbol in symbols:
            url = f"https://api.xeggex.com/api/v2/market/getbysymbol/{symbol}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
            }

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                market_data[symbol.lower()] = {
                    "last_btc": float(response.json()["lastPrice"]) if symbol == "YDA_BTC" else 0,
                    "last_usdt": float(response.json()["lastPrice"]) if symbol == "YDA_USDT" else 0
                }
            else:
                market_data[symbol.lower()] = {
                    "last_btc": 0,
                    "last_usdt": 0
                }

        formatted_data = {
            "last_btc": market_data["yda_btc"]["last_btc"],
            "last_usdt": market_data["yda_usdt"]["last_usdt"]
        }

        return formatted_data

class PoolInfoHandler(BaseWebHandler):
    async def get(self):
        await self.config.LatestBlock.block_checker()
        latest_pool_info = await self.config.mongo.async_db.pool_info.find_one(
            filter={},
            sort=[("time", -1)]
        )
        
        pool_hash_rate = latest_pool_info.get("pool_hash_rate", 0)
        network_hash_rate = latest_pool_info.get("network_hash_rate", 0)
        avg_network_hash_rate = latest_pool_info.get("avg_network_hash_rate", 0)
        net_difficulty = latest_pool_info.get("net_difficulty", 0)

        twenty_four_hours_ago = time.time() - 24 * 60 * 60

        history_query = {
            "time": {"$gte": twenty_four_hours_ago},
            "pool_hash_rate": {"$exists": True}
        }

        cursor = self.config.mongo.async_db.pool_info.find(
            history_query,
            {"_id": 0, "time": 1, "pool_hash_rate": 1}
        ).sort([("time", -1)])

        hashrate_history = await cursor.to_list(None)

        pool_public_key = (
            self.config.pool_public_key
            if hasattr(self.config, "pool_public_key")
            else self.config.public_key
        )
        total_blocks_found = await self.config.mongo.async_db.blocks.count_documents(
            {"public_key": pool_public_key}
        )
        pool_blocks_found_list = await self.config.mongo.async_db.pool_blocks.find(
            {},
            {"_id": 0, "index": 1, "found_time": 1, "time": 1}
        ).sort([("index", -1)]).to_list(5)

        expected_blocks = 144
        daily_blocks_found = await self.config.mongo.async_db.blocks.count_documents(
            {"time": {"$gte": time.time() - (600 * 144)}}
        )
        avg_block_time = daily_blocks_found / expected_blocks * 600

        try:
            pool_perecentage = pool_hash_rate / network_hash_rate * 100
        except:
            pool_perecentage = 0

        if pool_hash_rate == 0:
            avg_pool_block_time = 0
        else:
            avg_pool_block_time = int(
                network_hash_rate * avg_block_time // pool_hash_rate
            )

        if avg_pool_block_time == 0:
            avg_time = ["N/a"]
        else:
            avg_time = []
            for d, u in [(86400, "day"), (3600, "hour"), (60, "minute")]:
                n, avg_pool_block_time = divmod(avg_pool_block_time, d)
                if n:
                    avg_time.append(f"{n} {u}" + "s" * (n > 1))
            avg_time = "  ".join(avg_time)

        miner_count_pool_stat = await self.config.mongo.async_db.pool_stats.find_one(
            {"stat": "miner_count"}
        ) or {"value": 0}
        worker_count_pool_stat = await self.config.mongo.async_db.pool_stats.find_one(
            {"stat": "worker_count"}
        ) or {"value": 0}
        payouts = (
            await self.config.mongo.async_db.share_payout.find({}, {"_id": 0})
            .sort([("index", -1)])
            .to_list(50)
        )

        pipeline = [
            {
                "$unwind": "$txn.outputs"
            },
            {
                "$match": {
                    "txn.outputs.to": {"$ne": self.config.address}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_payments": {"$sum": "$txn.outputs.value"}
                }
            }
        ]

        result = await self.config.mongo.async_db.share_payout.aggregate(pipeline).to_list(1)

        total_payments = result[0]["total_payments"] if result else 0

        self.render_as_json(
            {
                "node": {
                    "version": ".".join([str(x) for x in version]),
                },
                "pool": {
                    "pool_diff": self.config.pool_diff,
                    "hashes_per_second": pool_hash_rate,
                    "miner_count": miner_count_pool_stat["value"],
                    "worker_count": worker_count_pool_stat["value"],
                    "payout_scheme": self.config.payout_scheme,
                    "pool_fee": self.config.pool_take,
                    "pool_address": self.config.address,
                    "min_payout": 0,
                    "total_payments": total_payments,
                    "url": getattr(
                        self.config,
                        "pool_url",
                        f"{self.config.peer_host}:{self.config.stratum_pool_port}",
                    ),
                    "last_five_blocks": [
                        {"timestamp": x["found_time"], "height": x["index"]}
                        for x in pool_blocks_found_list[:5]
                    ],
                    "blocks_found": total_blocks_found,
                    "fee": self.config.pool_take,
                    "payout_frequency": self.config.pool_payer_wait,
                    "payouts": payouts,
                    "pool_perecentage": pool_perecentage,
                    "avg_block_time": avg_time,
                    "hashrate_history": hashrate_history,
                },
                "network": {
                    "height": self.config.LatestBlock.block.index,
                    "reward": CHAIN.get_block_reward(
                        self.config.LatestBlock.block.index
                    ),
                    "last_block": self.config.LatestBlock.block.time,
                    "avg_hashes_per_second": avg_network_hash_rate,
                    "current_hashes_per_second": network_hash_rate,
                    "difficulty": net_difficulty,
                },
                "coin": {
                    "algo": "randomx YDA",
                    "circulating": CHAIN.get_circulating_supply(
                        self.config.LatestBlock.block.index
                    ),
                    "max_supply": 21000000,
                },
            }
        )



HANDLERS = [
    (r"/market-info", MarketInfoHandler),
    (r"/pool-info", PoolInfoHandler),
    (r"/", PoolStatsInterfaceHandler),
    (
        r"/yadacoinpoolstatic/(.*)",
        StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "static")},
    ),
]
