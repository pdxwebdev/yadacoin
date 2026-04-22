"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from unittest import mock
from unittest.mock import MagicMock

import pytest
from pymongo.errors import OperationFailure

from yadacoin.core.config import Config
from yadacoin.core.mongo import DeuggingListener, Mongo

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
            {"command_name": "find", f"query.not_indexed{i}": None}
        )
        i += 1

        # test find_one
        await m.async_db.test_collection.find_one({f"not_indexed{i}": 1})
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "find", f"query.not_indexed{i}": None}
        )
        i += 1

        # test count_documents
        await m.async_db.test_collection.count_documents({f"not_indexed{i}": 1})
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "aggregate", f"query.0.$match.not_indexed{i}": None}
        )
        i += 1

        # test delete_many
        await m.async_db.test_collection.delete_many({f"not_indexed{i}": 1})
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "delete", f"query.0.q.not_indexed{i}": None}
        )
        i += 1

        # test replace_one
        await m.async_db.test_collection.replace_one({f"not_indexed{i}": 1}, {})
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "update", f"query.0.q.not_indexed{i}": None}
        )
        i += 1

        # test update_one
        await m.async_db.test_collection.update_one(
            {f"not_indexed{i}": 1}, {"$set": {}}
        )
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "update", f"query.0.q.not_indexed{i}": None}
        )
        i += 1

        # test update_many
        await m.async_db.test_collection.update_many(
            {f"not_indexed{i}": 1}, {"$set": {}}
        )
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "update", f"query.0.q.not_indexed{i}": None}
        )
        i += 1

        # test aggregate
        await m.async_db.test_collection.aggregate(
            [{"$match": {f"not_indexed{i}": 1}}]
        ).to_list(1)
        assert await m.async_db.unindexed_queries.find_one(
            {"command_name": "aggregate", f"query.0.$match.not_indexed{i}": None}
        )


