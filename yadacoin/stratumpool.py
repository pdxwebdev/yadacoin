import json
import tornado.ioloop
from tornado.tcpserver import TCPServer
from tornado.iostream import StreamClosedError
from yadacoin.config import get_config, Config
from yadacoin.chain import CHAIN
from yadacoin.miningpool import MiningPool
from yadacoin.transactionutils import TU


class StratumServer(TCPServer):
    address = ''
    stream_set = set()
    @classmethod
    async def set_config(cls):
        cls.config = get_config()
        if cls.config.mp is None:
            cls.config.mp = MiningPool()
            cls.current_index = cls.config.mp.index

    @classmethod
    async def block_checker(cls):
        if not hasattr(cls, 'config'):
            await cls.set_config()
        if cls.current_index != cls.config.mp.index:
            job = await cls.config.mp.block_template()
            job['job_id'] = job['blocktemplate_blob']
            job['blob'] = job['blocktemplate_blob']
            data = json.dumps({
                'id': 1,
                'method': 'getblocktemplate',
                'jsonrpc': 2.0,
                'result': {
                    'id': job['blocktemplate_blob'],
                    'job': job
                }
            })
            cls.current_index = StratumServer.config.mp.index
            to_delete = []
            for stream in cls.stream_set:
                if stream.closed():
                    to_delete.append(stream)
                else:
                    await stream.write('{}\n'.format(data).encode())
            for stream in to_delete:
                cls.stream_set.remove(stream)

    async def handle_stream(self, stream, address):
        if not hasattr(StratumServer, 'config'):
            await StratumServer.set_config()
        StratumServer.stream_set.add(stream)
        while True:
            try:
                body = json.loads(await stream.read_until(b"\n"))
                if body.get('method') == 'getblocktemplate':
                    data = json.dumps({
                        'id': body.get('id'),
                        'method': body.get('method'),
                        'jsonrpc': body.get('jsonrpc'),
                        'result': await StratumServer.config.mp.block_template()
                    })
                elif body.get('method') == 'get_info':
                    if StratumServer.config.mp is None:
                        StratumServer.config.mp = MiningPool()
                    data = json.dumps({
                        'id': body.get('id'),
                        'method': body.get('method'),
                        'jsonrpc': body.get('jsonrpc'),
                        'result': await StratumServer.config.mp.block_template()
                    })
                elif body.get('method') == 'get_balance':
                    balance = StratumServer.config.BU.get_wallet_balance(StratumServer.config.address)
                    data = json.dumps({
                        'id': body.get('id'),
                        'method': body.get('method'),
                        'jsonrpc': body.get('jsonrpc'),
                        'result': {
                            'balance': balance,
                            'unlocked_balance': balance
                        }
                    })
                elif body.get('method') == 'getheight':
                    data = json.dumps({
                        'id': body.get('id'),
                        'method': body.get('method'),
                        'jsonrpc': body.get('jsonrpc'),
                        'result': {'height': StratumServer.config.BU.get_latest_block()['index']}
                    })
                elif body.get('method') == 'transfer':
                    for x in body.get('params').get('destinations'):
                        result = await TU.send(StratumServer.config, x['address'], x['amount'], from_address=StratumServer.config.address)
                        result['tx_hash'] = result['hash']
                    data = json.dumps({
                        'id': body.get('id'),
                        'method': body.get('method'),
                        'jsonrpc': body.get('jsonrpc'),
                        'result': result
                    })
                elif body.get('method') == 'get_bulk_payments':
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
                    data = json.dumps({
                        'id': body.get('id'),
                        'method': body.get('method'),
                        'jsonrpc': body.get('jsonrpc'),
                        'result': {'payments': result}
                    })
                elif body.get('method') == 'submit':
                    nonce = body['params'].get('nonce')
                    if type(nonce) is not str:
                        data = json.dumps({
                            'id': body.get('id'),
                            'method': body.get('method'),
                            'jsonrpc': body.get('jsonrpc'),
                            'result': {'n':'Ko'}
                        })
                    if len(nonce) > CHAIN.MAX_NONCE_LEN:
                        data = json.dumps({
                            'id': body.get('id'),
                            'method': body.get('method'),
                            'jsonrpc': body.get('jsonrpc'),
                            'result': {'n':'Ko'}
                        })
                    result = await StratumServer.config.mp.on_miner_nonce(nonce, address=self.address)
                    if result:
                        data = json.dumps({
                            'id': body.get('id'),
                            'method': body.get('method'),
                            'jsonrpc': body.get('jsonrpc'),
                            'result': result
                        })
                    else:
                        data = json.dumps({
                            'id': body.get('id'),
                            'method': body.get('method'),
                            'jsonrpc': body.get('jsonrpc'),
                            'result': {'n':'ko'}
                        })
                elif body.get('method') == 'login':
                    job = await StratumServer.config.mp.block_template()
                    self.address = body['params'].get('login')
                    job['job_id'] = job['blocktemplate_blob']
                    job['blob'] = job['blocktemplate_blob']
                    data = json.dumps({
                        'id': body.get('id'),
                        'method': body.get('method'),
                        'jsonrpc': body.get('jsonrpc'),
                        'result': {
                            'id': job['blocktemplate_blob'],
                            'job': job
                        }
                    })
                else:
                    data = {}
                
                await stream.write('{}\n'.format(data).encode())
            except StreamClosedError:
                break