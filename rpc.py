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
    InvalidTransactionSignatureException, MissingInputTransactionException, MiningPool, endpoints_old
)
import yadacoin.blockchainutils
import yadacoin.config
from pymongo import MongoClient
from socketIO_client import SocketIO, BaseNamespace
from pyfcm import FCMNotification
from multiprocessing import Process, Value, Array, Pool
from flask_cors import CORS
from eccsnacks.curve25519 import scalarmult, scalarmult_base
from bson.objectid import ObjectId

PROTOCOL_VERSION = 2

class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print('error')

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
CORS(app, supports_credentials=True)

@app.route('/pool-guide', methods=['GET', 'POST'])
def pool_guide():
    rid = session.get('rid')
    username = session.get('username')
    return render_template(
        'pool.html',
        rid=rid,
        username=username
        )

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    rid = session.get('rid')
    username = session.get('username')
    return render_template(
        'profile.html',
        rid=rid,
        username=username
        )

@app.route('/firebase-messaging-sw.js')
def firebase_service_worker():
    return app.send_static_file('app/www/ServiceWorker.js')

@app.route('/fcm-token', methods=['POST'])
def fcm_token():
    try:
        config = current_app.config['yada_config']
        mongo = current_app.config['yada_mongo']
        token = request.json.get('token')
        print(token)
        rid = request.json.get('rid')
        txn = BU().get_transaction_by_rid(rid, rid=True) 
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
    rid = session.get('rid')
    username = session.get('username')
    return render_template(
        'explorer.html',
        rid=rid,
        username=username
        )

@app.route('/docs')
def docs():
    return app.send_static_file('docs/index.html')

def changetime(block):
    from datetime import datetime
    block['time'] = datetime.utcfromtimestamp(int(block['time'])).strftime('%Y-%m-%dT%H:%M:%S UTC')
    return block

@app.route('/hashrate')
def hashrate():
    rid = session.get('rid')
    username = session.get('username')
    return render_template(
        'hashrate.html',
        rid=rid,
        username=username
        )

@app.route('/api-stats')
def api_stats():
    max_target = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    config = current_app.config['yada_config']
    mongo = current_app.config['yada_mongo']
    blocks = config.BU.get_blocks()
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
    rid = session.get('rid')
    username = session.get('username')
    return render_template(
        'index.html',
        rid=rid,
        username=username
        )

@app.route('/enterprise')
def enterprise():
    rid = session.get('rid')
    username = session.get('username')
    return render_template(
        'enterprise.html',
        rid=rid,
        username=username
        )

@app.route('/guide')
def guide():
    rid = session.get('rid')
    username = session.get('username')
    return render_template(
        'guide.html',
        rid=rid,
        username=username
        )

@app.route('/team')
def team():
    rid = session.get('rid')
    username = session.get('username')
    return render_template(
        'team.html',
        rid=rid,
        username=username
        )

@app.route('/get-rid')
def get_rid():
    my_bulletin_secret = config.get_bulletin_secret()
    rids = sorted([str(my_bulletin_secret), str(request.args.get('bulletin_secret'))], key=str.lower)
    rid = hashlib.sha256((str(rids[0]) + str(rids[1])).encode('utf-8')).digest().hex()
    return json.dumps({'rid': rid})

@app.route('/get-block')
def get_block():
    mongo = current_app.config['yada_mongo']
    blocks = mongo.db.blocks.find({'id': request.args.get('id')}, {'_id': 0}).limit(1).sort([('index',-1)])
    return json.dumps(blocks[0] if blocks.count() else {}, indent=4), 404

@app.route('/deeplink')
def deeplink():
    import urllib
    return redirect('myapp://' + urllib.quote(request.args.get('txn')))

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
            if request.json.get('failed'):
                return 'wrong consensus cleint version, please update', 400
            failed = request.json.get('failed_v1')
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
            Peers.peers_json = peers.init_local()
            return 'ok'
        except:
            return 'failed to add peer, invalid host', 400
    else:
        if not hasattr(Peers, 'peers'):
            Peers.peers_json = peers.init_local()
        return Peers.peers_json

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

endpoints_old.BaseGraphView.get_base_graph = get_base_graph

