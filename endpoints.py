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

app = Flask(__name__)
app.debug = True
app.secret_key = '23ljk2l9a08sd7f09as87df09as87df3k4j'
CORS(app)


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

@app.route('/transaction', methods=['GET', 'POST'])
def transaction():
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
        job = Process(target=txn_broadcast_job, args=(transaction,))
        job.start()
        if Config.fcm_key:
            for txn in transactions:
                job = Process(
                    target=do_push,
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

def do_push(txn, bulletin_secret):
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

def get_base_graph():
    bulletin_secret = request.args.get('bulletin_secret').replace(' ', '+')
    if bulletin_secret != Config.get_bulletin_secret():
        found = False
        for filename in os.listdir('config'):
            if filename.endswith(".json"):
                with open(os.path.join('config', filename)) as f:
                    config = json.loads(f.read())
                    if 'bulletin_secret' in config and config['bulletin_secret'] == bulletin_secret:
                        Config.from_dict(config)
                        found = True
        if not found:
            raise Exception("Config file not found for bulletin_secret: %s" % bulletin_secret)
    graph = Graph(bulletin_secret, wallet_mode=True)
    return graph

@app.route('/get-graph-info')
def get_graph_info():
    graph = get_base_graph()
    return graph.to_json()

@app.route('/get-graph-sent-friend-requests')
def get_sent_friend_requests():
    graph = get_base_graph()
    graph.get_sent_friend_requests()
    return graph.to_json()

@app.route('/get-graph-friend-requests')
def get_friend_requests():
    graph = get_base_graph()
    graph.get_friend_requests()
    return graph.to_json()

@app.route('/get-graph-friends')
def get_get_friends():
    graph = get_base_graph()
    return graph.to_json()

@app.route('/get-graph-posts')
def get_graph_posts():
    graph = get_base_graph()
    graph.get_posts()
    return graph.to_json()

@app.route('/get-graph-messages')
def get_graph_messages():
    graph = get_base_graph()
    graph.get_messages()
    return graph.to_json()

@app.route('/get-graph-new-messages')
def get_graph_new_messages():
    graph = get_base_graph()
    graph.get_new_messages()
    return graph.to_json()

@app.route('/get-graph')
def get_graph():
    graph = Graph(Config.get_bulletin_secret(), for_me=True)
    return graph.to_json()

@app.route('/wallet')
def get_wallet():
    address = request.args.get('address')
    wallet = {
        'balance': BU.get_wallet_balance(address),
        'unspent_transactions': [x for x in BU.get_wallet_unspent_transactions(address)]
    }
    return json.dumps(wallet, indent=4)

@app.route('/faucet')
def faucet():
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

@app.route('/firebase-messaging-sw.js')
def firebase_service_worker():
    return app.send_static_file('app/www/ServiceWorker.js')

@app.route('/fcm-token', methods=['POST'])
def fcm_token():
    try:
        token = request.json.get('token')
        print token
        rid = request.json.get('rid')
        txn = BU.get_transaction_by_rid(rid, rid=True) 
        Mongo.site_db.fcmtokens.update({'rid': rid}, {
            'rid': rid,
            'token': token
        }, upsert=True)
        return '', 200
    except Exception as e:
        return '', 400

@app.route('/get-usernames')
def get_username():
    res = Mongo.site_db.usernames.find({'rid': {'$in': request.args.get('rids')}}, {'_id': 0})
    if res.count():
        out = {}
        for x in res:
            out[x['rid']] = x['username']
        return json.dumps(out)
    else:
        return '{}'

@app.route('/change-username', methods=['POST'])
def change_username():
    request.json['username'] = request.json['username'].lower()
    exists = Mongo.site_db.usernames.find({
        'username': request.json.get('username')
    })
    if exists.count():
        return 'username taken', 400
    Mongo.site_db.usernames.update(
        {
            'rid': request.json.get('rid')
        },
        request.json,
        upsert=True
    )
    return 'ok'

@app.route('/create-relationship', methods=['GET', 'POST'])
def create_relationship():  # demo site
    if request.method == 'GET':
        bulletin_secret = request.args.get('bulletin_secret', '')
        username = request.args.get('username', '')
        to = request.args.get('to', '')
    else:
        bulletin_secret = request.json.get('bulletin_secret', '')
        username = request.json.get('username', '')
        to = request.json.get('to', '')

    if not bulletin_secret:
        return 'error: "bulletin_secret" missing', 400

    if not username:
        return 'error: "username" missing', 400

    if not to:
        return 'error: "to" missing', 400

    rid = TU.generate_rid(bulletin_secret)
    dup = Mongo.db.blocks.find({'transactions.rid': rid})
    if dup.count():
        for txn in dup:
            if txn['public_key'] == Config.public_key:
                return json.dumps({"success": False, "status": "Already added"})
    input_txns = BU.get_wallet_unspent_transactions(Config.address)

    miner_transactions = Mongo.db.miner_transactions.find()
    mtxn_ids = []
    for mtxn in miner_transactions:
        for mtxninput in mtxn['inputs']:
            mtxn_ids.append(mtxninput['id'])

    checked_out_txn_ids = Mongo.db.checked_out_txn_ids.find()
    for mtxn in checked_out_txn_ids:
        mtxn_ids.append(mtxn['id'])


    a = os.urandom(32)
    dh_public_key = scalarmult_base(a).encode('hex')
    dh_private_key = a.encode('hex')

    transaction = TransactionFactory(
        bulletin_secret=bulletin_secret,
        username=username,
        fee=0.01,
        public_key=Config.public_key,
        dh_public_key=dh_public_key,
        private_key=Config.private_key,
        dh_private_key=dh_private_key,
        outputs=[
            Output(to=to, value=1)
        ]
    )

    TU.save(transaction.transaction)

    Mongo.db.miner_transactions.insert(transaction.transaction.to_dict())
    job = Process(target=txn_broadcast_job, args=(transaction.transaction,))
    job.start()


    my_bulletin_secret = Config.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
    Mongo.site_db.friends.insert({'rid': rid, 'relationship': {'bulletin_secret': bulletin_secret}})
    return json.dumps({"success": True})

@app.route('/register')
def register():
    data = {
        'bulletin_secret': Config.get_bulletin_secret(),
        'username': Config.username,
        'callbackurl': Config.callbackurl,
        'to': Config.address
    }
    return json.dumps(data, indent=4)
