import os
from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING
from motor.motor_tornado import MotorClient

from yadacoin.core.config import get_config


class Mongo(object):

    def __init__(self):
        self.config = get_config()
        self.client = MongoClient(self.config.mongodb_host)
        self.db = self.client[self.config.database]
        self.site_db = self.client[self.config.site_database]
        try:
            # test connection
            self.db.yadacoin.find_one()
        except Exception as e:
            raise e

        __id = IndexModel([("id", ASCENDING)], name="__id", unique=True)
        __hash = IndexModel([("hash", ASCENDING)], name="__hash")
        __index = IndexModel([("index", ASCENDING)], name="__index")
        __to = IndexModel([("transactions.outputs.to", ASCENDING)], name="__to")
        __txn_id = IndexModel([("transactions.id", ASCENDING)], name="__txn_id")
        __txn_inputs_id = IndexModel([("transactions.inputs.id", ASCENDING)], name="__txn_inputs_id")
        __txn_public_key = IndexModel([("transactions.public_key", ASCENDING)], name="__txn_public_key")
        __txn_inputs_public_key = IndexModel([("transactions.inputs.public_key", ASCENDING)], name="__txn_inputs_public_key")
        __txn_inputs_address = IndexModel([("transactions.inputs.address", ASCENDING)], name="__txn_inputs_address")
        __txn_public_key_inputs_public_key_address = IndexModel([
            ("transactions.public_key", ASCENDING),
            ("transactions.inputs.public_key", ASCENDING),
            ("transactions.inputs.address", ASCENDING),
        ], name="__txn_public_key_inputs_public_key_address")
        __public_key_time = IndexModel([
            ("public_key", ASCENDING),
            ("time", ASCENDING),
        ], name="__public_key_time")
        __public_key = IndexModel([("public_key", ASCENDING)], name="__public_key")
        __prev_hash = IndexModel([("prevHash", ASCENDING)], name="__prev_hash")
        __txn_public_key_inputs_id = IndexModel([
            ("transactions.public_key", ASCENDING),
            ("transactions.inputs.id", ASCENDING)
        ], name="__txn_public_key_inputs_id")

        try:
            self.db.blocks.create_indexes([
                __hash,
                __index,
                __id,
                __to,
                __txn_id,
                __txn_inputs_id,
                __txn_public_key,
                __txn_inputs_public_key,
                __txn_inputs_address,
                __txn_public_key_inputs_public_key_address,
                __public_key_time,
                __public_key,
                __prev_hash,
                __txn_public_key_inputs_id
            ])
        except:
            pass

        __id = IndexModel([("id", ASCENDING)], name="__id")
        __height = IndexModel([("height", ASCENDING)], name="__height")
        try:
            self.db.unspent_cache.create_indexes([__id, __height])
        except:
            pass

        __id = IndexModel([("id", ASCENDING)], name="__id")
        __index = IndexModel([("index", ASCENDING)], name="__index")
        __block_hash = IndexModel([("block.hash", ASCENDING)], name="__block_hash")
        __block_prevHash_index_version = IndexModel([
            ("block.prevHash", ASCENDING),
            ("block.index", ASCENDING),
            ("block.version", ASCENDING)
        ], name="__block_prevHash_index_version")
        try:
            self.db.consensus.create_indexes([
                __id,
                __index,
                __block_hash,
                __block_prevHash_index_version
            ])
        except:
            pass

        __address = IndexModel([("address", ASCENDING)], name="__address")
        __index = IndexModel([("index", ASCENDING)], name="__index")
        __hash = IndexModel([("hash", ASCENDING)], name="__hash")
        __time = IndexModel([("time", DESCENDING)], name="__time")
        try:
            self.db.shares.create_indexes([__address, __index, __hash, __time])
        except:
            pass

        __txn_id = IndexModel([("txn.id", ASCENDING)], name="__txn_id")
        try:
            self.db.transactions_by_rid_cache.create_indexes([__txn_id])
        except:
            pass

        # TODO: add indexes for peers

        # See https://motor.readthedocs.io/en/stable/tutorial-tornado.html
        self.async_client = MotorClient(self.config.mongodb_host)
        self.async_db = self.async_client[self.config.database]
        self.async_site_db = self.async_client[self.config.site_database]

        # convert block time from string to number
        blocks_to_convert = self.db.blocks.find({'time': {'$type': 2}})
        for block in blocks_to_convert:
            self.config.app_log.warning(f'Converting block time to int for block: {block["index"]}')
            self.db.blocks.update({'index': block['index']}, {'$set': {'time': int(block['time'])}})

        too_high_reward_blocks = self.db.blocks.find({'index': {'$gte': 210000}})
        for block in too_high_reward_blocks:
            for txn in block['transactions']:
                if txn['public_key'] == block['public_key'] and len(txn['inputs']) == 0:
                    total_output = 0
                    for txn_out in txn['outputs']:
                        total_output += txn_out['value']
                    if total_output >= 50:
                        self.config.app_log.warning(f'Removing block with too high of reward: {block["index"]}')
                        self.db.blocks.delete_one({'index': block['index']})
