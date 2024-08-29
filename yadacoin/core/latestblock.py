import time

from yadacoin.core.config import Config
from yadacoin.core.chain import CHAIN


class LatestBlock:
    config = None
    block = None
    blocktemplate_target = None
    blocktemplate_time = None
    blocktemplate_index = None
    blocktemplate_hash = None

    @classmethod
    async def set_config(cls):
        cls.config = Config()

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

    @classmethod
    async def get_block_template(cls):
        from yadacoin.core.block import Block
        if not cls.block:
            await cls.update_latest_block()

        if cls.block:
            try:
                #cls.config.app_log.info(f"Block version: {cls.block.version}")
                #cls.config.app_log.info(f"Block hash: {cls.block.hash}")
                #cls.config.app_log.info(f"Block index: {cls.block.index}")
                #cls.config.app_log.info(f"Block time: {cls.block.time}")
                #cls.config.app_log.info(f"Block transactions: {cls.block.transactions}")

                if (cls.block.hash != cls.blocktemplate_hash or cls.block.index != cls.blocktemplate_index):
                    cls.blocktemplate_time = int(time.time())

                    new_block = await Block.init_async(
                        version=cls.block.version,
                        block_time=cls.blocktemplate_time,
                        block_index=cls.block.index + 1,
                        prev_hash=cls.block.hash,
                    )

                    cls.blocktemplate_target = await CHAIN.get_target_10min(cls.block, new_block)

                    cls.blocktemplate_index = cls.block.index
                    cls.blocktemplate_hash = cls.block.hash

                target_hex = hex(cls.blocktemplate_target)[2:].rjust(64, '0')

                return {
                    "version": cls.block.version,
                    "prev_hash": cls.block.hash,
                    "index": cls.block.index,
                    "target": target_hex,
                    "time": cls.blocktemplate_time
                }
            except Exception as e:
                cls.config.app_log.error(f"Error calculating block template: {e}")
                raise e
        else:
            cls.config.app_log.error("No block found when trying to get block template.")
        return None