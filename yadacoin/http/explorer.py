"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Handlers required by the explorer operations
"""

import base64
import os
import re
import time

from yadacoin.core.chain import CHAIN
from yadacoin.core.common import changetime
from yadacoin.decorators.jwtauth import jwtauthwallet
from yadacoin.http.base import BaseHandler

_FILE_SEARCH_FIELDS = (
    "title",
    "description",
    "keywords",
    "file_id",
    "filename",
    "share_url",
)


def _file_announcement_query(prefix, term):
    text = (term or "").strip()
    if not text:
        return None
    regex = {"$regex": re.escape(text), "$options": "i"}
    return {"$or": [{f"{prefix}.{field}": regex} for field in _FILE_SEARCH_FIELDS]}


_ANNOUNCEMENT_KEYS = (
    "identity",
    "node",
    "agent",
    "file",
    "credential",
    "branch",
    "rotation",
    "recovery",
    "recovers",
    "content_takedown",
)

_USERNAME_PATHS = (
    "relationship.identity.username",
    "relationship.node.identity.username",
    "relationship.agent.identity.username",
)

_SIGNATURE_PATHS = (
    "relationship.identity.username_signature",
    "relationship.node.identity.username_signature",
    "relationship.agent.identity.username_signature",
    "relationship.credential.subject_username_signature",
    "relationship.credential.issuer_username_signature",
)

_IDENTITY_TXN_PATHS = (
    "relationship.node.identity_announcement",
    "relationship.branch.identity_announcement",
    "relationship.credential.issuer_identity_announcement",
)

_PROFILE_LIMIT = 100


def _username_values(username):
    text = (username or "").strip()
    if not text:
        return []
    values = [text]
    lowered = text.lower()
    if lowered not in values:
        values.append(lowered)
    return values


def _eq(prefix, path, value):
    if isinstance(value, (list, tuple, set)):
        values = [item for item in value if item]
        if not values:
            return None
        if len(values) == 1:
            return {f"{prefix}{path}": values[0]}
        return {f"{prefix}{path}": {"$in": values}}
    if not value:
        return None
    return {f"{prefix}{path}": value}


def _nested(value, *keys):
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _announcement_kind(relationship):
    if not isinstance(relationship, dict):
        return None
    for key in _ANNOUNCEMENT_KEYS:
        if key in relationship:
            return key
    return None


def _same_username(left, right):
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    return left.strip().lower() == right.strip().lower()


def _signature_values(relationship):
    values = []
    for path in (
        ("identity", "username_signature"),
        ("node", "identity", "username_signature"),
        ("agent", "identity", "username_signature"),
        ("credential", "subject_username_signature"),
        ("credential", "issuer_username_signature"),
    ):
        value = _nested(relationship, *path)
        if isinstance(value, str) and value:
            values.append(value)
    return values


def _identity_from_txn(txn):
    identity = _nested(txn, "relationship", "identity")
    if not isinstance(identity, dict) or not identity.get("username"):
        return None
    return identity


def _txn_linked(txn, username, signature, identity_txn_id, public_keys):
    if not isinstance(txn, dict):
        return False
    relationship = txn.get("relationship") or {}
    if not _announcement_kind(relationship):
        return False
    if username:
        for path in (
            ("identity", "username"),
            ("node", "identity", "username"),
            ("agent", "identity", "username"),
        ):
            if _same_username(_nested(relationship, *path), username):
                return True
    if signature and signature in _signature_values(relationship):
        return True
    if identity_txn_id:
        if txn.get("id") == identity_txn_id:
            return True
        for path in (
            ("node", "identity_announcement"),
            ("branch", "identity_announcement"),
            ("credential", "issuer_identity_announcement"),
        ):
            if _nested(relationship, *path) == identity_txn_id:
                return True
    if public_keys and txn.get("public_key") in public_keys:
        return True
    return False


def _profile_queries(prefix, username, signature, identity_txn_id, public_keys):
    queries = []
    usernames = _username_values(username)
    if usernames:
        for path in _USERNAME_PATHS:
            queries.append(_eq(prefix, path, usernames))
    if signature:
        for path in _SIGNATURE_PATHS:
            queries.append(_eq(prefix, path, signature))
    if identity_txn_id:
        queries.append(_eq(prefix, "id", identity_txn_id))
        for path in _IDENTITY_TXN_PATHS:
            queries.append(_eq(prefix, path, identity_txn_id))
    if public_keys:
        keys = [key for key in public_keys if key]
        for key in _ANNOUNCEMENT_KEYS:
            query = _eq(prefix, "public_key", keys)
            if not query:
                continue
            query[f"{prefix}relationship.{key}"] = {"$exists": True}
            queries.append(query)
    return [query for query in queries if query]


def _stamp_time(doc, fallback=None):
    stamped = dict(doc)
    if stamped.get("time") in (None, ""):
        stamped["time"] = 0 if fallback is None else fallback
    try:
        return changetime(stamped)
    except Exception:
        return stamped


def _address_for_public_key(public_key):
    try:
        from bitcoin.wallet import P2PKHBitcoinAddress

        return str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
    except Exception:
        return ""


class HashrateAPIHandler(BaseHandler):
    async def refresh(self):
        from yadacoin.core.block import Block

        blocks = [
            await Block.from_dict(x)
            async for x in self.config.mongo.async_db.blocks.find({})
            .sort([("index", -1)])
            .limit(48)
        ]
        difficulty = int(CHAIN.MAX_TARGET / blocks[0].target)

        hash_rate = self.config.BU.get_hash_rate(blocks)
        self.config.HashRateAPIHandler = {
            "cache": {
                "time": time.time(),
                "circulating": CHAIN.get_circulating_supply(blocks[0].index),
                "height": blocks[0].index,
                "network_hash_rate": hash_rate,
                "difficulty": difficulty,
            }
        }

    async def get(self):
        self.config
        if not hasattr(self.config, "HashRateAPIHandler"):
            await self.refresh()
        elif time.time() - self.config.HashRateAPIHandler["cache"]["time"] > 600:
            await self.refresh()
        self.render_as_json({"stats": self.config.HashRateAPIHandler["cache"]})


_CHAIN_EXPLORER_INDEX = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "plugins",
        "chainexplorer",
        "dist",
        "index.html",
    )
)


class ExplorerHandler(BaseHandler):
    async def get(self):
        if os.path.exists(_CHAIN_EXPLORER_INDEX):
            from plugins.chainexplorer.handlers import explorer_page

            self.set_header("Content-Type", "text/html; charset=utf-8")
            self.finish(explorer_page(self))
            return
        self.render(
            "explorer/index.html",
            title="YadaCoin - Explorer",
            mixpanel="explorer page",
        )


class ExplorerSearchHandler(BaseHandler):
    async def get_wallet_balance(self, term):
        re.search(r"[A-Fa-f0-9]+", term).group(0)
        res = await self.config.mongo.async_db.blocks.count_documents(
            {"transactions.outputs.to": term}
        )
        if res:
            balance = await self.config.BU.get_wallet_balance(term)
            return self.render_as_json(
                {
                    "balance": "{0:.8f}".format(balance),
                    "resultType": "txn_outputs_to",
                    "result": [
                        changetime(x)
                        async for x in self.config.mongo.async_db.blocks.find(
                            {"transactions.outputs.to": term}, {"_id": 0}
                        )
                        .sort("index", -1)
                        .limit(10)
                    ],
                }
            )

    async def _iter_docs(self, collection, queries):
        docs = []
        seen = set()
        for query in queries:
            try:
                cursor = collection.find(query, {"_id": 0}).limit(_PROFILE_LIMIT)
                async for doc in cursor:
                    key = doc.get("hash") or doc.get("id") or id(doc)
                    if key in seen:
                        continue
                    seen.add(key)
                    docs.append(doc)
            except Exception:
                continue
        return docs

    async def _keys_for_identity(self, public_key):
        keys = set()
        if public_key:
            keys.add(public_key)
        if not public_key:
            return keys
        try:
            from yadacoin.core.keyeventlog import KeyEventLog

            log = await KeyEventLog.get_log(public_key=public_key, onchain_only=False)
        except Exception:
            return keys
        for entry in log or []:
            key = getattr(entry, "public_key", None)
            if not key and isinstance(entry, dict):
                key = entry.get("public_key")
            if key:
                keys.add(key)
        return keys

    async def _identity_anchor(self, term):
        username = (term or "").strip()
        if not username or len(username) > 253:
            return None
        db = self.config.mongo.async_db
        usernames = _username_values(username)
        if not usernames:
            return None
        block = await db.blocks.find_one(
            _eq("transactions.", "relationship.identity.username", usernames),
            {"_id": 0},
        )
        if isinstance(block, dict):
            for txn in block.get("transactions") or []:
                identity = _identity_from_txn(txn)
                if identity and _same_username(identity.get("username"), username):
                    return {
                        "block": block,
                        "txn": txn,
                        "identity": identity,
                        "source": "blockchain",
                    }
        mempool = await db.miner_transactions.find_one(
            _eq("", "relationship.identity.username", usernames),
            {"_id": 0},
        )
        if isinstance(mempool, dict):
            identity = _identity_from_txn(mempool)
            if identity and _same_username(identity.get("username"), username):
                return {
                    "block": None,
                    "txn": mempool,
                    "identity": identity,
                    "source": "mempool",
                }
        signature = username.replace(" ", "+")
        try:
            base64.b64decode(signature)
        except Exception:
            return None
        block = await db.blocks.find_one(
            {"transactions.relationship.identity.username_signature": signature},
            {"_id": 0},
        )
        if isinstance(block, dict):
            for txn in block.get("transactions") or []:
                identity = _identity_from_txn(txn)
                if identity and identity.get("username_signature") == signature:
                    return {
                        "block": block,
                        "txn": txn,
                        "identity": identity,
                        "source": "blockchain",
                    }
        mempool = await db.miner_transactions.find_one(
            {"relationship.identity.username_signature": signature},
            {"_id": 0},
        )
        if isinstance(mempool, dict):
            identity = _identity_from_txn(mempool)
            if identity and identity.get("username_signature") == signature:
                return {
                    "block": None,
                    "txn": mempool,
                    "identity": identity,
                    "source": "mempool",
                }
        return None

    def _profile_hit(self, kind, source, txn, block=None, reason="", error=""):
        raw = dict(txn)
        if reason and not raw.get("reason"):
            raw["reason"] = reason
        if error and not raw.get("error"):
            raw["error"] = error
        fallback = block.get("time") if isinstance(block, dict) else None
        stamped = _stamp_time(raw, fallback)
        hit = {"kind": kind, "source": source, "txn": stamped}
        if isinstance(block, dict):
            if block.get("index") is not None:
                hit["block_index"] = block.get("index")
            if block.get("hash"):
                hit["block_hash"] = block.get("hash")
        if reason:
            hit["reason"] = reason
        if error:
            hit["error"] = error
        return hit

    def _remember_hit(self, hits, seen, hit):
        txn = hit.get("txn") or {}
        key = (
            hit.get("source"),
            hit.get("kind"),
            txn.get("id") or txn.get("hash") or txn.get("rid"),
            hit.get("block_index"),
        )
        if key in seen:
            return
        seen.add(key)
        hits.append(hit)

    async def username_profile(self, term):
        anchor = await self._identity_anchor(term)
        if not anchor:
            return None
        identity = anchor["identity"]
        username = identity.get("username") or (term or "").strip()
        signature = identity.get("username_signature") or ""
        anchor_txn = anchor["txn"]
        identity_txn_id = anchor_txn.get("id") or ""
        public_key = anchor_txn.get("public_key") or ""
        public_keys = await self._keys_for_identity(public_key)
        addresses = []
        for key in public_keys:
            address = _address_for_public_key(key)
            if address and address not in addresses:
                addresses.append(address)

        hits = []
        seen = set()
        self._remember_hit(
            hits,
            seen,
            self._profile_hit(
                "identity",
                anchor["source"],
                anchor_txn,
                anchor.get("block"),
            ),
        )
        db = self.config.mongo.async_db
        try:
            clauses = _profile_queries(
                "transactions.",
                username,
                signature,
                identity_txn_id,
                public_keys,
            )
            if clauses:
                for block in await self._iter_docs(db.blocks, clauses):
                    for inner in block.get("transactions") or []:
                        if not _txn_linked(
                            inner, username, signature, identity_txn_id, public_keys
                        ):
                            continue
                        self._remember_hit(
                            hits,
                            seen,
                            self._profile_hit(
                                _announcement_kind(inner.get("relationship")),
                                "blockchain",
                                inner,
                                block,
                            ),
                        )
        except Exception:
            pass
        try:
            clauses = _profile_queries(
                "", username, signature, identity_txn_id, public_keys
            )
            if clauses:
                for inner in await self._iter_docs(db.miner_transactions, clauses):
                    if not _txn_linked(
                        inner, username, signature, identity_txn_id, public_keys
                    ):
                        continue
                    self._remember_hit(
                        hits,
                        seen,
                        self._profile_hit(
                            _announcement_kind(inner.get("relationship")),
                            "mempool",
                            inner,
                        ),
                    )
        except Exception:
            pass
        try:
            clauses = _profile_queries(
                "txn.", username, signature, identity_txn_id, public_keys
            )
            if clauses:
                for wrapper in await self._iter_docs(db.failed_transactions, clauses):
                    inner = wrapper.get("txn") if isinstance(wrapper, dict) else None
                    if not isinstance(inner, dict):
                        inner = wrapper if isinstance(wrapper, dict) else None
                    if not _txn_linked(
                        inner, username, signature, identity_txn_id, public_keys
                    ):
                        continue
                    self._remember_hit(
                        hits,
                        seen,
                        self._profile_hit(
                            _announcement_kind(inner.get("relationship")),
                            "failed",
                            inner,
                            reason=wrapper.get("reason")
                            or wrapper.get("exception")
                            or "",
                            error=wrapper.get("error") or "",
                        ),
                    )
        except Exception:
            pass

        def rank(hit):
            source_rank = {"blockchain": 0, "mempool": 1, "failed": 2}.get(
                hit.get("source"), 3
            )
            kind_rank = 0 if hit.get("kind") == "identity" else 1
            return (kind_rank, source_rank, -(hit.get("block_index") or 0))

        hits.sort(key=rank)
        counts = {}
        for hit in hits:
            counts[hit["kind"]] = counts.get(hit["kind"], 0) + 1
        payload = {
            "resultType": "username_profile",
            "username": username,
            "identity": {
                "username": username,
                "username_signature": signature,
                "identity_type": identity.get("identity_type") or "",
                "public_key": public_key,
                "public_keys": sorted(public_keys),
                "addresses": addresses,
                "transaction_id": identity_txn_id,
                "source": anchor["source"],
            },
            "counts": counts,
            "announcements": hits,
            "result": [hit["txn"] for hit in hits],
        }
        block = anchor.get("block")
        if isinstance(block, dict):
            if block.get("index") is not None:
                payload["identity"]["block_index"] = block.get("index")
            if block.get("hash"):
                payload["identity"]["block_hash"] = block.get("hash")
        if addresses:
            try:
                amount = await self.config.BU.get_wallet_balance(
                    addresses[0], wait=False
                )
                payload["balance"] = "{0:.8f}".format(float(amount))
            except Exception:
                pass
        return payload

    async def get(self):
        term = self.get_argument("term", False)
        if not term:
            self.render_as_json({})
            return

        result_type = self.get_argument("result_type", False)
        if result_type == "get_wallet_balance":
            try:
                return await self.get_wallet_balance(term)
            except Exception:
                raise

        try:
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"index": int(term)}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "block_height",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"index": int(term)}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass
        try:
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"public_key": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "block_height",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"public_key": term}, {"_id": 0}
                            ).limit(100)
                        ],
                    }
                )
        except:
            pass
        try:
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"transactions.public_key": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "block_height",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"transactions.public_key": term}, {"_id": 0}
                            ).limit(100)
                        ],
                    }
                )
        except:
            pass
        try:
            re.search(r"[A-Fa-f0-9]{64}", term).group(0)
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"hash": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "block_hash",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"hash": term}, {"_id": 0}
                            ).limit(10)
                        ],
                    }
                )
        except:
            pass

        try:
            base64.b64decode(term.replace(" ", "+"))
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"id": term.replace(" ", "+")}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "block_id",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"id": term.replace(" ", "+")}, {"_id": 0}
                            ).limit(10)
                        ],
                    }
                )
        except:
            pass

        try:
            re.search(r"[A-Fa-f0-9]{64}", term).group(0)
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"transactions.hash": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "txn_hash",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"transactions.hash": term}, {"_id": 0}
                            ).limit(10)
                        ],
                    }
                )
        except:
            pass

        try:
            re.search(r"[A-Fa-f0-9]{64}", term).group(0)
            res = await self.config.mongo.async_db.blocks.count_documents(
                {"transactions.rid": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "txn_rid",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {"transactions.rid": term}, {"_id": 0}
                            ).limit(10)
                        ],
                    }
                )
        except:
            pass

        try:
            base64.b64decode(term.replace(" ", "+"))
            res = await self.config.mongo.async_db.blocks.count_documents(
                {
                    "$or": [
                        {"transactions.id": term.replace(" ", "+")},
                        {"transactions.inputs.id": term.replace(" ", "+")},
                    ]
                }
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "txn_id",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.blocks.find(
                                {
                                    "$or": [
                                        {"transactions.id": term.replace(" ", "+")},
                                        {
                                            "transactions.inputs.id": term.replace(
                                                " ", "+"
                                            )
                                        },
                                    ]
                                },
                                {"_id": 0},
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            re.search(r"[A-Fa-f0-9]{64}", term).group(0)
            for field in [
                "transactions.public_key_hash",
                "transactions.prev_public_key_hash",
                "transactions.prerotated_key_hash",
                "transactions.twice_prerotated_key_hash",
                "transactions.relationship_hash",
                "transactions.dh_public_key",
                "transactions.miner_signature",
            ]:
                res = await self.config.mongo.async_db.blocks.count_documents(
                    {field: term}
                )
                if res:
                    return self.render_as_json(
                        {
                            "resultType": "txn_hash",
                            "result": [
                                changetime(x)
                                async for x in self.config.mongo.async_db.blocks.find(
                                    {field: term}, {"_id": 0}
                                ).limit(10)
                            ],
                        }
                    )
        except:
            pass

        try:
            profile = await self.username_profile(term)
            if profile:
                return self.render_as_json(profile)
        except:
            pass

        try:
            file_filter = _file_announcement_query(
                "transactions.relationship.file", term
            )
            if file_filter:
                res = await self.config.mongo.async_db.blocks.count_documents(
                    file_filter
                )
                if res:
                    return self.render_as_json(
                        {
                            "resultType": "txn_file_announcement",
                            "result": [
                                changetime(x)
                                async for x in self.config.mongo.async_db.blocks.find(
                                    file_filter, {"_id": 0}
                                )
                                .sort("index", -1)
                                .limit(10)
                            ],
                        }
                    )
        except:
            pass

        try:
            res = await self.get_wallet_balance(term)
            if res:
                return res
        except Exception:
            pass

        try:
            base64.b64decode(term.replace(" ", "+"))
            res = await self.config.mongo.async_db.miner_transactions.count_documents(
                {"id": term.replace(" ", "+")}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "mempool_id",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.miner_transactions.find(
                                {"id": term.replace(" ", "+")}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            re.search(r"[A-Fa-f0-9]{64}", term).group(0)
            res = await self.config.mongo.async_db.miner_transactions.count_documents(
                {"hash": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "mempool_hash",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.miner_transactions.find(
                                {"hash": term}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            re.search(r"[A-Fa-f0-9]+", term).group(0)
            res = await self.config.mongo.async_db.miner_transactions.count_documents(
                {"outputs.to": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "mempool_outputs_to",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.miner_transactions.find(
                                {"outputs.to": term}, {"_id": 0}
                            )
                            .sort("index", -1)
                            .limit(10)
                        ],
                    }
                )
        except:
            pass

        try:
            res = await self.config.mongo.async_db.miner_transactions.count_documents(
                {"public_key": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "mempool_public_key",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.miner_transactions.find(
                                {"public_key": term}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            res = await self.config.mongo.async_db.miner_transactions.count_documents(
                {"rid": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "mempool_rid",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.miner_transactions.find(
                                {"rid": term}, {"_id": 0}
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            file_filter = _file_announcement_query("relationship.file", term)
            if file_filter:
                res = (
                    await self.config.mongo.async_db.miner_transactions.count_documents(
                        file_filter
                    )
                )
                if res:
                    return self.render_as_json(
                        {
                            "resultType": "mempool_file_announcement",
                            "result": [
                                changetime(x)
                                async for x in self.config.mongo.async_db.miner_transactions.find(
                                    file_filter, {"_id": 0}
                                )
                                .sort("time", -1)
                                .limit(10)
                            ],
                        }
                    )
        except:
            pass

        try:
            base64.b64decode(term.replace(" ", "+"))
            res = await self.config.mongo.async_db.failed_transactions.count_documents(
                {"txn.id": term.replace(" ", "+")}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "failed_id",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.failed_transactions.find(
                                {"txn.id": term.replace(" ", "+")},
                                {"_id": 0, "txn._id": 0},
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            re.search(r"[A-Fa-f0-9]{64}", term).group(0)
            res = await self.config.mongo.async_db.failed_transactions.count_documents(
                {"txn.hash": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "failed_hash",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.failed_transactions.find(
                                {"txn.hash": term},
                                {"_id": 0, "txn._id": 0},
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            re.search(r"[A-Fa-f0-9]+", term).group(0)
            res = await self.config.mongo.async_db.failed_transactions.count_documents(
                {"txn.outputs.to": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "failed_outputs_to",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.failed_transactions.find(
                                {"txn.outputs.to": term},
                                {"_id": 0, "txn._id": 0},
                            )
                            .sort("index", -1)
                            .limit(10)
                        ],
                    }
                )
        except:
            pass

        try:
            res = await self.config.mongo.async_db.failed_transactions.count_documents(
                {"txn.public_key": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "failed_public_key",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.failed_transactions.find(
                                {"txn.public_key": term},
                                {"_id": 0, "txn._id": 0},
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            res = await self.config.mongo.async_db.failed_transactions.count_documents(
                {"txn.rid": term}
            )
            if res:
                return self.render_as_json(
                    {
                        "resultType": "failed_rid",
                        "result": [
                            changetime(x)
                            async for x in self.config.mongo.async_db.failed_transactions.find(
                                {"txn.rid": term},
                                {"_id": 0, "txn._id": 0},
                            )
                        ],
                    }
                )
        except:
            pass

        try:
            file_filter = _file_announcement_query("txn.relationship.file", term)
            if file_filter:
                res = await self.config.mongo.async_db.failed_transactions.count_documents(
                    file_filter
                )
                if res:
                    return self.render_as_json(
                        {
                            "resultType": "failed_file_announcement",
                            "result": [
                                changetime(x)
                                async for x in self.config.mongo.async_db.failed_transactions.find(
                                    file_filter,
                                    {"_id": 0, "txn._id": 0},
                                )
                                .sort("index", -1)
                                .limit(10)
                            ],
                        }
                    )
        except:
            pass

        return self.render_as_json({})


class ExplorerGetBalance(BaseHandler):
    async def get(self):
        address = self.get_argument("address", False)
        if not address:
            self.render_as_json({})
            return
        balance = await self.config.BU.get_wallet_balance(address, wait=False)
        return self.render_as_json({"balance": "{0:.8f}".format(balance)})


class ExplorerLatestHandler(BaseHandler):
    async def get(self):
        """Returns abstract of the latest 10 blocks"""
        res = (
            self.config.mongo.async_db.blocks.find({}, {"_id": 0})
            .sort("index", -1)
            .limit(10)
        )
        res = await res.to_list(length=10)
        print(res[0])
        return self.render_as_json(
            {"resultType": "blocks", "result": [changetime(x) for x in res]}
        )


class ExplorerLast50(BaseHandler):
    async def get(self):
        """Returns abstract of the latest 50 blocks miners"""
        latest = self.config.LatestBlock.block
        pipeline = [
            {"$match": {"index": {"$gte": latest["index"] - 50}}},
            {
                "$project": {
                    "outputs": 1,
                    "transaction": {"$arrayElemAt": ["$transactions", -1]},
                }
            },
            {
                "$project": {
                    "outputs": 1,
                    "output": {"$arrayElemAt": ["$transaction.outputs", 0]},
                }
            },
            {"$project": {"outputs": 1, "to": "$output.to"}},
            {"$group": {"_id": "$to", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]

        miners = []
        async for doc in self.config.mongo.async_db.blocks.aggregate(pipeline):
            miners.append(doc)

        return self.render_as_json(miners)


class HolderListPageHandler(BaseHandler):
    async def get(self):
        self.render("holders.html", title="YadaCoin - Holder List")


@jwtauthwallet
class HolderListAPIHandler(BaseHandler):
    async def get(self):
        # Cache for 10 minutes — computing all balances is expensive
        if hasattr(self.config, "_holder_list_cache"):
            cached = self.config._holder_list_cache
            if time.time() - cached["time"] < 600:
                return self.render_as_json(cached["data"])

        from bitcoin.wallet import P2PKHBitcoinAddress

        db = self.config.mongo.async_db

        # Deduplication prefix: if orphan/reorg blocks exist at the same height,
        # keep only one per index (the first found after sorting by index).
        # This prevents orphan coinbase outputs being counted as unspent supply,
        # and prevents orphan spending transactions from incorrectly marking
        # canonical UTXOs as spent.
        DEDUP = [
            {"$sort": {"index": 1}},
            {
                "$group": {
                    "_id": "$index",
                    "transactions": {"$first": "$transactions"},
                }
            },
        ]

        # Step 1: Derive address for every public key that has ever signed a
        # spending txn on the canonical chain. Never relies on reversed_public_keys.
        pk_to_addr = {}
        async for doc in db.blocks.aggregate(
            DEDUP
            + [
                {"$unwind": "$transactions"},
                {"$match": {"transactions.inputs.0": {"$exists": True}}},
                {"$group": {"_id": "$transactions.public_key"}},
            ],
            allowDiskUse=True,
        ):
            pk = doc["_id"]
            if pk:
                try:
                    pk_to_addr[pk] = str(
                        P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(pk))
                    )
                except Exception:
                    pass

        # Step 2: Build spent_by_addr: {address -> set of txn_ids spent}.
        # Only canonical spending transactions are considered.
        spent_by_addr = {}
        async for doc in db.blocks.aggregate(
            DEDUP
            + [
                {"$unwind": "$transactions"},
                {"$match": {"transactions.inputs.0": {"$exists": True}}},
                {"$unwind": "$transactions.inputs"},
                {
                    "$project": {
                        "_id": 0,
                        "pk": "$transactions.public_key",
                        "input_id": "$transactions.inputs.id",
                    }
                },
            ],
            allowDiskUse=True,
        ):
            pk = doc.get("pk")
            input_id = doc.get("input_id")
            if pk and input_id:
                addr = pk_to_addr.get(pk)
                if addr:
                    spent_by_addr.setdefault(addr, set()).add(input_id)

        # Step 3: Sum unspent outputs from canonical blocks only.
        balances = {}
        async for doc in db.blocks.aggregate(
            DEDUP
            + [
                {"$unwind": "$transactions"},
                {"$unwind": "$transactions.outputs"},
                {
                    "$match": {
                        "transactions.outputs.value": {"$gt": 0},
                        "transactions.outputs.to": {
                            "$exists": True,
                            "$nin": [None, ""],
                        },
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "txn_id": "$transactions.id",
                            "to": "$transactions.outputs.to",
                        },
                        "value": {"$sum": "$transactions.outputs.value"},
                    }
                },
            ],
            allowDiskUse=True,
        ):
            txn_id = doc["_id"]["txn_id"]
            to_addr = doc["_id"]["to"]
            value = doc["value"]
            addr_spent = spent_by_addr.get(to_addr)
            if addr_spent is None or txn_id not in addr_spent:
                balances[to_addr] = balances.get(to_addr, 0) + value

        holders = sorted(
            [
                {"address": addr, "balance": round(bal, 8)}
                for addr, bal in balances.items()
                if bal > 0
            ],
            key=lambda x: x["balance"],
            reverse=True,
        )

        circulating_supply = round(sum(h["balance"] for h in holders), 8)
        result = {
            "holders": holders,
            "count": len(holders),
            "circulating_supply": circulating_supply,
        }
        self.config._holder_list_cache = {"time": time.time(), "data": result}
        return self.render_as_json(result)


EXPLORER_HANDLERS = [
    (r"/api-stats", HashrateAPIHandler),
    (r"/explorer", ExplorerHandler),
    (r"/explorer-search", ExplorerSearchHandler),
    (r"/explorer-get-balance", ExplorerGetBalance),
    (r"/explorer-latest", ExplorerLatestHandler),
    (r"/explorer-last50", ExplorerLast50),
    (r"/holders", HolderListPageHandler),
    (r"/api-holders", HolderListAPIHandler),
]
