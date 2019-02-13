import json
import hashlib
import os
import base64

from io import BytesIO
from uuid import uuid4
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from bitcoin.signmessage import BitcoinMessage, VerifyMessage, SignMessage
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from crypt import Crypt
from transactionutils import TU
from blockchainutils import BU
from coincurve import verify_signature
from eccsnacks.curve25519 import scalarmult, scalarmult_base
from pymongo import MongoClient
from peers import Peers
from mongo import Mongo

class TransactionFactory(object):
    def __init__(
        self,
        config,
        mongo,
        bulletin_secret='',
        username='',
        value=0,
        fee=0.0,
        requester_rid='',
        requested_rid='',
        public_key='',
        dh_public_key='',
        private_key='',
        dh_private_key='',
        to='',
        inputs='',
        outputs='',
        coinbase=False,
        chattext=None,
        signin=None
    ):
        self.config = config
        self.mongo = mongo
        self.bulletin_secret = bulletin_secret
        self.username = username
        self.requester_rid = requester_rid
        self.requested_rid = requested_rid
        self.public_key = public_key
        self.dh_public_key = dh_public_key
        self.private_key = private_key
        self.value = value
        self.fee = float(fee)
        self.dh_private_key = dh_private_key
        self.to = to
        self.outputs = []
        for x in outputs:
            self.outputs.append(Output.from_dict(x))
        self.inputs = []
        for x in inputs:
            if 'signature' in x and 'public_key' in x:
                self.inputs.append(ExternalInput.from_dict(x))
            else:
                self.inputs.append(Input.from_dict(x))
        self.coinbase = coinbase
        self.chattext = chattext
        self.signin = signin
        self.do_money()
        inputs_concat = self.get_input_hashes()
        outputs_concat = self.get_output_hashes()
        if bulletin_secret:
            self.rid = self.generate_rid()
            if self.chattext:
                self.relationship = json.dumps({
                    "chatText": self.chattext
                })
                self.cipher = Crypt(self.config.wif)
                self.encrypted_relationship = self.cipher.encrypt(self.relationship)
            elif self.signin:
                for shared_secret in TU.get_shared_secrets_by_rid(self.config, self.mongo, self.rid):
                    self.relationship = SignIn(self.signin)
                    self.cipher = Crypt(shared_secret.encode('hex'), shared=True)
                    self.encrypted_relationship = self.cipher.shared_encrypt(self.relationship.to_json())
            else:
                if not self.dh_public_key or not self.dh_private_key:
                    a = os.urandom(32)
                    self.dh_public_key = scalarmult_base(a).encode('hex')
                    self.dh_private_key = a.encode('hex')
                self.relationship = self.generate_relationship()
                if not private_key:
                    raise BaseException('missing private key')
                self.cipher = Crypt(self.config.wif)
                self.encrypted_relationship = self.cipher.encrypt(self.relationship.to_json())
        else:
            self.rid = ''
            self.encrypted_relationship = ''
        self.header = self.dh_public_key + \
            self.rid + \
            self.encrypted_relationship + \
            "{0:.8f}".format(self.fee) + \
            self.requester_rid + \
            self.requested_rid + \
            inputs_concat + \
            outputs_concat
        self.hash = hashlib.sha256(self.header).digest().encode('hex')
        if self.private_key:
            self.transaction_signature = TU.generate_signature_with_private_key(private_key, self.hash)
        else:
            self.transaction_signature = ''
        self.transaction = self.generate_transaction()

    def do_money(self):
        my_address = str(P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex')))
        input_txns = BU.get_wallet_unspent_transactions(self.config, self.mongo, my_address)
        miner_transactions = self.mongo.db.miner_transactions.find()
        mtxn_ids = []
        for mtxn in miner_transactions:
            for mtxninput in mtxn['inputs']:
                mtxn_ids.append(mtxninput['id'])

        if self.inputs:
            inputs = self.inputs
        else:
            inputs = []
            for input_txn in input_txns:
                if input_txn['id'] not in mtxn_ids:
                    if 'signature' in input_txn and 'public_key' in input_txn:
                        inputs.append(ExternalInput.from_dict(input_txn))
                    else:
                        inputs.append(Input.from_dict(input_txn))

        input_sum = 0
        if self.coinbase:
            self.inputs = []
        else:
            if inputs:
                needed_inputs = []
                done = False
                for y in inputs:
                    print y.id
                    txn = BU.get_transaction_by_id(self.config, self.mongo, y.id, instance=True)
                    for txn_output in txn.outputs:
                        if txn_output.to == my_address:
                            input_sum += txn_output.value
                            needed_inputs.append(y)
                            if input_sum >= (sum([x.value for x in self.outputs])+self.fee):
                                done = True
                                break
                    if done == True:
                        break

                if not done:
                    raise NotEnoughMoneyException('not enough money')
                self.inputs = needed_inputs
            else:
                self.inputs = []

            remainder = input_sum-(sum([x.value for x in self.outputs])+self.fee)

            found = False
            for x in self.outputs:
                if my_address == x.to:
                    found = True
                    x.value += remainder
            if not found:
                return_change_output = Output(
                    to=my_address,
                    value=remainder
                )
                self.outputs.append(return_change_output)

    def get_input_hashes(self):
        input_hashes = []
        for x in self.inputs:
            txn = BU.get_transaction_by_id(self.config, self.mongo, x.id, instance=True)
            input_hashes.append(str(txn.transaction_signature))

        return ''.join(sorted(input_hashes, key=str.lower))

    def get_output_hashes(self):
        outputs_sorted = sorted([x.to_dict() for x in self.outputs], key=lambda x: x['to'].lower())
        return ''.join([x['to'] + "{0:.8f}".format(x['value']) for x in outputs_sorted])

    def generate_rid(self):
        my_bulletin_secret = self.config.get_bulletin_secret()
        if my_bulletin_secret == self.bulletin_secret:
            raise BaseException('bulletin secrets are identical. do you love yourself so much that you want a relationship on the blockchain?')
        bulletin_secrets = sorted([str(my_bulletin_secret), str(self.bulletin_secret)], key=str.lower)
        return hashlib.sha256(str(bulletin_secrets[0]) + str(bulletin_secrets[1])).digest().encode('hex')

    def generate_relationship(self):
        return Relationship(
            dh_private_key=self.dh_private_key,
            their_bulletin_secret=self.bulletin_secret,
            their_username=self.username,
            my_bulletin_secret=self.config.get_bulletin_secret(),
            my_username=self.config.username
        )

    def generate_transaction(self):
        return Transaction(
            self.config,
            self.mongo,
            self.rid,
            self.transaction_signature,
            self.encrypted_relationship,
            self.public_key,
            self.dh_public_key,
            float(self.fee),
            self.requester_rid,
            self.requested_rid,
            self.hash,
            inputs=[x.to_dict() for x in self.inputs],
            outputs=[x.to_dict() for x in self.outputs],
            coinbase=self.coinbase
        )

    def generate_transaction_signature(self):
        return TU.generate_signature(self.hash, self.private_key)

class InvalidTransactionException(BaseException):
    pass

class InvalidTransactionSignatureException(BaseException):
    pass

class MissingInputTransactionException(BaseException):
    pass

class NotEnoughMoneyException(BaseException):
    pass

class Transaction(object):
    def __init__(
        self,
        config,
        mongo,
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
        coinbase=False
    ):
        self.config = config
        self.mongo = mongo
        self.rid = rid
        self.transaction_signature = transaction_signature
        self.relationship = relationship
        self.public_key = public_key
        self.dh_public_key = dh_public_key if dh_public_key else ''
        self.fee = float(fee)
        self.requester_rid = requester_rid if requester_rid else ''
        self.requested_rid = requested_rid if requested_rid else ''
        self.hash = txn_hash
        self.outputs = []
        for x in outputs:
            self.outputs.append(Output.from_dict(x))
        self.inputs = []
        for x in inputs:
            if 'signature' in x and 'public_key' in x:
                self.inputs.append(ExternalInput.from_dict(x))
            else:
                self.inputs.append(Input.from_dict(x))
        self.coinbase = coinbase

    @classmethod
    def from_dict(cls, config, mongo, txn):
        try:
            relationship = Relationship(**txn.get('relationship', ''))
        except:
            relationship = txn.get('relationship', '')
        return cls(
            config=config,
            mongo=mongo,
            transaction_signature=txn.get('id'),
            rid=txn.get('rid', ''),
            relationship=relationship,
            public_key=txn.get('public_key'),
            dh_public_key=txn.get('dh_public_key'),
            fee=float(txn.get('fee')),
            requester_rid=txn.get('requester_rid', ''),
            requested_rid=txn.get('requested_rid', ''),
            txn_hash=txn.get('hash', ''),
            inputs=txn.get('inputs', []),
            outputs=txn.get('outputs', []),
            coinbase=txn.get('coinbase', '')
        )

    def verify(self):
        verify_hash = self.generate_hash()
        address = P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex'))

        if verify_hash != self.hash:
            raise InvalidTransactionException("transaction is invalid")

        try:
            result = verify_signature(base64.b64decode(self.transaction_signature), self.hash, self.public_key.decode('hex'))
            if not result:
                raise Exception()
        except:
            try:
                result = VerifyMessage(address, BitcoinMessage(self.hash, magic=''), self.transaction_signature)
                if not result:
                    raise
            except:
                raise InvalidTransactionSignatureException("transaction signature did not verify")

        # verify spend
        total_input = 0
        for txn in self.inputs:
            txn_input = Transaction.from_dict(self.config, self.mongo, BU.get_transaction_by_id(self.config, self.mongo, txn.id))

            found = False
            for output in txn_input.outputs:
                if hasattr(txn, 'public_key') and hasattr(txn, 'signature'):
                    ext_address = P2PKHBitcoinAddress.from_pubkey(txn.public_key.decode('hex'))
                    if str(output.to) == str(ext_address):
                        found = True
                        try:
                            result = verify_signature(base64.b64decode(txn.signature), txn.id, txn.public_key.decode('hex'))
                            if not result:
                                raise Exception()
                        except:
                            try:
                                result = VerifyMessage(ext_address, BitcoinMessage(txn.id, magic=''), txn.signature)
                                if not result:
                                    raise
                            except:
                                raise InvalidTransactionSignatureException("external input transaction signature did not verify")
                elif str(output.to) == str(address):
                    found = True
                    total_input += float(output.value)
                
            if not found:
                if hasattr(txn, 'public_key') and hasattr(txn, 'signature'):
                    raise InvalidTransactionException("external input signing information did not match any recipients of the input transaction")
                else:
                    raise InvalidTransactionException("using inputs from a transaction where you were not one of the recipients.")

        if self.coinbase:
            return

        total_output = 0
        for txn in self.outputs:
            total_output += float(txn.value)
        total = float(total_output) + float(self.fee)
        if "{0:.8f}".format(total_input) != "{0:.8f}".format(total):
            raise BaseException("inputs and outputs sum must match %s, %s, %s, %s" % (total_input, float(total_output), float(self.fee), total))

    def generate_hash(self):
        inputs_concat = self.get_input_hashes()
        outputs_concat = self.get_output_hashes()
        hashout = hashlib.sha256(
            self.dh_public_key +
            self.rid +
            self.relationship +
            "{0:.8f}".format(self.fee) +
            self.requester_rid +
            self.requested_rid +
            inputs_concat +
            outputs_concat
        ).digest().encode('hex')
        return hashout

    def get_input_hashes(self):
        input_hashes = []
        for x in self.inputs:
            txn = BU.get_transaction_by_id(self.config, self.mongo, x.id, instance=True)
            if not txn:
                raise MissingInputTransactionException("This transaction is not in the blockchain.")
            input_hashes.append(str(txn.transaction_signature))

        return ''.join(sorted(input_hashes, key=lambda v: v.lower()))

    def get_output_hashes(self):
        outputs_sorted = sorted([x.to_dict() for x in self.outputs], key=lambda x: x['to'].lower())
        return ''.join([x['to'] + "{0:.8f}".format(x['value']) for x in outputs_sorted])

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
            'outputs': [x.to_dict() for x in self.outputs]
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


class Input(object):
    def __init__(self, signature):
        self.id = signature

    @classmethod
    def from_dict(cls, txn):
        return cls(
            signature=txn.get('id', ''),
        )

    def to_dict(self):
        return {
            'id': self.id
        }


class ExternalInput(Input):
    def __init__(self, txn_id, public_key, signature):
        self.id = txn_id
        self.public_key = public_key
        self.signature = signature

    @classmethod
    def from_dict(cls, txn):
        return cls(
            txn_id=txn.get('id', ''),
            public_key=txn.get('public_key', ''),
            signature=txn.get('signature', '')
        )

    def to_dict(self):
        return {
            'id': self.id,
            'public_key': self.public_key,
            'signature': self.signature
        }


class Output(object):
    def __init__(self, to, value):
        self.to = to
        self.value = value

    @classmethod
    def from_dict(cls, txn):
        return cls(
            to=txn.get('to', ''),
            value=txn.get('value', '')
        )

    def to_dict(self):
        return {
            'to': self.to,
            'value': self.value
        }


class Relationship(object):
    def __init__(self, dh_private_key, their_bulletin_secret, their_username, my_bulletin_secret, my_username):
        self.dh_private_key = dh_private_key
        self.their_bulletin_secret = their_bulletin_secret
        self.their_username = their_username
        self.my_bulletin_secret = my_bulletin_secret
        self.my_username = my_username

    def to_dict(self):
        return {
            'dh_private_key': self.dh_private_key,
            'their_bulletin_secret': self.their_bulletin_secret,
            'their_username': self.their_username,
            'my_bulletin_secret': self.my_bulletin_secret,
            'my_username': self.my_username
        }

    def to_json(self):
        return json.dumps(self.to_dict())

class SignIn(object):
    def __init__(self, signin):
        self.signin = signin

    def to_dict(self):
        return {
            "signIn": self.signin
        }

    def to_json(self):
        return json.dumps(self.to_dict())
