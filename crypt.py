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


class Crypt(object):  # Relationship Utilities
    def __init__(self, shared_secret):
        self.key = PBKDF2(shared_secret, 'salt', 400).read(32)

    def encrypt_consistent(self, s):
        BS = AES.block_size
        s = s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
        iv = '3443cd461efa7d334e477600f25c8bb9'.decode('hex')
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return (iv + cipher.encrypt(buffer(s))).encode('hex')

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
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        try:
            s = base64.b64decode(enc[16:])
        except:
            s = cipher.decrypt(enc[16:])
        return s[0:-ord(s[-1])]