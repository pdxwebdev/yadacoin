"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.
"""

import os
import time

import tornado

from yadacoin.http.base import BaseHandler

# In-process result cache.
# Key: (kind, granularity, days) → (stored_at_epoch, payload)
_STATS_CACHE: dict = {}
_STATS_TTL = 600
_SUMMARY_TTL = 1800

# Chain activity cannot predate genesis. Times at or above this are milliseconds.
GENESIS_TS = 1483228800
MS_THRESHOLD = 100_000_000_000


def _cache_get(key: tuple, ttl: int):
    entry = _STATS_CACHE.get(key)
    if entry and (time.time() - entry[0]) < ttl:
        return entry[1]
    return None


def _cache_set(key: tuple, data) -> None:
    _STATS_CACHE[key] = (time.time(), data)


def _as_seconds(expr):
    converted = {
        "$convert": {
            "input": expr,
            "to": "double",
            "onError": None,
            "onNull": None,
        }
    }
    return {
        "$cond": [
            {"$gte": [converted, MS_THRESHOLD]},
            {"$floor": {"$divide": [converted, 1000]}},
            converted,
        ]
    }


def _sane_time(expr, now):
    return {
        "$and": [
            {"$ne": [expr, None]},
            {"$gte": [expr, GENESIS_TS]},
            {"$lte": [expr, now + 86400]},
        ]
    }


def _nonempty(expr):
    return {"$gt": [expr, ""]}


def _annotated_txn_pipeline(days: int, now: int) -> list:
    """Unwind block transactions and flag KEL, including miner coinbase entries.

    A transaction is a KEL entry when any key-event field is set. Mining blocks
    carry that on the confirming step and on the coinbase itself. Transaction
    time falls back to block time so a coinbase with a missing or millisecond
    timestamp is still counted in the block's period.
    """
    pipeline = []
    if days > 0:
        from_ts = now - days * 86400
        hi = now + 86400
        pipeline.append(
            {
                "$match": {
                    "$or": [
                        {"time": {"$gte": from_ts, "$lte": hi}},
                        {"transactions.time": {"$gte": from_ts, "$lte": hi}},
                    ]
                }
            }
        )

    pipeline.append(
        {
            "$project": {
                "_id": 0,
                "block_index": {"$ifNull": ["$index", "$_id"]},
                "block_time": _as_seconds("$time"),
                "block_public_key": "$public_key",
                "transactions": {
                    "$map": {
                        "input": {"$ifNull": ["$transactions", []]},
                        "as": "t",
                        "in": {
                            "time": _as_seconds("$$t.time"),
                            "prerotated_key_hash": "$$t.prerotated_key_hash",
                            "twice_prerotated_key_hash": "$$t.twice_prerotated_key_hash",
                            "public_key_hash": "$$t.public_key_hash",
                            "prev_public_key_hash": "$$t.prev_public_key_hash",
                            "inception_public_key_hash": "$$t.inception_public_key_hash",
                            "public_key": "$$t.public_key",
                            "has_inputs": {
                                "$gt": [
                                    {
                                        "$size": {
                                            "$cond": [
                                                {"$isArray": "$$t.inputs"},
                                                "$$t.inputs",
                                                [],
                                            ]
                                        }
                                    },
                                    0,
                                ]
                            },
                            "output_value": {
                                "$sum": {
                                    "$map": {
                                        "input": {
                                            "$cond": [
                                                {"$isArray": "$$t.outputs"},
                                                "$$t.outputs",
                                                [],
                                            ]
                                        },
                                        "as": "o",
                                        "in": {"$ifNull": ["$$o.value", 0]},
                                    }
                                }
                            },
                        },
                    }
                },
            }
        }
    )
    pipeline.append({"$unwind": "$transactions"})
    pipeline.append(
        {
            "$addFields": {
                "effective_time": {
                    "$cond": [
                        _sane_time("$transactions.time", now),
                        "$transactions.time",
                        {
                            "$cond": [
                                _sane_time("$block_time", now),
                                "$block_time",
                                None,
                            ]
                        },
                    ]
                },
                "is_kel": {
                    "$or": [
                        _nonempty("$transactions.prerotated_key_hash"),
                        _nonempty("$transactions.twice_prerotated_key_hash"),
                        _nonempty("$transactions.public_key_hash"),
                        _nonempty("$transactions.prev_public_key_hash"),
                        _nonempty("$transactions.inception_public_key_hash"),
                    ]
                },
                "is_coinbase": {
                    "$and": [
                        {"$eq": ["$transactions.has_inputs", False]},
                        {"$gt": ["$transactions.output_value", 0]},
                        {
                            "$eq": [
                                "$transactions.public_key",
                                "$block_public_key",
                            ]
                        },
                    ]
                },
            }
        }
    )

    time_match = {"effective_time": {"$ne": None}}
    if days > 0:
        time_match = {
            "effective_time": {"$gte": now - days * 86400, "$lte": now + 86400}
        }
    pipeline.append({"$match": time_match})
    pipeline.append(
        {
            "$addFields": {
                "is_kel_n": {"$cond": ["$is_kel", 1, 0]},
                "is_coinbase_kel": {
                    "$cond": [{"$and": ["$is_coinbase", "$is_kel"]}, 1, 0]
                },
                "is_inception": {
                    "$cond": [
                        {
                            "$and": [
                                "$is_kel",
                                {
                                    "$in": [
                                        "$transactions.prev_public_key_hash",
                                        [None, ""],
                                    ]
                                },
                            ]
                        },
                        1,
                        0,
                    ]
                },
                "is_rotation": {
                    "$cond": [
                        {
                            "$and": [
                                "$is_kel",
                                _nonempty("$transactions.prev_public_key_hash"),
                            ]
                        },
                        1,
                        0,
                    ]
                },
            }
        }
    )
    return pipeline


def _build_stats_pipeline(granularity: str, days: int, now: int = None) -> tuple:
    now = int(now if now is not None else time.time())
    divisor = 86400 * 7 if granularity == "weekly" else 86400
    pipeline = _annotated_txn_pipeline(days, now)
    pipeline.append(
        {
            "$addFields": {
                "period": {"$floor": {"$divide": ["$effective_time", divisor]}}
            }
        }
    )
    pipeline.append(
        {
            "$group": {
                "_id": {"period": "$period", "block": "$block_index"},
                "kel_count": {"$sum": "$is_kel_n"},
                "coinbase_kel_count": {"$sum": "$is_coinbase_kel"},
                "inception_count": {"$sum": "$is_inception"},
                "rotation_count": {"$sum": "$is_rotation"},
                "total_count": {"$sum": 1},
                "block_has_kel": {"$max": "$is_kel_n"},
                "block_has_coinbase_kel": {"$max": "$is_coinbase_kel"},
            }
        }
    )
    pipeline.append(
        {
            "$group": {
                "_id": "$_id.period",
                "kel_count": {"$sum": "$kel_count"},
                "coinbase_kel_count": {"$sum": "$coinbase_kel_count"},
                "inception_count": {"$sum": "$inception_count"},
                "rotation_count": {"$sum": "$rotation_count"},
                "total_count": {"$sum": "$total_count"},
                "block_count": {"$sum": 1},
                "kel_block_count": {"$sum": "$block_has_kel"},
                "coinbase_kel_block_count": {"$sum": "$block_has_coinbase_kel"},
            }
        }
    )
    pipeline.append({"$sort": {"_id": 1}})
    return pipeline, divisor


def _build_summary_pipeline(now: int = None) -> list:
    now = int(now if now is not None else time.time())
    pipeline = _annotated_txn_pipeline(0, now)
    pipeline.append(
        {
            "$group": {
                "_id": "$block_index",
                "kel_count": {"$sum": "$is_kel_n"},
                "coinbase_kel_count": {"$sum": "$is_coinbase_kel"},
                "inception_count": {"$sum": "$is_inception"},
                "rotation_count": {"$sum": "$is_rotation"},
                "total_count": {"$sum": 1},
                "block_has_kel": {"$max": "$is_kel_n"},
                "block_has_coinbase_kel": {"$max": "$is_coinbase_kel"},
            }
        }
    )
    pipeline.append(
        {
            "$group": {
                "_id": None,
                "total_txns": {"$sum": "$total_count"},
                "kel_txns": {"$sum": "$kel_count"},
                "coinbase_kel_txns": {"$sum": "$coinbase_kel_count"},
                "inception_txns": {"$sum": "$inception_count"},
                "rotation_txns": {"$sum": "$rotation_count"},
                "total_blocks": {"$sum": 1},
                "kel_blocks": {"$sum": "$block_has_kel"},
                "coinbase_kel_blocks": {"$sum": "$block_has_coinbase_kel"},
            }
        }
    )
    return pipeline


def _pct(part, whole) -> float:
    if not whole:
        return 0.0
    return round(part / whole * 100, 2)


def _empty_summary() -> dict:
    return {
        "total_txns": 0,
        "kel_txns": 0,
        "coinbase_kel_txns": 0,
        "inception_txns": 0,
        "rotation_txns": 0,
        "total_blocks": 0,
        "kel_blocks": 0,
        "coinbase_kel_blocks": 0,
        "kel_pct": 0.0,
        "block_kel_pct": 0.0,
    }


class KelUtilizationAppHandler(BaseHandler):
    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), "templates")

    async def get(self):
        return self.render("index.html")


class KelStatsHandler(BaseHandler):
    """
    Returns time-series KEL utilization data grouped by day or week.

    Query parameters:
        granularity: "daily" (default) or "weekly"
        days:        integer number of recent days to include (0 = all time, default 90)
    """

    async def get(self):
        granularity = self.get_query_argument("granularity", "daily")
        try:
            days = int(self.get_query_argument("days", "90"))
        except ValueError:
            days = 90

        cache_key = ("stats", granularity, days)
        cached = _cache_get(cache_key, _STATS_TTL)
        if cached is not None:
            return self.render_as_json(cached)

        now = int(time.time())
        pipeline, divisor = _build_stats_pipeline(granularity, days, now)

        result = []
        async for doc in self.config.mongo.async_db.blocks.aggregate(
            pipeline, allowDiskUse=True
        ):
            if doc.get("_id") is None:
                continue
            ts = int(doc["_id"]) * divisor
            if ts < GENESIS_TS or ts > now + 2 * 86400:
                continue
            total = doc["total_count"] or 0
            blocks = doc.get("block_count") or 0
            result.append(
                {
                    "timestamp": ts,
                    "kel_count": doc["kel_count"],
                    "coinbase_kel_count": doc.get("coinbase_kel_count") or 0,
                    "inception_count": doc["inception_count"],
                    "rotation_count": doc["rotation_count"],
                    "total_count": doc["total_count"],
                    "block_count": blocks,
                    "kel_block_count": doc.get("kel_block_count") or 0,
                    "coinbase_kel_block_count": doc.get("coinbase_kel_block_count")
                    or 0,
                    "kel_pct": _pct(doc["kel_count"], total),
                    "block_kel_pct": _pct(doc.get("kel_block_count") or 0, blocks),
                }
            )

        cumulative = 0
        for item in result:
            cumulative += item["kel_count"]
            item["cumulative"] = cumulative

        _cache_set(cache_key, result)
        self.render_as_json(result)


class KelSummaryHandler(BaseHandler):
    """Overall KEL utilization, including coinbase key events and block coverage."""

    async def get(self):
        cache_key = ("summary",)
        cached = _cache_get(cache_key, _SUMMARY_TTL)
        if cached is not None:
            return self.render_as_json(cached)

        pipeline = _build_summary_pipeline()
        docs = await self.config.mongo.async_db.blocks.aggregate(
            pipeline, allowDiskUse=True
        ).to_list(1)

        if docs:
            doc = docs[0]
            total = doc["total_txns"] or 0
            blocks = doc.get("total_blocks") or 0
            result = {
                "total_txns": doc["total_txns"],
                "kel_txns": doc["kel_txns"],
                "coinbase_kel_txns": doc.get("coinbase_kel_txns") or 0,
                "inception_txns": doc["inception_txns"],
                "rotation_txns": doc["rotation_txns"],
                "total_blocks": blocks,
                "kel_blocks": doc.get("kel_blocks") or 0,
                "coinbase_kel_blocks": doc.get("coinbase_kel_blocks") or 0,
                "kel_pct": _pct(doc["kel_txns"], total),
                "block_kel_pct": _pct(doc.get("kel_blocks") or 0, blocks),
            }
        else:
            result = _empty_summary()

        _cache_set(cache_key, result)
        self.render_as_json(result)


HANDLERS = [
    (r"/kel-utilization", KelUtilizationAppHandler),
    (r"/kel-utilization/api/stats", KelStatsHandler),
    (r"/kel-utilization/api/summary", KelSummaryHandler),
    (
        r"/kelstatic/(.*)",
        tornado.web.StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "templates")},
    ),
]
