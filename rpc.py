import json
import hashlib
import os
import argparse
import qrcode
import base64
import humanhash
import requests
import time
import logging

from logging.handlers import SMTPHandler
from io import BytesIO
from uuid import uuid4
from ecdsa import NIST384p, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from flask import Flask, request, render_template, session, redirect
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from blockchainutils import BU
from transactionutils import TU
from transaction import *
from block import Block
from graph import Graph
from pymongo import MongoClient
from socketIO_client import SocketIO, BaseNamespace
from pyfcm import FCMNotification
from multiprocessing import Process, Value, Array, Pool
from flask_cors import CORS
from eccsnacks.curve25519 import scalarmult, scalarmult_base


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

app = Flask(__name__)
CORS(app)
mail_handler = SMTPHandler(
    mailhost='127.0.0.1',
    fromaddr='localhost',
    toaddrs=['info@yadacoin.io'],
    subject='Application Error'
)
mail_handler.setLevel(logging.ERROR)
mail_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        ))
app.logger.addHandler(mail_handler)

def make_qr(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    out = BytesIO()
    qr_img = qr.make_image()
    qr_img = qr_img.convert("RGBA")
    qr_img.save(out, 'PNG')
    out.seek(0)
    return u"data:image/png;base64," + base64.b64encode(out.getvalue()).decode('ascii')

def get_logged_in_user():
    user = None
    tests = []
    res = mongo_client.yadacoin.blocks.aggregate([
        {
            "$match": {
                "transactions.challenge_code": session['challenge_code']
            }
        },
        {
            '$unwind': "$transactions"
        },
        {
            "$match": {
                "transactions.challenge_code": session['challenge_code']
            }
        }
    ])
    for transaction in res:
        transaction = transaction['transactions']
        tests = BU.get_transactions_by_rid(transaction['rid'], rid=True)
        for test in tests:
            if 'relationship' in test and 'shared_secret' in test['relationship']:
                cipher = Crypt(hashlib.sha256(test['relationship']['shared_secret']).digest().encode('hex'))
                answer = cipher.decrypt(transaction['answer'])
                if answer == transaction['challenge_code']:
                    for txn_output in transaction['outputs']:
                        if txn_output['to'] != my_address:
                            to = txn_output['to']
                    user = {
                        'balance': BU.get_wallet_balance(to),
                        'authenticated': True,
                        'rid': transaction['rid'],
                        'bulletin_secret': test['relationship']['bulletin_secret']
                    }
    return user if user else {'authenticated': False}

@app.route('/app')
def web_app():
    return app.send_static_file('app/www/index.html')

@app.route('/reset')
def reset():
    with open('blockchain.json', 'w') as f:
        f.write(json.dumps({'blocks':[]},indent=4))
    return 'ok'

@app.route('/blockchain')
def get_blockchain():
    with open('blockchain.json') as f:
        data = f.read()
    if request.args.get('poplastblock'):
        blocks = json.loads(data)
        blocks['blocks'].pop()
        with open('blockchain.json', 'w') as f:
            f.write(json.dumps(blocks, indent=4))
        with open('blockchain.json') as f:
            data = f.read()
    return json.dumps(json.loads(data), indent=4)

@app.route('/')
def index():
    return render_template(
        'index.html',
        )

@app.route('/team')
def team():
    return render_template(
        'team.html',
        )

@app.route('/register')
def register():
    data = {
        'bulletin_secret': TU.get_bulletin_secret(),
        'callbackurl': config.get('callbackurl'),
        'to': my_address
    }
    return json.dumps(data, indent=4)

@app.route('/create-relationship', methods=['GET', 'POST'])
def create_relationship():  # demo site
    if request.method == 'GET':
        bulletin_secret = request.args.get('bulletin_secret', '')
        to = request.args.get('to', '')
    else:
        bulletin_secret = request.json.get('bulletin_secret', '')
        to = request.json.get('to', '')

    if not bulletin_secret:
        return 'error: "bulletin_secret" missing', 400

    if not to:
        return 'error: "to" missing', 400

    input_txns = BU.get_wallet_unspent_transactions(my_address)

    miner_transactions = db.miner_transactions.find()
    mtxn_ids = []
    for mtxn in miner_transactions:
        for mtxninput in mtxn['inputs']:
            mtxn_ids.append(mtxninput['id'])

    checked_out_txn_ids = db.checked_out_txn_ids.find()
    for mtxn in checked_out_txn_ids:
        mtxn_ids.append(mtxn['id'])

    needed_inputs = []
    input_sum = 0
    done = False
    for x in input_txns:
        if x['id'] in mtxn_ids:
            continue
        x = Input.from_dict(x)
        txn = BU.get_transaction_by_id(x.id, instance=True)
        for txn_output in txn.outputs:
            if txn_output.to == my_address:
                input_sum += txn_output.value
                needed_inputs.append(x)
                db.checked_out_txn_ids.insert({'id': x.id})
                if input_sum >= 1.1:
                    done = True
                    break
        if done == True:
            break

    return_change_output = Output(
        to=my_address,
        value=input_sum-1.1
    )

    a = os.urandom(32)
    dh_public_key = scalarmult_base(a).encode('hex')
    dh_private_key = a.encode('hex')

    transaction = TransactionFactory(
        bulletin_secret=bulletin_secret,
        fee=0.1,
        public_key=public_key,
        dh_public_key=dh_public_key,
        private_key=private_key,
        dh_private_key=dh_private_key,
        inputs=needed_inputs,
        outputs=[
            Output(to=to, value=1),
            return_change_output
        ]
    )

    TU.save(transaction.transaction)

    db.miner_transactions.insert(transaction.transaction.to_dict())
    job = Process(target=txn_broadcast_job, args=(transaction.transaction,))
    job.start()

    mongo_client = MongoClient('localhost')

    my_bulletin_secret = TU.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
    mongo_client.yadacoinsite.friends.insert({'rid': rid, 'relationship': {'bulletin_secret': bulletin_secret}})
    return json.dumps({"success": True})

@app.route('/login-status')
def login_status():
    user = get_logged_in_user()
    return json.dumps(user)

@app.route('/show-user')
def show_user():
    authed_user = get_logged_in_user()
    user = BU.get_transaction_by_rid(request.args['rid'], rid=True)
    for output in user['outputs']:
        if output['to'] != my_address:
            to = output['to']
    dict_data = {
        'bulletin_secret': user['relationship']['bulletin_secret'],
        'requested_rid': user['rid'],
        'requester_rid': authed_user['rid'],
        'to': to
    }
    data = json.dumps(dict_data)
    qr_code = make_qr(data)
    return render_template(
        'show-user.html',
        qrcode=qr_code,
        data=json.dumps(dict_data, indent=4),
        bulletin_secret=user['relationship']['bulletin_secret'],
        to=to
    )



@app.route('/show-friend-request')
def show_friend_request():
    authed_user = get_logged_in_user()

    transaction = BU.get_transaction_by_rid(request.args.get('rid'), rid=True, raw=True)

    requested_transaction = BU.get_transaction_by_rid(transaction['requester_rid'], rid=True)
    dict_data = {
        'bulletin_secret': requested_transaction['relationship']['bulletin_secret'],
        'requested_rid': transaction['requested_rid'],
        'requester_rid': transaction['requester_rid']
    }
    data = json.dumps(dict_data)
    qr_code = make_qr(data)
    return render_template(
        'accept-friend-request.html',
        qrcode=qr_code,
        data=json.dumps(dict_data, indent=4),
        rid=requested_transaction['rid'],
        bulletin_secret=requested_transaction['relationship']['bulletin_secret']
    )
peer_to_rid = {}
rid_to_peer = {}
@app.route('/add-peer')
def add_peer():
    #authed_user = get_logged_in_user()
    peer_to_rid[request.args['peer_id']] = request.args['rid']
    rid_to_peer[request.args['rid']] = request.args['peer_id']
    return 'ok'

@app.route('/get-peer')
def get_peer():
    #authed_user = get_logged_in_user()
    #TODO: verify this user is has a friend request from the rid
    # graph = Graph()
    if 'rid' in request.args:
        return json.dumps({'peerId': rid_to_peer[request.args['rid']]})

    if 'peer_id' in request.args:
        return json.dumps({'rid': peer_to_rid[request.args['peer_id']]})

    return '{}'

@app.route('/show-users')
def show_users():
    users = BU.get_transactions()
    rids = set([x['rid'] for x in users])
    return render_template('show-users.html', users=rids)

@app.route('/get-rid')
def get_rid():
    my_bulletin_secret = TU.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(request.args.get('bulletin_secret'))], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
    return json.dumps({'rid': rid})

