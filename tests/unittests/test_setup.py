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

module_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(module_path, "../../"))

from random import randrange
from unittest import (
    IsolatedAsyncioTestCase,  # python 3.8 requiredsudo apt install python3.8,
)

import tornado
from tornado import testing

from yadacoin.app import NodeApplication
from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.blockchainutils import BlockChainUtils
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.mongo import Mongo

# Block id Mongo.__init__ inserts when index 516355 is missing.  The blocks
# collection has a unique index on ``id``; a full wipe (or an orphan doc that
# still holds this id at a different height) makes the seed insert raise
# DuplicateKeyError.  Tests that construct Mongo() must tolerate that race.
_MONGO_SEED_BLOCK_ID = (
    "MEUCIQC5J3qKoR6QF5e7h9DmWMB/OU+x+ApASqkykx77FRfdowIgeF+fxe9tudwzZKiJBMTN"
    "29XdE64Tf95Y4U0pQoNF04o="
)
_MONGO_SEED_BLOCK_INDEX = 516355


def ensure_test_mongo():
    """Return a usable ``Mongo`` instance for unit tests.

    Prefer the existing ``Config().mongo`` when it is already a ``Mongo``.
    Otherwise construct one, recovering from the known block-516355 seed
    DuplicateKeyError by clearing the colliding seed id/index and retrying.
    """
    from pymongo.errors import DuplicateKeyError

    c = Config()
    existing = getattr(c, "mongo", None)
    if isinstance(existing, Mongo):
        return existing

    def _clear_seed_collision():
        # Use a bare client so we do not recurse through Mongo.__init__.
        from pymongo import MongoClient

        db_name = getattr(c, "database", None) or "yadacoin"
        client = MongoClient()
        try:
            client[db_name].blocks.delete_many(
                {
                    "$or": [
                        {"id": _MONGO_SEED_BLOCK_ID},
                        {"index": _MONGO_SEED_BLOCK_INDEX},
                    ]
                }
            )
        finally:
            client.close()

    try:
        c.mongo = Mongo()
    except DuplicateKeyError:
        _clear_seed_collision()
        c.mongo = Mongo()
    return c.mongo


class AsyncTestCase(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        c = Config()
        c.network = "regnet"
        c.mongo = ensure_test_mongo()
        c.mongo_debug = True
        if c.BU is None:
            c.BU = BlockChainUtils()

        # Config is a process-wide singleton shared by every test in the
        # session. Individual tests frequently reassign attributes on it
        # (e.g. public_key, network, username) without restoring them,
        # which silently poisons unrelated tests that run later in the same
        # session/full-suite run. Snapshot the known-good baseline set up
        # above and restore it unconditionally after each test so tests
        # remain isolated regardless of run order.
        snapshot = dict(vars(c))

        def _restore_config():
            c.__dict__.clear()
            c.__dict__.update(snapshot)

        self.addAsyncCleanup(_restore_config)


class BaseTestCase(testing.AsyncHTTPTestCase):
    def get_new_ioloop(self):
        return tornado.ioloop.IOLoop.current()

    def get_app(self):
        return NodeApplication(test=True)

    async def create_fork_block(self):
        return await Block.generate(
            self._app.config,
            [],
            self._app.config.public_key,
            self._app.config.private_key,
            index=124499,
            force_version=4,
            nonce=1,
            prev_hash="",
            target=CHAIN.MAX_TARGET,
        )

    async def create_blockchain(self, start_index, num_blocks, fork_block):
        blocks = []

        for i in range(num_blocks):
            if i == 0:
                block = await Block.generate(
                    self._app.config,
                    [],
                    self._app.config.public_key,
                    self._app.config.private_key,
                    index=start_index,
                    force_version=4,
                    nonce=randrange(1, 1000000),
                    target=CHAIN.MAX_TARGET - 1,
                    prev_hash=fork_block.hash,
                )
            else:
                block = await Block.generate(
                    self._app.config,
                    [],
                    self._app.config.public_key,
                    self._app.config.private_key,
                    index=start_index + i,
                    force_version=4,
                    nonce=randrange(1, 1000000),
                    target=CHAIN.MAX_TARGET - 1,
                    prev_hash=block.hash,
                )
            blocks.append(block)

        return await Blockchain.init_async(blocks, partial=True)

    async def sort_blockchains_by_difficulty(self, *args):
        return [
            x["blockchain"]
            for x in sorted(
                [
                    {"blockchain": x, "difficulty": await x.get_difficulty()}
                    for x in args
                ],
                key=lambda bc: bc["difficulty"],
            )
        ]
