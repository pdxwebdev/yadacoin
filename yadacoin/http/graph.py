"""
Handlers required by the graph operations
"""

import base64
import hashlib
import json
import os
import time
import requests
import uuid

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve.utils import verify_signature
from eccsnacks.curve25519 import scalarmult_base
from logging import getLogger
from threading import Thread
from yadacoin.core.collections import Collections
from yadacoin.core.graphutils import GraphUtils
from yadacoin.core.peer import Group, User

from yadacoin.http.base import BaseHandler
from yadacoin.core.graph import Graph
from yadacoin.core.transaction import Transaction, InvalidTransactionException, \
    InvalidTransactionSignatureException, MissingInputTransactionException
from yadacoin.core.transactionutils import TU
from yadacoin.decorators.jwtauth import jwtauthwallet


class GraphConfigHandler(BaseHandler):

    async def get(self):
        peer = "{}".format(self.config.wallet_host_port)
        yada_config = {
            "baseUrl": "{}".format(peer),
            "transactionUrl": "{}/transaction".format(peer),
            "fastgraphUrl": "{}/post-fastgraph-transaction".format(peer),
            "graphUrl": "{}".format(peer),
            "walletUrl": "{}/get-graph-wallet".format(peer),
            "websocketUrl": "{}/websocket".format(self.config.websocket_host_port),
            "loginUrl": "{}/login".format(peer),
            "registerUrl": "{}/create-relationship".format(peer),
            "authenticatedUrl": "{}/authenticated".format(peer),
            "webSignInUrl": "{}/web-signin".format(peer),
            "logoData": '',
            "identity": self.config.get_identity(),
            "restricted": self.config.restrict_graph_api
        }
        return self.render_as_json(yada_config)

@jwtauthwallet
class BaseGraphHandler(BaseHandler):
    async def get_base_graph(self):
        self.username_signature = self.get_query_argument('username_signature').replace(' ', '+')
        self.to = self.get_query_argument('to', None)
        self.username = self.get_query_argument('username', None)
        self.rid = self.generate_rid(self.config.get_identity().get('username_signature'), self.username_signature)
        ids = []
        rids = []
        update_last_collection_time = None
        if self.request.body:
            body = json.loads(self.request.body.decode('utf-8'))
            ids = body.get('ids')
            rids = body.get('rids')
            if not isinstance(rids, list):
                rids = [rids]
            update_last_collection_time = body.get('update_last_collection_time')
        try:
            key_or_wif = self.get_secure_cookie('key_or_wif').decode()
        except:
            key_or_wif = None
        if not key_or_wif:
            try:
                key_or_wif = self.jwt.get('key_or_wif')
            except:
                key_or_wif = None
        return await Graph().async_init(
            self.config,
            self.config.mongo,
            self.username_signature,
            ids,
            rids,
            key_or_wif,
            update_last_collection_time
        )
        # TODO: should have a self.render here instead, not sure what is supposed to be returned here

    def generate_rid(self, first_username_signature, second_username_signature, collection = ''):
        username_signatures = sorted([str(first_username_signature), str(second_username_signature)], key=str.lower)
        return hashlib.sha256((str(username_signatures[0]) + str(username_signatures[1]) + str(collection)).encode('utf-8')).digest().hex()


class GraphInfoHandler(BaseGraphHandler):

    async def get(self):
        graph = await self.get_base_graph()
        self.render_as_json(graph.to_dict())


class GraphRIDWalletHandler(BaseGraphHandler):

    async def get(self):
        address = self.get_query_argument('address')
        amount_needed = self.get_query_argument('amount_needed', None)
        if amount_needed:
            amount_needed = float(amount_needed)

        regular_txns = []
        chain_balance = 0
        async for txn in self.config.BU.get_wallet_unspent_transactions(address, no_zeros=True):
            if amount_needed and chain_balance < amount_needed:
                for output in txn['outputs']:
                    if output['to'] == address and float(output['value']) > 0.0:
                        regular_txns.append(txn)
            for output in txn['outputs']:
                if output['to'] == address:
                    chain_balance += float(output['value'])
            self.app_log.warning(chain_balance)

        wallet = {
            'chain_balance': "{0:.8f}".format(chain_balance),
            'balance': "{0:.8f}".format(chain_balance),
            'unspent_transactions': regular_txns if amount_needed else []
        }
        self.render_as_json(wallet, indent=4)


