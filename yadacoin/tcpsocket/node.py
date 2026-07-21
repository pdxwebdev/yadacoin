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
from yadacoin.core.identity import Identity
from yadacoin.core.keyeventlog import (
    KELExceptionPredecessorNotYetInMempool,
    KELExceptionPreviousKeyHashReferenceMissing,
    KELLogUnbuildableException,
)
from yadacoin.core.keyrotation import NodeKeyRotationManager
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

    # In-flight "please resend your KEL from scratch" requests, keyed by a
    # per-request uuid.  Shared across server/client instances — request ids
    # are globally unique so there's no cross-talk risk.  See
    # _request_peer_kel_resync / request_kel_resync / kel_resync_response.
    _kel_resync_waiters: dict = {}
    # Same pattern for identity-announcement pulls — see
    # _request_peer_identity_announcement / request_identity_announcement /
    # identity_announcement_response.
    _ia_resync_waiters: dict = {}
    # Pending re-auth callbacks fired when a resync response arrives while
    # the read loop was blocked inside the original handler.  Keyed by the
    # same request id as the corresponding _*_waiters entry.  See
    # _request_peer_kel_resync / _request_peer_identity_announcement.
    _resync_reauth: dict = {}

    def __init__(self):
        super(NodeRPC, self).__init__()
        self.config = Config()

    config = None

    async def _get_pending_kel_chain(self) -> list:
        """Return all pending (mempool-only) KEL transactions for this node.

        Queries miner_transactions directly for entries whose public_key
        matches K0 — no need to walk the full blockchain chain.
        """
        manager = getattr(self.config, "kel_manager", None)
        if not manager:
            return []

        from yadacoin.core.identityannouncement import IdentityAnnouncement

        username = getattr(self.config, "username", "") or ""
        own_identity = await IdentityAnnouncement.get_by_username(
            username, include_mempool=True
        )
        k0_pub = (own_identity or {}).get("public_key") or getattr(
            self.config, "kel_anchor_public_key", None
        )
        if not k0_pub:
            return []

        # Directly query the mempool for all KEL entries signed by K0.
        # These are the only entries the peer might not have.
        docs = await self.config.mongo.async_db.miner_transactions.find(
            {"public_key": k0_pub, "public_key_hash": {"$exists": True, "$ne": ""}},
            {"_id": 0},
        ).to_list(length=None)
        return docs

    async def _get_kel_anchor_chain(self) -> list:
        """Return our complete KEL chain as a list of raw txn dicts (or
        empty if we have no resolvable K0 yet).

        The full chain is needed because a peer who cannot find our inception
        needs every entry from the inception onwards — the inception (with
        ``prev_public_key_hash == ""``) is what satisfies their ``_has_kel``
        check, and subsequent entries establish the chain of trust up to our
        current signing key.
        """
        from yadacoin.core.identityannouncement import IdentityAnnouncement
        from yadacoin.core.keyeventlog import KeyEventLog

        username = getattr(self.config, "username", "") or ""
        own_identity = await IdentityAnnouncement.get_by_username(
            username, include_mempool=True
        )
        k0_pub = (own_identity or {}).get("public_key") or getattr(
            self.config, "kel_anchor_public_key", None
        )
        if not k0_pub:
            return []

        try:
            kel = await KeyEventLog.build_from_public_key(k0_pub)
        except Exception as exc:
            self.config.app_log.debug("_get_kel_anchor_chain: KEL build error: %s", exc)
            return []
        if not kel:
            return []
        return [ke.to_dict() for ke in kel]

    async def _accept_peer_kel_chain(self, txn_list: list) -> None:
        """Receive, verify, and store a peer's unconfirmed KEL chain into the
        local mempool so the KEL lookup in ``authenticate`` can find them.
        """
        if not txn_list or not isinstance(txn_list, list):
            return
        check_max_inputs = (
            self.config.LatestBlock.block.index > CHAIN.CHECK_MAX_INPUTS_FORK
        )
        check_masternode_fee = (
            self.config.LatestBlock.block.index >= CHAIN.CHECK_MASTERNODE_FEE_FORK
        )
        check_kel = self.config.LatestBlock.block.index >= CHAIN.CHECK_KEL_FORK
        check_dynamic_nodes = (
            self.config.LatestBlock.block.index >= CHAIN.DYNAMIC_NODES_FORK
        )
        parsed = []
        for txn_dict in txn_list:
            if not txn_dict or not isinstance(txn_dict, dict):
                continue
            try:
                parsed.append(Transaction.from_dict(txn_dict))
            except Exception as exc:
                self.config.app_log.debug(
                    "_accept_peer_kel_chain: parse error: %s", exc
                )
        for txn in parsed:
            try:
                await txn.verify(
                    check_max_inputs=check_max_inputs,
                    check_masternode_fee=check_masternode_fee,
                    check_kel=check_kel,
                    check_dynamic_nodes=check_dynamic_nodes,
                    mempool=True,
                    batch_txns=parsed,
                )
                await self.config.mongo.async_db.miner_transactions.replace_one(
                    {"id": txn.transaction_signature}, txn.to_dict(), upsert=True
                )
            except Exception as exc:
                self.config.app_log.debug(
                    "_accept_peer_kel_chain: verify/store error: %s", exc
                )
        self.config.app_log.info(
            "Bootstrap: accepted %d peer KEL txn(s) into mempool.", len(parsed)
        )

    # ── KEL "start over" resync ────────────────────────────────────────────
    #
    # The normal handshake only ever sends KEL data opportunistically
    # (whatever _get_pending_kel_chain()/the off-chain delta happen to
    # contain at that instant). If a peer's inception hasn't propagated to
    # us yet — e.g. a startup race, or it's already been mined into a block
    # we haven't synced — _process_ratchet_auth has nothing to fall back on
    # and the handshake fails with "no KEL inception found" even though the
    # peer is perfectly legitimate. These three methods let either side
    # actively ask the other, over the same live stream, to resend its
    # complete KEL (on-chain + mempool) from scratch and retry once — the
    # same "actively re-request what's missing" pattern fill_gap() already
    # uses for block gaps.

    async def _request_peer_kel_resync(self, stream, reauth_cb=None) -> None:
        """Ask the peer to resend its full KEL.  Non-blocking — sends the
        request and returns immediately so the stream's read loop stays
        free to dispatch the peer's response.  When the response arrives,
        ``kel_resync_response`` ingests it and fires *reauth_cb* (if any)
        to re-run the handshake with the freshly-populated mempool.

        This must NOT await the response inline: ``handle_stream`` dispatches
        handlers via ``await getattr(self, method)(body, stream)``
        (base.py:409), so blocking inside a handler deadlocks the read loop
        — the peer's response would sit in the socket buffer unread until
        this handler returns, which it never does because it's waiting for
        that same response."""
        req_id = str(uuid4())
        self._kel_resync_waiters[req_id] = True
        if reauth_cb:
            self._resync_reauth[req_id] = reauth_cb
        await self.write_params(stream, "request_kel_resync", {"id": req_id})

    async def request_kel_resync(self, body, stream):
        """Peer is asking us to resend our complete KEL (on-chain + mempool)
        from scratch, because they couldn't find our inception locally."""
        params = body.get("params", {})
        req_id = params.get("id", "")
        kel_chain = await self._get_kel_anchor_chain()

        await self.write_params(
            stream, "kel_resync_response", {"id": req_id, "kel_chain": kel_chain}
        )
        self.config.app_log.info(
            "  [>]   kel_resync_response sent (%d entries)", len(kel_chain)
        )

    async def kel_resync_response(self, body, stream):
        """Ingest the peer's KEL and fire any pending re-auth callback."""
        params = body.get("params", {})
        req_id = params.get("id", "")
        kel_chain = params.get("kel_chain") or []
        self._kel_resync_waiters.pop(req_id, None)
        if kel_chain:
            await self._accept_peer_kel_chain(kel_chain)
        reauth_cb = self._resync_reauth.pop(req_id, None)
        if reauth_cb:
            await reauth_cb(kel_chain)

    # ── end identity-announcement pull ─────────────────────────────────────

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

        if txn.are_kel_fields_populated():
            existing_txn = await self.config.mongo.async_db.miner_transactions.find_one(
                {
                    "$or": [
                        {"twice_prerotated_key_hash": txn.twice_prerotated_key_hash},
                        {"prerotated_key_hash": txn.prerotated_key_hash},
                        {"public_key_hash": txn.public_key_hash},
                        {"prev_public_key_hash": txn.prev_public_key_hash},
                        {"public_key": txn.public_key},
                    ]
                }
            )
            if existing_txn:
                self.config.app_log.warning(
                    f"KEL Transaction {txn_id} already in mempool! Ignoring."
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
        mempool_transactions = []

        async for txn in self.config.mongo.async_db.miner_transactions.find(
            {"relationship.smart_contract": {"$exists": False}}
        ).sort([("fee", -1), ("time", 1)]).limit(1000):
            try:
                mempool_transactions.append(Transaction.from_dict(txn))
            except Exception as e:
                self.config.app_log.error(f"Failed to process mempool txn: {e}")

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
        identity_announcement = params["identity_announcement"]
        await self.config.mongo.async_db.miner_transactions.replace_one(
            {"id": identity_announcement["id"]}, identity_announcement, upsert=True
        )
        generic_peer = Peer.from_dict(params.get("peer"))
        generic_peer.identity = Identity(
            public_key=identity_announcement["public_key"],
            username=identity_announcement["relationship"]["identity"]["username"],
            username_signature=identity_announcement["relationship"]["identity"][
                "username_signature"
            ],
        )
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

        elif isinstance(self.config.peer, Pool):
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
        # Store the latest ratchet PKH the connecting peer reports having for
        # our chain so challenge can send only the delta they're missing.
        stream._client_latest_ratchet_pkh = params.get("latest_ratchet_pkh", "")
        # Accept the peer's unconfirmed KEL chain if provided.
        kel_chain_list = params.get("kel_chain") or []
        if kel_chain_list:
            await self._accept_peer_kel_chain(kel_chain_list)
        self.config.app_log.info(
            "Connected to {}: {}".format(
                stream.peer.__class__.__name__,
                stream.peer.identity.username or "(blank)",
            )
        )
        await self._handle_kel_connect(stream, params)
        return {}

    def ensure_protocol_version(self, body, stream):
        params = body.get("params", {})
        peer = params.get("peer", {})
        protocol_version = peer.get("protocol_version", 1)
        stream.peer.protocol_version = protocol_version
        if protocol_version < 5:
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

    # ── KEL single-connect helpers ────────────────────────────────────────────

    async def _process_ratchet_auth(
        self,
        stream,
        ratchet_chain,
        ratchet_public_key,
        latest_ratchet_pkh="",
        _retried=False,
    ):
        """Verify, store, and anchor-check a peer's ratchet_chain.

        Returns (peer_k0, has_kel, anchor_source, anchor_counter) on success.
        Calls remove_peer and returns None on failure.

        If the peer's inception can't be found locally on the first pass,
        actively asks the peer (over this same stream) to resend its
        complete KEL from scratch and retries once — see
        _request_peer_kel_resync — before giving up.  This covers the case
        where the inception simply hasn't propagated to us yet (a startup
        race, or it's already on-chain in a block we haven't synced).
        """
        from bitcoin.wallet import P2PKHBitcoinAddress

        from yadacoin.core.identityannouncement import IdentityAnnouncement as _IApeer
        from yadacoin.core.keyeventlog import KeyEvent as _KE
        from yadacoin.core.transaction import Transaction as _Txn

        peer_username = getattr(stream.peer.identity, "username", stream.peer.host)

        check_max_inputs = (
            self.config.LatestBlock.block.index > CHAIN.CHECK_MAX_INPUTS_FORK
        )
        check_masternode_fee = (
            self.config.LatestBlock.block.index >= CHAIN.CHECK_MASTERNODE_FEE_FORK
        )
        check_kel = self.config.LatestBlock.block.index >= CHAIN.CHECK_KEL_FORK
        check_dynamic_nodes = (
            self.config.LatestBlock.block.index >= CHAIN.DYNAMIC_NODES_FORK
        )

        parsed_ratchet = []
        for txn_dict in ratchet_chain:
            try:
                parsed_ratchet.append(_Txn.from_dict(txn_dict))
            except Exception as exc:
                await self.remove_peer(stream, reason=f"ratchet: malformed txn — {exc}")
                return None

        _peer_ia = await _IApeer.get_by_username(
            getattr(stream.peer.identity, "username", "") or "", include_mempool=True
        )
        _peer_k0 = (_peer_ia or {}).get("public_key") or (
            parsed_ratchet[0].public_key if parsed_ratchet else None
        )

        # Anchor to the on-chain identity announcement if this peer is
        # configured with one.  This overrides any username-based lookup so the
        # KEL is verified against the authoritative inception transaction.
        _ia_id = getattr(stream.peer, "identity_announcement", None)
        if _ia_id:
            _anchor_doc = await _IApeer.get_by_transaction_id(_ia_id)
            if not _anchor_doc:
                # We don't have the peer's identity-announcement transaction
                # locally.  Instead of disconnecting, actively ask the peer
                # to send it to us over this same stream.  The request is
                # non-blocking — we return None here to unblock the read
                # loop, and the response handler will ingest the txn and
                # re-run the handshake via a callback.
                if not _retried:
                    self.config.app_log.warning(
                        "ratchet: identity_announcement %s not found locally "
                        "— requesting it from peer %s",
                        _ia_id,
                        peer_username,
                    )

                await self.remove_peer(
                    stream, reason="ratchet: identity_announcement txn not found"
                )
                return None
            _anchor_pub = _anchor_doc.get("public_key")
            if not _anchor_pub:
                await self.remove_peer(
                    stream, reason="ratchet: identity_announcement missing public_key"
                )
                return None
            _peer_k0 = _anchor_pub

        for i, txn in enumerate(parsed_ratchet):
            try:
                await txn.verify(
                    check_max_inputs=check_max_inputs,
                    check_masternode_fee=check_masternode_fee,
                    check_kel=False,
                    check_dynamic_nodes=check_dynamic_nodes,
                    mempool=True,
                    batch_txns=parsed_ratchet,
                )
            except Exception as exc:
                await self.remove_peer(
                    stream, reason=f"ratchet: invalid txn [{i}] — {exc}"
                )
                return None

        # Assign counters and store entries
        _existing_tip = None
        if _peer_k0:
            if latest_ratchet_pkh:
                _existing_tip = await self.config.mongo.async_db.key_event_log.find_one(
                    {
                        "anchor_public_key": _peer_k0,
                        "public_key_hash": latest_ratchet_pkh,
                    }
                )
            if not _existing_tip:
                _existing_tip = await self.config.mongo.async_db.key_event_log.find_one(
                    {"anchor_public_key": _peer_k0}, sort=[("counter", -1)]
                )
        if _existing_tip:
            _next_counter = _existing_tip.get("counter") or (
                await self.config.mongo.async_db.key_event_log.count_documents(
                    {
                        "anchor_public_key": _peer_k0,
                        "_id": {"$lte": _existing_tip["_id"]},
                    }
                )
            )
            _next_counter += 1
        else:
            _next_counter = 1

        for txn in parsed_ratchet:
            _is_bridge = getattr(txn, "relationship", "") == "peer-kel-branch"
            if not txn.prev_public_key_hash and not _is_bridge:
                await self.config.mongo.async_db.miner_transactions.replace_one(
                    {"id": txn.transaction_signature}, txn.to_dict(), upsert=True
                )
            else:
                await self.config.mongo.async_db.key_event_log.replace_one(
                    {"public_key_hash": txn.public_key_hash},
                    {
                        "counter": _next_counter,
                        "id": txn.transaction_signature,
                        "anchor_public_key": _peer_k0,
                        "public_key": txn.public_key,
                        "public_key_hash": txn.public_key_hash,
                        "prerotated_key_hash": txn.prerotated_key_hash,
                        "txn": txn.to_dict(),
                        "timestamp": time.time(),
                    },
                    upsert=True,
                )
                _next_counter += 1

        # Find ratchet anchor
        _anchor_key_event = None
        _anchor_counter = 0
        if _peer_k0:
            _doc = await self.config.mongo.async_db.key_event_log.find_one(
                {"anchor_public_key": _peer_k0}, {"_id": 0}, sort=[("counter", -1)]
            )
            if _doc:
                _anchor_key_event = _KE(_Txn.from_dict(_doc["txn"]))
                _anchor_counter = _doc.get("counter", 0)

        _has_kel = bool(_anchor_key_event)
        if not _has_kel and _peer_k0:
            _has_kel = bool(
                await self.config.mongo.async_db.miner_transactions.find_one(
                    {"public_key": _peer_k0, "prev_public_key_hash": ""}
                )
                or await self.config.mongo.async_db.blocks.find_one(
                    {
                        "transactions.public_key": _peer_k0,
                        "transactions.prev_public_key_hash": "",
                    }
                )
            )

        if not _has_kel:
            if not _retried and _peer_k0:
                self.config.app_log.warning(
                    "ratchet: no local KEL inception for %s — requesting a "
                    "full KEL resync before giving up  (peer=%s)",
                    _peer_k0,
                    peer_username,
                )

                async def _kel_reauth(_kel_chain, _stream=stream):
                    if _kel_chain:
                        await self._process_ratchet_auth(
                            _stream,
                            _kel_chain,
                            ratchet_public_key,
                            latest_ratchet_pkh,
                            _retried=True,
                        )

                await self._request_peer_kel_resync(stream, reauth_cb=_kel_reauth)
                return None
            await self.remove_peer(
                stream,
                reason="ratchet: no KEL inception found — peer must send inception in connect",
            )
            return None

        # Username check
        getattr(stream.peer.identity, "username", "")
        if _peer_ia:
            _ia_pub = (_peer_ia or {}).get("public_key", "")
            if _ia_pub and _peer_k0 and _ia_pub != _peer_k0:
                await self.remove_peer(stream, reason="ratchet: username/K0 mismatch")
                return None

        # Signing key authorization
        signing_address = str(
            P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(ratchet_public_key))
        )
        authorized = (
            _anchor_key_event is not None
            and getattr(_anchor_key_event.txn, "prerotated_key_hash", "")
            == signing_address
        )
        if not authorized:
            await self.remove_peer(
                stream, reason="ratchet: signing key not authorized by KEL"
            )
            return None

        _anchor_source = "ratchet" if _anchor_key_event else "inception"
        self.config.app_log.info(
            "  [OK]   KEL verified via %s anchor  (tip=%d, peer=%s)",
            _anchor_source,
            _anchor_counter,
            peer_username,
        )
        return (_peer_k0, _has_kel, _anchor_source, _anchor_counter)

    async def _handle_kel_connect(self, stream, params):
        """Server-side: process KEL connect (phase 1 of 2).

        Receives client ECDH pub + ratchet data, stores ratchet chain, sends
        'connected' plaintext (server ECDH pub only), activates session cipher,
        then sends encrypted 'request_sig' asking client to cross-sign.
        """
        peer_host = stream.peer.host
        peer_username = getattr(stream.peer.identity, "username", peer_host)

        self.config.app_log.info(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  KEL Auth (ECDH exchange)  <  %s (%s)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            peer_username,
            peer_host,
        )

        peer_ecdh_pub = params.get("ecdh_public_key", "")
        ratchet_chain = params.get("ratchet_chain") or []
        latest_ratchet_pkh = params.get("latest_ratchet_pkh", "")

        if not peer_ecdh_pub:
            return await self.remove_peer(
                stream, reason="connect: missing ecdh_public_key"
            )

        # Store ratchet chain into key_event_log (no signature verification yet —
        # we haven't exchanged nonces, so there's nothing meaningful to sign yet).
        # We'll fully authenticate in sig_response.
        parsed_ratchet = []
        from yadacoin.core.identityannouncement import IdentityAnnouncement as _IApeer
        from yadacoin.core.transaction import Transaction as _Txn

        for txn_dict in ratchet_chain:
            try:
                parsed_ratchet.append(_Txn.from_dict(txn_dict))
            except Exception as exc:
                return await self.remove_peer(
                    stream, reason=f"connect: malformed ratchet txn — {exc}"
                )

        _peer_ia = await _IApeer.get_by_username(
            getattr(stream.peer.identity, "username", "") or "", include_mempool=True
        )
        _peer_k0 = (_peer_ia or {}).get("public_key") or (
            parsed_ratchet[0].public_key if parsed_ratchet else None
        )

        # Anchor to the on-chain identity announcement if this peer is
        # configured with one; walk the KEL from the anchor to its most current
        # entry and use that as the KEL anchor for tip discovery below.
        _ia_id = getattr(stream.peer, "identity_announcement", None)
        if _ia_id:
            _anchor_doc = await _IApeer.get_by_transaction_id(_ia_id)
            if _anchor_doc:
                _anchor_pub = _anchor_doc.get("public_key")
                if _anchor_pub:
                    _peer_k0 = _anchor_pub

        # Determine client's current KEL tip (what we'll put in the nonce)
        _client_kel_tip_pkh = ""
        if _peer_k0:
            _tip = await self.config.mongo.async_db.key_event_log.find_one(
                {"anchor_public_key": _peer_k0}, sort=[("counter", -1)]
            )
            if _tip:
                _client_kel_tip_pkh = _tip.get("public_key_hash", "")
        # Fall back to the latest entry in the incoming ratchet_chain itself
        if not _client_kel_tip_pkh and parsed_ratchet:
            _client_kel_tip_pkh = parsed_ratchet[-1].public_key_hash or ""

        # Generate server ECDH keypair
        _ecdh_priv, _ecdh_pub = SessionCipher.generate_keypair()

        # Derive session cipher — hold it, activate AFTER sending 'connected'
        _session_cipher = (
            SessionCipher.derive(_ecdh_priv, peer_ecdh_pub, "")
            if peer_ecdh_pub
            else None
        )

        # Send 'connected' PLAINTEXT (client needs server_ecdh_pub to derive cipher)
        await self.write_params(
            stream,
            "connected",
            {
                "peer": self.config.peer.to_dict(),
                "ecdh_public_key": _ecdh_pub,
                "identity_announcement": self.config.inception.to_dict(),
            },
        )

        # Activate session cipher — all subsequent messages are encrypted
        if _session_cipher:
            stream.session_cipher = _session_cipher

        # Build server's auth material for the encrypted request_sig.
        # Advances *this peer's own branch* of our off-chain ratchet — not
        # the global chain — so nothing generated for other peers is ever
        # exposed here, and nothing generated here leaks to other peers.
        _peer_identity_announcement = stream.peer.identity_announcement
        (
            _auth_priv,
            _auth_pub,
            _conf_priv,
            _conf_pub,
            tpkh,
            _is_new_branch,
        ) = await self.config.kel_manager.advance_peer_auth_ratchet(
            _peer_identity_announcement
        )

        # Nonce the server signs: client_ecdh_pub + server_kel_tip_pkh
        # Tells the client: "I received your ECDH key and my KEL position is X"
        # (position within *this peer's branch*, i.e. Kp0-anchored, not global)
        _k0_pub = await self.config.kel_manager.peer_branch_anchor_pub(
            _peer_identity_announcement
        )
        _server_kel_tip_pkh = ""
        if _k0_pub:
            _srv_tip = await self.config.mongo.async_db.key_event_log.find_one(
                {"anchor_public_key": _k0_pub}, sort=[("counter", -1)]
            )
            if _srv_tip:
                _server_kel_tip_pkh = _srv_tip.get("public_key_hash", "")

        # Server signs (client_ecdh_pub + server_kel_tip_pkh) with its ratchet key
        _server_nonce_str = peer_ecdh_pub + _server_kel_tip_pkh
        _server_signed = NodeKeyRotationManager._sign(_auth_priv, _server_nonce_str)
        _server_conf_signed = (
            NodeKeyRotationManager._sign(_conf_priv, _server_nonce_str)
            if _conf_priv
            else None
        )

        # Build server's ratchet_chain delta (client told us what they have via latest_ratchet_pkh)
        _srv_ratchet_chain = []
        if _k0_pub:
            skip_after_counter = -1
            if latest_ratchet_pkh:
                _tip = await self.config.mongo.async_db.key_event_log.find_one(
                    {
                        "anchor_public_key": _k0_pub,
                        "public_key_hash": latest_ratchet_pkh,
                    }
                )
                if _tip:
                    skip_after_counter = _tip.get("counter") or (
                        await self.config.mongo.async_db.key_event_log.count_documents(
                            {"anchor_public_key": _k0_pub, "_id": {"$lte": _tip["_id"]}}
                        )
                    )
            _cursor = self.config.mongo.async_db.key_event_log.find(
                {"anchor_public_key": _k0_pub, "counter": {"$gt": skip_after_counter}},
                {"_id": 0, "txn": 1},
            ).sort("counter", 1)
            _srv_ratchet_chain = [
                e["txn"] for e in await _cursor.to_list(length=None) if "txn" in e
            ]

            if _is_new_branch:
                bridge = await self.config.mongo.async_db.key_event_log.find_one(
                    {"anchor_public_key": _auth_pub, "counter": 0}
                )
                if bridge and "txn" in bridge:
                    _srv_ratchet_chain.insert(0, bridge["txn"])

        # Store state needed by sig_response handler
        stream._peer_ecdh_pub = peer_ecdh_pub
        stream._peer_k0 = _peer_k0
        stream._server_ecdh_pub = _ecdh_pub
        stream._client_kel_tip_pkh_expected = _client_kel_tip_pkh
        stream._connect_ratchet_chain = ratchet_chain
        stream._connect_latest_ratchet_pkh = latest_ratchet_pkh

        # Send encrypted 'request_sig'
        request_payload = {
            # Server proves its identity (client verifies this before signing back)
            "server_signed": _server_signed,
            "server_confirming_signed": _server_conf_signed,
            "ratchet_public_key": _auth_pub,
            "confirming_public_key": _conf_pub,
            "ratchet_chain": _srv_ratchet_chain,
            "server_kel_tip_pkh": _server_kel_tip_pkh,
            # What we want the client to sign: server_ecdh_pub + client_kel_tip_pkh
            "server_ecdh_pub": _ecdh_pub,
            "client_kel_tip_pkh": _client_kel_tip_pkh,
            # What we now have of client's chain (tip hint for next connect)
            "latest_ratchet_pkh": _client_kel_tip_pkh,
        }
        # A brand-new peer relationship has no other way to validate the
        # bridge entry's on-chain parent (K_n) — they likely haven't synced
        # our blocks yet, since block sync only starts after this handshake
        # completes. Send the single transaction that establishes K_n (the
        # inception itself, or our latest on-chain/mempool re-anchor) this
        # one time; every later reconnect only needs the small
        # mempool-pending slice, same as before.
        kel_chain = (
            await self._get_kel_anchor_chain()
            if _is_new_branch
            else await self._get_pending_kel_chain()
        )
        if kel_chain:
            request_payload["kel_chain"] = kel_chain

        await self.write_params(stream, "request_sig", request_payload)
        self.config.app_log.info(
            "  [>]   request_sig sent (encrypted)  (peer=%s, new_branch=%s)",
            peer_username,
            _is_new_branch,
        )

    async def connected(self, body, stream):
        """Client-side handler: processes server's 'connected' (ECDH-only, phase 1 of 2).

        Derives session cipher from server's ECDH pub.  All subsequent messages
        are encrypted.  Waits for 'request_sig' to complete mutual auth.
        """
        self.ensure_protocol_version(body, stream)
        params = body.get("params", {})

        server_ecdh_pub = params.get("ecdh_public_key", "")
        if not server_ecdh_pub:
            return await self.remove_peer(
                stream, reason="connected: missing ecdh_public_key"
            )

        # Derive session cipher — all subsequent traffic (including request_sig) will be encrypted
        _ecdh_priv = getattr(stream, "_ecdh_priv", None)
        if _ecdh_priv:
            stream.session_cipher = SessionCipher.derive(
                _ecdh_priv, server_ecdh_pub, ""
            )
        from yadacoin.core.identity import Identity

        # Store server's ECDH pub so request_sig handler can build the client nonce
        stream._server_ecdh_pub = server_ecdh_pub
        identity_announcement = params["identity_announcement"]
        await self.config.mongo.async_db.miner_transactions.replace_one(
            {"id": identity_announcement["id"]}, identity_announcement, upsert=True
        )
        identity = params["identity_announcement"]["relationship"]["identity"]
        stream.peer.identity = Identity(
            public_key=params["identity_announcement"]["public_key"],
            username=identity["username"],
            username_signature=identity["username_signature"],
        )
        peer_username = getattr(stream.peer.identity, "username") or stream.peer.host
        self.config.app_log.info(
            "  [>]   session cipher derived, awaiting encrypted request_sig  (%s)",
            peer_username,
        )

    async def request_sig(self, body, stream):
        """Client-side handler: receives encrypted auth challenge from server.

        Verifies server's identity (server signed client_ecdh_pub + server_kel_tip_pkh),
        then signs back (server_ecdh_pub + client_kel_tip_pkh) with client's ratchet key.
        """
        params = body.get("params", {})
        peer_host = stream.peer.host
        peer_username = getattr(stream.peer.identity, "username", peer_host)

        server_signed = params.get("server_signed", "")
        server_conf_signed = params.get("server_confirming_signed", "")
        ratchet_public_key = params.get("ratchet_public_key", "")
        confirming_public_key = params.get("confirming_public_key", "")
        ratchet_chain = params.get("ratchet_chain") or []
        server_kel_tip_pkh = params.get("server_kel_tip_pkh", "")
        latest_ratchet_pkh = params.get("latest_ratchet_pkh", "")
        # The nonce the server wants us to sign
        server_ecdh_pub = params.get("server_ecdh_pub", "") or getattr(
            stream, "_server_ecdh_pub", ""
        )
        client_kel_tip_pkh = params.get("client_kel_tip_pkh", "")

        if not server_signed or not ratchet_public_key:
            return await self.remove_peer(
                stream, reason="request_sig: missing server auth fields"
            )

        # Verify server signed (client_ecdh_pub + server_kel_tip_pkh)
        _client_ecdh_pub = getattr(stream, "_ecdh_pub_sent", "") or ""
        _server_nonce = _client_ecdh_pub + server_kel_tip_pkh
        if not verify_signature(
            base64.b64decode(server_signed),
            _server_nonce.encode(),
            bytes.fromhex(ratchet_public_key),
        ):
            return await self.remove_peer(
                stream, reason="request_sig: server signature invalid"
            )
        self.config.app_log.info(
            "  [OK]   Server cross-signature verified  (%s)", peer_username
        )

        if server_conf_signed and confirming_public_key:
            if not verify_signature(
                base64.b64decode(server_conf_signed),
                _server_nonce.encode(),
                bytes.fromhex(confirming_public_key),
            ):
                return await self.remove_peer(
                    stream, reason="request_sig: server confirming signature invalid"
                )
            self.config.app_log.info("  [OK]   Server confirming signature verified")

        # Accept server's pending KEL chain
        server_kel_chain = params.get("kel_chain") or []
        if server_kel_chain:
            await self._accept_peer_kel_chain(server_kel_chain)

        # Verify server's KEL authorization
        result = await self._process_ratchet_auth(
            stream, ratchet_chain, confirming_public_key, latest_ratchet_pkh
        )
        if result is None:
            return  # remove_peer already called

        # Client signs (server_ecdh_pub + client_kel_tip_pkh) with its ratchet
        # key — advanced within *this server's own branch* of our off-chain
        # ratchet, so nothing generated for other peers is exposed here.
        _peer_username_sig = stream.peer.identity.username_signature
        (
            _auth_priv,
            _auth_pub,
            _conf_priv,
            _conf_pub,
            tpkh,
            _is_new_branch,
        ) = await self.config.kel_manager.advance_peer_auth_ratchet(_peer_username_sig)
        _client_nonce_str = server_ecdh_pub + client_kel_tip_pkh
        _client_signed = NodeKeyRotationManager._sign(_auth_priv, _client_nonce_str)
        _client_conf_signed = (
            NodeKeyRotationManager._sign(_conf_priv, _client_nonce_str)
            if _conf_priv
            else None
        )

        # Build our ratchet chain for the server, scoped to this peer's
        # branch (server told us what it already has via latest_ratchet_pkh)
        _k0_self = await self.config.kel_manager.peer_branch_anchor_pub(
            _peer_username_sig
        )
        _client_ratchet_chain = []
        if _k0_self:
            skip_after_counter = 0
            if latest_ratchet_pkh:
                _tip = await self.config.mongo.async_db.key_event_log.find_one(
                    {
                        "anchor_public_key": _k0_self,
                        "public_key_hash": latest_ratchet_pkh,
                    }
                )
                if _tip:
                    skip_after_counter = _tip.get("counter") or (
                        await self.config.mongo.async_db.key_event_log.count_documents(
                            {
                                "anchor_public_key": _k0_self,
                                "_id": {"$lte": _tip["_id"]},
                            }
                        )
                    )
            _rc = self.config.mongo.async_db.key_event_log.find(
                {"anchor_public_key": _k0_self, "counter": {"$gt": skip_after_counter}},
                {"_id": 0, "txn": 1},
            ).sort("counter", 1)
            _client_ratchet_chain = [
                e["txn"] for e in await _rc.to_list(length=None) if "txn" in e
            ]

        # A brand-new peer relationship has no other way to validate our
        # bridge entry's on-chain parent (K_n) — the server likely hasn't
        # synced our blocks yet. Send the single transaction that
        # establishes K_n this one time; every later reconnect only needs
        # the small mempool-pending slice, same as before.
        sig_response_payload = {
            "client_signed": _client_signed,
            "client_confirming_signed": _client_conf_signed,
            "ratchet_public_key": _auth_pub,
            "confirming_public_key": _conf_pub,
            "ratchet_chain": _client_ratchet_chain,
        }
        kel_chain = (
            await self._get_kel_anchor_chain()
            if _is_new_branch
            else await self._get_pending_kel_chain()
        )
        if kel_chain:
            sig_response_payload["kel_chain"] = kel_chain

        await self.write_params(stream, "sig_response", sig_response_payload)
        self.config.app_log.info(
            "  [>]   sig_response sent (encrypted)  (%s, new_branch=%s)",
            peer_username,
            _is_new_branch,
        )

    async def sig_response(self, body, stream):
        """Server-side handler: verifies client's cross-signature and completes mutual auth.

        Client signed (server_ecdh_pub + client_kel_tip_pkh) with their ratchet key.
        Verify this then mark both sides authenticated.
        """
        params = body.get("params", {})
        peer_host = stream.peer.host
        peer_username = getattr(stream.peer.identity, "username", peer_host)

        client_signed = params.get("client_signed", "")
        client_conf_signed = params.get("client_confirming_signed", "")
        ratchet_public_key = params.get("ratchet_public_key", "")
        confirming_public_key = params.get("confirming_public_key", "")
        ratchet_chain = params.get("ratchet_chain") or []

        if not client_signed or not ratchet_public_key:
            return await self.remove_peer(
                stream, reason="sig_response: missing auth fields"
            )

        # Accept the client's KEL anchor entry (sent on first-ever contact,
        # or their regular mempool-pending chain otherwise) so the upcoming
        # _process_ratchet_auth call below has something to validate the
        # client's bridge entry's on-chain parent against.
        client_kel_chain = params.get("kel_chain") or []
        if client_kel_chain:
            await self._accept_peer_kel_chain(client_kel_chain)

        # Reconstruct the nonce: server_ecdh_pub + client_kel_tip_pkh
        _server_ecdh_pub = getattr(stream, "_server_ecdh_pub", "")
        _client_kel_tip_pkh = getattr(stream, "_client_kel_tip_pkh_expected", "")
        _client_nonce_str = _server_ecdh_pub + _client_kel_tip_pkh

        if not verify_signature(
            base64.b64decode(client_signed),
            _client_nonce_str.encode(),
            bytes.fromhex(ratchet_public_key),
        ):
            return await self.remove_peer(
                stream, reason="sig_response: client signature invalid"
            )
        self.config.app_log.info(
            "  [OK]   Client cross-signature verified  (%s)", peer_username
        )

        if client_conf_signed and confirming_public_key:
            if not verify_signature(
                base64.b64decode(client_conf_signed),
                _client_nonce_str.encode(),
                bytes.fromhex(confirming_public_key),
            ):
                return await self.remove_peer(
                    stream, reason="sig_response: client confirming signature invalid"
                )
            self.config.app_log.info("  [OK]   Client confirming signature verified")

        # Full KEL auth verification on the ratchet chain
        _connect_ratchet_chain = (
            getattr(stream, "_connect_ratchet_chain", []) or ratchet_chain
        )
        _connect_latest_ratchet_pkh = getattr(stream, "_connect_latest_ratchet_pkh", "")
        result = await self._process_ratchet_auth(
            stream,
            _connect_ratchet_chain,
            confirming_public_key,
            _connect_latest_ratchet_pkh,
        )
        if result is None:
            return  # remove_peer already called

        stream.peer.authenticated = True
        self.config.app_log.info(
            "  [OK]   %s mutually authenticated via cross-signing\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            peer_username,
        )
        await self.send_block_to_peer(self.config.LatestBlock.block, stream)
        await self.get_next_block(self.config.LatestBlock.block, stream)

    # ── end KEL cross-signing helpers ─────────────────────────────────────────

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
                self.config.app_log.info(
                    "NodeSocketClient.connect: skipping %s %s — super().connect returned None",
                    peer.__class__.__name__,
                    getattr(peer, peer.id_attribute),
                )
                return

            # Generate ephemeral ECDH keypair
            _ecdh_priv, _ecdh_pub = SessionCipher.generate_keypair()
            stream._ecdh_priv = _ecdh_priv

            # Auth keys are used in request_sig/sig_response (encrypted), not here

            # Store our ECDH pub so request_sig handler can reconstruct the server nonce
            stream._ecdh_pub_sent = _ecdh_pub

            connect_payload = {
                "peer": self.config.peer.to_dict(),
                "ecdh_public_key": _ecdh_pub,
                # No signatures in phase 1 — auth happens in encrypted request_sig/sig_response
            }

            # Our ratchet chain, scoped to *this peer's own branch* (server
            # will use it to determine client KEL tip for the nonce). Since
            # each peer gets an isolated branch rooted at its own bridge
            # entry, this is bounded by how many times we've connected to
            # this specific peer — never the global handshake history shared
            # with every other peer.

            _k0_self = await self.config.kel_manager.peer_branch_anchor_pub(
                peer.identity_announcement
            )
            _is_first_contact = bool(peer.identity_announcement) and not _k0_self
            if _k0_self:
                _rc = self.config.mongo.async_db.key_event_log.find(
                    {"anchor_public_key": _k0_self}, {"_id": 0, "txn": 1}
                ).sort("counter", 1)
                connect_payload["ratchet_chain"] = [
                    e["txn"] for e in await _rc.to_list(length=None) if "txn" in e
                ]

            # A brand-new peer relationship has no other way to validate our
            # bridge entry's on-chain parent (K_n) before block sync has even
            # started, so send the single transaction that establishes K_n
            # (the inception itself, or our latest on-chain/mempool
            # re-anchor) this one time; every later reconnect only needs the
            # small mempool-pending slice, same as before.
            kel_chain = (
                await self._get_kel_anchor_chain()
                if _is_first_contact
                else await self._get_pending_kel_chain()
            )
            if kel_chain:
                connect_payload["kel_chain"] = kel_chain
            connect_payload["identity_announcement"] = self.config.inception.to_dict()
            await self.write_params(stream, "connect", connect_payload)
            asyncio.create_task(self.send_keepalive(stream))
            await self.wait_for_data(stream)
        except StreamClosedError:
            Config().app_log.error(
                "Cannot connect to {}: {}".format(
                    peer.__class__.__name__, peer.to_json()
                )
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
