"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.latestblock import LatestBlock

from ..test_setup import AsyncTestCase


class TestLatestBlock(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        # Reset LatestBlock state
        LatestBlock.block = None
        LatestBlock.config = None

    async def test_set_config(self):
        await LatestBlock.set_config()
        self.assertIsNotNone(LatestBlock.config)

    async def test_block_checker_no_config_calls_set_config(self):
        LatestBlock.config = None
        # Mock update_latest_block to avoid DB calls
        from unittest.mock import patch

        with patch.object(
            LatestBlock, "update_latest_block", new=AsyncMock()
        ) as mock_update:
            await LatestBlock.block_checker()
            mock_update.assert_called_once()

    async def test_update_latest_block_no_block(self):
        await LatestBlock.set_config()
        # Motor's async_db.blocks returns a new Collection each access;
        # patch async_db itself to control find_one
        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        LatestBlock.config.BU = MagicMock()
        LatestBlock.config.BU.insert_genesis = AsyncMock()
        with patch.object(LatestBlock.config.mongo, "async_db", new=mock_db):
            await LatestBlock.update_latest_block()
        LatestBlock.config.BU.insert_genesis.assert_called_once()

    async def test_update_latest_block_with_block(self):
        from unittest.mock import patch

        from yadacoin.core.block import Block

        await LatestBlock.set_config()
        mock_block_data = {"index": 1, "hash": "abc123", "transactions": []}
        LatestBlock.config.mongo.async_db.blocks.find_one = AsyncMock(
            return_value=mock_block_data
        )
        with patch.object(
            Block, "from_dict", new=AsyncMock(return_value=MagicMock(spec=Block))
        ):
            await LatestBlock.update_latest_block()
            self.assertIsNotNone(LatestBlock.block)

    async def test_get_latest_block_no_block(self):
        await LatestBlock.set_config()
        # Motor's async_db.blocks returns a new Collection each access
        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        with patch.object(LatestBlock.config.mongo, "async_db", new=mock_db):
            result = await LatestBlock.get_latest_block()
        self.assertIsNone(result)
        self.assertIsNone(LatestBlock.block)

    async def test_get_latest_block_with_block(self):
        from unittest.mock import patch

        from yadacoin.core.block import Block

        await LatestBlock.set_config()
        mock_block_data = {"index": 5, "hash": "def456", "transactions": []}
        LatestBlock.config.mongo.async_db.blocks.find_one = AsyncMock(
            return_value=mock_block_data
        )
        mock_block = MagicMock(spec=Block)
        with patch.object(Block, "from_dict", new=AsyncMock(return_value=mock_block)):
            result = await LatestBlock.get_latest_block()
            self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
