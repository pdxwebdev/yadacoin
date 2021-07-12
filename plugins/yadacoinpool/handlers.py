import os
import time
import requests
from tornado.web import Application, StaticFileHandler
from yadacoin.http.base import BaseHandler
from yadacoin.core.chain import CHAIN


class BaseWebHandler(BaseHandler):

    def prepare(self):

        if self.request.protocol == 'http' and self.config.ssl:
            self.redirect('https://' + self.request.host + self.request.uri, permanent=False)

    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), 'templates')


class PoolStatsInterfaceHandler(BaseWebHandler):
    async def get(self):
        self.render(
            'pool-stats.html',
            yadacoin=self.yadacoin_vars,
            username_signature=self.get_secure_cookie("username_signature"),
            username=self.get_secure_cookie("username"),
            rid=self.get_secure_cookie("rid"),
            title='YadaCoin - Pool Stats',
            mixpanel='pool stats page'
        )


class PoolInfoHandler(BaseWebHandler):
    async def get(self):
        def get_ticker():
            return requests.get('https://safe.trade/api/v2/peatio/public/markets/tickers')
        
        try:
            if not hasattr(self.config, 'ticker'):
                self.config.ticker = get_ticker()
                self.config.last_update = time.time()
            if (time.time() - self.config.last_update) > (600 * 6):
                self.config.ticker = get_ticker()
                self.config.last_update = time.time()
            last_btc = self.config.ticker.json()['ydabtc']['ticker']['last']
        except:
            last_btc = 0
        await self.config.LatestBlock.block_checker()
        pool_public_key = self.config.pool_public_key if hasattr(self.config, 'pool_public_key') else self.config.public_key
        total_blocks_found = await self.config.mongo.async_db.blocks.count_documents(
            {
                'public_key': pool_public_key
            }
        )

        expected_blocks = 144
        pool_blocks_found = self.config.mongo.async_db.blocks.find(
            {
                'public_key': pool_public_key,
                'time': {'$gte': time.time() - ( 600 * 144 )}
            },
            {
                '_id': 0
            }
        ).sort([('index', -1)])
        expected_blocks = 144
        pool_blocks_found_list = await pool_blocks_found.to_list(length=expected_blocks)
        if len(pool_blocks_found_list) > 0:
            avg_target = 0
            for block in pool_blocks_found_list:
                avg_target += int(block['target'], 16)
            avg_target = avg_target / len(pool_blocks_found_list)
            difficulty = 0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffff / avg_target
            pool_hash_rate = ((len(pool_blocks_found_list)/expected_blocks)*difficulty * 2**32 / 600)
        else:
            pool_hash_rate = 0

        net_blocks_found = self.config.mongo.async_db.blocks.find({'time': {'$gte': time.time() - ( 600 * 144 )}})
        net_blocks_found = await net_blocks_found.to_list(length=expected_blocks*10)
        if len(net_blocks_found) > 0:
            avg_net_target = 0
            for block in net_blocks_found:
                avg_net_target += int(block['target'], 16)
            avg_net_target = avg_net_target / len(net_blocks_found)
            net_difficulty = 0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffff / avg_net_target
            network_hash_rate = ((len(net_blocks_found)/expected_blocks)*net_difficulty * 2**32 / 600)
        else:
            net_difficulty = 0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffff / 0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffff
            network_hash_rate = 0

        miner_count_pool_stat = await self.config.mongo.async_db.pool_stats.find_one({'stat': 'miner_count'})
        worker_count_pool_stat = await self.config.mongo.async_db.pool_stats.find_one({'stat': 'worker_count'})
        payouts = await self.config.mongo.async_db.share_payout.find({}, {'_id': 0}).sort([('index', -1)]).to_list(100)
        self.render_as_json({
            'pool': {
                'hashes_per_second': pool_hash_rate,
                'miner_count': miner_count_pool_stat['value'],
                'worker_count': worker_count_pool_stat['value'],
                'payout_scheme': 'PPLNS',
                'pool_fee': self.config.pool_take,
                'min_payout': 0,
                'url': getattr(self.config, 'pool_url', f'{self.config.peer_host}:{self.config.stratum_pool_port}'),
                'last_five_blocks': [{'timestamp': x['time'], 'height': x['index']} for x in pool_blocks_found_list[:5]],
                'blocks_found': total_blocks_found,
                'fee': self.config.pool_take,
                'payout_frequency': self.config.payout_frequency,
                'payouts': payouts,
                'blocks': pool_blocks_found_list[:100]
            },
            'network': {
                'height': self.config.LatestBlock.block.index,
                'reward': CHAIN.get_block_reward(self.config.LatestBlock.block.index),
                'last_block': self.config.LatestBlock.block.time,
                'hashes_per_second': network_hash_rate,
                'difficulty': net_difficulty
            },
            'market': {
                'last_btc': last_btc
            },
            'coin': {
                'algo': 'randomx YDA',
                'circulating': self.config.LatestBlock.block.index * 50,
                'max_supply': 21000000
            }
        })


HANDLERS = [
    (r'/pool-info', PoolInfoHandler),
    (r'/', PoolStatsInterfaceHandler),
    (r'/yadacoinpoolstatic/(.*)', StaticFileHandler, {"path": os.path.join(os.path.dirname(__file__), 'static')}),
]
