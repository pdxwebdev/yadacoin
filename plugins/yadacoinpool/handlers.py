import os
import time
import requests
from tornado.web import Application, StaticFileHandler
from yadacoin.http.base import BaseHandler
from yadacoin.core.chain import CHAIN
from yadacoin import version


class BaseWebHandler(BaseHandler):

    def prepare(self):

        if self.request.protocol == 'http' and self.config.ssl.is_valid():
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
        pool_blocks_found_list = await self.config.mongo.async_db.blocks.find(
            {
                'public_key': pool_public_key,
                'time': {'$gte': time.time() - ( 600 * 144 )}
            },
            {
                '_id': 0
            }
        ).sort([('index', -1)]).to_list(100)
        mining_time_interval = 600
        shares_count = await self.config.mongo.async_db.shares.count_documents({'time': {'$gte': time.time() - mining_time_interval}})
        if shares_count > 0:
            pool_hash_rate = (shares_count * self.config.pool_diff) / mining_time_interval
        else:
            pool_hash_rate = 0

        daily_blocks_found = await self.config.mongo.async_db.blocks.count_documents({'time': {'$gte': time.time() - (600 * 144)}})
        if daily_blocks_found > 0:
            net_target = self.config.LatestBlock.block.target
        avg_blocks_found = self.config.mongo.async_db.blocks.find({'time': {'$gte': time.time() - ( 600 * 12)}})
        avg_blocks_found = await avg_blocks_found.to_list(length=600 * 12)
        if len(avg_blocks_found) > 0:
            avg_net_target = 0
            for block in avg_blocks_found:
                avg_net_target += int(block['target'], 16)
            avg_net_target = avg_net_target / len(avg_blocks_found)
            avg_net_difficulty = int(0x0000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff) / int(avg_net_target)
            net_difficulty = int(0x0000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff) / int(net_target)
            network_hash_rate = ((daily_blocks_found / expected_blocks) * avg_net_difficulty * 2**48 / int(0x100000000) / 600)
        else:
            net_difficulty = 0x0000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff / 0x0000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
            network_hash_rate = 0

        miner_count_pool_stat = await self.config.mongo.async_db.pool_stats.find_one({'stat': 'miner_count'}) or {'value': 0}
        worker_count_pool_stat = await self.config.mongo.async_db.pool_stats.find_one({'stat': 'worker_count'}) or {'value': 0}
        payouts = await self.config.mongo.async_db.share_payout.find({}, {'_id': 0}).sort([('index', -1)]).to_list(100)
        self.render_as_json({
            'node': {
                'latest_block': self.config.LatestBlock.block.to_dict(),
                'health': self.config.health.to_dict(),
                'version': '.'.join([str(x) for x in version]),
            },
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
                'circulating': CHAIN.get_circulating_supply(self.config.LatestBlock.block.index),
                'max_supply': 21000000
            }
        })


HANDLERS = [
    (r'/pool-info', PoolInfoHandler),
    (r'/', PoolStatsInterfaceHandler),
    (r'/yadacoinpoolstatic/(.*)', StaticFileHandler, {"path": os.path.join(os.path.dirname(__file__), 'static')}),
]
