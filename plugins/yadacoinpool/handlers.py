import os
import time

import requests
from tornado.web import StaticFileHandler

from yadacoin import version
from yadacoin.core.chain import CHAIN
from yadacoin.http.base import BaseHandler

# Site DB collection used to cache the pool's KEL-aware block summary so we do
# not rebuild expensive aggregates on every request.  Only the count of won
# blocks, the last five, spent coinbase ids, and the signing public_key set
# are stored — the full set of won blocks is never cached.
POOL_KEL_BLOCKS_COLLECTION = "pool_kel_blocks"


def _pool_inception_public_key_hash(config):
    """Stable pool KEL identity: inception txn public_key_hash (P2PKH address).

    Prefer ``config.inception.public_key_hash``; otherwise derive the address
    from ``config.inception.public_key`` the same way mining pool payouts do.
    """
    inception = getattr(config, "inception", None)
    if inception is None:
        return None
    pkh = getattr(inception, "public_key_hash", None) or ""
    if pkh:
        return pkh
    pub = getattr(inception, "public_key", None) or ""
    if not pub:
        return None
    try:
        from bitcoin.wallet import P2PKHBitcoinAddress

        return str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(pub)))
    except Exception:
        return None


async def _build_pool_kel_cache(config, pool_public_key, latest_hash, latest_height):
    """Build pool win summary from inception-tagged coinbases.

    1. Locate every block whose coinbase (no inputs, block.public_key matches
       txn.public_key) carries ``inception_public_key_hash`` equal to this
       node's inception address.
    2. Collect those coinbase transaction ids.
    3. Cross-reference which of those ids appear as inputs on later
       transactions that carry the same ``inception_public_key_hash``
       (same-KEL spends / settlements).

    Returns a cache document with ``total``, ``last_five``, ``spent_coinbase_ids``,
    ``public_keys`` (distinct signing keys from won blocks), and tip metadata.
    """
    inception_pkh = _pool_inception_public_key_hash(config)
    identity = inception_pkh or pool_public_key

    if not inception_pkh:
        config.app_log.warning(
            "pool KEL cache: no config.inception public_key_hash; empty summary"
        )
        return {
            "identity": identity,
            "inception_public_key_hash": None,
            "public_keys": [pool_public_key] if pool_public_key else [],
            "total": 0,
            "last_five": [],
            "spent_coinbase_ids": [],
            "block_hash": latest_hash,
            "block_height": latest_height,
            "cached_at": time.time(),
        }

    # Coinbase = no inputs + same public_key as the block header (pool win).
    won_rows = await config.mongo.async_db.blocks.aggregate(
        [
            {
                "$match": {
                    "transactions": {
                        "$elemMatch": {
                            "inputs.0": {"$exists": False},
                            "inception_public_key_hash": inception_pkh,
                        }
                    }
                }
            },
            {"$unwind": "$transactions"},
            {
                "$match": {
                    "transactions.inputs.0": {"$exists": False},
                    "transactions.inception_public_key_hash": inception_pkh,
                    "$expr": {"$eq": ["$public_key", "$transactions.public_key"]},
                }
            },
            {"$sort": {"index": -1}},
            {
                "$project": {
                    "_id": 0,
                    "index": 1,
                    "hash": 1,
                    "public_key": 1,
                    "updated_at": 1,
                    "time": 1,
                    "target": 1,
                    "coinbase_id": {
                        "$ifNull": [
                            "$transactions.id",
                            "$transactions.transaction_signature",
                        ]
                    },
                    "transactions": ["$transactions"],
                }
            },
        ]
    ).to_list(length=None)

    coinbase_ids = []
    public_keys = []
    for row in won_rows:
        cid = row.get("coinbase_id")
        if cid and cid not in coinbase_ids:
            coinbase_ids.append(cid)
        pk = row.get("public_key")
        if pk and pk not in public_keys:
            public_keys.append(pk)

    spent_coinbase_ids = []
    if coinbase_ids:
        # Same-KEL spends of those coinbases (payouts / settlements / rotations).
        spend_rows = await config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        "transactions": {
                            "$elemMatch": {
                                "inception_public_key_hash": inception_pkh,
                                "inputs.id": {"$in": coinbase_ids},
                            }
                        }
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        "transactions.inception_public_key_hash": inception_pkh,
                        "transactions.inputs.id": {"$in": coinbase_ids},
                    }
                },
                {"$unwind": "$transactions.inputs"},
                {
                    "$match": {
                        "transactions.inputs.id": {"$in": coinbase_ids},
                    }
                },
                {
                    "$group": {
                        "_id": "$transactions.inputs.id",
                    }
                },
            ]
        ).to_list(length=None)
        spent_set = {r["_id"] for r in spend_rows if r.get("_id")}
        # Preserve coinbase order from newest won block first.
        spent_coinbase_ids = [cid for cid in coinbase_ids if cid in spent_set]

    total = len(won_rows)
    last_five = won_rows[:5]
    for row in last_five:
        row["coinbase_spent"] = row.get("coinbase_id") in set(spent_coinbase_ids)

    return {
        "identity": identity,
        "inception_public_key_hash": inception_pkh,
        "public_keys": public_keys or ([pool_public_key] if pool_public_key else []),
        "total": total,
        "last_five": last_five,
        "spent_coinbase_ids": spent_coinbase_ids,
        "block_hash": latest_hash,
        "block_height": latest_height,
        "cached_at": time.time(),
    }


