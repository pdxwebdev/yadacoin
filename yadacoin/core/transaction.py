import json
import hashlib
import os
import base64
import time
from logging import getLogger

from bitcoin.signmessage import BitcoinMessage, VerifyMessage
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import verify_signature
from eccsnacks.curve25519 import scalarmult_base

from yadacoin.core.crypt import Crypt
from yadacoin.core.transactionutils import TU
from yadacoin.core.config import get_config
from yadacoin.core.chain import CHAIN


def fix_float1(value):
    return '.'.join(["{0:.9f}".format(value).split('.')[0], "{0:.9f}".format(value).split('.')[1][:8]])

def fix_float2(value):
    return "{0:.8f}".format(value)


class InvalidTransactionException(Exception):
    pass


class InvalidTransactionSignatureException(Exception):
    pass


class MissingInputTransactionException(Exception):
    pass


class NotEnoughMoneyException(Exception):
    pass


class MaxRelationshipSizeExceeded(Exception):
    pass

class TransactionInputOutputMismatchException(Exception):
    pass

class TotalValueMismatchException(Exception):
    pass


class Transaction(object):

    def __init__(
        self,
        txn_time='',
        rid='',
        transaction_signature='',
        relationship='',
        public_key='',
        dh_public_key='',
        fee=0.0,
        requester_rid='',
        requested_rid='',
        txn_hash='',
        inputs='',
        outputs='',
        coinbase=False,
        extra_blocks=None,
        seed_gateway_rid='',
        seed_rid=''
    ):
        self.app_log = getLogger("tornado.application")
        self.config = get_config()
        self.mongo = self.config.mongo
        self.time = int(txn_time)
        self.rid = rid
        self.transaction_signature = transaction_signature
        self.relationship = relationship
        self.public_key = public_key
        self.dh_public_key = dh_public_key if dh_public_key else ''
        self.fee = float(fee)
        self.requester_rid = requester_rid if requester_rid else ''
        self.requested_rid = requested_rid if requested_rid else ''
        self.hash = txn_hash
        self.outputs = []
        self.extra_blocks = extra_blocks
        self.seed_gateway_rid = seed_gateway_rid,
        self.seed_rid = seed_rid
        for x in outputs:
            self.outputs.append(Output.from_dict(x))
        self.inputs = []
        for x in inputs:
            if 'signature' in x and 'public_key' in x and 'address' in x:
                self.inputs.append(ExternalInput.from_dict(x))
            else:
                self.inputs.append(Input.from_dict(x))
        self.coinbase = coinbase

    @classmethod
    async def generate(
        cls,
        username_signature='',
        username='',
        value=0,
        fee=0.0,
        rid='',
        requester_rid='',
        requested_rid='',
        public_key='',
        dh_public_key='',
        private_key='',
        dh_private_key='',
        to='',
        inputs='',
        outputs='',
        coinbase=False,
        chattext=None,
        signin=None,
        relationship='',
        no_relationship=False,
        exact_match=False
    ):
        cls_inst = cls()
        cls_inst.config = get_config()
        cls_inst.mongo = cls_inst.config.mongo
        cls_inst.app_log = getLogger('tornado.application')
        cls_inst.username_signature = username_signature
        cls_inst.username = username
        cls_inst.rid = rid
        cls_inst.requester_rid = requester_rid
        cls_inst.requested_rid = requested_rid
        cls_inst.public_key = public_key
        cls_inst.dh_public_key = dh_public_key
        cls_inst.private_key = private_key
        cls_inst.value = value
        cls_inst.fee = float(fee)
        cls_inst.dh_private_key = dh_private_key
        cls_inst.to = to
        cls_inst.time = int(time.time())
        cls_inst.outputs = []
        cls_inst.relationship = relationship
        cls_inst.no_relationship = no_relationship
        cls_inst.exact_match = exact_match
        for x in outputs:
            cls_inst.outputs.append(Output.from_dict(x))
        cls_inst.inputs = []
        for x in inputs:
            if 'signature' in x and 'public_key' in x and 'address' in x:
                cls_inst.inputs.append(ExternalInput.from_dict(x))
            else:
                cls_inst.inputs.append(Input.from_dict(x))
        cls_inst.coinbase = coinbase
        cls_inst.chattext = chattext
        cls_inst.signin = signin
        await cls_inst.do_money()

        inputs_concat = ''.join([x.id for x in sorted(cls_inst.inputs, key=lambda x: x.id.lower())])
        outputs_concat = cls_inst.get_output_hashes()
        if username_signature or rid:
            if not cls_inst.rid:
                cls_inst.rid = cls_inst.generate_rid()
            if cls_inst.chattext:
                cls_inst.relationship = json.dumps({
                    "chatText": cls_inst.chattext
                })
                cls_inst.encrypted_relationship = cls_inst.config.cipher.encrypt(cls_inst.relationship)
            elif cls_inst.signin:
                for shared_secret in cls_inst.config.GU.get_shared_secrets_by_rid(cls_inst.rid):
                    cls_inst.relationship = SignIn(cls_inst.signin)
                    cls_inst.cipher = Crypt(shared_secret.hex(), shared=True)
                    cls_inst.encrypted_relationship = cls_inst.cipher.shared_encrypt(cls_inst.relationship.to_json())
                    break
            elif cls_inst.relationship:
                cls_inst.encrypted_relationship = cls_inst.relationship
            elif cls_inst.no_relationship:
                cls_inst.encrypted_relationship = ''
            else:
                if not cls_inst.dh_public_key or not cls_inst.dh_private_key:
                    a = os.urandom(32).decode('latin1')
                    cls_inst.dh_public_key = scalarmult_base(a).encode('latin1').hex()
                    cls_inst.dh_private_key = a.encode().hex()
                cls_inst.relationship = cls_inst.generate_relationship()
                if not private_key:
                    raise Exception('missing private key')
                cls_inst.encrypted_relationship = cls_inst.config.cipher.encrypt(cls_inst.relationship.to_json().encode())
        else:
            cls_inst.rid = ''
            cls_inst.encrypted_relationship = ''
        
        cls_inst.header = (
            cls_inst.public_key +
            cls_inst.time +
            cls_inst.dh_public_key +
            cls_inst.rid +
            cls_inst.encrypted_relationship +
            "{0:.8f}".format(cls_inst.fee) +
            cls_inst.requester_rid +
            cls_inst.requested_rid +
            inputs_concat +
            outputs_concat
        )
        cls_inst.hash = hashlib.sha256(cls_inst.header.encode('utf-8')).digest().hex()
        if cls_inst.private_key:
            cls_inst.transaction_signature = TU.generate_signature_with_private_key(private_key, cls_inst.hash)
        else:
            cls_inst.transaction_signature = ''
        return cls(
            cls_inst.time,
            cls_inst.rid,
            cls_inst.transaction_signature,
            cls_inst.encrypted_relationship,
            cls_inst.public_key,
            cls_inst.dh_public_key,
            float(cls_inst.fee),
            cls_inst.requester_rid,
            cls_inst.requested_rid,
            cls_inst.hash,
            inputs=[x.to_dict() for x in cls_inst.inputs],
            outputs=[x.to_dict() for x in cls_inst.outputs],
            coinbase=cls_inst.coinbase
        )

    async def do_money(self):
        if self.coinbase:
            self.inputs = []
            return
        outputs_and_fee_total = sum([x.value for x in self.outputs])+self.fee
        if outputs_and_fee_total == 0:
            return
        my_address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))
        miner_transactions = self.mongo.db.miner_transactions.find({
            "public_key": self.public_key
        })
        mtxn_ids = []
        for mtxn in miner_transactions:
            for mtxninput in mtxn['inputs']:
                mtxn_ids.append(mtxninput['id'])
        
        input_sum = 0
        inputs = []
        enough = False
        if self.inputs:
            async for y in self.get_inputs(self.inputs):
                txn = self.config.BU.get_transaction_by_id(y.id, instance=True)
                if not txn:
                    raise MissingInputTransactionException()

                if isinstance(y, ExternalInput):
                    await y.verify()
                    address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(txn.public_key)))
                else:
                    address = my_address

                input_sum = await self.collect_needed_inputs(y, txn, address, input_sum, inputs, outputs_and_fee_total)
                if input_sum >= outputs_and_fee_total:
                    enough = True
                    break

            if not enough:
                raise NotEnoughMoneyException('not enough money')
            self.inputs = inputs
        else:
            async for input_txn in self.config.BU.get_wallet_unspent_transactions(my_address, no_zeros=True):
                input_txn = Transaction.from_dict(input_txn)
                if input_txn.transaction_signature in mtxn_ids:
                    continue
                else:
                    input_sum = await self.collect_needed_inputs(Input.from_dict(input_txn.to_dict()), input_txn, my_address, input_sum, inputs, outputs_and_fee_total)
                    if input_sum >= outputs_and_fee_total:
                        enough = True
                        break

            if not enough:
                raise NotEnoughMoneyException('not enough money')

            self.inputs = inputs

        if not self.inputs and not self.coinbase and outputs_and_fee_total > 0:
            raise NotEnoughMoneyException('No inputs, not a coinbase, and transaction amount is greater than zero')

        remainder = input_sum - outputs_and_fee_total
        if float(fix_float1(remainder)) == 0 and float(fix_float2(remainder)) == 0:
            remainder = 0.0

        found = False
        for x in self.outputs:
            if my_address == x.to:
                found = True
                x.value += remainder

        if not found:
            return_change_output = Output(
                to=my_address,
                value=remainder
            )
            self.outputs.append(return_change_output)

    async def collect_needed_inputs(self, input_obj, input_txn, my_address, input_sum, inputs, outputs_and_fee_total):

        if isinstance(input_obj, ExternalInput):
            await input_txn.verify()
            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(input_txn.public_key)))
        else:
            address = my_address

        for txn_output in input_txn.outputs:
            if txn_output.to == address and float(txn_output.value) > 0.0:
                fix1 = fix_float1(txn_output.value)
                fix2 = fix_float2(txn_output.value)
                fixtotal1 = fix_float1(outputs_and_fee_total)
                fixtotal2 = fix_float2(outputs_and_fee_total)
                if (
                    self.exact_match and
                    fix1 != fixtotal1 and
                    fix2 != fixtotal2
                ):
                    continue
                input_sum += txn_output.value

                if input_txn not in inputs:
                    inputs.append(input_obj)

                if input_sum >= outputs_and_fee_total:
                    return input_sum
        return input_sum

    def generate_transaction_signature(self):
        return TU.generate_signature(self.hash, self.private_key)

    @classmethod
    def from_dict(cls, txn):
        if isinstance(txn.get('relationship'), dict):
            relationship = Relationship(**txn.get('relationship'))
        else:
            relationship = txn.get('relationship', '')
        
        return cls(
            txn_time=txn.get('time'),
            transaction_signature=txn.get('id'),
            rid=txn.get('rid', ''),
            relationship=relationship,
            public_key=txn.get('public_key'),
            dh_public_key=txn.get('dh_public_key'),
            fee=float(txn.get('fee')),
            requester_rid=txn.get('requester_rid', ''),
            requested_rid=txn.get('requested_rid', ''),
            txn_hash=txn.get('hash', ''),
            inputs=txn.get('inputs', []),
            outputs=txn.get('outputs', []),
            coinbase=txn.get('coinbase', '')
        )

    def in_the_future(self):
        """Tells whether the transaction is too far away in the future"""
        return int(self.time) > time.time() + CHAIN.TIME_TOLERANCE

    async def get_inputs(self, inputs):
        for x in inputs:
            yield x

    async def verify(self):
        verify_hash = await self.generate_hash()
        address = P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key))

        if verify_hash != self.hash:
            raise InvalidTransactionException("transaction is invalid")

        try:
            result = verify_signature(base64.b64decode(self.transaction_signature), self.hash.encode('utf-8'),
                                      bytes.fromhex(self.public_key))
            if not result:
                print("t verify1")
                raise Exception()
        except:
            try:
                result = VerifyMessage(address, BitcoinMessage(self.hash, magic=''), self.transaction_signature)
                if not result:
                    print("t verify2")
                    raise
            except:
                print("t verify3")
                raise InvalidTransactionSignatureException("transaction signature did not verify")

        if len(self.relationship) > 20480:
            raise MaxRelationshipSizeExceeded('Relationship field cannot be greater than 20480 bytes')

        # verify spend
        total_input = 0
        exclude_recovered_ids = []
        async for txn in self.get_inputs(self.inputs):
            txn_input = None
            input_txn = self.config.BU.get_transaction_by_id(txn.id)
            if input_txn:
                txn_input = Transaction.from_dict(input_txn)
            if not input_txn:
                if self.extra_blocks:
                    txn_input = await self.find_in_extra_blocks(txn)
                if not txn_input:
                    result = await self.recover_missing_transaction(txn.id, exclude_recovered_ids)
                    exclude_recovered_ids.append(exclude_recovered_ids)
                    raise MissingInputTransactionException("Input not found on blockchain: {}".format(txn.id))

            found = False
            for output in txn_input.outputs:
                if isinstance(txn, ExternalInput):
                    ext_address = P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(txn_input.public_key))
                    int_address = P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(txn.public_key))
                    if str(output.to) == str(ext_address) and str(int_address) == str(txn.address):
                        try:
                            result = verify_signature(base64.b64decode(txn.signature), txn.id.encode('utf-8'), bytes.fromhex(txn_input.public_key))
                            if not result:
                                print("t verify4")
                                raise Exception()
                        except:
                            try:
                                result = VerifyMessage(ext_address, BitcoinMessage(txn.id, magic=''), txn.signature)
                                if not result:
                                    print("t verify5")
                                    raise
                            except:
                                raise InvalidTransactionSignatureException("external input transaction signature did not verify")
                        
                        found = True
                        total_input += float(output.value)
                elif str(output.to) == str(address):
                    found = True
                    total_input += float(output.value)
            
            if not found:
                if isinstance(txn, ExternalInput):
                    raise InvalidTransactionException("external input signing information did not match any recipients of the input transaction")
                else:
                    raise InvalidTransactionException("using inputs from a transaction where you were not one of the recipients.")

        if self.coinbase:
            return

        total_output = 0
        for txn in self.outputs:
            total_output += float(txn.value)
        total = float(total_output) + float(self.fee)
        if fix_float1(total_input) != fix_float1(total) and fix_float2(total_input) != fix_float2(total):
            raise TotalValueMismatchException("inputs and outputs sum must match %s, %s, %s, %s" % (total_input, float(total_output), float(self.fee), total))

    async def generate_hash(self):
        inputs_concat = await self.get_input_hashes()
        outputs_concat = self.get_output_hashes()
        if self.time:
            hashout = hashlib.sha256((
                self.public_key +
                str(self.time) +
                self.dh_public_key +
                self.rid +
                self.relationship +
                "{0:.8f}".format(self.fee) +
                self.requester_rid +
                self.requested_rid +
                inputs_concat +
                outputs_concat).encode('utf-8')
            ).digest().hex()
        else:
            hashout = hashlib.sha256((
                self.dh_public_key +
                self.rid +
                self.relationship +
                "{0:.8f}".format(self.fee) +
                self.requester_rid +
                self.requested_rid +
                inputs_concat +
                outputs_concat).encode('utf-8')
            ).digest().hex()
        return hashout

    async def get_input_hashes(self):
        return ''.join(sorted([x.id async for x in self.get_inputs(self.inputs)], key=lambda v: v.lower()))
    
    async def find_in_extra_blocks(self, txn_input):
        for block in self.extra_blocks:
            for xtxn in block.transactions:
                if xtxn.transaction_signature == txn_input.id:
                    return xtxn

    def get_output_hashes(self):
        outputs_sorted = sorted([x.to_dict() for x in self.outputs], key=lambda x: x['to'].lower())
        return ''.join([x['to'] + "{0:.8f}".format(x['value']) for x in outputs_sorted])

    def used_as_input(self, input_id):
        block = self.config.mongo.db.blocks.find_one({ # we need to look ahead in the chain
            'transactions.inputs.id': input_id
        })
        output_txn = None
        if not block:
            return output_txn
        for txn in block['transactions']:
            for inp in txn['inputs']:
                if inp['id'] == input_id:
                    output_txn = txn
                    return output_txn

    async def recover_missing_transaction(self, txn_id, exclude_ids=[]):
        return False
        if await self.config.mongo.async_db.failed_recoveries.find_one({'txn_id': txn_id}):
            return False
        self.app_log.warning("recovering missing transaction input: {}".format(txn_id))
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))
        missing_txns = self.config.mongo.async_db.blocks.aggregate([
            {
                '$unwind': '$transactions'
            },
            {
                '$project': {
                    'transaction': '$transactions',
                    'index': '$index'
                }
            }
        ], allowDiskUse=True)
        async for missing_txn in missing_txns:
            self.app_log.warning('recovery searching block index: {}'.format(missing_txn['index']))
            try:
                result = verify_signature(base64.b64decode(txn_id), missing_txn['transaction']['hash'].encode(),
                                        bytes.fromhex(self.public_key))
                if result:
                    block_index = await self.find_unspent_missing_index(missing_txn['transaction']['hash'], exclude_ids)
                    if block_index:
                        await self.replace_missing_transaction_input(
                            block_index,
                            missing_txn['transaction']['hash'],
                            txn_id
                        )
                        return True
                else:
                    if len(base64.b64decode(txn_id)) != 65:
                        continue
                    result = VerifyMessage(
                        address,
                        BitcoinMessage(missing_txn['transaction']['hash'], magic=''),
                        txn_id
                    )
                    if result:
                        block_index = await self.find_unspent_missing_index(missing_txn['transaction']['hash'], exclude_ids)
                        if block_index:
                            await self.replace_missing_transaction_input(
                                block_index,
                                missing_txn['transaction']['hash'],
                                txn_id
                            )
                            return True
            except:
                continue
        await self.config.mongo.async_db.failed_recoveries.update_one({
            'txn_id': txn_id
        },
        {
            '$set': {
                'txn_id': txn_id
            }
        }, upsert=True)
        return False

    async def replace_missing_transaction_input(self, block_index, txn_hash, txn_id):
        block_to_replace = await self.config.mongo.async_db.blocks.find_one({
            'index': block_index
        })

        async def get_txns(txns):
            for txn in txns:
                yield txn

        async for txn in get_txns(block_to_replace['transactions']):
            if txn['hash'] == txn_hash:
                txn['id'] = txn_id
                self.app_log.warning('missing transaction input id updated: {}'.format(block_index))
                break
        await self.config.mongo.async_db.blocks.replace_one({
            'index': block_index
        }, block_to_replace)
        self.app_log.warning('missing transaction input recovery successful: {}'.format(txn_hash))
        return True

    async def find_unspent_missing_index(self, txn_hash, exclude_ids=[]):
        blocks = self.config.mongo.async_db.blocks.find({'transactions.hash': txn_hash})
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))

        async def get_txns(txns):
            for txn in txns:
                yield txn

        async for block in blocks:
            async for txn in get_txns(block['transactions']):
                if txn['hash'] == txn_hash and txn['id'] not in exclude_ids:
                    spents = self.config.mongo.async_db.blocks.aggregate([
                        {
                            '$match': {
                                'transactions.inputs.id': txn['id'],
                                'transactions.public_key': self.public_key
                            }
                        },
                        {
                            '$unwind': '$transactions'
                        },
                        {
                            '$match': {
                                'transactions.inputs.id': txn['id'],
                                'transactions.public_key': self.public_key
                            }
                        },
                    ])
                    found = False
                    async for spent in spents:
                        found = True
                        break
                    if not found:
                        return block['index']

    def to_dict(self):
        relationship = self.relationship
        if hasattr(relationship, 'to_dict'):
            relationship = relationship.to_dict()
        ret = {
            'time': self.time,
            'rid': self.rid,
            'id': self.transaction_signature,  # Beware: changing name between object/dict view is very error prone
            'relationship': relationship,
            'public_key': self.public_key,
            'dh_public_key': self.dh_public_key,
            'fee': float(self.fee),
            'hash': self.hash,
            'inputs': [x.to_dict() for x in self.inputs],
            'outputs': [x.to_dict() for x in self.outputs]
        }
        if self.dh_public_key:
            ret['dh_public_key'] = self.dh_public_key
        if self.requester_rid:
            ret['requester_rid'] = self.requester_rid
        if self.requested_rid:
            ret['requested_rid'] = self.requested_rid
        return ret

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)


