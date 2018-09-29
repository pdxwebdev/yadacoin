import json
import hashlib
import os
import argparse
import qrcode
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
        rids = sorted([str(Config.get_bulletin_secret()), str(bulletin_secret)], key=str.lower)
        return hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')

    @classmethod
    def get_shared_secret_by_rid(cls, rid):
        from blockchainutils import BU
        shared_secrets = {}
        txns = BU.get_transactions_by_rid(rid, rid=True)
        for txn in txns:
            if txn['public_key'] == Config.public_key and txn['relationship']['dh_private_key']:
                shared_secrets['dh_private_key'] = txn['relationship']['dh_private_key']
        if 'dh_private_key' not in shared_secrets:
            return None
        txns = BU.get_transactions_by_rid(rid, rid=True, raw=True)
        for txn in txns:
            if txn['public_key'] != Config.public_key and txn['dh_public_key']:
                shared_secrets['dh_public_key'] = txn['dh_public_key']
        if 'dh_public_key' not in shared_secrets:
            return None
        return scalarmult(shared_secrets['dh_private_key'].decode('hex'), shared_secrets['dh_public_key'].decode('hex'))

    @classmethod
    def save(cls, items):
        Mongo.init()
        if not isinstance(items, list):
            items = [items.to_dict(), ]
        else:
            items = [item.to_dict() for item in items]

        for item in items:
            Mongo.db.miner_transactions.insert(item)