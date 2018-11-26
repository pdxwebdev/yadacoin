import socketio
import socket
import json
import time
import signal
import sys
import requests
import base64
import humanhash
import re
import pymongo
import subprocess
import os
import endpoints
import multiprocessing
from sys import exit
from multiprocessing import Process, Value, Array, Pool
from socketIO_client import SocketIO, BaseNamespace
from flask import Flask, render_template, request, Response
from flask_cors import CORS
from yadacoin import TransactionFactory, Transaction, \
                    MissingInputTransactionException, \
                    Input, Output, Block, Config, Peers, \
                    Blockchain, BlockChainException, TU, BU, \
                    Mongo, BlockFactory, NotEnoughMoneyException, Peer, \
                    Consensus, PoolPayer, Faucet, Send, Graph
from yadacoin import MiningPool
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from gevent import pywsgi


def signal_handler(signal, frame):
        print('Closing... Or use ctrl + \\')
        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    multiprocessing.freeze_support()
    import argparse
    import os.path
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', nargs=None, help='serve, mine, or consensus')
    parser.add_argument('config', default="config.json", nargs="?", help='config file')
    parser.add_argument('to', default="", nargs="?", help='to')
    parser.add_argument('value', default=0, nargs="?", help='amount')
    parser.add_argument('-c', '--cores', default=multiprocessing.cpu_count(), help='Specify number of cores to use')
    parser.add_argument('-p', '--pool', default='', help='Specify pool to use')
    args = parser.parse_args()

    if os.path.isfile(args.config):
        with open(args.config) as f:
            Config.from_dict(json.loads(f.read()))
    else:
        print 'no config file found at \'%s\'' % args.config
        exit()

    if args.mode == 'consensus':
        Peers.init()
        consensus = Consensus()
        consensus.verify_existing_blockchain()
        while 1:
            consensus.sync_top_down()
            consensus.sync_bottom_up()
            time.sleep(1)

    elif args.mode == 'send':
        Send.run(args.to, float(args.value))

    elif args.mode == 'mine':
        print Config.to_json()
        print '\r\n\r\n\r\n//// YADA COIN MINER ////'
        print "Core count:", args.cores
        def get_mine_data():
            return json.loads(requests.get("http://{pool}/pool".format(pool=args.pool)).content)
        running_processes = []
        Mongo.init()
        while 1:
            Peers.init(my_peer=False)
            if not Peers.peers:
                time.sleep(1)
                continue
            if len(running_processes) >= int(args.cores):
                for i, proc in enumerate(running_processes):
                    if not proc.is_alive():
                        proc.terminate()
                        data = get_mine_data()
                        p = Process(target=MiningPool.pool_mine, args=(args.pool, Config.address, data['header'], data['target'], data['nonces'], data['special_min']))
                        p.start()
                        running_processes[i] = p
            else:
                data = get_mine_data()
                p = Process(target=MiningPool.pool_mine, args=(args.pool, Config.address, data['header'], data['target'], data['nonces'], data['special_min']))
                p.start()
                running_processes.append(p)
            time.sleep(1)

    elif args.mode == 'faucet':
        while 1:
            Peers.init()
            if not Peers.peers:
                time.sleep(1)
                continue
            Faucet.run()
            time.sleep(1)

    elif args.mode == 'pool':
        pp = PoolPayer()
        while 1:            
            pp.do_payout()
            time.sleep(1)

    elif args.mode == 'serve':
        print Config.to_json()

        def get_base_graph(self):
            bulletin_secret = request.args.get('bulletin_secret').replace(' ', '+')
            graph = Graph(bulletin_secret)
            return graph
        endpoints.BaseGraphView.get_base_graph = get_base_graph

        app = Flask(__name__)
        app.debug = True
        app.secret_key = '23ljk2l9a08sd7f09as87df09as87df3k4j'
        CORS(app)

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
        app.add_url_rule('/pool', view_func=endpoints.MiningPoolView.as_view('pool'))
        app.add_url_rule('/pool-submit', view_func=endpoints.MiningPoolSubmitView.as_view('poolsubmit'), methods=['GET', 'POST'])
        app.add_url_rule('/pool-explorer', view_func=endpoints.MiningPoolExplorerView.as_view('pool-explorer'))
        app.add_url_rule('/get-block', view_func=endpoints.GetBlockByHashView.as_view('get-block'), methods=['GET'])
        app.add_url_rule('/getblockheight', view_func=endpoints.GetBlockHeightView.as_view('get-block-height'))
        app.add_url_rule('/newtransaction', view_func=endpoints.NewTransactionView.as_view('new-transaction'), methods=['POST'])
        app.add_url_rule('/newblock', view_func=endpoints.NewBlockView.as_view('new-block'), methods=['POST'])
        app.add_url_rule('/get-blocks', view_func=endpoints.GetBlocksView.as_view('get-blocks-range'))
        app.add_url_rule('/create-raw-transaction', view_func=endpoints.CreateRawTransactionView.as_view('create-raw-transaction'), methods=['POST'])
        app.add_url_rule('/sign-raw-transaction', view_func=endpoints.SignRawTransactionView.as_view('sign-raw-transaction'), methods=['POST'])
        app.add_url_rule('/generate-wallet', view_func=endpoints.GenerateWalletView.as_view('generate-wallet'))
        app.add_url_rule('/generate-child-wallet', view_func=endpoints.GenerateChildWalletView.as_view('generate-child-wallet'), methods=['POST'])
        app.add_url_rule('/explorer-search', view_func=endpoints.ExplorerSearchView.as_view('explorer-search'))
        app.add_url_rule('/get-latest-block', view_func=endpoints.GetLatestBlockView.as_view('get-latest-block'))

        sio = socketio.Server(async_mode='gevent')
        sio.register_namespace(endpoints.BlockchainSocketServer('/chat'))
        app = socketio.Middleware(sio, app)

        Peer.init_my_peer()
        peer = Config.peer_host + ":" + str(Config.peer_port)
        print "http://{}/generate-wallet".format(peer)

        Peers.init()
        if not Peers.peers:
            raise Exception("peer service unavailble, restart this process")
        pywsgi.WSGIServer((Config.serve_host, Config.serve_port), app).serve_forever()