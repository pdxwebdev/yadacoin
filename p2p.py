# import socketio
# import socket
import json
import time
import signal
import sys
# import requests
# import base64
# import humanhash
# import re
# import pymongo
# import subprocess
# import os
import multiprocessing
# from sys import exit
# from multiprocessing import Process, Value, Array, Pool
# from socketIO_client import SocketIO, BaseNamespace
# from flask import Flask, render_template, request, Response
# from flask_cors import CORS

from yadacoin.config import Config
from yadacoin.mongo import Mongo
from flask import Flask
# from yadacoin.block import Block
""""    (
    TransactionFactory, Transaction, MissingInputTransactionException,
    Input, Output, Block, Config, Peers, 
    Blockchain, BlockChainException, TU, BU, 
    Mongo, BlockFactory, NotEnoughMoneyException, Peer, 
    Consensus, PoolPayer, Faucet, Send, Graph, Serve, endpoints, Wallet
)
from yadacoin import MiningPool
"""
# from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
# from gevent import pywsgi, pool


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
    parser.add_argument('-n', '--network', default='mainnet', help='Specify mainnet, testnet or regnet')
    parser.add_argument('-c', '--cores', default=multiprocessing.cpu_count(), help='Specify number of cores to use')
    parser.add_argument('-p', '--pool', default='', help='Specify pool to use')
    parser.add_argument('-d', '--debug', default=False, help='Debug messages')
    parser.add_argument('-r', '--reset', default=False, help='If blockchain is invalid, truncate at error block')
    args = parser.parse_args()

    if os.path.isfile(args.config):
        with open(args.config) as f:
            config = Config(json.loads(f.read()))
    else:
        print("no config file found at '%s'" % args.config)
        sys.exit()

    with open('logodata.b64') as f:
        config.logo_data = f.read()

    mongo = Mongo(config)
    if args.mode == 'consensus':
        # Only import required modules
        from yadacoin.consensus import Consensus
        consensus = Consensus(config, mongo, args.debug)
        consensus.verify_existing_blockchain(reset=args.reset)
        while 1:
            wait = consensus.sync_bottom_up()
            if wait:
                time.sleep(1)

    elif args.mode == 'send':
        # Only import required modules
        from yadacoin.send import Send
        Send.run(config, mongo, args.to, float(args.value))

    elif args.mode == 'mine':
        print("Not supported Yet")
        sys.exit()
        """
        print config.to_json()
        print '\r\n\r\n\r\n//// YADA COIN MINER ////'
        print "Core count:", args.cores
        def get_mine_data():
            try:
                return json.loads(requests.get("http://{pool}/pool".format(pool=args.pool)).content)
            except Exception as e:
                print(e)
                return None
        running_processes = []
        mp = MiningPool(config, mongo)
        while 1:
            Peers.init(config, mongo, args.network, my_peer=False)
            if not Peers.peers:
                time.sleep(1)
                continue
            if len(running_processes) >= int(args.cores):
                for i, proc in enumerate(running_processes):
                    if not proc.is_alive():
                        proc.terminate()
                        data = get_mine_data()
                        if data:
                            p = Process(target=mp.pool_mine, args=(args.pool, config.address, data['header'], data['target'], data['nonces'], data['special_min']))
                            p.start()
                            running_processes[i] = p
            else:
                data = get_mine_data()
                if data:
                    p = Process(target=mp.pool_mine, args=(args.pool, config.address, data['header'], data['target'], data['nonces'], data['special_min']))
                    p.start()
                    running_processes.append(p)
            time.sleep(1)
        """

    elif args.mode == 'faucet':
        print("Not supported Yet")
        sys.exit()
        """
        while 1:
            Peers.init(config, mongo, args.network)
            if not Peers.peers:
                time.sleep(1)
                continue
            Faucet.run(config, mongo)
            time.sleep(1)
        """

    elif args.mode == 'pool':
        print("Not supported Yet")
        sys.exit()
        """
        pp = PoolPayer(config, mongo)
        while 1:            
            pp.do_payout()
            time.sleep(1)
        """

    elif args.mode == 'serve':
        from yadacoin.peers import Peer
        from yadacoin.serve import Serve
        print(config.to_json())

        config.network = args.network

        my_peer = Peer.init_my_peer(config, mongo, config.network)
        print("http://{}".format(my_peer.to_string()))

        app = Flask(__name__)
        serve = Serve(config, mongo, app)
        app.run(config.serve_host, config.serve_port)

        