class Input(object):
    def __init__(self, signature):
        self.id = signature

    @classmethod
    def from_dict(cls, txn):
        return cls(
            signature=txn.get('id', ''),
        )

    def to_dict(self):
        return {
            'id': self.id
        }


class ExternalInput(Input):

    def __init__(self, public_key, address, txn_id, signature):
        # TODO: error, superclass init missing
        self.config = get_config()
        self.mongo = self.config.mongo
        self.public_key = public_key
        self.id = txn_id
        self.signature = signature
        self.address = address

    def verify(self):
        txn = self.config.BU.get_transaction_by_id(self.id, instance=True)
        result = verify_signature(base64.b64decode(self.signature), self.id.encode('utf-8'), bytes.fromhex(txn.public_key))
        if not result:
            raise Exception('Invalid external input')

    @classmethod
    def from_dict(cls, txn):
        # TODO: sig doees not match
        return cls(
            public_key=txn.get('public_key', ''),
            address=txn.get('address', ''),
            txn_id=txn.get('id', ''),
            signature=txn.get('signature', '')
        )

    def to_dict(self):
        return {
            'public_key': self.public_key,
            'address': self.address,
            'id': self.id,
            'signature': self.signature
        }


class Output(object):
    def __init__(self, to, value):
        self.to = to
        self.value = value

    @classmethod
    def from_dict(cls, txn):
        return cls(
            to=txn.get('to', ''),
            value=txn.get('value', '')
        )

    def to_dict(self):
        return {
            'to': self.to,
            'value': self.value
        }


