import base64
import time
from uuid import uuid4

from coincurve import verify_signature
from tornado.iostream import StreamClosedError

from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
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
from yadacoin.core.transaction import Transaction
from yadacoin.core.transactionutils import TU
from yadacoin.enums.modes import MODES
from yadacoin.enums.peertypes import PEER_TYPES
from yadacoin.tcpsocket.base import BaseRPC, RPCSocketClient, RPCSocketServer

class NodeServerDisconnectTracker:
    by_host = {}
    by_reason = {}

    def to_dict(self):
        return {"by_host": self.by_host, "by_reason": self.by_reason}


class NodeServerNewTxnTracker:
    by_host = {}
    by_txn_id = {}

    def to_dict(self):
        #return {"by_host": self.by_host, "by_txn_id": self.by_txn_id}
        return {"by_host": self.by_host}


class NodeClientDisconnectTracker:
    by_host = {}
    by_reason = {}

    def to_dict(self):
        return {"by_host": self.by_host, "by_reason": self.by_reason}


class NodeClientNewTxnTracker:
    by_host = {}
    by_txn_id = {}

    def to_dict(self):
        #return {"by_host": self.by_host, "by_txn_id": self.by_txn_id}
        return {"by_host": self.by_host}


class NodeRPC(BaseRPC):
    retry_messages = {}
    confirmed_peers = set()

    def __init__(self):
        super(NodeRPC, self).__init__()
        self.config = Config()

    config = None

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
            scheme = "wss" if service_provider.peer.secure else "ws"
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
        payload = body.get("params", {})
        transaction = payload.get("transaction")
        if transaction:
            txn = Transaction.from_dict(transaction)
            if stream.peer.protocol_version > 2:
                await self.write_result(
                    stream, "newtxn_confirmed", body.get("params", {}), body["id"]
                )
        elif payload.get("hash"):
            txn = Transaction.from_dict(payload)
            if stream.peer.protocol_version > 2:
                await self.write_result(
                    stream,
                    "newtxn_confirmed",
                    {"transaction": body.get("params", {})},
                    body["id"],
                )
        else:
            self.config.app_log.info("newtxn, no payload")
            return

        self.newtxn_tracker.by_host[stream.peer.host] = (
            self.newtxn_tracker.by_host.get(stream.peer.host, 0) + 1
        )
        self.newtxn_tracker.by_txn_id[txn.transaction_signature] = (
            self.newtxn_tracker.by_txn_id.get(txn.transaction_signature, 0) + 1
        )

        self.config.processing_queues.transaction_queue.add(
            TransactionProcessingQueueItem(txn, stream)
        )

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
        item = self.config.processing_queues.transaction_queue.pop()
        i = 0  # max loops
        while item:
            self.config.processing_queues.transaction_queue.inc_num_items_processed()
            await self.process_transaction_queue_item(item)

            i += 1
            if i >= 100:
                self.config.app_log.info(
                    "process_transaction_queue: max loops exceeded, exiting"
                )
                return

            item = self.config.processing_queues.transaction_queue.pop()

    async def process_transaction_queue_item(self, item):
        txn = item.transaction
        stream = item.stream

        check_max_inputs = False
        if self.config.LatestBlock.block.index > CHAIN.CHECK_MAX_INPUTS_FORK:
            check_max_inputs = True
        try:
            await txn.verify(check_input_spent=True, check_max_inputs=check_max_inputs)
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

        async def make_gen(streams):
            for stream in streams:
                yield stream

        async for peer_stream in self.config.peer.get_inbound_streams():
            if peer_stream.peer.rid == stream.peer.rid:
                self.config.app_log.debug(
                    f"Skipping peer {stream.peer.rid} in inbound stream as it is the sender."
                )
                continue
            elif (stream.peer.rid, "newtxn", txn.transaction_signature) in self.confirmed_peers:
                self.config.app_log.debug(
                    f"Skipping peer {stream.peer.rid} in inbound stream as it has already confirmed the transaction."
                )
                continue
            if peer_stream.peer.protocol_version > 1:
                self.retry_messages[
                    (peer_stream.peer.rid, "newtxn", txn.transaction_signature)
                ] = {"transaction": txn.to_dict()}

        async for peer_stream in make_gen(
            await self.config.peer.get_outbound_streams()
        ):
            if peer_stream.peer.rid == stream.peer.rid:
                self.config.app_log.debug(
                    f"Skipping peer {stream.peer.rid} in outbound stream as it is the sender."
                )
                continue
            elif (stream.peer.rid, "newtxn", txn.transaction_signature) in self.confirmed_peers:
                self.config.app_log.debug(
                    f"Skipping peer {stream.peer.rid} in outbound stream as it has already confirmed the transaction."
                )
                continue
            if peer_stream.peer.protocol_version > 1:
                self.config.nodeClient.retry_messages[
                    (peer_stream.peer.rid, "newtxn", txn.transaction_signature)
                ] = {"transaction": txn.to_dict()}

    async def newtxn_confirmed(self, body, stream):
        result = body.get("result", {})
        transaction = Transaction.from_dict(result.get("transaction"))

        if (
            stream.peer.rid,
            "newtxn",
            transaction.transaction_signature,
        ) in self.retry_messages:
            del self.retry_messages[
                (stream.peer.rid, "newtxn", transaction.transaction_signature)
            ]

        self.confirmed_peers.add((stream.peer.rid, "newtxn", transaction.transaction_signature))
        self.config.app_log.debug(
            f"Transaction {transaction.transaction_signature} confirmed by peer {stream.peer.rid}. Peer added to the list of confirmed peers."
        )

    async def newblock(self, body, stream):
        payload = body.get("params", {}).get("payload", {})
        if not payload.get("block"):
            self.config.app_log.info("newblock, no payload")
            return

        self.config.processing_queues.block_queue.add(
            BlockProcessingQueueItem(Blockchain(payload.get("block")), stream, body)
        )
        if stream.peer.protocol_version > 1:
            await self.config.nodeShared.write_result(
                stream, "newblock_confirmed", body.get("params", {}), body["id"]
            )

    async def newblock_confirmed(self, body, stream):
        payload = body.get("result", {}).get("payload")
        block = await Block.from_dict(payload.get("block"))

        if (stream.peer.rid, "newblock", block.hash) in self.retry_messages:
            del self.retry_messages[(stream.peer.rid, "newblock", block.hash)]

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
        await self.config.nodeShared.write_params(
            stream,
            "getblocks",
            {"start_index": start_block["index"] + 1, "end_index": end_index - 1},
        )

    async def send_mempool(self, peer_stream):
        check_max_inputs = False
        if self.config.LatestBlock.block.index > CHAIN.CHECK_MAX_INPUTS_FORK:
            check_max_inputs = True
        async for x in self.config.mongo.async_db.miner_transactions.find({}):
            txn = Transaction.from_dict(x)
            try:
                await txn.verify(check_max_inputs=check_max_inputs)
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
        self.config.app_log.info(
            f"Sent block with index {block.index} to peer {peer_stream.peer.rid}."
        )
        if peer_stream.peer.protocol_version > 1:
            self.retry_messages[
                (peer_stream.peer.rid, "newblock", block.hash)
            ] = payload

    async def get_next_block(self, block):
        async for peer_stream in self.config.peer.get_sync_peers():
            await self.write_params(peer_stream, "getblock", {"index": block.index + 1})

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
        # get blocks should be done only by syncing peers
        result = body.get("result")
        blocks = result.get("blocks")
        if stream.peer.protocol_version > 1:
            await self.write_result(
                stream, "blocksresponse_confirmed", body.get("result", {}), body["id"]
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
        if self.config.LatestBlock.block.index >= CHAIN.REQUIRE_NODE_VERSION_566:
            if generic_peer.node_version[0] < 6:
                await self.write_result(stream, "version_too_old", {}, body["id"])
                stream.close()
                return {}
            elif generic_peer.node_version[0] == 6 and generic_peer.node_version[1] < 3:
                await self.write_result(stream, "version_too_old", {}, body["id"])
                stream.close()
                return {}
            elif (
                generic_peer.node_version[0] == 6
                and generic_peer.node_version[1] == 3
                and generic_peer.node_version[2] < 3
            ):
                await self.write_result(stream, "version_too_old", {}, body["id"])
                stream.close()
                return {}
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
                stream, reason="NodeRPC challenge: ensure_protocol version"
            )
        try:
            params = body.get("params", {})
            challenge = params.get("token")
            signed_challenge = TU.generate_signature(challenge, self.config.private_key)
        except:
            return await self.remove_peer(
                stream, reason="NodeRPC challenge: generate_signature"
            )
        if stream.peer.protocol_version > 1:
            await self.write_params(
                stream,
                "authenticate",
                {
                    "peer": self.config.peer.to_dict(),
                    "signed_challenge": signed_challenge,
                },
            )
        else:
            await self.write_result(
                stream,
                "authenticate",
                {
                    "peer": self.config.peer.to_dict(),
                    "signed_challenge": signed_challenge,
                },
                body["id"],
            )
        stream.peer.token = str(uuid4())
        await self.write_params(
            stream,
            "challenge",
            {"peer": self.config.peer.to_dict(), "token": stream.peer.token},
        )

    async def authenticate(self, body, stream):
        self.ensure_protocol_version(body, stream)
        if stream.peer.protocol_version > 1:
            params = body.get("params", {})
        else:
            params = body.get("result", {})
        signed_challenge = params.get("signed_challenge")
        result = verify_signature(
            base64.b64decode(signed_challenge),
            stream.peer.token.encode(),
            bytes.fromhex(stream.peer.identity.public_key),
        )
        if result:
            stream.peer.authenticated = True
            self.config.app_log.info(
                "Authenticated {}: {}".format(
                    stream.peer.__class__.__name__, stream.peer.to_json()
                )
            )
            await self.send_block_to_peer(self.config.LatestBlock.block, stream)
            #await self.get_next_block(self.config.LatestBlock.block)
        else:
            stream.close()

    def ensure_protocol_version(self, body, stream):
        params = body.get("params", {})
        peer = params.get("peer", {})
        protocol_version = peer.get("protocol_version", 1)
        stream.peer.protocol_version = protocol_version

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

            await self.write_params(
                stream, "connect", {"peer": self.config.peer.to_dict()}
            )

            stream.peer.token = str(uuid4())
            await self.write_params(
                stream,
                "challenge",
                {"peer": self.config.peer.to_dict(), "token": stream.peer.token},
            )

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
                stream, reason="NodeSocketClient challenge: ensure_protocol_version"
            )
        try:
            params = body.get("params", {})
            challenge = params.get("token")
            signed_challenge = TU.generate_signature(challenge, self.config.private_key)
        except:
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
                },
            )
        else:
            await self.write_result(
                stream,
                "authenticate",
                {
                    "peer": self.config.peer.to_dict(),
                    "signed_challenge": signed_challenge,
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
