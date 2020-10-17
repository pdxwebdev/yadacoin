import base64
import time
from uuid import uuid4

from tornado.iostream import StreamClosedError
from coincurve import verify_signature

from yadacoin.socket.base import RPCSocketServer, RPCSocketClient
from yadacoin.core.chain import CHAIN
from yadacoin.core.block import Block
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.peer import Peer, Seed, SeedGateway, ServiceProvider, User
from yadacoin.core.config import get_config
from yadacoin.core.transactionutils import TU


class NodeSocketServer(RPCSocketServer):

    def __init__(self):
        super(NodeSocketServer, self).__init__()
        self.config = get_config()

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
        result = body.get('result')
        block = Block.from_dict(result)
        block.verify()
        if (block.index + 60) < LatestBlock.block.index:
            return
        await self.config.consensus.insert_consensus_block(block, stream.peer)
    
    async def route(self, body, stream):
        await SharedMethods.route(self, body, stream)


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
        signed_challenge = body.get('result', {}).get('signed_challenge')
        result = verify_signature(
            base64.b64decode(signed_challenge),
            stream.peer.token.encode(),
            bytes.fromhex(stream.peer.identity.public_key)
        )
        if result:
            stream.peer.authenticated = True
            self.config.app_log.info('Authenticated {}: {}'.format(stream.peer.__class__.__name__, stream.peer.to_json()))
    
    async def capacity(self, body, stream):
        NodeSocketClient.outbound_ignore[stream.peer.__class__.__name__][stream.peer.rid] = stream.peer
        self.config.app_log.warning('{} at full capacity: {}'.format(stream.peer.__class__.__name__, stream.peer.to_json()))
    
    async def route(self, body, stream):
        await SharedMethods.route(self, body, stream)


class SharedMethods:
    @staticmethod
    async def route(self, body, stream):
        rid = body.get('params', {}).get('rid')
        payload = body.get('params', {}).get('payload')
        if isinstance(self.config.peer, ServiceProvider):
            if rid in self.config.nodeServer.inbound_streams[User.__name__]:
                await self.write_result(stream, 'found', self.config.nodeServer.inbound_streams[User.__name__][rid].peer.to_dict())
        elif isinstance(self.config.peer, Seed):
            if isinstance(stream.peer, SeedGateway):
                seed = await SharedMethods.calculate_seed()
                if self.config.nodeServer.inbound_streams[Seed.__name__]:
                if self.config.nodeClient.outbound_streams[Seed.__name__]:
                await self.write_params(peer_stream, 'route', {
                    'rid': rid,
                    'payload': payload
                })
            elif isinstance(stream.peer, Seed):
                if self.config.nodeServer.inbound_streams[SeedGateway.__name__][]
                    await self.write_params(peer_stream, 'route', {
                        'rid': rid,
                        'payload': payload
                    })
        elif isinstance(self.config.peer, SeedGateway):
            if isinstance(stream.peer, Seed):
                for rid, peer_stream in self.config.nodeServer.inbound_streams[ServiceProvider.__name__].items():
                    await self.write_params(peer_stream, 'route', {
                        'rid': rid,
                        'payload': payload
                    })
            elif isinstance(stream.peer, ServiceProvider):
                for rid, peer_stream in self.config.nodeServer.inbound_streams[ServiceProvider.__name__].items():
                    await self.write_params(peer_stream, 'route', {
                        'rid': rid,
                        'payload': payload
                    })
                for rid, peer_stream in self.config.nodeClient.outbound_streams[Seed.__name__].items():
                    await self.write_params(peer_stream, 'route', {
                        'rid': rid,
                        'payload': payload
                    })
    
    async def calculate_seed(username_signature):
        epoch = 1602914018
        ttl = 259200
        username_signature_hash = hashlib.sha256(username_signature).hexdigest()
        #introduce some kind of unpredictability here. This uses the latest block hash. So we won't be able to get the new seed without the block hash
        #which is not known in advance
        seed_mod = (int(username_signature_hash, 16) + int(LatestBlock.block.hash, 16)) % len(self.config.seeds)
        seed_time = (time.time() - epoch) / ttl
        return self.config.seeds[list(self.config.seeds)[seed_select]]