class Relationship(object):
    def __init__(
        self,
        dh_private_key=None,
        their_username_signature=None,
        their_username=None,
        my_username_signature=None,
        my_username=None,
        their_public_key=None,
        their_address=None,
        group=None,
        reply=None,
        topic=None,
        my_public_key=None
    ):
        self.dh_private_key = dh_private_key
        self.their_username_signature = their_username_signature
        self.their_username = their_username
        self.my_username_signature = my_username_signature
        self.my_username = my_username
        self.their_public_key = their_public_key
        self.their_address = their_address
        self.group = group
        self.reply = reply
        self.topic = topic
        self.my_public_key = my_public_key

    def to_dict(self):
        return {
            'dh_private_key': self.dh_private_key,
            'their_username_signature': self.their_username_signature,
            'their_username': self.their_username,
            'my_username_signature': self.my_username_signature,
            'my_username': self.my_username,
            'their_public_key': self.their_public_key,
            'their_address': self.their_address,
            'group': self.group,
            'reply': self.reply,
            'topic': self.topic,
            'my_public_key': self.my_public_key
        }

    def to_json(self):
        return json.dumps(self.to_dict())


class SignIn(object):
    def __init__(self, signin):
        self.signin = signin

    def to_dict(self):
        return {
            "signIn": self.signin
        }

    def to_json(self):
        return json.dumps(self.to_dict())
