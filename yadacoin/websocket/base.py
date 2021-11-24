import json
import base64
import functools
from traceback import format_exc

from tornado import gen, ioloop
from tornado.websocket import WebSocketHandler, WebSocketClosedError
from coincurve import verify_signature
from bitcoin.wallet import P2PKHBitcoinAddress
from yadacoin.core.collections import Collections
from yadacoin.core.graphutils import GraphUtils

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
        pass # removing cookies! Yada does not do cookies or sessions! EVER!

    async def on_message(self, data):
        if not data:
            return
        body = json.loads(data)
        method = body.get('method')
        await getattr(self, method)(body)
        self.config.app_log.debug(f'RECEIVED {self.peer.identity.username} {method} {data}')

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
        for collection in Collections:
            rid = self.peer.identity.generate_rid(self.peer.identity.username_signature, collection.value)
            RCPWebSocketServer.inbound_streams[User.__name__][rid] = self

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
            await self.write_result('connect_confirm', {
              'identity': self.config.peer.identity.to_dict,
              'shares_required': self.config.shares_required,
              'credit_balance': await self.get_credit_balance(),
              'server_pool_address': f'{self.config.peer_host}:{self.config.stratum_pool_port}'
            }, body=body)
        except:
            self.config.app_log.error('invalid peer identity signature')
            self.close()
            return {}

    async def chat_history(self, body):
        results = await self.config.mongo.async_db.miner_transactions.find({
            'requested_rid': self.config.peer.identity.generate_rid(body.get('params', {}).get('to').get('username_signature'))
        }, {
            '_id': 0
        }).sort([('time', -1)]).to_list(100)
        await self.write_result('chat_history_response', {'chats': sorted(results, key=lambda x: x['time']), 'to': body.get('params', {}).get('to')}, body=body)

    async def route_confirm(self, body):
        credit_balance = await self.get_credit_balance()
        await self.write_result('route_server_confirm', {'credit_balance': credit_balance}, body=body)

    async def route(self, body):
        # our peer SHOULD only ever been a service provider if we're offering a websocket but we'll give other options here
        route_server_confirm_out = {}
        if self.config.shares_required:

            credit_balance = await self.get_credit_balance()

            if credit_balance <= 0:
                await self.write_result('route_server_confirm', {'credit_balance': credit_balance}, body=body)
                return
            route_server_confirm_out = {'credit_balance': credit_balance}

        params = body.get('params')
        transaction = Transaction.from_dict(params['transaction'])
        await self.config.mongo.async_db.miner_transactions.replace_one(
            {
                'id': transaction.transaction_signature
            },
            transaction.to_dict(),
            upsert=True
        )
        if isinstance(self.config.peer, Seed):
            pass
            # for rid, peer_stream in self.config.nodeServer.inbound_streams[Seed.__name__].items():
            #     await BaseRPC().write_params(peer_stream, 'route', params)

            # for rid, peer_stream in self.config.nodeServer.inbound_streams[SeedGateway.__name__].items():
            #     await BaseRPC().write_params(peer_stream, 'route', params)

            # for rid, peer_stream in self.config.nodeClient.outbound_streams[Seed.__name__].items():
            #     await BaseRPC().write_params(peer_stream, 'route', params)

        elif isinstance(self.config.peer, SeedGateway):
            pass
            # for rid, peer_stream in self.config.nodeServer.inbound_streams[ServiceProvider.__name__].items():
            #     await BaseRPC().write_params(peer_stream, 'route', params)

            # for rid, peer_stream in self.config.nodeClient.outbound_streams[Seed.__name__].items():
            #     await BaseRPC().write_params(peer_stream, 'route', params)

        elif isinstance(self.config.peer, ServiceProvider):
            pass
            # for rid, peer_stream in self.config.nodeServer.inbound_streams[User.__name__].items():
            #     await BaseRPC().write_params(peer_stream, 'route', params)

            # for rid, peer_stream in self.config.nodeClient.outbound_streams[SeedGateway.__name__].items():
            #     await BaseRPC().write_params(peer_stream, 'route', params)

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
            pass
            # for rid, peer_stream in self.config.nodeClient.outbound_streams[ServiceProvider.__name__].items():
            #     await BaseRPC().write_params(peer_stream, 'route', params)

        else:
            self.config.app_log.error('inbound peer is not defined, disconnecting')
            self.close()
            return {}
        await self.write_result('route_server_confirm', route_server_confirm_out, body=body)

    async def newtxn(self, body, source='websocket'):
        params = body.get('params')
        if (
            not params.get('transaction')
        ):
            return

        txn = Transaction.from_dict(params.get('transaction'))
        try:
            await txn.verify()
        except:
            return

        await self.config.mongo.async_db.miner_transactions.replace_one(
            {
                'id': txn.transaction_signature
            },
            txn.to_dict(),
            upsert=True
        )
        if self.peer.identity.public_key == params.get('transaction', {}).get('public_key') and source == 'websocket':
            if isinstance(self.config.peer, ServiceProvider):
                for rid, peer_stream in self.config.nodeServer.inbound_streams[User.__name__].items():
                    await BaseRPC().write_params(peer_stream, 'newtxn', params)

                for rid, peer_stream in self.config.nodeClient.outbound_streams[SeedGateway.__name__].items():
                    await BaseRPC().write_params(peer_stream, 'newtxn', params)
            return

        await self.write_params('newtxn', params)

    async def newtxn_confirm(self, body):
        pass

    async def get_credit_balance(self):
      address = P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.peer.identity.public_key))

      shares = await self.config.mongo.async_db.shares.count_documents({'address': str(address)})

      txns_routed = await self.config.mongo.async_db.miner_transactions.count_documents({'public_key': self.peer.identity.public_key})

      credit_balance = shares - (txns_routed * .1)

      return credit_balance if credit_balance > 0 else 0.00

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

        group = Identity.from_dict(body.get('params'))

        members = {}
        members.update(self.append_to_group(group, Collections.GROUP_CHAT.value))
        members.update(self.append_to_group(group, Collections.GROUP_MAIL.value))
        members.update(self.append_to_group(group, Collections.GROUP_CALENDAR.value))

        await self.write_result('join_confirmed', {
          'members': members
        }, body=body)

    def append_to_private(self, group, collection):
        group_rid = group.generate_rid(group.username_signature, collection)
        if group_rid not in RCPWebSocketServer.inbound_streams[Group.__name__]:
            RCPWebSocketServer.inbound_streams[Group.__name__][group_rid] = {}
        peer_rid = self.peer.identity.generate_rid(self.peer.identity.username_signature, collection)
        RCPWebSocketServer.inbound_streams[Group.__name__][group_rid][peer_rid] = self
        return {
            group_rid: [x.peer.identity.to_dict for y, x in RCPWebSocketServer.inbound_streams[Group.__name__][group_rid].items()]
        }

    def append_to_group(self, group, collection):
        group_rid = group.generate_rid(group.username_signature, collection)
        if group_rid not in RCPWebSocketServer.inbound_streams[Group.__name__]:
            RCPWebSocketServer.inbound_streams[Group.__name__][group_rid] = {}
        peer_rid = self.peer.identity.generate_rid(self.peer.identity.username_signature, collection)
        RCPWebSocketServer.inbound_streams[Group.__name__][group_rid][peer_rid] = self
        return {
            group_rid: [x.peer.identity.to_dict for y, x in RCPWebSocketServer.inbound_streams[Group.__name__][group_rid].items()]
        }

    async def service_provider_request(self, body):
        if not body.get('params').get('group'):
            self.config.app_log.error('Group not provided')
            return
        group = Group.from_dict({
            'host': None,
            'port': None,
            'identity': body.get('params').get('group')
        })
        seed_gateway = await group.calculate_seed_gateway()
        if not seed_gateway:
            self.config.app_log.error('No seed gateways available.')
            return
        params = {
            'seed_gateway': seed_gateway.to_dict(),
            'group': group.to_dict()
        }

        for rid, peer_stream in self.config.nodeClient.outbound_streams[SeedGateway.__name__].items():
            await BaseRPC().write_params(peer_stream, 'service_provider_request', params)
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
        req_id = body.get('id') if body else 1
        rpc_data = {
            'id': req_id,
            'method': method,
            'jsonrpc': 2.0,
            rpc_type: data
        }

        try:
            await self.write_message('{}'.format(json.dumps(rpc_data)).encode())
        except:
            self.config.app_log.warning('message did not send')

        self.config.app_log.debug(f'SENT {self.peer.identity.username} {method} {data} {rpc_type} {req_id}')

WEBSOCKET_HANDLERS = [(r'/websocket', RCPWebSocketServer),]
