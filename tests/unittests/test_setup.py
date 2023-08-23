import sys

sys.path.append("../../")
from random import randrange
from unittest import (
    IsolatedAsyncioTestCase,  # python 3.8 requiredsudo apt install python3.8,
)
from unittest import mock

import tornado
from mongomock import MongoClient
from tornado import testing

import yadacoin.core.config
from yadacoin.app import NodeApplication
from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config, get_config


class AsyncTestCase(IsolatedAsyncioTestCase):
    @mock.patch(
        "yadacoin.core.blockchain.Blockchain.mongo", new_callable=lambda: MongoClient
    )
    async def asyncSetUp(self, mongo):
        mongo.async_db = mock.MagicMock()
        mongo.async_db.blocks = mock.MagicMock()
        yadacoin.core.config.CONFIG = Config.generate()
        get_config().mongo = mongo


class BaseTestCase(testing.AsyncHTTPTestCase):
    def get_new_ioloop(self):
        return tornado.ioloop.IOLoop.current()

    def get_app(self):
        return NodeApplication()

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
