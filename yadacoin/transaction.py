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


class TransactionFactory(object):
    
    def __init__(
        self,
        block_height,
        bulletin_secret='',
        username='',
        value=0,
        fee=0.0,
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
        no_relationship=False
    ):
        self.config = get_config()
        self.mongo = self.config.mongo
        self.app_log = getLogger('tornado.application')
        self.block_height = block_height
        self.bulletin_secret = bulletin_secret
        self.username = username
        self.requester_rid = requester_rid
        self.requested_rid = requested_rid
        self.public_key = public_key
        self.dh_public_key = dh_public_key
        self.private_key = private_key
        self.value = value
        self.fee = float(fee)
        self.dh_private_key = dh_private_key
        self.to = to
        self.time = str(int(time.time()))
        self.outputs = []
        self.no_relationship = no_relationship
        for x in outputs:
            self.outputs.append(Output.from_dict(x))
        self.inputs = []
        for x in inputs:
            if 'signature' in x and 'public_key' in x and 'address' in x:
                self.inputs.append(ExternalInput.from_dict(x))
            else:
                self.inputs.append(Input.from_dict(x))
        self.coinbase = coinbase
        self.chattext = chattext
        self.signin = signin
        self.do_money()
        inputs_concat = self.get_input_hashes()
        outputs_concat = self.get_output_hashes()
        if bulletin_secret:
            self.rid = self.generate_rid()
            if self.chattext:
                self.relationship = json.dumps({
                    "chatText": self.chattext
                })
                self.cipher = Crypt(self.config.wif)
                self.encrypted_relationship = self.cipher.encrypt(self.relationship)
            elif self.signin:
                for shared_secret in TU.get_shared_secrets_by_rid(self.rid):
                    self.relationship = SignIn(self.signin)
                    self.cipher = Crypt(shared_secret.hex(), shared=True)
                    self.encrypted_relationship = self.cipher.shared_encrypt(self.relationship.to_json())
                    break
            elif self.no_relationship:
                self.encrypted_relationship = ''
            else:
                if not self.dh_public_key or not self.dh_private_key:
                    a = os.urandom(32).decode('latin1')
                    self.dh_public_key = scalarmult_base(a).encode('latin1').hex()
                    self.dh_private_key = a.encode().hex()
                self.relationship = self.generate_relationship()
                if not private_key:
                    raise Exception('missing private key')
                self.cipher = Crypt(self.config.wif)
                self.encrypted_relationship = self.cipher.encrypt(self.relationship.to_json())
        else:
            self.rid = ''
            self.encrypted_relationship = ''
        
        self.header = (
            self.public_key +
            self.time +
            self.dh_public_key +
            self.rid +
            self.encrypted_relationship +
            "{0:.8f}".format(self.fee) +
            self.requester_rid +
            self.requested_rid +
            inputs_concat +
            outputs_concat
        )
        self.hash = hashlib.sha256(self.header.encode('utf-8')).digest().hex()
        if self.private_key:
            self.transaction_signature = TU.generate_signature_with_private_key(private_key, self.hash)
        else:
            self.transaction_signature = ''
        self.transaction = self.generate_transaction()

    def do_money(self):
        my_address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))
        miner_transactions = self.mongo.db.miner_transactions.find()
        mtxn_ids = []
        for mtxn in miner_transactions:
            for mtxninput in mtxn['inputs']:
                mtxn_ids.append(mtxninput['id'])
        
        if self.inputs:
            inputs = self.inputs
        elif self.coinbase:
            inputs = []
        else:
            input_txns = self.config.BU.get_wallet_unspent_transactions(my_address)
            inputs = []
            for input_txn in input_txns:
                if input_txn['id'] not in mtxn_ids:
                    if 'signature' in input_txn and 'public_key' in input_txn and 'address' in input_txn:
                        inputs.append(ExternalInput.from_dict(input_txn))
                    else:
                        inputs.append(Input.from_dict(input_txn))
        
        outputs_and_fee_total = sum([x.value for x in self.outputs])+self.fee

        input_sum = 0
        if self.coinbase:
            self.inputs = []
        else:
            if inputs:
                needed_inputs = []
                done = False
                for y in inputs:
                    txn = self.config.BU.get_transaction_by_id(y.id, instance=True)
                    if not txn:
                        raise MissingInputTransactionException()
                        
                    if isinstance(y, ExternalInput):
                        y.verify()
                        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(txn.public_key)))
                    else:
                        address = my_address
                    for txn_output in txn.outputs:
                        if txn_output.to == address:
                            input_sum += txn_output.value
                            needed_inputs.append(y)
                            if input_sum >= (outputs_and_fee_total):
                                done = True
                                break
                    if done:
                        break

                if not done:
                    raise NotEnoughMoneyException('not enough money')
                self.inputs = needed_inputs
            else:
                self.inputs = []

            remainder = input_sum-(sum([x.value for x in self.outputs])+self.fee)

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

    def get_input_hashes(self):
        from yadacoin.fastgraph import FastGraph
        input_hashes = []
        for x in self.inputs:
            txn = self.config.BU.get_transaction_by_id(x.id, instance=True, include_fastgraph=isinstance(self, FastGraph))
            input_hashes.append(str(txn.transaction_signature))

        return ''.join(sorted(input_hashes, key=str.lower))

    def get_output_hashes(self):
        outputs_sorted = sorted([x.to_dict() for x in self.outputs], key=lambda x: x['to'].lower())
        return ''.join([x['to'] + "{0:.8f}".format(x['value']) for x in outputs_sorted])

    def generate_rid(self):
        my_bulletin_secret = self.config.get_bulletin_secret()
        if my_bulletin_secret == self.bulletin_secret:
            raise Exception('bulletin secrets are identical. do you love yourself so much that you want a relationship on the blockchain?')
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
        try:
            relationship = Relationship(**txn.get('relationship', ''))
        except:
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

    def verify(self):
        from yadacoin.fastgraph import FastGraph
        verify_hash = self.generate_hash()
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

        if len(self.relationship) > 2048:
            raise MaxRelationshipSizeExceeded('Relationship field cannot be greater than 2048 bytes')

        # verify spend
        total_input = 0
        for txn in self.inputs:
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
        if "{0:.8f}".format(total_input) != "{0:.8f}".format(total):
            raise Exception("inputs and outputs sum must match %s, %s, %s, %s" % (total_input, float(total_output), float(self.fee), total))

    def generate_hash(self):
        inputs_concat = self.get_input_hashes()
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

    def get_input_hashes(self):
        from yadacoin.fastgraph import FastGraph
        input_hashes = []
        for x in self.inputs:
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
        ret = {
            'time': self.time,
            'rid': self.rid,
            'id': self.transaction_signature,  # Beware: changing name between object/dict view is very error prone
            'relationship': self.relationship,
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

    def __init__(self, config, mongo, public_key, address, txn_id, signature):
        # TODO: error, superclass init missing
        self.config = config
        self.mongo = mongo
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
    def from_dict(cls, config, mongo, txn):
        # TODO: sig doees not match
        return cls(
            config=config,
            mongo=mongo,
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
    def __init__(self, dh_private_key, their_bulletin_secret, their_username, my_bulletin_secret, my_username):
        self.dh_private_key = dh_private_key
        self.their_bulletin_secret = their_bulletin_secret
        self.their_username = their_username
        self.my_bulletin_secret = my_bulletin_secret
        self.my_username = my_username

    def to_dict(self):
        return {
            'dh_private_key': self.dh_private_key,
            'their_bulletin_secret': self.their_bulletin_secret,
            'their_username': self.their_username,
            'my_bulletin_secret': self.my_bulletin_secret,
            'my_username': self.my_username
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
