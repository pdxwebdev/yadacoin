import json
import hashlib
import os
import argparse
import qrcode
import base64
import humanhash

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


mongo_client = MongoClient()
db = mongo_client.yadacoin
collection = db.blocks
consensus = db.consensus
txncache = db.txncache
BU.collection = collection
TU.collection = collection
BU.consensus = consensus
TU.consensus = consensus

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--conf',
                help='set your config file')
args = parser.parse_args()

with open(args.conf) as f:
    config = json.loads(f.read())

public_key = config.get('public_key')
my_address = str(P2PKHBitcoinAddress.from_pubkey(public_key.decode('hex')))
private_key = config.get('private_key')
TU.private_key = private_key
BU.private_key = private_key
api_key = config.get('fcm_key')
push_service = FCMNotification(api_key=api_key)
# print sk.get_verifying_key().to_string().encode('hex')
# vk2 = VerifyingKey.from_string(pk.decode('hex'))
# print vk2.verify(signature, "message")
class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

app = Flask(__name__)

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
    try:
        transaction = collection.find({'challenge_code': session['challenge_code']})[0]
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
    except:
        return {'authenticated': False}

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

@app.route('/demo')
def demo():
    bulletin_secret = TU.get_bulletin_secret()
    shared_secret = str(uuid4())
    existing = [x for x in txncache.find()]
    new = BU.get_transactions(skip=[txn['id'] for txn in existing])
    for txn in new:
        txncache.insert(txn)
    existing.extend(new)
    session.setdefault('challenge_code', str(uuid4()))
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    data = {
        'challenge_code': session['challenge_code'],
        'bulletin_secret': TU.get_bulletin_secret(),
        'shared_secret': shared_secret,
        'callbackurl': config.get('callbackurl'),
        'to': my_address
    }
    qr.add_data(json.dumps(data))
    qr.make(fit=True)

    login_out = BytesIO()
    qr_img = qr.make_image()
    qr_img = qr_img.convert("RGBA")
    qr_img.save(login_out, 'PNG')
    login_out.seek(0)
    authed_user = get_logged_in_user()

    if authed_user['authenticated']:
        rid = authed_user['rid']
    else:
        rid = ''

    return render_template(
        'demo.html',
        user=authed_user,
        bulletin_secret=bulletin_secret,
        shared_secret=shared_secret,
        existing=existing,
        data=json.dumps(data, indent=4),
        challenge_code=session['challenge_code'],
        users=set([x['rid'] for x in existing if x['rid'] != rid]),
        login_qrcode=u"data:image/png;base64," + base64.b64encode(login_out.getvalue()).decode('ascii'),
    )

@app.route('/create-relationship', methods=['GET', 'POST'])
def create_relationship():  # demo site
    if request.method == 'GET':
        bulletin_secret = request.args.get('bulletin_secret', '')
        shared_secret = request.args.get('shared_secret', '')
        requester_rid = request.args.get('requester_rid', '')
        requested_rid = request.args.get('requested_rid', '')
        to = request.args.get('to', '')
    else:
        bulletin_secret = request.json.get('bulletin_secret', '')
        shared_secret = request.json.get('shared_secret', '')
        requester_rid = request.json.get('requester_rid', '')
        requested_rid = request.json.get('requested_rid', '')
        to = request.json.get('to', '')

    input_txns = BU.get_wallet_unspent_transactions(my_address)

    inputs = [Input.from_dict(input_txn) for input_txn in input_txns]

    needed_inputs = []
    input_sum = 0
    done = False
    for x in inputs:
        txn = BU.get_transaction_by_id(x.id, instance=True)
        for txn_output in txn.outputs:
            if txn_output.to == my_address:
                input_sum += txn_output.value
                needed_inputs.append(x)
                if input_sum >= 1.1:
                    done = True
                    break
        if done == True:
            break


    return_change_output = Output(
        to=my_address,
        value=input_sum-1.1
    )

    transaction = TransactionFactory(
        bulletin_secret=bulletin_secret,
        shared_secret=shared_secret,
        fee=0.1,
        requester_rid=requester_rid,
        requested_rid=requested_rid,
        public_key=public_key,
        private_key=private_key,
        inputs=needed_inputs,
        outputs=[
            Output(to=to, value=1),
            return_change_output
        ]
    )

    TU.save(transaction.transaction)

    my_bulletin_secret = TU.get_bulletin_secret()

    with open('peers.json') as f:
        peers = json.loads(f.read())
    for peer in peers:
        try:
            socketIO = SocketIO(peer['ip'], 8000, wait_for_connection=False)
            chat_namespace = socketIO.define(ChatNamespace, '/chat')
            chat_namespace.emit('newtransaction', transaction.transaction.to_dict())
            socketIO.wait(seconds=1)
        except Exception as e:
            raise e
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
    rids = sorted([str(my_bulletin_secret), str(requeset.args.get('bulletin_secret'))], key=str.lower)
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
    phrase = request.args.get('phrase')
    bulletin_secret = request.args.get('bulletin_secret')
    graph = Graph(TU.get_bulletin_secret(), for_me=True)
    for friend in graph.friends:
        if humanhash.humanize(friend['rid']) == phrase:
            my_bulletin_secret = TU.get_bulletin_secret()
            rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
            rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
            for output in friend['outputs']:
                if output['to'] != my_address:
                    to = output['to']
            return json.dumps({
                'bulletin_secret': friend['relationship']['bulletin_secret'],
                'requested_rid': friend['rid'],
                'requester_rid': rid,
                'to': to
            }, indent=4)
    return '{}', 404

