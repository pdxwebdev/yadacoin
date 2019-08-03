import hashlib
import base64
import random
import sys
# from binascii import unhexlify
from coincurve.keys import PrivateKey
from coincurve._libsecp256k1 import ffi
# from eccsnacks.curve25519 import scalarmult
from bitcoin.wallet import P2PKHBitcoinAddress


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
        bulletin_secrets = sorted([str(config.bulletin_secret), str(bulletin_secret)], key=str.lower)
        return hashlib.sha256((str(bulletin_secrets[0]) + str(bulletin_secrets[1])).encode('utf-8')).digest().hex()
    
    @classmethod
    def check_rid_txn_fully_spent(cls, config, rid_txn, address, index):
        from yadacoin.transaction import Transaction
        rid_txn = Transaction.from_dict(index, rid_txn)
        spending_txn = rid_txn.used_as_input(rid_txn.transaction_signature)
        if spending_txn:
            for output in spending_txn['outputs']:
                if output['to'] == address and output['value'] == 0:
                    return True # now we can create a duplicate relationship
            x = config.BU.get_transaction_by_id(spending_txn['id'], instance=True)
            result = cls.check_rid_txn_fully_spent(config, x.to_dict(), address, index)
            if result:
                return True
            return False
        else:
            return False # hasn't been spent to zero yet
