from yadacoin.socket.base import RPCSocketServer, RPCSocketClient
from yadacoin.core.chain import CHAIN
from yadacoin.core.block import Block
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.peer import Peer


class NodeSocketServer(RPCSocketServer):

    sockets = {}
    async def connect(self, body, stream):
        params = body.get('params')
        peer = Peer.from_dict(params)

        if self.config.peer_type == 'seed' and peer.identity.peer_type not in ['seed', 'seed_gateway']:
            stream.close()
            return
        elif self.config.peer_type == 'seed_gateway' and peer.identity.peer_type != 'service_provider':
            stream.close()
            return
        elif self.config.peer_type == 'service_provider' and peer.identity.peer_type != 'user':
            stream.close()
            return
        elif self.config.peer_type == 'user':
            stream.close()
            return
        self.__class__.streams[peer.identity.username_signature] = stream
        return {}

    async def receivepeers(self, body, stream):
        params = body.get('params')
        peers = params('peers')
        Peers.import_peers(peers)
        return {}

    async def receivepeeridentity(self, body, stream):
        params = body.get('params')
        peers = params('peers')
        Peers.import_peers(peers)

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

    async def connect(self, peer: Peer):
        if (peer.identity.username_signature in NodeSocketServer.sockets and NodeSocketServer.sockets[peer.identity.username_signature]):
            return
        NodeSocketServer.sockets[peer.identity.username_signature] = None
        sock = await super(NodeSocketClient, self).connect(peer.host, peer.port)
        NodeSocketServer.sockets[peer.identity.username_signature] = sock