class RegistrationHandler(BaseHandler):

    async def get(self):
        data = {
            'username_signature': self.config.get_identity().get('username_signature'),
            'username': self.config.get_identity().get('username'),
            'callbackurl': self.config.callbackurl,
            'to': self.config.address
        }
        self.render_as_json(data)


class GraphTransactionHandler(BaseGraphHandler):

    async def get(self):
        rid = self.request.args.get('rid')
        if rid:
            transactions = GU().get_transactions_by_rid(rid, self.config.get_identity().get('username_signature'), rid=True, raw=True)
        else:
            transactions = []
        self.render_as_json(list(transactions))

    async def post(self):
        await self.get_base_graph()  # TODO: did this to set username_signature, refactor this
        items = json.loads(self.request.body.decode('utf-8'))
        if not isinstance(items, list):
            items = [items, ]
        else:
            items = [item for item in items]
        transactions = []
        for txn in items:
            transaction = Transaction.from_dict(txn)
            try:
                await transaction.verify()
            except InvalidTransactionException:
                await self.config.mongo.async_db.failed_transactions.insert_one({
                    'exception': 'InvalidTransactionException',
                    'txn': txn
                })
                print('InvalidTransactionException')
                return 'InvalidTransactionException', 400
            except InvalidTransactionSignatureException:
                print('InvalidTransactionSignatureException')
                await self.config.mongo.async_db.failed_transactions.insert_one({
                    'exception': 'InvalidTransactionSignatureException',
                    'txn': txn
                })
                return 'InvalidTransactionSignatureException', 400
            except MissingInputTransactionException:
                pass
            except:
                raise
                print('uknown error')
                return 'uknown error', 400
            transactions.append(transaction)

        for x in transactions:
            if x.rid == self.rid and x.dh_public_key:
                me_pending_exists = await self.config.mongo.async_db.miner_transactions.find_one({
                    'public_key': self.config.public_key,
                    'rid': self.rid,
                    'requester_rid': x.requester_rid,
                    'requested_rid': x.requested_rid,
                    'dh_public_key': {'$exists': True}
                })
                me_blockchain_exists = await self.config.mongo.async_db.blocks.find_one({
                    'public_key': self.config.public_key,
                    'rid': self.rid,
                    'requester_rid': x.requester_rid,
                    'requested_rid': x.requested_rid,
                    'dh_public_key': {'$exists': True}
                })
                pending_exists = await self.config.mongo.async_db.miner_transactions.find_one({
                    'public_key': x.public_key,
                    'rid': self.rid,
                    'requester_rid': x.requester_rid,
                    'requested_rid': x.requested_rid,
                    'dh_public_key': {'$exists': True}
                })
                blockchain_exists = await self.config.mongo.async_db.blocks.find_one({
                    'public_key': x.public_key,
                    'rid': self.rid,
                    'requester_rid': x.requester_rid,
                    'requested_rid': x.requested_rid,
                    'dh_public_key': {'$exists': True}
                })
                if pending_exists or blockchain_exists:
                    continue

            if x.dh_public_key:
                dup_check_count = await self.config.mongo.async_db.miner_transactions.count_documents({
                    'dh_public_key': {'$exists': True},
                    'rid': x.rid,
                    'requester_rid': x.requester_rid,
                    'requested_rid': x.requested_rid,
                    'public_key': x.public_key
                })
                if dup_check_count:
                    self.app_log.debug('found duplicate tx for rid set {}'.format(x.transaction_signature))
                    return self.render_as_json({'status': True, 'message': 'dup rid'})

            stream = None
            websocket_streams = self.config.websocketServer.inbound_streams[User.__name__]
            if (
              x.rid in websocket_streams and
              websocket_streams[x.rid].peer.identity.username_signature != self.username_signature
            ):
                stream = websocket_streams[x.rid]

            if (
              x.requester_rid in websocket_streams and
              websocket_streams[x.requester_rid].peer.identity.username_signature != self.username_signature
            ):
                stream = websocket_streams[x.requester_rid]

            if (
              x.requested_rid in websocket_streams and
              websocket_streams[x.requested_rid].peer.identity.username_signature != self.username_signature
            ):
                stream = websocket_streams[x.requested_rid]

            if stream:
                await stream.write_params(
                    'newtxn',
                    {'transaction': x.to_dict()}
                )

            websocket_group_streams = self.config.websocketServer.inbound_streams[Group.__name__]
            if (
              x.requester_rid in websocket_group_streams
            ):
                for rid, stream in websocket_group_streams[x.requester_rid].items():
                    if (
                        x.requester_rid == self.peer.identity.generate_rid(
                          self.peer.identity.username_signature,
                          Collections.GROUP_CHAT.value
                        ) or
                        x.requester_rid == self.peer.identity.generate_rid(
                          self.peer.identity.username_signature,
                          Collections.GROUP_MAIL.value
                        ) or
                        x.requester_rid == self.peer.identity.generate_rid(
                          self.peer.identity.username_signature,
                          Collections.GROUP_CALENDAR.value
                        )
                    ):
                        continue

                    await stream.write_params(
                        'newtxn',
                        {'transaction': x.to_dict()}
                    )

            if (
              x.requested_rid in websocket_group_streams
            ):
                for rid, stream in websocket_group_streams[x.requested_rid].items():
                    await stream.write_params(
                        'newtxn',
                        {'transaction': x.to_dict()}
                    )

            await self.config.mongo.async_db.miner_transactions.insert_one(x.to_dict())

            async for peer_stream in self.config.peer.get_sync_peers():
                await self.config.nodeShared.write_params(
                    peer_stream,
                    'newtxn',
                    {'transaction': x.to_dict()}
                )
                if peer_stream.peer.protocol_version > 1:
                    self.config.nodeClient.retry_messages[(peer_stream.peer.rid, 'newtxn', x.transaction_signature)] = {'transaction': x.to_dict()}

        return self.render_as_json(items)

    async def create_relationship(self, username_signature, username, to):
        config = self.config
        mongo = self.config.mongo

        if not username_signature:
            return 'error: "username_signature" missing', 400

        if not username:
            return 'error: "username" missing', 400

        if not to:
            return 'error: "to" missing', 400
        rid = TU.generate_rid(config, username_signature)
        dup = mongo.db.blocks.find({'transactions.rid': rid})
        if dup.count():
            found_a = False
            found_b = False
            for txn in dup:
                if txn['public_key'] == config.public_key:
                    found_a = True
                if txn['public_key'] != config.public_key:
                    found_b = True
            if found_a and found_b:
                return json.dumps({"success": False, "status": "Already added"})

        miner_transactions = mongo.db.miner_transactions.find()
        mtxn_ids = []
        for mtxn in miner_transactions:
            for mtxninput in mtxn['inputs']:
                mtxn_ids.append(mtxninput['id'])

        checked_out_txn_ids = mongo.db.checked_out_txn_ids.find()
        for mtxn in checked_out_txn_ids:
            mtxn_ids.append(mtxn['id'])

        a = os.urandom(32).decode('latin1')
        dh_public_key = scalarmult_base(a).encode('latin1').hex()
        dh_private_key = a.encode('latin1').hex()

        transaction = await Transaction.generate(
            username_signature=username_signature,
            username=username,
            fee=0.00,
            public_key=config.public_key,
            dh_public_key=dh_public_key,
            private_key=config.private_key,
            dh_private_key=dh_private_key,
            outputs=[
                {
                    'to': to,
                    'value': 0
                }
            ]
        )
        return transaction


