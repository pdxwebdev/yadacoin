"""
Handlers required by the graph operations
"""

import base64
import hashlib
import json
import os
import time
import requests

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve.utils import verify_signature
from eccsnacks.curve25519 import scalarmult_base
from logging import getLogger
from threading import Thread
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU
from yadacoin.fastgraph import FastGraph
from yadacoin.graph import Graph
from yadacoin.graphutils import GraphUtils as GU
from yadacoin.transaction import TransactionFactory, Transaction, InvalidTransactionException, \
    InvalidTransactionSignatureException, MissingInputTransactionException
from yadacoin.transactionutils import TU
from yadacoin.transactionbroadcaster import TxnBroadcaster
from yadacoin.nsbroadcaster import NSBroadcaster
from yadacoin.peers import Peer
from yadacoin.auth import jwtauth


class GraphConfigHandler(BaseHandler):

    async def get(self):
        peer = "http://{}:{}".format(self.config.peer_host, self.config.peer_port)
        yada_config = {
            "baseUrl": "{}".format(peer),
            "transactionUrl": "{}/transaction".format(peer),
            "fastgraphUrl": "{}/post-fastgraph-transaction".format(peer),
            "graphUrl": "{}".format(peer),
            "walletUrl": "{}/get-graph-wallet".format(peer),
            "loginUrl": "{}/login".format(peer),
            "registerUrl": "{}/create-relationship".format(peer),
            "authenticatedUrl": "{}/authenticated".format(peer),
            "logoData": ''
        }
        return self.render_as_json(yada_config)

@jwtauth
class BaseGraphHandler(BaseHandler):
    def get_base_graph(self):
        self.bulletin_secret = self.get_query_argument('bulletin_secret').replace(' ', '+')
        self.to = self.get_query_argument('to', None)
        self.username = self.get_query_argument('username', None)
        self.rid = self.generate_rid(self.config.bulletin_secret, self.bulletin_secret)
        if self.request.body:
            ids = json.loads(self.request.body.decode('utf-8')).get('ids')
            rids = json.loads(self.request.body.decode('utf-8')).get('rids')
        else:
            ids = []
            rids = []
        try:
            key_or_wif = self.get_secure_cookie('key_or_wif').decode()
        except:
            key_or_wif = None
        if not key_or_wif:
            try:
                key_or_wif = self.jwt.get('key_or_wif')
            except:
                key_or_wif = None
        return Graph(self.config, self.config.mongo, self.bulletin_secret, ids, rids, key_or_wif)
        # TODO: should have a self.render here instead, not sure what is supposed to be returned here

    def generate_rid(self, first_bulletin_secret, second_bulletin_secret):
        bulletin_secrets = sorted([str(first_bulletin_secret), str(second_bulletin_secret)], key=str.lower)
        return hashlib.sha256((str(bulletin_secrets[0]) + str(bulletin_secrets[1])).encode('utf-8')).digest().hex()


class GraphInfoHandler(BaseGraphHandler):

    async def get(self):
        graph = self.get_base_graph()
        self.render_as_json(graph.to_dict())


class GraphRIDWalletHandler(BaseGraphHandler):

    async def get(self):
        address = self.get_query_argument('address')
        amount_needed = self.get_query_argument('amount_needed', None)
        if amount_needed:
            amount_needed = int(amount_needed)
        
        regular_txns = []
        chain_balance = 0
        async for txn in BU().get_wallet_unspent_transactions(address):
            if amount_needed:
                regular_txns.append(txn)
            for output in txn['outputs']:
                if output['to'] == address:
                    chain_balance += int(output['value'])
    
        wallet = {
            'chain_balance': chain_balance,
            'balance': chain_balance,
            'unspent_transactions': regular_txns if amount_needed else []
        }
        self.render_as_json(wallet, indent=4)


class RegistrationHandler(BaseHandler):

    async def get(self):
        data = {
            'bulletin_secret': self.config.bulletin_secret,
            'username': self.config.username,
            'callbackurl': self.config.callbackurl,
            'to': self.config.address
        }
        self.render_as_json(data)


