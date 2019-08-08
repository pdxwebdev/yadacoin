"""
Handlers required by the graph operations
"""

import base64
import hashlib
import json
import os
import time
import requests

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve.utils import verify_signature
from eccsnacks.curve25519 import scalarmult_base
from logging import getLogger
from threading import Thread

from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU
from yadacoin.fastgraph import FastGraph
from yadacoin.graph import Graph
from yadacoin.graphutils import GraphUtils as GU
from yadacoin.transaction import TransactionFactory, Transaction, InvalidTransactionException, \
    InvalidTransactionSignatureException, MissingInputTransactionException
from yadacoin.transactionutils import TU
from yadacoin.transactionbroadcaster import TxnBroadcaster
from yadacoin.peers import Peer


class GraphConfigHandler(BaseHandler):

    async def get(self):
        if int(self.config.web_server_port) == 443:
            peer = "https://{}:{}".format(self.config.web_server_host, self.config.web_server_port)
        else:
            peer = "http://{}:{}".format(self.config.web_server_host, self.config.web_server_port)
        yada_config = {
            "baseUrl": "{}".format(peer),
            "transactionUrl": "{}/transaction".format(peer),
            "fastgraphUrl": "{}/post-fastgraph-transaction".format(peer),
            "graphUrl": "{}".format(peer),
            "walletUrl": "{}/get-graph-wallet".format(peer),
            "loginUrl": "{}/login".format(peer),
            "registerUrl": "{}/create-relationship".format(peer),
            "authenticatedUrl": "{}/authenticated".format(peer),
            "logoData": ''
        }
        return self.render_as_json(yada_config)


class BaseGraphHandler(BaseHandler):
    def get_base_graph(self):
        self.bulletin_secret = self.get_query_argument('bulletin_secret').replace(' ', '+')
        if self.request.body:
            ids = json.loads(self.request.body.decode('utf-8')).get('ids')
        else:
            ids = []
        try:
            key_or_wif = self.get_secure_cookie('key_or_wif').decode()
        except:
            key_or_wif = None
        return Graph(self.config, self.config.mongo, self.bulletin_secret, ids, key_or_wif)
        # TODO: should have a self.render here instead, not sure what is supposed to be returned here


class GraphInfoHandler(BaseGraphHandler):

    async def get(self):
        graph = self.get_base_graph()
        self.render_as_json(graph.to_dict())

class GraphRIDWalletHandler(BaseGraphHandler):

    async def get(self):
        graph = self.get_base_graph()
        config = self.config
        address = self.get_query_argument('address')
        bulletin_secret = self.get_query_argument('bulletin_secret').replace(' ', "+")
        amount_needed = self.get_query_argument('amount_needed', None)
        if amount_needed:
            amount_needed = int(amount_needed)
        rid = TU.generate_rid(config, bulletin_secret)
        
        unspent_transactions = [x for x in BU().get_wallet_unspent_transactions(address)]
        spent_txn_ids = []
        
        for x in unspent_transactions:
            spent_txn_ids.extend([y['id'] for y in x['inputs']])

        unspent_fastgraph_transactions = [x for x in BU().get_wallet_unspent_fastgraph_transactions(address) if x['id'] not in spent_txn_ids]
        spent_fastgraph_ids = []
        for x in unspent_fastgraph_transactions:
            spent_fastgraph_ids.extend([y['id'] for y in x['inputs']])
        regular_txns = []
        txns_for_fastgraph = []
        chain_balance = 0
        fastgraph_balance = 0
        for txn in unspent_transactions + unspent_fastgraph_transactions:
            if 'signatures' in txn and txn['signatures']:
                fastgraph = FastGraph.from_dict(0, txn)
                origin_fasttrack = fastgraph.get_origin_relationship(rid)
                if origin_fasttrack or (('rid' in txn and txn['rid'] == rid) or txn.get('requester_rid') == rid or txn.get('requested_rid') == rid):
                    txns_for_fastgraph.append(txn)
                    for output in txn['outputs']:
                        if output['to'] == address:
                            fastgraph_balance += int(output['value'])
                else:
                    regular_txns.append(txn)
                    for output in txn['outputs']:
                        if output['to'] == address:    
                            chain_balance += int(output['value'])
            elif 'dh_public_key' in txn and txn['dh_public_key'] and (('rid' in txn and txn['rid'] == rid) or txn.get('requester_rid') == rid or txn.get('requested_rid') == rid):
                txns_for_fastgraph.append(txn)
                for output in txn['outputs']:
                    if output['to'] == address:
                        fastgraph_balance += int(output['value'])
            else:
                regular_txns.append(txn)
                for output in txn['outputs']:
                    if output['to'] == address:
                        chain_balance += int(output['value'])
    
        wallet = {
            'chain_balance': chain_balance,
            'fastgraph_balance': fastgraph_balance,
            'balance': fastgraph_balance + chain_balance,
            'unspent_transactions': regular_txns,
            'txns_for_fastgraph': txns_for_fastgraph
        }
        self.render_as_json(wallet, indent=4)