class GraphSentFriendRequestsHandler(BaseGraphHandler):
    async def post(self):
        req_body = json.loads(self.request.body)
        search_rid = req_body.get('rids')[0]
        graph = await self.get_base_graph()
        await graph.get_sent_friend_requests(search_rid)
        self.render_as_json(graph.to_dict())


class GraphFriendRequestsHandler(BaseGraphHandler):
    async def post(self):
        req_body = json.loads(self.request.body)
        search_rid = req_body.get('rids')[0]
        graph = await self.get_base_graph()
        await graph.get_friend_requests(search_rid)
        self.render_as_json(graph.to_dict())


class GraphFriendsHandler(BaseGraphHandler):
    async def get(self):
        graph = await self.get_base_graph()
        self.render_as_json(graph.to_dict())


class GraphSentMessagesHandler(BaseGraphHandler):
    async def post(self):
        graph = await self.get_base_graph()
        await graph.get_sent_messages()
        self.render_as_json(graph.to_dict())


class GraphGroupMessagesHandler(BaseGraphHandler):
    async def post(self):
        graph = await self.get_base_graph()
        graph.get_group_messages()
        self.render_as_json(graph.to_dict())


class GraphNewMessagesHandler(BaseGraphHandler):
    async def get(self):
        graph = await self.get_base_graph()
        await graph.get_new_messages()
        self.render_as_json(graph.to_dict())


