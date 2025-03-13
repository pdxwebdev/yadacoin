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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
        }
        response = requests.get(
            "https://safe.trade/api/v2/peatio/public/markets/tickers", headers=headers
        )

        if response.status_code == 200:
            market_data = {
                "last_btc": float(response.json()["ydabtc"]["ticker"]["last"]),
                "last_usdt": float(response.json()["ydausdt"]["ticker"]["last"]),
            }
        else:
            market_data = {"last_btc": 0, "last_usdt": 0}

        return market_data


class PoolInfoHandler(BaseWebHandler):
    async def get(self):
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
            .to_list(5)
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
                        {"timestamp": x["updated_at"], "height": x["index"]}
                        for x in pool_blocks_found_list[:5]
                    ],
                    "blocks_found": total_blocks_found,
                    "fee": self.config.pool_take,
                    "payout_frequency": self.config.payout_frequency,
                    "blocks": pool_blocks_found_list[:5],
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
                "coin": {
                    "algo": "randomx YDA",
                    "circulating": CHAIN.get_circulating_supply(
                        self.config.LatestBlock.block.index
                    ),
                    "max_supply": 21000000,
                },
            }
        )


class PoolBlocksHandler(BaseWebHandler):
    async def get(self):
        pool_public_key = (
            self.config.pool_public_key
            if hasattr(self.config, "pool_public_key")
            else self.config.public_key
        )

        pool_blocks_found_list = (
            await self.config.mongo.async_db.blocks.find(
                {"public_key": pool_public_key},
                {"_id": 0, "index": 1, "hash": 1, "updated_at": 1, "transactions": 1, "target": 1},  
            )
            .sort([("index", -1)])
            .to_list(300)
        )

        max_target = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF

        result_blocks = []
        for block in pool_blocks_found_list:
            if not block.get("transactions"):
                continue

            coinbase_tx = block["transactions"][-1]
            reward = 0

            for output in coinbase_tx.get("outputs", []):  
                if output["to"] == self.config.address:
                    reward += output["value"]

            difficulty = max_target / int(block["target"], 16) if "target" in block else 0
            txn_count = max(len(block["transactions"]) - 1, 0)

            result_blocks.append({
                "height": block["index"],
                "time": block.get("updated_at", coinbase_tx["time"]),
                "hash": block["hash"],
                "reward": reward,
                "difficulty": round(difficulty, 3),
                "txn_count": txn_count,
            })

        self.render_as_json({"blocks": result_blocks})



class PoolPayoutsHandler(BaseWebHandler):
    async def get(self):
        payouts = (
            await self.config.mongo.async_db.share_payout.find({}, {"_id": 0})
            .sort([("index", -1)])
            .to_list(50)
        )

        result_payouts = []
        for payout in payouts:
            txn = payout.get("txn", {})
            outputs = txn.get("outputs", [])

            tx_hash = txn.get("hash", "N/A")
            tx_time = txn.get("time", 0)
            pool_fee = sum(o["value"] for o in outputs if o["to"] == self.config.address)
            total_amount = sum(o["value"] for o in outputs if o["to"] != self.config.address)
            payees = len([o for o in outputs if o["to"] != self.config.address])

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

            result_payouts.append({
                "time": tx_time,
                "hash": tx_hash,
                "amount": total_amount,
                "fee": pool_fee,
                "payees": payees,
                "status": status,
                "block_height": block_index,
            })

        self.render_as_json({"payouts": result_payouts})


class GetStartHandler(BaseHandler):
    async def get(self):
        pool_info = {
            "pool_url": self.config.peer_host,
            "pool_port": self.config.stratum_pool_port,
            "pool_diff": self.config.pool_diff,
            "algorithm": "rx/yada"
        }
        
        self.render_as_json({"pool": pool_info})


HANDLERS = [
    (r"/market-info", MarketInfoHandler),
    (r"/pool-info", PoolInfoHandler),
    (r"/pool-blocks", PoolBlocksHandler),
    (r"/pool-payouts", PoolPayoutsHandler),
    (r"/get-start", GetStartHandler),
    (r"/", PoolStatsInterfaceHandler),
    (
        r"/yadacoinpoolstatic/(.*)",
        StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "static")},
    ),
]