class GraphTransactionHandler(BaseGraphHandler):

    async def get(self):
        rid = self.request.args.get('rid')
        if rid:
            transactions = BU().get_transactions_by_rid(rid, self.config.bulletin_secret, rid=True, raw=True)
        else:
            transactions = []
        self.render_as_json(list(transactions))

    async def post(self):
        self.get_base_graph()  # TODO: did this to set bulletin_secret, refactor this
        items = json.loads(self.request.body.decode('utf-8'))
        if not isinstance(items, list):
            items = [items, ]
        else:
            items = [item for item in items]
        transactions = []
        for txn in items:
            transaction = Transaction.from_dict(BU().get_latest_block()['index'], txn)
            try:
                transaction.verify()
            except InvalidTransactionException:
                await self.config.mongo.async_db.failed_transactions.insert_one({
                    'exception': 'InvalidTransactionException',
                    'txn': txn
                })
                print('InvalidTransactionException')
                return 'InvalidTransactionException', 400
            except InvalidTransactionSignatureException:
                print('InvalidTransactionSignatureException')
                await self.config.mongo.async_db.failed_transactions.insert_one({
                    'exception': 'InvalidTransactionSignatureException',
                    'txn': txn
                })
                return 'InvalidTransactionSignatureException', 400
            except MissingInputTransactionException:
                pass
            except:
                raise
                print('uknown error')
                return 'uknown error', 400
            transactions.append(transaction)

        for x in transactions:
            if x.rid == self.rid and x.dh_public_key:
                me_pending_exists = await self.config.mongo.async_db.miner_transactions.find_one({
                    'public_key': self.config.public_key, 
                    'rid': self.rid, 
                    'dh_public_key': {'$exists': True}
                })
                me_blockchain_exists = await self.config.mongo.async_db.blocks.find_one({
                    'public_key': self.config.public_key, 
                    'rid': self.rid, 
                    'dh_public_key': {'$exists': True}
                })
                if not me_pending_exists and not me_blockchain_exists:
                    created_relationship = await self.create_relationship(self.bulletin_secret, self.username, self.to)
                    await self.config.mongo.async_db.miner_transactions.insert_one(created_relationship.transaction.to_dict())
                    created_relationship.transaction.relationship = created_relationship.relationship
                    await self.config.mongo.async_db.name_server.insert_one({
                        'rid': created_relationship.transaction.rid,
                        'requester_rid': created_relationship.transaction.requester_rid,
                        'requested_rid': created_relationship.transaction.requested_rid,
                        'peer_str': 'me', 
                        'peer': {'host': 'me', 'port': 0},
                        'txn': created_relationship.transaction.to_dict()
                    })
                    tb = NSBroadcaster(self.config)
                    await tb.ns_broadcast_job(created_relationship.transaction)
                
                pending_exists = await self.config.mongo.async_db.miner_transactions.find_one({
                    'public_key': x.public_key, 
                    'rid': self.rid, 
                    'dh_public_key': {'$exists': True}
                })
                blockchain_exists = await self.config.mongo.async_db.blocks.find_one({
                    'public_key': x.public_key, 
                    'rid': self.rid, 
                    'dh_public_key': {'$exists': True}
                })
                if pending_exists or blockchain_exists:
                    continue
            
            if x.dh_public_key:
                dup_check_count = await self.config.mongo.async_db.miner_transactions.count_documents({
                    'dh_public_key': {'$exists': True},
                    'rid': x.rid,
                    'requester_rid': x.requester_rid,
                    'requested_rid': x.requested_rid,
                    'public_key': x.public_key
                })
                if dup_check_count:
                    self.app_log.debug('found duplicate tx for rid set {}'.format(x.transaction_signature))
                    return

            ns_exists = await self.config.mongo.async_db.name_server.find_one({
                    'rid': x.rid,
                    'requester_rid': x.requester_rid,
                    'requested_rid': x.requested_rid
            })
            if not ns_exists:
                await self.config.mongo.async_db.name_server.insert_one({
                    'rid': x.rid,
                    'requester_rid': x.requester_rid,
                    'requested_rid': x.requested_rid,
                    'peer_str': 'me', 
                    'peer': {'host': 'me', 'port': 0},
                    'txn': x.to_dict()
                })
                tb = NSBroadcaster(self.config)
                await tb.ns_broadcast_job(x)
            if x.rid == self.rid and x.relationship:
                self.config.GU.verify_message(
                    x.rid,
                    '',
                    self.config.public_key,
                    x.transaction_signature,
                    x
                )

            await self.config.mongo.async_db.miner_transactions.insert_one(x.to_dict())
            txn_b = TxnBroadcaster(self.config)
            await txn_b.txn_broadcast_job(x)
            try:
                await self.config.push_service.do_push(x.to_dict(), self.bulletin_secret, self.app_log)
            except Exception as e:
                self.app_log.error(e)

        return self.render_as_json(items)

    async def create_relationship(self, bulletin_secret, username, to):
        config = self.config
        mongo = self.config.mongo

        if not bulletin_secret:
            return 'error: "bulletin_secret" missing', 400

        if not username:
            return 'error: "username" missing', 400

        if not to:
            return 'error: "to" missing', 400
        rid = TU.generate_rid(config, bulletin_secret)
        dup = mongo.db.blocks.find({'transactions.rid': rid})
        if dup.count():
            found_a = False
            found_b = False
            for txn in dup:
                if txn['public_key'] == config.public_key:
                    found_a = True
                if txn['public_key'] != config.public_key:
                    found_b = True
            if found_a and found_b:
                return json.dumps({"success": False, "status": "Already added"})

        miner_transactions = mongo.db.miner_transactions.find()
        mtxn_ids = []
        for mtxn in miner_transactions:
            for mtxninput in mtxn['inputs']:
                mtxn_ids.append(mtxninput['id'])

        checked_out_txn_ids = mongo.db.checked_out_txn_ids.find()
        for mtxn in checked_out_txn_ids:
            mtxn_ids.append(mtxn['id'])

        a = os.urandom(32).decode('latin1')
        dh_public_key = scalarmult_base(a).encode('latin1').hex()
        dh_private_key = a.encode('latin1').hex()

        transaction = await TransactionFactory.construct(
            block_height=BU().get_latest_block()['index'],
            bulletin_secret=bulletin_secret,
            username=username,
            fee=0.00,
            public_key=config.public_key,
            dh_public_key=dh_public_key,
            private_key=config.private_key,
            dh_private_key=dh_private_key,
            outputs=[
                {
                    'to': to,
                    'value': 0
                }
            ]
        )
        return transaction


class GraphSentFriendRequestsHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        await graph.get_sent_friend_requests()
        self.render_as_json(graph.to_dict())


class GraphFriendRequestsHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        await graph.get_friend_requests()
        self.render_as_json(graph.to_dict())


class GraphFriendsHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        self.render_as_json(graph.to_dict())


class GraphMessagesHandler(BaseGraphHandler):
    async def post(self):
        graph = self.get_base_graph()
        await graph.get_messages()
        self.render_as_json(graph.to_dict())


class GraphGroupMessagesHandler(BaseGraphHandler):
    async def post(self):
        graph = self.get_base_graph()
        graph.get_group_messages()
        self.render_as_json(graph.to_dict())


class GraphNewMessagesHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        await graph.get_new_messages()
        self.render_as_json(graph.to_dict())


class GraphCommentsHandler(BaseGraphHandler):
    async def post(self):
        graph = self.get_base_graph()
        await graph.get_comments()
        self.render_as_json(graph.to_dict())


class GraphReactsHandler(BaseGraphHandler):
    async def post(self):
        graph = self.get_base_graph()
        await graph.get_reacts()
        self.render_as_json(graph.to_dict())


class NSLookupHandler(BaseGraphHandler):
    async def get(self):
        ns_username = self.get_query_argument('username', None)
        ns_requested_rid = self.get_query_argument('requested_rid', None)
        ns_requester_rid = self.get_query_argument('requester_rid', None)
        id_type = self.get_query_argument('id_type', None)
        if ns_username:
            return self.render_as_json(await self.config.GU.search_ns_username(ns_username, ns_requested_rid, id_type))
        if ns_requested_rid:
            return self.render_as_json(await self.config.GU.search_ns_requested_rid(ns_requested_rid, ns_username, id_type))
        if ns_requester_rid:
            return self.render_as_json(await self.config.GU.search_ns_requester_rid(ns_requester_rid, ns_username, id_type))
        return self.render_as_json({"status": "error"}, 400)