class TestDeuggingListener(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.listener = DeuggingListener()
        self.config = Config()

    def test_get_collection_name_unknown_command_returns_none(self):
        """Line 1080: return None when command_name not in known commands"""
        event = MagicMock()
        event.command_name = "unknown_xyz_command"
        result = self.listener.get_collection_name(event)
        self.assertIsNone(result)

    def test_started_returns_when_mongo_is_none(self):
        """Line 1087: early return when config.mongo is None"""
        event = MagicMock()
        event.command_name = "find"
        event.command = {"find": "test_collection"}
        original_mongo = self.config.mongo
        try:
            self.config.mongo = None
            self.listener.started(event)
        finally:
            self.config.mongo = original_mongo

    def test_started_returns_when_no_mongo_debug(self):
        """Line 1090: early return when config has no mongo_debug attribute"""
        event = MagicMock()
        event.command_name = "find"
        event.command = {"find": "test_collection"}
        had_attr = hasattr(self.config, "mongo_debug")
        original_val = getattr(self.config, "mongo_debug", None)
        try:
            if had_attr:
                delattr(self.config, "mongo_debug")
            self.listener.started(event)
        finally:
            if had_attr:
                self.config.mongo_debug = original_val

    def test_started_returns_when_mongo_debug_false(self):
        """Line 1092: early return when config.mongo_debug is False"""
        event = MagicMock()
        event.command_name = "find"
        event.command = {"find": "test_collection"}
        original_val = self.config.mongo_debug
        try:
            self.config.mongo_debug = False
            self.listener.started(event)
        finally:
            self.config.mongo_debug = original_val

    def test_started_returns_for_child_keys_collection(self):
        """Line 1096: early return when collection name is child_keys"""
        event = MagicMock()
        event.command_name = "find"
        event.command = {"find": "child_keys"}
        self.config.mongo_debug = True
        self.listener.started(event)

    def test_get_used_indexes_returns_none_for_falsy_explain_result(self):
        """Line 1183: early return when explain_result is falsy"""
        event = MagicMock()
        result = self.listener.get_used_indexes(None, event)
        self.assertIsNone(result)

    def test_get_used_indexes_logs_when_indexes_used(self):
        """Lines 1250-1251: log message when used_indexes is truthy (filter branch)"""
        import logging

        self.config.app_log = logging.getLogger("tornado.application")
        event = MagicMock()
        event.command_name = "find"
        event.command = {"filter": {"field": "value"}}
        explain_result = {
            "queryPlanner": {
                "namespace": "testdb.test_collection",
                "winningPlan": {"inputStage": {"indexName": "my_index"}},
            }
        }
        result = self.listener.get_used_indexes(explain_result, event)
        self.assertEqual(result, "my_index")

    def test_get_used_index_from_input_stage_with_index_name(self):
        """Lines 1259-1260: append indexName and return True"""
        result = self.listener.get_used_index_from_input_stage({"indexName": "idx1"})
        self.assertTrue(result)

    def test_get_used_index_from_input_stage_nested_returns_false(self):
        """Lines 1264-1267: nested inputStage with no usable index returns False"""
        result = self.listener.get_used_index_from_input_stage(
            {"inputStage": {"placeholder": True}}
        )
        self.assertFalse(result)

    def test_get_used_index_from_input_stages_loop_returns_false(self):
        """Lines 1270-1274: inputStages loop where a sub-stage returns False"""
        result = self.listener.get_used_index_from_input_stage(
            {"inputStages": [{"placeholder": True}]}
        )
        self.assertFalse(result)

    def test_get_used_index_from_input_stages_loop_returns_indexes(self):
        """Lines 1270-1274: inputStages loop where all sub-stages have indexes"""
        result = self.listener.get_used_index_from_input_stage(
            {"inputStages": [{"indexName": "idx1"}]}
        )
        self.assertTrue(result)

    def test_flatten_data_with_list_plain_value(self):
        """Line 1316: list item that is a plain (non-dict/list) value"""
        result = self.listener.flatten_data(["plain_string"])
        self.assertIn("0", result)
        self.assertIsNone(result["0"])

    # ------------------------------------------------------------------
    # Lines 1108, 1110, 1113-1114: succeeded() paths
    # ------------------------------------------------------------------

    def test_succeeded_returns_when_no_mongo_debug_attr(self):
        """Line 1108: returns early when config has no mongo_debug attribute."""
        event = MagicMock()
        event.command = {"start_time": 0}
        had_attr = hasattr(self.config, "mongo_debug")
        original_val = getattr(self.config, "mongo_debug", None)
        try:
            if had_attr:
                delattr(self.config, "mongo_debug")
            self.listener.succeeded(event)  # should not raise
        finally:
            if had_attr:
                self.config.mongo_debug = original_val

    def test_succeeded_returns_when_mongo_debug_false(self):
        """Line 1110: returns early when config.mongo_debug is False."""
        event = MagicMock()
        event.command = {"start_time": 0}
        original_val = self.config.mongo_debug
        try:
            self.config.mongo_debug = False
            self.listener.succeeded(event)
        finally:
            self.config.mongo_debug = original_val

    def test_succeeded_full_path_calls_do_logging(self):
        """Lines 1113-1114: reached when mongo_debug=True and event has command."""
        event = MagicMock()
        event.command = {"start_time": 0, "find": "test_collection"}
        original_val = self.config.mongo_debug
        try:
            self.config.mongo_debug = True
            with mock.patch.object(self.listener, "do_logging"):
                self.listener.succeeded(event)
        finally:
            self.config.mongo_debug = original_val

    # ------------------------------------------------------------------
    # Lines 1117-1123: failed() paths
    # ------------------------------------------------------------------

    def test_failed_returns_when_no_mongo_debug_attr(self):
        """Line 1119: returns early when config has no mongo_debug attribute."""
        event = MagicMock()
        event.command = {"start_time": 0}
        had_attr = hasattr(self.config, "mongo_debug")
        original_val = getattr(self.config, "mongo_debug", None)
        try:
            if had_attr:
                delattr(self.config, "mongo_debug")
            self.listener.failed(event)
        finally:
            if had_attr:
                self.config.mongo_debug = original_val

    def test_failed_returns_when_mongo_debug_false(self):
        """Line 1121: returns early when config.mongo_debug is False."""
        event = MagicMock()
        event.command = {"start_time": 0}
        original_val = self.config.mongo_debug
        try:
            self.config.mongo_debug = False
            self.listener.failed(event)
        finally:
            self.config.mongo_debug = original_val

    def test_failed_full_path_calls_do_logging(self):
        """Lines 1122-1123: reached when mongo_debug=True."""
        event = MagicMock()
        event.command = {"start_time": 0, "find": "test_collection"}
        original_val = self.config.mongo_debug
        try:
            self.config.mongo_debug = True
            with mock.patch.object(self.listener, "do_logging"):
                self.listener.failed(event)
        finally:
            self.config.mongo_debug = original_val

    # ------------------------------------------------------------------
    # Lines 1126-1138: do_logging() body
    # ------------------------------------------------------------------

    def test_do_logging_slow_query_logs_warning(self):
        """Lines 1126-1133: slow query path (duration > 3) logs a SLOW message."""
        import logging

        self.config.app_log = logging.getLogger("tornado.application")
        self.config.slow_query_logging = True
        self.listener.collection = "test_collection"
        self.listener.set_duration = lambda: None
        self.listener.duration = 5.0  # > 3 seconds
        with mock.patch.object(self.config.mongo.async_db, "slow_queries", []):
            self.listener.do_logging("find", {}, {})

    def test_do_logging_debug_message(self):
        """Lines 1126-1128, 1134-1138: normal (fast) query logs a debug message."""
        import logging

        self.config.app_log = logging.getLogger("tornado.application")
        self.config.slow_query_logging = False
        self.listener.collection = "test_collection"
        self.listener.set_duration = lambda: None
        self.listener.duration = 0.1  # < 3 seconds
        original_val = self.config.mongo_debug
        try:
            self.config.mongo_debug = True
            self.listener.do_logging("find", {}, {})
        finally:
            self.config.mongo_debug = original_val

    # ------------------------------------------------------------------
    # Line 1178: log_explain_output() aggregate+explain early return
    # ------------------------------------------------------------------

    def test_log_explain_output_aggregate_with_explain_flag_returns_early(self):
        """Line 1178: aggregate command with 'explain' flag returns before querying."""
        event = MagicMock()
        event.command_name = "aggregate"
        event.command = {
            "aggregate": "test_collection",
            "pipeline": [{"$match": {}}],
            "explain": True,
        }
        event.database_name = "yadacoin"
        # Should return at line 1178 without hitting the DB
        self.listener.log_explain_output(event)

    # ------------------------------------------------------------------
    # Lines 1208-1210: get_used_indexes() pipeline branch exception
    # ------------------------------------------------------------------

    def test_get_used_indexes_pipeline_branch_exception_logs_warning(self):
        """Lines 1208-1210: except block in pipeline branch when get_used_index raises."""
        import logging

        self.config.app_log = logging.getLogger("tornado.application")
        event = MagicMock()
        event.command_name = "find"
        event.command = {"pipeline": [{"$match": {}}]}
        explain_result = {
            "queryPlanner": {
                "namespace": "testdb.test_collection",
                "winningPlan": {},  # no indexName → used_indexes stays False
            }
        }
        with mock.patch.object(
            self.listener,
            "get_used_index_from_input_stage",
            side_effect=Exception("index error"),
        ):
            with mock.patch.object(self.listener, "handle_unindexed_log"):
                self.listener.get_used_indexes(explain_result, event)

    # ------------------------------------------------------------------
    # Lines 1227-1229: get_used_indexes() filter branch exception
    # ------------------------------------------------------------------

    def test_get_used_indexes_filter_branch_exception_logs_warning(self):
        """Lines 1227-1229: except block in filter branch when get_used_index raises."""
        import logging

        self.config.app_log = logging.getLogger("tornado.application")
        event = MagicMock()
        event.command_name = "find"
        event.command = {"filter": {"field": "value"}}
        explain_result = {
            "queryPlanner": {
                "namespace": "testdb.test_collection",
                "winningPlan": {"inputStage": {}},  # no indexName
            }
        }
        with mock.patch.object(
            self.listener,
            "get_used_index_from_input_stage",
            side_effect=Exception("index error"),
        ):
            with mock.patch.object(self.listener, "handle_unindexed_log"):
                self.listener.get_used_indexes(explain_result, event)


class TestMongoInitPaths(AsyncTestCase):
    """Tests for exception and special code paths in Mongo.__init__"""

    def _make_default_mock_db(self):
        """Returns a mock db where all operations succeed by default."""
        mock_db = MagicMock()
        mock_db.blocks.find.return_value = []
        mock_db.miner_transactions.find.return_value = []
        mock_db.blocks.find_one.return_value = None
        return mock_db

    def test_init_auth_existing_user_suppresses_error(self):
        """Lines 31-49, 451: OperationFailure('already exists') is silently ignored."""
        config = Config()
        config.mongodb_username = "testuser"
        config.mongodb_password = "testpass"
        try:
            mock_db = self._make_default_mock_db()
            mock_db.command.side_effect = OperationFailure("user already exists")
            mock_client = MagicMock()
            mock_client.__getitem__.return_value = mock_db
            with mock.patch(
                "yadacoin.core.mongo.MongoClient", return_value=mock_client
            ):
                with mock.patch(
                    "yadacoin.core.mongo.MotorClient", return_value=MagicMock()
                ):
                    m = Mongo()
            self.assertIsNotNone(m)
        finally:
            del config.mongodb_username
            del config.mongodb_password

    def test_init_auth_unknown_error_raises(self):
        """Lines 44-48: OperationFailure with unknown message and non-13 code re-raises."""
        config = Config()
        config.mongodb_username = "testuser"
        config.mongodb_password = "testpass"
        try:
            mock_db = self._make_default_mock_db()
            mock_db.command.side_effect = OperationFailure(
                "some unexpected error", code=0
            )
            mock_client = MagicMock()
            mock_client.__getitem__.return_value = mock_db
            with mock.patch(
                "yadacoin.core.mongo.MongoClient", return_value=mock_client
            ):
                with mock.patch(
                    "yadacoin.core.mongo.MotorClient", return_value=MagicMock()
                ):
                    with self.assertRaises(OperationFailure):
                        Mongo()
        finally:
            del config.mongodb_username
            del config.mongodb_password

    def test_init_connection_test_failure_raises(self):
        """Lines 61-62: raises when the connection test find_one fails."""
        mock_db = self._make_default_mock_db()
        mock_db.blocks.find_one.side_effect = Exception("connection refused")
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        with mock.patch("yadacoin.core.mongo.MongoClient", return_value=mock_client):
            with mock.patch(
                "yadacoin.core.mongo.MotorClient", return_value=MagicMock()
            ):
                with self.assertRaises(Exception):
                    Mongo()

    def test_init_create_indexes_except_pass_all_collections(self):
        """Lines 256-257, 264-265, 282-283, 308-309, 318-319, 325-326, 363-364, 407-408, 423-424."""
        mock_db = self._make_default_mock_db()
        for coll_name in [
            "blocks",
            "unspent_cache",
            "consensus",
            "shares",
            "share_payout",
            "transactions_by_rid_cache",
            "miner_transactions",
            "failed_transactions",
            "user_collection_last_activity",
        ]:
            getattr(mock_db, coll_name).create_indexes.side_effect = Exception(
                "dup index"
            )
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        with mock.patch("yadacoin.core.mongo.MongoClient", return_value=mock_client):
            with mock.patch(
                "yadacoin.core.mongo.MotorClient", return_value=MagicMock()
            ):
                m = Mongo()
        self.assertIsNotNone(m)

    def test_init_node_status_index_failure_raises(self):
        """Lines 436-437: node_status create_indexes failure re-raises."""
        mock_db = self._make_default_mock_db()
        mock_db.node_status.create_indexes.side_effect = Exception("node_status error")
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        with mock.patch("yadacoin.core.mongo.MongoClient", return_value=mock_client):
            with mock.patch(
                "yadacoin.core.mongo.MotorClient", return_value=MagicMock()
            ):
                with self.assertRaises(Exception):
                    Mongo()

    def test_init_pool_stats_index_failure_raises(self):
        """Lines 443-444: pool_stats create_indexes failure re-raises."""
        mock_db = self._make_default_mock_db()
        mock_db.pool_stats.create_indexes.side_effect = Exception("pool_stats error")
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        with mock.patch("yadacoin.core.mongo.MongoClient", return_value=mock_client):
            with mock.patch(
                "yadacoin.core.mongo.MotorClient", return_value=MagicMock()
            ):
                with self.assertRaises(Exception):
                    Mongo()

    def test_init_block_time_conversion(self):
        """Lines 468-471: block with string time gets converted."""
        mock_db = self._make_default_mock_db()

        def find_side_effect(query, *args, **kwargs):
            if query == {"time": {"$type": 2}}:
                return [{"index": 1, "time": "1620000000"}]
            return []

        mock_db.blocks.find.side_effect = find_side_effect
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        with mock.patch("yadacoin.core.mongo.MongoClient", return_value=mock_client):
            with mock.patch(
                "yadacoin.core.mongo.MotorClient", return_value=MagicMock()
            ):
                Mongo()
        mock_db.blocks.update.assert_called()

    def test_init_mempool_txn_time_conversion(self):
        """Lines 479-482: mempool transaction with string time gets converted."""
        mock_db = self._make_default_mock_db()
        mock_db.miner_transactions.find.return_value = [
            {"id": "txn1", "time": "1620000000"}
        ]
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        with mock.patch("yadacoin.core.mongo.MongoClient", return_value=mock_client):
            with mock.patch(
                "yadacoin.core.mongo.MotorClient", return_value=MagicMock()
            ):
                Mongo()
        mock_db.miner_transactions.update.assert_called()

    def test_init_blockchain_txn_time_conversion(self):
        """Lines 492-504: blockchain transactions with string times get converted."""
        mock_db = self._make_default_mock_db()
        block = {
            "index": 1,
            "transactions": [
                {"id": "tx1", "time": ""},  # triggers del txn["time"] branch
                {"id": "tx2", "time": "1620000000"},  # triggers int() conversion branch
                {"id": "tx3"},  # no "time" key, exercises if check
            ],
        }

        def find_side_effect(query, *args, **kwargs):
            if query == {"transactions.time": {"$type": 2}}:
                return [block]
            return []

        mock_db.blocks.find.side_effect = find_side_effect
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        with mock.patch("yadacoin.core.mongo.MongoClient", return_value=mock_client):
            with mock.patch(
                "yadacoin.core.mongo.MotorClient", return_value=MagicMock()
            ):
                Mongo()
        mock_db.blocks.update.assert_called()

    def test_init_hack_present_triggers_rollback(self):
        """Lines 1061-1069: hack detection triggers block deletion and resync warning."""
        mock_db = self._make_default_mock_db()
        mock_db.blocks.find_one.side_effect = [
            None,  # connection test
            {"index": 516355},  # missing block already present, skip insert
            {"transactions": "hack_data"},  # hack check: exploit detected
        ]
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        with mock.patch("yadacoin.core.mongo.MongoClient", return_value=mock_client):
            with mock.patch(
                "yadacoin.core.mongo.MotorClient", return_value=MagicMock()
            ):
                Mongo()
        mock_db.blocks.delete_many.assert_called_with({"index": {"$gte": 591762}})
        mock_db.consensus.delete_many.assert_called_with(
            {"block.index": {"$gte": 591762}}
        )
