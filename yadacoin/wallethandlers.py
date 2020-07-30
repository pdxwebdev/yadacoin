"""
Handlers required by the wallet operations
"""

import hashlib
import binascii
import base58
import json
import datetime
import jwt
import time
from bip32utils import BIP32Key
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU
from yadacoin.transaction import Transaction, TransactionFactory, NotEnoughMoneyException
from yadacoin.transactionbroadcaster import TxnBroadcaster
from yadacoin.auth import jwtauth
from yadacoin.transactionutils import TU


class WalletHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


class GenerateWalletHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


@jwtauth
class GenerateChildWalletHandler(BaseHandler):

    async def post(self):
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif and self.jwt.get('key_or_wif') != 'true':
            return self.render_as_json({'error': 'not authorized'})
        args = json.loads(self.request.body)
        if not args.get('uid'):
            return self.render_as_json({"error": True, "message": "no user account provided"})
        keyhash = hashlib.sha256(
                TU.generate_deterministic_signature(self.config, 'child_wallet').encode()
            ).hexdigest()
        exkey = BIP32Key.fromExtendedKey(self.config.xprv)
        last_child_key = self.config.mongo.db.child_keys.find({
            'signature': keyhash
        }, sort=[('inc', -1)])
        inc = last_child_key.count() + 1
        key = exkey.ChildKey(inc)
        child_key = BIP32Key.fromExtendedKey(key.ExtendedKey())
        child_key = child_key.ChildKey(inc)
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
            'wif': wif,
            'signature': keyhash
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
        addresses = []
        async for x in await self.config.mongo.async_db.child_keys.find():
            addresses.append(x['address'])
        addresses.append(self.config.address)

        return self.render_as_json({'addresses': list(set(addresses))})


class GetBalanceSum(BaseHandler):

    async def get(self):
        args = json.loads(self.request.body.decode())
        addresses = args.get("addresses", None)
        if not addresses:
            self.render_as_json({})
            return
        balance = 0.0
        for address in addresses:
            balance += await BU().get_wallet_balance(address)
        return self.render_as_json({
            'balance': "{0:.8f}".format(balance)
        })


@jwtauth
class CreateTransactionView(BaseHandler):
    async def post(self):
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif and self.jwt.get('key_or_wif') != 'true':
            return self.render_as_json({'error': 'not authorized'})
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
            inputs.extend([x async for x in BU().get_wallet_unspent_transactions(from_address)])

        txn = await TransactionFactory.construct(
            block_height=BU().get_latest_block()['index'],
            private_key=config.private_key,
            public_key=config.public_key,
            fee=float(fee),
            inputs=inputs,
            outputs=outputs
        )
        return self.render_as_json(txn.transaction.to_dict())


@jwtauth
class CreateRawTransactionView(BaseHandler):
    async def post(self):
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif and self.jwt.get('key_or_wif') != 'true':
            return self.render_as_json({'error': 'not authorized'})
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
            inputs.extend([x async for x in await BU().get_wallet_unspent_transactions(from_address)])

        txn = await TransactionFactory.construct(
            block_height=BU().get_latest_block()['index'],
            public_key=config.public_key,
            fee=float(fee),
            inputs=inputs,
            outputs=outputs
        )
        return self.render_as_json(txn.transaction.to_dict())


@jwtauth
class SendTransactionView(BaseHandler):
    async def post(self):
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif and self.jwt.get('key_or_wif') != 'true':
            return self.render_as_json({'error': 'not authorized'})
        config = self.config
        args = json.loads(self.request.body.decode())
        to = args.get('address')
        value = float(args.get('value'))
        from_address = args.get('from')
        dry_run = args.get('dry_run')
        txn = await TU.send(config, to, value, from_address, dry_run)
        return self.render_as_json(txn)


@jwtauth
class UnlockedHandler(BaseHandler):

    async def prepare(self):

        origin = self.get_query_argument('origin', '*')
        if origin[-1] == '/':
            origin = origin[:-1]
        self.set_header("Access-Control-Allow-Origin", origin)
        self.set_header('Access-Control-Allow-Credentials', "true")
        self.set_header('Access-Control-Allow-Methods', "GET, POST, OPTIONS")
        self.set_header('Access-Control-Expose-Headers', "Content-Type")
        self.set_header('Access-Control-Allow-Headers', "Authorization, Content-Type, Depth, User-Agent, X-File-Size, X-Requested-With, X-Requested-By, If-Modified-Since, X-File-Name, Cache-Control")
        self.set_header('Access-Control-Max-Age', 600)
        await super(UnlockedHandler, self).prepare()

    async def get(self):

        if self.get_secure_cookie('key_or_wif') == 'true':
            return self.render_as_json({
                'unlocked': True
            })

        if self.jwt.get('key_or_wif') == 'true':
            return self.render_as_json({
                'unlocked': True
            })
        
        return self.render_as_json({
            'unlocked': False
        })


class UnlockHandler(BaseHandler):

    async def get(self):
        """
        :return:
        """
        self.render(
            "auth.html"
        )
    
    async def post(self):
        try:
            key_or_wif = self.get_body_argument('key_or_wif')
            expires = self.get_body_argument('expires', 23040)
        except:
            json_body = json.loads(self.request.body.decode())
            key_or_wif = json_body.get('key_or_wif')
            expires = json_body.get('expires', 23040)
        if key_or_wif in [self.config.wif, self.config.private_key, self.config.seed]:
            self.set_secure_cookie("key_or_wif", 'true')

            payload = {
                'timestamp': time.time(),
                'key_or_wif': 'true',
                'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=int(expires))
            }

            self.encoded = jwt.encode(
                payload,
                self.config.jwt_secret_key,
                algorithm='ES256'
            )
            await self.config.mongo.async_db.config.update_one(
                {
                    'key': 'jwt'
                },
                {
                    '$set': {
                        'key':'jwt',
                        'value': {
                            'timestamp': payload['timestamp']
                        }
                    }
                }, 
                upsert=True
            )
            return self.render_as_json({'token': self.encoded.decode()})
        else:
            self.write({'status': 'error', 'message': 'Wrong private key or WIF. You must provide the private key or WIF of the currently running server.'})
            self.set_header('Content-Type', 'application/json')
            return self.finish()


WALLET_HANDLERS = [
    (r'/wallet', WalletHandler),
    (r'/generate-wallet', GenerateWalletHandler),
    (r'/generate-child-wallet', GenerateChildWalletHandler),
    (r'/get-addresses', GetAddressesHandler),
    (r'/create-transaction', CreateTransactionView),
    (r'/create-raw-transaction', CreateRawTransactionView),
    (r'/get-balance-sum', GetBalanceSum),
    (r'/send-transaction', SendTransactionView),
    (r'/unlocked', UnlockedHandler),
    (r'/unlock', UnlockHandler),
]
