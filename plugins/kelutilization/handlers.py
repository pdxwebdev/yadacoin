"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.
"""

import os
import time

import tornado

from yadacoin.http.base import BaseHandler

# ---------------------------------------------------------------------------
# In-process result cache.
# Key: (granularity, days) tuple → (stored_at_epoch, payload)
# Stats (time-ranged) are cached for 10 minutes; the all-time summary for
# 30 minutes (it changes slowly as new blocks arrive).
# ---------------------------------------------------------------------------
_STATS_CACHE: dict = {}
_STATS_TTL = 600  # 10 minutes
_SUMMARY_TTL = 1800  # 30 minutes


def _cache_get(key: tuple, ttl: int):
    entry = _STATS_CACHE.get(key)
    if entry and (time.time() - entry[0]) < ttl:
        return entry[1]
    return None


def _cache_set(key: tuple, data) -> None:
    _STATS_CACHE[key] = (time.time(), data)


def _build_stats_pipeline(granularity: str, days: int) -> tuple:
    """
    Build an optimized aggregation pipeline for KEL time-series stats.

    Optimizations applied
    ---------------------
    1. Pre-unwind $match  – filters entire blocks by transactions.time so
       MongoDB can use a multikey index and avoid unwinding irrelevant blocks.
    2. Minimal pre-unwind $project – strips every field except the three
       transaction sub-fields we actually need, drastically reducing document
       size before the expensive $unwind.
    3. Post-unwind $match – removes the non-qualifying transactions that
       slipped through inside partially-matching blocks.
    4. Lean computed $project – converts the two raw fields to the four
       boolean counters in a single pass.
    5. $group / $sort – unchanged but operating on much smaller documents.

    Returns (pipeline, divisor).
    """
    divisor = 86400 * 7 if granularity == "weekly" else 86400
    pipeline = []

    if days > 0:
        from_ts = int(time.time()) - days * 86400
        # Stage 1 – drop entire blocks that have no qualifying transactions.
        # With an index on transactions.time this is very cheap.
        pipeline.append({"$match": {"transactions.time": {"$gte": from_ts}}})

    # Stage 2 – keep only the three sub-fields we need from each transaction
    # element before unwinding so each unwound document is tiny.
    pipeline.append(
        {
            "$project": {
                "_id": 0,
                "transactions": {
                    "time": 1,
                    "prerotated_key_hash": 1,
                    "prev_public_key_hash": 1,
                },
            }
        }
    )

    # Stage 3 – unwind (now operates on lean documents)
    pipeline.append({"$unwind": "$transactions"})

    if days > 0:
        # Stage 4 – remove transactions from boundary blocks that don't match.
        pipeline.append({"$match": {"transactions.time": {"$gte": from_ts}}})

    # Stage 5 – compute period bucket and boolean counters in one $project.
    pipeline.append(
        {
            "$project": {
                "_id": 0,
                "period": {"$floor": {"$divide": ["$transactions.time", divisor]}},
                # A transaction is a KEL event when prerotated_key_hash is set.
                # (All KEL transactions produced by the node set this field.)
                "is_kel": {
                    "$cond": [{"$gt": ["$transactions.prerotated_key_hash", ""]}, 1, 0]
                },
                "is_inception": {
                    "$cond": [
                        {
                            "$and": [
                                {"$gt": ["$transactions.prerotated_key_hash", ""]},
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
                                {"$gt": ["$transactions.prerotated_key_hash", ""]},
                                {"$gt": ["$transactions.prev_public_key_hash", ""]},
                            ]
                        },
                        1,
                        0,
                    ]
                },
            }
        }
    )

    # Stage 6 – group by period
    pipeline.append(
        {
            "$group": {
                "_id": "$period",
                "kel_count": {"$sum": "$is_kel"},
                "inception_count": {"$sum": "$is_inception"},
                "rotation_count": {"$sum": "$is_rotation"},
                "total_count": {"$sum": 1},
            }
        }
    )

    # Stage 7 – sort ascending
    pipeline.append({"$sort": {"_id": 1}})

    return pipeline, divisor


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

        pipeline, divisor = _build_stats_pipeline(granularity, days)

        result = []
        async for doc in self.config.mongo.async_db.blocks.aggregate(
            pipeline, allowDiskUse=True
        ):
            ts = int(doc["_id"]) * divisor
            total = doc["total_count"] or 1
            result.append(
                {
                    "timestamp": ts,
                    "kel_count": doc["kel_count"],
                    "inception_count": doc["inception_count"],
                    "rotation_count": doc["rotation_count"],
                    "total_count": doc["total_count"],
                    "kel_pct": round(doc["kel_count"] / total * 100, 2),
                }
            )

        # Compute running cumulative in Python (no extra DB round-trip)
        cumulative = 0
        for item in result:
            cumulative += item["kel_count"]
            item["cumulative"] = cumulative

        _cache_set(cache_key, result)
        self.render_as_json(result)


class KelSummaryHandler(BaseHandler):
    """
    Returns overall KEL utilization summary across the entire chain.

    Uses the same optimized pipeline as KelStatsHandler (days=0) and
    derives the summary totals from the per-period results so we only
    scan the chain once, then caches the result.
    """

    async def get(self):
        cache_key = ("summary",)
        cached = _cache_get(cache_key, _SUMMARY_TTL)
        if cached is not None:
            return self.render_as_json(cached)

        # Reuse the stats pipeline for all-time (days=0) with daily granularity.
        # We only need the group totals, so add a final $group over all periods.
        pipeline, _ = _build_stats_pipeline("daily", 0)
        pipeline.append(
            {
                "$group": {
                    "_id": None,
                    "total_txns": {"$sum": "$total_count"},
                    "kel_txns": {"$sum": "$kel_count"},
                    "inception_txns": {"$sum": "$inception_count"},
                    "rotation_txns": {"$sum": "$rotation_count"},
                }
            }
        )

        docs = await self.config.mongo.async_db.blocks.aggregate(
            pipeline, allowDiskUse=True
        ).to_list(1)

        if docs:
            doc = docs[0]
            total = doc["total_txns"] or 1
            kel = doc["kel_txns"]
            result = {
                "total_txns": doc["total_txns"],
                "kel_txns": kel,
                "inception_txns": doc["inception_txns"],
                "rotation_txns": doc["rotation_txns"],
                "kel_pct": round(kel / total * 100, 2),
            }
        else:
            result = {
                "total_txns": 0,
                "kel_txns": 0,
                "inception_txns": 0,
                "rotation_txns": 0,
                "kel_pct": 0.0,
            }

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
