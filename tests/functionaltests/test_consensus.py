"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os
import sys
import unittest

parent_dir = os.path.abspath(
    os.path.join(
        os.path.dirname(os.path.realpath(__file__)), os.pardir, os.pardir, os.pardir
    )
)
sys.path.insert(0, parent_dir)
parent_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, os.pardir)
)
sys.path.insert(0, parent_dir)
parent_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir)
)
sys.path.insert(0, parent_dir)

from test_setup import BaseTestCase
from tornado.testing import gen_test

# Scenerios:
#
# Upper line represents local blockchain
# Lower line represents remote blockchain
#
# 1. One block ahead, no fork
# _
#  \
#
# 2. Same height, fork, one block
# __
#  \
#
# 3. Two blocks ahead, no fork
# _
#  \_
#
# 4. Same height, fork, two blocks
# ___
#  \_
#
### Should fail ###
#
# 5. One block behind, fork
# ___
#  \
#
# 6. Same height, fork, lower diff
# ___
#  \_
#


class TestConsensus(BaseTestCase):
    @gen_test
    async def test_scenerio_1(self):
        """One block ahead, no fork"""

        fork_block = await self.create_fork_block()

        sorted_blockchains = await self.sort_blockchains_by_difficulty(
            *[
                await self.create_blockchain(124500, 0, fork_block),
                await self.create_blockchain(124500, 1, fork_block),
            ]
        )

        result = await self._app.config.consensus.test_chain_insertable(
            fork_block,
            sorted_blockchains[0],
            sorted_blockchains[1],
        )
        self.assertTrue(result)

    @gen_test
    async def test_scenerio_2(self):
        """Same height, fork, one block"""

        fork_block = await self.create_fork_block()

        sorted_blockchains = await self.sort_blockchains_by_difficulty(
            *[
                await self.create_blockchain(124500, 1, fork_block),
                await self.create_blockchain(124500, 1, fork_block),
            ]
        )

        result = await self._app.config.consensus.test_chain_insertable(
            fork_block,
            sorted_blockchains[0],
            sorted_blockchains[1],
        )
        self.assertTrue(result)

    @gen_test
    async def test_scenerio_3(self):
        """Two blocks ahead, no fork"""

        fork_block = await self.create_fork_block()

        sorted_blockchains = await self.sort_blockchains_by_difficulty(
            *[
                await self.create_blockchain(124500, 0, fork_block),
                await self.create_blockchain(124500, 2, fork_block),
            ]
        )

        result = await self._app.config.consensus.test_chain_insertable(
            fork_block,
            sorted_blockchains[0],
            sorted_blockchains[1],
        )
        self.assertTrue(result)

    @gen_test
    async def test_scenerio_4(self):
        """Same height, fork, two blocks"""

        fork_block = await self.create_fork_block()

        sorted_blockchains = await self.sort_blockchains_by_difficulty(
            *[
                await self.create_blockchain(124500, 2, fork_block),
                await self.create_blockchain(124500, 2, fork_block),
            ]
        )

        result = await self._app.config.consensus.test_chain_insertable(
            fork_block,
            sorted_blockchains[0],
            sorted_blockchains[1],
        )
        self.assertTrue(result)

    @gen_test
    async def test_scenerio_5(self):
        """One block behind, fork"""

        fork_block = await self.create_fork_block()

        result = await self._app.config.consensus.test_chain_insertable(
            fork_block,
            await self.create_blockchain(124500, 2, fork_block),
            await self.create_blockchain(124500, 1, fork_block),
        )

        self.assertFalse(result)

    @gen_test
    async def test_scenerio_6(self):
        """Same height, fork, lower diff"""

        fork_block = await self.create_fork_block()

        sorted_blockchains = await self.sort_blockchains_by_difficulty(
            *[
                await self.create_blockchain(124500, 1, fork_block),
                await self.create_blockchain(124500, 1, fork_block),
            ]
        )

        result = await self._app.config.consensus.test_chain_insertable(
            fork_block,
            sorted_blockchains[1],
            sorted_blockchains[0],
        )
        self.assertFalse(result)

    @gen_test
    async def test_integrate_remote_chain_with_existing_chain(self):
        fork_block = await self.create_fork_block()

        sorted_blockchains = await self.sort_blockchains_by_difficulty(
            *[
                await self.create_blockchain(124500, 5, fork_block),
                await self.create_blockchain(124500, 5, fork_block),
            ]
        )

        first_remote_block = await sorted_blockchains[1].get_block(0, 1)
        first_local_block = await sorted_blockchains[0].get_block(0, 1)

        await self._app.config.consensus.integrate_remote_chain_with_existing_chain(
            sorted_blockchains[0]
        )

        result = await self._app.config.mongo.async_db.blocks.find_one()
        self.assertEqual(result["hash"], first_local_block.hash)

        result = (
            await self._app.config.consensus.integrate_remote_chain_with_existing_chain(
                sorted_blockchains[1]
            )
        )
        self.assertTrue(result)

        result = await self._app.config.mongo.async_db.blocks.find_one()
        self.assertEqual(result["hash"], first_remote_block.hash)
        self.assertNotEqual(result["hash"], first_local_block.hash)

    @gen_test
    async def test_build_local_chain(self):
        fork_block = await self.create_fork_block()

        sorted_blockchains = await self.sort_blockchains_by_difficulty(
            *[
                await self.create_blockchain(124500, 5, fork_block),
                await self.create_blockchain(124500, 5, fork_block),
            ]
        )

        first_local_block = await sorted_blockchains[0].get_block(0, 1)
        first_remote_block = await sorted_blockchains[1].get_block(0, 1)

        await self._app.config.consensus.integrate_remote_chain_with_existing_chain(
            sorted_blockchains[0]
        )
        local_chain = await self._app.config.consensus.build_local_chain(
            first_remote_block
        )
        local_block = await local_chain.get_block(0, 1)
        self.assertEqual(local_block.hash, first_local_block.hash)

    @gen_test
    async def test_build_remote_chain(self):
        fork_block = await self.create_fork_block()

        sorted_blockchains = await self.sort_blockchains_by_difficulty(
            *[
                await self.create_blockchain(124500, 5, fork_block),
                await self.create_blockchain(124500, 5, fork_block),
            ]
        )

        first_remote_block = await sorted_blockchains[1].get_block(0, 1)
        async for block in sorted_blockchains[1].blocks:
            self._app.config.mongo.async_db.consensus.replace_one(
                {"index": block.index, "id": block.signature}, block.to_dict()
            )
        remote_chain = await self._app.config.consensus.build_remote_chain(
            first_remote_block
        )
        remote_block = await remote_chain.get_block(0, 1)
        self.assertEqual(remote_block.hash, first_remote_block.hash)


if "__main__" == __name__:
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
