from pymongo import MongoClient, IndexModel, ASCENDING, DESCENDING

class Mongo(object):
    @classmethod
    def __init__(self, config):
        self.config = config
        self.client = MongoClient(self.config.mongodb_host)
        self.db = self.client[self.config.database]
        self.site_db = self.client[self.config.site_database]

        __id = IndexModel([("id", ASCENDING)], name="__id", unique=True)
        __hash = IndexModel([("hash", ASCENDING)], name="__hash")
        __index = IndexModel([("index", ASCENDING)], name="__index")
        try:
            self.db.blocks.create_indexes([__hash, __index, __id])
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
        try:
            self.db.consensus.create_indexes([__id, __index, __block_hash])
        except:
            pass

        __address = IndexModel([("address", ASCENDING)], name="__address")
        __index = IndexModel([("index", ASCENDING)], name="__index")
        __hash = IndexModel([("hash", ASCENDING)], name="__hash")
        try:
            self.db.shares.create_indexes([__address, __index, __hash])
        except:
            pass