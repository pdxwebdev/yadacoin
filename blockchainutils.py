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
from bson.son import SON


class BU(object):  # Blockchain Utilities
    collection = None
    @classmethod
    def get_blocks(cls):
        blocks = cls.collection.find({}, {'_id': 0}).sort([('index',1)])
        return blocks

    @classmethod
    def get_latest_block(cls):
        res = cls.collection.find({}, {'_id': 0}).limit(1).sort([('index',-1)])
        if res.count():
            return res[0]
        else:
            return {}

    @classmethod
    def get_block_by_index(cls, index):
        res = cls.collection.find({'index': index}, {'_id': 0})
        if res.count():
            return res[0]

    @classmethod
    def get_block_objs(cls):
        from block import Block
        from transaction import Transaction, Input, Crypt
        blocks = cls.get_blocks()
        block_objs = []
        for block in blocks:
            block_objs.append(Block.from_dict(block))
        return block_objs
    #  miner -> person 1 -> person 2
    #  | mine coin | requester_rid and rid is miner.bulletin_secret + miner.bulletin_secret | 
    @classmethod
    def get_wallet_balances(cls):
        unspent_transactions = cls.get_unspent_transactions()
        balances = {}
        for idx, txns in unspent_transactions.items():
            for txn in txns:
                if idx not in balances:
                    balances[idx] = 0
                for output in txn['outputs']:
                    if output['to'] == idx:
                        balances[idx] += float(output['value'])
        return balances

    @classmethod
    def get_wallet_balance(cls, address):
        balance = cls.get_wallet_balances().get(address)
        if balance:
            return balance
        else:
            return 0

    @classmethod
    def get_unspent_transactions(cls):
        from block import Block
        from transaction import Transaction, Input, Crypt
        blocks = cls.get_blocks()
        unspent_transactions = {}
        for block in blocks:
            for txn in block.get('transactions'):
                transaction = Transaction.from_dict(txn)
                for output in transaction.outputs:
                    if output.to not in unspent_transactions:
                        unspent_transactions[output.to] = {}
                    unspent_transactions[output.to][transaction.transaction_signature] = transaction.to_dict()
        for block in blocks:
            for txn in block.get('transactions'):
                transaction = Transaction.from_dict(txn)
                address = str(P2PKHBitcoinAddress.from_pubkey(transaction.public_key.decode('hex')))
                for input_txn in transaction.inputs:
                    try:
                        del unspent_transactions[address][input_txn.id]
                    except KeyError:
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
        return cls.get_unspent_transactions().get(address, [])

    @classmethod
    def get_transactions(cls, raw=False):
        from block import Block
        from transaction import Transaction
        from crypt import Crypt
        transactions = []
        for block in cls.collection.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}}):
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

        for block in cls.collection.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}}):
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
        blocks = cls.collection.find({"transactions.rid": {"$in": selectors}, "transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}})
        for block in blocks:
            for transaction in block.get('transactions'):
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
        for block in cls.collection.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}}):
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
        for block in cls.collection.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}}):
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
    def get_transaction_by_id(cls, id, instance=False):
        from transaction import Transaction, Input, Crypt
        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                if transaction.get('id') == id:
                    if instance:
                        return Transaction.from_dict(transaction)
                    else:
                        return transaction

    @classmethod
    def get_block_reward(cls, block=None):
        try:
            with open('block_rewards.json', 'r') as f:
                block_rewards = json.loads(f.read())
        except:
            raise BaseException("Block reward file not found")

        latest_block = BU.get_latest_block()
        if latest_block:
            block_count = (latest_block['index'] + 1)
        else:
            block_count = 0


        for t, block_reward in enumerate(block_rewards):
            if block:
                if block.index >= int(block_reward['block']) and block.index < int(block_rewards[t+1]['block']):
                    break
            else:
                if block_count == 0:
                    break
                if block_count >= int(block_reward['block']) and block_count < int(block_rewards[t+1]['block']):
                    break

        return float(block_reward['reward'])

    @classmethod
    def check_double_spend(cls, transaction_obj):
        double_spends = []
        for txn_input in transaction_obj.inputs:
            res = BU.collection.aggregate([
                {"$unwind": "$transactions" },
                {
                    "$project": {
                        "_id": 0,
                        "txn": "$transactions"
                    }
                },
                {"$unwind": "$txn.inputs" },
                {
                    "$project": {
                        "_id": 0,
                        "input_id": "$txn.inputs.id",
                        "public_key": "$txn.public_key"
                    }
                },
                {"$sort": SON([("count", -1), ("input_id", -1)])},
                {"$match":
                    {
                        "public_key": transaction_obj.public_key,
                        "input_id": txn_input.id
                    }
                }
            ])
            res_consensus = BU.consensus.aggregate([
                {"$unwind": "$block.transactions" },
                {
                    "$project": {
                        "_id": 0,
                        "txn": "$block.transactions"
                    }
                },
                {"$unwind": "$txn.inputs" },
                {
                    "$project": {
                        "_id": 0,
                        "input_id": "$txn.inputs.id",
                        "public_key": "$txn.public_key"
                    }
                },
                {"$sort": SON([("count", -1), ("input_id", -1)])},
                {"$match":
                    {
                        "public_key": transaction_obj.public_key,
                        "input_id": txn_input.id
                    }
                }
            ])
            double_spends.extend([x for x in res] + [x for x in res_consensus])
        return double_spends
