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
from yadacoin.core.transaction import Transaction
from yadacoin.core.transactionutils import TU
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
        txn = await self.config.mongo.async_db.miner_transactions.find_one(
            {"public_key": public_key}
        )
        if txn:
            txn["mempool"] = True
            return self.render_as_json(txn)

        txns = await self.config.mongo.async_db.blocks.aggregate(
            [
                {"$match": {"transactions.public_key": public_key}},
                {"$unwind": "$transactions"},
                {"$match": {"transactions.public_key": public_key}},
            ]
        ).to_list(length=1)
        if txns:
            return self.render_as_json(txns[0]["transactions"])

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
        await self.config.TU.rebroadcast_mempool(self.config)
        return self.render_as_json({"status": "success"})


class RebroadcastFailedTransactions(BaseHandler):
    async def get(self):
        txn_id = self.get_query_argument("id").replace(" ", "+")
        await self.config.TU.rebroadcast_failed(self.config, txn_id)
        return self.render_as_json({"status": "success"})


class GetCurrentSmartContractTransactions(BaseHandler):
    async def get(self):
        return self.render_as_json({"txn_ids": [x["id"] for x in txns]})


class GetCurrentSmartContractTransaction(BaseHandler):
    async def get(self):
        return self.render_as_json({"txn_ids": [x["id"] for x in txns]})


class GetExpiredSmartContractTransactions(BaseHandler):
    async def get(self):
        return self.render_as_json({"txn_ids": [x["id"] for x in txns]})


class GetExpiredSmartContractTransaction(BaseHandler):
    async def get(self):
        return self.render_as_json({"txn_ids": [x["id"] for x in txns]})


class GetSmartContractTriggerTransaction(BaseHandler):
    async def get(self):
        txn_id = self.get_query_argument("id", None).replace(" ", "+")
        start_index = self.get_query_argument("start_index", None)
        end_index = self.get_query_argument("end_index", None)
        smart_contracts = self.config.mongo.async_db.blocks.aggregate(
            [
                {"$match": {"transactions.id": txn_id}},
                {"$unwind": "$transactions"},
                {"$match": {"transactions.id": txn_id}},
                {"$sort": {"transactions.time": -1}},
            ]
        )
        smart_contract = None
        async for smart_contract in smart_contracts:
            break
        if not smart_contract:
            self.status_code = 404
            return self.render_as_json({"status": False, "message": "not found"})
        smart_contract_txn = Transaction.from_dict(smart_contract["transactions"])
        trigger_txns = []
        async for trigger_txn in TU.get_trigger_txns(
            self.config, smart_contract_txn, start_index, end_index
        ):
            trigger_txns.append(Transaction.from_dict(trigger_txn).to_dict())
        return self.render_as_json({"transactions": trigger_txns})


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
    (r"/get-current-smart-contract-transactions", GetCurrentSmartContractTransactions),
    (r"/get-current-smart-contract-transaction", GetCurrentSmartContractTransaction),
    (r"/get-expired-smart-contract-transactions", GetExpiredSmartContractTransactions),
    (r"/get-expired-smart-contract-transaction", GetExpiredSmartContractTransaction),
    (r"/get-trigger-transactions", GetSmartContractTriggerTransaction),
    (r"/get-monitoring", GetMonitoringHandler),
    (r"/get-tested-nodes", GetTestedNodesHandler),
]