@app.route('/get-block')
def get_block():
    blocks = collection.find({'id': request.args.get('id')}, {'_id': 0}).limit(1).sort([('index',-1)])
    return json.dumps(blocks[0] if blocks.count() else {}, indent=4), 404


@app.route('/post-block', methods=['POST'])
def post_block():
    block = Block.from_dict(request.json)
    block.verify()
    my_latest_block = BU.get_latest_block()
    if my_latest_block[0].get('index') - block.index == 1:
        block.save()
        return '{"status": "ok"}'
    else:
        return '{"status": "error"}', 400

@app.route('/search')
def search():
    mongo_client = MongoClient('localhost')
    phrase = request.args.get('phrase')
    bulletin_secret = request.args.get('bulletin_secret')
    my_bulletin_secret = TU.get_bulletin_secret()

    rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')

    friend = mongo_client.yadacoinsite.usernames.find({'username': phrase.lower().strip()})
    if friend.count():
        friend = friend[0]
        to = friend['to']
    else:
        return '{}', 404
    out = json.dumps({
        'bulletin_secret': friend['relationship']['bulletin_secret'],
        'requested_rid': friend['rid'],
        'requester_rid': rid,
        'to': to
    }, indent=4)
    return out
        

@app.route('/react', methods=['POST'])
def react():
    my_bulletin_secret = TU.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(request.json.get('bulletin_secret'))], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
    mongo_client = MongoClient('localhost')
    mongo_client.yadacoinsite.reacts.insert({
        'rid': rid,
        'emoji': request.json.get('react'),
        'txn_id': request.json.get('txn_id')
    })
    return 'ok'

