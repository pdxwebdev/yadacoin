"""
Handlers required by the wallet operations
"""


from yadacoin.basehandlers import BaseHandler


class WalletHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


class GenerateWalletHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


class GenerateChildWalletHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


WALLET_HANDLERS = [(r'/wallet', WalletHandler), (r'/generate-wallet', GenerateWalletHandler),
                   (r'/generate-child-wallet', GenerateChildWalletHandler)]