class RegistrationHandler(BaseHandler):

    async def get(self):
        data = {
            'bulletin_secret': self.config.bulletin_secret,
            'username': self.config.username,
            'callbackurl': self.config.callbackurl,
            'to': self.config.address
        }
        self.render_as_json(data)


class GraphTransactionHandler(BaseGraphHandler):

    async def get(self):
        rid = self.request.args.get('rid')
        if rid:
            transactions = BU().get_transactions_by_rid(rid, self.config.bulletin_secret, rid=True, raw=True)
        else:
            transactions = []
        self.render_as_json(list(transactions))

    async def post(self):
        self.get_base_graph()  # TODO: did this to set bulletin_secret, refactor this
        items = json.loads(self.request.body.decode('utf-8'))
        if not isinstance(items, list):
            items = [items, ]
        else:
            items = [item for item in items]
        transactions = []
        for txn in items:
            transaction = Transaction.from_dict(BU().get_latest_block()['index'], txn)
            try:
                transaction.verify()
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
            await self.config.mongo.async_db.miner_transactions.insert_one(x.to_dict())
            try:
                self.config.push_service.do_push(x.to_dict(), self.bulletin_secret, self.app_log)
            except Exception as e:
                print(e)
                print('do_push failed')
        txn_b = TxnBroadcaster(self.config)
        await txn_b.txn_broadcast_job(transaction)

        return self.render_as_json(items)


