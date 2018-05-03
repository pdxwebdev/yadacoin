import json
import hashlib
import os
import argparse
import qrcode
import base64

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


class TU(object):  # Transaction Utilities
    private_key = None

    @classmethod
    def hash(cls, message):
        return hashlib.sha256(message).digest().encode('hex')

    @classmethod
    def get_bulletin_secret(cls):
        cipher = Crypt(cls.private_key)
        return hashlib.sha256(cipher.encrypt_consistent(cls.private_key)).digest().encode('hex')

    @classmethod
    def generate_deterministic_signature(cls):
        key = PrivateKey.from_hex(cls.private_key)
        signature = key.sign(cls.private_key)
        return hashlib.sha256(base64.b64encode(signature)).digest().encode('hex')

    @classmethod
    def generate_signature(cls, message):
        key = PrivateKey.from_hex(cls.private_key)
        signature = key.sign(message)
        return base64.b64encode(signature)

    @classmethod
    def save(cls, items):
        if not isinstance(items, list):
            items = [items.to_dict(), ]
        else:
            items = [item.to_dict() for item in items]

        for item in items:
            cls.miner_transactions.insert(item)