class GraphCommentsHandler(BaseGraphHandler):
    async def post(self):
        graph = await self.get_base_graph()
        await graph.get_comments()
        self.render_as_json(graph.to_dict())


class GraphReactsHandler(BaseGraphHandler):
    async def post(self):
        graph = await self.get_base_graph()
        await graph.get_reacts()
        self.render_as_json(graph.to_dict())


class GraphCollectionHandler(BaseGraphHandler):
    async def post(self):
        graph = await self.get_base_graph()
        data = json.loads(self.request.body.decode())
        result = await self.has_access(data.get('rids'), data.get('collection'))
        if result:
            await graph.get_collection()
        self.render_as_json(graph.to_dict())

    async def has_access(self, rids, collection):
        if not isinstance(rids, list):
            rids = [rids]
        username_signature = self.get_query_argument('username_signature').replace(' ', '+')
        if self.config.get_identity().get('username_signature') == username_signature or not self.config.restrict_graph_api:
            return True

        organzation = await self.config.mongo.async_site_db.organizations.find_one({'username_signature': username_signature})
        if organzation:
            parent_username_signature = self.config.get_identity().get('username_signature')
            child_username_signatures = [x.get('user', {}).get('username_signature') async for x in self.config.mongo.async_site_db.organization_members.find({'organization_username_signature': organzation.get('username_signature')})]
        else:
            organzation_member = await self.config.mongo.async_site_db.organization_members.find_one({'user.username_signature': username_signature})
            if organzation_member:
                parent_username_signature = organzation_member.get('organization_username_signature')
                child_username_signatures = [x.get('user', {}).get('username_signature') async for x in self.config.mongo.async_site_db.member_contacts.find({'member_username_signature': organzation_member.get('user', {}).get('username_signature')})]
            else:
                member_contact = await self.config.mongo.async_site_db.member_contacts.find_one({'user.username_signature': username_signature})
                if member_contact:
                    parent_username_signature = member_contact.get('member_username_signature')
                    child_username_signatures = []
                else:
                    return False

        base_groups = []
        for collection in Collections:
            base_groups.append(self.generate_rid(parent_username_signature, parent_username_signature, collection.value))
            base_groups.append(self.generate_rid(username_signature, username_signature, collection.value))
            base_groups.append(self.generate_rid(parent_username_signature, username_signature, collection.value))
            for child_username_signature in child_username_signatures:
                base_groups.append(self.generate_rid(child_username_signature, child_username_signature, collection.value))
                base_groups.append(self.generate_rid(username_signature, child_username_signature, collection.value))

        if len(set(base_groups) & set(rids)) == len(set(rids)):
            return True
        else:
            return False


class NSLookupHandler(BaseGraphHandler):
    async def get(self):
        ns_username = self.get_query_argument('username', None)
        ns_requested_rid = self.get_query_argument('requested_rid', None)
        ns_requester_rid = self.get_query_argument('requester_rid', None)
        id_type = self.get_query_argument('id_type', None)
        if ns_username:
            return self.render_as_json(await self.config.GU.search_ns_username(ns_username, ns_requested_rid, id_type))
        if ns_requested_rid:
            return self.render_as_json(await self.config.GU.search_ns_requested_rid(ns_requested_rid, ns_username, id_type))
        if ns_requester_rid:
            return self.render_as_json(await self.config.GU.search_ns_requester_rid(ns_requester_rid, ns_username, id_type))
        return self.render_as_json({"status": "error"}, 400)


