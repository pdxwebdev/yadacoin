import json
import hashlib
import base64
import time
import binascii
import pyrx

from sys import exc_info
from os import path
from decimal import Decimal, getcontext
from bitcoin.signmessage import BitcoinMessage, VerifyMessage
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve.utils import verify_signature
from logging import getLogger

from yadacoin.core.chain import CHAIN
import yadacoin.core.config
from yadacoin.core.transaction import (
    Transaction,
    NotEnoughMoneyException,
    InvalidTransactionException,
    MissingInputTransactionException,
    InvalidTransactionSignatureException
)
from yadacoin.core.transactionutils import TU
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.config import get_config


def quantize_eight(value):
    value = Decimal(value)
    value = value.quantize(Decimal('0.00000000'))
    return value


class CoinbaseRule1(Exception):
    pass

class CoinbaseRule2(Exception):
    pass

class CoinbaseRule3(Exception):
    pass

class CoinbaseRule4(Exception):
    pass

class RelationshipRule1(Exception):
    pass

class RelationshipRule2(Exception):
    pass

class FastGraphRule1(Exception):
    pass

class FastGraphRule2(Exception):
    pass

class ExternalInputSpentException(Exception):
    pass


class Block(object):

    # Memory optimization
    __slots__ = ('app_log', 'config', 'mongo', 'version', 'time', 'index', 'prev_hash', 'nonce', 'transactions', 'txn_hashes',
                 'merkle_root', 'verify_merkle_root','hash', 'public_key', 'signature', 'special_min', 'target',
                 'special_target', 'header')
    
    @classmethod
    async def init_async(
        cls,
        version=1,
        block_time=0,
        block_index=-1,
        prev_hash='',
        nonce:str='',
        transactions=None,
        block_hash='',
        merkle_root='',
        public_key='',
        signature='',
        special_min: bool=False,
        header= '',
        target: int=0,
        special_target: int=0
    ):
        self = cls()
        self.config = get_config()
        self.app_log = getLogger('tornado.application')
        self.version = version
        self.time = int(block_time)
        self.index = block_index
        self.prev_hash = prev_hash
        self.nonce = nonce
        self.transactions = transactions or []
        # txn_hashes = self.get_transaction_hashes()
        # self.set_merkle_root(txn_hashes)
        self.merkle_root = merkle_root
        self.verify_merkle_root = ''
        self.hash = block_hash
        self.public_key = public_key
        self.signature = signature
        self.special_min = special_min
        self.target = target
        self.special_target = special_target
        if target==0:
            # Same call as in new block check - but there's a circular reference here.
            latest_block = LatestBlock.block
            if not latest_block:
                self.target = CHAIN.MAX_TARGET
            else:
                if self.index >= CHAIN.FORK_10_MIN_BLOCK:
                    self.target = await CHAIN.get_target_10min(self.index, latest_block, self)
                else:
                    self.target = await CHAIN.get_target(self.index, latest_block, self)
            self.special_target = self.target
            # TODO: do we need recalc special target here if special min?
        self.header = header
        return self

    async def copy(self):
        return await Block.from_json(self.to_json())

    @classmethod
    async def generate(
        cls,
        transactions=None,
        public_key=None,
        private_key=None,
        force_version=None,
        index=0,
        force_time=None,
        prev_hash=None,
        nonce=None,
        target=0
    ):
        config = get_config()
        app_log = getLogger("tornado.application")
        if force_version is None:
            version = CHAIN.get_version_for_height(index)
        else:
            version = force_version
        if force_time:
            xtime = int(force_time)
        else:
            xtime = int(time.time())
        index = int(index)
        if index == 0:
            prev_hash = ''
        elif prev_hash is None and index != 0:
            prev_hash = LatestBlock.block.hash
        transactions = transactions or []

        transaction_objs = []
        fee_sum = 0.0
        used_sigs = []
        used_inputs = {}
        for txn in transactions:
            try:
                if isinstance(txn, Transaction):
                    transaction_obj = txn
                else:
                    transaction_obj = Transaction.from_dict(txn)

                if transaction_obj.transaction_signature in used_sigs:
                    print('duplicate transaction found and removed')
                    continue

                await transaction_obj.verify()
                used_sigs.append(transaction_obj.transaction_signature)
            except:
                raise InvalidTransactionException("invalid transactions")
            try:
                if int(index) > CHAIN.CHECK_TIME_FROM and (int(transaction_obj.time) > int(xtime) + CHAIN.TIME_TOLERANCE):
                    config.mongo.db.miner_transactions.remove({'id': transaction_obj.transaction_signature}, multi=True)
                    app_log.debug("Block embeds txn too far in the future {} {}".format(xtime, transaction_obj.time))
                    continue
                
                if transaction_obj.inputs:
                    failed = False
                    used_ids_in_this_txn = []
                    for x in transaction_obj.inputs:
                        if config.BU.is_input_spent(x.id, transaction_obj.public_key):
                            failed = True
                        if x.id in used_ids_in_this_txn:
                            failed = True
                        if (x.id, transaction_obj.public_key) in used_inputs:
                            failed = True
                        used_inputs[(x.id, transaction_obj.public_key)] = transaction_obj
                        used_ids_in_this_txn.append(x.id)
                    if failed:
                        continue

                transaction_objs.append(transaction_obj)

                fee_sum += float(transaction_obj.fee)
            except Exception as e:
                await config.mongo.async_db.miner_transactions.delete_many({'id': transaction_obj.transaction_signature})
                config.app_log.debug('Exception {}'.format(e))
                continue

        block_reward = CHAIN.get_block_reward(index)
        coinbase_txn = await Transaction.generate(
            public_key=public_key,
            private_key=private_key,
            outputs=[{
                'value': block_reward + float(fee_sum),
                'to': str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
            }],
            coinbase=True
        )
        transaction_objs.append(coinbase_txn)

        transactions = transaction_objs
        block = await cls.init_async(
            version=version,
            block_time=xtime,
            block_index=index,
            prev_hash=prev_hash,
            transactions=transactions,
            public_key=public_key,
            target=target
        )
        txn_hashes = block.get_transaction_hashes()
        block.set_merkle_root(txn_hashes)
        block.target = target
        block.header = block.generate_header()
        if nonce:
            block.nonce = str(nonce)
            block.hash = block.generate_hash_from_header(
                block.index,
                block.header,
                str(block.nonce)
            )
            block.signature = TU.generate_signature(block.hash, private_key)
        return block

    def little_hash(self):
        little_hex = bytearray.fromhex(self.hash)
        little_hex.reverse()

        str_little = ''.join(format(x, '02x') for x in little_hex)

        return str_little

    def generate_header(self):
        if int(self.version) < 3:
            return str(self.version) + \
                str(self.time) + \
                self.public_key + \
                str(self.index) + \
                self.prev_hash + \
                '{nonce}' + \
                str(self.special_min) + \
                str(self.target) + \
                self.merkle_root
        else:
            # version 3 block do not contain special_min anymore and have target as 64 hex string
            # print("target", block.target)
            # TODO: somewhere, target is calc with a / and result is float instead of int.
            return str(self.version) + \
                   str(self.time) + \
                   self.public_key + \
                   str(self.index) + \
                   self.prev_hash + \
                   '{nonce}' + \
                   hex(int(self.target))[2:].rjust(64, '0') + \
                   self.merkle_root

    def set_merkle_root(self, txn_hashes):
        self.merkle_root = self.get_merkle_root(txn_hashes)

    def get_merkle_root(self, txn_hashes):
        hashes = []
        for i in range(0, len(txn_hashes), 2):
            txn1 = txn_hashes[i]
            try:
                txn2 = txn_hashes[i+1]
            except:
                txn2 = ''
            hashes.append(hashlib.sha256((txn1+txn2).encode('utf-8')).digest().hex())
        if len(hashes) > 1:
            return self.get_merkle_root(hashes)
        else:
            return hashes[0]

    @classmethod
    async def from_dict(cls, block):
        transactions = []
        for txn in block.get('transactions'):
            # TODO: do validity checking for coinbase transactions
            if str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(block.get('public_key')))) in [x['to'] for x in txn.get('outputs', '')] and len(txn.get('outputs', '')) == 1 and not txn.get('inputs') and not txn.get('relationship'):
                txn['coinbase'] = True  
            else:
                txn['coinbase'] = False
            transactions.append(Transaction.from_dict(txn))

        if block.get('special_target', 0) == 0:
            block['special_target'] = block.get('target')

        return await cls.init_async(
            version=block.get('version'),
            block_time=block.get('time'),
            block_index=block.get('index'),
            public_key=block.get('public_key'),
            prev_hash=block.get('prevHash'),
            nonce=block.get('nonce'),
            transactions=transactions,
            block_hash=block.get('hash'),
            merkle_root=block.get('merkleRoot'),
            signature=block.get('id'),
            special_min=block.get('special_min'),
            header=block.get('header', ''),
            target=int(block.get('target'), 16),
            special_target=int(block.get('special_target', 0), 16)
        )

    @classmethod
    async def from_json(cls, block_json):
        return await cls.from_dict(json.loads(block_json))
    
    def get_coinbase(self):
        for txn in self.transactions:
            if str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key))) in [x.to for x in txn.outputs] and len(txn.outputs) == 1 and not txn.relationship and len(txn.inputs) == 0:
                return txn

    def generate_hash_from_header(self, height, header, nonce):
        if not hasattr(Block, 'pyrx'):
            Block.pyrx = pyrx.PyRX()
        seed_hash = binascii.unhexlify('4181a493b397a733b083639334bc32b407915b9a82b7917ac361816f0a1f5d4d') #sha256(yadacoin65000)
        if height >= CHAIN.BLOCK_V5_FORK:
            bh = Block.pyrx.get_rx_hash(
                header.encode().replace(
                    b'{nonce}',
                    binascii.unhexlify(
                        nonce
                    )
                ),
                seed_hash,
                height
            )
            hh = binascii.hexlify(bh).decode()
            return hh
        elif height >= CHAIN.RANDOMX_FORK:
            header = header.format(nonce=nonce)
            bh = Block.pyrx.get_rx_hash(header, seed_hash, height)
            hh = binascii.hexlify(bh).decode()
            return hh
        else:
            header = header.format(nonce=nonce)
            return hashlib.sha256(hashlib.sha256(header.encode('utf-8')).digest()).digest()[::-1].hex()

    def verify(self):
        getcontext().prec = 8
        if int(self.version) != int(CHAIN.get_version_for_height(self.index)):
            raise Exception("Wrong version for block height", self.version, CHAIN.get_version_for_height(self.index))

        txns = self.get_transaction_hashes()
        verify_merkle_root = self.get_merkle_root(txns)
        if verify_merkle_root != self.merkle_root:
            raise Exception("Invalid block merkle root")

        header = self.generate_header()
        hashtest = self.generate_hash_from_header(self.index, header, str(self.nonce))
        # print("header", header, "nonce", self.nonce, "hashtest", hashtest)
        if self.hash != hashtest:
            getLogger("tornado.application").warning("Verify error hashtest {} header {} nonce {}".format(hashtest, header, self.nonce))
            raise Exception('Invalid block hash')

        address = P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key))
        try:
            # print("address", address, "sig", self.signature, "pubkey", self.public_key)
            result = verify_signature(base64.b64decode(self.signature), self.hash.encode('utf-8'), bytes.fromhex(self.public_key))
            if not result:
                raise Exception("block signature1 is invalid")
        except:
            try:
                result = VerifyMessage(address, BitcoinMessage(self.hash.encode('utf-8'), magic=''), self.signature)
                if not result:
                    raise
            except:
                raise Exception("block signature2 is invalid")

        # verify reward
        coinbase_sum = 0
        for txn in self.transactions:
            if int(self.index) > CHAIN.CHECK_TIME_FROM and (int(txn.time) > int(self.time) + CHAIN.TIME_TOLERANCE):
                #yadacoin.core.config.CONFIG.mongo.db.miner_transactions.remove({'id': txn.transaction_signature}, multi=True)
                #raise Exception("Block embeds txn too far in the future")
                pass

            if txn.coinbase:
                for output in txn.outputs:
                    coinbase_sum += float(output.value)

        fee_sum = 0.0
        for txn in self.transactions:
            if not txn.coinbase:
                fee_sum += float(txn.fee)
        reward = CHAIN.get_block_reward(self.index)

        #if Decimal(str(fee_sum)[:10]) != Decimal(str(coinbase_sum)[:10]) - Decimal(str(reward)[:10]):
        """
        KO for block 13949
        0.02099999 50.021 50.0
        Integrate block error 1 ('Coinbase output total does not equal block reward + transaction fees', 0.020999999999999998, 0.021000000000000796)
        """
        if quantize_eight(fee_sum) != quantize_eight(coinbase_sum - reward):
            print(fee_sum, coinbase_sum, reward)
            raise Exception("Coinbase output total does not equal block reward + transaction fees", fee_sum, (coinbase_sum - reward))
    
    async def check_transactions(self):
        async def get_txns(txns):
            for x in txns:
                yield x

        async def get_inputs(inputs):
            for x in inputs:
                yield x

        used_inputs = {}
        i = 0
        async for transaction in get_txns(self.transactions):
            self.app_log.warning('verifying txn: {} block: {}'.format(i, self.index))
            i += 1
            try:
                await transaction.verify()
            except InvalidTransactionException as e:
                self.app_log.warning(e)
                return False
            except InvalidTransactionSignatureException as e:
                self.app_log.warning(e)
                return False
            except MissingInputTransactionException as e:
                self.app_log.warning(e)
            except NotEnoughMoneyException as e:
                self.app_log.warning(e)
                return False
            except Exception as e:
                self.app_log.warning(e)
                return False

            if transaction.inputs:
                failed = False
                used_ids_in_this_txn = []
                async for x in get_inputs(transaction.inputs):
                    if yadacoin.core.config.CONFIG.BU.is_input_spent(x.id, transaction.public_key):
                        failed = True
                    if x.id in used_ids_in_this_txn:
                        failed = True
                    if (x.id, transaction.public_key) in used_inputs:
                        failed = True
                    used_inputs[(x.id, transaction.public_key)] = transaction
                    used_ids_in_this_txn.append(x.id)
                if failed and self.index >= CHAIN.CHECK_DOUBLE_SPEND_FROM:
                    raise MissingInputTransactionException()
                elif failed and self.index < CHAIN.CHECK_DOUBLE_SPEND_FROM:
                    continue
        return True

    def get_transaction_hashes(self):
        """Returns a sorted list of tx hash, so the merkle root is constant across nodes"""
        return sorted([str(x.hash) for x in self.transactions], key=str.lower)

    async def save(self):
        self.verify()
        for txn in self.transactions:
            if txn.inputs:
                failed = False
                used_ids_in_this_txn = []
                for x in txn.inputs:
                    if yadacoin.core.config.CONFIG.BU.is_input_spent(x.id, txn.public_key):
                        failed = True
                    if x.id in used_ids_in_this_txn:
                        failed = True
                    used_ids_in_this_txn.append(x.id)
                if failed:
                    raise Exception('double spend', [x.id for x in txn.inputs])
        res = await self.config.mongo.async_db.blocks.find_one({"index": (int(self.index) - 1)})
        if (res and res[0]['hash'] == self.prev_hash) or self.index == 0:
            await self.config.mongo.async_db.blocks.replace_one({'index': self.index}, self.to_dict(), upsert=True)
        else:
            print("CRITICAL: block rejected...")

    def delete(self):
        self.config.mongo.db.blocks.remove({"index": self.index})

    def to_dict(self):
        try:
            return {
                'version': self.version,
                'time': int(self.time),
                'index': self.index,
                'public_key': self.public_key,
                'prevHash': self.prev_hash,
                'nonce': self.nonce,
                'transactions': [x.to_dict() for x in self.transactions],
                'hash': self.hash,
                'merkleRoot': self.merkle_root,
                'special_min': self.special_min,
                'target': hex(self.target)[2:].rjust(64, '0'),
                'special_target': hex(self.special_target)[2:].rjust(64, '0'),
                'header': self.header,
                'id': self.signature
            }
        except Exception as e:
            print(e)
            print("target", self.target, "spec", self.special_target)

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)

    def in_the_future(self):
        """Tells wether the block is too far away in the future"""
        return int(self.time) > time.time() + CHAIN.TIME_TOLERANCE