class SignRawTransactionHandler(BaseHandler):
    async def post(self):
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif and self.jwt.get('key_or_wif') != 'true':
            return self.render_as_json({'error': 'not authorized'})
        config = self.config
        mongo = self.config.mongo
        body = json.loads(self.request.body.decode('utf-8'))
        try:
            fg = FastGraph.from_dict(0, body.get('txn'), raw=True)
            fg.verify()
        except:
            raise
            return 'invalid transaction', 400
        res = mongo.db.signed_transactions.find_one({'hash': body.get('hash')})
        if res:
            return 'no', 400
        try:
            rid = TU.generate_rid(config, body.get('bulletin_secret'))
            my_entry_for_relationship = GU().get_transaction_by_rid(rid, config.wif, rid=True, my=True, public_key=config.public_key)
            their_entry_for_relationship = GU().get_transaction_by_rid(rid, rid=True, raw=True, theirs=True, public_key=config.public_key)
            verified = verify_signature(
                base64.b64decode(body.get('bulletin_secret')),
                my_entry_for_relationship['relationship']['their_username'].encode(),
                bytes.fromhex(their_entry_for_relationship['public_key'])
            )
            if not verified:
                return 'no', 400
            verified = verify_signature(
                base64.b64decode(body.get('id')),
                body.get('hash').encode('utf-8'),
                bytes.fromhex(their_entry_for_relationship['public_key'])
            )
            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(their_entry_for_relationship['public_key'])))
            found = False
            async for x in BU().get_wallet_unspent_transactions(address, [body.get('input')]):
                if body.get('input') == x['id']:
                    found = True
            
            if not found:
                for x in BU().get_wallet_unspent_fastgraph_transactions(address):
                    if body.get('input') == x['id']:
                        found = True

            if found:
                signature = mongo.db.signed_transactions.find_one({
                    'input': body.get('input'),
                    'txn.public_key': body['txn']['public_key']
                })
                if signature:
                    already_spent = mongo.db.fastgraph_transactions.find_one({
                        'txn.inputs.id': body['input'],
                        'txn.public_key': body['txn']['public_key']
                    })
                    if already_spent:
                        self.set_status(400)
                        self.write('already spent!')
                        self.finish()
                        return True
                    else:
                        signature['txn']['signatures'] = [signature['signature']]
                        fastgraph = FastGraph.from_dict(0, signature['txn'])
                        try:
                            fastgraph.verify()
                        except Exception as e:
                            raise
                            return 'did not verify', 400
                        result = mongo.db.fastgraph_transactions.find_one({
                            'txn.hash': fastgraph.hash
                        })
                        if result:
                            return 'duplicate transaction found', 400
                        spent_check = mongo.db.fastgraph_transactions.find_one({
                            'txn.inputs.id': {'$in': [x.id for x in fastgraph.inputs]}
                        })
                        if spent_check:
                            return 'already spent input', 400
                        fastgraph.save()
            else:
                return 'no transactions with this input found', 400
            if verified:
                transaction_signature = TU.generate_signature_with_private_key(config.private_key, body.get('hash'))
                signature = {
                    'signature': transaction_signature,
                    'hash': body.get('hash'),
                    'bulletin_secret': body.get('bulletin_secret'),
                    'input': body.get('input'),
                    'id': body.get('id'),
                    'txn': body.get('txn')
                }
                mongo.db.signed_transactions.insert(signature)
                if '_id' in signature:
                    del signature['_id']
                self.render_as_json(signature, indent=4)
            else:
                return 'no', 400
        except Exception as e:
            raise
            self.render_as_json({
                'status': 'error',
                'msg': e
            })


