import requests
import hashlib
import base64
import json
from socketIO_client import SocketIO, BaseNamespace
from blockchainutils import BU
from transactionutils import TU
from coincurve.utils import verify_signature
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from transaction import Transaction, Relationship, Input, Output
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
        signatures=None
    ):
        self.config = config
        self.mongo = Mongo(self.config)
        self.rid = rid
        self.transaction_signature = transaction_signature
        self.relationship = relationship
        self.public_key = public_key
        self.dh_public_key = dh_public_key
        self.fee = fee
        self.requester_rid = requester_rid
        self.requested_rid = requested_rid
        self.hash = txn_hash
        self.inputs = inputs
        self.outputs = outputs
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
    def from_dict(cls, config, txn):
        try:
            relationship = Relationship(**txn.get('relationship', ''))
        except:
            relationship = txn.get('relationship', '')

        return cls(
            config=config,
            transaction_signature=txn.get('id'),
            rid=txn.get('rid', ''),
            relationship=relationship,
            public_key=txn.get('public_key'),
            dh_public_key=txn.get('dh_public_key', ''),
            fee=float(txn.get('fee')),
            requester_rid=txn.get('requester_rid', ''),
            requested_rid=txn.get('requested_rid', ''),
            txn_hash=txn.get('hash', ''),
            inputs=[Input.from_dict(input_txn) for input_txn in txn.get('inputs', '')],
            outputs=[Output.from_dict(output_txn) for output_txn in txn.get('outputs', '')],
            coinbase=txn.get('coinbase', ''),
            signatures=txn.get('signatures', '')
        )

    def generate_rid(self, first_bulletin_secret, second_bulletin_secret):
        if first_bulletin_secret == second_bulletin_secret:
            raise BaseException('bulletin secrets are identical. do you love yourself so much that you want a relationship on the blockchain?')
        bulletin_secrets = sorted([str(first_bulletin_secret), str(second_bulletin_secret)], key=str.lower)
        return hashlib.sha256(str(bulletin_secrets[0]) + str(bulletin_secrets[1])).digest().encode('hex')

    def verify(self):
        super(FastGraph, self).verify()
        
        if not self.signatures:
            raise InvalidFastGraphTransactionException('no signatures were provided')

        xaddress = str(P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex')))
        unspent = [x['id'] for x in BU.get_wallet_unspent_transactions(self.config, xaddress)]
        unspent_fastgraph = [x['id'] for x in BU.get_wallet_unspent_fastgraph_transactions(self.config, xaddress)]
        inputs = [x.id for x in self.inputs]
        if len(set(inputs) & set(unspent)) != len(inputs) and len(set(inputs) & set(unspent_fastgraph)) != len(inputs):
            return False

        highest_height = 0
        for inp in inputs:
            # TODO: go back to the on-chain transaction to determine the relationship state
            txn = BU.get_transaction_by_id(self.config, inp, give_block=True)
            if 'index' in txn and txn['index'] > highest_height:
                highest_height = txn['index']

        for signature in self.signatures:
            signature.passed = False
            # did I sign it?
            signed = verify_signature(
                base64.b64decode(signature.signature),
                self.hash,
                self.config.public_key.decode('hex')
            )
            if signed:
                signature.passed = True

            """
            # This is for a later fork to include a wider consensus area for a larger spending group
            else:
                mutual_friends = [x for x in BU.get_transactions_by_rid(self.config, self.rid, self.config.bulletin_secret, raw=True, rid=True, lt_block_height=highest_height)]
                for mutual_friend in mutual_friends:
                    mutual_friend = Transaction.from_dict(self.config, mutual_friend)
                    if isinstance(mutual_friend.relationship, Relationship) and signature.bulletin_secret == mutual_friend.relationship.their_bulletin_secret:
                        other_mutual_friend = mutual_friend
                for mutual_friend in mutual_friends:
                    mutual_friend = Transaction.from_dict(self.config, mutual_friend)
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
                return False
        return True

    def get_signatures(self, peers):
        Peers.init(self.config, self.config.network)
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
        Peers.init(self.config, self.config.network)
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
        