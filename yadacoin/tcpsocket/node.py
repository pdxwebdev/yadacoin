"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import base64
import time
from uuid import uuid4

from coincurve import verify_signature
from tornado.iostream import StreamClosedError

from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.keyeventlog import (
    KELExceptionPredecessorNotYetInMempool,
    KELExceptionPreviousKeyHashReferenceMissing,
    KELLogUnbuildableException,
)
from yadacoin.core.peer import (
    Group,
    Peer,
    Pool,
    Seed,
    SeedGateway,
    ServiceProvider,
    User,
)
from yadacoin.core.processingqueue import (
    BlockProcessingQueueItem,
    TransactionProcessingQueueItem,
)
from yadacoin.core.transaction import MissingInputTransactionException, Transaction
from yadacoin.core.transactionutils import TU
from yadacoin.enums.modes import MODES
from yadacoin.enums.peertypes import PEER_TYPES
from yadacoin.tcpsocket.base import (
    BaseRPC,
    ProtocolVersionTooLowError,
    RPCSocketClient,
    RPCSocketServer,
    SessionCipher,
)


class NodeServerDisconnectTracker:
    by_host = {}
    by_reason = {}

    def to_dict(self):
        return {"by_host": self.by_host, "by_reason": self.by_reason}


class NodeServerNewTxnTracker:
    by_host = {}

    def to_dict(self):
        return {"by_host": self.by_host}


class NodeClientDisconnectTracker:
    by_host = {}
    by_reason = {}

    def to_dict(self):
        return {"by_host": self.by_host, "by_reason": self.by_reason}


class NodeClientNewTxnTracker:
    by_host = {}

    def to_dict(self):
        return {"by_host": self.by_host}