class SignRawTransactionHandler(BaseHandler):
    async def post(self):
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif and self.jwt.get('key_or_wif') != 'true':
            return self.render_as_json({'error': 'not authorized'})
        config = self.config
        mongo = self.config.mongo
        body = json.loads(self.request.body.decode('utf-8'))
        try:
            fg = FastGraph.from_dict(0, body.get('txn'), raw=True)
            fg.verify()
        except:
            raise
            return 'invalid transaction', 400
        res = mongo.db.signed_transactions.find_one({'hash': body.get('hash')})
        if res:
            return 'no', 400
        try:
            rid = TU.generate_rid(config, body.get('username_signature'))
            my_entry_for_relationship = GU().get_transaction_by_rid(rid, config.wif, rid=True, my=True, public_key=config.public_key)
            their_entry_for_relationship = GU().get_transaction_by_rid(rid, rid=True, raw=True, theirs=True, public_key=config.public_key)
            verified = verify_signature(
                base64.b64decode(body.get('username_signature')),
                my_entry_for_relationship['relationship']['their_username'].encode(),
                bytes.fromhex(their_entry_for_relationship['public_key'])
            )
            if not verified:
                return 'no', 400
            verified = verify_signature(
                base64.b64decode(body.get('id')),
                body.get('hash').encode('utf-8'),
                bytes.fromhex(their_entry_for_relationship['public_key'])
            )
            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(their_entry_for_relationship['public_key'])))
            found = False
            async for x in self.config.BU.get_wallet_unspent_transactions(address, [body.get('input')]):
                if body.get('input') == x['id']:
                    found = True

            if not found:
                for x in self.config.BU.get_wallet_unspent_fastgraph_transactions(address):
                    if body.get('input') == x['id']:
                        found = True

            if found:
                signature = mongo.db.signed_transactions.find_one({
                    'input': body.get('input'),
                    'txn.public_key': body['txn']['public_key']
                })
                if signature:
                    already_spent = mongo.db.fastgraph_transactions.find_one({
                        'txn.inputs.id': body['input'],
                        'txn.public_key': body['txn']['public_key']
                    })
                    if already_spent:
                        self.set_status(400)
                        self.write('already spent!')
                        self.finish()
                        return True
                    else:
                        signature['txn']['signatures'] = [signature['signature']]
                        fastgraph = FastGraph.from_dict(0, signature['txn'])
                        try:
                            fastgraph.verify()
                        except Exception as e:
                            raise
                            return 'did not verify', 400
                        result = mongo.db.fastgraph_transactions.find_one({
                            'txn.hash': fastgraph.hash
                        })
                        if result:
                            return 'duplicate transaction found', 400
                        spent_check = mongo.db.fastgraph_transactions.find_one({
                            'txn.inputs.id': {'$in': [x.id for x in fastgraph.inputs]}
                        })
                        if spent_check:
                            return 'already spent input', 400
                        fastgraph.save()
            else:
                return 'no transactions with this input found', 400
            if verified:
                transaction_signature = TU.generate_signature_with_private_key(config.private_key, body.get('hash'))
                signature = {
                    'signature': transaction_signature,
                    'hash': body.get('hash'),
                    'username_signature': body.get('username_signature'),
                    'input': body.get('input'),
                    'id': body.get('id'),
                    'txn': body.get('txn')
                }
                mongo.db.signed_transactions.insert(signature)
                if '_id' in signature:
                    del signature['_id']
                self.render_as_json(signature, indent=4)
            else:
                return 'no', 400
        except Exception as e:
            raise
            self.render_as_json({
                'status': 'error',
                'msg': e
            })


class FastGraphHandler(BaseGraphHandler):
    async def post(self):
        # after the necessary signatures are gathered, the transaction is sent here.
        mongo = self.config.mongo
        graph = await self.get_base_graph()
        fastgraph = json.loads(self.request.body.decode('utf-8'))
        fastgraph = FastGraph.from_dict(0, fastgraph)
        try:
            fastgraph.verify()
        except Exception as e:
            raise
            return 'did not verify', 400
        result = mongo.db.fastgraph_transactions.find_one({
            'txn.hash': fastgraph.hash
        })
        if result:
            return 'duplicate transaction found', 400
        spent_check = mongo.db.fastgraph_transactions.find_one({
            'public_key': fastgraph.public_key,
            'txn.inputs.id': {'$in': [x.id for x in fastgraph.inputs]}
        })
        if spent_check:
            return 'already spent input', 400
        fastgraph.save()
        # TODO: use new peer framework to broadcast fastgraph transactions
        #fastgraph.broadcast()
        self.render_as_json(fastgraph.to_dict())
        try:
            await self.config.push_service.do_push(fastgraph.to_dict(), self.username_signature, self.app_log)
        except Exception as e:
            self.app_log.debug(e)


