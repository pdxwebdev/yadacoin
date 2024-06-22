import pytest

from yadacoin.core.config import Config
from yadacoin.core.mongo import Mongo

from ..test_setup import AsyncTestCase


class TestMongo(AsyncTestCase):
    async def test_mongo(self):
        m = Mongo()
        try:
            [x async for x in m.async_db.test_collection.find({})]
            assert True
        except Exception as e:
            pytest.fail("DID RAISE {0}".format(e))
        try:
            await m.async_db.test_collection.find_one({})
            assert True
        except Exception as e:
            pytest.fail("DID RAISE {0}".format(e))
        try:
            await m.async_db.test_collection.count_documents({})
            assert True
        except Exception as e:
            pytest.fail("DID RAISE {0}".format(e))
        try:
            await m.async_db.test_collection.delete_many({})
            assert True
        except Exception as e:
            pytest.fail("DID RAISE {0}".format(e))
        try:
            await m.async_db.test_collection.insert_one({})
            assert True
        except Exception as e:
            pytest.fail("DID RAISE {0}".format(e))
        try:
            await m.async_db.test_collection.replace_one({}, {})
            assert True
        except Exception as e:
            pytest.fail("DID RAISE {0}".format(e))
        try:
            await m.async_db.test_collection.update_one({}, {"$set": {}})
            assert True
        except Exception as e:
            pytest.fail("DID RAISE {0}".format(e))
        try:
            await m.async_db.test_collection.update_many({}, {"$set": {}})
            assert True
        except Exception as e:
            pytest.fail("DID RAISE {0}".format(e))
        try:
            [x async for x in m.async_db.test_collection.aggregate([{"$match": {}}])]
            assert True
        except Exception as e:
            pytest.fail("DID RAISE {0}".format(e))

    async def test_unindexed(self):
        class AppLog:
            def warning(self, message):
                pass

            def info(self, message):
                pass

        c = Config()
        c.mongo_debug = True
        c.app_log = AppLog()
        m = c.mongo
        await m.async_db.unindexed_queries.delete_many({})

        i = 0
        # test find
        await m.async_db.test_collection.find({f"not_indexed{i}": 1}).limit(1).to_list(
            1
        )
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "find", f"query.not_indexed{i}": 1}
        )
        i += 1

        # test find_one
        await m.async_db.test_collection.find_one({f"not_indexed{i}": 1})
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "find", f"query.not_indexed{i}": 1}
        )
        i += 1

        # test count_documents
        await m.async_db.test_collection.count_documents({f"not_indexed{i}": 1})
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "aggregate", f"query.0.$match.not_indexed{i}": 1}
        )
        i += 1

        # test delete_many
        await m.async_db.test_collection.delete_many({f"not_indexed{i}": 1})
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "delete", f"query.0.q.not_indexed{i}": 1}
        )
        i += 1

        # test replace_one
        await m.async_db.test_collection.replace_one({f"not_indexed{i}": 1}, {})
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "update", f"query.0.q.not_indexed{i}": 1}
        )
        i += 1

        # test update_one
        await m.async_db.test_collection.update_one(
            {f"not_indexed{i}": 1}, {"$set": {}}
        )
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "update", f"query.0.q.not_indexed{i}": 1}
        )
        i += 1

        # test update_many
        await m.async_db.test_collection.update_many(
            {f"not_indexed{i}": 1}, {"$set": {}}
        )
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "update", f"query.0.q.not_indexed{i}": 1}
        )
        i += 1

        # test aggregate
        await m.async_db.test_collection.aggregate(
            [{"$match": {f"not_indexed{i}": 1}}]
        ).to_list(1)
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "aggregate", f"query.0.$match.not_indexed{i}": 1}
        )