class FastGraphHandler(BaseGraphHandler):
    async def post(self):
        # after the necessary signatures are gathered, the transaction is sent here.
        mongo = self.config.mongo
        graph = self.get_base_graph()
        fastgraph = json.loads(self.request.body.decode('utf-8'))
        fastgraph = FastGraph.from_dict(0, fastgraph)
        try:
            fastgraph.verify()
        except Exception as e:
            raise
            return 'did not verify', 400
        result = mongo.db.fastgraph_transactions.find_one({
            'txn.hash': fastgraph.hash
        })
        if result:
            return 'duplicate transaction found', 400
        spent_check = mongo.db.fastgraph_transactions.find_one({
            'public_key': fastgraph.public_key,
            'txn.inputs.id': {'$in': [x.id for x in fastgraph.inputs]}
        })
        if spent_check:
            return 'already spent input', 400
        fastgraph.save()
        # TODO: use new peer framework to broadcast fastgraph transactions
        #fastgraph.broadcast()
        self.render_as_json(fastgraph.to_dict())
        try:
            await self.config.push_service.do_push(fastgraph.to_dict(), self.bulletin_secret, self.app_log)
        except Exception as e:
            self.app_log.debug(e)


class NSHandler(BaseGraphHandler):
    async def get(self):
        graph = self.get_base_graph()
        config = self.config
        phrase = self.get_query_argument('searchTerm', None)
        requester_rid = self.get_query_argument('requester_rid', None)
        requested_rid = self.get_query_argument('requested_rid', None)
        username = bool(self.get_query_argument('username', True))
        complete = bool(self.get_query_argument('complete', False))
        if not phrase and not requester_rid and not requested_rid:
            return 'phrase required', 400
        bulletin_secret = self.get_query_argument('bulletin_secret').replace(' ', '+')
        if not bulletin_secret:
            return 'bulletin_secret required', 400
        my_bulletin_secret = config.get_bulletin_secret()

        if requester_rid:
            query = {
                '$or': [
                    {'rid': requester_rid},
                    {'requester_rid': requester_rid}
                ]
            }
            if username:
                query['txn.relationship.their_username'] = {
                    '$exists': True
                }
            ns_record = await self.config.mongo.async_db.name_server.find_one(query, {'_id': 0})
            if ns_record:
                ns_record = ns_record['txn']
            else:
                ns_record = await graph.resolve_ns(requester_rid, username=True)
                
            if ns_record:
                requester_rid = ns_record['rid']
                rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
                requested_rid = hashlib.sha256(rids[0].encode() + rids[1].encode()).hexdigest()
            
                address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(ns_record['public_key'])))
                filter_address = [x['to'] for x in ns_record['outputs'] if x['to'] != address]
                to = address if not filter_address else filter_address[0]
            else:
                return '{}', 404
            
            if complete:
                return self.render_as_json(ns_record)
            else:
                return self.render_as_json({
                    'bulletin_secret': ns_record['relationship']['their_bulletin_secret'],
                    'requested_rid': requested_rid,
                    'requester_rid': requester_rid,
                    'to': to,
                    'username': ns_record['relationship']['their_username']
                })

        rids = sorted([str(my_bulletin_secret), str(bulletin_secret)], key=str.lower)
        requester_rid = hashlib.sha256(rids[0].encode() + rids[1].encode()).hexdigest()
        if requested_rid:
            query = {
                'rid': requested_rid,
            }
            if username:
                query['username'] = {
                    'txn.relationship.their_username': {
                        '$exists': True
                    }
                }
            ns_record = await self.config.mongo.async_db.name_server.find_one(query)
            if ns_record:
                if complete:
                    return self.render_as_json(ns_record['txn'])
                else:
                    ns_record['txn']['relationship']['requested_rid'] = requested_rid
                    ns_record['txn']['relationship']['requester_rid'] = requester_rid
                    return self.render_as_json(ns_record['txn']['relationship'])
        else:
            friends = [x for x in GU().search_username(phrase)]
            ns_records = await self.config.mongo.async_db.name_server.find({
                'txn.relationship.their_username': phrase,
            }).to_list(10)
            return self.render_as_json([x['txn'] for x in ns_records] + [x for x in friends])

    async def post(self):
        try:
            ns = json.loads(self.request.body.decode('utf-8'))
        except:
            return self.render_as_json({'status': 'error', 'message': 'invalid request body'})
        try:
            nstxn = Transaction.from_dict(self.config.BU.get_latest_block()['index'], ns['txn'])
        except:
            return self.render_as_json({'status': 'error', 'message': 'invalid transaction'})
        try:
            peer = Peer(ns['peer']['host'], ns['peer']['port'])
        except:
            return self.render_as_json({'status': 'error', 'message': 'invalid peer'})

        existing = await self.config.mongo.async_db.name_server.find_one({
            'rid': nstxn.rid,
            'requester_rid': nstxn.requester_rid,
            'requested_rid': nstxn.requested_rid,
            'peer_str': peer.to_string(),
        })
        if not existing:
            await self.config.mongo.async_db.name_server.insert_one({
                'rid': nstxn.rid,
                'requester_rid': nstxn.requester_rid,
                'requested_rid': nstxn.requested_rid,
                'peer_str': peer.to_string(), 
                'peer': peer.to_dict(),
                'txn': nstxn.to_dict()
            })
        tb = NSBroadcaster(self.config)
        await tb.ns_broadcast_job(nstxn)
        return self.render_as_json({'status': 'success'})


