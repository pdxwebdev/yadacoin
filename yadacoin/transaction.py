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

from yadacoin.crypt import Crypt
from yadacoin.transactionutils import TU
# from yadacoin.blockchainutils import BU
from yadacoin.config import get_config
from yadacoin.chain import CHAIN


def fix_float1(value):
    return '.'.join(["{0:.9f}".format(value).split('.')[0], "{0:.9f}".format(value).split('.')[1][:8]])


class TransactionFactory(object):
    @classmethod
    async def construct(
        cls,
        block_height,
        bulletin_secret='',
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
        no_relationship=False
    ):
        cls_inst = cls()
        cls_inst.config = get_config()
        cls_inst.mongo = cls_inst.config.mongo
        cls_inst.app_log = getLogger('tornado.application')
        cls_inst.block_height = block_height
        cls_inst.bulletin_secret = bulletin_secret
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
        cls_inst.time = str(int(time.time()))
        cls_inst.outputs = []
        cls_inst.relationship = relationship
        cls_inst.no_relationship = no_relationship
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
        if bulletin_secret or rid:
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
        cls_inst.transaction = cls_inst.generate_transaction()
        return cls_inst

    async def do_money(self):
        if self.coinbase:
            self.inputs = []
            return
        outputs_and_fee_total = sum([x.value for x in self.outputs])+self.fee
        if outputs_and_fee_total == 0:
            return
        my_address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))
        miner_transactions = self.mongo.db.miner_transactions.find({
            '$or': [
                {"txn.public_key": self.public_key},
                {"txn.inputs.public_key": self.public_key},
                {"txn.inputs.address": my_address}
            ]
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
                input_txn = Transaction.from_dict(self.config.BU.get_latest_block()['index'], input_txn)
                if input_txn.transaction_signature in mtxn_ids:
                    continue
                else:
                    input_sum = self.collect_needed_inputs(Input.from_dict(input_txn.to_dict()), input_txn, my_address, input_sum, inputs, outputs_and_fee_total)
                    if input_sum >= outputs_and_fee_total:
                        enough = True
                        break

            if not enough:
                raise NotEnoughMoneyException('not enough money')

            self.inputs = inputs

        if not self.inputs and not self.coinbase and outputs_and_fee_total > 0:
            raise NotEnoughMoneyException('No inputs, not a coinbase, and transaction amount is greater than zero')

        remainder = input_sum - outputs_and_fee_total

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
                input_sum += txn_output.value

                if input_txn not in inputs:
                    inputs.append(input_obj)

                if input_sum >= outputs_and_fee_total:
                    return input_sum
        return input_sum

    async def get_inputs(self, inputs):
        for x in inputs:
            yield x

    async def get_input_hashes(self):
        from yadacoin.fastgraph import FastGraph
        input_hashes = []
        async for x in self.get_inputs(self.inputs):
            txn = self.config.BU.get_transaction_by_id(x.id, instance=True, include_fastgraph=isinstance(self, FastGraph))
            input_hashes.append(str(txn.transaction_signature))

        return ''.join(sorted(input_hashes, key=str.lower))

    def get_output_hashes(self):
        outputs_sorted = sorted([x.to_dict() for x in self.outputs], key=lambda x: x['to'].lower())
        return ''.join([x['to'] + "{0:.8f}".format(x['value']) for x in outputs_sorted])

    def generate_rid(self):
        my_bulletin_secret = self.config.get_bulletin_secret()
        if my_bulletin_secret == self.bulletin_secret:
            raise Exception('bulletin secrets are identical.')
        bulletin_secrets = sorted([str(my_bulletin_secret), str(self.bulletin_secret)], key=str.lower)
        return hashlib.sha256((str(bulletin_secrets[0]) + str(bulletin_secrets[1])).encode('utf-8')).digest().hex()

    def generate_relationship(self):
        return Relationship(
            dh_private_key=self.dh_private_key,
            their_bulletin_secret=self.bulletin_secret,
            their_username=self.username,
            my_bulletin_secret=self.config.get_bulletin_secret(),
            my_username=self.config.username
        )

    def generate_transaction(self):
        return Transaction(
            self.block_height,
            self.time,
            self.rid,
            self.transaction_signature,
            self.encrypted_relationship,
            self.public_key,
            self.dh_public_key,
            float(self.fee),
            self.requester_rid,
            self.requested_rid,
            self.hash,
            inputs=[x.to_dict() for x in self.inputs],
            outputs=[x.to_dict() for x in self.outputs],
            coinbase=self.coinbase
        )

    def generate_transaction_signature(self):
        return TU.generate_signature(self.hash, self.private_key)


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
        block_height,
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
        extra_blocks=None
    ):
        self.config = get_config()
        self.mongo = self.config.mongo
        self.block_height = block_height
        self.time = txn_time
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
    def from_dict(cls, block_height, txn):
        if isinstance(txn.get('relationship'), dict):
            relationship = Relationship(**txn.get('relationship'))
        else:
            relationship = txn.get('relationship', '')
        
        return cls(
            block_height=block_height,
            txn_time=txn.get('time', ''),
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
        from yadacoin.fastgraph import FastGraph
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
                result = VerifyMessage(address, BitcoinMessage(self.hash.encode('utf-8'), magic=''), self.transaction_signature)
                if not result:
                    print("t verify2")
                    raise
            except:
                print("t verify3")
                raise InvalidTransactionSignatureException("transaction signature did not verify")

        if len(self.relationship) > 20480:
            raise MaxRelationshipSizeExceeded('Relationship field cannot be greater than 2048 bytes')

        # verify spend
        total_input = 0
        async for txn in self.get_inputs(self.inputs):
            # TODO: move to async
            input_txn = self.config.BU.get_transaction_by_id(txn.id, include_fastgraph=isinstance(self, FastGraph))
            if not input_txn:
                raise InvalidTransactionException("Input not found on blockchain.")
            txn_input = Transaction.from_dict(self.block_height, input_txn)

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
        if fix_float1(total_input) != fix_float1(total):
            raise TotalValueMismatchException("inputs and outputs sum must match %s, %s, %s, %s" % (total_input, float(total_output), float(self.fee), total))

    async def generate_hash(self):
        inputs_concat = await self.get_input_hashes()
        outputs_concat = self.get_output_hashes()
        if self.time:
            hashout = hashlib.sha256((
                self.public_key +
                self.time +
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
        from yadacoin.fastgraph import FastGraph
        input_hashes = []
        async for x in self.get_inputs(self.inputs):
            txn = self.config.BU.get_transaction_by_id(x.id, instance=True, include_fastgraph=isinstance(self, FastGraph))
            if txn:
                input_hashes.append(str(txn.transaction_signature))
            else:
                found = False
                if self.extra_blocks:
                    for block in self.extra_blocks:
                        for xtxn in block.transactions:
                            if xtxn.transaction_signature == x.id:
                                input_hashes.append(str(xtxn.transaction_signature))
                                found = True
                                break
                        if found:
                            break
                if not found:
                    raise MissingInputTransactionException("This transaction is not in the blockchain.")

        return ''.join(sorted(input_hashes, key=lambda v: v.lower()))

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
        their_bulletin_secret=None,
        their_username=None,
        my_bulletin_secret=None,
        my_username=None,
        their_public_key=None,
        their_address=None,
        group=None,
        reply=None,
        topic=None,
        my_public_key=None
    ):
        self.dh_private_key = dh_private_key
        self.their_bulletin_secret = their_bulletin_secret
        self.their_username = their_username
        self.my_bulletin_secret = my_bulletin_secret
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
            'their_bulletin_secret': self.their_bulletin_secret,
            'their_username': self.their_username,
            'my_bulletin_secret': self.my_bulletin_secret,
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