@app.route('/get-reacts', methods=['POST'])
def get_reacts():
    if request.json:
        data = request.json
        ids = data.get('txn_ids')
    else:
        data = request.form
        ids = json.loads(data.get('txn_ids'))

    mongo_client = MongoClient('localhost')
    res = mongo_client.yadacoinsite.reacts.find({
        'txn_id': {
            '$in': ids
        },
    }, {'_id': 0})
    out = {}
    for x in res:
        if x['txn_id'] not in out:
            out[x['txn_id']] = ''
        out[x['txn_id']] = out[x['txn_id']] + x['emoji']
    return json.dumps(out)

@app.route('/get-reacts-detail', methods=['POST'])
def get_reacts_detail():
    if request.json:
        data = request.json
        txn_id = data.get('txn_id')
    else:
        data = request.form
        txn_id = json.loads(data.get('txn_id'))

    mongo_client = MongoClient('localhost')
    res = mongo_client.yadacoinsite.reacts.find({
        'txn_id': txn_id,
    }, {'_id': 0})
    out = []
    for x in res:
        res1 = mongo_client.yadacoinsite.usernames.find({'rid': x['rid']})
        if res1.count():
            x['username'] = res1[0]['username']
        else:
            x['username'] = humanhash.humanize(x['rid'])
        out.append(x)
    return json.dumps(out)

@app.route('/comment', methods=['POST'])
def comment():
    my_bulletin_secret = TU.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(request.json.get('bulletin_secret'))], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
    mongo_client = MongoClient('localhost')
    mongo_client = MongoClient('localhost')
    mongo_client.yadacoinsite.comments.insert({
        'rid': rid,
        'body': request.json.get('comment'),
        'txn_id': request.json.get('txn_id')
    })
    txn = mongo_client.yadacoinsite.fcmtokens.find({'id': request.json.get('txn_id')})

    res = mongo_client.yadacoinsite.fcmtokens.find({"rid": txn['requester_rid']})
    for token in res:
        result = push_service.notify_single_device(
            registration_id=token['token'],
            message_title='Your friend request was approved!',
            message_body='Say "hi" to your friend!',
            extra_kwargs={'priority': 'high'}
        )
    return 'ok'

