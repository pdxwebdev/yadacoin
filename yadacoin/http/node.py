"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Handlers required by the core chain operations
"""

import json
import time
from datetime import datetime, timezone

from tornado import escape

from yadacoin.core.chain import CHAIN
from yadacoin.decorators.jwtauth import jwtauthwallet
from yadacoin.http.base import BaseHandler


class GetLatestBlockHandler(BaseHandler):
    async def get(self):
        """
        :return:
        """
        block = await self.config.LatestBlock.block.copy()
        self.render_as_json(block.to_dict())


class GetBlocksHandler(BaseHandler):
    async def get(self):
        # TODO: dup code between http route and websocket handlers. move to a .mongo method?
        start_index = int(self.get_argument("start_index", 0))
        # safety, add bound on block# to fetch
        end_index = min(
            int(self.get_argument("end_index", 0)),
            start_index + CHAIN.MAX_BLOCKS_PER_MESSAGE,
        )
        # global chain object with cache of current block height,
        # so we can instantly answer to pulling requests without any db request
        if start_index > self.config.LatestBlock.block.index:
            # early exit without request
            self.render_as_json([])
        else:
            blocks = self.config.mongo.async_db.blocks.find(
                {
                    "$and": [
                        {"index": {"$gte": start_index}},
                        {"index": {"$lte": end_index}},
                    ]
                },
                {"_id": 0},
            ).sort([("index", 1)])
            self.render_as_json(
                await blocks.to_list(length=CHAIN.MAX_BLOCKS_PER_MESSAGE)
            )


class GetBlockHandler(BaseHandler):
    async def get(self):
        """
        :return:
        """
        block_hash = self.get_argument("hash", None)
        block_index = self.get_argument("index", None)

        if block_hash:
            return self.render_as_json(
                await self.config.mongo.async_db.blocks.find_one(
                    {"hash": block_hash}, {"_id": 0}
                )
            )

        if block_index:
            return self.render_as_json(
                await self.config.mongo.async_db.blocks.find_one(
                    {"index": int(block_index)}, {"_id": 0}
                )
            )

        return self.render_as_json({})


class GetBlockHeightHandler(BaseHandler):
    async def get(self):
        block = self.config.LatestBlock.block
        self.render_as_json({"height": block.index, "hash": block.hash})


class GetPeersHandler(BaseHandler):
    async def get(self):
        """
        :return:
        """
        inbound_peers = await self.config.peer.get_all_inbound_streams()
        outbound_peers = await self.config.peer.get_all_outbound_streams()
        self.render_as_json(
            {
                "inbound_peers": [x.peer.to_dict() for x in inbound_peers],
                "outbound_peers": [x.peer.to_dict() for x in outbound_peers],
            },
            4,
        )


class GetStatusHandler(BaseHandler):
    async def get(self):
        """
        :return:
        """
        from_time = self.get_query_argument("from_time", None)
        archived = self.get_query_argument("archived", False)
        if from_time:
            status = self.config.mongo.async_db.node_status.find(
                {
                    "timestamp": {"$gte": int(time.time()) - int(from_time)},
                    "archived": {"$exists": bool(archived)},
                },
                {"_id": 0},
            )
            return self.render_as_json([x async for x in status], indent=4)
        status = await self.config.mongo.async_db.node_status.find_one(
            {"archived": {"$exists": bool(archived)}},
            {"_id": 0},
            sort=[("timestamp", -1)],
            hint="__timestamp_archived",
        )

        if status is None:
            status = {}

        status["unindexed_queries"] = {
            "count": await self.config.mongo.async_db.unindexed_queries.count_documents(
                {}
            ),
            "detail": [
                x
                async for x in self.config.mongo.async_db.unindexed_queries.find(
                    {}, {"_id": 0}
                )
            ],
        }
        self.render_as_json(status, indent=4)


class NewBlockHandler(BaseHandler):
    async def post(self):
        """
        A peer does notify us of a new block. This is deprecated, since the new code uses events via websocket to notify of a new block.
        Still, can be used to force notification to important nodes, pools...
        """
        from yadacoin.peers import Peer

        try:
            block_data = escape.json_decode(self.request.body)
            peer_string = block_data.get("peer")

            if block_data["index"] == 0:
                return
            if int(block_data["version"]) != self.config.BU.get_version_for_height(
                block_data["index"]
            ):
                print(
                    "rejected old version %s from %s"
                    % (block_data["version"], peer_string)
                )
                return
            # Dup code with websocket handler
            self.app_log.info(
                "Post new block: {} {}".format(peer_string, json.dumps(block_data))
            )
            # TODO: handle a dict here to store the consensus state
            if not self.peers.syncing:
                self.app_log.debug(
                    "Trying to sync on latest block from {}".format(peer_string)
                )
                my_index = self.config.LatestBlock.block.index
                # This is mostly to keep in sync with fast moving blocks from whitelisted peers and pools.
                # ignore if this does not fit.
                if block_data["index"] == my_index + 1:
                    self.app_log.debug(
                        "Next index, trying to merge from {}".format(peer_string)
                    )
                    peer = Peer.from_string(peer_string)
                    if await self.config.consensus.process_next_block(block_data, peer):
                        pass
                        # if ok, block was inserted and event triggered by import block
                        # await self.peers.on_block_insert(data)
                elif block_data["index"] > my_index + 1:
                    self.app_log.warning(
                        "Missing blocks between {} and {} , can't catch up from http route for {}".format(
                            my_index, block_data["index"], peer_string
                        )
                    )
                    # data = {"start_index": my_index + 1, "end_index": my_index + 1 + CHAIN.MAX_BLOCKS_PER_MESSAGE}
                    # await self.emit('get_blocks', data=data, room=sid)
                else:
                    # Remove later on
                    self.app_log.debug(
                        "Old or same index, ignoring {} from {}".format(
                            block_data["index"], peer_string
                        )
                    )

        except:
            print("ERROR: failed to get peers, exiting...")


class GetPendingTransactionHandler(BaseHandler):
    async def get(self):
        txn_id = self.get_query_argument("id", None).replace(" ", "+")
        if not txn_id:
            return self.render_as_json({})
        return self.render_as_json(
            await self.config.mongo.async_db.miner_transactions.find_one({"id": txn_id})
        )


class GetTransactionByPublicKeyHandler(BaseHandler):
    async def get(self):
        public_key = self.get_query_argument("public_key")
        if not public_key:
            return self.render_as_json({})

        txns = await self.config.mongo.async_db.blocks.aggregate(
            [
                {"$match": {"transactions.public_key": public_key}},
                {"$unwind": "$transactions"},
                {"$match": {"transactions.public_key": public_key}},
            ]
        ).to_list(length=1)
        if txns:
            return self.render_as_json(txns[0]["transactions"])

        txn = await self.config.mongo.async_db.miner_transactions.find_one(
            {"public_key": public_key}
        )
        if txn:
            txn["mempool"] = True
            return self.render_as_json(txn)

        return self.render_as_json({})


class GetPendingTransactionIdsHandler(BaseHandler):
    async def get(self):
        txns = await self.config.mongo.async_db.miner_transactions.find({}).to_list(
            length=100
        )
        return self.render_as_json({"txn_ids": [x["id"] for x in txns]})


class GetTransactionTrackingHandler(BaseHandler):
    async def get(self):
        """
        Retrieves transaction tracking data.

        - If `rid` is provided, returns tracking data only for that peer.
        - If `limit` is provided, returns only the latest N transactions per peer.
        - Otherwise, returns all transaction tracking data.
        """
        rid = self.get_query_argument("rid", None)
        limit = int(self.get_query_argument("limit", 500))

        query = {"rid": rid} if rid else {}

        transactions = await self.config.mongo.async_db.txn_tracking.find(
            query
        ).to_list(length=None)

        response = []

        for entry in transactions:
            formatted_transactions = []

            if "transactions" in entry:
                sorted_txn = sorted(
                    entry["transactions"].items(), key=lambda x: x[1], reverse=True
                )
                for txn_id, timestamp in sorted_txn[:limit]:
                    formatted_transactions.append(
                        {
                            "txn_id": txn_id,
                            "timestamp": datetime.fromtimestamp(
                                timestamp, tz=timezone.utc
                            ).strftime("%Y-%m-%d %H:%M:%S UTC"),
                        }
                    )

            response.append(
                {
                    "host": entry.get("host", "Unknown"),
                    "rid": entry["rid"],
                    "transactions": formatted_transactions,
                }
            )

        return self.render_as_json({"transaction_tracking": response})


class RebroadcastTransactions(BaseHandler):
    async def get(self):
        await self.config.TU.rebroadcast_mempool(self.config, send_to_all=True)
        return self.render_as_json({"status": "success"})


class RebroadcastFailedTransactions(BaseHandler):
    async def get(self):
        txn_id = self.get_query_argument("id").replace(" ", "+")
        await self.config.TU.rebroadcast_failed(self.config, txn_id)
        return self.render_as_json({"status": "success"})


class GetMempoolHandler(BaseHandler):
    async def get(self):
        page = int(self.get_query_argument("page", 1))
        page_size = min(int(self.get_query_argument("page_size", 25)), 100)
        skip = (page - 1) * page_size
        total = await self.config.mongo.async_db.miner_transactions.count_documents({})
        cursor = (
            self.config.mongo.async_db.miner_transactions.find({}, {"_id": 0})
            .sort([("fee", -1), ("time", 1)])
            .skip(skip)
            .limit(page_size)
        )
        txns = await cursor.to_list(length=page_size)
        return self.render_as_json(
            {
                "transactions": txns,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )


class GetMonitoringHandler(BaseHandler):
    async def get(self):
        # Node Data
        node_status = self.config.mongo.async_db.node_status.aggregate(
            [
                {"$sort": {"timestamp": -1}},
                {"$limit": 1},
                {
                    "$project": {
                        "_id": 0,
                        "message_sender": 0,
                        "slow_queries": 0,
                        "unindexed_queries": 0,
                        "transaction_tracker": 0,
                        "disconnect_tracker": 0,
                        "processing_queues": 0,
                    }
                },
            ],
            hint="__timestamp",
        )
        op_data = {
            "address": self.config.address,
        }
        node_data = [x async for x in node_status]
        if node_data:
            op_data["node"] = node_data[0]

        if hasattr(self.config, "peer"):
            # Peer Data
            inbound_peers = await self.config.peer.get_all_inbound_streams()
            outbound_peers = await self.config.peer.get_all_outbound_streams()

            peer_data = {
                "inbound_peers": [x.peer.to_dict() for x in inbound_peers],
                "outbound_peers": [x.peer.to_dict() for x in outbound_peers],
            }
            op_data["peers"] = peer_data

        # Pool Data Calcs
        await self.config.LatestBlock.block_checker()
        pool_public_key = (
            self.config.pool_public_key
            if hasattr(self.config, "pool_public_key")
            else self.config.public_key
        )
        mining_time_interval = 600
        shares_count = await self.config.mongo.async_db.shares.count_documents(
            {"time": {"$gte": time.time() - mining_time_interval}}, hint="__time"
        )
        if shares_count > 0:
            pool_hash_rate = (
                shares_count * self.config.pool_diff
            ) / mining_time_interval
        else:
            pool_hash_rate = 0

        pool_blocks_found_list = (
            await self.config.mongo.async_db.blocks.find(
                {"public_key": pool_public_key}, {"_id": 0, "time": 1, "index": 1}
            )
            .sort([("index", -1)])
            .to_list(5)
        )

        lbt = 0
        lbh = 0
        if pool_blocks_found_list:
            lbt = pool_blocks_found_list[0]["time"]
            lbh = pool_blocks_found_list[0]["index"]

        pool_data = {
            "hashes_per_second": pool_hash_rate,
            "last_block_time": lbt,
            "last_block_height": lbh,
            "fee": self.config.pool_take,
            "reward": CHAIN.get_block_reward(self.config.LatestBlock.block.index),
        }

        # Create output data
        op_data["pool"] = pool_data
        self.render_as_json(op_data, indent=4)


class GetTestedNodesHandler(BaseHandler):
    async def get(self):
        """Zwraca listę ostatnio przetestowanych węzłów."""
        result = await self.config.mongo.async_db.tested_nodes.find_one(
            {"_id": "latest_test"}, {"_id": 0}
        )

        if not result:
            return self.render_as_json(
                {"error": "No test results available."}, status=404
            )

        return self.render_as_json(result)


@jwtauthwallet
class MineBlockHandler(BaseHandler):
    async def get(self):
        pass

        self.get_argument("private_key", None)

        if private_key_param:
            # KEL-based authorization: derive public key and verify against latest KEL entry
            try:
                priv_bytes = bytes.fromhex(private_key_param)
                priv_obj = _CoincurvePrivateKey(priv_bytes)
                pub_bytes = priv_obj.public_key.format(compressed=True)
                pub_hex = pub_bytes.hex()
                address = str(P2PKHBitcoinAddress.from_pubkey(pub_bytes))
            except Exception:
                return self.render_as_json({"error": "invalid private_key parameter"})

            kel = await KeyEventLog.build_from_public_key(pub_hex)
            if not kel or kel[-1].public_key_hash != address:
                return self.render_as_json({"error": "not authorized"})

        else:
            if not await self.wallet_is_unlocked():
                return self.render_as_json({"error": "not authorized"})

        if self.config.network != "regnet":
            return self.render_as_json(
                {"status": False, "message": "Node not in regnet mode."}
            )
        if not self.config.mp or not self.config.mp.block_factory:
            return self.render_as_json(
                {"status": False, "message": "Mining pool not initialized."}
            )
        self.config.mp.block_factory.hash = (
            await self.config.mp.block_factory.generate_hash_from_header(
                self.config.mp.block_factory.index,
                self.config.mp.block_factory.header,
                "",
            )
        )

        self.config.mp.block_factory.signature = self.config.kel_manager._sign(
            self.config.mp.block_factory.private_key, self.config.mp.block_factory.hash
        )
        await self.config.mp.block_factory.verify()
        await self.config.mongo.async_db.blocks.insert_one(
            self.config.mp.block_factory.to_dict()
        )
        await self.config.mp.refresh()
        return self.render_as_json(
            {"status": True, "block": self.config.mp.block_factory.to_dict()}
        )


class GetNetworkTopologyHandler(BaseHandler):
    """Serves the network topology monitor page and its JSON data API."""

    async def get(self):
        fmt = self.get_query_argument("format", "html")
        if fmt == "json":
            await self._json_data()
        else:
            self.render("network_topology.html")

    async def _json_data(self):
        import asyncio

        import aiohttp

        # ── 1. Local tested-nodes (from NodesTester / MongoDB) ──────────────
        tested_result = await self.config.mongo.async_db.tested_nodes.find_one(
            {"_id": "latest_test"}, {"_id": 0}
        )
        successful_nodes = (
            tested_result.get("successful_nodes", []) if tested_result else []
        )

        # ── 2. Build initial node map from tested nodes ───────────────────────
        # Key: "<http_protocol>://<http_host>:<http_port>"
        nodes_map = {}  # id -> node dict

        def infer_proto(proto, port):
            if proto:
                return proto
            return "https" if str(port) in ("443", "8443") else "http"

        def node_id(n):
            port = n.get("http_port") or n.get("port", 80)
            proto = infer_proto(n.get("http_protocol"), port)
            host = n.get("http_host") or n.get("host", "")
            return f"{proto}://{host}:{port}"

        for n in successful_nodes:
            nid = node_id(n)
            # peer_type may be None if the node was created from a hardcoded dict
            # without a peer_type key — infer from seed/seed_gateway fields as fallback
            pt = n.get("peer_type") or None
            if not pt:
                if n.get("seed") and n.get("seed_gateway"):
                    pt = "service_provider"
                elif n.get("seed") and not n.get("seed_gateway"):
                    pt = "seed_gateway"
                else:
                    pt = "seed"  # tested_nodes only contains masternode-tier nodes
            nodes_map[nid] = {
                "id": nid,
                "host": n.get("http_host") or n.get("host", ""),
                "port": n.get("http_port") or n.get("port"),
                "http_protocol": infer_proto(
                    n.get("http_protocol"), n.get("http_port") or n.get("port", 80)
                ),
                "peer_type": pt,
                "username": (n.get("identity") or {}).get("username", ""),
                "username_signature": (n.get("identity") or {}).get(
                    "username_signature", ""
                ),
                "node_version": n.get("node_version"),
                "protocol_version": n.get("protocol_version"),
                "seed": n.get("seed"),
                "seed_gateway": n.get("seed_gateway"),
                "status": None,  # enriched below
                "height": None,
                "uptime": None,
                "inbound_peers": None,
                "outbound_peers": None,
            }

        # ── 3. Add self node ──────────────────────────────────────────────────
        self_status = await self.config.get_status()
        my_proto = (
            "https"
            if (hasattr(self.config, "ssl") and self.config.ssl.is_valid())
            else "http"
        )
        my_host = (
            (self.config.ssl.common_name if hasattr(self.config, "ssl") else None)
            or self.config.peer_host
            or "localhost"
        )
        my_port = (
            (self.config.ssl.port if hasattr(self.config, "ssl") else None)
            or self.config.serve_port
            or 8000
        )
        self_id = f"{my_proto}://{my_host}:{my_port}"
        self_peer_type = getattr(self.config, "peer_type", "user")

        nodes_map[self_id] = {
            "id": self_id,
            "host": my_host,
            "port": my_port,
            "http_protocol": my_proto,
            "peer_type": self_peer_type,
            "username": getattr(self.config, "username", ""),
            "node_version": self_status.get("version"),
            "protocol_version": self_status.get("protocol_version"),
            "seed": None,
            "seed_gateway": None,
            "status": "online",
            "height": self_status.get("height"),
            "uptime": self_status.get("uptime"),
            "network": self_status.get("network"),
            "inbound_peers": self_status.get("inbound_peers"),
            "outbound_peers": self_status.get("outbound_peers"),
            "is_self": True,
        }

        # ── 4. Fetch /get-status from each remote masternode-tier node ────────
        MASTERNODE_TYPES = {"seed", "seed_gateway", "service_provider"}
        timeout = aiohttp.ClientTimeout(total=5)

        async def fetch_status(nid, n):
            proto = n["http_protocol"]
            host = n["host"]
            port = n["port"]
            url = f"{proto}://{host}:{port}/get-status"
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, ssl=False) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            n["status"] = "online"
                            n["height"] = data.get("height")
                            n["uptime"] = data.get("uptime")
                            n["network"] = data.get("network")
                            n["inbound_peers"] = data.get("inbound_peers")
                            n["outbound_peers"] = data.get("outbound_peers")
                            if data.get("version"):
                                n["node_version"] = data.get("version")
                            if data.get("username"):
                                n["username"] = data.get("username")
                            if data.get("peer_type"):
                                n["peer_type"] = data.get("peer_type")
                        else:
                            n["status"] = "degraded"
            except Exception:
                n["status"] = "unreachable"

        async def fetch_peers(nid, n):
            proto = n["http_protocol"]
            host = n["host"]
            port = n["port"]
            url = f"{proto}://{host}:{port}/get-peers"
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, ssl=False) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            inbound = data.get("inbound_peers", [])
                            outbound = data.get("outbound_peers", [])
                            return nid, inbound + outbound
            except Exception:
                pass
            return nid, []

        # ── 4a. BFS crawl: keep fetching /get-peers from every newly discovered
        #        masternode-tier node until the frontier is empty ─────────────
        edges = []
        crawled = set()  # nids whose /get-peers we've already fetched

        def make_node_entry(p):
            pt = p.get("peer_type", "user")
            ph = p.get("http_host") or p.get("host", "")
            pp = p.get("http_port") or p.get("port", 80)
            pproto = infer_proto(p.get("http_protocol"), pp)
            pid = f"{pproto}://{ph}:{pp}"
            return (
                pid,
                ph,
                {
                    "id": pid,
                    "host": ph,
                    "port": pp,
                    "http_protocol": pproto,
                    "peer_type": pt,
                    "username": p.get("identity", {}).get("username", ""),
                    "username_signature": p.get("identity", {}).get(
                        "username_signature", ""
                    ),
                    "node_version": p.get("node_version"),
                    "protocol_version": p.get("protocol_version"),
                    "seed": p.get("seed"),
                    "seed_gateway": p.get("seed_gateway"),
                    "status": "online",
                    "height": None,
                    "uptime": None,
                },
            )

        # Start with ALL non-self nodes from tested_nodes — they are always
        # masternode-tier; peer_type may still be None for some until fetch_status
        # returns the live value, so don't filter by peer_type here.
        frontier = {nid: n for nid, n in nodes_map.items() if not n.get("is_self")}

        while frontier:
            # Fetch /get-status and /get-peers for all nodes in the current frontier
            await asyncio.gather(*[fetch_status(nid, n) for nid, n in frontier.items()])
            peer_results = await asyncio.gather(
                *[fetch_peers(nid, n) for nid, n in frontier.items()]
            )
            crawled.update(frontier.keys())

            next_frontier = {}
            for source_nid, peers in peer_results:
                for p in peers:
                    pid, ph, entry = make_node_entry(p)
                    if not ph:
                        continue
                    # Add to nodes_map if not seen before
                    if pid not in nodes_map:
                        nodes_map[pid] = entry
                    # If it's a masternode-tier node we haven't crawled yet, add to next frontier
                    if (
                        entry["peer_type"] in MASTERNODE_TYPES
                        and pid not in crawled
                        and pid not in next_frontier
                    ):
                        next_frontier[pid] = nodes_map[pid]
                    edges.append({"source": source_nid, "target": pid})

            frontier = next_frontier

        # ── 5. Add self edges from local /get-peers ───────────────────────────
        if hasattr(self.config, "peer"):
            inbound = await self.config.peer.get_all_inbound_streams()
            outbound = await self.config.peer.get_all_outbound_streams()
            for stream in inbound:
                p = stream.peer
                ph = p.http_host or p.host or ""
                pp = p.http_port or p.port or 80
                pproto = infer_proto(p.http_protocol, pp)
                pid = f"{pproto}://{ph}:{pp}"
                if ph:
                    edges.append({"source": self_id, "target": pid})
            for stream in outbound:
                p = stream.peer
                ph = p.http_host or p.host or ""
                pp = p.http_port or p.port or 80
                pproto = infer_proto(p.http_protocol, pp)
                pid = f"{pproto}://{ph}:{pp}"
                if ph:
                    edges.append({"source": self_id, "target": pid})

        # Deduplicate edges (same source+target)
        seen_edges = set()
        unique_edges = []
        for e in edges:
            key = (e["source"], e["target"])
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(e)

        # ── 5b. Deduplicate nodes that represent the same host ────────────────
        # Build a canonical-id map keyed by (host, port) — prefer the entry with
        # the most data (status online, highest port specificity).
        # username_signature is the true unique identity; use it when available.
        host_canonical = {}  # (host, port) -> canonical nid
        sig_canonical = {}  # username_signature -> canonical nid

        def _score(n):
            """Higher = more complete/preferred entry."""
            return (
                1 if n.get("status") == "online" else 0,
                1 if n.get("username_signature") else 0,
                1 if n.get("username") else 0,
                1 if n.get("height") is not None else 0,
            )

        for nid, n in list(nodes_map.items()):
            sig = n.get("username_signature") or ""
            host = n.get("host", "")
            port = n.get("port")
            hk = (host, port)

            # Check if we already have a canonical entry for this sig or host:port
            existing_nid = sig_canonical.get(sig) if sig else None
            if not existing_nid:
                existing_nid = host_canonical.get(hk)

            if existing_nid and existing_nid != nid:
                # Merge: keep the better-scored entry as canonical, remap the other
                existing = nodes_map[existing_nid]
                if _score(n) > _score(existing):
                    # current entry is better — make it canonical, remap existing
                    nodes_map[nid] = n
                    del nodes_map[existing_nid]
                    # update remapping for old id
                    if sig:
                        sig_canonical[sig] = nid
                    host_canonical[hk] = nid
                    # rewrite edges that pointed to old id
                    for e in unique_edges:
                        if e["source"] == existing_nid:
                            e["source"] = nid
                        if e["target"] == existing_nid:
                            e["target"] = nid
                else:
                    # existing entry is better — remap current to existing
                    del nodes_map[nid]
                    for e in unique_edges:
                        if e["source"] == nid:
                            e["source"] = existing_nid
                        if e["target"] == nid:
                            e["target"] = existing_nid
            else:
                if sig:
                    sig_canonical[sig] = nid
                host_canonical[hk] = nid

        # Remove self-loop edges and re-deduplicate after remapping
        seen_edges = set()
        final_edges = []
        for e in unique_edges:
            if e["source"] == e["target"]:
                continue
            key = (e["source"], e["target"])
            if key not in seen_edges:
                seen_edges.add(key)
                final_edges.append(e)
        unique_edges = final_edges

        # ── 6. Build ontology tree ────────────────────────────────────────────        # Hierarchy: Seed -> SeedGateway -> ServiceProvider -> User/Pool
        def peer_tier(pt):
            return {
                "seed": 0,
                "seed_gateway": 1,
                "service_provider": 2,
                "pool": 3,
                "user": 3,
            }.get(pt, 3)

        ontology = {"name": "YadaCoin Network", "peer_type": "root", "children": []}
        tier_nodes = {0: [], 1: [], 2: [], 3: []}
        for nid, n in nodes_map.items():
            tier_nodes[peer_tier(n.get("peer_type", "user"))].append(n)

        for seed in tier_nodes[0]:
            seed_node = {
                "name": seed["username"] or seed["host"],
                "id": seed["id"],
                "peer_type": "seed",
                "children": [],
            }
            for gw in tier_nodes[1]:
                if gw.get("seed") == seed.get("username_signature"):
                    gw_node = {
                        "name": gw["username"] or gw["host"],
                        "id": gw["id"],
                        "peer_type": "seed_gateway",
                        "children": [],
                    }
                    for sp in tier_nodes[2]:
                        if sp.get("seed_gateway") == gw.get("username_signature"):
                            sp_node = {
                                "name": sp["username"] or sp["host"],
                                "id": sp["id"],
                                "peer_type": "service_provider",
                                "children": [],
                            }
                            gw_node["children"].append(sp_node)
                    seed_node["children"].append(gw_node)
            ontology["children"].append(seed_node)

        # Drop any edges whose source or target was removed during deduplication
        known_ids = set(nodes_map.keys())
        unique_edges = [
            e
            for e in unique_edges
            if e["source"] in known_ids and e["target"] in known_ids
        ]

        return self.render_as_json(
            {
                "nodes": list(nodes_map.values()),
                "edges": unique_edges,
                "ontology": ontology,
                "self_id": self_id,
                "generated_at": time.time(),
            }
        )


NODE_HANDLERS = [
    (r"/get-latest-block", GetLatestBlockHandler),
    (r"/get-blocks", GetBlocksHandler),
    (r"/get-block", GetBlockHandler),
    (r"/get-height|/getheight", GetBlockHeightHandler),
    (r"/get-peers", GetPeersHandler),
    (r"/newblock", NewBlockHandler),
    (r"/get-status", GetStatusHandler),
    (r"/get-pending-transaction", GetPendingTransactionHandler),
    (
        r"/get-transaction-by-public-key",
        GetTransactionByPublicKeyHandler,
    ),
    (r"/get-pending-transaction-ids", GetPendingTransactionIdsHandler),
    (r"/get-transaction-tracking", GetTransactionTrackingHandler),
    (r"/rebroadcast-transactions", RebroadcastTransactions),
    (r"/rebroadcast-failed-transaction", RebroadcastFailedTransactions),
    (r"/get-mempool", GetMempoolHandler),
    (r"/get-monitoring", GetMonitoringHandler),
    (r"/get-tested-nodes", GetTestedNodesHandler),
    (r"/network-topology", GetNetworkTopologyHandler),
    (r"/mine-block", MineBlockHandler),
]