class NSHandler(BaseGraphHandler):
    async def get(self):
        graph = await self.get_base_graph()
        config = self.config
        phrase = self.get_query_argument('searchTerm', None)
        requester_rid = self.get_query_argument('requester_rid', None)
        requested_rid = self.get_query_argument('requested_rid', None)
        username = bool(self.get_query_argument('username', True))
        complete = bool(self.get_query_argument('complete', False))
        if not phrase and not requester_rid and not requested_rid:
            return 'phrase required', 400
        username_signature = self.get_query_argument('username_signature').replace(' ', '+')
        if not username_signature:
            return 'username_signature required', 400
        my_username_signature = config.get_username_signature()

        if requester_rid:
            query = {
                '$or': [
                    {'rid': requester_rid},
                    {'requester_rid': requester_rid}
                ]
            }
            if username:
                query['txn.relationship.their_username'] = {
                    '$exists': True
                }
            ns_record = await self.config.mongo.async_db.name_server.find_one(query, {'_id': 0})
            if ns_record:
                ns_record = ns_record['txn']
            else:
                ns_record = await graph.resolve_ns(requester_rid, username=True)

            if ns_record:
                requester_rid = ns_record['rid']
                rids = sorted([str(my_username_signature), str(username_signature)], key=str.lower)
                requested_rid = hashlib.sha256(rids[0].encode() + rids[1].encode()).hexdigest()

                address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(ns_record['public_key'])))
                filter_address = [x['to'] for x in ns_record['outputs'] if x['to'] != address]
                to = address if not filter_address else filter_address[0]
            else:
                return '{}', 404

            if complete:
                return self.render_as_json(ns_record)
            else:
                return self.render_as_json({
                    'username_signature': ns_record['relationship']['their_username_signature'],
                    'requested_rid': requested_rid,
                    'requester_rid': requester_rid,
                    'to': to,
                    'username': ns_record['relationship']['their_username']
                })

        rids = sorted([str(my_username_signature), str(username_signature)], key=str.lower)
        requester_rid = hashlib.sha256(rids[0].encode() + rids[1].encode()).hexdigest()
        if requested_rid:
            query = {
                'rid': requested_rid,
            }
            if username:
                query['username'] = {
                    'txn.relationship.their_username': {
                        '$exists': True
                    }
                }
            ns_record = await self.config.mongo.async_db.name_server.find_one(query)
            if ns_record:
                if complete:
                    return self.render_as_json(ns_record['txn'])
                else:
                    ns_record['txn']['relationship']['requested_rid'] = requested_rid
                    ns_record['txn']['relationship']['requester_rid'] = requester_rid
                    return self.render_as_json(ns_record['txn']['relationship'])
        else:
            friends = [x async for x in GU().search_username(phrase)]
            ns_records = await self.config.mongo.async_db.name_server.find({
                'txn.relationship.their_username': phrase,
            }).to_list(10)
            return self.render_as_json([x['txn'] for x in ns_records] + [x for x in friends])

    async def post(self):
        try:
            ns = json.loads(self.request.body.decode('utf-8'))
        except:
            return self.render_as_json({'status': 'error', 'message': 'invalid request body'})
        try:
            nstxn = Transaction.from_dict(ns['txn'])
        except:
            return self.render_as_json({'status': 'error', 'message': 'invalid transaction'})
        try:
            peer = Peer(ns['peer']['host'], ns['peer']['port'])
        except:
            return self.render_as_json({'status': 'error', 'message': 'invalid peer'})

        existing = await self.config.mongo.async_db.name_server.find_one({
            'rid': nstxn.rid,
            'requester_rid': nstxn.requester_rid,
            'requested_rid': nstxn.requested_rid,
            'peer_str': peer.to_string(),
        })
        if not existing:
            await self.config.mongo.async_db.name_server.insert_one({
                'rid': nstxn.rid,
                'requester_rid': nstxn.requester_rid,
                'requested_rid': nstxn.requested_rid,
                'peer_str': peer.to_string(),
                'peer': peer.to_dict(),
                'txn': nstxn.to_dict()
            })
        tb = NSBroadcaster(self.config)
        await tb.ns_broadcast_job(nstxn)
        return self.render_as_json({'status': 'success'})


class SiaFileHandler(BaseGraphHandler):
    async def get(self):
        from requests.auth import HTTPBasicAuth
        headers = {
            'User-Agent': 'Sia-Agent'
        }
        try:
            res = requests.get('http://0.0.0.0:9980/renter/files', headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
            fileData = json.loads(res.content.decode())
            files = fileData.get('files') or []

            return self.render_as_json({
                'status': 'success',
                'files': [
                    {
                        'siapath': x['siapath'],
                        'stream_url': 'http://0.0.0.0:9980/renter/stream/' + x['siapath'],
                        'available': x['available']
                    } for x in files
                ]
            })
        except:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })


