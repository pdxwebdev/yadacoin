import hashlib
import base64
import random
import sys

from coincurve.keys import PrivateKey
from coincurve._libsecp256k1 import ffi
from eccsnacks.curve25519 import scalarmult


class TU(object):  # Transaction Utilities

    @classmethod
    def hash(cls, message):
        return hashlib.sha256(message).digest().hex()

    @classmethod
    def generate_deterministic_signature(cls, config, message:str, private_key=None):
        if not private_key:
            private_key = config.private_key
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message.encode('utf-8'))
        return base64.b64encode(signature).decode('utf-8')

    @classmethod
    def generate_signature_with_private_key(cls, private_key, message):
        x = ffi.new('long *')
        # TODO : no maxint in python3
        x[0] = random.SystemRandom().randint(0, sys.maxint)
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message, custom_nonce=(ffi.NULL, x))
        return base64.b64encode(signature).decode('utf-8')

    @classmethod
    def generate_signature(cls, message, private_key):
        x = ffi.new('long *')
        # TODO : no maxint in python3
        x[0] = random.SystemRandom().randint(0, sys.maxint)
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message, custom_nonce=(ffi.NULL, x))
        return base64.b64encode(signature).decode('utf-8')

    @classmethod
    def generate_rid(cls, config, bulletin_secret):
        if config.bulletin_secret == bulletin_secret:
            raise Exception('bulletin secrets are identical. do you love yourself so much that you want a relationship on the blockchain?')
        bulletin_secrets = sorted([str(config.bulletin_secret), str(bulletin_secret)], key=str.lower)
        return hashlib.sha256((str(bulletin_secrets[0]) + str(bulletin_secrets[1])).encode('utf-8')).digest().hex()

    @classmethod
    def get_shared_secrets_by_rid(cls, config, mongo, rid):
        from yadacoin.blockchainutils import BU
        shared_secrets = []
        dh_public_keys = []
        dh_private_keys = []
        txns = BU.get_transactions_by_rid(config, mongo, rid, config.bulletin_secret, rid=True)
        for txn in txns:
            if str(txn['public_key']) == str(config.public_key) and txn['relationship']['dh_private_key']:
                dh_private_keys.append(txn['relationship']['dh_private_key'])
        txns = BU.get_transactions_by_rid(config, mongo, rid, config.bulletin_secret, rid=True, raw=True)
        for txn in txns:
            if str(txn['public_key']) != str(config.public_key) and txn['dh_public_key']:
                dh_public_keys.append(txn['dh_public_key'])
        for dh_public_key in dh_public_keys:
            for dh_private_key in dh_private_keys:
                shared_secrets.append(scalarmult(bytes.fromhex(dh_private_key), bytes.fromhex(dh_public_key)))
        return shared_secrets

    @classmethod
    def save(cls, config, mongo, items):
        if not isinstance(items, list):
            items = [items.to_dict(), ]
        else:
            items = [item.to_dict() for item in items]

        for item in items:
            mongo.db.miner_transactions.insert(item)