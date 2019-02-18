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
from flask import Flask, request, render_template, session, redirect, current_app
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from yadacoin import (
    BU, TU, Transaction, TransactionFactory, Output, Input, 
    Config, Peers, Graph, Block, Mongo, InvalidTransactionException, 
    InvalidTransactionSignatureException, MissingInputTransactionException, MiningPool, endpoints
)
from pymongo import MongoClient
from socketIO_client import SocketIO, BaseNamespace
from pyfcm import FCMNotification
from multiprocessing import Process, Value, Array, Pool
from flask_cors import CORS
from eccsnacks.curve25519 import scalarmult, scalarmult_base
from bson.objectid import ObjectId


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

app = Flask(__name__)
app.debug = True
app.secret_key = '23ljk2l9a08sd7f09as87df09as87df3k4j'
CORS(app)

@app.route('/pool', methods=['GET', 'POST'])
def pool():
    return render_template('pool.html')

@app.route('/firebase-messaging-sw.js')
def firebase_service_worker():
    return app.send_static_file('app/www/ServiceWorker.js')

@app.route('/fcm-token', methods=['POST'])
def fcm_token():
    try:
        config = current_app.config['yada_config']
        mongo = current_app.config['yada_mongo']
        token = request.json.get('token')
        print token
        rid = request.json.get('rid')
        txn = BU.get_transaction_by_rid(rid, rid=True) 
        mongo.site_db.fcmtokens.update({'rid': rid}, {
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

def changetime(block):
    from datetime import datetime
    block['time'] = datetime.utcfromtimestamp(int(block['time'])).strftime('%Y-%m-%dT%H:%M:%S UTC')
    return block

@app.route('/hashrate')
def hashrate():
    return render_template('hashrate.html')

@app.route('/api-stats')
def api_stats():
    max_target = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    config = current_app.config['yada_config']
    blocks = BU.get_blocks(config, mongo)
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
                    'hashrate': (((int(block.get('index')) / 144) * difficulty) * 2**32) / 600 / 100,
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

@app.route('/get-rid')
def get_rid():
    my_bulletin_secret = config.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(request.args.get('bulletin_secret'))], key=str.lower)
    rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
    return json.dumps({'rid': rid})

@app.route('/get-block')
def get_block():
    blocks = mongo.db.blocks.find({'id': request.args.get('id')}, {'_id': 0}).limit(1).sort([('index',-1)])
    return json.dumps(blocks[0] if blocks.count() else {}, indent=4), 404

@app.route('/deeplink')
def deeplink():
    import urllib
    return redirect('myapp://' + urllib.quote(request.args.get('txn')))

@app.route('/get-url')
def get_url():
    res = requests.get(request.args.get('url'))
    return res.content

@app.route('/block-user', methods=['POST'])
def block_user():
    config = current_app.config['yada_config']
    mongo = current_app.config['yada_mongo']
    mongo.site_db.blocked_users.update({'bulletin_secret': request.json.get('bulletin_secret'), 'username': request.json.get('user')}, {'bulletin_secret': request.json.get('bulletin_secret'), 'username': request.json.get('user')}, upsert=True)
    return 'ok'

@app.route('/flag', methods=['POST'])
def flag():
    config = current_app.config['yada_config']
    mongo = current_app.config['yada_mongo']
    mongo.site_db.flagged_content.update(request.json, request.json, upsert=True)
    return 'ok'

@app.route('/peers', methods=['GET', 'POST'])
def peers():
    config = current_app.config['yada_config']
    mongo = current_app.config['yada_mongo']
    peers = Peers(config, mongo)
    if request.method == 'POST':
        try:
            socket.inet_aton(request.json['host'])
            host = request.json['host']
            port = int(request.json['port'])
            failed = request.json.get('failed')
            if failed:
                res = mongo.db.peers.find({'host': host, 'port': port})
                if res.count():
                    mongo.db.peers.update({'host': host, 'port': port}, {'$inc': {'failed': 1}})
            else:
                mongo.db.peers.update({
                    'host': host, 
                    'port': port
                }, {
                    'host': host, 
                    'port': port, 
                    'active': True, 
                    'failed': 0
                }, upsert=True)
            Peers.peers = peers.init_local()
            return 'ok'
        except:
            return 'failed to add peer, invalid host', 400
    else:
        if not hasattr(Peers, 'peers'):
            Peers.peers = peers.init_local()
        return Peers.peers

@app.route('/stats')
def stats():
    return app.send_static_file('stats/index.html')

def get_base_graph(self):
    bulletin_secret = request.args.get('bulletin_secret').replace(' ', '+')
    if request.json:
        ids = request.json.get('ids')
    else:
        ids = []
    graph = Graph(app.config['yada_config'], app.config['yada_mongo'], bulletin_secret, ids)
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
app.add_url_rule('/explorer-search', view_func=endpoints.ExplorerSearchView.as_view('explorer-search'))
app.add_url_rule('/get-latest-block', view_func=endpoints.GetLatestBlockView.as_view('get-latest-block'))
app.add_url_rule('/create-relationship', view_func=endpoints.CreateRelationshipView.as_view('create-relationship'))
app.add_url_rule('/yada_config.json', view_func=endpoints.GetYadaConfigView.as_view('yada-config'))

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--conf',
                help='set your config file')
args = parser.parse_args()
conf = args.conf or 'config/config.json'
with open(conf) as f:
    config = Config(json.loads(f.read()))

app.config['yada_config'] = config
app.config['yada_mongo'] = Mongo(config)
#push_service = FCMNotification(api_key=config.fcm_key)

