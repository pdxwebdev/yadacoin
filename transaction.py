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
        challenge_code='',
        public_key='',
        private_key='',
        to='',
        inputs='',
        outputs='',
        answer='',
        coinbase=False
    ):
        self.bulletin_secret = bulletin_secret
        self.challenge_code = challenge_code
        self.requester_rid = requester_rid
        self.requested_rid = requested_rid
        self.public_key = public_key
        self.private_key = private_key
        self.value = value
        self.fee = fee
        self.shared_secret = shared_secret
        self.to = to
        self.answer = answer
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
            self.rid +
            self.encrypted_relationship +
            str(self.fee) +
            self.requester_rid +
            self.requested_rid +
            self.challenge_code +
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
            self.shared_secret,
            self.bulletin_secret
        )

    def generate_transaction(self):
        return Transaction(
            self.rid,
            self.transaction_signature,
            self.encrypted_relationship,
            self.public_key,
            str(self.fee),
            self.requester_rid,
            self.requested_rid,
            self.challenge_code,
            self.hash,
            inputs=self.inputs,
            outputs=self.outputs,
            answer=self.answer,
            coinbase=self.coinbase
        )

    def generate_transaction_signature(self):
        return TU.generate_signature(self.hash)


class Transaction(object):
    def __init__(
        self,
        rid='',
        transaction_signature='',
        relationship='',
        public_key='',
        fee='0.1',
        requester_rid='',
        requested_rid='',
        challenge_code='',
        txn_hash='',
        answer='',
        post_text='',
        inputs='',
        outputs='',
        coinbase=False
    ):
        self.rid = rid
        self.transaction_signature = transaction_signature
        self.relationship = relationship
        self.public_key = public_key
        self.fee = str(fee)
        self.requester_rid = requester_rid if requester_rid else ''
        self.requested_rid = requested_rid if requested_rid else ''
        self.challenge_code = challenge_code if challenge_code else ''
        self.hash = txn_hash
        self.answer = answer if answer else ''
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
            fee=txn.get('fee'),
            requester_rid=txn.get('requester_rid', ''),
            requested_rid=txn.get('requested_rid', ''),
            challenge_code=txn.get('challenge_code', ''),
            answer=txn.get('answer', ''),
            txn_hash=txn.get('hash', ''),
            post_text=txn.get('post_text', ''),
            inputs=[Input.from_dict(input_txn) for input_txn in txn.get('inputs', '')],
            outputs=[Output.from_dict(output_txn) for output_txn in txn.get('outputs', '')],
            coinbase=txn.get('coinbase', '')
        )

    def verify(self):
        inputs_concat = self.get_input_hashes()
        outputs_concat = self.get_output_hashes()
        verify_hash = hashlib.sha256(
            self.rid +
            self.relationship +
            str(self.fee) +
            self.requester_rid +
            self.requested_rid +
            self.challenge_code +
            self.answer +
            self.post_text +
            inputs_concat +
            outputs_concat
        ).digest().encode('hex')

        address = P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex'))
        if verify_hash != self.hash:
            raise BaseException("transaction is invalid")
        result = VerifyMessage(address, BitcoinMessage(self.hash, magic=''), self.transaction_signature)
        if not result:
            raise BaseException("transaction signature did not verify")

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
        print total_input, total_output, self.fee
        if float(total_input) != (float(total_output) + float(self.fee)):
            raise BaseException("inputs and outputs sum must match")

    def get_input_hashes(self):
        input_hashes = []
        for x in self.inputs:
            txn = BU.get_transaction_by_id(x.id, instance=True)
            input_hashes.append(str(txn.transaction_signature))

        return ''.join(sorted(input_hashes, key=str.lower))

    def get_output_hashes(self):
        outputs_sorted = sorted([x.to_dict() for x in self.outputs], key=lambda x: x['to'])
        return ''.join([x['to']+str(float(x['value'])) for x in outputs_sorted])

    def to_dict(self):
        ret = {
            'rid': self.rid,
            'id': self.transaction_signature,
            'relationship': self.relationship,
            'public_key': self.public_key,
            'fee': self.fee,
            'hash': self.hash,
            'post_text': self.post_text,
            'inputs': [x.to_dict() for x in self.inputs],
            'outputs': [x.to_dict() for x in self.outputs]
        }
        if self.requester_rid:
            ret['requester_rid'] = self.requester_rid
        if self.requested_rid:
            ret['requested_rid'] = self.requested_rid
        if self.challenge_code:
            ret['challenge_code'] = self.challenge_code
        if self.answer:
            ret['answer'] = self.answer
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
    def __init__(self, shared_secret, bulletin_secret):
        self.shared_secret = shared_secret
        self.bulletin_secret = bulletin_secret

    def to_dict(self):
        return {
            'shared_secret': self.shared_secret,
            'bulletin_secret': self.bulletin_secret
        }

    def to_json(self):
        return json.dumps(self.to_dict())
