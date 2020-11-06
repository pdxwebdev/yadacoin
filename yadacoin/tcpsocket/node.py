import base64
import json
import time
from uuid import uuid4

from tornado.iostream import StreamClosedError
from coincurve import verify_signature

from yadacoin.tcpsocket.base import RPCSocketServer, RPCSocketClient, SharedBaseMethods
from yadacoin.core.chain import CHAIN
from yadacoin.core.block import Block
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.peer import Peer, Seed, SeedGateway, ServiceProvider, User
from yadacoin.core.config import get_config
from yadacoin.core.transactionutils import TU
from yadacoin.core.identity import Identity
from yadacoin.core.transaction import Transaction
from yadacoin.core.blockchain import Blockchain


class NodeSocketServer(RPCSocketServer):

    def __init__(self):
        super(NodeSocketServer, self).__init__()
        self.config = get_config()

    async def getblocks(self, body, stream):
        # get blocks should be done only by syncing peers
        params = body.get('params')
        start_index = int(params.get("start_index", 0))
        end_index = min(int(params.get("end_index", 0)), start_index + CHAIN.MAX_BLOCKS_PER_MESSAGE)
        if start_index > self.config.LatestBlock.block.index:
            result = []
        else:
            blocks = self.config.mongo.async_db.blocks.find({
                '$and': [
                    {'index':
                        {'$gte': start_index}

                    },
                    {'index':
                        {'$lte': end_index}
                    }
                ]
            }, {'_id': 0}).sort([('index',1)])
            result = await blocks.to_list(length=CHAIN.MAX_BLOCKS_PER_MESSAGE)
        return result
    
    async def newblock(self, body, stream):
        await RPCBase.newblock(self, body, stream)
    
    async def newtxn(self, body, stream):
        await RPCBase.newtxn(self, body, stream)

    async def getblock(self, body, stream):
        await RPCBase.getblock(self, body, stream)
    
    async def blockresponse(self, body, stream):
        await RPCBase.blockresponse(self, body, stream)
    
    async def authenticate(self, body, stream):
        await RPCBase.authenticate(self, body, stream)
    
    async def connect(self, body, stream):
        await RPCBase.connect(self, body, stream)
    
    async def challenge(self, body, stream):
        await RPCBase.challenge(self, body, stream)


class NodeSocketClient(RPCSocketClient):

    def __init__(self):
        super(NodeSocketClient, self).__init__()
        self.config = get_config()

    async def connect(self, peer: Peer):
        try:
            stream = await super(NodeSocketClient, self).connect(peer)
            if stream:
                await self.write_params(stream, 'connect', {
                    'peer': self.config.peer.to_dict()
                })

                stream.peer.token = str(uuid4())
                await self.write_params(stream, 'challenge', {
                    'token': stream.peer.token
                })

                await self.wait_for_data(stream)
        except StreamClosedError:
            get_config().app_log.error('Cannot connect to {}: {}'.format(peer.__class__.__name__, peer.to_json()))
    
    async def challenge(self, body, stream):
        challenge =  body.get('params', {}).get('token')
        signed_challenge = TU.generate_signature(challenge, self.config.private_key)
        await self.write_result(stream, 'authenticate', {
            'peer': self.config.peer.to_dict(),
            'signed_challenge': signed_challenge
        })
    
    async def authenticate(self, body, stream):
        await RPCBase.authenticate(self, body, stream)
    
    async def capacity(self, body, stream):
        NodeSocketClient.outbound_ignore[stream.peer.__class__.__name__][stream.peer.rid] = stream.peer
        self.config.app_log.warning('{} at full capacity: {}'.format(stream.peer.__class__.__name__, stream.peer.to_json()))
    
    async def newblock(self, body, stream):
        await RPCBase.newblock(self, body, stream)
    
    async def newtxn(self, body, stream):
        await RPCBase.newtxn(self, body, stream)

    async def getblock(self, body, stream):
        await RPCBase.getblock(self, body, stream)
    
    async def blockresponse(self, body, stream):
        await RPCBase.blockresponse(self, body, stream)


