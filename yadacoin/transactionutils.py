import hashlib
import base64
import random
import sys
# from binascii import unhexlify
from coincurve.keys import PrivateKey
from coincurve._libsecp256k1 import ffi
# from eccsnacks.curve25519 import scalarmult


class TU(object):  # Transaction Utilities

    @classmethod
    def hash(cls, message):
        return hashlib.sha256(message.encode('utf-8')).digest().hex()

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
        x[0] = random.SystemRandom().randint(0, sys.maxsize)
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message.encode('utf-8'), custom_nonce=(ffi.NULL, x))
        return base64.b64encode(signature).decode('utf-8')

    @classmethod
    def generate_signature(cls, message, private_key):
        x = ffi.new('long *')
        x[0] = random.SystemRandom().randint(0, sys.maxsize)
        key = PrivateKey.from_hex(private_key)
        signature = key.sign(message.encode('utf-8'), custom_nonce=(ffi.NULL, x))
        return base64.b64encode(signature).decode('utf-8')

    @classmethod
    def generate_rid(cls, config, bulletin_secret):
        if config.bulletin_secret == bulletin_secret:
            raise Exception('bulletin secrets are identical. do you love yourself so much that you want a relationship on the blockchain?')
        bulletin_secrets = sorted([str(config.bulletin_secret), str(bulletin_secret)], key=str.lower)
        return hashlib.sha256((str(bulletin_secrets[0]) + str(bulletin_secrets[1])).encode('utf-8')).digest().hex()
