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

        app.config.consensus.target = CHAIN.MAX_TARGET

        result = await app.config.consensus.test_chain_insertable(
            local_blocks[-1],
            local_blockchain,
            remote_blocks[-1],
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
        local_blocks = [
            await BlockFactory.generate(
                app.config,
                [],
                app.config.public_key,
                app.config.private_key,
                index=12500,
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

if "__main__" == __name__:
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
