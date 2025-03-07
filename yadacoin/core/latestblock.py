"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import time

from yadacoin.core.config import Config


class LatestBlock:
    config = None
    block = None
    blocktemplate_target = None
    blocktemplate_time = None
    blocktemplate_index = None
    blocktemplate_hash = None
    cached_transactions = []


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
        from yadacoin.core.transaction import Transaction

        if not cls.block:
            await cls.update_latest_block()

        if cls.block:
            try:
                current_time = int(time.time())

                if (cls.block.hash != cls.blocktemplate_hash or cls.block.index != cls.blocktemplate_index or
                    current_time - cls.blocktemplate_time > 900):

                    cls.blocktemplate_time = current_time

                    transactions_raw = await cls.config.mongo.async_db.miner_transactions.find().to_list(length=None)
                    transactions = [Transaction.ensure_instance(txn) for txn in transactions_raw]

                    prev_hash = cls.block.hash if cls.block.hash else "0" * 64

                    new_block = await Block.generate(
                        transactions=transactions,
                        index=cls.block.index + 1,
                        prev_hash=prev_hash
                    )

                    cls.blocktemplate_index = cls.block.index
                    cls.blocktemplate_hash = cls.block.hash
                    cls.blocktemplate_target = new_block.target
                    cls.cached_transactions = transactions

                return {
                    "version": cls.block.version,
                    "prev_hash": cls.block.hash if cls.block.hash else "0" * 64,
                    "index": cls.block.index + 1,
                    "target": hex(cls.blocktemplate_target)[2:].rjust(64, '0') if cls.blocktemplate_target else "0" * 64,
                    "time": cls.blocktemplate_time,
                    "transactions": [txn.to_dict() for txn in cls.cached_transactions]
                }

            except Exception as e:
                cls.config.app_log.error(f"Error generating full block template: {e}")
                raise e
        return None