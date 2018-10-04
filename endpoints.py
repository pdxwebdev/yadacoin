import json
import hashlib
import humanhash
import socket
import os
from multiprocessing import Process, Value, Array, Pool
from flask import Flask, render_template, request, Response
from socketIO_client import SocketIO, BaseNamespace
from flask_cors import CORS
from yadacoin import TransactionFactory, Transaction, \
                    MissingInputTransactionException, \
                    Input, Output, Block, Config, Peers, \
                    Blockchain, BlockChainException, BU, TU, \
                    Graph, Mongo, InvalidTransactionException, \
                    InvalidTransactionSignatureException
from eccsnacks.curve25519 import scalarmult, scalarmult_base
from pyfcm import FCMNotification
from flask.views import View


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

class TransactionView(View):
    def dispatch_request(self):
        if request.method == 'POST':
            items = request.json
            if not isinstance(items, list):
                items = [items, ]
            else:
                items = [item for item in items]
            transactions = []
            for txn in items:
                transaction = Transaction.from_dict(txn)
                try:
                    transaction.verify()
                except InvalidTransactionException:
                    Mongo.db.failed_transactions.insert({
                        'exception': 'InvalidTransactionException',
                        'txn': txn
                    })
                    print 'InvalidTransactionException'
                    return 'InvalidTransactionException', 400
                except InvalidTransactionSignatureException:
                    print 'InvalidTransactionSignatureException'
                    Mongo.db.failed_transactions.insert({
                        'exception': 'InvalidTransactionSignatureException',
                        'txn': txn
                    })
                    return 'InvalidTransactionSignatureException', 400
                except MissingInputTransactionException:
                    pass
                except:
                    raise
                    print 'uknown error'
                    return 'uknown error', 400
                transactions.append(transaction)

            for x in transactions:
                Mongo.db.miner_transactions.insert(x.to_dict())
            job = Process(target=TxnBroadcaster.txn_broadcast_job, args=(transaction,))
            job.start()
            if Config.fcm_key:
                for txn in transactions:
                    job = Process(
                        target=self.do_push,
                        args=(txn.to_dict(), request.args.get('bulletin_secret'))
                    )
                    job.start()
            return json.dumps(request.get_json())
        else:
            rid = request.args.get('rid')
            if rid:
                transactions = BU.get_transactions_by_rid(rid, rid=True, raw=True)
            else:
                transactions = []
            return json.dumps([x for x in transactions])

    def do_push(self, txn, bulletin_secret):
        my_bulletin_secret = Config.get_bulletin_secret()
        rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
        rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')

        res1 = Mongo.site_db.usernames.find({'rid': rid})
        if res1.count():
            username = res1[0]['username']
        else:
            username = humanhash.humanize(rid)

        if txn.get('relationship') and txn.get('dh_public_key') and txn.get('requester_rid') == rid:
            #friend request
            #if rid is the requester_rid, then we send a friend request notification to the requested_rid
            res = Mongo.site_db.fcmtokens.find({"rid": txn['requested_rid']})
            for token in res:
                result = push_service.notify_single_device(
                    registration_id=token['token'],
                    message_title='%s sent you a friend request!' % username,
                    message_body="See the request and approve!",
                    extra_kwargs={'priority': 'high'}
                )

        elif txn.get('relationship') and txn.get('dh_public_key') and txn.get('requested_rid') == rid:
            #friend accept
            #if rid is the requested_rid, then we send a friend accepted notification to the requester_rid
            res = Mongo.site_db.fcmtokens.find({"rid": txn['requester_rid']})
            for token in res:
                result = push_service.notify_single_device(
                    registration_id=token['token'],
                    message_title='%s approved your friend request!' % username,
                    message_body='Say "hi" to your friend!',
                    extra_kwargs={'priority': 'high'}
                )

        elif txn.get('relationship') and not txn.get('dh_public_key') and not txn.get('rid'):
            #post
            #we find all mutual friends of rid and send new post notifications to them
            rids = []
            rids.extend([x['requested_rid'] for x in BU.get_sent_friend_requests(rid)])
            rids.extend([x['requester_rid'] for x in BU.get_friend_requests(rid)])
            for friend_rid in rids:
                res = Mongo.site_db.fcmtokens.find({"rid": friend_rid})
                used_tokens = []
                for token in res:
                    if token['token'] in used_tokens:
                        continue
                    used_tokens.append(token['token'])

                    result = push_service.notify_single_device(
                        registration_id=token['token'],
                        message_title='%s has posted something!' % username,
                        message_body='Check out what your friend posted!',
                        extra_kwargs={'priority': 'high'}
                    )

        elif txn.get('relationship') and not txn.get('dh_public_key') and txn.get('rid'):
            #message
            #we find the relationship of the transaction rid and send a new message notification to the rid
            #of the relationship that does not match the arg rid
            txns = [x for x in BU.get_transactions_by_rid(txn['rid'], rid=True, raw=True)]
            rids = []
            rids.extend([x['requested_rid'] for x in txns if 'requested_rid' in x and rid != x['requested_rid']])
            rids.extend([x['requester_rid'] for x in txns if 'requester_rid' in x and rid != x['requester_rid']])
            for friend_rid in rids:
                res = Mongo.site_db.fcmtokens.find({"rid": friend_rid})
                used_tokens = []
                for token in res:
                    if token['token'] in used_tokens:
                        continue
                    used_tokens.append(token['token'])

                    result = push_service.notify_single_device(
                        registration_id=token['token'],
                        message_title='New message from %s!' % username,
                        message_body='Go see what your friend said!',
                        extra_kwargs={'priority': 'high'}
                    )
                    print result