class SiaFileHandler(BaseGraphHandler):
    async def get(self):
        from requests.auth import HTTPBasicAuth
        headers = {
            'User-Agent': 'Sia-Agent'
        }
        try:
            res = requests.get('http://0.0.0.0:9980/renter/files', headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
            fileData = json.loads(res.content.decode())
            return self.render_as_json({
                'status': 'success',
                'files': [
                    {
                        'siapath': x['siapath'],
                        'stream_url': 'http://0.0.0.0:9980/renter/stream/' + x['siapath'],
                        'available': x['available']
                    } for x in fileData.get('files', [])
                ]
            })
        except:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })


class SiaStreamFileHandler(BaseGraphHandler):
    def prepare(self):
        header = "Content-Type"
        body = "video/mp4"
        self.set_header(header, body)

    async def get(self):
        from requests.auth import HTTPBasicAuth
        headers = {
            'User-Agent': 'Sia-Agent'
        }
        siapath = self.get_query_argument('siapath')
        try:
            res = requests.get('http://0.0.0.0:9980/renter/file/{}'.format(siapath), headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        except:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })
        fileData = json.loads(res.content.decode())
        if fileData.get('file', {}).get('available'):
            http_client = AsyncHTTPClient()
            url = 'http://0.0.0.0:9980/renter/stream/' + siapath.replace(' ', '%20')
            request = HTTPRequest(url=url, streaming_callback=self.on_chunk, request_timeout=2000000)
            await http_client.fetch(request)
        else:
            self.set_status(400)
            self.write('{"status": "error", "message": "file not available"}')
        self.finish()

    def on_chunk(self, chunk):
        self.write(chunk)
        self.flush()