class NodeRPC(BaseRPC):
    retry_messages = {}

    def __init__(self):
        super(NodeRPC, self).__init__()
        self.config = Config()

    config = None

    async def _get_pending_inception(self) -> dict:
        """Return this node's pending KEL inception transaction dict if it
        exists in the local mempool but is not yet confirmed on-chain, or
        None if the inception is already mined (peers will have it via blocks).
        Used to break the bootstrapping deadlock: new nodes embed their
        inception in the plaintext connect/challenge so peers can accept them
        before the inception is gossiped any other way.
        """
        manager = getattr(self.config, "kel_manager", None)
        if not manager or not manager._inception_txn_id:
            return None
        # Only send if inception is NOT yet confirmed (no need to re-send once mined)
        if getattr(manager, "_inception_complete", False):
            return None
        doc = await self.config.mongo.async_db.miner_transactions.find_one(
            {"id": manager._inception_txn_id}, {"_id": 0}
        )
        return doc  # may be None if already moved to blocks

    async def _accept_peer_inception(self, txn_dict: dict) -> None:
        """Receive and store a peer's pending inception transaction.

        Verifies the transaction's self-consistency (public_key signed hash)
        without requiring the blockchain, then upserts into the local mempool.
        This is safe to call before authentication because the signature check
        is self-contained: it only proves the sender controls the key embedded
        in the transaction, which is exactly what the KEL lookup needs.
        """
        if not txn_dict or not isinstance(txn_dict, dict):
            return
        try:
            from yadacoin.core.transaction import Transaction

            txn = Transaction.from_dict(txn_dict)
            # Self-consistency check: transaction_signature must verify against
            # the transaction's own hash using the transaction's own public_key.
            sig_ok = verify_signature(
                base64.b64decode(txn.transaction_signature),
                txn.hash.encode("utf-8"),
                bytes.fromhex(txn.public_key),
            )
            if not sig_ok:
                self.config.app_log.warning(
                    "NodeRPC: rejected peer inception — invalid transaction signature"
                )
                return
            await self.config.mongo.async_db.miner_transactions.replace_one(
                {"id": txn.transaction_signature}, txn.to_dict(), upsert=True
            )
            self.config.app_log.info(
                "Bootstrap: accepted peer inception txn %s into mempool.\n"
                "  This allows the peer to authenticate even after the KEL fork —\n"
                "  the inception was delivered in the plaintext connect handshake\n"
                "  before encryption.",
                txn.transaction_signature[:24],
            )
        except Exception as exc:
            self.config.app_log.debug(
                "NodeRPC: could not accept peer inception: %s", exc
            )

    async def getblocks(self, body, stream):
        # get blocks should be done only by syncing peers
        params = body.get("params")
        start_index = int(params.get("start_index", 0))
        end_index = min(
            int(params.get("end_index", 0)), start_index + CHAIN.MAX_BLOCKS_PER_MESSAGE
        )
        blocks = self.config.mongo.async_db.blocks.find(
            {
                "$and": [
                    {"index": {"$gte": start_index}},
                    {"index": {"$lte": end_index}},
                ]
            },
            {"_id": 0},
        ).sort([("index", 1)])
        result = await blocks.to_list(length=CHAIN.MAX_BLOCKS_PER_MESSAGE)

        message = {"blocks": result, "start_index": start_index}
        await self.write_result(stream, "blocksresponse", message, body["id"])
        if stream.peer.protocol_version > 1:
            self.retry_messages[
                (stream.peer.rid, "blocksresponse", start_index, body["id"])
            ] = message

    async def service_provider_request(self, body, stream):
        payload = body.get("params", {})
        if not payload.get("seed_gateway"):
            return
        seed_gateway = SeedGateway.from_dict(payload.get("seed_gateway"))
        if (
            self.config.peer.__class__ == SeedGateway
            and self.config.peer.identity.username_signature
            == seed_gateway.identity.username_signature
        ):
            service_provider = None
            for x, service_provider in self.config.nodeServer.inbound_streams[
                ServiceProvider.__name__
            ].items():
                break

            if not service_provider:
                return
            payload[
                service_provider.peer.source_property
            ] = service_provider.peer.to_dict()
            scheme = "wss" if service_provider.peer.http_protocol == "https" else "ws"
            payload[service_provider.peer.source_property][
                "websocket_host"
            ] = f"{scheme}://{service_provider.peer.http_host}:{service_provider.peer.http_port}"
            return await self.write_params(stream, "service_provider_request", payload)
        payload2 = payload.copy()
        payload2.setdefault(
            self.config.peer.source_property, self.config.peer.to_dict()
        )
        async for peer_stream in self.config.peer.get_service_provider_request_peers(
            stream.peer, payload
        ):
            try:
                await self.write_params(
                    peer_stream, "service_provider_request", payload2
                )
            except:
                await peer_stream.write_params("service_provider_request", payload2)

    async def newtxn(self, body, stream):
        """
        Handles incoming new transactions and ensures they are valid before processing.

        - Verifies if the transaction already exists in the mempool to prevent duplicates.
        - Checks for double-spending by ensuring none of the transaction inputs have been used before.
        - Tracks incoming transactions per host and transaction ID for monitoring.
        - Immediately stores the sender in `txn_tracking` to prevent re-sending the transaction to them.
        - Adds the transaction to the processing queue if all validations pass.
        - If the transaction involves a known WebSocket user, forwards it to the appropriate peer.

        ### Protocol version handling:
        - `protocol_version > 2`: The node confirms transactions by returning the full transaction payload.
        - `protocol_version > 3`: The node optimizes transaction confirmation by returning only `transaction_id`.

        The method ensures efficient transaction propagation across the network while reducing unnecessary database queries.
        """
        payload = body.get("params", {})
        transaction = payload.get("transaction")
        txn = None

        if transaction:
            txn = Transaction.from_dict(transaction)
        elif payload.get("hash"):
            txn = Transaction.from_dict(payload)

        if txn is None:
            self.config.app_log.info(
                "[NEW_TXN] No valid transaction received, ignoring request."
            )
            return

        txn_id = txn.transaction_signature

        if stream.peer.protocol_version > 3:
            await self.write_result(
                stream, "newtxn_confirmed", {"transaction_id": txn_id}, body["id"]
            )
        elif stream.peer.protocol_version > 2:
            await self.write_result(
                stream, "newtxn_confirmed", {"transaction": txn.to_dict()}, body["id"]
            )

        await self.config.mongo.async_db.txn_tracking.update_one(
            {"rid": stream.peer.rid},
            {
                "$set": {
                    "host": stream.peer.host,
                    f"transactions.{txn_id}": int(time.time()),
                }
            },
            upsert=True,
        )

        existing_txn = await self.config.mongo.async_db.miner_transactions.find_one(
            {"id": txn_id}
        )
        if existing_txn:
            self.config.app_log.warning(
                f"Transaction {txn_id} already in mempool! Ignoring."
            )
            return

        input_ids = [input_item.id for input_item in txn.inputs]
        existing_input_txn = (
            await self.config.mongo.async_db.miner_transactions.find_one(
                {"public_key": txn.public_key, "inputs.id": {"$in": input_ids}}
            )
        )
        if existing_input_txn:
            self.config.app_log.warning(
                f"Duplicate transaction detected for {txn_id}! Ignoring."
            )
            return

        if (
            self.config.LatestBlock.block.index >= CHAIN.XEGGEX_HACK_FORK
            and self.config.LatestBlock.block.index < CHAIN.CHECK_KEL_FORK
        ) or (self.config.LatestBlock.block.index >= CHAIN.XEGGEX_HACK_FORK_2):
            remove = False
            if (
                txn.public_key
                == "02fd3ad0e7a613672d9927336d511916e15c507a1fab225ed048579e9880f15fed"
            ):
                remove = True
            if not remove:
                for output in txn.outputs:
                    if output.to == "1Kh8tcPNxJsDH4KJx4TzLbqWwihDfhFpzj":
                        remove = True
                        break
            if remove:
                self.config.app_log.info(
                    f"New txn rejected: Xeggex wallet has been frozen."
                )
                return

        self.newtxn_tracker.by_host[stream.peer.host] = (
            self.newtxn_tracker.by_host.get(stream.peer.host, 0) + 1
        )

        self.config.processing_queues.transaction_queue.add(
            TransactionProcessingQueueItem(txn, stream)
        )

        await self.config.notifier.notify_new_transaction(txn)

        if MODES.WEB.value not in self.config.modes:
            return

        ws_users = self.config.websocketServer.inbound_streams[User.__name__]

        peer_stream = None
        if txn.requested_rid in ws_users:
            peer_stream = ws_users[txn.requested_rid]

        if txn.requester_rid in ws_users:
            peer_stream = ws_users[txn.requester_rid]

        if txn.rid in ws_users:
            peer_stream = ws_users[txn.rid]

        for output in txn.outputs:
            if output.to in ws_users:
                peer_stream = ws_users[output.to]

        if peer_stream:
            await peer_stream.newtxn(body, source="tcpsocket")

    async def process_transaction_queue(self):
        mempool_transactions = [
            Transaction.from_dict(txn)
            async for txn in self.config.mongo.async_db.miner_transactions.find(
                {"relationship.smart_contract": {"$exists": False}}
            )
            .sort([("fee", -1), ("time", 1)])
            .limit(1000)
        ]

        transactions = [
            x.transaction
            for x in self.config.processing_queues.transaction_queue.queue.values()
        ] + mempool_transactions

        if (
            self.config.LatestBlock.block.index + 1
            >= CHAIN.ALLOW_SAME_BLOCK_SPENDING_FORK
        ):
            items_indexed = {x.transaction_signature: x for x in transactions}
            for txn in transactions:
                for input_item in txn.inputs:
                    if input_item.id in items_indexed:
                        input_item.input_txn = items_indexed[input_item.id]
                        items_indexed[input_item.id].spent_in_txn = txn

        item = self.config.processing_queues.transaction_queue.pop()
        i = 0  # max loops
        to_retry = []
        while item:
            if item.retry_time and item.retry_time < int(time.time()):
                to_retry.append(item)
                item = self.config.processing_queues.transaction_queue.pop()
                if not item:
                    break
            self.config.processing_queues.transaction_queue.inc_num_items_processed()
            await self.process_transaction_queue_item(item)

            i += 1
            if i >= 100:
                self.config.app_log.info(
                    "process_transaction_queue: max loops exceeded, exiting"
                )
                return

            item = self.config.processing_queues.transaction_queue.pop()

        if hasattr(self.config, "transaction_retry_seconds"):
            transaction_retry_seconds = self.config.transaction_retry_seconds
        else:
            transaction_retry_seconds = 60
        for retry_item in to_retry:
            self.config.processing_queues.transaction_queue.add(
                TransactionProcessingQueueItem(
                    retry_item.transaction,
                    retry_item.stream,
                    int(time.time()) + transaction_retry_seconds,
                ),
                ignore_last_popped=True,
            )

    async def process_transaction_queue_item(self, item):
        """
        Processes each transaction from the queue, verifies it, and propagates it to unconfirmed peers.

        - Runs transaction verification with the latest validation rules.
        - Stores the transaction in `miner_transactions` if valid.
        - Checks `txn_tracking` in MongoDB to avoid sending to already confirmed peers.
        - Sends transaction to inbound and outbound peers who have not yet confirmed it.
        """
        txn = item.transaction

        # Reject any externally-submitted transaction claiming to be a coinbase.
        # Coinbase transactions are generated exclusively by the block builder and
        # must never enter the mempool.  Allowing them in would let a malicious
        # peer bypass Transaction.verify()'s input/output balance check (which
        # returns early for coinbase) and pollute the mempool, causing miners to
        # build invalid blocks (coinbase_count != 1 failure in Block.verify()).
        if txn.coinbase:
            self.config.app_log.warning(
                f"Rejecting coinbase transaction submitted to mempool: {txn.transaction_signature}"
            )
            return

        check_max_inputs = False
        if self.config.LatestBlock.block.index > CHAIN.CHECK_MAX_INPUTS_FORK:
            check_max_inputs = True

        check_masternode_fee = False
        if self.config.LatestBlock.block.index >= CHAIN.CHECK_MASTERNODE_FEE_FORK:
            check_masternode_fee = True

        check_kel = False
        if self.config.LatestBlock.block.index >= CHAIN.CHECK_KEL_FORK:
            check_kel = True

        check_dynamic_nodes = False
        if self.config.LatestBlock.block.index >= CHAIN.DYNAMIC_NODES_FORK:
            check_dynamic_nodes = True

        try:
            await txn.verify(
                check_input_spent=True,
                check_max_inputs=check_max_inputs,
                check_masternode_fee=check_masternode_fee,
                check_kel=check_kel,
                check_dynamic_nodes=check_dynamic_nodes,
                mempool=True,
            )
        except (
            MissingInputTransactionException,
            KELExceptionPredecessorNotYetInMempool,
            KELExceptionPreviousKeyHashReferenceMissing,
            KELLogUnbuildableException,
        ):
            # Transient: prerequisite txn may not have arrived yet. Store in mempool so
            # it is available once the prerequisite is present (same behaviour as local node).
            self.config.app_log.warning(
                f"process_transaction_queue_item, transient error — holding in mempool: {txn.transaction_signature}"
            )
            await self.config.mongo.async_db.miner_transactions.replace_one(
                {"id": txn.transaction_signature}, txn.to_dict(), upsert=True
            )
            return
        except Exception as e:
            await Transaction.handle_exception(e, txn)
            return

        if self.config.LatestBlock.block.index >= CHAIN.TXN_V3_FORK:
            if not hasattr(txn, "version"):
                return
            if int(txn.version) < 3:
                return

        if await self.config.mongo.async_db.blocks.find_one(
            {"transactions.id": txn.transaction_signature}
        ):
            return

        await self.config.mongo.async_db.miner_transactions.replace_one(
            {"id": txn.transaction_signature}, txn.to_dict(), upsert=True
        )

        confirmed_peers = await self.config.mongo.async_db.txn_tracking.find(
            {f"transactions.{txn.transaction_signature}": {"$exists": True}}
        ).to_list(length=None)

        confirmed_rids = {peer["rid"] for peer in confirmed_peers}

        async def make_gen(streams):
            for stream in streams:
                yield stream

        payload = {"transaction": txn.to_dict()}

        async for peer_stream in self.config.peer.get_inbound_streams():
            if peer_stream.peer.rid in confirmed_rids:
                self.config.app_log.debug(
                    f"Skipping {peer_stream.peer.rid} - already confirmed."
                )
                continue
            await self.write_params(peer_stream, "newtxn", payload)
            if peer_stream.peer.protocol_version > 1:
                self.retry_messages[
                    (peer_stream.peer.rid, "newtxn", txn.transaction_signature)
                ] = payload

        async for peer_stream in make_gen(
            await self.config.peer.get_outbound_streams()
        ):
            if peer_stream.peer.rid in confirmed_rids:
                self.config.app_log.debug(
                    f"Skipping {peer_stream.peer.rid} - already confirmed."
                )
                continue
            await self.write_params(peer_stream, "newtxn", payload)
            if peer_stream.peer.protocol_version > 1:
                self.config.nodeClient.retry_messages[
                    (peer_stream.peer.rid, "newtxn", txn.transaction_signature)
                ] = payload

    async def newtxn_confirmed(self, body, stream):
        """
        Handles transaction confirmation received from a peer.

        - Extracts the confirmed transaction ID from the response.
        - Supports both protocol versions:
          - If `protocol_version > 3`, confirmation contains only `transaction_id`.
          - If `protocol_version > 2`, confirmation contains full transaction data.
        - Removes the transaction from the retry queue if it was previously pending.
        - Marks the peer as a confirmed receiver of the transaction to avoid redundant processing.

        This method ensures efficient tracking of confirmed transactions and prevents unnecessary retransmissions.
        """

        result = body.get("result", {})

        txn_id = result.get("transaction_id")

        if txn_id is None and result.get("transaction"):
            txn = Transaction.from_dict(result.get("transaction"))
            txn_id = txn.transaction_signature

        if not txn_id:
            self.config.app_log.warning(
                "[NEW_TXN_CONFIRM] Received confirmation without a transaction ID!"
            )
            return

        retry_key = (stream.peer.rid, "newtxn", txn_id)
        if retry_key in self.retry_messages:
            del self.retry_messages[retry_key]

        await self.config.mongo.async_db.txn_tracking.update_one(
            {"rid": stream.peer.rid},
            {
                "$set": {
                    "host": stream.peer.host,
                    f"transactions.{txn_id}": int(time.time()),
                }
            },
            upsert=True,
        )

        self.config.app_log.info(
            f"[NEW_TXN_CONFIRM] Transaction {txn_id} confirmed by peer {stream.peer.rid}. Peer added to confirmed list."
        )

    async def newblock(self, body, stream):
        """
        Handles the reception of a new block from a peer node.

        - Extracts block data from the received payload.
        - Sends a confirmation response (`newblock_confirmed`) back to the sender.
        - Checks if the block already exists in the database to prevent redundant processing.
        - Adds the block to the processing queue if it's new.
        - Supports both protocol versions:
          - If `protocol_version > 3`, confirmation contains only `block_hash` and `block_index`.
          - If `protocol_version > 1`, confirmation contains the full payload.

        This method ensures efficient block propagation by preventing duplicate processing
        and reducing unnecessary load on the node.
        """
        payload = body.get("params", {}).get("payload", {})

        if not payload.get("block"):
            self.config.app_log.info("[NEW_BLOCK] Received newblock, but no payload")
            return

        block_index = payload["block"].get("index")
        block_hash = payload["block"].get("hash")

        if stream.peer.protocol_version > 3:
            confirm_message = {"block_hash": block_hash, "block_index": block_index}
        elif stream.peer.protocol_version > 1:
            confirm_message = body.get("params", {})

        await self.config.nodeShared.write_result(
            stream, "newblock_confirmed", confirm_message, body["id"]
        )

        existing_block = await self.config.mongo.async_db.blocks.find_one(
            {"index": block_index, "hash": block_hash}
        )

        if existing_block:
            self.config.app_log.warning(
                f"[NEW_BLOCK] Block {block_index} already exists in DB, skipping processing."
            )
            return

        self.config.processing_queues.block_queue.add(
            BlockProcessingQueueItem(Blockchain(payload.get("block")), stream, body)
        )

    async def newblock_confirmed(self, body, stream):
        """
        Handles block confirmation messages received from peer nodes.

        - Extracts block hash and index from the response.
        - Supports both protocol versions:
          - If `protocol_version > 3`, confirmation contains only `block_hash` and `block_index`.
          - If `protocol_version > 1 , confirmation contains a full block payload.
        - Removes the corresponding entry from the retry queue if it was pending.

        This method improves synchronization and prevents redundant retry attempts.
        """

        payload = body.get("result", {})

        block_hash = payload.get("block_hash")
        payload.get("block_index")

        if block_hash is None and payload.get("payload"):
            block = await Block.from_dict(payload.get("payload").get("block"))
            block_hash = block.hash
            block.index

        if not block_hash:
            self.config.app_log.warning(
                "[NEW_BLOCK_CONFIRM] Received confirmation without a block hash!"
            )
            return

        retry_key = (stream.peer.rid, "newblock", block_hash)
        if retry_key in self.retry_messages:
            del self.retry_messages[retry_key]

    async def ensure_previous_block(self, block, stream):
        have_prev = await self.ensure_previous_on_blockchain(block)
        if not have_prev:
            have_prev = await self.ensure_previous_in_consensus(block)
            if not have_prev:
                await self.write_params(
                    stream,
                    "getblock",
                    {"hash": block.prev_hash, "index": block.index - 1},
                )
                return False
        return True

    async def ensure_previous_on_blockchain(self, block):
        return await self.config.mongo.async_db.blocks.find_one(
            {"hash": block.prev_hash}
        )

    async def ensure_previous_in_consensus(self, block):
        return await self.config.mongo.async_db.consensus.find_one(
            {"block.hash": block.prev_hash}
        )

    async def fill_gap(self, end_index, stream):
        start_block = await self.config.mongo.async_db.blocks.find_one(
            {"index": {"$lt": end_index}}, sort=[("index", -1)]
        )
        if end_index - 1 <= start_block["index"] + 1:
            return
        await self.config.nodeShared.write_params(
            stream,
            "getblocks",
            {"start_index": start_block["index"] + 1, "end_index": end_index - 1},
        )

    async def send_mempool(self, peer_stream):
        check_max_inputs = False
        if self.config.LatestBlock.block.index > CHAIN.CHECK_MAX_INPUTS_FORK:
            check_max_inputs = True

        check_masternode_fee = False
        if self.config.LatestBlock.block.index >= CHAIN.CHECK_MASTERNODE_FEE_FORK:
            check_masternode_fee = True

        check_kel = False
        if self.config.LatestBlock.block.index >= CHAIN.CHECK_KEL_FORK:
            check_kel = True

        check_dynamic_nodes = False
        if self.config.LatestBlock.block.index >= CHAIN.DYNAMIC_NODES_FORK:
            check_dynamic_nodes = True

        async for x in self.config.mongo.async_db.miner_transactions.find({}):
            txn = Transaction.from_dict(x)
            try:
                await txn.verify(
                    check_max_inputs=check_max_inputs,
                    check_masternode_fee=check_masternode_fee,
                    check_kel=check_kel,
                    check_dynamic_nodes=check_dynamic_nodes,
                )
            except Exception as e:
                await Transaction.handle_exception(e, txn)
                continue
            payload = {"transaction": txn.to_dict()}
            await self.write_params(peer_stream, "newtxn", payload)
            if peer_stream.peer.protocol_version > 1:
                self.retry_messages[
                    (peer_stream.peer.rid, "newtxn", txn.transaction_signature)
                ] = payload

    async def send_block_to_peers(self, block):
        async for peer_stream in self.config.peer.get_sync_peers():
            if (
                hasattr(peer_stream.peer, "block")
                and peer_stream.peer.block.index > block.index + 100
            ):
                continue
            await self.send_block_to_peer(block, peer_stream)

    async def send_block_to_peer(self, block, peer_stream):
        payload = {"payload": {"block": block.to_dict()}}
        await self.write_params(peer_stream, "newblock", payload)
        if peer_stream.peer.protocol_version > 1:
            self.retry_messages[
                (peer_stream.peer.rid, "newblock", block.hash)
            ] = payload

    async def get_next_block(self, block, peer_stream):
        """We should get another block, but only from a specific peer"""
        peer_id = getattr(peer_stream.peer, "rid", "Unknown")
        self.config.app_log.info(
            f"Requesting next block {block.index + 1} from peer {peer_id}"
        )

        try:
            await self.write_params(peer_stream, "getblock", {"index": block.index + 1})
        except Exception as e:
            self.config.app_log.error(
                f"Error requesting next block from peer {peer_id}: {e}"
            )

    async def getblock(self, body, stream):
        # get blocks should be done only by syncing peers
        params = body.get("params")
        block_hash = params.get("hash")
        block_index = params.get("index")
        block = await self.config.mongo.async_db.blocks.find_one(
            {"hash": block_hash}, {"_id": 0}
        )
        if not block:
            block = await self.config.mongo.async_db.consensus.find_one(
                {"block.hash": block_hash}, {"_id": 0}
            )
            if block:
                block = block["block"]
            else:
                block = await self.config.mongo.async_db.blocks.find_one(
                    {"index": block_index}, {"_id": 0}
                )
        if block:
            message = {"block": block}
            await self.write_result(stream, "blockresponse", message, body["id"])
            if stream.peer.protocol_version > 1:
                self.retry_messages[
                    (stream.peer.rid, "blockresponse", block["hash"], body["id"])
                ] = message
        else:
            await self.write_result(stream, "blockresponse", {}, body["id"])
            if stream.peer.protocol_version > 1:
                self.retry_messages[
                    (stream.peer.rid, "blockresponse", "", body["id"])
                ] = {}

    async def blocksresponse(self, body, stream):
        """
        Handles the response containing blockchain blocks from a peer node.

        - Extracts block data from the received response.
        - Sends a minimal confirmation (`blocksresponse_confirmed`) containing only `start_index`.
        - Processes received blocks and ensures they fit within the node's blockchain.
        - Builds forward and backward chains to maintain network synchronization.
        - Reduces unnecessary data transfer by avoiding sending large payloads.

        This method improves synchronization efficiency and prevents excessive network load.
        """
        result = body.get("result")
        blocks = result.get("blocks")

        if stream.peer.protocol_version > 1:
            start_index = body.get("result", {}).get("start_index", None)
            await self.write_result(
                stream,
                "blocksresponse_confirmed",
                {"start_index": start_index},
                body["id"],
            )

        if not blocks:
            self.config.app_log.info(f"blocksresponse, no blocks, {stream.peer.host}")
            self.config.consensus.syncing = False
            stream.synced = True
            return

        self.config.consensus.syncing = True
        blocks = [await Block.from_dict(x) for x in blocks]
        first_inbound_block = blocks[0]
        forward_blocks_chain = await self.config.consensus.build_remote_chain(
            blocks[-1]
        )
        inbound_blocks = blocks + forward_blocks_chain.init_blocks[1:]
        inbound_blockchain = Blockchain(inbound_blocks, partial=True)
        (
            backward_blocks,
            status,
        ) = await self.config.consensus.build_backward_from_block_to_fork(
            first_inbound_block, [], stream
        )

        if not status:
            await self.fill_gap(first_inbound_block.index, stream)
            self.config.consensus.syncing = False
            return False

        self.config.processing_queues.block_queue.add(
            BlockProcessingQueueItem(inbound_blockchain, stream, body)
        )
        self.config.consensus.syncing = False

    async def blocksresponse_confirmed(self, body, stream):
        """
        Handles confirmation of received block responses.

        - Extracts the `start_index` from the response.
        - Removes the corresponding entry from the retry queue to prevent duplicate processing.

        This method ensures proper acknowledgment of received block sync responses.
        """
        params = body.get("result")
        start_index = params.get("start_index")

        if (
            stream.peer.rid,
            "blocksresponse",
            start_index,
            body["id"],
        ) in self.retry_messages:
            del self.retry_messages[
                (stream.peer.rid, "blocksresponse", start_index, body["id"])
            ]

    async def blockresponse(self, body, stream):
        # get blocks should be done only by syncing peers
        result = body.get("result", {})
        if stream.peer.protocol_version > 1:
            await self.config.nodeShared.write_result(
                stream, "blockresponse_confirmed", body.get("result", {}), body["id"]
            )

        if not result.get("block"):
            self.config.app_log.info(f"blockresponse, no block, {stream.peer.host}")
            return

        self.config.processing_queues.block_queue.add(
            BlockProcessingQueueItem(Blockchain(result.get("block")), stream, body)
        )

    async def blockresponse_confirmed(self, body, stream):
        result = body.get("result")
        if not result.get("block"):
            if (
                stream.peer.rid,
                "blockresponse",
                "",
                body["id"],
            ) in self.retry_messages:
                del self.retry_messages[
                    (stream.peer.rid, "blockresponse", "", body["id"])
                ]
            return
        block = await Block.from_dict(result.get("block"))
        if (
            stream.peer.rid,
            "blockresponse",
            block.hash,
            body["id"],
        ) in self.retry_messages:
            del self.retry_messages[
                (stream.peer.rid, "blockresponse", block.hash, body["id"])
            ]

    async def connect(self, body, stream):
        params = body.get("params")
        if not params.get("peer"):
            stream.close()
            return {}

        generic_peer = Peer.from_dict(params.get("peer"))

        min_major, min_minor, min_patch = self.config.min_supported_version
        peer_major, peer_minor, peer_patch = generic_peer.node_version

        self.config.app_log.info(
            f"Incoming connection from {generic_peer.host}:{generic_peer.port} | "
            f"Peer Version: {peer_major}.{peer_minor}.{peer_patch} | "
            f"Node Version: {'.'.join(map(str, self.config.node_version))} | "
            f"Min Supported Version: {'.'.join(map(str, self.config.min_supported_version))}"
        )

        if (
            peer_major < min_major
            or (peer_major == min_major and peer_minor < min_minor)
            or (
                peer_major == min_major
                and peer_minor == min_minor
                and peer_patch < min_patch
            )
        ):
            self.config.app_log.warning(
                f"Peer {generic_peer.host}:{generic_peer.port} rejected "
                f"(version {peer_major}.{peer_minor}.{peer_patch} < {'.'.join(map(str, self.config.min_supported_version))})"
            )

            await self.write_params(
                stream,
                "disconnect",
                {"reason": "Version too old, please upgrade to latest release."},
            )
            stream.close()
            return

        peerCls = None
        if isinstance(self.config.peer, Seed):
            if generic_peer.identity.username_signature in self.config.seeds:
                peerCls = Seed
            elif generic_peer.identity.username_signature in self.config.seed_gateways:
                peerCls = SeedGateway

        elif isinstance(self.config.peer, SeedGateway):
            if generic_peer.identity.username_signature in self.config.seeds:
                peerCls = Seed
            else:
                peerCls = ServiceProvider

        elif isinstance(self.config.peer, ServiceProvider):
            if generic_peer.identity.username_signature in self.config.seed_gateways:
                peerCls = SeedGateway
            elif generic_peer.peer_type == PEER_TYPES.USER.value:
                peerCls = User
            elif generic_peer.peer_type == PEER_TYPES.POOL.value:
                peerCls = Pool

        elif isinstance(self.config.peer, User):
            peerCls = User
        else:
            self.config.app_log.error("inbound peer is not defined, disconnecting")
            stream.close()
            return {}

        if not peerCls:
            self.config.app_log.error("unknown peer type")
            self.config.app_log.error(generic_peer)
            self.config.app_log.error(params.get("peer"))
            stream.close()
            return {}

        try:
            stream.peer = peerCls.from_dict(params.get("peer"))
        except:
            self.config.app_log.error("invalid peer identity")
            stream.close()
            return {}

        limit = self.config.peer.__class__.type_limit(peerCls)
        self.config.app_log.info(
            f"limit num peers {limit}, currently at {len(self.config.nodeServer.inbound_streams[peerCls.__name__])}"
        )
        if (
            len(self.config.nodeServer.inbound_pending[peerCls.__name__])
            + len(self.config.nodeServer.inbound_streams[peerCls.__name__])
        ) >= limit:
            if not self.config.peer.is_linked_peer(stream.peer):
                self.config.app_log.info("sent capacity message, stream closed")
                await self.write_result(stream, "capacity", {}, body["id"])
                await self.remove_peer(stream)
                return {}

        if (
            generic_peer.rid
            in self.config.nodeServer.inbound_pending[stream.peer.__class__.__name__]
        ):
            await self.remove_peer(
                stream,
                close=False,
                reason=f"{generic_peer.rid} in nodeServer.inbound_pending",
            )
            return {}

        if (
            generic_peer.rid
            in self.config.nodeServer.inbound_streams[stream.peer.__class__.__name__]
        ):
            await self.remove_peer(
                stream,
                close=False,
                reason=f"{generic_peer.rid} in nodeServer.inbound_streams",
            )
            return {}

        if (
            generic_peer.rid
            in self.config.nodeClient.outbound_pending[stream.peer.__class__.__name__]
        ):
            await self.remove_peer(
                stream,
                close=False,
                reason=f"{generic_peer.rid} in nodeServer.outbound_pending",
            )
            return

        if (
            generic_peer.rid
            in self.config.nodeClient.outbound_streams[stream.peer.__class__.__name__]
        ):
            await self.remove_peer(
                stream,
                close=False,
                reason=f"{generic_peer.rid} in nodeServer.outbound_streams",
            )
            return

        try:
            result = verify_signature(
                base64.b64decode(stream.peer.identity.username_signature),
                stream.peer.identity.username.encode(),
                bytes.fromhex(stream.peer.identity.public_key),
            )
            if result:
                self.config.app_log.info(
                    "new {} peer is valid".format(stream.peer.__class__.__name__)
                )
        except:
            self.config.app_log.error("invalid peer identity signature")
            stream.close()
            return {}

        self.config.nodeServer.inbound_streams[peerCls.__name__][
            stream.peer.rid
        ] = stream
        # Store the peer's ECDH public key for session cipher derivation
        stream._peer_ecdh_pub = params.get("ecdh_public_key", "")
        # Accept the peer's pending inception transaction if provided.
        # This breaks the bootstrapping deadlock: a brand-new node whose
        # inception has never been gossiped embeds it in the plaintext
        # connect message so the receiver can add it to its mempool before
        # authenticate runs the KEL lookup.
        inception_txn_dict = params.get("inception_txn")
        if inception_txn_dict:
            await self._accept_peer_inception(inception_txn_dict)
        self.config.app_log.info(
            "Connected to {}: {}".format(
                stream.peer.__class__.__name__, stream.peer.to_json()
            )
        )
        return {}

    async def challenge(self, body, stream):
        try:
            self.ensure_protocol_version(body, stream)
        except:
            return await self.remove_peer(
                stream, reason="protocol version < 5 not allowed (KEL enforcement)"
            )
        try:
            params = body.get("params", {})
            challenge = params.get("token")
            from yadacoin.core.keyrotation import get_node_auth_key

            _auth_priv, _auth_pub, _conf_priv, _conf_pub = await get_node_auth_key(
                self.config
            )
            signed_challenge = TU.generate_signature(challenge, _auth_priv)
            # Confirming signature: next key signs the same challenge to prove
            # knowledge of K_{n+i+1} without revealing SECOND_FACTOR.
            confirming_signed_challenge = None
            if _conf_priv:
                confirming_signed_challenge = TU.generate_signature(
                    challenge, _conf_priv
                )
            # Fetch the ratchet chain from the signing log so the peer can
            # verify the path from the on-chain anchor to the ratchet key.
            ratchet_chain = []
            anchor_pub = getattr(self.config, "kel_public_key", None)
            if anchor_pub:
                cursor = self.config.mongo.async_db.kel_signing_log.find(
                    {"anchor_public_key": anchor_pub},
                    {
                        "_id": 0,
                        "anchor_public_key": 1,
                        "public_key": 1,
                        "prev_public_key": 1,
                        "certification": 1,
                    },
                ).sort("counter", 1)
                ratchet_chain = await cursor.to_list(length=200)
            # Generate ephemeral ECDH keypair; derive session cipher using
            # the peer's ECDH key (from connect) + this challenge token.
            _ecdh_priv, _ecdh_pub = SessionCipher.generate_keypair()
            peer_ecdh_pub = getattr(stream, "_peer_ecdh_pub", "")
            if peer_ecdh_pub:
                stream.session_cipher = SessionCipher.derive(
                    _ecdh_priv, peer_ecdh_pub, ""
                )
        except Exception as _exc:
            self.config.app_log.warning(
                "NodeRPC challenge error (%s): %s",
                stream.peer.host if stream.peer else "?",
                _exc,
                exc_info=True,
            )
            return await self.remove_peer(
                stream, reason="NodeRPC challenge: generate_signature"
            )
        # Send the challenge (plaintext — in PRE_AUTH_METHODS) FIRST so the
        # client can derive the session cipher before we send the encrypted
        # authenticate response.  Swapping the order prevents the client from
        # receiving an encrypted message it can't yet decrypt.
        stream.peer.token = str(uuid4())
        challenge_payload = {
            "peer": self.config.peer.to_dict(),
            "token": stream.peer.token,
        }
        if peer_ecdh_pub:
            challenge_payload["ecdh_public_key"] = _ecdh_pub
        # Embed our pending inception (if not yet mined) so the client can
        # add it to their mempool before running the KEL lookup in authenticate.
        pending_inception = await self._get_pending_inception()
        if pending_inception:
            challenge_payload["inception_txn"] = pending_inception
        await self.write_params(stream, "challenge", challenge_payload)
        # Send authenticate AFTER challenge so the client has the ECDH key
        # (from the challenge payload above) before it receives this encrypted message.
        if stream.peer.protocol_version > 1:
            await self.write_params(
                stream,
                "authenticate",
                {
                    "peer": self.config.peer.to_dict(),
                    "signed_challenge": signed_challenge,
                    "ratchet_public_key": _auth_pub,
                    "confirming_signed_challenge": confirming_signed_challenge,
                    "confirming_public_key": _conf_pub,
                    "ratchet_chain": ratchet_chain,
                },
            )
        else:
            await self.write_result(
                stream,
                "authenticate",
                {
                    "peer": self.config.peer.to_dict(),
                    "signed_challenge": signed_challenge,
                    "ratchet_public_key": _auth_pub,
                    "confirming_signed_challenge": confirming_signed_challenge,
                    "confirming_public_key": _conf_pub,
                    "ratchet_chain": ratchet_chain,
                },
                body["id"],
            )

    async def authenticate(self, body, stream):
        self.ensure_protocol_version(body, stream)
        if stream.peer.protocol_version > 1:
            params = body.get("params", {})
        else:
            params = body.get("result", {})
        signed_challenge = params.get("signed_challenge")
        ratchet_public_key = (
            params.get("ratchet_public_key") or stream.peer.identity.public_key
        )
        confirming_signed_challenge = params.get("confirming_signed_challenge")
        confirming_public_key = params.get("confirming_public_key")
        ratchet_chain = params.get("ratchet_chain") or []

        peer_host = stream.peer.host
        peer_username = getattr(stream.peer.identity, "username", peer_host)

        self.config.app_log.info(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  KEL Authentication  ←  %s (%s)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            peer_username,
            peer_host,
        )

        # ── Step 1: primary signature ─────────────────────────────────────
        # The peer signs a random challenge with their current ratchet key
        # K_{n+i}.  This proves they *possess* that key right now.
        result = verify_signature(
            base64.b64decode(signed_challenge),
            stream.peer.token.encode(),
            bytes.fromhex(ratchet_public_key),
        )
        if not result:
            self.config.app_log.warning(
                "  [FAIL] Primary signature invalid  (key=%s...)",
                ratchet_public_key[:16],
            )
            return await self.remove_peer(
                stream, reason="authenticate: primary signature invalid"
            )
        self.config.app_log.info(
            "  [OK]   Primary signature verified\n"
            "         signing key : %s...%s\n"
            "         Unlike TLS, this key rotates every authentication.",
            ratchet_public_key[:16],
            ratchet_public_key[-8:],
        )

        # ── Step 2: confirming signature ──────────────────────────────────
        # The peer also signs the challenge with K_{n+i+1} — the *next* key.
        # This proves they know SECOND_FACTOR (needed to derive K_{n+i+1}).
        # An attacker who steals only K_{n+i} cannot produce this signature.
        if confirming_signed_challenge and confirming_public_key:
            confirming_ok = verify_signature(
                base64.b64decode(confirming_signed_challenge),
                stream.peer.token.encode(),
                bytes.fromhex(confirming_public_key),
            )
            if not confirming_ok:
                self.config.app_log.warning(
                    "  [FAIL] Confirming signature invalid  (next key=%s...)\n"
                    "         Peer has current key but not SECOND_FACTOR — "
                    "possible key theft.",
                    confirming_public_key[:16],
                )
                return await self.remove_peer(
                    stream,
                    reason="authenticate: confirming signature invalid — "
                    "peer may have only the current key, not SECOND_FACTOR",
                )
            self.config.app_log.info(
                "  [OK]   Confirming signature verified\n"
                "         next key    : %s...%s\n"
                "         Peer holds SECOND_FACTOR — stolen key alone is useless.",
                confirming_public_key[:16],
                confirming_public_key[-8:],
            )
        else:
            self.config.app_log.info(
                "  [--]   No confirming signature (KEL ratchet not yet active for this peer)"
            )

        # ── Step 3: KEL on-chain verification (post-fork) ─────────────────
        current_index = getattr(
            getattr(self.config, "LatestBlock", None), "block", None
        )
        current_index = getattr(current_index, "index", 0) if current_index else 0
        if (
            stream.peer.protocol_version >= 5
            and current_index >= CHAIN.KEL_P2P_AUTH_FORK
        ):
            from bitcoin.wallet import P2PKHBitcoinAddress

            from yadacoin.core.keyeventlog import KeyEventLog

            # Verify the peer has an inception transaction on-chain or in the
            # mempool.  This anchors their identity to the blockchain — no CA
            # needed; any node can verify independently.
            peer_kel = await KeyEventLog.build_from_public_key(
                stream.peer.identity.public_key, onchain_only=False
            )
            if not peer_kel:
                self.config.app_log.warning(
                    "  [FAIL] No KEL inception found for %s (key=%s...)\n"
                    "         Post-fork nodes must have an on-chain or mempool inception.",
                    peer_username,
                    stream.peer.identity.public_key[:16],
                )
                return await self.remove_peer(
                    stream,
                    reason="protocol v5: no on-chain key event log found for this peer",
                )
            kel_source = (
                "mempool" if getattr(peer_kel[0], "mempool", False) else "blockchain"
            )
            mempool_note = (
                "\n         (mempool inception — will strengthen once mined in a block)"
                if kel_source == "mempool"
                else ""
            )
            self.config.app_log.info(
                "  [OK]   KEL inception verified  (source=%s, depth=%d)%s\n"
                "         inception key : %s...%s\n"
                "         This key was committed to the blockchain — cannot be faked by a CA.",
                kel_source,
                len(peer_kel),
                mempool_note,
                stream.peer.identity.public_key[:16],
                stream.peer.identity.public_key[-8:],
            )

            if ratchet_public_key != stream.peer.identity.public_key:
                if not ratchet_chain:
                    return await self.remove_peer(
                        stream,
                        reason="protocol v5: ratchet key used but no ratchet chain provided",
                    )
                anchor_pub = ratchet_chain[0].get("anchor_public_key", "")
                try:
                    anchor_addr = str(
                        P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(anchor_pub))
                    )
                except Exception:
                    return await self.remove_peer(
                        stream,
                        reason="protocol v5: invalid anchor public key in ratchet chain",
                    )
                if anchor_addr != peer_kel[-1].prerotated_key_hash:
                    return await self.remove_peer(
                        stream,
                        reason="protocol v5: ratchet chain anchor does not match on-chain KEL tip",
                    )
                prev_pub = anchor_pub
                for entry in ratchet_chain:
                    try:
                        cert_ok = verify_signature(
                            base64.b64decode(entry["certification"]),
                            entry["public_key"].encode("utf-8"),
                            bytes.fromhex(prev_pub),
                        )
                    except Exception:
                        cert_ok = False
                    if not cert_ok:
                        return await self.remove_peer(
                            stream,
                            reason="protocol v5: ratchet chain certification failed",
                        )
                    prev_pub = entry["public_key"]
                if prev_pub != ratchet_public_key:
                    return await self.remove_peer(
                        stream,
                        reason="protocol v5: ratchet chain tip does not match signing key",
                    )
                self.config.app_log.info(
                    "  [OK]   Ratchet chain verified  (%d steps from on-chain anchor)\n"
                    "         Each step is self-certified — no third party required.",
                    len(ratchet_chain),
                )
        else:
            self.config.app_log.info(
                "  [--]   KEL on-chain enforcement not yet active\n"
                "         current block : %d  /  activation fork : %d\n"
                "         Identity is still verified via the signed challenge above.\n"
                "         Once the network reaches block %d, every peer will be required\n"
                "         to have a KEL inception committed to the blockchain, making\n"
                "         impersonation impossible without controlling the chain itself.\n"
                "         Note: new nodes bootstrap safely even after the fork — their\n"
                "         inception transaction is embedded in the plaintext connect\n"
                "         handshake (before encrypt/auth), so the receiving peer stores\n"
                "         it in mempool and the KEL check finds it immediately.",
                current_index,
                CHAIN.KEL_P2P_AUTH_FORK,
                CHAIN.KEL_P2P_AUTH_FORK,
            )

        stream.peer.authenticated = True
        self.config.app_log.info(
            "  [✓]   %s authenticated  (protocol v%d)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            peer_username,
            stream.peer.protocol_version,
        )
        await self.send_block_to_peer(self.config.LatestBlock.block, stream)
        await self.get_next_block(self.config.LatestBlock.block, stream)

    def ensure_protocol_version(self, body, stream):
        params = body.get("params", {})
        peer = params.get("peer", {})
        protocol_version = peer.get("protocol_version", 1)
        stream.peer.protocol_version = protocol_version
        current_index = getattr(
            getattr(self.config, "LatestBlock", None),
            "block",
            None,
        )
        current_index = getattr(current_index, "index", 0) if current_index else 0
        if current_index >= CHAIN.KEL_P2P_AUTH_FORK and protocol_version < 5:
            raise ProtocolVersionTooLowError(
                f"Peer {stream.peer.host} is using protocol version {protocol_version}; "
                "version 5+ is required (KEL enforcement). "
                "The peer's key may be compromised — refusing connection."
            )

    async def disconnect(self, body, stream):
        params = body.get("params", {})
        if params.get("reason"):
            self.disconnect_tracker.by_host[stream.peer.host] = (
                self.disconnect_tracker.by_host.get(stream.peer.host, 0) + 1
            )
            self.disconnect_tracker.by_reason[params.get("reason")] = (
                self.disconnect_tracker.by_reason.get(params.get("reason"), 0) + 1
            )
            self.config.app_log.info(f"disconnect: {params.get('reason')}")
        await self.remove_peer(stream, reason="NodeRPC disconnect")

    async def route(self, body, stream):
        # check if rid in peers
        # if rid is in the list, decrypt
        # find the decrypted rid in peer list
        # route the resulting transaction if rid is found
        # if not found, check the websocket peers for rid
        # forward to websocket if rid is found
        # if not found in websockets, rerturn not found
        params = body.get("params")
        route = params["route"]
        if isinstance(self.config.peer, Seed):
            if isinstance(stream.peer, SeedGateway):
                # Being routed out to seed layer from user node
                for rid, peer_stream in self.config.nodeServer.inbound_streams[
                    Seed.__name__
                ].items():
                    if peer_stream == stream:
                        continue
                    await BaseRPC().write_params(peer_stream, "route", params)

                for rid, peer_stream in self.config.nodeClient.outbound_streams[
                    Seed.__name__
                ].items():
                    if peer_stream == stream:
                        continue
                    await BaseRPC().write_params(peer_stream, "route", params)
            elif isinstance(stream.peer, Seed):
                # Being routed in from seed. We should be in the route selector
                for rid, peer_stream in self.config.nodeServer.inbound_streams[
                    SeedGateway.__name__
                ].items():
                    if peer_stream == stream:
                        continue
                    await BaseRPC().write_params(peer_stream, "route", params)

        elif isinstance(self.config.peer, SeedGateway):
            if isinstance(stream.peer, Seed):
                for rid, peer_stream in self.config.nodeServer.inbound_streams[
                    ServiceProvider.__name__
                ].items():
                    if peer_stream == stream:
                        continue
                    await BaseRPC().write_params(peer_stream, "route", params)

            elif isinstance(stream.peer, ServiceProvider):
                for rid, peer_stream in self.config.nodeClient.outbound_streams[
                    Seed.__name__
                ].items():
                    if peer_stream == stream:
                        continue
                    await BaseRPC().write_params(peer_stream, "route", params)

        elif isinstance(self.config.peer, ServiceProvider):
            if isinstance(stream.peer, SeedGateway):
                for rid, peer_stream in self.config.nodeServer.inbound_streams[
                    User.__name__
                ].items():
                    if peer_stream == stream:
                        continue
                    await BaseRPC().write_params(peer_stream, "route", params)

                ws_stream = await self.get_ws_stream(route)
                if ws_stream:
                    await BaseRPC().write_params(peer_stream, "route", params)

            elif isinstance(stream.peer, User):
                for rid, peer_stream in self.config.nodeClient.outbound_streams[
                    SeedGateway.__name__
                ].items():
                    if peer_stream == stream:
                        continue
                    await BaseRPC().write_params(peer_stream, "route", params)

        elif isinstance(self.config.peer, User):
            if isinstance(stream.peer, ServiceProvider):
                ws_stream = await self.get_ws_stream(route)
                if ws_stream:
                    await ws_stream.route(body, source="tcpsocket")

    async def get_ws_stream(self, route):
        if MODES.WEB.value not in self.config.modes:
            return False

        ws_users = self.config.websocketServer.inbound_streams[User.__name__]
        if not ws_users:
            return False

        group = None
        for rid in route.split(":"):
            if rid in self.config.websocketServer.inbound_streams[Group.__name__]:
                group = self.config.websocketServer.inbound_streams[Group.__name__][rid]
            if group and rid in group:
                return group[rid]