app.add_url_rule('/register', view_func=endpoints_old.RegisterView.as_view('register'))
app.add_url_rule('/transaction', view_func=endpoints_old.TransactionView.as_view('transaction'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-info', view_func=endpoints_old.GraphView.as_view('graph'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-sent-friend-requests', view_func=endpoints_old.GraphSentFriendRequestsView.as_view('graphsentfriendrequests'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-friend-requests', view_func=endpoints_old.GraphFriendRequestsView.as_view('graphfriendrequests'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-friends', view_func=endpoints_old.GraphFriendsView.as_view('graphfriends'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-posts', view_func=endpoints_old.GraphPostsView.as_view('graphposts'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-messages', view_func=endpoints_old.GraphMessagesView.as_view('graphmessages'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-new-messages', view_func=endpoints_old.GraphNewMessagesView.as_view('graphnewmessages'), methods=['GET', 'POST'])
app.add_url_rule('/get-graph-comments', view_func=endpoints_old.GraphCommentsView.as_view('get-comments'), methods=['POST'])
app.add_url_rule('/get-graph-reacts', view_func=endpoints_old.GraphReactsView.as_view('get-reacts'), methods=['POST'])
app.add_url_rule('/get-graph-wallet', view_func=endpoints_old.RidWalletView.as_view('get-wallet'))
app.add_url_rule('/wallet', view_func=endpoints_old.WalletView.as_view('wallet'))
app.add_url_rule('/faucet', view_func=endpoints_old.FaucetView.as_view('faucet'))
app.add_url_rule('/explorer-search', view_func=endpoints_old.ExplorerSearchView.as_view('explorer-search'))
app.add_url_rule('/get-latest-block', view_func=endpoints_old.GetLatestBlockView.as_view('get-latest-block'))
app.add_url_rule('/create-relationship', view_func=endpoints_old.CreateRelationshipView.as_view('create-relationship'), methods=['POST'])
app.add_url_rule('/yada_config.json', view_func=endpoints_old.GetYadaConfigView.as_view('yada-config'))
app.add_url_rule('/authenticated', view_func=endpoints_old.AuthenticatedView.as_view('authenticated'))
app.add_url_rule('/login', view_func=endpoints_old.GetSiginCodeView.as_view('login'))
app.add_url_rule('/logout', view_func=endpoints_old.LogoutView.as_view('logout'))
app.add_url_rule('/sign-raw-transaction', view_func=endpoints_old.SignRawTransactionView.as_view('sign-raw-transaction'), methods=['POST'])
app.add_url_rule('/post-fastgraph-transaction', view_func=endpoints_old.PostFastGraphView.as_view('post-fastgraph-transaction'), methods=['POST'])
app.add_url_rule('/authenticated', view_func=endpoints_old.AuthenticatedView.as_view('home'))
app.add_url_rule('/search', view_func=endpoints_old.SearchView.as_view('search'))
app.add_url_rule('/react', view_func=endpoints_old.ReactView.as_view('react'), methods=['POST'])
app.add_url_rule('/comment-react', view_func=endpoints_old.CommentReactView.as_view('comment-react'), methods=['POST'])
app.add_url_rule('/get-comment-reacts', view_func=endpoints_old.GetCommentReactsView.as_view('get-comment-reacts'), methods=['POST'])
app.add_url_rule('/get-comment-reacts-detail', view_func=endpoints_old.GetCommentReactsDetailView.as_view('get-comment-reacts-detail'), methods=['POST'])
app.add_url_rule('/comment', view_func=endpoints_old.CommentView.as_view('comment'), methods=['POST'])
app.add_url_rule('/pool', view_func=endpoints_old.MiningPoolView.as_view('pool'))
app.add_url_rule('/pool-submit', view_func=endpoints_old.MiningPoolSubmitView.as_view('poolsubmit'), methods=['GET', 'POST'])
app.add_url_rule('/pool-explorer', view_func=endpoints_old.MiningPoolExplorerView.as_view('pool-explorer'))

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--conf',
                help='set your config file')
args = parser.parse_args()
conf = args.conf or 'config/regnet.json'

global config
with open(conf) as f:
    config = yadacoin.config.Config(json.loads(f.read()))
    # Sets the global var for all objects
    yadacoin.config.CONFIG = config
    mongo = Mongo()
    config.mongo = mongo
    # force network, command line one takes precedence
    config.debug = True
    config.network = 'regnet'
    config.protocol_version = PROTOCOL_VERSION
    BU = yadacoin.blockchainutils.BlockChainUtils()
    yadacoin.blockchainutils.set_BU(BU)  # To be removed
    config.BU = yadacoin.blockchainutils.GLOBAL_BU


with open('logodata.b64') as f:
    config.logo_data = f.read()
config.network = 'regnet'
app.config['yada_config'] = config
app.config['yada_mongo'] = config.mongo
#push_service = FCMNotification(api_key=config.fcm_key)
app.run(host=config.serve_host, port=config.web_server_port, threaded=True)
