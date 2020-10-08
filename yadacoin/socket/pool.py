import json

import tornado.ioloop

from yadacoin.core.transactionutils import TU
from yadacoin.core.config import Config
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import get_config
from yadacoin.socket.base import RPCSocketServer


class StratumServer(RPCSocketServer):
    address = ''
    current_index = 0
    config = None

    @classmethod
    async def block_checker(cls):
        if not cls.config:
            cls.config = get_config()
        if cls.current_index != cls.config.LatestBlock.block.index:
            job = await cls.config.mp.block_template()
            job['job_id'] = job['blocktemplate_blob']
            job['blob'] = job['blocktemplate_blob']
            cls.current_index = cls.config.LatestBlock.block.index
            result = {
                'id': job['blocktemplate_blob'],
                'job': job
            }
            rpc_data = {
                'id': 1,
                'method': 'login',
                'jsonrpc': 2.0,
                'result': result
            }
            for stream in cls.streams:
                if 'miner' in stream.peer.roles:
                    await stream.write('{}\n'.format(json.dumps(rpc_data)).encode())

    async def getblocktemplate(self, body, stream):
        return await self.config.mp.block_template()
    
    async def get_info(self, body, stream):
        return await self.config.mp.block_template()

    async def get_balance(self, body, stream):
        balance = self.config.BU.get_wallet_balance(self.config.address)
        return {
            'balance': balance,
            'unlocked_balance': balance
        }
    
    async def getheight(self, body, stream):
        return {
            'height': self.config.LatestBlock.block.index
        }
    
    async def transfer(self, body, stream):
        for x in body.get('params').get('destinations'):
            result = await TU.send(self.config, x['address'], x['amount'], from_address=self.config.address)
            result['tx_hash'] = result['hash']
        return result
    
    async def get_bulk_payments(self, body, stream):
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
        return result

    async def submit(self, body, stream):
        nonce = body['params'].get('nonce')
        if type(nonce) is not str:
            result = {'error': True, 'message': 'nonce is wrong data type'}
        if len(nonce) > CHAIN.MAX_NONCE_LEN:
            result = {'error': True, 'message': 'nonce is too long'}
        result = await self.config.mp.on_miner_nonce(nonce, address=stream.address)
        if not result:
            result = {'error': True, 'message': 'nonce rejected'}
        return result

    async def login(self, body, stream):
        job = await self.config.mp.block_template()
        stream.address = body['params'].get('login')
        job['job_id'] = job['blocktemplate_blob']
        job['blob'] = job['blocktemplate_blob']
        result = {
            'id': job['blocktemplate_blob'],
            'job': job
        }
        return result
