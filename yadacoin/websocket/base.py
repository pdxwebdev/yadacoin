import json
import base64
import functools
from traceback import format_exc

from tornado import gen, ioloop
from tornado.websocket import WebSocketHandler, WebSocketClosedError
from coincurve import verify_signature

from yadacoin.core.identity import Identity
from yadacoin.core.peer import Peer, Seed, SeedGateway, ServiceProvider, User, Group
from yadacoin.core.config import get_config
from yadacoin.core.transaction import Transaction
from yadacoin.tcpsocket.base import BaseRPC

class RCPWebSocketServer(WebSocketHandler):
    inbound_streams = {}
    inbound_pending = {}
    config = None

    def __init__(self, application, request):
        super(RCPWebSocketServer, self).__init__(application, request)
        self.config = get_config()

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
        self.peer = user
        self.peer.groups = {}

    async def on_message(self, data):
        if not data:
            return
        body = json.loads(data)
        method = body.get('method')
        await getattr(self, method)(body)

    def on_close(self):
        self.remove_peer(self.peer)
    
    def check_origin(self, origin):
        return True

    async def connect(self, body):
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
        self.peer.groups = {}
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
            self.config.app_log.info('new {} is valid'.format(peer.__class__.__name__))
            await self.write_result('connect_confirm', self.config.peer.to_dict(), body=body)
        except:
            self.config.app_log.error('invalid peer identity signature')
            self.close()
            return {}
    
    async def route_confirm(self, body):
        await self.write_result('route_server_confirm', {}, body=body)
    
    async def route(self, body):
        # our peer SHOULD only ever been a service provider if we're offering a websocket but we'll give other options here
        params = body.get('params')
        transaction = Transaction.from_dict(params['transaction'])

        if isinstance(self.config.peer, Seed):

            for rid, peer_stream in self.config.nodeServer.inbound_streams[Seed.__name__].items():
                await BaseRPC().write_params(peer_stream, 'route', params)

            for rid, peer_stream in self.config.nodeServer.inbound_streams[SeedGateway.__name__].items():
                await BaseRPC().write_params(peer_stream, 'route', params)

            for rid, peer_stream in self.config.nodeClient.outbound_streams[Seed.__name__].items():
                await BaseRPC().write_params(peer_stream, 'route', params)

        elif isinstance(self.config.peer, SeedGateway):

            for rid, peer_stream in self.config.nodeServer.inbound_streams[ServiceProvider.__name__].items():
                await BaseRPC().write_params(peer_stream, 'route', params)

            for rid, peer_stream in self.config.nodeClient.outbound_streams[Seed.__name__].items():
                await BaseRPC().write_params(peer_stream, 'route', params)

        elif isinstance(self.config.peer, ServiceProvider):

            for rid, peer_stream in self.config.nodeServer.inbound_streams[User.__name__].items():
                await BaseRPC().write_params(peer_stream, 'route', params)

            for rid, peer_stream in self.config.nodeClient.outbound_streams[SeedGateway.__name__].items():
                await BaseRPC().write_params(peer_stream, 'route', params)

            if transaction.requested_rid in self.config.websocketServer.inbound_streams[Group.__name__]:
                for rid, peer_stream in self.config.websocketServer.inbound_streams[Group.__name__][transaction.requested_rid].items():
                    if rid == transaction.requester_rid:
                        continue
                    await peer_stream.write_params('route', params)

            if transaction.requested_rid in self.config.websocketServer.inbound_streams[User.__name__]:
                peer_stream = self.config.websocketServer.inbound_streams[User.__name__][transaction.requested_rid]
                if peer_stream.peer.rid != transaction.requester_rid:
                    await peer_stream.write_params('route', params)
            
            if 'group' in params:
                group = Group.from_dict({
                    'host': None,
                    'port': None,
                    'identity': params['group']
                })
                params2 = params.copy()
                to = User.from_dict({
                    'host': None,
                    'port': None,
                    'identity': params['to']
                })
                peer_stream = self.config.websocketServer.inbound_streams[Group.__name__][group.rid].get(to.rid)
                if peer_stream:
                    await peer_stream.write_params('route', params2)


        elif isinstance(self.config.peer, User):

            for rid, peer_stream in self.config.nodeClient.outbound_streams[ServiceProvider.__name__].items():
                await BaseRPC().write_params(peer_stream, 'route', params)

        else:
            self.config.app_log.error('inbound peer is not defined, disconnecting')
            self.close()
            return {}
        await self.write_result('route_server_confirm', {}, body=body)
    
    async def join_group(self, body):
        
        # for rid, group in self.peer.groups.items():
        #     group_id_attr = getattr(group, group.id_attribute)
        #     if group_id_attr in self.inbound_streams[Group.__name__]:
        #         if self.peer.rid in self.inbound_streams[Group.__name__][group_id_attr]:
        #             del self.inbound_streams[Group.__name__][group_id_attr][self.peer.rid]

        #             for rid, peer_stream in RCPWebSocketServer.inbound_streams[Group.__name__][group_id_attr].items():
        #                 await peer_stream.write_result('group_user_count', {
        #                     'group_user_count': len(RCPWebSocketServer.inbound_streams[Group.__name__][group_id_attr])
        #                 }, body=body)

        if body.get('params').get('username_signature') in self.config.groups:
            group = self.config.groups[body.get('params').get('username_signature')]
        else:
            group = Group.from_dict({
                'host': None,
                'port': None,
                'identity': body.get('params')
            })
        if group.rid not in RCPWebSocketServer.inbound_streams[Group.__name__]:
            RCPWebSocketServer.inbound_streams[Group.__name__][group.rid] = {}
        RCPWebSocketServer.inbound_streams[Group.__name__][group.rid][self.peer.rid] = self
        self.peer.groups[group.rid] = group

        await self.write_result('join_confirmed', {
            'group_user_count': len(RCPWebSocketServer.inbound_streams[Group.__name__][group.rid])
        }, body=body)
        for rid, peer_stream in RCPWebSocketServer.inbound_streams[Group.__name__][group.rid].items():
            try:
                await peer_stream.write_result('group_user_count', {
                    'group_user_count': len(RCPWebSocketServer.inbound_streams[Group.__name__][group.rid])
                }, body=body)
            except WebSocketClosedError:
                self.remove_peer(peer_stream.peer)
            except:
                self.config.app_log.warning(format_exc())
    
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
            await BaseRPC().write_params(peer_stream, 'service_provider_request', params, body=body)
        await self.write_result('service_provider_request_confirm', {}, body=body)
    
    async def online(self, body):
        rids = body.get('params').get('rids')
        matching_rids = set(rids) & set(self.config.websocketServer.inbound_streams[User.__name__].keys())
        await self.write_result('online', {'online_rids': list(matching_rids)}, body=body)

    def remove_peer(self, peer):
        id_attr = getattr(peer, peer.id_attribute)
        if id_attr in self.inbound_streams[peer.__class__.__name__]:
            del self.inbound_streams[peer.__class__.__name__][id_attr]
        
        loop = ioloop.IOLoop.current()
        for rid, group in peer.groups.items():
            group_id_attr = getattr(group, group.id_attribute)
            if group_id_attr in self.inbound_streams[Group.__name__]:
                if id_attr in self.inbound_streams[Group.__name__]:
                    del self.inbound_streams[Group.__name__][group_id_attr][id_attr]
                for rid, peer_stream in RCPWebSocketServer.inbound_streams[Group.__name__][group_id_attr].items():
                    if id_attr == rid:
                        continue
                    loop.add_callback(
                        peer_stream.write_result,
                        'group_user_count',
                        {
                            'group_user_count': len(RCPWebSocketServer.inbound_streams[Group.__name__][group_id_attr])
                        }
                    )

    async def write_result(self, method, data, body=None):
        await self.write_as_json(method, data, 'result', body)

    async def write_params(self, method, data, body=None):
        await self.write_as_json(method, data, 'params', body)

    async def write_as_json(self, method, data, rpc_type, body=None):
        rpc_data = {
            'id': body.get('id') if body else 1,
            'method': method,
            'jsonrpc': 2.0,
            rpc_type: data
        }
        try:
            await self.write_message('{}'.format(json.dumps(rpc_data)).encode())
        except:
            self.config.app_log.warning('message did not send')

WEBSOCKET_HANDLERS = [(r'/websocket', RCPWebSocketServer),]
