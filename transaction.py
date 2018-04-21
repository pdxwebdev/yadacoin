import json
import hashlib
import os
import argparse
import qrcode
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

class TransactionFactory(object):
    def __init__(
        self,
        bulletin_secret='',
        shared_secret='',
        value=1,
        fee=0.1,
        requester_rid='',
        requested_rid='',
        public_key='',
        dh_public_key='',
        private_key='',
        dh_private_key='',
        to='',
        inputs='',
        outputs='',
        coinbase=False
    ):
        self.bulletin_secret = bulletin_secret
        self.requester_rid = requester_rid
        self.requested_rid = requested_rid
        self.public_key = public_key
        self.dh_public_key = dh_public_key
        self.private_key = private_key
        self.value = value
        self.fee = fee
        self.dh_private_key = dh_private_key
        self.to = to
        self.outputs = outputs
        self.inputs = inputs
        self.coinbase = coinbase
        inputs_concat = self.get_input_hashes()
        outputs_concat = self.get_output_hashes()
        if bulletin_secret:
            self.rid = self.generate_rid()
            self.relationship = self.generate_relationship()
            if not private_key:
                raise BaseException('missing private key')
            self.cipher = Crypt(private_key)
            self.encrypted_relationship = self.cipher.encrypt(self.relationship.to_json())
        else:
            self.rid = ''
            self.encrypted_relationship = ''
        self.hash = hashlib.sha256(
            self.dh_public_key +
            self.rid +
            self.encrypted_relationship +
            str(self.fee) +
            self.requester_rid +
            self.requested_rid +
            inputs_concat +
            outputs_concat
        ).digest().encode('hex')
        self.transaction_signature = self.generate_transaction_signature()
        self.transaction = self.generate_transaction()

    def get_input_hashes(self):
        input_hashes = []
        for x in self.inputs:
            txn = BU.get_transaction_by_id(x.id, instance=True)
            input_hashes.append(str(txn.transaction_signature))

        return ''.join(sorted(input_hashes, key=str.lower))

    def get_output_hashes(self):
        outputs_sorted = sorted([x.to_dict() for x in self.outputs], key=lambda x: x['to'])
        return ''.join([x['to']+str(float(x['value'])) for x in outputs_sorted])

    def generate_rid(self):
        my_bulletin_secret = TU.get_bulletin_secret()
        if my_bulletin_secret == self.bulletin_secret:
            raise BaseException('bulletin secrets are identical. do you love yourself so much that you want a relationship on the blockchain?')
        rids = sorted([str(my_bulletin_secret), str(self.bulletin_secret)], key=str.lower)
        return hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')

    def generate_relationship(self):
        return Relationship(
            self.dh_private_key,
            self.bulletin_secret
        )

    def generate_transaction(self):
        return Transaction(
            self.rid,
            self.transaction_signature,
            self.encrypted_relationship,
            self.public_key,
            self.dh_public_key,
            str(self.fee),
            self.requester_rid,
            self.requested_rid,
            self.hash,
            inputs=self.inputs,
            outputs=self.outputs,
            coinbase=self.coinbase
        )

    def generate_transaction_signature(self):
        return TU.generate_signature(self.hash)

class InvalidTransactionException(BaseException):
    pass

class InvalidTransactionSignatureException(BaseException):
    pass

class MissingInputTransactionException(BaseException):
    pass

class Transaction(object):
    def __init__(
        self,
        rid='',
        transaction_signature='',
        relationship='',
        public_key='',
        dh_public_key='',
        fee='0.1',
        requester_rid='',
        requested_rid='',
        txn_hash='',
        post_text='',
        inputs='',
        outputs='',
        coinbase=False
    ):
        self.rid = rid
        self.transaction_signature = transaction_signature
        self.relationship = relationship
        self.public_key = public_key
        self.dh_public_key = dh_public_key if dh_public_key else ''
        self.fee = str(fee)
        self.requester_rid = requester_rid if requester_rid else ''
        self.requested_rid = requested_rid if requested_rid else ''
        self.hash = txn_hash
        self.post_text = post_text
        self.inputs = inputs
        self.outputs = outputs
        self.coinbase = coinbase

    @classmethod
    def from_dict(cls, txn):
        return cls(
            transaction_signature=txn.get('id'),
            rid=txn.get('rid', ''),
            relationship=txn.get('relationship', ''),
            public_key=txn.get('public_key'),
            dh_public_key=txn.get('dh_public_key'),
            fee=txn.get('fee'),
            requester_rid=txn.get('requester_rid', ''),
            requested_rid=txn.get('requested_rid', ''),
            txn_hash=txn.get('hash', ''),
            post_text=txn.get('post_text', ''),
            inputs=[Input.from_dict(input_txn) for input_txn in txn.get('inputs', '')],
            outputs=[Output.from_dict(output_txn) for output_txn in txn.get('outputs', '')],
            coinbase=txn.get('coinbase', '')
        )

    def verify(self):
        verify_hash = self.generate_hash()

        address = P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex'))
        if verify_hash != self.hash:
            raise InvalidTransactionException("transaction is invalid")
        result = VerifyMessage(address, BitcoinMessage(self.hash, magic=''), self.transaction_signature)
        if not result:
            raise InvalidTransactionSignatureException("transaction signature did not verify")

        # verify spend
        total_input = 0
        for txn in self.inputs:
            txn_input = Transaction.from_dict(BU.get_transaction_by_id(txn.id))
            for output in txn_input.outputs:
                if str(output.to) == str(address):
                    total_input += float(output.value)

        if self.coinbase:
            return

        total_output = 0
        for txn in self.outputs:
            total_output += float(txn.value)
        total = float(total_output) + float(self.fee)
        if str(total_input) != str(total):
            raise BaseException("inputs and outputs sum must match %s, %s, %s, %s" % (total_input, float(total_output), float(self.fee), total))

    def generate_hash(self):
        inputs_concat = self.get_input_hashes()
        outputs_concat = self.get_output_hashes()
        return hashlib.sha256(
            self.dh_public_key +
            self.rid +
            self.relationship +
            str(self.fee) +
            self.requester_rid +
            self.requested_rid +
            inputs_concat +
            outputs_concat
        ).digest().encode('hex')

    def get_input_hashes(self):
        input_hashes = []
        for x in self.inputs:
            txn = BU.get_transaction_by_id(x.id, instance=True)
            if not txn:
                raise MissingInputTransactionException("This transaction is not in the blockchain.")
            input_hashes.append(str(txn.transaction_signature))

        return ''.join(sorted(input_hashes, key=lambda v: v.lower()))

    def get_output_hashes(self):
        outputs_sorted = sorted([x.to_dict() for x in self.outputs], key=lambda x: x['to'].lower())
        return ''.join([x['to']+str(float(x['value'])) for x in outputs_sorted])

    def to_dict(self):
        ret = {
            'rid': self.rid,
            'id': self.transaction_signature,
            'relationship': self.relationship,
            'public_key': self.public_key,
            'dh_public_key': self.dh_public_key,
            'fee': self.fee,
            'hash': self.hash,
            'post_text': self.post_text,
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
    def __init__(self, dh_private_key, bulletin_secret):
        self.dh_private_key = dh_private_key
        self.bulletin_secret = bulletin_secret

    def to_dict(self):
        return {
            'dh_private_key': self.dh_private_key,
            'bulletin_secret': self.bulletin_secret
        }

    def to_json(self):
        return json.dumps(self.to_dict())
