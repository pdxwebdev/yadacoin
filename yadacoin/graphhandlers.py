"""
Handlers required by the graph operations
"""

import json
import os
import hashlib
import base64
from eccsnacks.curve25519 import scalarmult, scalarmult_base
from coincurve.utils import verify_signature
from bitcoin.wallet import P2PKHBitcoinAddress
from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU
from yadacoin.transactionutils import TU
from yadacoin.graph import Graph
from yadacoin.graphutils import GraphUtils as GU
from yadacoin.fastgraph import FastGraph
from yadacoin.transaction import (
    TransactionFactory,
    Transaction,
    InvalidTransactionException,
    InvalidTransactionSignatureException,
    MissingInputTransactionException
)


class GraphConfigHandler(BaseHandler):

    async def get(self):
        peer = "http://{}:{}".format(self.config.serve_host, self.config.peer_port)
        return self.render_as_json({
            "baseUrl": "{}".format(peer),
            "transactionUrl": "{}/transaction".format(peer),
            "fastgraphUrl": "{}/post-fastgraph-transaction".format(peer),
            "graphUrl": "{}".format(peer),
            "walletUrl": "{}/get-graph-wallet".format(peer),
            "loginUrl": "{}/login".format(peer),
            "registerUrl": "{}/create-relationship".format(peer),
            "authenticatedUrl": "{}/authenticated".format(peer),
            "logoData": ''
        })

class BaseGraphHandler(BaseHandler):
    def get_base_graph(self):
        bulletin_secret = self.get_query_argument('bulletin_secret').replace(' ', '+')
        if self.request.body:
            ids = json.loads(self.request.body.decode('utf-8')).get('ids')
        else:
            ids = []
        return Graph(self.config, self.config.mongo, bulletin_secret, ids)

class GraphInfoHandler(BaseGraphHandler):

    async def get(self):
        graph = self.get_base_graph()
        self.write(graph.to_json())
        self.finish()
        return True

class GraphRIDWalletHandler(BaseHandler):

    async def get(self):
        config = self.config
        address = self.get_query_argument('address')
        bulletin_secret = self.get_query_argument('bulletin_secret').replace(' ', "+")
        rid = TU.generate_rid(config, bulletin_secret)
        unspent_transactions = [x for x in BU().get_wallet_unspent_transactions(address)]
        spent_txn_ids = []
        for x in unspent_transactions:
            spent_txn_ids.extend([y['id'] for y in x['inputs']])

        unspent_fastgraph_transactions = [x for x in BU().get_wallet_unspent_fastgraph_transactions(address) if x['id'] not in spent_txn_ids]
        print('fastgraph uspent txn ids:')
        print([x['id'] for x in unspent_fastgraph_transactions])
        spent_fastgraph_ids = []
        for x in unspent_fastgraph_transactions:
            spent_fastgraph_ids.extend([y['id'] for y in x['inputs']])
        print('regular unspent txn ids:')
        print([x['id'] for x in unspent_transactions])
        regular_txns = []
        txns_for_fastgraph = []
        for txn in unspent_transactions:
            if 'signatures' in txn and txn['signatures']:
                fastgraph = FastGraph.from_dict(0, txn)
                origin_fasttrack = fastgraph.get_origin_relationship(rid)
                if origin_fasttrack:
                    txns_for_fastgraph.append(txn)
                else:
                    regular_txns.append(txn)
            else:
                if 'rid' in txn and txn['rid'] == rid and 'dh_public_key' in txn and txn['dh_public_key']:
                    txns_for_fastgraph.append(txn)
                else:
                    regular_txns.append(txn)
        #print(unspent_fastgraph_transactions)
        if unspent_fastgraph_transactions:
            txns_for_fastgraph.extend(unspent_fastgraph_transactions)
        print('final txn ids:')
        print([x['id'] for x in txns_for_fastgraph])
        wallet = {
            'balance': BU().get_wallet_balance(address),
            'unspent_transactions': regular_txns,
            'txns_for_fastgraph': txns_for_fastgraph
        }
        return self.render_as_json(wallet, indent=4)


class RegistrationHandler(BaseHandler):

    async def get(self):

        data = {
            'bulletin_secret': self.config.bulletin_secret,
            'username': self.config.username,
            'callbackurl': self.config.callbackurl,
            'to': self.config.address
        }
        self.render_as_json(data)


class GraphTransactionHandler(BaseHandler):

    async def get(self):
        rid = self.request.args.get('rid')
        if rid:
            transactions = BU().get_transactions_by_rid(rid, self.config.bulletin_secret, rid=True, raw=True)
        else:
            transactions = []
        return json.dumps([x for x in transactions])
    
    async def post(self):
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
                self.config.mongo.async_db.failed_transactions.insert({
                    'exception': 'InvalidTransactionException',
                    'txn': txn
                })
                print('InvalidTransactionException')
                return 'InvalidTransactionException', 400
            except InvalidTransactionSignatureException:
                print('InvalidTransactionSignatureException')
                self.config.mongo.async_db.failed_transactions.insert({
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
            self.config.mongo.async_db.miner_transactions.insert_one(x.to_dict())
        """
        # TODO: integrate new socket/peer framework for transmitting txns

        job = Process(target=TxnBroadcaster.txn_broadcast_job, args=(transaction,))
        job.start()
        """
        self.render_as_json(items)


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
        self.write(graph.to_json())
        self.finish()


class GraphFriendRequestsHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        graph.get_friend_requests()
        self.write(graph.to_json())
        self.finish()


class GraphFriendsHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        self.write(graph.to_json())
        self.finish()


class GraphPostsHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        graph.get_posts()
        self.write(graph.to_json())
        self.finish()


class GraphMessagesHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        graph.get_messages()
        self.write(graph.to_json())
        self.finish()


class GraphNewMessagesHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        graph.get_new_messages()
        self.write(graph.to_json())
        self.finish()


class GraphCommentsHandler(BaseGraphHandler):
    async def post(self):
        graph = self.get_base_graph()
        graph.get_comments()
        self.write(graph.to_json())
        self.finish()


class GraphReactsHandler(BaseGraphHandler):
    async def post(self):
        graph = self.get_base_graph()
        graph.get_reacts()
        self.write(graph.to_json())
        self.finish()


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
                signature = mongo.db.signed_transactions.find_one({'input': body.get('input')})
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
                    self.set_status(400)
                    self.write('already signed!')
                    self.finish()
                    return True
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


class FastGraphHandler(BaseHandler):
    async def post(self):
        # after the necessary signatures are gathered, the transaction is sent here.
        mongo = self.config.mongo
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
            'txn.inputs.id': {'$in': [x.id for x in fastgraph.inputs]}
        })
        if spent_check:
            return 'already spent input', 400
        fastgraph.save()
        # TODO: use new peer framework to broadcast fastgraph transactions
        #fastgraph.broadcast()
        self.render_as_json(fastgraph.to_dict())

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