@app.route('/fcm-token', methods=['POST'])
def fcm_token():
    try:
        token = request.json.get('token')
        rid = request.json.get('rid')
        shared_secret = request.json.get('shared_secret')
        txn = BU.get_transaction_by_rid(rid, rid=True) 
        if txn['relationship']['shared_secret'] == shared_secret:
            mongo_client.yadacoinsite.fcmtokens.update({'rid': rid}, {
                'rid': rid,
                'token': token
            }, upsert=True)
            return '', 200
        return '', 400
    except Exception as e:
        return '', 4000

@app.route('/request-notification', methods=['POST'])
def request_notification():
    shared_secret = request.json.get('shared_secret')
    requested_rid = request.json.get('requested_rid')
    rid = request.json.get('rid')
    data = json.loads(request.json.get('data'))
    txn = BU.get_transaction_by_rid(rid, rid=True) 
    if txn['relationship']['shared_secret'] == shared_secret:
        res = mongo_client.yadacoinsite.fcmtokens.find({
            'rid': requested_rid
        });
        for token in res:
            if data.get('accept'):
                result = push_service.notify_single_device(
                    registration_id=token['token'],
                    message_title='Friend Request Accepted!',
                    message_body='Your friend request was approved!',
                    data_message=data
                )
            else:
                result = push_service.notify_single_device(
                    registration_id=token['token'],
                    message_title='New Friend Request!',
                    message_body='You have a new friend request to approve!',
                    data_message=data
                )
        return '', 200
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
                return '', 400
            except InvalidTransactionSignatureException:
                return '', 400
            except MissingInputTransactionException:
                pass
            transactions.append(transaction)

        for x in transactions:
            db.miner_transactions.insert(x.to_dict())
        job = Process(target=txn_broadcast_job, args=(transaction,))
        job.start()
        return json.dumps(request.get_json())
    else:
        rid = request.args.get('rid')
        transaction = BU.get_transactions_by_rid(rid, rid=True, raw=True)
        return json.dumps(transaction)

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


@app.route('/get-graph-mobile')
def get_graph_mobile():
    bulletin_secret = request.args.get('bulletin_secret')
    graph = Graph(bulletin_secret)
    graph_dict = graph.to_dict()
    graph_dict['registered'] = graph.rid in [x.get('rid') for x in graph.friends]
    return json.dumps(graph_dict, indent=4)


@app.route('/get-graph')
def get_graph():
    graph = Graph(TU.get_bulletin_secret(), for_me=True)

    return graph.to_json()

@app.route('/wallet')
def get_wallet():
    address = request.args.get('address')
    wallet = {
        'balance': BU.get_wallet_balance(address),
        'unspent_transactions': BU.get_wallet_unspent_transactions(address)
    }
    return json.dumps(wallet, indent=4)

app.debug = True
app.secret_key = '23ljk2l3k4j'
app.run(host=config.get('host'), port=config.get('port'), threaded=True)
