import unittest
import pyrx
import binascii
import os
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, os.pardir, os.pardir))
sys.path.insert(0, parent_dir)
parent_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, os.pardir))
sys.path.insert(0, parent_dir)
parent_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))
sys.path.insert(0, parent_dir)
from unittest import IsolatedAsyncioTestCase # python 3.8 requiredsudo apt install python3.8
from yadacoin.core.transaction import Transaction
from yadacoin.core.block import BlockFactory
from yadacoin.core.chain import CHAIN
from yadacoin.core.blockchain import Blockchain

from test_setup import app

# Scenerios:
#
# Upper line represents local blockchain
# Lower line represents remote blockchain
#
# 1. Same height, larger diff
#  ________
#  \_______
# 
# 2. Larger diff, smaller height
#  ________
#  \______
# 
# 3. Larger height, smaller diff
#  ________
#  \________
# 
# 4. Chain has error, preceeding blocks have larger diff, same height
#  _____
#  \____e____
# 
# 4. Chain has error, preceeding blocks have larger diff, smaller height
#  _____
#  \__e______
# 
# 4. Chain has error, preceeding blocks have larger diff, greater height
#  _____
#  \______e__
# 


class TestConsensus(IsolatedAsyncioTestCase):
    async def test_test_block_insertable(self):
        """ test the block validation before it is passed to the db
        """
        genesis = await BlockFactory.generate(
            app.config,
            [],
            app.config.public_key,
            app.config.private_key,
            index=124999,
            force_version=4,
            nonce=1,
            prev_hash='',
            target=CHAIN.MAX_TARGET
        )

        app.config.LatestBlock.block = genesis

        bf1 = await BlockFactory.generate(
            app.config,
            [],
            app.config.public_key,
            app.config.private_key,
            index=125000,
            force_version=4,
            nonce=1,
            target=CHAIN.MAX_TARGET -1
        )

        app.config.consensus.target = CHAIN.MAX_TARGET

        result = await app.config.consensus.test_block_insertable(
            genesis,
            bf1
        )
        self.assertTrue(result)

    async def test_block_insertable_fails(self):
        """ this case receives a block that returns false.
            We do not merge it.
        """
        genesis = await BlockFactory.generate(
            app.config,
            [],
            app.config.public_key,
            app.config.private_key,
            index=124999,
            force_version=4,
            nonce=1,
            prev_hash='',
            target=CHAIN.MAX_TARGET
        )

        app.config.LatestBlock.block = genesis

        bf1 = await BlockFactory.generate(
            app.config,
            [],
            app.config.public_key,
            app.config.private_key,
            index=125001, # block is 2 blocks ahead
            force_version=4,
            nonce=1,
            target=CHAIN.MAX_TARGET -1
        )

        app.config.consensus.target = CHAIN.MAX_TARGET

        result = await app.config.consensus.test_block_insertable(
            genesis,
            bf1
        )
        self.assertFalse(result)

    async def test_test_chain_insertable(self):
        """ test the chain validation before it is passed to the db
        """
        local_blocks = [
            await BlockFactory.generate(
                app.config,
                [],
                app.config.public_key,
                app.config.private_key,
                index=124999,
                force_version=4,
                nonce=1,
                prev_hash='',
                target=CHAIN.MAX_TARGET
            )
        ]

        app.config.LatestBlock.block = local_blocks[0]

        rb1 = await BlockFactory.generate(
            app.config,
            [],
            app.config.public_key,
            app.config.private_key,
            index=125000,
            force_version=4,
            nonce=1,
            target=CHAIN.MAX_TARGET - 1
        )
        rb2 = await BlockFactory.generate(
            app.config,
            [],
            app.config.public_key,
            app.config.private_key,
            index=125001,
            force_version=4,
            nonce=1,
            target=CHAIN.MAX_TARGET - 1,
            prev_hash=rb1.hash
        )
        remote_blocks = [rb1, rb2]

        local_blockchain = await Blockchain.init_async(local_blocks, partial=True)

        remote_blockchain = await Blockchain.init_async(remote_blocks, partial=True)

        result = await app.config.consensus.test_chain_insertable(
            local_blockchain,
            remote_blockchain,
        )
        self.assertTrue(result)

    async def test_external_consecutive_merge(self):
        """ this case receives a block at the next block height.
            We merge it.
        """
        genesis = await BlockFactory.generate(
            app.config,
            [],
            app.config.public_key,
            app.config.private_key,
            index=124999,
            force_version=4,
            nonce=1,
            prev_hash='',
            target=CHAIN.MAX_TARGET
        )

        app.config.LatestBlock.block = genesis

        bf1 = await BlockFactory.generate(
            app.config,
            [],
            app.config.public_key,
            app.config.private_key,
            index=125000,
            force_version=4,
            nonce=1,
            target=CHAIN.MAX_TARGET -1
        )

        app.config.consensus.target = CHAIN.MAX_TARGET

        result = await app.config.consensus.test_block_insertable(
            genesis,
            bf1
        )
        self.assertTrue(result)

    async def test_external_future_block_consecutive_merge(self):
        """ this case receives a future block and the chain 
            running up to it starts at our current height. 
            The chain difficulty is greater than ours. 
            We merge it.
        """
        local_blocks = [
            await BlockFactory.generate(
                app.config,
                [],
                app.config.public_key,
                app.config.private_key,
                index=124999,
                force_version=4,
                nonce=1,
                prev_hash='',
                target=CHAIN.MAX_TARGET
            )
        ]

        app.config.LatestBlock.block = local_blocks[0]

        rb1 = await BlockFactory.generate(
            app.config,
            [],
            app.config.public_key,
            app.config.private_key,
            index=124999,
            force_version=4,
            nonce=1,
            target=CHAIN.MAX_TARGET - 1
        )
        rb2 = await BlockFactory.generate(
            app.config,
            [],
            app.config.public_key,
            app.config.private_key,
            index=125000,
            force_version=4,
            nonce=1,
            target=CHAIN.MAX_TARGET - 1,
            prev_hash=rb1.hash
        )
        remote_blocks = [rb1, rb2]

        local_blockchain = await Blockchain.init_async(local_blocks, partial=True)

        remote_blockchain = await Blockchain.init_async(remote_blocks, partial=True)

        app.config.consensus.target = CHAIN.MAX_TARGET

        result = await app.config.consensus.test_chain_insertable(
            local_blocks[-1],
            local_blockchain,
            remote_blocks[-1],
            remote_blockchain,
        )
        self.assertTrue(result)
    
    async def test_external_future_block_backtrace_merge(self):
        """ this case receives a future block and the chain 
            running up to it starts at a height below our 
            current height. The chain difficulty is greater 
            than ours. We merge it.
        """

        genesis = await BlockFactory.generate(
            app.config,
            [],
            app.config.public_key,
            app.config.private_key,
            index=124499,
            force_version=4,
            nonce=1,
            prev_hash='',
            target=CHAIN.MAX_TARGET
        )

        sorted_blockchains = await self.sort_blockchains_by_difficulty(*[
            await self.create_blockchain(124500, 5, genesis),
            await self.create_blockchain(124500, 5, genesis)
        ])

        result = await app.config.consensus.test_chain_insertable(
            genesis,
            sorted_blockchains[0],
            sorted_blockchains[1],
        )
        self.assertTrue(result)
    
    async def test_external_future_block_backtrace_with_block_failure_merge(self):
        """ this case receives a future block and the chain 
            running up to it starts at a height below our 
            current height. The chain difficulty is greater 
            than ours but a block in that chain raises an exeption.
            The chain should be shortened and tested again upto
            but not including the block raising the exception. If that
            chain results in greater difficulty than our own, merge it.
        """
        pass
    
    async def create_blockchain(self, start_index, num_blocks, genesis):
        blocks = []

        for i in range(num_blocks):
            if i == 0:
                block = await BlockFactory.generate(
                    app.config,
                    [],
                    app.config.public_key,
                    app.config.private_key,
                    index=start_index,
                    force_version=4,
                    nonce=1,
                    target=CHAIN.MAX_TARGET - 1,
                    prev_hash=genesis.hash
                )
            else:
                block = await BlockFactory.generate(
                    app.config,
                    [],
                    app.config.public_key,
                    app.config.private_key,
                    index=start_index + i,
                    force_version=4,
                    nonce=1,
                    target=CHAIN.MAX_TARGET - 1,
                    prev_hash=block.hash
                )
            blocks.append(block)

        return await Blockchain.init_async(blocks, partial=True)
    
    async def sort_blockchains_by_difficulty(self, *args):
        return [x['blockchain'] for x in sorted([
            {
                'blockchain': x, 
                'difficulty': await x.get_difficulty()
            } for x in args
        ], key=lambda bc: bc['difficulty'])]

if "__main__" == __name__:
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
