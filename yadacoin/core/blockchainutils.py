"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import json
import math
from logging import getLogger
from time import perf_counter as precise_time
from time import time

# from yadacoin.transactionutils import TU
from bitcoin.wallet import P2PKHBitcoinAddress

from yadacoin.core.blockchain import Blockchain
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config

GLOBAL_BU = None


def BU():
    return GLOBAL_BU


def set_BU(BU):
    global GLOBAL_BU
    GLOBAL_BU = BU


class TooManyUTXOsException(Exception):
    pass


class BlockChainUtils(object):
    # Blockchain Utilities

    collection = None
    database = None

    def __init__(self):
        self.config = Config()
        self.mongo = self.config.mongo
        self.latest_block = None
        self.app_log = getLogger("tornado.application")

    def invalidate_latest_block(self):
        self.latest_block = None

    async def get_blocks_async(self, reverse=False):
        if reverse:
            return self.mongo.async_db.blocks.find({}, {"_id": 0}).sort([("index", -1)])
        else:
            return self.mongo.async_db.blocks.find({}, {"_id": 0}).sort([("index", 1)])

    async def get_latest_block(self) -> dict:
        # cached - WARNING : this is a json doc, NOT a block
        if not self.latest_block is None:
            return self.latest_block
        self.latest_block = await self.mongo.async_db.blocks.find_one(
            {}, {"_id": 0}, sort=[("index", -1)]
        )
        # self.app_log.debug("last block " + str(self.latest_block))
        return self.latest_block

    async def insert_genesis(self):
        # insert genesis if it doesn't exist
        genesis_block = await Blockchain.get_genesis_block()
        await genesis_block.save()
        await self.mongo.async_db.consensus.update_one(
            {
                "block": genesis_block.to_dict(),
                "peer": "me",
                "id": genesis_block.signature,
                "index": 0,
            },
            {
                "$set": {
                    "block": genesis_block.to_dict(),
                    "peer": "me",
                    "id": genesis_block.signature,
                    "index": 0,
                }
            },
            upsert=True,
        )
        await self.config.LatestBlock.block_checker()

    def set_latest_block(self, block: dict):
        self.latest_block = block

    async def get_latest_block_async(self, use_cache=True) -> dict:
        # cached, async version
        if self.latest_block is not None and use_cache:
            return self.latest_block
        self.latest_block = await self.mongo.async_db.blocks.find_one(
            {}, {"_id": 0}, sort=[("index", -1)]
        )
        return self.latest_block

    async def get_block_by_index(self, index):
        return await self.mongo.async_db.blocks.find_one({"index": index}, {"_id": 0})

    async def get_unspent_txns(self, unspent_txns_query):
        # Return the cursor directly without awaiting it
        return self.config.mongo.async_db.blocks.aggregate(
            unspent_txns_query, allowDiskUse=True, hint="__to"
        )

    async def _async_empty_set(self):
        return set()

    async def _aggregate_blocks(self, pipeline, hint=None, length=1):
        """Run a blocks aggregation, falling back without hint if the index is missing."""
        kwargs = {"allowDiskUse": True}
        if hint:
            try:
                return await self.mongo.async_db.blocks.aggregate(
                    pipeline, hint=hint, **kwargs
                ).to_list(length=length)
            except Exception as e:
                self.config.app_log.warning(
                    "blocks aggregate hint=%s failed (%s); retrying without hint",
                    hint,
                    e,
                )
        return await self.mongo.async_db.blocks.aggregate(pipeline, **kwargs).to_list(
            length=length
        )

    async def _iter_blocks_aggregate(self, pipeline, hint=None):
        """Yield aggregation docs; fall back without hint if the index is missing."""
        kwargs = {"allowDiskUse": True}
        cursor = None
        if hint:
            try:
                cursor = self.mongo.async_db.blocks.aggregate(
                    pipeline, hint=hint, **kwargs
                )
                # Probe first batch by starting iteration; on failure recreate without hint.
                async for doc in cursor:
                    yield doc
                return
            except Exception as e:
                self.config.app_log.warning(
                    "blocks aggregate hint=%s failed (%s); retrying without hint",
                    hint,
                    e,
                )
        cursor = self.mongo.async_db.blocks.aggregate(pipeline, **kwargs)
        async for doc in cursor:
            yield doc

    async def get_total_spent_balance(self, address, public_key=None, from_index=None):
        if public_key is None:
            public_key = await self.get_reverse_public_key(address)
        if not public_key:
            return 0.0

        match = {
            "transactions.public_key": public_key,
            "transactions.inputs.0": {"$exists": True},
        }
        if from_index is not None:
            match["index"] = {"$gt": from_index}

        # Sum external outputs + fee + masternode_fee per spend txn.
        pipeline = [
            {"$match": match},
            {
                "$project": {
                    "transactions": {
                        "$filter": {
                            "input": "$transactions",
                            "as": "txn",
                            "cond": {
                                "$and": [
                                    {"$eq": ["$$txn.public_key", public_key]},
                                    {
                                        "$gt": [
                                            {
                                                "$size": {
                                                    "$ifNull": ["$$txn.inputs", []]
                                                }
                                            },
                                            0,
                                        ]
                                    },
                                ]
                            },
                        }
                    }
                }
            },
            {"$unwind": "$transactions"},
            {
                "$project": {
                    "spent": {
                        "$add": [
                            {
                                "$sum": {
                                    "$map": {
                                        "input": {
                                            "$filter": {
                                                "input": "$transactions.outputs",
                                                "as": "out",
                                                "cond": {"$ne": ["$$out.to", address]},
                                            }
                                        },
                                        "as": "out",
                                        "in": "$$out.value",
                                    }
                                }
                            },
                            {"$ifNull": ["$transactions.fee", 0]},
                            {"$ifNull": ["$transactions.masternode_fee", 0]},
                        ]
                    }
                }
            },
            {"$group": {"_id": None, "totalSpent": {"$sum": "$spent"}}},
        ]

        hint = "__txn_public_key" if from_index is None else None
        result = await self._aggregate_blocks(pipeline, hint=hint)
        return result[0]["totalSpent"] if result else 0.0

    async def get_received_from_others_balance(
        self, address, public_key=None, from_index=None
    ):
        if public_key is None:
            public_key = await self.get_reverse_public_key(address)

        # Non-coinbase payments from others (has inputs).
        if public_key:
            txn_cond = {
                "$and": [
                    {"$ne": ["$$txn.public_key", public_key]},
                    {
                        "$gt": [
                            {"$size": {"$ifNull": ["$$txn.inputs", []]}},
                            0,
                        ]
                    },
                    {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$$txn.outputs",
                                        "as": "out",
                                        "cond": {"$eq": ["$$out.to", address]},
                                    }
                                }
                            },
                            0,
                        ]
                    },
                ]
            }
        else:
            txn_cond = {
                "$and": [
                    {
                        "$gt": [
                            {"$size": {"$ifNull": ["$$txn.inputs", []]}},
                            0,
                        ]
                    },
                    {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$$txn.outputs",
                                        "as": "out",
                                        "cond": {"$eq": ["$$out.to", address]},
                                    }
                                }
                            },
                            0,
                        ]
                    },
                ]
            }

        match = {"transactions.outputs.to": address}
        if from_index is not None:
            match["index"] = {"$gt": from_index}

        pipeline = [
            {"$match": match},
            {
                "$project": {
                    "transactions": {
                        "$filter": {
                            "input": "$transactions",
                            "as": "txn",
                            "cond": txn_cond,
                        }
                    }
                }
            },
            {"$unwind": "$transactions"},
            {
                "$project": {
                    "received": {
                        "$sum": {
                            "$map": {
                                "input": {
                                    "$filter": {
                                        "input": "$transactions.outputs",
                                        "as": "out",
                                        "cond": {"$eq": ["$$out.to", address]},
                                    }
                                },
                                "as": "out",
                                "in": "$$out.value",
                            }
                        }
                    }
                }
            },
            {"$group": {"_id": None, "totalReceived": {"$sum": "$received"}}},
        ]

        hint = "__to" if from_index is None else None
        result = await self._aggregate_blocks(pipeline, hint=hint)
        return result[0]["totalReceived"] if result else 0.0

    async def get_received_solo_mining_balance(
        self, address, public_key=None, from_index=None
    ):
        """Coinbase outputs paid to address on blocks mined by public_key."""
        if public_key is None:
            public_key = await self.get_reverse_public_key(address)
        if not public_key:
            return 0.0

        match = {
            "public_key": public_key,
            "transactions.outputs.to": address,
        }
        if from_index is not None:
            match["index"] = {"$gt": from_index}

        pipeline = [
            {"$match": match},
            {
                "$project": {
                    "transactions": {
                        "$filter": {
                            "input": "$transactions",
                            "as": "txn",
                            "cond": {
                                "$and": [
                                    {
                                        "$eq": [
                                            {
                                                "$size": {
                                                    "$ifNull": ["$$txn.inputs", []]
                                                }
                                            },
                                            0,
                                        ]
                                    },
                                    {
                                        "$gt": [
                                            {
                                                "$size": {
                                                    "$filter": {
                                                        "input": "$$txn.outputs",
                                                        "as": "out",
                                                        "cond": {
                                                            "$eq": ["$$out.to", address]
                                                        },
                                                    }
                                                }
                                            },
                                            0,
                                        ]
                                    },
                                ]
                            },
                        }
                    }
                }
            },
            {"$unwind": "$transactions"},
            {
                "$project": {
                    "received": {
                        "$sum": {
                            "$map": {
                                "input": {
                                    "$filter": {
                                        "input": "$transactions.outputs",
                                        "as": "out",
                                        "cond": {"$eq": ["$$out.to", address]},
                                    }
                                },
                                "as": "out",
                                "in": "$$out.value",
                            }
                        }
                    }
                }
            },
            {"$group": {"_id": None, "totalReceived": {"$sum": "$received"}}},
        ]

        hint = "__public_key_outputs_to" if from_index is None else None
        result = await self._aggregate_blocks(pipeline, hint=hint)
        return result[0]["totalReceived"] if result else 0.0

    async def get_masternode_coinbase_balance(
        self, address, public_key=None, from_index=None
    ):
        """Coinbase outputs paid to address on blocks NOT mined by public_key."""
        if public_key is None:
            public_key = await self.get_reverse_public_key(address)

        if public_key:
            txn_cond = {
                "$and": [
                    {"$ne": ["$$txn.public_key", public_key]},
                    {
                        "$eq": [
                            {"$size": {"$ifNull": ["$$txn.inputs", []]}},
                            0,
                        ]
                    },
                    {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$$txn.outputs",
                                        "as": "out",
                                        "cond": {"$eq": ["$$out.to", address]},
                                    }
                                }
                            },
                            0,
                        ]
                    },
                ]
            }
        else:
            txn_cond = {
                "$and": [
                    {
                        "$eq": [
                            {"$size": {"$ifNull": ["$$txn.inputs", []]}},
                            0,
                        ]
                    },
                    {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$$txn.outputs",
                                        "as": "out",
                                        "cond": {"$eq": ["$$out.to", address]},
                                    }
                                }
                            },
                            0,
                        ]
                    },
                ]
            }

        match = {
            "transactions.outputs.to": address,
            "transactions.inputs": {"$eq": []},
        }
        if from_index is not None:
            match["index"] = {"$gt": from_index}

        pipeline = [
            {"$match": match},
            {
                "$project": {
                    "transactions": {
                        "$filter": {
                            "input": "$transactions",
                            "as": "txn",
                            "cond": txn_cond,
                        }
                    }
                }
            },
            {"$unwind": "$transactions"},
            {
                "$project": {
                    "received": {
                        "$sum": {
                            "$map": {
                                "input": {
                                    "$filter": {
                                        "input": "$transactions.outputs",
                                        "as": "out",
                                        "cond": {"$eq": ["$$out.to", address]},
                                    }
                                },
                                "as": "out",
                                "in": "$$out.value",
                            }
                        }
                    }
                }
            },
            {"$group": {"_id": None, "totalReceived": {"$sum": "$received"}}},
        ]

        hint = "__to" if from_index is None else None
        result = await self._aggregate_blocks(pipeline, hint=hint)
        return result[0]["totalReceived"] if result else 0.0

    # Backward-compatible aliases used by older callers/tests
    async def get_coinbase_total_output_balance(self, address):
        return await self.get_received_solo_mining_balance(address)

    async def get_total_received_balance(self, address):
        return await self.get_received_from_others_balance(address)

    async def get_spent_balance(self, address, from_index=None):
        """Public spent balance.

        ``from_index`` is an exclusive upper bound (index < from_index), matching
        the historical API. Incremental cache updates use
        ``get_total_spent_balance(..., from_index=)`` with a lower bound instead.
        """
        if from_index is None:
            return await self.get_total_spent_balance(address)

        public_key = await self.get_reverse_public_key(address)
        if not public_key:
            return 0.0

        match = {
            "transactions.public_key": public_key,
            "transactions.inputs.0": {"$exists": True},
            "index": {"$lt": from_index},
        }
        pipeline = [
            {"$match": match},
            {
                "$project": {
                    "transactions": {
                        "$filter": {
                            "input": "$transactions",
                            "as": "txn",
                            "cond": {
                                "$and": [
                                    {"$eq": ["$$txn.public_key", public_key]},
                                    {
                                        "$gt": [
                                            {
                                                "$size": {
                                                    "$ifNull": ["$$txn.inputs", []]
                                                }
                                            },
                                            0,
                                        ]
                                    },
                                ]
                            },
                        }
                    }
                }
            },
            {"$unwind": "$transactions"},
            {
                "$project": {
                    "spent": {
                        "$add": [
                            {
                                "$sum": {
                                    "$map": {
                                        "input": {
                                            "$filter": {
                                                "input": "$transactions.outputs",
                                                "as": "out",
                                                "cond": {"$ne": ["$$out.to", address]},
                                            }
                                        },
                                        "as": "out",
                                        "in": "$$out.value",
                                    }
                                }
                            },
                            {"$ifNull": ["$transactions.fee", 0]},
                            {"$ifNull": ["$transactions.masternode_fee", 0]},
                        ]
                    }
                }
            },
            {"$group": {"_id": None, "totalSpent": {"$sum": "$spent"}}},
        ]
        result = await self._aggregate_blocks(pipeline, hint=None)
        return result[0]["totalSpent"] if result else 0.0

    async def _compute_balance_components(
        self, address, public_key=None, from_index=None
    ):
        if public_key is None:
            public_key = await self.get_reverse_public_key(address)

        (
            total_spent,
            received_from_others,
            received_solo_mining,
            received_masternode,
        ) = await asyncio.gather(
            self.get_total_spent_balance(address, public_key, from_index=from_index),
            self.get_received_from_others_balance(
                address, public_key, from_index=from_index
            ),
            self.get_received_solo_mining_balance(
                address, public_key, from_index=from_index
            ),
            self.get_masternode_coinbase_balance(
                address, public_key, from_index=from_index
            ),
        )
        return {
            "public_key": public_key,
            "total_spent": float(total_spent or 0.0),
            "received_from_others": float(received_from_others or 0.0),
            "received_solo_mining": float(
                (received_solo_mining or 0.0) + (received_masternode or 0.0)
            ),
        }

    async def _get_wallet_balance_cache(self, address):
        return await self.mongo.async_db.wallet_balance_cache.find_one(
            {"address": address}
        )

    async def _save_wallet_balance_cache(
        self,
        address,
        public_key,
        total_spent,
        received_from_others,
        received_solo_mining,
        latest_block,
    ):
        balance = (received_solo_mining + received_from_others) - total_spent
        doc = {
            "address": address,
            "public_key": public_key,
            "total_spent": float(total_spent),
            "received_from_others": float(received_from_others),
            "received_solo_mining": float(received_solo_mining),
            "balance": float(balance),
            "last_block_hash": latest_block.get("hash") if latest_block else None,
            "last_block_index": latest_block.get("index") if latest_block else None,
            "cache_time": time(),
        }
        await self.mongo.async_db.wallet_balance_cache.update_one(
            {"address": address},
            {"$set": doc},
            upsert=True,
        )
        return balance

    async def _chain_marker_is_valid(self, cache_doc, latest_block=None):
        """Validate a cache marker against the live chain to guard against reorgs.

        Requires:
        1. Marker hash still exists in blocks
        2. That block's index matches the cached marker index
        3. Tip is at or past the marker (chain was not shortened past it)
        4. Block currently stored at the marker index still has the marker hash
        """
        if not cache_doc:
            return False
        marker_hash = cache_doc.get("last_block_hash")
        marker_index = cache_doc.get("last_block_index")
        if not marker_hash or marker_index is None:
            return False

        # 1 + 2: hash must still exist and point at the same height.
        by_hash = await self.mongo.async_db.blocks.find_one(
            {"hash": marker_hash}, {"hash": 1, "index": 1, "_id": 0}
        )
        if not by_hash:
            return False
        if by_hash.get("index") != marker_index:
            return False

        # 3: tip must not have rewound past the marker.
        if latest_block is None:
            latest_block = await self.get_latest_block_async()
        if not latest_block:
            return False
        tip_index = latest_block.get("index")
        if tip_index is None or tip_index < marker_index:
            return False

        # 4: block at marker height must still be the same hash (canonical tip path).
        by_index = await self.mongo.async_db.blocks.find_one(
            {"index": marker_index}, {"hash": 1, "_id": 0}
        )
        if not by_index or by_index.get("hash") != marker_hash:
            return False

        return True

    async def _wallet_balance_cache_is_valid(self, cache_doc, latest_block=None):
        return await self._chain_marker_is_valid(cache_doc, latest_block=latest_block)

    async def _invalidate_wallet_balance_cache(self, address, reason=None):
        await self.mongo.async_db.wallet_balance_cache.delete_one({"address": address})
        if reason:
            self.config.app_log.info(
                "Invalidated wallet_balance_cache for %s: %s", address, reason
            )

    async def _get_wallet_unspent_cache(self, address):
        return await self.mongo.async_db.wallet_unspent_cache.find_one(
            {"address": address}
        )

    async def get_cached_max_transferable_value(self, address):
        """Return max_transferable_value from wallet_unspent_cache when safe.

        O(1) mongo reads only — never runs UTXO selection.

        Uses the cache whenever the marker block is still on the canonical
        chain (reorg-safe). Does NOT require the tip hash to match, because
        tips advance continuously and max_transferable only drifts when new
        receives/spends hit this address. Exact tip match is reserved for the
        full UTXO HIT path that returns spendable inputs.
        """
        latest_block = await self.get_latest_block_async()
        cache_doc = await self._get_wallet_unspent_cache(address)
        if not cache_doc:
            return 0.0
        if not await self._wallet_unspent_cache_is_valid(
            cache_doc, latest_block=latest_block
        ):
            return 0.0

        if cache_doc.get("max_transferable_value") is not None:
            return float(cache_doc["max_transferable_value"])

        # Legacy cache docs: sum stored UTXOs.
        total = 0.0
        for utxo in cache_doc.get("unspent_utxos") or []:
            for out in utxo.get("outputs") or []:
                total += float(out.get("value") or 0.0)
        return total

    async def _save_wallet_unspent_cache(
        self,
        address,
        public_key,
        unspent_utxos,
        latest_block,
        selection_complete=False,
        max_utxos=None,
    ):
        balance = 0.0
        compact = []
        for utxo in unspent_utxos:
            outputs = utxo.get("outputs") or []
            value = sum(float(o.get("value") or 0.0) for o in outputs)
            balance += value
            compact.append(
                {
                    "id": utxo.get("id"),
                    "time": utxo.get("time"),
                    "outputs": outputs,
                }
            )
        if max_utxos is None:
            max_utxos = CHAIN.MAX_INPUTS
        # Full input set or explicit complete flag means later amount_needed
        # values cannot unlock more coins without exceeding MAX_INPUTS.
        complete = bool(selection_complete) or len(compact) >= max_utxos
        doc = {
            "address": address,
            "public_key": public_key,
            "unspent_utxos": compact,
            "balance": float(balance),
            "max_transferable_value": float(self.floor_to_two_decimal_places(balance)),
            "selection_complete": complete,
            "last_block_hash": latest_block.get("hash") if latest_block else None,
            "last_block_index": latest_block.get("index") if latest_block else None,
            "cache_time": time(),
        }
        try:
            await self.mongo.async_db.wallet_unspent_cache.update_one(
                {"address": address},
                {"$set": doc},
                upsert=True,
            )
        except Exception as e:
            # Large wallets can exceed the 16MB BSON doc limit; skip caching.
            self.config.app_log.warning(
                "Failed to save wallet_unspent_cache for %s: %s", address, e
            )
        return float(balance)

    async def _wallet_unspent_cache_is_valid(self, cache_doc, latest_block=None):
        return await self._chain_marker_is_valid(cache_doc, latest_block=latest_block)

    async def _invalidate_wallet_unspent_cache(self, address, reason=None):
        await self.mongo.async_db.wallet_unspent_cache.delete_one({"address": address})
        if reason:
            self.config.app_log.info(
                "Invalidated wallet_unspent_cache for %s: %s", address, reason
            )

    async def get_final_balance(self, address):
        start = precise_time()
        public_key = await self.get_reverse_public_key(address)
        latest_block = await self.get_latest_block_async()

        cache_doc = await self._get_wallet_balance_cache(address)
        cache_valid = await self._wallet_balance_cache_is_valid(
            cache_doc, latest_block=latest_block
        )
        if cache_doc and not cache_valid:
            await self._invalidate_wallet_balance_cache(
                address, reason="reorg or missing marker block hash"
            )
            cache_doc = None

        # Fast path: tip unchanged since last cache write.
        if (
            cache_valid
            and latest_block
            and cache_doc.get("last_block_hash") == latest_block.get("hash")
        ):
            elapsed = precise_time() - start
            self.config.app_log.info(
                "Balance cache HIT for %s: %.8f (%.2fs)",
                address,
                cache_doc.get("balance", 0.0),
                elapsed,
            )
            return float(cache_doc.get("balance", 0.0))

        # Incremental path: apply only blocks after the cached marker.
        if cache_valid and latest_block:
            from_index = cache_doc.get("last_block_index")
            delta = await self._compute_balance_components(
                address, public_key=public_key, from_index=from_index
            )
            total_spent = (
                float(cache_doc.get("total_spent", 0.0)) + delta["total_spent"]
            )
            received_from_others = (
                float(cache_doc.get("received_from_others", 0.0))
                + delta["received_from_others"]
            )
            received_solo_mining = (
                float(cache_doc.get("received_solo_mining", 0.0))
                + delta["received_solo_mining"]
            )
            final_balance = await self._save_wallet_balance_cache(
                address,
                public_key or cache_doc.get("public_key"),
                total_spent,
                received_from_others,
                received_solo_mining,
                latest_block,
            )
            elapsed = precise_time() - start
            self.config.app_log.info(
                "Balance cache INCREMENTAL for %s: delta_spent=%.8f "
                "delta_from_others=%.8f delta_solo=%.8f final=%.8f "
                "(from_index=%s, %.2fs)",
                address,
                delta["total_spent"],
                delta["received_from_others"],
                delta["received_solo_mining"],
                final_balance,
                from_index,
                elapsed,
            )
            return final_balance

        # Full recompute (cold cache or reorg invalidated marker).
        components = await self._compute_balance_components(
            address, public_key=public_key
        )
        final_balance = await self._save_wallet_balance_cache(
            address,
            components["public_key"],
            components["total_spent"],
            components["received_from_others"],
            components["received_solo_mining"],
            latest_block,
        )
        elapsed = precise_time() - start
        self.config.app_log.info(
            "Balance cache MISS/FULL for %s: spent=%.8f from_others=%.8f "
            "solo_mining=%.8f final=%.8f (%.2fs)",
            address,
            components["total_spent"],
            components["received_from_others"],
            components["received_solo_mining"],
            final_balance,
            elapsed,
        )
        return final_balance

    async def get_wallet_balance(self, address, amount_needed=None):
        total_balance = await self.get_final_balance(address)
        return total_balance

    async def get_public_key_address_pairs(self, address):
        pipeline = [
            {"$match": {"transactions.outputs.to": address}},
            {"$unwind": "$transactions"},
            {"$unwind": "$transactions.outputs"},
            {"$match": {"transactions.outputs.to": address}},
            {
                "$group": {
                    "_id": None,
                    "unique_public_keys": {"$addToSet": "$transactions.public_key"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "unique_public_keys": 1,
                }
            },
        ]
        # Return the cursor directly without awaiting it
        public_key_address_pair_list = self.mongo.async_db.blocks.aggregate(
            pipeline, allowDiskUse=True, hint="__to"
        )
        return await public_key_address_pair_list.to_list(length=None)

    async def get_reverse_public_key(self, address):
        reversed_public_key = await self.mongo.async_db.reversed_public_keys.find_one(
            {"address": address}
        )
        if reversed_public_key:
            return reversed_public_key["public_key"]
        public_key_address_pairs = await self.get_public_key_address_pairs(address)

        if not public_key_address_pairs:
            return

        for public_key in public_key_address_pairs[0]["unique_public_keys"]:
            xaddress = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
            if xaddress == address:
                await self.mongo.async_db.reversed_public_keys.update_one(
                    {"address": address, "public_key": public_key},
                    {"$set": {"address": address, "public_key": public_key}},
                    upsert=True,
                )
                return public_key

        return None

    def get_wallet_unspent_transactions_for_dusting(self, address, limit=None):
        query = [
            {
                "$match": {
                    "transactions.outputs.to": address,
                },
            },
            {"$unwind": "$transactions"},
            {"$unwind": "$transactions.outputs"},
            {
                "$match": {
                    "transactions.outputs.to": address,
                    "transactions.outputs.value": {"$gt": 0},
                },
            },
            {
                "$group": {
                    "_id": {
                        "transactionId": "$transactions.id",
                        "to": "$transactions.outputs.to",
                    },
                    "totalValue": {"$sum": "$transactions.outputs.value"},
                    "time": {"$first": "$transactions.time"},
                }
            },
            {
                "$group": {
                    "_id": "$_id.transactionId",
                    "id": {"$first": "$_id.transactionId"},
                    "outputs": {"$push": {"to": "$_id.to", "value": "$totalValue"}},
                    "time": {"$first": "$time"},
                }
            },
            {"$sort": {"outputs.time": 1}},
        ]
        return self.get_wallet_unspent_transactions(
            unspent_txns_query=query, address=address, limit=limit
        )

    def get_wallet_unspent_transactions_for_spending(
        self, address, amount_needed=None, inc_mempool=False, limit=None
    ):
        if limit is None or limit > CHAIN.MAX_INPUTS:
            limit = CHAIN.MAX_INPUTS
        query = [
            {
                "$match": {
                    "transactions.outputs.to": address,
                    "transactions.outputs.value": {
                        "$gte": self.config.balance_min_utxo
                    },
                },
            },
            {"$unwind": "$transactions"},
            {"$unwind": "$transactions.outputs"},
            {
                "$match": {
                    "transactions.outputs.to": address,
                    "transactions.outputs.value": {
                        "$gte": self.config.balance_min_utxo
                    },
                },
            },
            {
                "$group": {
                    "_id": {
                        "transactionId": "$transactions.id",
                        "to": "$transactions.outputs.to",
                    },
                    "totalValue": {"$sum": "$transactions.outputs.value"},
                }
            },
            {
                "$group": {
                    "_id": "$_id.transactionId",
                    "id": {"$first": "$_id.transactionId"},
                    "outputs": {"$push": {"to": "$_id.to", "value": "$totalValue"}},
                }
            },
            {"$sort": {"outputs.value": -1}},
        ]
        return self.get_wallet_unspent_transactions(
            unspent_txns_query=query,
            address=address,
            inc_mempool=inc_mempool,
            amount_needed=amount_needed,
            limit=limit,
        )

    async def get_wallet_unspent_transactions(
        self,
        unspent_txns_query,
        address,
        inc_mempool=False,
        amount_needed=None,
        limit=None,
    ):
        public_key = await self.get_reverse_public_key(address)

        # Return the cursor directly without awaiting it
        utxos = await self.get_unspent_txns(unspent_txns_query)
        total = 0
        count = 0
        async for utxo in utxos:
            if not await self.config.BU.is_input_spent(
                utxo["id"], public_key, inc_mempool=inc_mempool
            ):
                count += 1
                if limit and count > limit:
                    raise TooManyUTXOsException(
                        f"The UTXO limit of {limit} has been exceeded"
                    )
                total += sum(
                    [x["value"] for x in utxo["outputs"] if x["to"] == address]
                )
                yield utxo
                if amount_needed is not None and total >= amount_needed:
                    break  # pragma: no cover
                if limit and count >= limit and amount_needed is not None:
                    break

        if not inc_mempool:
            return  # pragma: no cover  (async-generator return; not instrumentable in Py3.9)
        mempool_txns = self.config.mongo.async_db.miner_transactions.find(
            {"public_key": public_key}
        )
        pending_used_inputs = {}
        unspent_mempool_txns = {}
        async for mempool_txn in mempool_txns:
            if mempool_txn["id"] in pending_used_inputs:
                continue

            xaddress = str(
                P2PKHBitcoinAddress.from_pubkey(
                    bytes.fromhex(mempool_txn["public_key"])
                )
            )
            if address == xaddress and mempool_txn.get("inputs"):
                for x in mempool_txn.get("inputs"):
                    pending_used_inputs[x["id"]] = mempool_txn
                    if x["id"] in unspent_mempool_txns:
                        del unspent_mempool_txns[x["id"]]

            unspent_mempool_txns[mempool_txn["id"]] = {
                "_id": mempool_txn["id"],
                "id": mempool_txn["id"],
                "outputs": [x for x in mempool_txn["outputs"] if x["to"] == address],
            }
        for x in list(unspent_mempool_txns.values()):
            yield x

    async def get_wallet_masternode_fees_paid_transactions(
        self, public_key, from_block
    ):
        query = [
            {
                "$match": {
                    "index": {"$gte": from_block},
                    "transactions.public_key": public_key,
                },
            },
            {"$unwind": "$transactions"},
            {
                "$match": {
                    "transactions.public_key": public_key,
                    "transactions.masternode_fee": {"$gt": 0},
                },
            },
        ]
        # Return the cursor directly without awaiting it

        txns = self.config.mongo.async_db.blocks.aggregate(query)
        async for txn in txns:
            yield txn

    async def get_wallet_masternode_fees_delegated_transactions(
        self, address, from_block
    ):
        query = [
            {
                "$match": {
                    "index": {"$gte": from_block},
                    "transactions.relationship": address,
                },
            },
            {"$unwind": "$transactions"},
            {
                "$match": {
                    "transactions.relationship": address,
                    "transactions.masternode_fee": {"$gt": 0},
                },
            },
        ]
        # Return the cursor directly without awaiting it

        txns = self.config.mongo.async_db.blocks.aggregate(query)
        async for txn in txns:
            yield txn

    async def get_masternode_fees_paid_sum(self, public_key, from_block):
        sum = 0
        async for txn in self.get_wallet_masternode_fees_paid_transactions(
            public_key, from_block
        ):
            sum += txn["transactions"]["masternode_fee"]

        if sum == 0:
            async for txn in self.get_wallet_masternode_fees_delegated_transactions(
                str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key))),
                from_block,
            ):
                sum += txn["transactions"]["masternode_fee"]

        return sum

    async def get_transactions(
        self, wif, query, queryType, raw=False, both=True, skip=None
    ):
        if not skip:
            skip = []
        # from block import Block
        # from transaction import Transaction
        from yadacoin import Crypt

        get_transactions_cache = (
            await self.mongo.async_db.get_transactions_cache.find_one(
                {
                    "public_key": self.config.public_key,
                    "raw": raw,
                    "both": both,
                    "skip": skip,
                    "queryType": queryType,
                },
                sort=[("height", -1)],
            )
        )
        latest_block = await self.config.LatestBlock.block.copy()
        if get_transactions_cache:
            block_height = get_transactions_cache["height"]
        else:
            block_height = 0

        cipher = None
        transactions = []
        async for block in self.mongo.async_db.blocks.find(
            {
                "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}},
                "index": {"$gt": block_height},
            }
        ):
            for transaction in block.get("transactions"):
                try:
                    if transaction.get("id") in skip:
                        continue
                    if "relationship" not in transaction:
                        continue
                    if not transaction["relationship"]:
                        continue
                    if not raw:
                        if not cipher:
                            cipher = Crypt(wif)
                        decrypted = cipher.decrypt(transaction["relationship"])
                        relationship = json.loads(decrypted.decode("latin1"))
                        transaction["relationship"] = relationship
                    transaction["height"] = block["index"]
                    await self.mongo.async_db.get_transactions_cache.update_many(
                        {
                            "public_key": self.config.public_key,
                            "raw": raw,
                            "both": both,
                            "skip": skip,
                            "height": latest_block.index,
                            "block_hash": latest_block.hash,
                            "queryType": queryType,
                            "id": transaction["id"],
                        },
                        {
                            "public_key": self.config.public_key,
                            "raw": raw,
                            "both": both,
                            "skip": skip,
                            "height": latest_block.index,
                            "block_hash": latest_block.hash,
                            "txn": transaction,
                            "queryType": queryType,
                            "id": transaction["id"],
                            "cache_time": time(),
                        },
                        upsert=True,
                    )
                except:
                    self.app_log.debug(
                        "failed decrypt. block: {}".format(block["index"])
                    )
                    if both:
                        transaction["height"] = block["index"]
                        await self.mongo.async_db.get_transactions_cache.update_many(
                            {
                                "public_key": self.config.public_key,
                                "raw": raw,
                                "both": both,
                                "skip": skip,
                                "height": latest_block.index,
                                "block_hash": latest_block.hash,
                                "queryType": queryType,
                            },
                            {
                                "public_key": self.config.public_key,
                                "raw": raw,
                                "both": both,
                                "skip": skip,
                                "height": latest_block.index,
                                "block_hash": latest_block.hash,
                                "txn": transaction,
                                "queryType": queryType,
                                "cache_time": time(),
                            },
                            upsert=True,
                        )
                    continue

        if not transactions:
            await self.mongo.async_db.get_transactions_cache.insert_one(
                {
                    "public_key": self.config.public_key,
                    "raw": raw,
                    "both": both,
                    "skip": skip,
                    "queryType": queryType,
                    "height": latest_block.index,
                    "block_hash": latest_block.hash,
                    "cache_time": time(),
                }
            )

        search_query = {
            "public_key": self.config.public_key,
            "raw": raw,
            "both": both,
            "skip": skip,
            "queryType": queryType,
            "txn": {"$exists": True},
        }
        search_query.update(query)
        transactions = self.mongo.async_db.get_transactions_cache.find(
            search_query
        ).sort([("height", -1)])

        async for transaction in transactions:
            yield transaction["txn"]

    async def get_transaction_by_id(
        self,
        id,
        instance=False,
        give_block=False,
        include_fastgraph=False,
        inc_mempool=False,
    ):
        from yadacoin.core.transaction import Transaction

        async for block in self.mongo.async_db.blocks.find({"transactions.id": id}):
            if give_block:
                return block
            for txn in block["transactions"]:
                if txn["id"] == id:
                    if instance:
                        return Transaction.from_dict(txn)
                    else:
                        return txn
        if inc_mempool:
            res2 = await self.mongo.async_db.miner_transactions.find_one({"id": id})
            if res2:
                if give_block:
                    raise Exception("Cannot give block for mempool transaction")
                if instance:
                    return Transaction.from_dict(res2)
                else:
                    return res2
            return None
        else:
            # fix for bug when unspent cache returns an input
            # that has been removed from the chain
            await self.mongo.async_db.unspent_cache.delete_many({})
            return None

    async def is_input_spent(
        self,
        input_ids,
        public_key,
        instance=False,
        give_block=False,
        include_fastgraph=False,
        inc_mempool=False,
        from_index=None,
        extra_blocks=None,
        spender_inception=None,
    ):
        if not isinstance(input_ids, list):
            input_ids = [input_ids]
        input_ids_set = set(input_ids)

        from yadacoin.core.keyeventlog import KeyEventLog

        async def conflicts(other_public_key, other_inception=None):
            # Non-KEL: exact public_key match only.
            # KEL: True when both keys share the same inception. Prefer tags on
            # the spending txns (pool tip keys often lack on-chain address
            # resolution until confirmed).
            return await KeyEventLog.kel_spend_conflict(
                public_key,
                other_public_key,
                inception_a=spender_inception,
                inception_b=other_inception,
                onchain_only=True,
            )

        # Candidate fork / sync batch: scan prior in-memory blocks first.
        # from_index is the block being validated — only earlier fork heights
        # can have already spent this input.
        fork_indices = set()
        if extra_blocks:
            for block in extra_blocks:
                fork_indices.add(block.index)
                if from_index is not None and block.index >= from_index:
                    continue
                for txn in block.transactions:
                    for txn_input in getattr(txn, "inputs", None) or []:
                        if getattr(txn_input, "id", None) in input_ids_set:
                            other_inc = getattr(txn, "inception_public_key_hash", None)
                            if await conflicts(
                                getattr(txn, "public_key", None), other_inc
                            ):
                                return True

        # Search mongo by input id only. Heights covered by extra_blocks are
        # replaced by the fork view above and must not count as spent.
        query = [
            {
                "$match": {
                    "transactions": {
                        "$elemMatch": {
                            "inputs.id": {"$in": input_ids},
                        }
                    }
                }
            },
            {"$unwind": "$transactions"},
            {
                "$match": {
                    "transactions.inputs.id": {"$in": input_ids},
                }
            },
        ]
        if from_index is not None:
            self.config.app_log.debug(f"from_index {from_index}")
            query.insert(0, {"$match": {"index": {"$lt": from_index}}})
        async for x in self.mongo.async_db.blocks.aggregate(query, allowDiskUse=True):
            if x.get("index") in fork_indices:
                continue
            other_txn = x.get("transactions", {}) or {}
            if await conflicts(
                other_txn.get("public_key"),
                other_txn.get("inception_public_key_hash"),
            ):
                return True

        if inc_mempool:
            if await self.get_mempool_transactions(
                public_key, input_ids, spender_inception=spender_inception
            ):
                return True
        return False

    async def get_mempool_transactions(
        self, public_key, input_ids, spender_inception=None
    ):
        from yadacoin.core.keyeventlog import KeyEventLog

        cursor = self.mongo.async_db.miner_transactions.find(
            {"inputs.id": {"$in": input_ids}}
        )
        async for doc in cursor:
            other_pk = doc.get("public_key")
            if not other_pk:
                continue
            if await KeyEventLog.kel_spend_conflict(
                public_key,
                other_pk,
                inception_a=spender_inception,
                inception_b=doc.get("inception_public_key_hash"),
                onchain_only=True,
            ):
                return doc
        return None

    async def _fetch_received_outputs(
        self,
        address,
        from_index=None,
        to_index=None,
        sort_time=-1,
        limit=None,
        max_blocks=None,
        min_value=0,
        sort_by_value=False,
    ):
        """Fetch grouped outputs paid to address, optionally bounded by block index.

        sort_time: -1 newest first (default), 1 oldest first.
        sort_by_value: if True, return largest grouped outputs first (best for spending).
        min_value: skip dust outputs below this amount.
        max_blocks: if set, only the newest/oldest matching blocks are unwound.
        """
        value_match = {"$gt": 0}
        if min_value and min_value > 0:
            value_match = {"$gte": float(min_value)}
        match = {
            "transactions.outputs.to": address,
            "transactions.outputs.value": value_match,
        }
        index_q = {}
        if from_index is not None:
            index_q["$gt"] = from_index
        if to_index is not None:
            index_q["$lt"] = to_index
        if index_q:
            match["index"] = index_q

        query = [{"$match": match}]
        # Bound block scan BEFORE unwind so large wallets stay fast.
        if max_blocks is not None:
            query.append({"$sort": {"index": -1 if sort_time < 0 else 1}})
            query.append({"$limit": int(max_blocks)})

        query.extend(
            [
                {"$unwind": "$transactions"},
                {"$unwind": "$transactions.outputs"},
                {
                    "$match": {
                        "transactions.outputs.to": address,
                        "transactions.outputs.value": value_match,
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "transactionId": "$transactions.id",
                            "to": "$transactions.outputs.to",
                        },
                        "totalValue": {"$sum": "$transactions.outputs.value"},
                        "time": {"$first": "$transactions.time"},
                    }
                },
                {
                    "$group": {
                        "_id": "$_id.transactionId",
                        "id": {"$first": "$_id.transactionId"},
                        "time": {"$first": "$time"},
                        "outputs": {"$push": {"to": "$_id.to", "value": "$totalValue"}},
                    }
                },
            ]
        )
        if sort_by_value:
            # Largest UTXOs first so spend selection covers amount_needed with fewer inputs.
            query.append({"$sort": {"outputs.value": -1, "time": -1}})
        else:
            query.append({"$sort": {"time": sort_time}})
        if limit is not None:
            query.append({"$limit": int(limit)})

        # Compound index supports match(to)+sort(index).
        if max_blocks is not None and from_index is None and to_index is None:
            hint = "__txn_outputs_to_index"
        elif from_index is None and to_index is None:
            hint = "__to"
        else:
            hint = None

        try:
            if hint:
                return await self.mongo.async_db.blocks.aggregate(
                    query, allowDiskUse=True, hint=hint
                ).to_list(length=None)
            return await self.mongo.async_db.blocks.aggregate(
                query, allowDiskUse=True
            ).to_list(length=None)
        except Exception:
            return await self.mongo.async_db.blocks.aggregate(
                query, allowDiskUse=True
            ).to_list(length=None)

    async def _filter_unspent_outputs(
        self, public_key, outputs, batch_size=100, max_unspent=None, amount_needed=None
    ):
        """Drop spent outputs; optionally stop once max_unspent / amount_needed met."""
        if not outputs:
            return [], 0.0

        unspent = []
        total = 0.0
        pending = []

        async def flush():
            nonlocal total
            if not pending:
                return False
            ids = [o["id"] for o in pending if o.get("id")]
            spent = await self.get_spent_among_candidates(public_key, ids)
            stop = False
            for output in pending:
                oid = output.get("id")
                if not oid or oid in spent:
                    continue
                value = sum(
                    float(o.get("value") or 0.0) for o in (output.get("outputs") or [])
                )
                unspent.append(output)
                total += value
                if max_unspent is not None and len(unspent) >= max_unspent:
                    stop = True
                    break
                if (
                    amount_needed is not None
                    and amount_needed > 0
                    and total >= amount_needed
                ):
                    stop = True
                    break
            pending.clear()
            return stop

        for output in outputs:
            pending.append(output)
            if len(pending) >= batch_size:
                if await flush():
                    return unspent, total
        await flush()
        return unspent, total

    def _utxo_value(self, utxo):
        return sum(float(o.get("value") or 0.0) for o in (utxo.get("outputs") or []))

    async def _select_spendable_utxos(
        self, address, public_key, max_utxos, amount_needed=0, min_value=None
    ):
        """
        Find up to max_utxos currently-unspent outputs for spending.

        Prefers larger UTXOs so amount_needed is covered with fewer inputs.
        Expands the block window until amount_needed is met or max_utxos is full.
        """
        if min_value is None:
            # Default dust floor from config; never require more than the spend target.
            cfg_min = float(getattr(self.config, "balance_min_utxo", 0) or 0)
            if amount_needed and amount_needed > 0:
                # Allow collecting smaller coins only when needed to hit the target
                # with MAX_INPUTS, but still skip pure dust when larger coins exist.
                min_value = min(cfg_min, float(amount_needed) / max(max_utxos, 1))
            else:
                min_value = cfg_min

        # Progressive windows: start moderate, grow until covered.
        windows = [
            (max(max_utxos * 20, 2000), max(max_utxos * 50, 2000)),
            (max(max_utxos * 100, 10000), max(max_utxos * 200, 10000)),
            (max(max_utxos * 500, 50000), max(max_utxos * 500, 25000)),
        ]

        unspent = []
        total = 0.0
        seen = set()
        target = float(amount_needed) if amount_needed else None

        for max_blocks, max_candidates in windows:
            if len(unspent) >= max_utxos:
                break
            if target is not None and total >= target:
                break

            outputs = await self._fetch_received_outputs(
                address,
                sort_time=-1,
                limit=max_candidates,
                max_blocks=max_blocks,
                min_value=min_value,
                sort_by_value=True,
            )
            self.config.app_log.info(
                "UTXO select window for %s: got %s candidates "
                "(max_blocks=%s min_value=%s)",
                address,
                len(outputs),
                max_blocks,
                min_value,
            )

            # Largest first.
            outputs = sorted(
                outputs,
                key=lambda o: (-self._utxo_value(o), -(o.get("time") or 0)),
            )
            fresh = [o for o in outputs if o.get("id") and o.get("id") not in seen]
            for o in fresh:
                seen.add(o.get("id"))

            need = max_utxos - len(unspent)
            more, more_total = await self._filter_unspent_outputs(
                public_key,
                fresh,
                batch_size=50,
                max_unspent=need,
                amount_needed=(target - total) if target is not None else None,
            )
            unspent.extend(more)
            total += more_total

            # If this window returned fewer candidates than requested, deeper
            # windows will not add much for this min_value — try dust next.
            if len(outputs) < max_candidates and (target is None or total < target):
                break

        # Fallback: if still short and we were filtering dust, retry without min_value.
        if (
            (
                (target is not None and total < target and len(unspent) < max_utxos)
                or (target is None and len(unspent) < max_utxos)
            )
            and min_value
            and min_value > 0
        ):
            self.config.app_log.info(
                "UTXO select dust fallback for %s (have %.8f need %s)",
                address,
                total,
                target,
            )
            more_u, more_t = await self._select_spendable_utxos(
                address,
                public_key,
                max_utxos - len(unspent),
                amount_needed=(target - total) if target is not None else 0,
                min_value=0,
            )
            for u in more_u:
                oid = u.get("id")
                if oid and oid not in seen:
                    unspent.append(u)
                    seen.add(oid)
                    total += self._utxo_value(u)
                if len(unspent) >= max_utxos:
                    break
                if target is not None and total >= target:
                    break

        # Final order: largest first for max_transferable / efficient spends.
        unspent = sorted(
            unspent, key=lambda o: (-self._utxo_value(o), o.get("time") or 0)
        )
        return unspent[:max_utxos], sum(
            self._utxo_value(u) for u in unspent[:max_utxos]
        )

    async def get_unspent_outputs(
        self,
        address,
        amount_needed=0,
        min_value=0,
        max_utxos=None,
        from_index=None,
    ):
        """
        Retrieves unspent transaction outputs (UTXOs) for the given address.

        Never returns more than CHAIN.MAX_INPUTS UTXOs (100), matching the
        per-transaction input limit.

        Chain UTXO selection is cached in wallet_unspent_cache (address +
        last_block_hash marker). Balance comes from wallet_balance_cache via
        get_wallet_balance — this method does not rescan the full receive history.
        """
        if max_utxos is None or max_utxos > CHAIN.MAX_INPUTS:
            max_utxos = CHAIN.MAX_INPUTS

        public_key = await self.get_reverse_public_key(address)
        latest_block = await self.get_latest_block_async()
        start_time = precise_time()

        # Balance is maintained separately (and cheaply once cached).
        balance_task = asyncio.create_task(self.get_wallet_balance(address))
        # Fetch mempool spends early so selection does not early-stop on
        # coins that will be filtered out by the mempool overlay.
        mempool_spent_task = asyncio.create_task(
            self.get_mempool_spent_inputs(public_key)
        )

        cache_doc = await self._get_wallet_unspent_cache(address)

        # amount_needed=0 is a balance/max_transferable poll. Prefer any
        # reorg-safe cached max_transferable without running selection.
        if not amount_needed and cache_doc:
            if await self._wallet_unspent_cache_is_valid(
                cache_doc, latest_block=latest_block
            ):
                balance = await balance_task
                max_t = cache_doc.get("max_transferable_value")
                if max_t is None:
                    max_t = sum(
                        self._utxo_value(u)
                        for u in (cache_doc.get("unspent_utxos") or [])
                    )
                max_t = self.floor_to_two_decimal_places(float(max_t or 0.0))
                elapsed = precise_time() - start_time
                self.config.app_log.info(
                    "Unspent cache DISPLAY for %s: max_transferable=%.8f (%.2fs)",
                    address,
                    max_t,
                    elapsed,
                )
                return {
                    "unspent_utxos": [],
                    "balance": balance,
                    "max_transferable_value": max_t,
                }
        cache_valid = await self._wallet_unspent_cache_is_valid(
            cache_doc, latest_block=latest_block
        )
        if cache_doc and not cache_valid:
            await self._invalidate_wallet_unspent_cache(
                address, reason="reorg or missing marker block hash"
            )
            cache_doc = None

        selectable = None
        cache_mode = "FULL"

        # Fast path: tip unchanged.
        # Use cache when:
        #  - no amount requested, or
        #  - cached UTXOs cover amount_needed, or
        #  - cache already holds a full max_utxos set (can't spend more inputs), or
        #  - cache was marked selection_complete (full select already done at this tip)
        if (
            cache_valid
            and latest_block
            and cache_doc.get("last_block_hash") == latest_block.get("hash")
        ):
            cached = list(cache_doc.get("unspent_utxos") or [])[:max_utxos]
            cached_total = float(
                cache_doc.get("max_transferable_value")
                if cache_doc.get("max_transferable_value") is not None
                else sum(self._utxo_value(u) for u in cached)
            )
            at_input_cap = len(cached) >= max_utxos
            complete = bool(cache_doc.get("selection_complete"))
            covers = (not amount_needed) or cached_total >= float(amount_needed)
            if covers or at_input_cap or complete:
                selectable = cached
                cache_mode = "HIT"
            else:
                # Cache has fewer than max_utxos and can't cover amount — try harder.
                self.config.app_log.info(
                    "Unspent cache incomplete for %s: have %.8f/%s utxos need %.8f — reselect",
                    address,
                    cached_total,
                    len(cached),
                    float(amount_needed),
                )
                cache_mode = "RESELECT"

        # Incremental: drop spends since marker, add new receives, re-select top N.
        elif cache_valid and latest_block:
            cache_mode = "INCREMENTAL"
            marker_index = cache_doc.get("last_block_index")
            by_id = {
                u["id"]: u
                for u in (cache_doc.get("unspent_utxos") or [])
                if u.get("id")
            }

            new_outputs, spent_since = await asyncio.gather(
                self._fetch_received_outputs(
                    address,
                    from_index=marker_index,
                    sort_time=-1,
                    limit=1000,
                    max_blocks=2000,
                ),
                (
                    self.get_spent_among_candidates(
                        public_key, list(by_id.keys()), from_index=marker_index
                    )
                    if by_id
                    else self._async_empty_set()
                ),
            )
            for oid in list(by_id.keys()):
                if oid in spent_since:
                    del by_id[oid]
            for output in new_outputs:
                oid = output.get("id")
                if oid:
                    by_id[oid] = output

            # Re-check spend status for merged set (covers edge cases).
            merged = list(by_id.values())
            unspent, _ = await self._filter_unspent_outputs(
                public_key, merged, batch_size=100, max_unspent=max_utxos
            )
            # If cache was sparse and we still need more, pull fresh newest candidates.
            if len(unspent) < max_utxos:
                extra, _ = await self._select_spendable_utxos(
                    address, public_key, max_utxos, amount_needed=amount_needed
                )
                seen = {u.get("id") for u in unspent}
                for u in extra:
                    if u.get("id") not in seen:
                        unspent.append(u)
                        seen.add(u.get("id"))
                    if len(unspent) >= max_utxos:
                        break
            selectable = unspent[:max_utxos]
            sel_total = sum(self._utxo_value(u) for u in selectable)
            # Only reselect if we have room for more inputs AND still short.
            if (
                amount_needed
                and sel_total < float(amount_needed)
                and len(selectable) < max_utxos
            ):
                selectable = None  # fall through to full select
            elif not from_index and selectable is not None:
                await self._save_wallet_unspent_cache(
                    address,
                    public_key,
                    selectable,
                    latest_block,
                    selection_complete=True,
                    max_utxos=max_utxos,
                )

        # Full cold select / reselect: largest live outputs up to max_utxos.
        if selectable is None:
            if cache_mode != "RESELECT":
                cache_mode = "FULL"
            if from_index:
                outputs = await self._fetch_received_outputs(
                    address,
                    to_index=from_index,
                    sort_time=-1,
                    limit=max_utxos * 50,
                    min_value=float(getattr(self.config, "balance_min_utxo", 0) or 0),
                    sort_by_value=True,
                )
                # Exclude mempool-spent before amount trim so under-collection
                # cannot leave us short after the overlay.
                spent_mp = set(await mempool_spent_task or [])
                if spent_mp:
                    outputs = [o for o in outputs if o.get("id") not in spent_mp]
                selectable, _ = await self._filter_unspent_outputs(
                    public_key,
                    outputs,
                    batch_size=100,
                    max_unspent=max_utxos,
                    amount_needed=amount_needed if amount_needed else None,
                )
            else:
                # Do not early-stop on amount during chain select; mempool may
                # remove large coins. Collect up to max_utxos then overlay.
                selectable, _ = await self._select_spendable_utxos(
                    address, public_key, max_utxos, amount_needed=0
                )
                spent_mp = set(await mempool_spent_task or [])
                if spent_mp:
                    selectable = [u for u in selectable if u.get("id") not in spent_mp]
                if latest_block:
                    await self._save_wallet_unspent_cache(
                        address,
                        public_key,
                        selectable,
                        latest_block,
                        selection_complete=True,
                        max_utxos=max_utxos,
                    )

        # Mempool overlay (not cached).
        spent_inputs_mempool = set(await mempool_spent_task or [])
        if spent_inputs_mempool:
            selectable = [
                u for u in selectable if u.get("id") not in spent_inputs_mempool
            ]

        balance = await balance_task

        # Largest first so max_transferable and amount_needed use the best coins.
        top = sorted(
            selectable or [],
            key=lambda x: (-self._utxo_value(x), x.get("time") or 0),
        )[:max_utxos]
        max_transferable_value = self.floor_to_two_decimal_places(
            sum(self._utxo_value(u) for u in top)
        )

        if not amount_needed:
            elapsed = precise_time() - start_time
            self.config.app_log.info(
                "Unspent cache %s for %s: balance=%.8f selectable=%s "
                "max_transferable=%.8f (%.2fs)",
                cache_mode,
                address,
                balance,
                len(top),
                max_transferable_value,
                elapsed,
            )
            return {
                "unspent_utxos": [],
                "balance": balance,
                "max_transferable_value": max_transferable_value,
            }

        unspent_utxos = []
        total_collected_value = 0.0
        for utxo in top:
            value = self._utxo_value(utxo)
            unspent_utxos.append(utxo)
            total_collected_value += value
            if total_collected_value >= amount_needed:
                break

        elapsed = precise_time() - start_time
        self.config.app_log.info(
            "Unspent cache %s for %s: returning %s/%s utxos collected=%.8f "
            "balance=%.8f (%.2fs)",
            cache_mode,
            address,
            len(unspent_utxos),
            max_utxos,
            total_collected_value,
            balance,
            elapsed,
        )

        return {
            "unspent_utxos": unspent_utxos,
            "balance": balance,
            "max_transferable_value": max_transferable_value,
        }

    def floor_to_two_decimal_places(self, value):
        """Rounds the value down to two decimal places."""
        return math.floor(value * 100) / 100

    async def get_chain_spent_inputs(self, public_key, batch_size=100000):
        """
        Retrieves spent input IDs for the given public key.

        Streams one document per input id (no $addToSet) to avoid MongoDB's
        16MB BSON document limit on large wallets.
        """
        if not public_key:
            return set()

        query = [
            {"$match": {"transactions.public_key": public_key}},
            {
                "$project": {
                    "transactions": {
                        "$filter": {
                            "input": "$transactions",
                            "as": "txn",
                            "cond": {"$eq": ["$$txn.public_key", public_key]},
                        }
                    }
                }
            },
            {"$unwind": "$transactions"},
            {"$unwind": "$transactions.inputs"},
            {
                "$match": {
                    "transactions.inputs.id": {"$exists": True, "$ne": None},
                }
            },
            {"$project": {"_id": 0, "id": "$transactions.inputs.id"}},
        ]

        spent_inputs = set()
        async for doc in self._iter_blocks_aggregate(query, hint="__txn_public_key"):
            inp_id = doc.get("id")
            if inp_id is not None:
                spent_inputs.add(inp_id)
        return spent_inputs

    async def get_spent_among_candidates(
        self, public_key, candidate_ids, batch_size=500, from_index=None
    ):
        """
        Return the subset of candidate_ids that are already spent on-chain
        by transactions signed with public_key.

        Groups by individual input id (small docs) and only searches among
        the provided candidates — avoids loading every historical spent input.
        When from_index is set, only blocks after that height are scanned
        (incremental cache updates).
        """
        if not public_key or not candidate_ids:
            return set()

        candidates = list(candidate_ids)
        spent = set()
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i + batch_size]
            match = {
                "transactions.public_key": public_key,
                "transactions.inputs.id": {"$in": batch},
            }
            if from_index is not None:
                match["index"] = {"$gt": from_index}
            query = [
                {"$match": match},
                {
                    "$project": {
                        "transactions": {
                            "$filter": {
                                "input": "$transactions",
                                "as": "txn",
                                "cond": {"$eq": ["$$txn.public_key", public_key]},
                            }
                        }
                    }
                },
                {"$unwind": "$transactions"},
                {"$unwind": "$transactions.inputs"},
                {"$match": {"transactions.inputs.id": {"$in": batch}}},
                {"$group": {"_id": "$transactions.inputs.id"}},
            ]
            # Prefer compound index when available (skip hint on incremental index filter).
            hint = None if from_index is not None else "__txn_public_key_inputs_id"
            async for doc in self._iter_blocks_aggregate(query, hint=hint):
                if doc.get("_id") is not None:
                    spent.add(doc["_id"])
        return spent

    async def get_mempool_spent_inputs(self, public_key):
        """
        Fetches all input IDs (`inputs.id`) used in mempool transactions signed by a given public key.

        Function Description:
        1. Matches all transactions in the mempool signed by the provided public key.
        2. Expands the `inputs` array in those transactions, breaking it into individual records.
        3. Groups the results to create a unique list of all `inputs.id`.

        :param public_key: The public key for which input IDs are to be fetched.
        :return: A list of unique input IDs (`inputs.id`) from the matching mempool transactions.
        """

        query = [
            {
                "$match": {
                    "public_key": public_key,
                }
            },
            {"$unwind": "$inputs"},
            {"$group": {"_id": None, "spent_inputs": {"$addToSet": "$inputs.id"}}},
        ]

        result = await self.mongo.async_db.miner_transactions.aggregate(query).to_list(
            length=None
        )

        return result[0]["spent_inputs"] if result else []

    def get_hash_rate(self, blocks):
        sum_time = 0
        sum_work = 0
        max_target = (2**16 - 1) * 2**208
        prev_time = 0
        for block in blocks:
            # calculations from https://bitcoin.stackexchange.com/questions/14086/how-can-i-calculate-network-hashrate-for-a-given-range-of-blocks-where-difficult/30225#30225
            difficulty = max_target / block.target
            sum_work += difficulty * 4295032833
            if prev_time > 0:
                sum_time += prev_time - int(block.time)
            prev_time = int(block.time)

        # total work(number of hashes) over time gives us the hashrate
        return int(sum_work / sum_time) if len(blocks) > 1 else 0
