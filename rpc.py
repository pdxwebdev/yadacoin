import json
import hashlib
import os
import argparse
import qrcode
import base64
import humanhash
import requests
import pyDH

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
from gcm import GCM


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

app = Flask(__name__)
CORS(app)

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
    friends = [x for x in mongo_client.yadacoinsite.friends.find()]

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
        existing=friends,
        data=json.dumps(data, indent=4),
        challenge_code=session['challenge_code'],
        users=set([x['rid'] for x in friends if x['rid'] != rid]),
        login_qrcode=u"data:image/png;base64," + base64.b64encode(login_out.getvalue()).decode('ascii'),
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

    miner_transactions = db.miner_transactions.find()
    mtxn_ids = []
    for mtxn in miner_transactions:
        for mtxninput in mtxn['inputs']:
            mtxn_ids.append(mtxninput['id'])

    input_txns = BU.get_wallet_unspent_transactions(my_address)

    inputs = [Input.from_dict(input_txn) for input_txn in input_txns if input_txn['id'] not in mtxn_ids]

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

    dh = pyDH.DiffieHellman(group=17)
    dh_public_key = "%x" % dh.gen_public_key()
    dh_private_key = "%x" % dh.get_private_key()

    transaction = TransactionFactory(
        bulletin_secret=bulletin_secret,
        shared_secret=shared_secret,
        fee=0.1,
        requester_rid=requester_rid,
        requested_rid=requested_rid,
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
    try:
        friend = mongo_client.yadacoinsite.friends.find({'humanized': phrase})
        if friend.count():
            friend = friend[0]
            for output in friend['outputs']:
                if output['to'] != my_address:
                    to = output['to']
        else:
            friend = mongo_client.yadacoinsite.usernames.find({'username': phrase.lower()})
            if friend.count():
                friend = friend[0]
                to = friend['to']
            else:
                raise
        out = json.dumps({
            'bulletin_secret': friend['relationship']['bulletin_secret'],
            'requested_rid': friend['rid'],
            'requester_rid': rid,
            'to': to
        }, indent=4)
        return out
    except:
        raise
        return '{}', 404

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
    for x in res:
        if x['txn_id'] not in out:
            out[x['txn_id']] = []
        out[x['txn_id']].append(x['body'])
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
    if data.get('accept'):
        res = mongo_client.yadacoinsite.fcmtokens.find({
            'rid': data['requested_rid']
        })
        for token in res:
            gcm_service.plaintext_request(registration_id=token['token'], data={'the message': 'you have friends!', 'param2': 'param'})
            result = push_service.notify_single_device(
                registration_id=token['token'],
                message_title='Friend Request Accepted!',
                message_body='Your friend request was approved!',
                data_message=data,
                extra_kwargs={'priority': 'high'}
            )
    else:
        res = mongo_client.yadacoinsite.fcmtokens.find({
            'rid': data['requested_rid']
        })
        for token in res:
            result = push_service.notify_single_device(
                registration_id=token['token'],
                message_title='New Friend Request!',
                message_body='You have a new friend request to approve!',
                data_message=data,
                extra_kwargs={'priority': 'high'}
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
    graph = Graph(bulletin_secret, push_service=push_service)
    graph_dict = graph.to_dict()
    graph_dict['registered'] = graph.rid in [x.get('rid') for x in graph.friends]
    graph_dict['pending_registration'] = False
    if not graph_dict['registered']:
        # not regisered, let's check for a pending transaction
        mongo_client = MongoClient('localhost')
        res = mongo_client.yadacoin.miner_transactions.find({'rid': graph.rid})
        if res.count():
            graph_dict['pending_registration'] = True
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

app.debug = True
app.secret_key = '23ljk2l3k4j'
if __name__ == '__main__':
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

    with open(args.conf) as f:
        config = json.loads(f.read())

    public_key = config.get('public_key')
    my_address = str(P2PKHBitcoinAddress.from_pubkey(public_key.decode('hex')))

    private_key = config.get('private_key')
    TU.private_key = private_key
    BU.private_key = private_key
    api_key = config.get('fcm_key')
    push_service = FCMNotification(api_key=api_key)
    gcm_service = GCM(api_key)


    for transaction in BU.get_transactions():
        exists = mongo_client.yadacoinsite.friends.find({'id': transaction['id']})
        if not exists.count():
            transaction['humanized'] = humanhash.humanize(transaction['rid'])
            mongo_client.yadacoinsite.friends.insert(transaction)
        bulletin_secret = transaction['relationship']['bulletin_secret']
        exists = mongo_client.yadacoinsite.posts.find({
            'id': transaction.get('id')
        })
        if exists.count():
            if not exists[0]['skip']:
                transaction['relationship'] = {'postText': exists[0]['postText']}
                self.friend_posts.append(transaction)
            continue
        try:
            data = transaction['relationship']
            if 'postText' in data:
                mongo_client.yadacoinsite.posts.remove({'id': transaction.get('id')})
                transaction['relationship'] = data
                self.friend_posts.append(transaction)
                mongo_client.yadacoinsite.posts.insert({
                    'postText': data['postText'],
                    'rid': transaction.get('rid'),
                    'id': transaction.get('id'),
                    'requester_rid': transaction.get('requester_rid'),
                    'requested_rid': transaction.get('requested_rid'),
                    'skip': False
                })
        except:
            raise
            mongo_client.yadacoinsite.posts.insert({
                'postText': data['postText'],
                'rid': transaction.get('rid'),
                'id': transaction.get('id'),
                'requester_rid': transaction.get('requester_rid'),
                'requested_rid': transaction.get('requested_rid'),
                'skip': True
            })

    app.run(host=config.get('host'), port=config.get('port'), threaded=True)