async def _load_pool_kel_cache(config, pool_public_key=None):
    """Return the cached pool KEL doc, rebuilding it when the on-chain tip
    changes (or there is no entry).  The cache is invalidated whenever the
    latest cached entry's stored ``block_hash`` no longer equals
    ``config.LatestBlock.block.hash`` (the chain advanced or reorged)."""
    site_db = config.mongo.async_site_db
    latest_hash = config.LatestBlock.block.hash
    latest_height = config.LatestBlock.block.index
    inception_pkh = _pool_inception_public_key_hash(config)
    identity = inception_pkh or pool_public_key or "unknown"

    cached = await site_db[POOL_KEL_BLOCKS_COLLECTION].find_one(
        {"identity": identity}, sort=[("cached_at", -1)]
    )
    if (
        cached
        and cached.get("block_hash") == latest_hash
        and cached.get("inception_public_key_hash") == inception_pkh
        and "spent_coinbase_ids" in cached
    ):
        return cached

    doc = await _build_pool_kel_cache(
        config, pool_public_key, latest_hash, latest_height
    )

    # Invalidate any stale entries for this identity, then store the fresh result.
    try:
        await site_db[POOL_KEL_BLOCKS_COLLECTION].delete_many({"identity": identity})
    except Exception:
        pass
    try:
        await site_db[POOL_KEL_BLOCKS_COLLECTION].insert_one(doc)
    except Exception as exc:
        config.app_log.warning("pool KEL cache write failed for %s: %s", identity, exc)

    return doc


async def get_pool_kel_blocks(config, pool_public_key=None):
    """Return the pool-info block summary for this node's KEL inception.

    Won blocks are those whose coinbase is tagged with
    ``config.inception.public_key_hash``.  Coinbase ids are then cross-checked
    against same-inception spends on-chain.

    Returns::

        {
            "total": <blocks won>,
            "last_five": [<won block docs with coinbase_id / coinbase_spent>],
            "spent_coinbase_ids": [<coinbase txn ids spent by same-KEL txns>],
            "inception_public_key_hash": <address>,
        }
    """
    doc = await _load_pool_kel_cache(config, pool_public_key)
    return {
        "total": doc.get("total", 0),
        "last_five": doc.get("last_five", []),
        "spent_coinbase_ids": doc.get("spent_coinbase_ids", []),
        "inception_public_key_hash": doc.get("inception_public_key_hash"),
    }


