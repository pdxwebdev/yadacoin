import os
import time

import requests
from tornado.web import StaticFileHandler

from yadacoin import version
from yadacoin.core.chain import CHAIN
from yadacoin.http.base import BaseHandler


class BaseWebHandler(BaseHandler):
    def prepare(self):
        if self.request.protocol == "http" and self.config.ssl.is_valid():
            self.redirect(
                "https://" + self.request.host + self.request.uri, permanent=False
            )

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


class PoolInfoHandler(BaseWebHandler):
    async def get(self):
        def get_ticker():
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
            }
            return requests.get(
                "https://safe.trade/api/v2/peatio/public/markets/tickers",
                headers=headers,
            )

        try:
            if not hasattr(self.config, "ticker"):
                self.config.ticker = get_ticker()
                self.config.last_update = time.time()
            if (time.time() - self.config.last_update) > (600 * 6):
                self.config.ticker = get_ticker()
                self.config.last_update = time.time()
            last_btc = float(self.config.ticker.json()["ydabtc"]["ticker"]["last"])
            last_usdt = float(self.config.ticker.json()["ydausdt"]["ticker"]["last"])
        except:
            last_btc = 0
            last_usdt = 0
        await self.config.LatestBlock.block_checker()
        pool_public_key = (
            self.config.pool_public_key
            if hasattr(self.config, "pool_public_key")
            else self.config.public_key
        )
        total_blocks_found = await self.config.mongo.async_db.blocks.count_documents(
            {"public_key": pool_public_key}
        )
        pool_blocks_found_list = (
            await self.config.mongo.async_db.blocks.find(
                {
                    "public_key": pool_public_key,
                },
                {"_id": 0},
            )
            .sort([("index", -1)])
            .to_list(100)
        )
        expected_blocks = 144
        mining_time_interval = 600
        shares_count = await self.config.mongo.async_db.shares.count_documents(
            {"time": {"$gte": time.time() - mining_time_interval}}
        )
        if shares_count > 0:
            pool_hash_rate = (
                shares_count * self.config.pool_diff
            ) / mining_time_interval
        else:
            pool_hash_rate = 0

        daily_blocks_found = await self.config.mongo.async_db.blocks.count_documents(
            {"time": {"$gte": time.time() - (600 * 144)}}
        )
        if daily_blocks_found > 0:
            net_target = self.config.LatestBlock.block.target
        avg_blocks_found = self.config.mongo.async_db.blocks.find(
            {"time": {"$gte": time.time() - (600 * 36)}}
        )
        avg_blocks_found = await avg_blocks_found.to_list(length=52)
        avg_block_time = daily_blocks_found / expected_blocks * 600
        if len(avg_blocks_found) > 0:
            avg_net_target = 0
            for block in avg_blocks_found:
                avg_net_target += int(block["target"], 16)
            avg_net_target = avg_net_target / len(avg_blocks_found)
            avg_net_difficulty = (
                0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
                / avg_net_target
            )
            net_difficulty = (
                0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
                / net_target
            )
            avg_network_hash_rate = (
                len(avg_blocks_found)
                / 36
                * avg_net_difficulty
                * 2**16
                / avg_block_time
            )
            network_hash_rate = net_difficulty * 2**16 / 600
        else:
            avg_network_hash_rate = 1
            net_difficulty = (
                0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
                / 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
            )
            network_hash_rate = 0

        pool_perecentage = pool_hash_rate / network_hash_rate * 100

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
            .to_list(100)
        )

        self.render_as_json(
            {
                "node": {
                    "latest_block": self.config.LatestBlock.block.to_dict(),
                    "health": self.config.health.to_dict(),
                    "version": ".".join([str(x) for x in version]),
                },
                "pool": {
                    "hashes_per_second": pool_hash_rate,
                    "miner_count": miner_count_pool_stat["value"],
                    "worker_count": worker_count_pool_stat["value"],
                    "payout_scheme": "PPLNS",
                    "pool_fee": self.config.pool_take,
                    "min_payout": 0,
                    "url": getattr(
                        self.config,
                        "pool_url",
                        f"{self.config.peer_host}:{self.config.stratum_pool_port}",
                    ),
                    "last_five_blocks": [
                        {"timestamp": x["time"], "height": x["index"]}
                        for x in pool_blocks_found_list[:5]
                    ],
                    "blocks_found": total_blocks_found,
                    "fee": self.config.pool_take,
                    "payout_frequency": self.config.payout_frequency,
                    "payouts": payouts,
                    "blocks": pool_blocks_found_list[:100],
                    "pool_perecentage": pool_perecentage,
                    "avg_block_time": avg_time,
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
                "market": {"last_btc": last_btc, "last_usdt": last_usdt},
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
    (r"/pool-info", PoolInfoHandler),
    (r"/", PoolStatsInterfaceHandler),
    (
        r"/yadacoinpoolstatic/(.*)",
        StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "static")},
    ),
]
