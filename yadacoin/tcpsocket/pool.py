import json
import traceback

import tornado.ioloop
from tornado.iostream import StreamClosedError

from yadacoin.core.transactionutils import TU
from yadacoin.core.config import Config
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import get_config
from yadacoin.tcpsocket.base import RPCSocketServer
from yadacoin.core.miningpool import MiningPool
from yadacoin.core.peer import Miner


class Peer:
    address = ''

    def __init__(self, address):
        self.address = address

    def to_json(self):
        return {
            'address': self.address
        }

class StratumServer(RPCSocketServer):
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
            for stream in StratumServer.inbound_streams[Miner.__name__].values():
                try:
                    await stream.write(
                        '{}\n'.format(json.dumps(rpc_data)).encode()
                    )
                except StreamClosedError:
                    await StratumServer.remove_peer(stream.peer)
                except Exception:
                    cls.config.app_log.warning(traceback.format_exc())

    @classmethod
    async def remove_peer(self, peer):
        if peer in StratumServer.inbound_streams[Miner.__name__]:
            del StratumServer.inbound_streams[Miner.__name__][peer]

    async def getblocktemplate(self, body, stream):
        return await StratumServer.config.mp.block_template()
    
    async def get_info(self, body, stream):
        return await StratumServer.config.mp.block_template()

    async def get_balance(self, body, stream):
        balance = StratumServer.config.BU.get_wallet_balance(StratumServer.config.address)
        return {
            'balance': balance,
            'unlocked_balance': balance
        }
    
    async def getheight(self, body, stream):
        return {
            'height': StratumServer.config.LatestBlock.block.index
        }
    
    async def transfer(self, body, stream):
        for x in body.get('params').get('destinations'):
            result = await TU.send(StratumServer.config, x['address'], x['amount'], from_address=StratumServer.config.address)
            result['tx_hash'] = result['hash']
        return result
    
    async def get_bulk_payments(self, body, stream):
        result =  []
        for y in body.get('params').get('payment_ids'):
            config = Config.generate(prv=y)
            async for x in StratumServer.config.BU.get_wallet_unspent_transactions(config.address):
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
        result = await StratumServer.config.mp.on_miner_nonce(nonce, address=stream.peer.address)
        data = {
            'id': body.get('id'),
            'method': body.get('method'),
            'jsonrpc': body.get('jsonrpc'),
            'result': result
        }
        await stream.write('{}\n'.format(json.dumps(data)).encode())
        await StratumServer.block_checker()

    async def login(self, body, stream):
        if not StratumServer.config:
            StratumServer.config = get_config()
        if not StratumServer.config.mp:
            StratumServer.config.mp = await MiningPool.init_async()
        await StratumServer.block_checker()
        job = await StratumServer.config.mp.block_template()
        stream.peer = Peer(body['params'].get('login'))
        self.config.app_log.info(f'Connected to Miner: {stream.peer.to_json()}')
        StratumServer.inbound_streams[Miner.__name__][stream.peer] = stream
        job['job_id'] = job['blocktemplate_blob']
        job['blob'] = job['blocktemplate_blob']
        result = {
            'id': job['blocktemplate_blob'],
            'job': job
        }
        rpc_data = {
            'id': body.get('id'),
            'method': body.get('method'),
            'jsonrpc': body.get('jsonrpc'),
            'result': result
        }
        await stream.write('{}\n'.format(json.dumps(rpc_data)).encode())
    
    @classmethod
    async def status(self):
        return {
            'miners': len(StratumServer.inbound_streams[Miner.__name__].keys())
        }