@app.route('/get-comments', methods=['POST'])
def get_comments():
    if request.json:
        data = request.json
        ids = data.get('txn_ids')
    else:
        data = request.form
        ids = json.loads(data.get('txn_ids'))
    mongo_client = MongoClient('localhost')
    res = mongo_client.yadacoinsite.comments.find({
        'txn_id': {
            '$in': ids
        },
    }, {'_id': 0})
    out = {}
    usernames = {}
    for x in res:
        if x['txn_id'] not in out:
            out[x['txn_id']] = []
        res1 = mongo_client.yadacoinsite.usernames.find({'rid': x['rid']})
        if res1.count():
            x['username'] = res1[0]['username']
        else:
            x['username'] = humanhash.humanize(x['rid'])
        out[x['txn_id']].append(x)
    return json.dumps(out)

@app.route('/get-usernames')
def get_username():
    mongo_client = MongoClient('localhost')
    res = mongo_client.yadacoinsite.usernames.find({'rid': {'$in': request.args.get('rids')}}, {'_id': 0})
    if res.count():
        out = {}
        for x in res:
            out[x['rid']] = x['username']
        return json.dumps(out)
    else:
        return '{}'

@app.route('/change-username', methods=['POST'])
def change_username():
    mongo_client = MongoClient('localhost')
    request.json['username'] = request.json['username'].lower()
    exists = mongo_client.yadacoinsite.usernames.find({
        'username': request.json.get('username')
    })
    if exists.count():
        return 'username taken', 400
    mongo_client.yadacoinsite.usernames.update(
        {
            'rid': request.json.get('rid')
        },
        request.json,
        upsert=True
    )
    return 'ok'

@app.route('/fcm-token', methods=['POST'])
def fcm_token():
    try:
        token = request.json.get('token')
        print token
        rid = request.json.get('rid')
        txn = BU.get_transaction_by_rid(rid, rid=True) 
        mongo_client.yadacoinsite.fcmtokens.update({'rid': rid}, {
            'rid': rid,
            'token': token
        }, upsert=True)
        return '', 200
    except Exception as e:
        return '', 400

@app.route('/deeplink')
def deeplink():
    import urllib
    return redirect('myapp://' + urllib.quote(request.args.get('txn')))

@app.route('/get-latest-block')
def get_latest_block():
    blocks = BU.get_latest_block()
    return json.dumps(blocks[0], indent=4)

@app.route('/get-chain')
def get_chain():
    # some type of generator
    return json.dumps()


@app.route('/get-peers')
def get_peers():
    with open('peers.json') as f:
        peers = f.read()
    return json.dumps({'peers': peers})


@app.route('/transaction', methods=['GET', 'POST'])
def transaction():
    mongo_client = MongoClient('localhost')
    if request.method == 'POST':
        from transaction import InvalidTransactionException, InvalidTransactionSignatureException, MissingInputTransactionException
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
                mongo_client.yadacoin.failed_transactions.insert({
                    'exception': 'InvalidTransactionException',
                    'txn': txn
                })
                print 'InvalidTransactionException'
                return 'InvalidTransactionException', 400
            except InvalidTransactionSignatureException:
                print 'InvalidTransactionSignatureException'
                mongo_client.yadacoin.failed_transactions.insert({
                    'exception': 'InvalidTransactionSignatureException',
                    'txn': txn
                })
                return 'InvalidTransactionSignatureException', 400
            except MissingInputTransactionException:
                pass
            except:
                print 'uknown error'
                return 'uknown error', 400
            transactions.append(transaction)

        for x in transactions:
            db.miner_transactions.insert(x.to_dict())
        job = Process(target=txn_broadcast_job, args=(transaction,))
        job.start()
        for txn in transactions:
            job = Process(
                target=do_push,
                args=(txn.to_dict(), request.args.get('bulletin_secret'))
            )
            job.start()
        return json.dumps(request.get_json())
    else:
        rid = request.args.get('rid')
        transactions = BU.get_transactions_by_rid(rid, rid=True, raw=True)
        return json.dumps([x for x in transactions])