class SiaStreamFileHandler(BaseGraphHandler):
    async def prepare(self):
        await super(SiaStreamFileHandler, self).prepare()
        header = "Content-Type"
        body = self.get_query_argument('mimetype')
        self.set_header(header, body)

    async def get(self):
        from requests.auth import HTTPBasicAuth
        headers = {
            'User-Agent': 'Sia-Agent'
        }
        siapath = self.get_query_argument('siapath')
        try:
            res = requests.get('http://0.0.0.0:9980/renter/file/{}'.format(siapath), headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        except:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })
        fileData = json.loads(res.content.decode())
        if fileData.get('file', {}).get('available'):
            url = 'http://0.0.0.0:9980/renter/stream/' + siapath.replace(' ', '%20')
            request = HTTPRequest(url=url, streaming_callback=self.on_chunk, request_timeout=2000000)
            await self.config.http_client.fetch(request)
        else:
            path = '/tmp/{}'.format(siapath)
            if os.path.isfile(path):
                with open(path, 'rb') as f:
                    data = f.read()
                    self.write(data)
            else:
                self.set_status(400)
                self.write('{"status": "error", "message": "file not available"}')
        self.finish()

    def on_chunk(self, chunk):
        self.write(chunk)
        self.flush()


class SiaUploadHandler(BaseGraphHandler):
    async def post(self):
        from requests.auth import HTTPBasicAuth
        from siaskynet import SkynetClient, utils
        sc = SkynetClient(self.config.skynet_url)
        json_body = json.loads(self.request.body)
        try:
            skylink = sc.upload({
                self.get_query_argument('filename'): base64.b64decode(json_body['file'])
            },
            {
                'custom_user_agent': 'Sia-Agent',
                'api_key': self.config.skynet_api_key,
                'extra_path': self.get_query_argument('filename')
            })
        except Exception as e:
            try:
                skylink = sc.upload({
                    self.get_query_argument('filename'): base64.b64decode(json_body['file'])
                },
                {
                    'custom_user_agent': 'Sia-Agent',
                    'api_key': self.config.skynet_api_key,
                    'extra_path': self.get_query_argument('filename') + '?dryrun=true'
                })
            except Exception as e:
                self.set_status(400)
                return self.render_as_json({
                    'status': 'error',
                    'message': 'sia node not responding'
                })
        return self.render_as_json({'status': 'success', 'skylink': utils.strip_prefix(skylink)})


class SiaDownloadHandler(BaseGraphHandler):
    async def get(self):
        from siaskynet import SkynetClient, utils
        sc = SkynetClient(self.config.skynet_url)
        skylink = '/skynet/skylink/' + self.get_query_argument('skylink')
        response = sc.download_file_request(skylink)
        for key, header in response.headers.items():
          self.set_header(key, header)
        self.write(response.content)
        self.finish()


class SiaUploadDirectoryHandler(BaseGraphHandler):
    async def post(self):
        import zipfile
        from requests.auth import HTTPBasicAuth
        from siaskynet import Skynet
        uploaded_file = self.request.files['file'][0]
        filename = self.get_query_argument('filename')
        local_filename = '/tmp/{}'.format(filename)
        with open(uploaded_file['filename'], 'wb') as f:
            f.write(uploaded_file['body'])
        with zipfile.ZipFile(uploaded_file['filename'], 'r') as zip_ref:
            zip_ref.extractall(local_filename + '/dir')
        try:
            opts = Skynet.default_upload_options()
            opts.portal_url = 'http://0.0.0.0:9980'
            skylink = Skynet.upload_directory(local_filename + '/dir')
        except Exception as e:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })
        return self.render_as_json({'status': 'success', 'skylink': Skynet.strip_prefix(skylink)})