class RPCBase:
    @staticmethod
    async def service_provider_request(self, body, stream):
        payload = body.get('params', {}).get('payload')
        if (
            not payload.get('service_provider')
        ):
            return

        for peer_stream in self.config.peer.get_service_provider_request_peers(stream.peer, payload):
            await self.write_params(
                peer_stream,
                'service_provider_request',
                {
                    'payload': payload
                }
            )

    @staticmethod
    async def newtxn(self, body, stream):
        payload = body.get('params', {}).get('payload')
        if (
            not payload.get('transaction')
        ):
            return

        peer = None
        if payload.get('identity'):
            peer = Peer.from_dict({'host': None, 'port': None, 'identity': payload.get('identity')})

        request_peer = None
        if payload.get('request_peer'):
            request_peer = Identity.from_dict(payload.get('request_peer'))

        if request_peer:
            response_peer = self.config.nodeServer.inbound_streams[ServiceProvider.__name__][request_peer.username_signature]
            del payload['request_peer']
            payload['response_peer'] = response_peer.to_dict()
            # TODO: figure out if I am the intended recipient. Maintain list of friends in memory with rid as index

        if request_peer:
            payload['from_peer'] = peer.identity.to_dict()

        for peer_stream in self.config.peer.get_route_peers(stream.peer, payload):
            await self.write_params(
                peer_stream,
                'newtxn',
                {
                    'payload': payload
                }
            )

    @staticmethod
    async def newblock(self, body, stream):
        payload = body.get('params', {}).get('payload')
        if payload.get('block'):
            block = await Block.from_dict(payload.get('block'))
            await self.config.consensus.insert_consensus_block(block, stream.peer)
            self.ensure_previous_block(self, block, stream)
            for peer_stream in self.config.peer.get_newblock_peers(stream.peer, payload):
                await self.write_params(
                    peer_stream,
                    'newblock',
                    {
                        'payload': payload
                    }
                )

    @staticmethod
    async def ensure_previous_block(self, block, stream):
        have_prev = self.config.mongo.async_db.blocks.find_one({
            'hash': block.prev_hash
        })
        if not have_prev:
            have_prev = self.config.mongo.async_db.consensus.find_one({
                'block.hash': block.prev_hash
            })
            if not have_prev:
                await self.write_params(
                    stream,
                    'getblock',
                    {
                        'hash': block.prev_hash
                    }
                )
                return False
        return True

    @staticmethod
    async def ensure_previous_on_blockchain(self, block):
        return self.config.mongo.async_db.blocks.find_one({
            'hash': block.prev_hash
        })
    
    @staticmethod
    async def send_block(self, block):
        outbound_class = await self.config.peer.get_outbound_class()
        inbound_class = await self.config.peer.get_inbound_class()
        streams = {
            **self.config.nodeClient.outbound_streams[outbound_class.__name__], 
            **self.config.nodeServer.inbound_streams[inbound_class.__name__]
        }
        for rid, peer_stream in streams.items():
            await RPCBase.write_params(
                self,
                peer_stream,
                'newblock',
                {
                    'payload': {
                        'block': block.to_dict()
                    }
                }
            )

    @staticmethod
    async def getblock(self, body, stream):
        # get blocks should be done only by syncing peers
        params = body.get('params')
        block_hash = params.get("hash")
        block = await self.config.mongo.async_db.blocks.find_one({'hash': block_hash}, {'_id': 0})
        if not block:
            block = await self.config.mongo.async_db.consensus.find_one({'block.hash': block_hash}, {'_id': 0})
            if block:
                block = block['block']
        if block:
            await self.write_result(stream, 'blockresponse', {
                'block': block
            })
    
    @staticmethod
    async def blockresponse(self, body, stream):
        # get blocks should be done only by syncing peers
        result = body.get('result')
        block = await Block.from_dict(result.get("block"))
        await self.config.consensus.insert_consensus_block(block, stream.peer)
        self.ensure_previous_block(self, block, stream)

        fork_block = await self.ensure_previous_on_blockchain(self, block)
        if fork_block:
            fork_block = await Block.from_dict(fork_block)
            # ensure_previous_on_blockchain is true, so we have the 
            # linking block from our existing chain.
            local_chain = await self.config.consensus.buld_local_chain(block)
            remote_chain = await self.config.consensus.buld_remote_chain(block)
    
            if not await self.consensus.test_chain_insertable(
                fork_block,
                local_chain,
                remote_chain
            ):
                return False
            
            await self.consensus.integrate_remote_chain_with_existing_chain(local_chain, remote_chain)

    @staticmethod
    async def connect(self, body, stream):
        params = body.get('params')
        if not params.get('peer'):
            stream.close()
            return {}
        generic_peer = Peer.from_dict(params.get('peer'))
        if isinstance(self.config.peer, Seed):

            if generic_peer.identity.username_signature in self.config.seeds:
                peerCls = Seed
            elif generic_peer.identity.username_signature in self.config.seed_gateways:
                peerCls = SeedGateway

        elif isinstance(self.config.peer, SeedGateway):

            if generic_peer.identity.username_signature in self.config.seeds:
                peerCls = Seed
            elif generic_peer.identity.username_signature in self.config.service_providers:
                peerCls = ServiceProvider

        elif isinstance(self.config.peer, ServiceProvider):

            if generic_peer.identity.username_signature in self.config.seed_gateways:
                peerCls = SeedGateway
            else:
                peerCls = User
        else:
            self.config.app_log.error('inbound peer is not defined, disconnecting')
            stream.close()
            return {}

        limit = self.config.peer.__class__.type_limit(peerCls)
        if (len(NodeSocketServer.inbound_pending[peerCls.__name__]) + len(NodeSocketServer.inbound_streams[peerCls.__name__])) >= limit:
            await self.write_result(stream, 'capacity', {})
            stream.close()
            return {}

        try:
            stream.peer = peerCls.from_dict(params.get('peer'))
        except:
            self.config.app_log.error('invalid peer identity')
            stream.close()
            return {}

        if generic_peer.rid in NodeSocketServer.inbound_pending[stream.peer.__class__.__name__]:
            stream.close()
            return {}

        if generic_peer.rid in NodeSocketServer.inbound_streams[stream.peer.__class__.__name__]:
            stream.close()
            return {}

        if generic_peer.rid in self.config.nodeClient.outbound_ignore[stream.peer.__class__.__name__]:
            stream.close()
            return

        if generic_peer.rid in self.config.nodeClient.outbound_pending[stream.peer.__class__.__name__]:
            stream.close()
            return

        if generic_peer.rid in self.config.nodeClient.outbound_streams[stream.peer.__class__.__name__]:
            stream.close()
            return

        try:
            result = verify_signature(
                base64.b64decode(stream.peer.identity.username_signature),
                stream.peer.identity.username.encode(),
                bytes.fromhex(stream.peer.identity.public_key)
            )
            if result:
                self.config.app_log.info('new {} peer is valid'.format(stream.peer.__class__.__name__))
        except:
            self.config.app_log.error('invalid peer identity signature')
            stream.close()
            return {}

        NodeSocketServer.inbound_streams[peerCls.__name__][stream.peer.rid] = stream
        self.config.app_log.info('Connected to {}: {}'.format(stream.peer.__class__.__name__, stream.peer.to_json()))
        return {}
    
    @staticmethod
    async def challenge(self, body, stream):
        challenge = body.get('params', {}).get('token')
        signed_challenge = TU.generate_signature(challenge, self.config.private_key)
        await self.write_result(stream, 'authenticate', {
            'peer': self.config.peer.to_dict(),
            'signed_challenge': signed_challenge
        })

        stream.peer.token = str(uuid4())
        await self.write_params(stream, 'challenge', {
            'token': stream.peer.token
        })
    
    @staticmethod
    async def authenticate(self, body, stream):
        signed_challenge = body.get('result', {}).get('signed_challenge')
        result = verify_signature(
            base64.b64decode(signed_challenge),
            stream.peer.token.encode(),
            bytes.fromhex(stream.peer.identity.public_key)
        )
        if result:
            stream.peer.authenticated = True
            self.config.app_log.info('Authenticated {}: {}'.format(stream.peer.__class__.__name__, stream.peer.to_json()))
    
    async def write_result(self, stream, method, data):
        await SharedBaseMethods.write_result(self, stream, method, data)
    
    async def write_params(self, stream, method, data):
        await SharedBaseMethods.write_params(self, stream, method, data)