class TxnBroadcaster(object):
    @classmethod
    def txn_broadcast_job(transaction):
        Peers.init()
        for peer in Peers.peers:
            try:
                socketIO = SocketIO(peer.host, peer.port, wait_for_connection=False)
                chat_namespace = socketIO.define(ChatNamespace, '/chat')
                chat_namespace.emit('newtransaction', transaction.to_dict())
                socketIO.wait(seconds=1)
                chat_namespace.disconnect()
            except Exception as e:
                pass

class BaseGraphView(View):
    def get_base_graph(self):
        raise NotImplemented("you should implement this method")

class GraphView(BaseGraphView):
    def dispatch_request(self):
        graph = self.get_base_graph()
        return graph.to_json()

class GraphSentFriendRequestsView(BaseGraphView):
    def dispatch_request(self):
        graph = self.get_base_graph()
        graph.get_sent_friend_requests()
        return graph.to_json()

class GraphFriendRequestsView(BaseGraphView):
    def dispatch_request(self):
        graph = self.get_base_graph()
        graph.get_friend_requests()
        return graph.to_json()

class GraphFriendsView(BaseGraphView):
    def dispatch_request(self):
        graph = self.get_base_graph()
        return graph.to_json()

class GraphPostsView(BaseGraphView):
    def dispatch_request(self):
        graph = self.get_base_graph()
        graph.get_posts()
        return graph.to_json()

class GraphMessagesView(BaseGraphView):
    def dispatch_request(self):
        graph = self.get_base_graph()
        graph.get_messages()
        return graph.to_json()

class GraphNewMessagesView(BaseGraphView):
    def dispatch_request(self):
        graph = self.get_base_graph()
        graph.get_new_messages()
        return graph.to_json()


class WalletView(View):
    def dispatch_request(self):
        address = request.args.get('address')
        wallet = {
            'balance': BU.get_wallet_balance(address),
            'unspent_transactions': [x for x in BU.get_wallet_unspent_transactions(address)]
        }
        return json.dumps(wallet, indent=4)

class FaucetView(View):
    def dispatch_request(self):
        address = request.args.get('address')
        if len(address) < 36:
            exists = Mongo.site_db.faucet.find({
                'address': address
            })
            if not exists.count():
                Mongo.site_db.faucet.insert({
                    'address': address,
                    'active': True
                })
            return json.dumps({'status': 'ok'})
        else:
            return json.dumps({'status': 'error'}), 400

class RegisterView(View):
    def dispatch_request(self):
        data = {
            'bulletin_secret': Config.get_bulletin_secret(),
            'username': Config.username,
            'callbackurl': Config.callbackurl,
            'to': Config.address
        }
        return json.dumps(data, indent=4)
