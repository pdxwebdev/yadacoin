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
    def apply_transaction_rules(cls, config, transaction_obj, index):
        from yadacoin.transaction import (
            ExternalInput,
            MissingInputTransactionException,
            InvalidTransactionException
        )
        from yadacoin.block import (
            ExternalInputSpentException,
            CoinbaseRule1,
            CoinbaseRule2,
            CoinbaseRule3,
            CoinbaseRule4,
            RelationshipRule1,
            RelationshipRule2,
            FastGraphRule1,
            FastGraphRule2
        )
        from yadacoin.fastgraph import FastGraph
        from yadacoin.chain import CHAIN
        unspent_indexed = {}
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(transaction_obj.public_key)))
        #check double spend
        if address in unspent_indexed:
            unspent_ids = unspent_indexed[address].keys()
        else:
            res = [x for x in config.BU.get_wallet_unspent_transactions(address)]
            upspent_txns = {x['id']:x for x in res}
            unspent_indexed[address] = upspent_txns
            unspent_ids = unspent_indexed[address].keys()

        used_ids_in_this_txn = []

        for x in transaction_obj.inputs:
            x = config.BU.get_transaction_by_id(x.id, instance=True)
            if x.transaction_signature not in unspent_ids:
                if isinstance(x, ExternalInput):
                    txn2 = config.BU.get_transaction_by_id(x.id, instance=True)
                    address2 = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(txn2.public_key)))
                    res = config.BU.get_wallet_unspent_transactions(address2)
                    unspent_ids2 = [y['id'] for y in res]
                    if x.id not in unspent_ids2:
                        # The external input has already been spent
                        raise ExternalInputSpentException('The external input has already been spent')

            if index >= CHAIN.MINING_AND_TXN_REFORM_FORK: # restrictions begin on transactions at this fork
                if not x:
                    raise MissingInputTransactionException('The external input has already been spent')
                if not unspent_indexed[address][x.transaction_signature]['inputs'] and len(unspent_indexed[address][x.transaction_signature]['inputs']) == 0: # input is a coinbase txn 
                    # Coinbase Rule 1.
                    # Coinbase transactions must only be used as inputs for relationship creation
                    if not transaction_obj.rid or not transaction_obj.relationship or not transaction_obj.dh_public_key:
                        raise CoinbaseRule1('Transaction rejected: Input was a coinbase and this transaction does contain required relationship information')

                    # Coinbase Rule 2. 
                    # No dups are allowed for an rid until the dup rid txn is spent entirely.
                    rid_txns = config.GU.get_transactions_by_rid(transaction_obj.rid, '', rid=True)
                    for rid_txn in rid_txns: # now we have to figure out if all of these are spent fully
                        for output in rid_txn['outputs']:
                            if output['to'] == address and output['value'] == 0:
                                break # now we can create a duplicate relationship

                        for rid_txn_input in rid_txn['inputs']:
                            # if it's in the unspent list then we know it has a remaining balance 
                            # and therefor should be used instead of creating a new relataionship.
                            # This prevents someone from generating the same relationship repeatedly in order spent their coins more quickly.
                            if rid_txn_input['id'] in unspent_ids: 
                                raise CoinbaseRule2('Transaction rejected: No duplicte relationships are allowed for an rid until the duplicate rid txn is spent entirely.')

                        result = cls.check_rid_txn_fully_spent(config, rid_txn, address, index)
                        if not result:
                            raise CoinbaseRule2('Transaction rejected: No duplicte relationships are allowed for an rid until the duplicate rid txn is spent entirely.')

                    # Coinbase Rule 3.
                    # Origin transacation must already be on the blockchain, not in fastgraph collection
                    # we are checking if the transaction is on the blockchain in the above logic as well
                    res = config.mongo.db.fastgraph_transactions.find_one({
                        'dh_public_key': {'$exists': True, '$ne': ''},
                        'rid': transaction_obj.rid,
                        'relationship': {'$exists': True, '$ne': ''}
                    })
                    if res:
                        raise CoinbaseRule3('Transaction rejected: Origin transacation must already be on the blockchain, not in fastgraph collection')

                    # Coinbase Rule 4.
                    # Cannot be used as input for fastgraph
                    if isinstance(transaction_obj, FastGraph):
                        raise CoinbaseRule4('Transaction rejected: Cannot be used as input for fastgraph. Must be used for relationship creation')

                elif (x.rid and x.dh_public_key and x.relationship): # input is a relationship creation transaction
                    # Relationship Rule 1.
                    # Can only be used as inputs for fastgraph or relationship transactions
                    if (not isinstance(transaction_obj, FastGraph) and
                        (not transaction_obj.rid or not transaction_obj.dh_public_key or not transaction_obj.relationship)
                    ):
                        raise RelationshipRule1('Transaction rejected: Cannot be used as input for fastgraph. Must be used for relationship creation')

                    # Relationship Rule 2.
                    # Remainer or "change" transactions cannot be used
                    # any transaction input created by the same public_key is giving itself change
                    if x.public_key == transaction_obj.public_key:
                        raise RelationshipRule2('Transaction rejected: Remainer or "change" transactions cannot be used for relationship creation. Only funds sent from the other relationship party can be used.')

                elif isinstance(x, FastGraph):
                    # FastGraph Rule 1.
                    # Can only be used as inputs for fastgraph transactions
                    if not isinstance(transaction_obj, FastGraph):
                        raise FastGraphRule1('Transaction rejected: Can only be used as inputs for fastgraph transactions.')

                    # FastGraph Rule 2.
                    # Remainer or "change" transactions cannot be used
                    # any transaction input created by me is giving myself change
                    if x.public_key == transaction_obj.public_key:
                        raise FastGraphRule2('Transaction rejected: Remainer or "change" transactions cannot be used as inputs for fastgraph.')
                else:
                    # The trasnaction is none of these types. So it's invalid.
                    raise InvalidTransactionException('Transaction rejected: This transaction is not a coinbase, relationship, or fastgraph.')
                        

            if x.transaction_signature in used_ids_in_this_txn:
                # The trasnaction is none of these types. So it's invalid.
                raise InvalidTransactionException('Transaction rejected: Transaction is a duplicate')
            used_ids_in_this_txn.append(x.transaction_signature)
    
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
