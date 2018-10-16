from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING
from config import Config

class Mongo(object):
    @classmethod
    def init(cls):
        cls.client = MongoClient(Config.mongodb_host)
        cls.db = cls.client[Config.database]
        cls.site_db = cls.client[Config.site_database]

        __id = IndexModel([("id", ASCENDING)], name="__id", unique=True)
        __hash = IndexModel([("hash", ASCENDING)], name="__hash")
        __index = IndexModel([("index", ASCENDING)], name="__index")
        try:
            cls.db.blocks.create_indexes([__hash, __index, __id])
        except:
            pass

        __id = IndexModel([("id", ASCENDING)], name="__id")
        __height = IndexModel([("height", ASCENDING)], name="__height")
        try:
            cls.db.unspent_cache.create_indexes([__id, __height])
        except:
            pass

        __id = IndexModel([("id", ASCENDING)], name="__id")
        __index = IndexModel([("index", ASCENDING)], name="__index")
        __block_hash = IndexModel([("block.hash", ASCENDING)], name="__block_hash")
        try:
            cls.db.consensus.create_indexes([__id, __index, __block_hash])
        except:
            pass