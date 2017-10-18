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
from transactionutils import TU
from bitcoin.wallet import CBitcoinSecret
from bitcoin.signmessage import BitcoinMessage, VerifyMessage, SignMessage


class BU(object):  # Blockchain Utilities
    @classmethod
    def get_blocks(cls):
        with open('blockchain.json', 'r') as f:
            blocks = json.loads(f.read()).get('blocks')
        return blocks

    @classmethod
    def get_block_objs(cls):
        from block import Block
        from transaction import Transaction, Crypt
        with open('blockchain.json', 'r') as f:
            blocks = json.loads(f.read()).get('blocks')
        block_objs = []
        for block in blocks:
            block_objs.append(Block(
                block_index=block.get('index'),
                public_key=block.get('public_key'),
                prev_hash=block.get('prevHash'),
                nonce=block.get('nonce'),
                transactions=[Transaction(
                        transaction_signature=txn.get('id', ''),
                        rid=txn.get('rid', ''),
                        relationship=txn.get('relationship', ''),
                        public_key=txn.get('public_key', ''),
                        value=txn.get('value', ''),
                        fee=txn.get('fee', ''),
                        requester_rid=txn.get('requester_rid', ''),
                        requested_rid=txn.get('requested_rid', ''),
                        challenge_code=txn.get('challenge_code', ''),
                        answer=txn.get('answer', ''),
                        txn_hash=txn.get('hash', ''),
                        post_text=txn.get('post_text', '')
                    ) for txn in block.get('transactions')],
                block_hash=block.get('hash'),
                merkle_root=block.get('merkleRoot'),
                answer=block.get('answer', ''),
                difficulty=block.get('difficulty'),
                signature=block.get('signature')                
            ))
        return block_objs

    @classmethod
    def get_transactions(cls, raw=False):
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        transactions = []
        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                try:
                    if 'relationship' not in transaction:
                        continue
                    if not raw:
                        cipher = Crypt(cls.private_key)
                        decrypted = cipher.decrypt(transaction['relationship'])
                        relationship = json.loads(decrypted)
                        transaction['relationship'] = relationship
                    transactions.append(transaction)
                except:
                    continue
        return transactions

    @classmethod
    def get_relationships(cls):
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        relationships = []
        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                try:
                    cipher = Crypt(cls.private_key)
                    decrypted = cipher.decrypt(transaction['relationship'])
                    relationship = json.loads(decrypted)
                    relationships.append(relationship)
                except:
                    continue
        return relationships

    @classmethod
    def get_transaction_by_rid(cls, selector, rid=False, raw=False):
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        ds = TU.get_bulletin_secret()
        if not rid:
            selectors = [
                TU.hash(ds+selector),
                TU.hash(selector+ds)
            ]
        else:
            selectors = [selector, ]

        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                if transaction.get('rid') in selectors:
                    if 'relationship' in transaction:
                        if not raw:
                            try:
                                cipher = Crypt(cls.private_key)
                                decrypted = cipher.decrypt(transaction['relationship'])
                                relationship = json.loads(decrypted)
                                transaction['relationship'] = relationship
                            except:
                                continue
                    return transaction

    @classmethod
    def get_transactions_by_rid(cls, selector, rid=False, raw=False):
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        ds = TU.get_bulletin_secret()
        if not rid:
            selectors = [
                TU.hash(ds+selector),
                TU.hash(selector+ds)
            ]
        else:
            selectors = [selector, ]

        transactions = []
        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                if transaction.get('rid') in selectors:
                    if 'relationship' in transaction:
                        if not raw:
                            try:
                                cipher = Crypt(cls.private_key)
                                decrypted = cipher.decrypt(transaction['relationship'])
                                relationship = json.loads(decrypted)
                                transaction['relationship'] = relationship
                            except:
                                continue
                    transactions.append(transaction)
        return transactions

    @classmethod
    def get_bulletins(cls, bulletin_secret):
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        bulletins = []
        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                if 'post_text' in transaction:
                    try:
                        cipher = Crypt(bulletin_secret)
                        decrypted = cipher.decrypt(transaction['post_text'])
                        decrypted.decode('utf8')
                        if not decrypted:
                            continue
                        transaction['post_text'] = decrypted
                        bulletins.append(transaction)
                    except:
                        continue
        return bulletins

    @classmethod
    def get_second_degree_transactions_by_rids(cls, rids):
        if not isinstance(rids, list):
            rids = [rids, ]
        transactions = []
        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                if transaction.get('requester_rid') in rids or transaction.get('requested_rid') in rids:
                    transactions.append(transaction)
        return transactions

    @classmethod
    def generate_signature(cls, message):
        key = CBitcoinSecret(cls.private_key)
        signature = SignMessage(key, BitcoinMessage(message, magic=''))
        return signature
