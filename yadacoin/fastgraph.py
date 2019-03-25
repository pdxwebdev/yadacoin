import requests
import hashlib
import base64
import json
from socketIO_client import SocketIO, BaseNamespace
from blockchainutils import BU
from transactionutils import TU
from coincurve.utils import verify_signature
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from transaction import Transaction, Relationship, Input, Output, ExternalInput
from peers import Peers
from mongo import Mongo


class InvalidFastGraphTransactionException(Exception):
    pass

class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

class FastGraph(Transaction):
    def __init__(
        self,
        config,
        mongo,
        block_height,
        time='',
        rid='',
        transaction_signature='',
        relationship='',
        public_key='',
        dh_public_key='',
        fee=0.0,
        requester_rid='',
        requested_rid='',
        txn_hash='',
        inputs='',
        outputs='',
        coinbase=False,
        signatures=None,
        extra_blocks=None
    ):
        self.config = config
        self.mongo = mongo
        self.block_height = block_height
        self.time = time
        self.rid = rid
        self.transaction_signature = transaction_signature
        self.relationship = relationship
        self.public_key = public_key
        self.dh_public_key = dh_public_key
        self.fee = fee
        self.requester_rid = requester_rid
        self.requested_rid = requested_rid
        self.hash = txn_hash
        self.outputs = []
        self.extra_blocks = extra_blocks
        for x in outputs:
            self.outputs.append(Output.from_dict(x))
        self.inputs = []
        for x in inputs:
            if 'signature' in x and 'public_key' in x and 'address' in x:
                self.inputs.append(ExternalInput.from_dict(self.config, self.mongo, x))
            else:
                self.inputs.append(Input.from_dict(x))
        self.coinbase = coinbase

        if not signatures:
            signatures = []

        self.signatures = []
        for signature in signatures:
            if isinstance(signature, FastGraphSignature):
                self.signatures.append(signature)
            else:
                self.signatures.append(FastGraphSignature(signature))
    
    @classmethod
    def from_dict(cls, config, mongo, block_height, txn):
        try:
            relationship = Relationship(**txn.get('relationship', ''))
        except:
            relationship = txn.get('relationship', '')

        return cls(
            config=config,
            mongo=mongo,
            block_height=block_height,
            time=txn.get('time'),
            transaction_signature=txn.get('id'),
            rid=txn.get('rid', ''),
            relationship=relationship,
            public_key=txn.get('public_key'),
            dh_public_key=txn.get('dh_public_key', ''),
            fee=float(txn.get('fee')),
            requester_rid=txn.get('requester_rid', ''),
            requested_rid=txn.get('requested_rid', ''),
            txn_hash=txn.get('hash', ''),
            inputs=txn.get('inputs', []),
            outputs=txn.get('outputs', []),
            coinbase=txn.get('coinbase', ''),
            signatures=txn.get('signatures', [])
        )

    def generate_rid(self, first_bulletin_secret, second_bulletin_secret):
        if first_bulletin_secret == second_bulletin_secret:
            raise Exception('bulletin secrets are identical. do you love yourself so much that you want a relationship on the blockchain?')
        bulletin_secrets = sorted([str(first_bulletin_secret), str(second_bulletin_secret)], key=str.lower)
        return hashlib.sha256(str(bulletin_secrets[0]) + str(bulletin_secrets[1])).digest().encode('hex')

    def get_origin_relationship(self, rid=None, bulletin_secret=None):
        for inp in self.inputs:
            inp = inp.id
            while 1:
                txn = BU.get_transaction_by_id(self.config, self.mongo, inp, give_block=False, include_fastgraph=True)
                if txn:
                    if 'rid' in txn and txn['rid'] and 'dh_public_key' in txn and txn['dh_public_key']:
                        if rid and txn['rid'] != rid:
                            continue
                        rids = [txn['rid']]
                        if 'requester_rid' in txn and txn['requester_rid']:
                            rids.append(txn['requester_rid'])
                        if 'requested_rid' in txn and txn['requested_rid']:
                            rids.append(txn['requested_rid'])
                        
                        # we need their public_key, not mine, so we get both transactions for the relationship
                        txn_for_rids = BU.get_transaction_by_rid(self.config, self.mongo, rids, bulletin_secret=bulletin_secret, raw=True, rid=True, theirs=True, public_key=self.public_key)

                        if txn_for_rids:
                            return txn_for_rids
                        else:
                            return False
                    else:
                        inp = txn['inputs'][0]['id']
                else:
                    txn = self.mongo.db.fastgraph_transactions.find_one({'id': inp})
                    if txn and 'inputs' in txn['txn'] and txn['txn']['inputs'] and 'id' in txn['txn']['inputs'][0]:
                        inp = txn['txn']['inputs'][0]['id']
                    else:
                        return False


    def verify(self):
        super(FastGraph, self).verify()
        result = self.mongo.db.fastgraph_transactions.find_one({
            'txn.hash': self.hash
        })
        
        if not self.signatures:
            raise InvalidFastGraphTransactionException('no signatures were provided')

        xaddress = str(P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex')))
        unspent = [x['id'] for x in BU.get_wallet_unspent_transactions(self.config, self.mongo, xaddress)]
        unspent_fastgraph = [x['id'] for x in BU.get_wallet_unspent_fastgraph_transactions(self.config, self.mongo, xaddress)]
        inputs = [x.id for x in self.inputs]
        if len(set(inputs) & set(unspent)) != len(inputs) and len(set(inputs) & set(unspent_fastgraph)) != len(inputs):
            raise InvalidFastGraphTransactionException('Input not found in unspent')

        txn_for_rids = self.get_origin_relationship()
        if not txn_for_rids:
            raise InvalidFastGraphTransactionException('no origin transactions found')
        public_key = txn_for_rids['public_key']

        for signature in self.signatures:
            signature.passed = False
            signed = verify_signature(
                base64.b64decode(signature.signature),
                self.hash,
                public_key.decode('hex')
            )
            if signed:
                signature.passed = True

            """
            # This is for a later fork to include a wider consensus area for a larger spending group
            else:
                mutual_friends = [x for x in BU.get_transactions_by_rid(self.config, self.mongo, self.rid, self.config.bulletin_secret, raw=True, rid=True, lt_block_height=highest_height)]
                for mutual_friend in mutual_friends:
                    mutual_friend = Transaction.from_dict(self.config, self.mongo, mutual_friend)
                    if isinstance(mutual_friend.relationship, Relationship) and signature.bulletin_secret == mutual_friend.relationship.their_bulletin_secret:
                        other_mutual_friend = mutual_friend
                for mutual_friend in mutual_friends:
                    mutual_friend = Transaction.from_dict(self.config, self.mongo, mutual_friend)
                    if mutual_friend.public_key != self.config.public_key:
                        identity = verify_signature(
                            base64.b64decode(other_mutual_friend.relationship.their_bulletin_secret),
                            other_mutual_friend.relationship.their_username,
                            mutual_friend.public_key.decode('hex')
                        )
                        signed = verify_signature(
                            base64.b64decode(signature.signature),
                            self.hash,
                            mutual_friend.public_key.decode('hex')
                        )
                        if identity and signed:
                            signature.passed = True
            """
        for signature in self.signatures:
            if not signature.passed:
                raise InvalidFastGraphTransactionException('not all signatures verified')

    def get_signatures(self, peers):
        Peers.init(self.config, self.mongo, self.config.network)
        for peer in Peers.peers:
            try:
                socketIO = SocketIO(peer.host, peer.port, wait_for_connection=False)
                chat_namespace = socketIO.define(ChatNamespace, '/chat')
                chat_namespace.emit('newfastgraphtransaction', self.to_dict())
                socketIO.wait(seconds=1)
                chat_namespace.disconnect()
            except Exception as e:
                print e
                pass

    def broadcast(self):
        Peers.init(self.config, self.mongo, self.config.network)
        for peer in Peers.peers:
            try:
                socketIO = SocketIO(peer.host, peer.port, wait_for_connection=False)
                chat_namespace = socketIO.define(ChatNamespace, '/chat')
                chat_namespace.emit('new-fastgraph-transaction', self.to_dict())
                socketIO.wait(seconds=1)
                chat_namespace.disconnect()
            except Exception as e:
                print e
                pass
    
    def save(self):
        self.mongo.db.fastgraph_transactions.insert({
            'txn': self.to_dict(),
            'public_key': self.public_key,
            'id': self.transaction_signature
        })

    def to_dict(self):
        ret = {
            'time': self.time,
            'rid': self.rid,
            'id': self.transaction_signature,
            'relationship': self.relationship,
            'public_key': self.public_key,
            'dh_public_key': self.dh_public_key,
            'fee': float(self.fee),
            'hash': self.hash,
            'inputs': [x.to_dict() for x in self.inputs],
            'outputs': [x.to_dict() for x in self.outputs],
            'signatures': [sig.to_string() for sig in self.signatures]
        }
        if self.dh_public_key:
            ret['dh_public_key'] = self.dh_public_key
        if self.requester_rid:
            ret['requester_rid'] = self.requester_rid
        if self.requested_rid:
            ret['requested_rid'] = self.requested_rid
        return ret
    
    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)

class FastGraphSignature(object):
    def __init__(self, signature):
        self.signature = signature

    def to_string(self):
        return self.signature
        