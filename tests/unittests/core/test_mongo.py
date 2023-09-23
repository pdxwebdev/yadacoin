import pytest

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
