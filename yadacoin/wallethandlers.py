"""
Handlers required by the wallet operations
"""

import hashlib
import binascii
import base58
import json
from bip32utils import BIP32Key
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU
from yadacoin.transaction import Transaction, TransactionFactory, NotEnoughMoneyException
from yadacoin.transactionbroadcaster import TxnBroadcaster


class WalletHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


class GenerateWalletHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


class GenerateChildWalletHandler(BaseHandler):

    async def post(self):
        args = json.loads(self.request.body)
        exkey = BIP32Key.fromExtendedKey(self.config.xprv)
        last_child_key = await self.config.mongo.async_db.child_keys.find_one({'account': args.get('uid')}, sort=[('inc', -1)])
        if last_child_key:
            inc = last_child_key['inc'] + 1
        else:
            inc = 0
        key = exkey.ChildKey(inc)
        child_key = BIP32Key.fromExtendedKey(key.ExtendedKey())
        public_key = child_key.PublicKey().hex()
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        private_key = child_key.PrivateKey().hex()
        wif = self.to_wif(private_key)

        await self.config.mongo.async_db.child_keys.insert_one({
            'account': args.get('uid'),
            'inc': inc,
            'extended': child_key.ExtendedKey(),
            'public_key': public_key,
            'address': address,
            'private_key': private_key,
            'wif': wif
        })
        return self.render_as_json({"address": address})
    
    def to_wif(self, private_key):

        #to wif
        private_key_static = private_key
        extended_key = "80"+private_key_static+"01"
        first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key)).hexdigest()
        second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
        final_key = extended_key+second_sha256[:8]
        return base58.b58encode(binascii.unhexlify(final_key)).decode('utf-8')


class GetAddressesHandler(BaseHandler):

    async def get(self):
        addresses = [x['address'] async for x in self.config.mongo.async_db.child_keys.find()]
        addresses.append(self.config.address)

        return self.render_as_json({'addresses': list(set(addresses))})


class GetBalanceSum(BaseHandler):

    async def get(self):
        args = json.loads(self.request.body)
        addresses = args.get("addresses", None)
        if not addresses:
            self.render_as_json({})
            return
        balance = 0.0
        for address in addresses:
            balance += BU().get_wallet_balance(address)
        return self.render_as_json({
            'balance': "{0:.8f}".format(balance)
        })


class CreateTransactionView(BaseHandler):
    async def post(self):
        config = self.config

        args = json.loads(self.request.body)
        address = args.get('address')
        if not address:
            return self.render_as_json({})

        fee = args.get('fee', 0.0)
        outputs = args.get('outputs')
        if not outputs:
            return self.render_as_json({})
        from_addresses = args.get('from', [])

        inputs = []
        for from_address in from_addresses:
            unspent = BU().get_wallet_unspent_transactions(from_address)
            inputs.extend(unspent)

        txn = TransactionFactory(
            block_height=BU().get_latest_block()['index'],
            private_key=config.private_key,
            public_key=config.public_key,
            fee=float(fee),
            inputs=inputs,
            outputs=outputs
        )
        return self.render_as_json(txn.transaction.to_dict())


class CreateRawTransactionView(BaseHandler):
    async def post(self):
        config = self.config

        args = json.loads(self.request.body)
        address = args.get('address')
        if not address:
            return self.render_as_json({})

        fee = args.get('fee', 0.0)
        outputs = args.get('outputs')
        if not outputs:
            return self.render_as_json({})
        from_addresses = args.get('from', [])

        inputs = []
        for from_address in from_addresses:
            unspent = BU().get_wallet_unspent_transactions(from_address)
            inputs.extend(unspent)

        txn = TransactionFactory(
            block_height=BU().get_latest_block()['index'],
            public_key=config.public_key,
            fee=float(fee),
            inputs=inputs,
            outputs=outputs
        )
        return self.render_as_json(txn.transaction.to_dict())

class SendTransactionView(BaseHandler):
    async def post(self):
        config = self.config
        args = json.loads(self.request.body)
        to = args.get('address')
        value = args.get('value')
        from_address = args.get('from')

        if from_address == config.address:
            private_key = config.private_key
        else:
            child_key = await config.mongo.async_db.child_keys.find_one({'address': from_address})
            if child_key:
                public_key = child_key['public_key']
                private_key = child_key['private_key']
            else:
                return self.render_as_json({'status': 'error', 'message': 'no wallet matching from address'})

        try:
            transaction = TransactionFactory(
                block_height=config.BU.get_latest_block()['index'],
                fee=0.00,
                public_key=public_key,
                private_key=private_key,
                outputs=[
                    {'to': to, 'value': value}
                ]
            )
        except NotEnoughMoneyException:
            return self.render_as_json({'status': "error", 'message': "not enough money"})
        except:
            raise
        try:
            transaction.transaction.verify()
        except:
            return self.render_as_json({"error": "invalid transaction"})

        await config.mongo.async_db.miner_transactions.insert_one(transaction.transaction.to_dict())
        txn_b = TxnBroadcaster(config)
        await txn_b.txn_broadcast_job(transaction)

        return self.render_as_json({'status': 'success', 'message': 'Transaction generated and transmitted successfully.'})
 


WALLET_HANDLERS = [
    (r'/wallet', WalletHandler),
    (r'/generate-wallet', GenerateWalletHandler),
    (r'/generate-child-wallet', GenerateChildWalletHandler),
    (r'/get-addresses', GetAddressesHandler),
    (r'/create-transaction', CreateTransactionView),
    (r'/create-raw-transaction', CreateRawTransactionView),
    (r'/get-balance-sum', GetBalanceSum),
    (r'/send-transaction', SendTransactionView),
]
