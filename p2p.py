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
import multiprocessing
from sys import exit
from multiprocessing import Process, Value, Array, Pool
from socketIO_client import SocketIO, BaseNamespace
from flask import Flask, render_template, request, Response
from flask_cors import CORS
from yadacoin import (
    TransactionFactory, Transaction, MissingInputTransactionException,
    Input, Output, Block, Config, Peers, 
    Blockchain, BlockChainException, TU, BU, 
    Mongo, BlockFactory, NotEnoughMoneyException, Peer, 
    Consensus, PoolPayer, Faucet, Send, Graph, Serve, endpoints
)
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
    parser.add_argument('-n', '--network', default='mainnet', help='Specify maintnet or testnet')
    parser.add_argument('-c', '--cores', default=multiprocessing.cpu_count(), help='Specify number of cores to use')
    parser.add_argument('-p', '--pool', default='', help='Specify pool to use')
    args = parser.parse_args()

    if os.path.isfile(args.config):
        with open(args.config) as f:
            config = Config(json.loads(f.read()))
    else:
        print 'no config file found at \'%s\'' % args.config
        exit()

    mongo = Mongo(config)
    if args.mode == 'consensus':
        consensus = Consensus(config, mongo)
        consensus.verify_existing_blockchain()
        while 1:
            consensus.sync_top_down()
            consensus.sync_bottom_up()
            time.sleep(1)

    elif args.mode == 'send':
        Send.run(config, args.to, float(args.value))

    elif args.mode == 'mine':
        print config.to_json()
        print '\r\n\r\n\r\n//// YADA COIN MINER ////'
        print "Core count:", args.cores
        def get_mine_data():
            return json.loads(requests.get("http://{pool}/pool".format(pool=args.pool)).content)
        running_processes = []
        mongo = Mongo(config)
        while 1:
            Peers.init(config, args.network, my_peer=False)
            if not Peers.peers:
                time.sleep(1)
                continue
            if len(running_processes) >= int(args.cores):
                for i, proc in enumerate(running_processes):
                    if not proc.is_alive():
                        proc.terminate()
                        data = get_mine_data()
                        p = Process(target=MiningPool.pool_mine, args=(args.pool, config.address, data['header'], data['target'], data['nonces'], data['special_min']))
                        p.start()
                        running_processes[i] = p
            else:
                data = get_mine_data()
                p = Process(target=MiningPool.pool_mine, args=(args.pool, config.address, data['header'], data['target'], data['nonces'], data['special_min']))
                p.start()
                running_processes.append(p)
            time.sleep(1)

    elif args.mode == 'faucet':
        while 1:
            Peers.init(config, args.network)
            if not Peers.peers:
                time.sleep(1)
                continue
            Faucet.run(config)
            time.sleep(1)

    elif args.mode == 'pool':
        pp = PoolPayer(config, mongo)
        while 1:            
            pp.do_payout()
            time.sleep(1)

    elif args.mode == 'serve':
        print config.to_json()

        config.network = args.network

        my_peer = Peer.init_my_peer(config, config.network)
        config.callbackurl = 'http://%s/create-relationship' % my_peer.to_string()
        print "http://{}/generate-wallet".format(my_peer.to_string())

        serve = Serve(config)
        pywsgi.WSGIServer((config.serve_host, config.serve_port), serve.app).serve_forever()

        