class CreateRelationshipHandler(BaseHandler):

    async def post(self):
        config = self.config
        mongo = self.config.mongo
        kwargs = json.loads(self.request.body.decode('utf-8'))
        bulletin_secret = kwargs.get('bulletin_secret', '')
        username = kwargs.get('username', '')
        to = kwargs.get('to', '')

        if not bulletin_secret:
            return 'error: "bulletin_secret" missing', 400

        if not username:
            return 'error: "username" missing', 400

        if not to:
            return 'error: "to" missing', 400
        rid = TU.generate_rid(config, bulletin_secret)
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

        transaction = TransactionFactory(
            block_height=BU().get_latest_block()['index'],
            bulletin_secret=bulletin_secret,
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

        mongo.db.miner_transactions.insert(transaction.transaction.to_dict())
        """
        # TODO: integrate new socket/peer framework for transmitting txns

        job = Process(target=TxnBroadcaster.txn_broadcast_job, args=(transaction.transaction,))
        job.start()
        """

        self.render_as_json({"success": True})


class GraphSentFriendRequestsHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        graph.get_sent_friend_requests()
        self.render_as_json(graph.to_dict())


class GraphFriendRequestsHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        graph.get_friend_requests()
        self.render_as_json(graph.to_dict())


class GraphFriendsHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        self.render_as_json(graph.to_dict())


class GraphPostsHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        graph.get_posts()
        self.render_as_json(graph.to_dict())


class GraphMessagesHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        await graph.get_messages()
        self.render_as_json(graph.to_dict())


class GraphGroupMessagesHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        graph.get_group_messages()
        self.render_as_json(graph.to_dict())


class GraphNewMessagesHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        graph.get_new_messages()
        self.render_as_json(graph.to_dict())


class GraphCommentsHandler(BaseGraphHandler):
    async def post(self):
        graph = self.get_base_graph()
        graph.get_comments()
        self.render_as_json(graph.to_dict())


class GraphReactsHandler(BaseGraphHandler):
    async def post(self):
        graph = self.get_base_graph()
        graph.get_reacts()
        self.render_as_json(graph.to_dict())


class SearchHandler(BaseHandler):
    async def get(self):
        config = self.config
        phrase = self.get_query_argument('phrase', None)
        requester_rid = self.get_query_argument('requester_rid', None)
        if not phrase and not requester_rid:
            return 'phrase required', 400
        bulletin_secret = self.get_query_argument('bulletin_secret').replace(' ', '+')
        if not bulletin_secret:
            return 'bulletin_secret required', 400
        my_bulletin_secret = config.get_bulletin_secret()

        if requester_rid:
            friend = [x for x in GU().search_rid(requester_rid)][0]
            requester_rid = friend['rid']
            rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
            requested_rid = hashlib.sha256(rids[0].encode() + rids[1].encode()).hexdigest()
        else:
            rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
            requester_rid = hashlib.sha256(rids[0].encode() + rids[1].encode()).hexdigest()
            friend = [x for x in GU().search_username(phrase)][0]
            requested_rid = friend['rid']
        
        if friend:
            to = [x['to'] for x in friend['outputs'] if x['to'] != config.address][0]
        else:
            return '{}', 404
        self.render_as_json({
            'bulletin_secret': friend['relationship']['their_bulletin_secret'],
            'requested_rid': requested_rid,
            'requester_rid': requester_rid,
            'to': to,
            'username': friend['relationship']['their_username']
        })


class SignRawTransactionHandler(BaseHandler):
    async def post(self):
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
            rid = TU.generate_rid(config, body.get('bulletin_secret'))
            my_entry_for_relationship = GU().get_transaction_by_rid(rid, config.wif, rid=True, my=True, public_key=config.public_key)
            their_entry_for_relationship = GU().get_transaction_by_rid(rid, rid=True, raw=True, theirs=True, public_key=config.public_key)
            verified = verify_signature(
                base64.b64decode(body.get('bulletin_secret')),
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
            for x in BU().get_wallet_unspent_transactions(address, [body.get('input')]):
                if body.get('input') == x['id']:
                    found = True
            
            if not found:
                for x in BU().get_wallet_unspent_fastgraph_transactions(address):
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
                    'bulletin_secret': body.get('bulletin_secret'),
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
        graph = self.get_base_graph()
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
            await self.config.push_service.do_push(fastgraph.to_dict(), self.bulletin_secret, self.app_log)
        except Exception as e:
            self.app_log.error(e)


# these routes are placed in the order of operations for getting started.
GRAPH_HANDLERS = [
    (r'/yada_config.json', GraphConfigHandler), # first the config is requested
    (r'/get-graph-info', GraphInfoHandler), # then basic graph info is requested. Giving existing relationship information, if present.
    (r'/get-graph-wallet', GraphRIDWalletHandler), # request balance and UTXOs
    (r'/register', RegistrationHandler), # if a relationship is not present, we "register." client requests information necessary to generate a friend request transaction
    (r'/transaction', GraphTransactionHandler), # first the client submits their friend request transaction.
    (r'/create-relationship', CreateRelationshipHandler), # this generates and submits an friend accept transaction. You're done registering once these are on the blockchain.
    (r'/get-graph-sent-friend-requests', GraphSentFriendRequestsHandler), # get all friend requests I've sent
    (r'/get-graph-friend-requests', GraphFriendRequestsHandler), # get all friend requests sent to me
    (r'/get-graph-friends', GraphFriendsHandler), # get client/server relationship. Same as get-graph-info, but here for symantic purposes
    (r'/get-graph-posts', GraphPostsHandler), # get posts from friends that are mutual friends of client/server
    (r'/get-graph-messages', GraphMessagesHandler), # get messages from friends
    (r'/get-graph-new-messages', GraphNewMessagesHandler), # get new messages that are newer than a given timestamp
    (r'/get-graph-reacts', GraphReactsHandler), # get reacts for posts and comments
    (r'/get-graph-comments', GraphCommentsHandler), # get comments for posts
    (r'/search', SearchHandler), # search by username for friend of server. Server provides necessary information to generate friend request transaction, just like /register for the server.
    (r'/sign-raw-transaction', SignRawTransactionHandler), # server signs the client transaction
    (r'/post-fastgraph-transaction', FastGraphHandler), # fastgraph transaction is submitted by client
]