class SiaUploadHandler(BaseGraphHandler):
    async def get(self):
        from requests.auth import HTTPBasicAuth
        headers = {
            'User-Agent': 'Sia-Agent'
        }
        filepath = self.get_query_argument('filepath')
        try:
            res = requests.post('http://0.0.0.0:9980/renter/upload/{}'.format(filepath.split('/')[-1]), data={'source': filepath}, headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        except:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })
        res = requests.get('http://0.0.0.0:9980/renter/files', headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        fileData = json.loads(res.content.decode())
        return self.render_as_json({'status': 'success', 'files': [{'siapath': x['siapath'], 'stream_url': 'http://0.0.0.0:9980/renter/stream/' + x['siapath']} for x in fileData.get('files', [])]})


class SiaShareFileHandler(BaseGraphHandler):
    async def get(self):
        from requests.auth import HTTPBasicAuth
        headers = {
            'User-Agent': 'Sia-Agent'
        }
        dst='/home/mvogel/'
        siapath = self.get_query_argument('siapath')
        try:
            res = requests.get('http://0.0.0.0:9980/renter/share/send?dst={}&siapath={}'.format(dst + siapath.split('/')[-1] + '.sia', siapath), headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        except:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })
        with open(dst + siapath.split('/')[-1] + '.sia', 'rb') as f:
            data = f.read()
        bdata = base64.b64encode(data)
        return self.render_as_json({'filedata': bdata.decode()}) # this data will go in the relationship of the yada transaction


    async def post(self):
        from requests.auth import HTTPBasicAuth
        headers = {
            'User-Agent': 'Sia-Agent'
        }
        src='/home/mvogel/'
        relationship = json.loads(self.request.body.decode('utf-8'))
        siafiledata = base64.b64decode(relationship['groupChatFile'])
        with open(src + relationship['groupChatFileName'].split('/')[-1] + '.sia', 'wb') as f:
            f.write(bytearray(siafiledata))
        try:
            res = requests.get('http://0.0.0.0:9980/renter/file/{}'.format(relationship['groupChatFileName']), headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        except:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })
        fileData = json.loads(res.content.decode())
        if not fileData.get('file', None):
            res = requests.post('http://0.0.0.0:9980/renter/share/receive', {'src': src + relationship['groupChatFileName'] + '.sia', 'siapath': ''}, headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        return self.render_as_json({'status': 'success', 'stream_url': 'http://0.0.0.0:9980/renter/stream/' + relationship['groupChatFileName']})


class SiaDeleteHandler(BaseGraphHandler):
    async def get(self):
        from requests.auth import HTTPBasicAuth
        headers = {
            'User-Agent': 'Sia-Agent'
        }
        siapath = self.get_query_argument('siapath')
        try:
            res = requests.post('http://0.0.0.0:9980/renter/delete/{}'.format(siapath), headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        except:
            self.set_status(400)
            return self.render_as_json({
                'status': 'error',
                'message': 'sia node not responding'
            })
        res = requests.get('http://0.0.0.0:9980/renter/files', headers=headers, auth=HTTPBasicAuth('', self.config.sia_api_key))
        fileData = json.loads(res.content.decode())
        return self.render_as_json({
            'status': 'success',
            'files': [
                {
                    'siapath': x['siapath'],
                    'stream_url': 'http://0.0.0.0:9980/renter/stream/' + x['siapath'],
                    'available': x['available']
                } for x in fileData.get('files', [])
            ]
        })


# these routes are placed in the order of operations for getting started.
GRAPH_HANDLERS = [
    (r'/yada_config.json', GraphConfigHandler), # first the config is requested
    (r'/get-graph-info', GraphInfoHandler), # then basic graph info is requested. Giving existing relationship information, if present.
    (r'/get-graph-wallet', GraphRIDWalletHandler), # request balance and UTXOs
    (r'/register', RegistrationHandler), # if a relationship is not present, we "register." client requests information necessary to generate a friend request transaction
    (r'/transaction', GraphTransactionHandler), # first the client submits their friend request transaction.
    (r'/get-graph-sent-friend-requests', GraphSentFriendRequestsHandler), # get all friend requests I've sent
    (r'/get-graph-friend-requests', GraphFriendRequestsHandler), # get all friend requests sent to me
    (r'/get-graph-friends', GraphFriendsHandler), # get client/server relationship. Same as get-graph-info, but here for symantic purposes
    (r'/get-graph-messages', GraphMessagesHandler), # get messages from friends
    (r'/get-graph-new-messages', GraphNewMessagesHandler), # get new messages that are newer than a given timestamp
    (r'/get-graph-reacts', GraphReactsHandler), # get reacts for posts and comments
    (r'/get-graph-comments', GraphCommentsHandler), # get comments for posts
    (r'/ns-lookup', NSLookupHandler), # search by username for ns name server.
    (r'/sign-raw-transaction', SignRawTransactionHandler), # server signs the client transaction
    (r'/post-fastgraph-transaction', FastGraphHandler), # fastgraph transaction is submitted by client
    (r'/sia-upload', SiaUploadHandler), # upload a file to your local sia renter
    (r'/sia-files', SiaFileHandler), # list files from the local sia renter
    (r'/sia-files-stream', SiaStreamFileHandler), #stream the file from the sia network, we need this because of cross origin
    (r'/sia-share-file', SiaShareFileHandler), # share a file or list files from the local sia renter and return the .sia data base 64 encoded
    (r'/sia-delete', SiaDeleteHandler),
    (r'/ns', NSHandler), # name server endpoints
]
