"""
Handlers required by the wallet operations
"""

from bip32utils import BIP32Key
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU


class WalletHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


class GenerateWalletHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


class GenerateChildWalletHandler(BaseHandler):

    async def post(self):
        exkey = BIP32Key.fromExtendedKey(self.config.xprv)
        last_child_key = await self.config.mongo.async_db.child_keys.find_one({'account': self.get_body_argument('uid')}, sort=[('inc', -1)])
        if last_child_key:
            inc = last_child_key['inc'] + 1
        else:
            inc = 0
        key = exkey.ChildKey(inc)
        child_key = BIP32Key.fromExtendedKey(key.ExtendedKey())
        private_key = child_key.PrivateKey().hex()
        public_key = child_key.PublicKey().hex()
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        await self.config.mongo.async_db.child_keys.insert_one({
            'account': self.get_body_argument('uid'),
            'inc': inc,
            'extended': child_key.ExtendedKey(),
            'public_key': private_key,
            'address': address
        })
        return self.render_as_json({"address": address})


class GetAddressesHandler(BaseHandler):

    async def get(self):
        addresses = [x['address'] async for x in await self.config.mongo.async_db.child_keys.find()]
        addresses.append(self.config.address)

        return self.render_as_json({'addresses': addresses})


class GetAddressesHandler(BaseHandler):

    async def get(self):
        addresses = [x['address'] async for x in await self.config.mongo.async_db.child_keys.find()]
        addresses.append(self.config.address)

        return self.render_as_json({'addresses': addresses})


class GetBalanceSum(BaseHandler):

    async def get(self):
        addresses = self.get_body_argument("addresses", False)
        if not addresses:
            self.render_as_json({})
            return
        balance = 0.0
        for address in addresses:
            balance += BU().get_wallet_balance(address)
        return self.render_as_json({
            'balance': "{0:.8f}".format(balance)
        })


WALLET_HANDLERS = [
    (r'/wallet', WalletHandler),
    (r'/generate-wallet', GenerateWalletHandler),
    (r'/generate-child-wallet', GenerateChildWalletHandler),
    (r'/get-addresses', GetAddressesHandler),
]
