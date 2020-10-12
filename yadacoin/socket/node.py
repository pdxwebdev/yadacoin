import base64
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

    sockets = {}
    pending = {}
    async def connect(self, body, stream):
        params = body.get('params')
        peerCls = None
        if isinstance(self.config.peer, Seed):
            peerCls = SeedGateway
        elif isinstance(self.config.peer, SeedGateway):
            peerCls = ServiceProvider
        elif isinstance(self.config.peer, ServiceProvider):
            peerCls = User
        stream.peer = peerCls.from_dict(params.get('peer'))
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

class NodeSocketClient(RPCSocketClient):

    def __init__(self, streams, pending):
        super(NodeSocketClient, self).__init__()
        self.streams = streams
        self.pending = pending
        self.config = get_config()

    async def connect(self, peer: Peer):
        try:
            stream = await super(NodeSocketClient, self).connect(peer)
            if stream:
                stream.peer = peer
                stream.peer.token = str(uuid4())
                await self.write_params(stream, 'connect', {
                    'peer': self.config.peer.to_dict()
                })
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
