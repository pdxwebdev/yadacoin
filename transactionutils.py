import json
import hashlib
import os
import argparse
import qrcode
import base64

from io import BytesIO
from uuid import uuid4
from ecdsa import NIST384p, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2


class TU(object):  # Transaction Utilities
    private_key = None

    @classmethod
    def hash(cls, message):
        return hashlib.sha256(message).digest().encode('hex')

    @classmethod
    def generate_deterministic_signature(cls):
        sk = SigningKey.from_string(cls.private_key.decode('hex'))
        signature = sk.sign_deterministic(hashlib.sha256(cls.private_key).digest().encode('hex'))
        return hashlib.sha256(signature.encode('hex')).digest().encode('hex')

    @classmethod
    def generate_signature(cls, message):
        sk = SigningKey.from_string(cls.private_key.decode('hex'))
        signature = sk.sign(message)
        return signature.encode('hex')

    @classmethod
    def save(cls, items):
        if not isinstance(items, list):
            items = [items.toDict(), ]
        else:
            items = [item.toDict() for item in items]

        with open('miner_transactions.json', 'a+') as f:
            try:
                existing = json.loads(f.read())
            except:
                existing = []
            existing.extend(items)
            f.seek(0)
            f.truncate()
            f.write(json.dumps(existing, indent=4))
            f.truncate()