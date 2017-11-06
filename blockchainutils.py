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
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress


class BU(object):  # Blockchain Utilities
    @classmethod
    def get_blocks(cls):
        with open('blockchain.json', 'r') as f:
            blocks = json.loads(f.read()).get('blocks')
        return blocks

    @classmethod
    def get_block_by_id(cls, id):
        for block in cls.get_blocks():
            if block.get('id') == id:
                return block

    @classmethod
    def get_block_objs(cls):
        from block import Block
        from transaction import Transaction, Input, Crypt
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
                        post_text=txn.get('post_text', ''),
                        to=txn.get('to', ''),
                        inputs=[Input(
                            transaction_signature=input_txn.get('id', ''),
                            rid=input_txn.get('rid', ''),
                            relationship=input_txn.get('relationship', ''),
                            public_key=input_txn.get('public_key', ''),
                            value=input_txn.get('value', ''),
                            fee=input_txn.get('fee', ''),
                            requester_rid=input_txn.get('requester_rid', ''),
                            requested_rid=input_txn.get('requested_rid', ''),
                            challenge_code=input_txn.get('challenge_code', ''),
                            answer=input_txn.get('answer', ''),
                            txn_hash=input_txn.get('hash', ''),
                            post_text=input_txn.get('post_text', ''),
                            to=input_txn.get('to', ''),
                            inputs=input_txn.get('inputs', ''),
                            coinbase=True
                        ) for input_txn in txn.get('inputs', '')],
                        coinbase=True if str(P2PKHBitcoinAddress.from_pubkey(block.get('public_key').decode('hex'))) == txn.get('to', '') else False
                    ) for i, txn in enumerate(block.get('transactions'))],
                block_hash=block.get('hash'),
                merkle_root=block.get('merkleRoot'),
                answer=block.get('answer', ''),
                difficulty=block.get('difficulty'),
                signature=block.get('signature')                
            ))
        return block_objs
    #  miner -> person 1 -> person 2
    #  | mine coin | requester_rid and rid is miner.bulletin_secret + miner.bulletin_secret | 
    @classmethod
    def get_wallet_balances(cls):
        unspent_transactions = cls.get_unspent_transactions()
        balances = {}
        for idx, txns in unspent_transactions.items():
            for txn in txns:
                print 'idx:', idx
                if idx not in balances:
                    balances[idx] = 0
                balances[idx] += float(txn['value'])
        return balances

    @classmethod
    def get_wallet_balance(cls, address):
        return cls.get_wallet_balances().get(address)

    @classmethod
    def get_unspent_transactions(cls):
        from block import Block
        from transaction import Transaction, Input, Crypt
        with open('blockchain.json', 'r') as f:
            blocks = json.loads(f.read()).get('blocks')
        unspent_transactions = {}
        for block in blocks:
            for txn in block.get('transactions'):
                transaction = Transaction(
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
                    post_text=txn.get('post_text', ''),
                    to=txn.get('to', ''),
                    inputs=[Input(
                        transaction_signature=input_txn.get('id', ''),
                        rid=input_txn.get('rid', ''),
                        relationship=input_txn.get('relationship', ''),
                        public_key=input_txn.get('public_key', ''),
                        value=input_txn.get('value', ''),
                        fee=input_txn.get('fee', ''),
                        requester_rid=input_txn.get('requester_rid', ''),
                        requested_rid=input_txn.get('requested_rid', ''),
                        challenge_code=input_txn.get('challenge_code', ''),
                        answer=input_txn.get('answer', ''),
                        txn_hash=input_txn.get('hash', ''),
                        post_text=input_txn.get('post_text', ''),
                        to=input_txn.get('to', ''),
                        inputs=input_txn.get('inputs', ''),
                        coinbase=True
                    ) for v, input_txn in enumerate(txn.get('inputs', ''))],
                    coinbase=True
                )
                if transaction.to not in unspent_transactions:
                    unspent_transactions[transaction.to] = {}
                unspent_transactions[transaction.to][transaction.transaction_signature] = transaction.toDict()
                for spend in transaction.inputs:
                    try:
                        del unspent_transactions[spend.to][spend.id]
                    except:
                        pass
        utxn = {}
        for i, x in unspent_transactions.items():
            for j, y in x.items():
                if i not in utxn:
                    utxn[i] = []
                utxn[i].append(y)

        return utxn

    @classmethod
    def get_wallet_unspent_transactions(cls, address):
        return cls.get_unspent_transactions().get(address)

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
            if not isinstance(selector, list):
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
            if not isinstance(selector, list):
                selectors = [selector, ]
            else:
                selectors = selector

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

    @classmethod
    def get_transaction_by_id(cls, id):
        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                if transaction.get('id') == id:
                    return transaction
