import json

from yadacoin.core.config import get_config
from yadacoin.core.block import Block


class LatestBlock:
    config = None
    block = None
    @classmethod
    async def set_config(cls):
        cls.config = get_config()

    @classmethod
    async def block_checker(cls):
        if not cls.config:
            await cls.set_config()
        await cls.update_latest_block()

    @classmethod
    async def update_latest_block(cls):
        block = await cls.config.BU.get_latest_block()
        if not block:
            cls.config.app_log.critical('get_latest_block failed')
            return
        cls.block = await Block.from_dict(block)

    @classmethod
    async def get_latest_block(cls):
        block = await cls.config.BU.get_latest_block()
        if block:
            return await Block.from_dict(block)
        else:
            cls.block = None
