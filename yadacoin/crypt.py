import hashlib
import base64

from Crypto.Cipher import AES
from pbkdf2 import PBKDF2


class Crypt(object):  # Relationship Utilities
    def __init__(self, shared_secret, shared=False):
        self.key = PBKDF2(hashlib.sha256(shared_secret.encode('utf-8')).hexdigest(), 'salt', 400).read(32)

    def encrypt_consistent(self, s):
        BS = AES.block_size
        s = s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
        iv = bytes.fromhex('3443cd461efa7d334e477600f25c8bb9')
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return (iv + cipher.encrypt(bytes.fromhex(s))).hex()

    def encrypt(self, s):
        from Crypto import Random
        BS = AES.block_size
        iv = Random.new().read(BS)
        s = s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return (iv + cipher.encrypt(s)).hex()

    def shared_encrypt(self, s):
        s = base64.b64encode(s)
        from Crypto import Random
        BS = AES.block_size
        iv = Random.new().read(BS)
        s = s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return (iv + cipher.encrypt(s)).hex()

    def decrypt(self, enc):
        enc = bytes.fromhex(enc)
        iv = enc[:16]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        s = cipher.decrypt(enc[16:])
        return s[0:-ord(s.decode('latin1')[-1])]

    def shared_decrypt(self, enc):
        enc =  bytes.fromhex(enc)
        iv = enc[:16]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        s = cipher.decrypt(enc[16:])
        return base64.b64decode(s[0:-ord(s.decode('latin1')[-1])])