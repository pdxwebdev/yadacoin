import unittest
from unittest import mock
from unittest.mock import AsyncMock

import yadacoin.core.config
from yadacoin.core.block import Block

from ..test_setup import AsyncTestCase


class TestBlock(AsyncTestCase):
    async def test_init_async(self):
        block = await Block.init_async()
        self.assertIsInstance(block, Block)

    async def test_copy(self):
        block = await Block.init_async()
        block_copy = await block.copy()
        self.assertIsInstance(block_copy, Block)

    async def test_to_dict(self):
        block = await Block.init_async()
        self.assertIsInstance(block.to_dict(), dict)

    async def test_from_dict(self):
        block = await Block.init_async()
        self.assertIsInstance(await Block.from_dict(block.to_dict()), Block)

    async def test_get_coinbase(self):
        block = await Block.init_async()
        coinbase = block.get_coinbase()
        self.assertIsNone(coinbase)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_generate(self, mock_blocks):
        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        self.assertIsInstance(block, Block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_generate_hash_from_header(self, mock_blocks):
        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        block_hash = block.generate_hash_from_header(0, block.header, 0)

        self.assertIsInstance(block_hash, str)
        self.assertTrue(len(block_hash), 64)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_verify(self, mock_blocks):
        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            nonce="0",
        )
        block.hash = block.generate_hash_from_header(0, block.header, "0")
        try:
            await block.verify()
        except Exception:
            from traceback import format_exc

            self.fail(f"verify() raised an exception. {format_exc()}")

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_get_transaction_hashes(self, mock_blocks):
        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            nonce="0",
        )
        self.assertEqual(block.transactions[0].hash, block.get_transaction_hashes()[0])

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_set_merkle_root(self, mock_blocks):
        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            nonce="0",
        )
        block.set_merkle_root(block.get_transaction_hashes())
        self.assertEqual(len(block.merkle_root), 64)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_to_json(self, mock_blocks):
        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            nonce="0",
        )
        self.assertIsInstance(block.to_json(), str)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