class SiaShareFileHandler(BaseGraphHandler):
    async def get(self):
        from requests.auth import HTTPBasicAuth
        headers = {
            'User-Agent': 'Sia-Agent'
        }
        filename = self.get_query_argument('siapath')
        siapath = self.get_query_argument('siapath')
        try:
            res = requests.get('http://{}/skynet/skyfile/something?filename=?dst={}&siapath={}'.format(self.config.sia_server, dst + siapath.split('/')[-1] + '.sia', siapath), headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        except:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })
        with open(dst + siapath.split('/')[-1] + '.sia', 'rb') as f:
            data = f.read()
        bdata = base64.b64encode(data)
        return self.render_as_json({'filedata': bdata.decode()}) # this data will go in the relationship of the yada transaction


    async def post(self):
        from requests.auth import HTTPBasicAuth
        headers = {
            'User-Agent': 'Sia-Agent'
        }
        src='/home/mvogel/'
        relationship = json.loads(self.request.body.decode('utf-8'))
        siafiledata = base64.b64decode(relationship['groupChatFile'])
        with open(src + relationship['groupChatFileName'].split('/')[-1] + '.sia', 'wb') as f:
            f.write(bytearray(siafiledata))
        try:
            res = requests.get('http://0.0.0.0:9980/renter/file/{}'.format(relationship['groupChatFileName']), headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        except:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })
        fileData = json.loads(res.content.decode())
        if not fileData.get('file', None):
            res = requests.post('http://0.0.0.0:9980/renter/share/receive', {'src': src + relationship['groupChatFileName'] + '.sia', 'siapath': ''}, headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        return self.render_as_json({'status': 'success', 'stream_url': 'http://0.0.0.0:9980/renter/stream/' + relationship['groupChatFileName']})


class SiaDeleteHandler(BaseGraphHandler):
    async def get(self):
        from requests.auth import HTTPBasicAuth
        headers = {
            'User-Agent': 'Sia-Agent'
        }
        siapath = self.get_query_argument('siapath')
        try:
            res = requests.post('http://0.0.0.0:9980/renter/delete/{}'.format(siapath), headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        except:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })
        res = requests.get('http://0.0.0.0:9980/renter/files', headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        fileData = json.loads(res.content.decode())
        files = fileData.get('files') or []
        return self.render_as_json({
            'status': 'success',
            'files': [
                {
                    'siapath': x['siapath'],
                    'stream_url': 'http://0.0.0.0:9980/renter/stream/' + x['siapath'],
                    'available': x['available']
                } for x in files
            ]
        })


class WebSignInHandler(BaseGraphHandler):
    async def get(self):
        return self.render('web-sign-in.html')

    async def post(self):
        #self.config.app_log.info(self.request.body)
        return self.render_as_json({
          'success': False
        })


# these routes are placed in the order of operations for getting started.
GRAPH_HANDLERS = [
    (r'/yada-config', GraphConfigHandler), # first the config is requested
    (r'/get-graph-info', GraphInfoHandler), # then basic graph info is requested. Giving existing relationship information, if present.
    (r'/get-graph-wallet', GraphRIDWalletHandler), # request balance and UTXOs
    (r'/register', RegistrationHandler), # if a relationship is not present, we "register." client requests information necessary to generate a friend request transaction
    (r'/transaction', GraphTransactionHandler), # first the client submits their friend request transaction.
    (r'/get-graph-sent-friend-requests', GraphSentFriendRequestsHandler), # get all friend requests I've sent
    (r'/get-graph-friend-requests', GraphFriendRequestsHandler), # get all friend requests sent to me
    (r'/get-graph-friends', GraphFriendsHandler), # get client/server relationship. Same as get-graph-info, but here for symantic purposes
    (r'/get-graph-sent-messages', GraphSentMessagesHandler), # get new messages that are newer than a given timestamp
    (r'/get-graph-new-messages', GraphNewMessagesHandler), # get new messages that are newer than a given timestamp
    (r'/get-graph-reacts', GraphReactsHandler), # get reacts for posts and comments
    (r'/get-graph-comments', GraphCommentsHandler), # get comments for posts
    (r'/get-graph-collection', GraphCollectionHandler), # get calendar of events
    (r'/ns-lookup', NSLookupHandler), # search by username for ns name server.
    (r'/sign-raw-transaction', SignRawTransactionHandler), # server signs the client transaction
    (r'/post-fastgraph-transaction', FastGraphHandler), # fastgraph transaction is submitted by client
    (r'/sia-upload', SiaUploadHandler), # upload a file to your local sia renter
    (r'/sia-upload-dir', SiaUploadDirectoryHandler), # upload a directory to your local sia renter
    (r'/sia-files', SiaFileHandler), # list files from the local sia renter
    (r'/sia-files-stream', SiaStreamFileHandler), #stream the file from the sia network, we need this because of cross origin
    (r'/sia-share-file', SiaShareFileHandler), # share a file or list files from the local sia renter and return the .sia data base 64 encoded
    (r'/sia-delete', SiaDeleteHandler),
    (r'/ns', NSHandler), # name server endpoints
    (r'/sia-download', SiaDownloadHandler),
    (r'/web-signin', WebSignInHandler),
]
