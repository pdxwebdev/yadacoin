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
import re
import socket
import uuid
import urllib
from logging.handlers import SMTPHandler
from io import BytesIO
from uuid import uuid4
from ecdsa import NIST384p, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from flask import Flask, request, render_template, session, redirect
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from yadacoin import BU, TU, Transaction, TransactionFactory, Output, Input, \
                     Config, Peers, Graph, Block, Mongo, InvalidTransactionException, \
                     InvalidTransactionSignatureException, MissingInputTransactionException
from pymongo import MongoClient
from socketIO_client import SocketIO, BaseNamespace
from pyfcm import FCMNotification
from multiprocessing import Process, Value, Array, Pool
from flask_cors import CORS
from eccsnacks.curve25519 import scalarmult, scalarmult_base
from bson.objectid import ObjectId
import endpoints


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

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
    res = Mongo.db.blocks.aggregate([
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
                        if txn_output['to'] != Config.address:
                            to = txn_output['to']
                    user = {
                        'balance': BU.get_wallet_balance(to),
                        'authenticated': True,
                        'rid': transaction['rid'],
                        'bulletin_secret': test['relationship']['bulletin_secret']
                    }
    return user if user else {'authenticated': False}

app = Flask(__name__)
app.debug = True
app.secret_key = '23ljk2l9a08sd7f09as87df09as87df3k4j'
CORS(app)


@app.route('/pool', methods=['GET', 'POST'])
def pool():
    return render_template('pool.html')

@app.route('/demo', methods=['GET', 'POST'])
def demo():
    session.setdefault('id', str(uuid.uuid4()))

    if request.method == 'POST':
        bulletin_secret = request.form.get('bulletin_secret', '')
        if not bulletin_secret:
            return redirect('/demo?error')
        # generate a transaction which contains a signin message containing the current sessions identifier
        txn = TransactionFactory(
            bulletin_secret=bulletin_secret,
            public_key=Config.public_key,
            private_key=Config.private_key,
            signin=session.get('id'),
            fee=0.01
        ).transaction

        # send the transaction to our own serve instance, which saves it to miner_transactions
        # the miner looks in miner_transactions to include in a block when it finds a new block
        for peer in Peers.peers:
            print peer.host, peer.port
            requests.post(
                "http://{host}:{port}/newtransaction".format(
                    host=peer.host,
                    port=peer.port
                ),
                txn.to_json(),
                headers={"Content-Type": "application/json"}
            )
        return redirect('/demo?bulletin_secret=%s' % urllib.quote_plus(bulletin_secret))
    elif request.method == 'GET':
        bulletin_secret = request.args.get('bulletin_secret', '')
        rid = TU.generate_rid(bulletin_secret)
        txns = BU.get_transactions_by_rid(rid, rid=True)

        txns2 = BU.get_transactions_by_rid(rid, rid=True, raw=True)
        half1 = False
        half2 = False
        for txn in txns:
            if txn['public_key'] == Config.public_key:
                half1 = True
        for txn in txns2:
            if txn['public_key'] != Config.public_key:
                half2 = True
        registered = half1 and half2
        sent, received = BU.verify_message(rid, session['id'])
        session['loggedin'] = received
        return render_template(
            'authdemo.html',
            session_id=str(session.get('id')),
            registered=str(registered),
            sent=str(sent),
            received=str(received),
            loggedin=str(session['loggedin']),
            bulletin_secret=str(bulletin_secret),
            rid=str(rid)
        )
    else:
        return redirect('/demo')

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
    job = Process(target=endpoints.TxnBroadcaster.txn_broadcast_job, args=(transaction.transaction,))
    job.start()


    my_bulletin_secret = Config.get_bulletin_secret()
    bulletin_secrets = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
    rid = hashlib.sha256(str(bulletin_secrets[0]) + str(bulletin_secrets[1])).digest().encode('hex')
    Mongo.site_db.friends.insert({'rid': rid, 'relationship': {'bulletin_secret': bulletin_secret}})
    return json.dumps({"success": True})


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

@app.route('/config.xml')
def configxml():
    return app.send_static_file('config.xml')

@app.route('/screen')
def screen():
    return app.send_static_file('app/www/assets/img/logo.png')

@app.route('/explorer')
def explorer():
    return app.send_static_file('explorer/index.html')

@app.route('/explorer-search')
def explorer_search():
    if not request.args.get('term'):
        return '{}'

    try:
        term = int(request.args.get('term'))
        res = Mongo.db.blocks.find({'index': term}, {'_id': 0})
        if res.count():
            return json.dumps({
                'resultType': 'block_height',
                'result': [changetime(x) for x in res]
            }, indent=4)
    except:
        pass
    try:
        term = request.args.get('term')
        res = Mongo.db.blocks.find({'public_key': term}, {'_id': 0})
        if res.count():
            return json.dumps({
                'resultType': 'block_height',
                'result': [changetime(x) for x in res]
            }, indent=4)
    except:
        pass
    try:
        term = request.args.get('term')
        res = Mongo.db.blocks.find({'transactions.public_key': term}, {'_id': 0})
        if res.count():
            return json.dumps({
                'resultType': 'block_height',
                'result': [changetime(x) for x in res]
            }, indent=4)
    except:
        pass
    try:
        term = request.args.get('term')
        re.search(r'[A-Fa-f0-9]{64}', term).group(0)
        res = Mongo.db.blocks.find({'hash': term}, {'_id': 0})
        if res.count():
            return json.dumps({
                'resultType': 'block_hash',
                'result': [changetime(x) for x in res]
            }, indent=4)
    except:
        pass

    try:
        term = request.args.get('term').replace(' ', '+')
        base64.b64decode(term)
        res = Mongo.db.blocks.find({'id': term}, {'_id': 0})
        if res.count():
            return json.dumps({
                'resultType': 'block_id',
                'result': [changetime(x) for x in res]
            }, indent=4)
    except:
        pass

    try:
        term = request.args.get('term')
        re.search(r'[A-Fa-f0-9]{64}', term).group(0)
        res = Mongo.db.blocks.find({'transactions.hash': term}, {'_id': 0})
        if res.count():
            return json.dumps({
                'resultType': 'txn_hash',
                'result': [changetime(x) for x in res]
            }, indent=4)
    except:
        pass

    try:
        term = request.args.get('term')
        re.search(r'[A-Fa-f0-9]{64}', term).group(0)
        res = Mongo.db.blocks.find({'transactions.rid': term}, {'_id': 0})
        if res.count():
            return json.dumps({
                'resultType': 'txn_rid',
                'result': [changetime(x) for x in res]
            }, indent=4)
    except:
        pass

    try:
        term = request.args.get('term').replace(' ', '+')
        base64.b64decode(term)
        res = Mongo.db.blocks.find({'transactions.id': term}, {'_id': 0})
        if res.count():
            return json.dumps({
                'resultType': 'txn_id',
                'result': [changetime(x) for x in res]
            }, indent=4)
    except:
        pass

    try:
        term = request.args.get('term')
        re.search(r'[A-Fa-f0-9]+', term).group(0)
        res = Mongo.db.blocks.find({'transactions.outputs.to': term}, {'_id': 0}).sort('index', -1)
        if res.count():
            balance = BU.get_wallet_balance(term)
            return json.dumps({
                'balance': balance,
                'resultType': 'txn_outputs_to',
                'result': [changetime(x) for x in res]
            }, indent=4)
    except:
        pass

    return '{}'

def changetime(block):
    from datetime import datetime
    block['time'] = datetime.utcfromtimestamp(int(block['time'])).strftime('%Y-%m-%dT%H:%M:%S UTC')
    return block

@app.route('/api-stats')
def api_stats():
    max_target = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    blocks = BU.get_blocks()
    total_nonce = 0
    periods = []
    last_time = None
    for block in blocks:
        difficulty = max_target / int(block.get('target'), 16)
        if block.get('index') == 0:
            start_timestamp = block.get('time')
        if last_time:
            if int(block.get('time')) > last_time:
                periods.append({
                    'hashrate': (difficulty * 2**32) / (int(block.get('time')) - last_time),
                    'index': block.get('index'),
                    'elapsed_time': (int(block.get('time')) - last_time)
                })
        last_time = int(block.get('time'))
        total_nonce += block.get('nonce')
    sorted(periods, key=lambda x: x['index'])
    total_time_elapsed = int(block.get('time')) - int(start_timestamp)
    network_hash_rate =  total_nonce / int(total_time_elapsed)
    return json.dumps({
        'stats': {
            'network_hash_rate': network_hash_rate,
            'total_time_elapsed': total_time_elapsed,
            'total_nonce': total_nonce,
            'periods': periods
        }
    }, indent=4)

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

@app.route('/guide')
def guide():
    return render_template(
        'guide.html',
        )

@app.route('/team')
def team():
    return render_template(
        'team.html',
        )

@app.route('/login-status')
def login_status():
    user = get_logged_in_user()
    return json.dumps(user)

@app.route('/show-user')
def show_user():
    authed_user = get_logged_in_user()
    user = BU.get_transaction_by_rid(request.args['rid'], rid=True)
    for output in user['outputs']:
        if output['to'] != Config.address:
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
    my_bulletin_secret = Config.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(request.args.get('bulletin_secret'))], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
    return json.dumps({'rid': rid})

@app.route('/get-block')
def get_block():
    blocks = Mongo.db.blocks.find({'id': request.args.get('id')}, {'_id': 0}).limit(1).sort([('index',-1)])
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
    my_bulletin_secret = Config.get_bulletin_secret()

    rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')

    friend = Mongo.site_db.usernames.find({'username': phrase.lower().strip()})
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
    my_bulletin_secret = Config.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(request.json.get('bulletin_secret'))], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')

    res1 = Mongo.site_db.usernames.find({'rid': rid})
    if res1.count():
        username = res1[0]['username']
    else:
        username = humanhash.humanize(rid)

    Mongo.site_db.reacts.insert({
        'rid': rid,
        'emoji': request.json.get('react'),
        'txn_id': request.json.get('txn_id')
    })

    txn = Mongo.db.posts_cache.find({'id': request.json.get('txn_id')})[0]

    rids = sorted([str(my_bulletin_secret), str(txn.get('bulletin_secret'))], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')

    res = Mongo.site_db.fcmtokens.find({"rid": rid})
    for token in res:
        result = push_service.notify_single_device(
            registration_id=token['token'],
            message_title='%s reacted to your post!' % username,
            message_body='Go see how they reacted!',
            extra_kwargs={'priority': 'high'}
        )
    return 'ok'

@app.route('/get-reacts', methods=['POST'])
def get_reacts():
    if request.json:
        data = request.json
        ids = data.get('txn_ids')
    else:
        data = request.form
        ids = json.loads(data.get('txn_ids'))

    res = Mongo.site_db.reacts.find({
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

    res = Mongo.site_db.reacts.find({
        'txn_id': txn_id,
    }, {'_id': 0})
    out = []
    for x in res:
        res1 = Mongo.site_db.usernames.find({'rid': x['rid']})
        if res1.count():
            x['username'] = res1[0]['username']
        else:
            x['username'] = humanhash.humanize(x['rid'])
        out.append(x)
    return json.dumps(out)

@app.route('/comment-react', methods=['POST'])
def comment_react():
    my_bulletin_secret = Config.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(request.json.get('bulletin_secret'))], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')

    res1 = Mongo.site_db.usernames.find({'rid': rid})
    if res1.count():
        username = res1[0]['username']
    else:
        username = humanhash.humanize(rid)

    Mongo.site_db.comment_reacts.insert({
        'rid': rid,
        'emoji': request.json.get('react'),
        'comment_id': request.json.get('_id')
    })

    comment = Mongo.site_db.comments.find({'_id': ObjectId(str(request.json.get('_id')))})[0]

    res = Mongo.site_db.fcmtokens.find({"rid": comment['rid']})
    for token in res:
        result = push_service.notify_single_device(
            registration_id=token['token'],
            message_title='%s reacted to your comment!' % username,
            message_body='Go see how they reacted!',
            extra_kwargs={'priority': 'high'}
        )
    return 'ok'

@app.route('/get-comment-reacts', methods=['POST'])
def get_comment_reacts():
    if request.json:
        data = request.json
        ids = data.get('ids')
    else:
        data = request.form
        ids = json.loads(data.get('ids'))
    ids = [str(x) for x in ids]
    res = Mongo.site_db.comment_reacts.find({
        'comment_id': {
            '$in': ids
        },
    })
    out = {}
    for x in res:
        if str(x['comment_id']) not in out:
            out[str(x['comment_id'])] = ''
        out[str(x['comment_id'])] = out[str(x['comment_id'])] + x['emoji']
    return json.dumps(out)

@app.route('/get-comment-reacts-detail', methods=['POST'])
def get_comment_reacts_detail():
    if request.json:
        data = request.json
        comment_id = data.get('_id')
    else:
        data = request.form
        comment_id = json.loads(data.get('_id'))

    res = Mongo.site_db.comment_reacts.find({
        'comment_id': comment_id,
    }, {'_id': 0})
    out = []
    for x in res:
        res1 = Mongo.site_db.usernames.find({'rid': x['rid']})
        if res1.count():
            x['username'] = res1[0]['username']
        else:
            x['username'] = humanhash.humanize(x['rid'])
        out.append(x)
    return json.dumps(out)

@app.route('/comment', methods=['POST'])
def comment():
    my_bulletin_secret = Config.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(request.json.get('bulletin_secret'))], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')

    res1 = Mongo.site_db.usernames.find({'rid': rid})
    if res1.count():
        username = res1[0]['username']
    else:
        username = humanhash.humanize(rid)

    Mongo.site_db.comments.insert({
        'rid': rid,
        'body': request.json.get('comment'),
        'txn_id': request.json.get('txn_id')
    })
    txn = Mongo.db.posts_cache.find({'id': request.json.get('txn_id')})[0]

    rids = sorted([str(my_bulletin_secret), str(txn.get('bulletin_secret'))], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
    res = Mongo.site_db.fcmtokens.find({"rid": rid})
    for token in res:
        result = push_service.notify_single_device(
            registration_id=token['token'],
            message_title='%s commented on your post!' % username,
            message_body='Go see what they said!',
            extra_kwargs={'priority': 'high'}
        )

    comments = Mongo.site_db.comments.find({
        'rid': {'$ne': rid},
        'txn_id': request.json.get('txn_id')
    })
    for comment in comments:
        res = Mongo.site_db.fcmtokens.find({"rid": comment['rid']})
        for token in res:
            result = push_service.notify_single_device(
                registration_id=token['token'],
                message_title='%s commented on a post you commented on!' % username,
                message_body='Go see what they said!',
                extra_kwargs={'priority': 'high'}
            )
    return 'ok'

@app.route('/get-comments', methods=['POST'])
def get_comments():
    if request.json:
        data = request.json
        ids = data.get('txn_ids')
        bulletin_secret = data.get('bulletin_secret')
    else:
        data = request.form
        ids = json.loads(data.get('txn_ids'))
        bulletin_secret = data.get('bulletin_secret')

    res = Mongo.site_db.comments.find({
        'txn_id': {
            '$in': ids
        },
    })
    blocked = [x['username'] for x in Mongo.site_db.blocked_users.find({'bulletin_secret': bulletin_secret})]
    out = {}
    usernames = {}
    for x in res:
        if x['txn_id'] not in out:
            out[x['txn_id']] = []
        res1 = Mongo.site_db.usernames.find({'rid': x['rid']})
        if res1.count():
            x['username'] = res1[0]['username']
        else:
            x['username'] = humanhash.humanize(x['rid'])
        x['_id'] = str(x['_id'])
        if x['username'] not in blocked:
            out[x['txn_id']].append(x)
    return json.dumps(out)

@app.route('/deeplink')
def deeplink():
    import urllib
    return redirect('myapp://' + urllib.quote(request.args.get('txn')))

@app.route('/get-latest-block')
def get_latest_block():
    block = BU.get_latest_block()
    return json.dumps(block, indent=4)

@app.route('/get-chain')
def get_chain():
    # some type of generator
    return json.dumps()

@app.route('/bulletins')
def bulletin():
    bulletin_secret = request.args.get('bulletin_secret')
    bulletins = BU.get_bulletins(bulletin_secret)
    return json.dumps(bulletins)

@app.route('/get-url')
def get_url():
    res = requests.get(request.args.get('url'))
    return res.content

@app.route('/block-user', methods=['POST'])
def block_user():
    Mongo.site_db.blocked_users.update({'bulletin_secret': request.json.get('bulletin_secret'), 'username': request.json.get('user')}, {'bulletin_secret': request.json.get('bulletin_secret'), 'username': request.json.get('user')}, upsert=True)
    return 'ok'

@app.route('/flag', methods=['POST'])
def flag():
    Mongo.site_db.flagged_content.update(request.json, request.json, upsert=True)
    return 'ok'

@app.route('/peers', methods=['GET', 'POST'])
def peers():
    if request.method == 'POST':
        try:
            socket.inet_aton(request.json['host'])
            host = request.json['host']
            port = int(request.json['port'])
            failed = request.json.get('failed')
            if failed:
                res = Mongo.db.peers.find({'host': host, 'port': port})
                if res.count():
                    Mongo.db.peers.update({'host': host, 'port': port}, {'$inc': {'failed': 1}})
            else:
                Mongo.db.peers.update({'host': host, 'port': port}, {'host': host, 'port': port, 'active': True, 'failed': 0}, upsert=True)
            Peers.init_local()
            return 'ok'
        except:
            return 'failed to add peer, invalid host', 400
    else:
        return json.dumps(Peers.to_dict(), indent=4)

@app.route('/stats')
def stats():
    return app.send_static_file('stats/index.html')

def get_base_graph(self):
    bulletin_secret = request.args.get('bulletin_secret').replace(' ', '+')
    graph = Graph(bulletin_secret)
    return graph

endpoints.BaseGraphView.get_base_graph = get_base_graph

app.add_url_rule('/register', view_func=endpoints.RegisterView.as_view('register'))
app.add_url_rule('/transaction', view_func=endpoints.TransactionView.as_view('transaction'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-info', view_func=endpoints.GraphView.as_view('graph'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-sent-friend-requests', view_func=endpoints.GraphSentFriendRequestsView.as_view('graphsentfriendrequests'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-friend-requests', view_func=endpoints.GraphFriendRequestsView.as_view('graphfriendrequests'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-friends', view_func=endpoints.GraphFriendsView.as_view('graphfriends'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-posts', view_func=endpoints.GraphPostsView.as_view('graphposts'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-messages', view_func=endpoints.GraphMessagesView.as_view('graphmessages'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-new-messages', view_func=endpoints.GraphNewMessagesView.as_view('graphnewmessages'), methods=['GET', 'POST'])
app.add_url_rule('/wallet', view_func=endpoints.WalletView.as_view('wallet'))
app.add_url_rule('/faucet', view_func=endpoints.FaucetView.as_view('faucet'))

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--conf',
                help='set your config file')
args = parser.parse_args()
conf = args.conf or 'config/config.json'
with open(conf) as f:
    Config.from_dict(json.loads(f.read()))

Peers.init_local()
Mongo.init()
#push_service = FCMNotification(api_key=Config.fcm_key)

