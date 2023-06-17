"""
Handlers required by the core chain operations
"""

import json
from time import sleep, time
from tornado import escape

from yadacoin.http.base import BaseHandler
from yadacoin.core.common import ts_to_utc
from yadacoin.core.chain import CHAIN
from yadacoin.core.transaction import Transaction
from yadacoin.core.transactionutils import TU


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
        peers = await self.config.peer.get_all_streams()
        self.render_as_json({"peers": [x.peer.to_dict() for x in peers]})


class GetStatusHandler(BaseHandler):
    async def get(self):
        """
        :return:
        """
        # TODO: complete and cache
        status = await self.config.get_status()
        status["health"] = self.config.health.to_dict()
        status["latest_block"] = self.config.LatestBlock.block.to_dict()
        status["queues"] = self.config.processing_queues.to_status_dict()
        status["message_sender"] = {
            "nodeServer": {
                "num_messages": len(list(self.config.nodeServer.retry_messages))
            },
            "nodeClient": {
                "num_messages": len(list(self.config.nodeClient.retry_messages))
            },
        }
        status["slow_queries"] = {
            "count": len(self.config.mongo.async_db.slow_queries),
            "detail": self.config.mongo.async_db.slow_queries,
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
            self.config.mongo.async_db.miner_transactions.find_one({"id": txn_id})
        )


class GetPendingTransactionIdsHandler(BaseHandler):
    async def get(self):
        txns = await self.config.mongo.async_db.miner_transactions.find({}).to_list(
            length=100
        )
        return self.render_as_json({"txn_ids": [x["id"] for x in txns]})


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


NODE_HANDLERS = [
    (r"/get-latest-block", GetLatestBlockHandler),
    (r"/get-blocks", GetBlocksHandler),
    (r"/get-block", GetBlockHandler),
    (r"/get-height|/getheight", GetBlockHeightHandler),
    (r"/get-peers", GetPeersHandler),
    (r"/newblock", NewBlockHandler),
    (r"/get-status", GetStatusHandler),
    (r"/get-pending-transaction", GetPendingTransactionHandler),
    (r"/get-pending-transaction-ids", GetPendingTransactionIdsHandler),
    (r"/rebroadcast-transactions", RebroadcastTransactions),
    (r"/rebroadcast-failed-transaction", RebroadcastFailedTransactions),
    (r"/get-current-smart-contract-transactions", GetCurrentSmartContractTransactions),
    (r"/get-current-smart-contract-transaction", GetCurrentSmartContractTransaction),
    (r"/get-expired-smart-contract-transactions", GetExpiredSmartContractTransactions),
    (r"/get-expired-smart-contract-transaction", GetExpiredSmartContractTransaction),
    (r"/get-trigger-transactions", GetSmartContractTriggerTransaction),
]
