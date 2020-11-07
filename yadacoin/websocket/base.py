import json
import base64

from tornado.websocket import WebSocketHandler
from coincurve import verify_signature

from yadacoin.core.identity import Identity
from yadacoin.core.peer import Peer, Seed, SeedGateway, ServiceProvider, User, Group
from yadacoin.core.config import get_config
from yadacoin.tcpsocket.node import RPCBase

class RCPWebSocketServer(WebSocketHandler):
    inbound_streams = {}
    inbound_pending = {}
    config = None

    async def open(self):
        user = User.from_dict({
            'host': None,
            'port': None,
            'identity': {
                'username': self.get_secure_cookie('username'),
                'username_signature': self.get_secure_cookie('username_signature'),
                'public_key': self.get_secure_cookie('public_key')
            }
        })
        RCPWebSocketServer.inbound_streams[User.__name__][user.rid] = self

    async def on_message(self, data):
        body = json.loads(data)
        method = body.get('method')
        await getattr(self, method)(body)

    def on_close(self):
        self.remove_peer(self.peer)
    
    def check_origin(self, origin):
        return True

    async def connect(self, body):
        self.config = get_config()
        params = body.get('params')
        if not params.get('identity'):
            self.close()
            return {}

        peer = User.from_dict({
            'host': None,
            'port': None,
            'identity': params.get('identity')
        })
        self.peer = peer
        RCPWebSocketServer.inbound_streams[User.__name__][peer.rid] = self

        try:
            result = verify_signature(
                base64.b64decode(peer.identity.username_signature),
                peer.identity.username.encode(),
                bytes.fromhex(peer.identity.public_key)
            )
            if not result:
                self.close()
        except:
            self.config.app_log.error('invalid peer identity signature')
            self.close()
            return {}

        try:
            result = verify_signature(
                base64.b64decode(peer.identity.username_signature),
                peer.identity.username.encode(),
                bytes.fromhex(self.get_secure_cookie('public_key').decode())
            )
            if result:
                self.config.app_log.info('new {} is valid'.format(peer.__class__.__name__))
            else:
                self.close()
        except:
            self.config.app_log.error('invalid peer identity signature')
            self.close()
            return {}
    
    async def route(self, body):
        # our peer SHOULD only ever been a service provider if we're offering a websocket but we'll give other options here
        params = body.get('params')
        if isinstance(self.config.peer, Seed):

            for rid, peer_stream in self.config.nodeServer.inbound_streams[Seed.__name__].items():
                await RPCBase.write_params(self, peer_stream, 'route', params)

            for rid, peer_stream in self.config.nodeServer.inbound_streams[SeedGateway.__name__].items():
                await RPCBase.write_params(self, peer_stream, 'route', params)

            for rid, peer_stream in self.config.nodeClient.outbound_streams[Seed.__name__].items():
                await RPCBase.write_params(self, peer_stream, 'route', params)

        elif isinstance(self.config.peer, SeedGateway):

            for rid, peer_stream in self.config.nodeServer.inbound_streams[ServiceProvider.__name__].items():
                await RPCBase.write_params(self, peer_stream, 'route', params)

            for rid, peer_stream in self.config.nodeClient.outbound_streams[Seed.__name__].items():
                await RPCBase.write_params(self, peer_stream, 'route', params)

        elif isinstance(self.config.peer, ServiceProvider):

            for rid, peer_stream in self.config.nodeServer.inbound_streams[User.__name__].items():
                await RPCBase.write_params(self, peer_stream, 'route', params)

            for rid, peer_stream in self.config.nodeClient.outbound_streams[SeedGateway.__name__].items():
                await RPCBase.write_params(self, peer_stream, 'route', params)

        elif isinstance(self.config.peer, User):

            for rid, peer_stream in self.config.nodeClient.outbound_streams[ServiceProvider.__name__].items():
                await RPCBase.write_params(self, peer_stream, 'route', params)

        else:
            self.config.app_log.error('inbound peer is not defined, disconnecting')
            self.close()
            return {}
    
    async def join_group(self, body):
        group = self.config.groups[body.get('params').get('username_signature')]
        if group.identity.username_signature not in RCPWebSocketServer.inbound_streams[Group.__name__]:
            RCPWebSocketServer.inbound_streams[Group.__name__][group.identity.username_signature] = {}
        RCPWebSocketServer.inbound_streams[Group.__name__][group.identity.username_signature][self.peer.identity.username_signature] = self
    
    async def service_provider_request(self, body):
        group = Group.from_dict({
            'host': None,
            'port': None,
            'identity': body.get('params').get('group')
        })
        seed_gateway = await group.calculate_seed_gateway()
        params = {
            'seed_gateway': seed_gateway.to_dict(),
            'group': group.to_dict()
        }

        for rid, peer_stream in self.config.nodeClient.outbound_streams[SeedGateway.__name__].items():
            await RPCBase.write_params(self, peer_stream, 'service_provider_request', params)

    def remove_peer(self, peer):
        id_attr = getattr(peer, peer.id_attribute)
        if id_attr in self.inbound_streams[peer.__class__.__name__]:
            del self.inbound_streams[peer.__class__.__name__][id_attr]
        if id_attr in self.inbound_streams[Group.__name__]:
            del self.inbound_streams[Group.__name__][id_attr]

    async def write_result(self, method, data):
        await self.write_as_json(method, data, 'result')

    async def write_params(self, method, data):
        await self.write_as_json(method, data, 'params')

    async def write_as_json(self, method, data, rpc_type):
        rpc_data = {
            'id': 1,
            'method': method,
            'jsonrpc': 2.0,
            rpc_type: data
        }
        await self.write_message('{}'.format(json.dumps(rpc_data)).encode())

WEBSOCKET_HANDLERS = [(r'/websocket', RCPWebSocketServer),]
