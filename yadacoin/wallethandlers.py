"""
Handlers required by the wallet operations
"""

from bip32utils import BIP32Key
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from yadacoin.basehandlers import BaseHandler


class WalletHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


class GenerateWalletHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


class GenerateChildWalletHandler(BaseHandler):

    async def post(self):
        exkey = BIP32Key.fromExtendedKey(self.config.xprv)
        last_child_key = await self.config.mongo.async_db.child_keys.find_one({'account': self.get_body_argument('account')}, sort=[('inc', -1)])
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
            'account': self.get_body_argument('account'),
            'inc': inc,
            'extended': child_key.ExtendedKey(),
            'public_key': private_key,
            'address': address
        })
        return self.render_as_json({"address": address})


WALLET_HANDLERS = [(r'/wallet', WalletHandler), (r'/generate-wallet', GenerateWalletHandler),
                   (r'/generate-child-wallet', GenerateChildWalletHandler)]
