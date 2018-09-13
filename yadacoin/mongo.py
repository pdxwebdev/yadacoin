from pymongo import MongoClient
from config import Config

class Mongo(object):
    @classmethod
    def init(cls):
        cls.client = MongoClient(Config.mongodb_host)
        cls.db = cls.client[Config.database]
        cls.site_db = cls.client[Config.site_database]