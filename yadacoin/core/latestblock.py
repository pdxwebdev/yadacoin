import json

from yadacoin.core.config import get_config


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
        from yadacoin.core.block import Block

        block = await cls.config.mongo.async_db.blocks.find_one(
            {}, {"_id": 0}, sort=[("index", -1)]
        )
        if not block:
            await cls.config.BU.insert_genesis()
            return
        cls.block = await Block.from_dict(block)

    @classmethod
    async def get_latest_block(cls):
        from yadacoin.core.block import Block

        block = await cls.config.mongo.async_db.blocks.find_one(
            {}, {"_id": 0}, sort=[("index", -1)]
        )
        if block:
            return await Block.from_dict(block)
        else:
            cls.block = None
