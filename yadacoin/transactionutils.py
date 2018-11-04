import json
import hashlib
import os
import base64
import time
import random
import sys

from io import BytesIO
from uuid import uuid4
from ecdsa import SECP256k1, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from bitcoin.wallet import CBitcoinSecret
from bitcoin.signmessage import BitcoinMessage, VerifyMessage, SignMessage
from crypt import Crypt
from coincurve.keys import PrivateKey
from coincurve._libsecp256k1 import ffi
from eccsnacks.curve25519 import scalarmult, scalarmult_base
from config import Config
from mongo import Mongo


class TU(object):  # Transaction Utilities

    @classmethod
    def hash(cls, message):
        return hashlib.sha256(message).digest().encode('hex')

    @classmethod
    def generate_deterministic_signature(cls, message):
        key = PrivateKey.from_hex(Config.private_key)
        signature = key.sign(message)
        return base64.b64encode(signature)

    @classmethod
    def generate_signature(cls, message):
        x = ffi.new('long *')
        x[0] = random.SystemRandom().randint(0, sys.maxint)
        key = PrivateKey.from_hex(Config.private_key)
        signature = key.sign(message, custom_nonce=(ffi.NULL, x))
        return base64.b64encode(signature)

    @classmethod
    def generate_rid(cls, bulletin_secret):
        if Config.get_bulletin_secret() == bulletin_secret:
            raise BaseException('bulletin secrets are identical. do you love yourself so much that you want a relationship on the blockchain?')
        bulletin_secrets = sorted([str(Config.get_bulletin_secret()), str(bulletin_secret)], key=str.lower)
        return hashlib.sha256(str(bulletin_secrets[0]) + str(bulletin_secrets[1])).digest().encode('hex')

    @classmethod
    def get_shared_secrets_by_rid(cls, rid):
        from blockchainutils import BU
        shared_secrets = []
        dh_public_keys = []
        dh_private_keys = []
        txns = BU.get_transactions_by_rid(rid, rid=True)
        for txn in txns:
            if str(txn['public_key']) == str(Config.public_key) and txn['relationship']['dh_private_key']:
                dh_private_keys.append(txn['relationship']['dh_private_key'])
        txns = BU.get_transactions_by_rid(rid, rid=True, raw=True)
        for txn in txns:
            if str(txn['public_key']) != str(Config.public_key) and txn['dh_public_key']:
                dh_public_keys.append(txn['dh_public_key'])
        for dh_public_key in dh_public_keys:
            for dh_private_key in dh_private_keys:
                shared_secrets.append(scalarmult(dh_private_key.decode('hex'), dh_public_key.decode('hex')))
        return shared_secrets

    @classmethod
    def save(cls, items):
        Mongo.init()
        if not isinstance(items, list):
            items = [items.to_dict(), ]
        else:
            items = [item.to_dict() for item in items]

        for item in items:
            Mongo.db.miner_transactions.insert(item)