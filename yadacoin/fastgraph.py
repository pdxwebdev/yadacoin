import hashlib
import base64
import json
# TODO: socketio, socketio_client, flask.socketio => 3 different libs for the same thing?
from logging import getLogger
from socketIO_client import SocketIO, BaseNamespace
from coincurve.utils import verify_signature
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress

from yadacoin.blockchainutils import BU
from yadacoin.graphutils import GraphUtils as GU
from yadacoin.config import get_config

from yadacoin.transaction import Transaction, Relationship, Input, Output, ExternalInput
from yadacoin.peers import Peers


class InvalidFastGraphTransactionException(Exception):
    pass

class MissingFastGraphInputTransactionException(Exception):
    pass


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print('error')


class FastGraph(Transaction):

    def __init__(
        self,
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
        extra_blocks=None,
        raw=False
    ):
        self.config = get_config()
        self.mongo = self.config.mongo
        self.app_log = getLogger('tornado.application')
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
        self.raw = raw
        for x in outputs:
            self.outputs.append(Output.from_dict(x))
        self.inputs = []
        for x in inputs:
            if 'signature' in x and 'public_key' in x and 'address' in x:
                self.inputs.append(ExternalInput.from_dict( x))
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
    def from_dict(cls, block_height, txn, raw=False):
        try:
            relationship = Relationship(**txn.get('relationship', ''))
        except:
            relationship = txn.get('relationship', '')

        return cls(
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
            signatures=txn.get('signatures', []),
            raw=raw
        )

    def generate_rid(self, first_bulletin_secret, second_bulletin_secret):
        if first_bulletin_secret == second_bulletin_secret:
            raise Exception('bulletin secrets are identical. do you love yourself so much that you want a relationship on the blockchain?')
        bulletin_secrets = sorted([str(first_bulletin_secret), str(second_bulletin_secret)], key=str.lower)
        return hashlib.sha256((str(bulletin_secrets[0]) + str(bulletin_secrets[1])).encode('utf-8')).digest().hex()

    def get_origin_relationship(self, rid=None, bulletin_secret=None):
        for inp in self.inputs:
            inp = inp.id
            while 1:
                txn = BU().get_transaction_by_id(inp, give_block=False, include_fastgraph=True)
                if txn:
                    if 'rid' in txn and txn['rid'] and 'dh_public_key' in txn and txn['dh_public_key']:
                        if rid and txn['rid'] != rid and txn.get('requester_rid') != rid and txn.get('requested_rid') != rid:
                            return False
                        return txn
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
        
        if not self.signatures and not self.raw:
            raise InvalidFastGraphTransactionException('no signatures were provided')

        origin_relationship = self.get_origin_relationship()
        if not origin_relationship:
            raise InvalidFastGraphTransactionException('no origin transactions found')

        rids = [origin_relationship['rid']]  # for signin, we maybe sending messages directly to do the service provider
        if 'requester_rid' in origin_relationship and origin_relationship['requester_rid']:
            rids.append(origin_relationship['requester_rid'])
        if 'requested_rid' in origin_relationship and origin_relationship['requested_rid']:
            rids.append(origin_relationship['requested_rid'])
        
        # we need the public_key of the service provider, either requester_rid, or requested_rid, we don't know, so we try both
        txns_for_rids = []
        for rid in rids:
            txn_for_rid = GU().get_transaction_by_rid(
                rid,
                raw=True,
                rid=True,
                theirs=True,
                public_key=self.public_key
            )
            if txn_for_rid:
                txns_for_rids.append(txn_for_rid)

        for signature in self.signatures:
            signature.passed = False
            for txn_for_rid in txns_for_rids:
                signed = verify_signature(
                    base64.b64decode(signature.signature),
                    self.hash.encode('utf-8'),
                    bytes.fromhex(txn_for_rid['public_key'])
                )
                self.app_log.debug(signed)
                self.app_log.debug(signature.signature)
                self.app_log.debug(self.hash.encode('utf-8'))
                self.app_log.debug(txn_for_rid['public_key'])
                if signed:
                    signature.passed = True
                    break

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
                        other_mutual_friend.relationship.their_username.encode('utf-8'),
                        bytes.fromhex(mutual_friend.public_key)
                    )
                    signed = verify_signature(
                        base64.b64decode(signature.signature),
                        self.hash.encode('utf-8'),
                        bytes.fromhex(mutual_friend.public_key)
                    )
                    if identity and signed:
                        signature.passed = True
        """
        for signature in self.signatures:
            if not signature.passed:
                raise InvalidFastGraphTransactionException('not all signatures verified')

    def get_signatures(self, peers):
        Peers.init( self.config.network)
        for peer in Peers.peers:
            try:
                socketIO = SocketIO(peer.host, peer.port, wait_for_connection=False)
                chat_namespace = socketIO.define(ChatNamespace, '/chat')
                chat_namespace.emit('newfastgraphtransaction', self.to_dict())
                socketIO.wait(seconds=1)
                chat_namespace.disconnect()
            except Exception as e:
                print("Error fastgraph.get_signatures", e)
                pass

    def broadcast(self):
        Peers.init( self.config.network)
        for peer in Peers.peers:
            try:
                socketIO = SocketIO(peer.host, peer.port, wait_for_connection=False)
                chat_namespace = socketIO.define(ChatNamespace, '/chat')
                chat_namespace.emit('new-fastgraph-transaction', self.to_dict())
                socketIO.wait(seconds=1)
                chat_namespace.disconnect()
            except Exception as e:
                print("Error fastgraph.broadcast", e)
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