class NodeSocketServer(RPCSocketServer, NodeRPC):
    retry_messages = {}
    disconnect_tracker = NodeServerDisconnectTracker()
    newtxn_tracker = NodeServerNewTxnTracker()

    def __init__(self):
        super(NodeSocketServer, self).__init__()
        self.config = Config()


class NodeSocketClient(RPCSocketClient, NodeRPC):
    retry_messages = {}
    disconnect_tracker = NodeClientDisconnectTracker()
    newtxn_tracker = NodeClientNewTxnTracker()

    def __init__(self):
        super(NodeSocketClient, self).__init__()
        self.config = Config()

    async def connect(self, peer: Peer):
        try:
            stream = await super(NodeSocketClient, self).connect(peer)

            if not stream:
                return

            # Generate ephemeral ECDH keypair; send public key in connect so
            # the server can derive the session cipher after the challenge.
            _ecdh_priv, _ecdh_pub = SessionCipher.generate_keypair()
            stream._ecdh_priv = _ecdh_priv

            connect_payload = {
                "peer": self.config.peer.to_dict(),
                "ecdh_public_key": _ecdh_pub,
            }
            # Embed our pending inception so the server can accept us before
            # our inception has been mined or gossiped any other way.
            pending_inception = await self._get_pending_inception()
            if pending_inception:
                connect_payload["inception_txn"] = pending_inception

            await self.write_params(stream, "connect", connect_payload)

            stream.peer.token = str(uuid4())
            await self.write_params(
                stream,
                "challenge",
                {"peer": self.config.peer.to_dict(), "token": stream.peer.token},
            )

            asyncio.create_task(self.send_keepalive(stream))

            await self.wait_for_data(stream)
        except StreamClosedError:
            Config().app_log.error(
                "Cannot connect to {}: {}".format(
                    peer.__class__.__name__, peer.to_json()
                )
            )

    async def challenge(self, body, stream):
        try:
            self.ensure_protocol_version(body, stream)
        except:
            return await self.remove_peer(
                stream, reason="protocol version < 5 not allowed (KEL enforcement)"
            )
        try:
            params = body.get("params", {})
            challenge = params.get("token")
            from yadacoin.core.keyrotation import get_node_auth_key

            _auth_priv, _auth_pub, _conf_priv, _conf_pub = await get_node_auth_key(
                self.config
            )
            signed_challenge = TU.generate_signature(challenge, _auth_priv)
            confirming_signed_challenge = None
            if _conf_priv:
                confirming_signed_challenge = TU.generate_signature(
                    challenge, _conf_priv
                )
            ratchet_chain = []
            anchor_pub = getattr(self.config, "kel_public_key", None)
            if anchor_pub:
                cursor = self.config.mongo.async_db.kel_signing_log.find(
                    {"anchor_public_key": anchor_pub},
                    {
                        "_id": 0,
                        "anchor_public_key": 1,
                        "public_key": 1,
                        "prev_public_key": 1,
                        "certification": 1,
                    },
                ).sort("counter", 1)
                ratchet_chain = await cursor.to_list(length=200)
            # Derive session cipher from server's ECDH key + challenge token.
            server_ecdh_pub = params.get("ecdh_public_key", "")
            _ecdh_priv = getattr(stream, "_ecdh_priv", None)
            if server_ecdh_pub and _ecdh_priv:
                stream.session_cipher = SessionCipher.derive(
                    _ecdh_priv, server_ecdh_pub, ""
                )
            # Accept the server's pending inception if provided, completing
            # the mutual inception exchange started in our connect message.
            server_inception = params.get("inception_txn")
            if server_inception:
                await self._accept_peer_inception(server_inception)
        except Exception as _exc:
            self.config.app_log.warning(
                "NodeSocketClient challenge error (%s): %s",
                stream.peer.host if stream.peer else "?",
                _exc,
                exc_info=True,
            )
            return await self.remove_peer(
                stream, reason="NodeSocketClient challenge: generate_signature"
            )
        if stream.peer.protocol_version > 1:
            await self.write_params(
                stream,
                "authenticate",
                {
                    "peer": self.config.peer.to_dict(),
                    "signed_challenge": signed_challenge,
                    "ratchet_public_key": _auth_pub,
                    "confirming_signed_challenge": confirming_signed_challenge,
                    "confirming_public_key": _conf_pub,
                    "ratchet_chain": ratchet_chain,
                },
            )
        else:
            await self.write_result(
                stream,
                "authenticate",
                {
                    "peer": self.config.peer.to_dict(),
                    "signed_challenge": signed_challenge,
                    "ratchet_public_key": _auth_pub,
                    "confirming_signed_challenge": confirming_signed_challenge,
                    "confirming_public_key": _conf_pub,
                    "ratchet_chain": ratchet_chain,
                },
                body["id"],
            )

    async def capacity(self, body, stream):
        self.config.nodeClient.outbound_ignore[stream.peer.__class__.__name__][
            stream.peer.identity.username_signature
        ] = time.time()
        self.config.app_log.warning(
            "{} at full capacity: {}".format(
                stream.peer.__class__.__name__, stream.peer.to_json()
            )
        )