def do_push(txn, bulletin_secret):
    my_bulletin_secret = TU.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')

    if txn.get('relationship') and txn.get('dh_public_key') and txn.get('requester_rid') == rid:
        #friend request
        #if rid is the requester_rid, then we send a friend request notification to the requested_rid
        res = mongo_client.yadacoinsite.fcmtokens.find({"rid": txn['requested_rid']})
        for token in res:
            result = push_service.notify_single_device(
                registration_id=token['token'],
                message_title='New friend request!',
                message_body='You have a new friend request to approve!',
                extra_kwargs={'priority': 'high'}
            )

    elif txn.get('relationship') and txn.get('dh_public_key') and txn.get('requested_rid') == rid:
        #friend accept
        #if rid is the requested_rid, then we send a friend accepted notification to the requester_rid
        res = mongo_client.yadacoinsite.fcmtokens.find({"rid": txn['requester_rid']})
        for token in res:
            result = push_service.notify_single_device(
                registration_id=token['token'],
                message_title='Your friend request was approved!',
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
            res = mongo_client.yadacoinsite.fcmtokens.find({"rid": friend_rid})
            used_tokens = []
            for token in res:
                if token['token'] in used_tokens:
                    continue
                used_tokens.append(token['token'])
                result = push_service.notify_single_device(
                    registration_id=token['token'],
                    message_title='Your friend has posted something!',
                    message_body='Go check out what your friend posted!',
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
            res = mongo_client.yadacoinsite.fcmtokens.find({"rid": friend_rid})
            used_tokens = []
            for token in res:
                if token['token'] in used_tokens:
                    continue
                used_tokens.append(token['token'])
                result = push_service.notify_single_device(
                    registration_id=token['token'],
                    message_title='New message!',
                    message_body='You have a new message from a friend!',
                    extra_kwargs={'priority': 'high'}
                )



def txn_broadcast_job(transaction):
    with open('peers.json') as f:
        peers = json.loads(f.read())
    for peer in peers:
        try:
            socketIO = SocketIO(peer['ip'], 8000, wait_for_connection=False)
            chat_namespace = socketIO.define(ChatNamespace, '/chat')
            chat_namespace.emit('newtransaction', transaction.to_dict())
            socketIO.wait(seconds=1)
            chat_namespace.disconnect()
        except Exception as e:
            raise e

@app.route('/bulletins')
def bulletin():
    bulletin_secret = request.args.get('bulletin_secret')
    bulletins = BU.get_bulletins(bulletin_secret)
    return json.dumps(bulletins)

def get_base_graph():
    mongo_client = MongoClient('localhost')
    bulletin_secret = request.args.get('bulletin_secret')
    graph = Graph(bulletin_secret, public_key, my_address, push_service=push_service)
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
    #graph.get_friends()
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

@app.route('/get-graph')
def get_graph():
    graph = Graph(TU.get_bulletin_secret(), for_me=True)
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
        exists = mongo_client.yadacoinsite.faucet.find({
            'address': address
        })
        if not exists.count():
            mongo_client.yadacoinsite.faucet.insert({
                'address': address,
                'active': True
            })
        return json.dumps({'status': 'ok'})
    else:
        return json.dumps({'status': 'error'}), 400


@app.route('/get-url')
def get_url():
    res = requests.get(request.args.get('url'))
    return res.content


@app.route('/firebase-messaging-sw.js')
def firebase_service_worker():
    return app.send_static_file('app/www/ServiceWorker.js')

app.debug = True
app.secret_key = '23ljk2l3k4j'
mongo_client = MongoClient('localhost')
db = mongo_client.yadacoin
collection = db.blocks
consensus = db.consensus
miner_transactions = db.miner_transactions
BU.collection = collection
TU.collection = collection
BU.consensus = consensus
TU.consensus = consensus
BU.miner_transactions = miner_transactions
TU.miner_transactions = miner_transactions

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--conf',
                help='set your config file')
args = parser.parse_args()
conf = args.conf or 'config.json'

with open(conf) as f:
    raw = f.read()
    config = json.loads(raw)
print 'RUNNING SERVER WITH CONFIG:'
print raw
public_key = config.get('public_key')
my_address = str(P2PKHBitcoinAddress.from_pubkey(public_key.decode('hex')))

private_key = config.get('private_key')
TU.private_key = private_key
BU.private_key = private_key
api_key = config.get('fcm_key')
push_service = FCMNotification(api_key=api_key)
