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
from transactionutils import TU

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
        private_key=''
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
            str(self.value) +
            str(self.fee) +
            self.requester_rid +
            self.requested_rid +
            self.challenge_code
        ).digest().encode('hex')
        self.transaction_signature = self.generate_transaction_signature()
        self.transaction = self.generate_transaction()

    def generate_rid(self):
        my_bulletin_secret = TU.generate_deterministic_signature()
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
            str(self.value),
            str(self.fee),
            self.requester_rid,
            self.requested_rid,
            self.challenge_code,
            self.hash
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
        value='1',
        fee='0.1',
        requester_rid='',
        requested_rid='',
        challenge_code='',
        txn_hash='',
        answer=''
    ):
        self.rid = rid
        self.transaction_signature = transaction_signature
        self.relationship = relationship
        self.public_key = public_key
        self.value = str(value)
        self.fee = str(fee)
        self.requester_rid = requester_rid if requester_rid else ''
        self.requested_rid = requested_rid if requested_rid else ''
        self.challenge_code = challenge_code if challenge_code else ''
        self.hash = txn_hash
        self.answer = answer
        self.verify()

    def verify(self):
        verify_hash = hashlib.sha256(
            self.rid +
            self.relationship +
            str(self.value) +
            str(self.fee) +
            self.requester_rid +
            self.requested_rid +
            self.challenge_code +
            self.answer
        ).digest().encode('hex')

        if verify_hash != self.hash:
            raise BaseException("transaction is invalid")
        print 'pubkey',self.public_key
        if not VerifyMessage(P2PKHBitcoinAddress.from_pubkey(self.public_key.decode('hex')), BitcoinMessage(self.hash, magic=''), self.transaction_signature):
            raise BaseException("transaction signature is invalid")

    def toDict(self):
        ret = {
            'rid': self.rid,
            'id': self.transaction_signature,
            'relationship': self.relationship,
            'public_key': self.public_key,
            'value': self.value,
            'fee': self.fee,
            'hash': self.hash
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

    def toJson(self):
        return json.dumps(self.toDict(), indent=4)


class Relationship(object):
    def __init__(self, shared_secret, bulletin_secret):
        self.shared_secret = shared_secret
        self.bulletin_secret = bulletin_secret

    def toDict(self):
        return {
            'shared_secret': self.shared_secret,
            'bulletin_secret': self.bulletin_secret
        }

    def to_json(self):
        return json.dumps(self.toDict())


class Crypt(object):  # Relationship Utilities
    def __init__(self, shared_secret):
        self.key = PBKDF2(shared_secret, 'salt', 400).read(32)

    def encrypt(self, s):
        from Crypto import Random
        BS = AES.block_size
        iv = Random.new().read(BS)
        s = s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return (iv + cipher.encrypt(buffer(s))).encode('hex')

    def decrypt(self, enc):
        enc = enc.decode("hex")
        iv = enc[:16]
        enc = enc[16:]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        s = cipher.decrypt(enc)
        return s[0:-ord(s[-1])]