async def get_pool_kel_public_keys(config, pool_public_key=None):
    """Return distinct block signing public keys from won pool blocks.

    Derived from inception-tagged coinbase wins (cached by tip hash).  Falls
    back to ``pool_public_key`` when no wins / no inception are available.
    """
    doc = await _load_pool_kel_cache(config, pool_public_key)
    keys = doc.get("public_keys") or []
    if keys:
        return keys
    if pool_public_key:
        return [pool_public_key]
    return []


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
        pool_blocks_found = await get_pool_kel_blocks(self.config)
        total_blocks_found = pool_blocks_found["total"]
        pool_blocks_found_list = pool_blocks_found["last_five"]
        expected_blocks = 144
        mining_time_interval = 600
        shares_count = await self.config.mongo.async_db.shares.count_documents(
            {
                "time": {"$gte": time.time() - mining_time_interval},
            }
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
        # Full won-block listing via inception-tagged coinbases (same cache as
        # pool-info).  public_keys remain available for callers that need them.
        summary = await get_pool_kel_blocks(self.config)
        inception_pkh = summary.get("inception_public_key_hash")
        spent = set(summary.get("spent_coinbase_ids") or [])

        if not inception_pkh:
            self.render_as_json({"blocks": []})
            return

        pool_blocks_found_list = await self.config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        "transactions": {
                            "$elemMatch": {
                                "inputs.0": {"$exists": False},
                                "inception_public_key_hash": inception_pkh,
                            }
                        }
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        "transactions.inputs.0": {"$exists": False},
                        "transactions.inception_public_key_hash": inception_pkh,
                        "$expr": {"$eq": ["$public_key", "$transactions.public_key"]},
                    }
                },
                {"$sort": {"index": -1}},
                {"$limit": 300},
                {
                    "$project": {
                        "_id": 0,
                        "index": 1,
                        "hash": 1,
                        "updated_at": 1,
                        "target": 1,
                        "transactions": ["$transactions"],
                        "coinbase_id": {
                            "$ifNull": [
                                "$transactions.id",
                                "$transactions.transaction_signature",
                            ]
                        },
                    }
                },
            ]
        ).to_list(300)

        max_target = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        pool_address = getattr(self.config, "address", None)

        result_blocks = []
        for block in pool_blocks_found_list:
            txns = block.get("transactions") or []
            if not txns:
                continue
            coinbase_tx = txns[0]
            reward = 0.0
            prerotated = coinbase_tx.get("prerotated_key_hash") or ""
            for output in coinbase_tx.get("outputs", []):
                to = output.get("to")
                if prerotated and to == prerotated:
                    reward += float(output.get("value") or 0)
                elif pool_address and to == pool_address:
                    reward += float(output.get("value") or 0)

            difficulty = (
                max_target / int(block["target"], 16) if block.get("target") else 0
            )
            coinbase_id = block.get("coinbase_id")
            result_blocks.append(
                {
                    "height": block["index"],
                    "time": block.get("updated_at", coinbase_tx.get("time")),
                    "hash": block["hash"],
                    "reward": reward,
                    "difficulty": round(difficulty, 3),
                    "txn_count": 0,  # listing is coinbase-only unwind
                    "coinbase_id": coinbase_id,
                    "coinbase_spent": coinbase_id in spent,
                }
            )

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
            pool_fee = sum(
                o["value"] for o in outputs if o["to"] == self.config.address
            )
            total_amount = sum(
                o["value"] for o in outputs if o["to"] != self.config.address
            )
            payees = len([o for o in outputs if o["to"] != self.config.address])

            block = await self.config.mongo.async_db.blocks.find_one(
                {"transactions.hash": tx_hash}, {"index": 1}
            )
            in_mempool = (
                await self.config.mongo.async_db.miner_transactions.count_documents(
                    {"hash": tx_hash}
                )
            )
            in_failed = (
                await self.config.mongo.async_db.failed_transactions.count_documents(
                    {"txn.hash": tx_hash}
                )
            )

            if block:
                status = "Confirmed"
                block_index = block["index"]
            elif in_mempool:
                status = "Pending"
                block_index = "N/A"
            elif in_failed:
                # Before reporting failure, check whether the payout inputs are
                # already confirmed-spent by a *different* transaction — the
                # duplicate-payout reorg scenario where P1 was confirmed, a reorg
                # window triggered P2, and P2 later failed because P1 came back.
                # If P1 is on-chain spending the same inputs the payout succeeded.
                input_ids = [i["id"] for i in txn.get("inputs", []) if "id" in i]
                confirmed_spend = None
                if input_ids:
                    confirmed_spend = await self.config.mongo.async_db.blocks.find_one(
                        {
                            "transactions.inputs.id": {"$in": input_ids},
                            "transactions.public_key": txn.get("public_key"),
                        },
                        {"index": 1},
                    )
                if confirmed_spend:
                    status = "Confirmed"
                    block_index = confirmed_spend["index"]
                else:
                    status = "Failed"
                    block_index = "N/A"
            else:
                status = "Unknown"
                block_index = "N/A"

            result_payouts.append(
                {
                    "time": tx_time,
                    "hash": tx_hash,
                    "amount": total_amount,
                    "fee": pool_fee,
                    "payees": payees,
                    "status": status,
                    "block_height": block_index,
                }
            )

        self.render_as_json({"payouts": result_payouts})


class GetStartHandler(BaseHandler):
    async def get(self):
        pool_info = {
            "pool_url": self.config.peer_host,
            "pool_port": self.config.stratum_pool_port,
            "pool_diff": self.config.pool_diff,
            "algorithm": "rx/yada",
        }

        self.render_as_json({"pool": pool_info})


HANDLERS = [
    (r"/market-info", MarketInfoHandler),
    (r"/pool-info", PoolInfoHandler),
    (r"/pool-blocks", PoolBlocksHandler),
    (r"/pool-payouts", PoolPayoutsHandler),
    (r"/get-start", GetStartHandler),
    (r"/pool", PoolStatsInterfaceHandler),
    (
        r"/yadacoinpoolstatic/(.*)",
        StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "static")},
    ),
]
