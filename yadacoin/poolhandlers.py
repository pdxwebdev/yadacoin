"""
Handlers required by the pool operations
"""
import json
from yadacoin.basehandlers import BaseHandler
from yadacoin.miningpool import MiningPool
from yadacoin.miningpoolpayout import PoolPayer
from yadacoin.transactionutils import TU
from yadacoin.block import Block
from yadacoin.chain import CHAIN
from tornado import escape
from coincurve import PrivateKey, PublicKey
from yadacoin.config import Config


class JSONRPC(BaseHandler):
    async def post(self):
        body = json.loads(self.request.body.decode())
        if body.get('method') == 'getblocktemplate':
            if self.config.mp is None:
                self.config.mp = MiningPool()
            self.render_as_json({
                'id': body.get('id'),
                'method': body.get('method'),
                'jsonrpc': body.get('jsonrpc'),
                'result': await self.config.mp.block_template()
            })
        elif body.get('method') == 'get_balance':
            balance = self.config.BU.get_wallet_balance(self.config.address)
            self.render_as_json({
                'id': body.get('id'),
                'method': body.get('method'),
                'jsonrpc': body.get('jsonrpc'),
                'result': {
                    'balance': balance,
                    'unlocked_balance': balance
                }
            })
        elif body.get('method') == 'getheight':
            self.render_as_json({
                'id': body.get('id'),
                'method': body.get('method'),
                'jsonrpc': body.get('jsonrpc'),
                'result': {'height': self.config.BU.get_latest_block()['index']}
            })
        elif body.get('method') == 'transfer':
            for x in body.get('params').get('destinations'):
                result = await TU.send(self.config, x['address'], x['amount'], from_address=self.config.address)
                result['tx_hash'] = result['hash']
            self.render_as_json({
                'id': body.get('id'),
                'method': body.get('method'),
                'jsonrpc': body.get('jsonrpc'),
                'result': result
            })
        elif body.get('method') == 'get_bulk_payments':
            result =  []
            for y in body.get('params').get('payment_ids'):
                config = Config.generate(prv=y)
                async for x in self.config.BU.get_wallet_unspent_transactions(config.address):
                    txn = {'amount': 0}
                    txn['block_height'] = x['height']
                    for j in x['outputs']:
                        if j['to'] == config.address:
                            txn['amount'] += j['value']
                    if txn['amount']:
                        result.append(txn)
            self.render_as_json({
                'id': body.get('id'),
                'method': body.get('method'),
                'jsonrpc': body.get('jsonrpc'),
                'result': {'payments': result}
            })
        elif body.get('method') == 'submitblock':
            nonce = body.get('nonce')
            address = body.get('wallet_address')
            if type(nonce) is not str:
                return self.render_as_json({
                    'id': body.get('id'),
                    'method': body.get('method'),
                    'jsonrpc': body.get('jsonrpc'),
                    'result': {'n':'Ko'}
                })
            if len(nonce) > CHAIN.MAX_NONCE_LEN:
                return self.render_as_json({
                    'id': body.get('id'),
                    'method': body.get('method'),
                    'jsonrpc': body.get('jsonrpc'),
                    'result': {'n':'Ko'}
                })
            result = await self.config.mp.on_miner_nonce(nonce, address=address)
            if result:
                return self.render_as_json({
                    'id': body.get('id'),
                    'method': body.get('method'),
                    'jsonrpc': body.get('jsonrpc'),
                    'result': result
                })
            else:
                return self.render_as_json({
                    'id': body.get('id'),
                    'method': body.get('method'),
                    'jsonrpc': body.get('jsonrpc'),
                    'result': {'n':'ko'}
                })


POOL_HANDLERS = [
    (r'/json_rpc', JSONRPC),
]
