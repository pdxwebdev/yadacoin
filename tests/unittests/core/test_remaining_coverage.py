"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from logging import getLogger
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.blockchainutils import BlockChainUtils
from yadacoin.core.config import Config
from yadacoin.core.keyeventlog import KeyEventLog

from ..test_setup import AsyncTestCase


class _AsyncIter:
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        self._iter = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class RemainingBUCoverage(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        if not hasattr(self.config, "app_log") or self.config.app_log is None:
            self.config.app_log = getLogger("tornado.application")
        self.bu = BlockChainUtils()

    def test_sync_aggregate_retries_without_hint(self):
        coll = MagicMock()

        def aggregate(pipeline, hint=None, **kwargs):
            if hint:
                raise RuntimeError("missing hint")
            return [{"ok": 1}, {"ok": 2}]

        coll.aggregate.side_effect = aggregate
        with patch.object(
            self.bu.mongo,
            "get_balance_db",
            return_value=MagicMock(blocks=coll),
        ):
            docs = self.bu._sync_aggregate_blocks([{"$match": {}}], hint="h", length=1)
        self.assertEqual(docs, [{"ok": 1}])

    async def test_schedule_balance_refresh_reuses_task_and_logs_failure(self):
        self.bu._refresh_final_balance = AsyncMock(side_effect=RuntimeError("boom"))
        first = self.bu._schedule_balance_refresh("addr")
        second = self.bu._schedule_balance_refresh("addr")
        self.assertIs(first, second)
        with self.assertRaises(RuntimeError):
            await first

    async def test_get_final_balance_awaits_inflight_refresh(self):
        self.bu._get_wallet_balance_cache = AsyncMock(return_value=None)
        self.bu.get_latest_block_async = AsyncMock(return_value=None)

        async def done():
            return 4.2

        import asyncio

        task = asyncio.get_running_loop().create_task(done())
        self.bu._balance_refresh_tasks["addr"] = task
        self.assertEqual(await self.bu.get_final_balance("addr"), 4.2)

    async def test_compute_final_balance_cache_hit(self):
        self.bu.get_reverse_public_key = AsyncMock(return_value="pk")
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "tip", "index": 3}
        )
        self.bu._get_wallet_balance_cache = AsyncMock(
            return_value={"balance": 9.5, "last_block_hash": "tip"}
        )
        self.bu._wallet_balance_cache_is_valid = AsyncMock(return_value=True)
        self.assertEqual(await self.bu._compute_final_balance("addr"), 9.5)

    async def test_schedule_wallet_refresh_reuses_task_and_logs_failure(self):
        self.bu.get_wallet_balance = AsyncMock(side_effect=RuntimeError("wallet"))
        first = self.bu._schedule_wallet_refresh("addr")
        second = self.bu._schedule_wallet_refresh("addr")
        self.assertIs(first, second)
        with self.assertRaises(RuntimeError):
            await first

    def test_sync_tagged_balance_and_spent_ids(self):
        received_docs = [
            {
                "time": 1,
                "transactions": [
                    {
                        "id": "t1",
                        "outputs": [
                            "not-dict",
                            {
                                "inception_public_key_hash": "other",
                                "to": "x",
                                "value": 1,
                            },
                            {
                                "inception_public_key_hash": "inc",
                                "to": "a",
                                "value": 3,
                            },
                        ],
                    },
                    {
                        "id": "t2",
                        "outputs": [
                            {
                                "inception_public_key_hash": "inc",
                                "to": "b",
                                "value": 1,
                            }
                        ],
                    },
                    {
                        "id": None,
                        "outputs": [
                            {
                                "inception_public_key_hash": "inc",
                                "to": "c",
                                "value": 1,
                            }
                        ],
                    },
                ],
            },
            {"transactions": None},
        ]
        spent_docs = [
            {
                "transactions": [
                    {"inputs": [{"id": "t1"}, "nope", {"id": "missing"}]},
                    {"inputs": None},
                ]
            },
            {"transactions": None},
        ]
        calls = {"n": 0}

        class Coll:
            def find(self, query, projection=None):
                calls["n"] += 1
                cursor = MagicMock()
                if calls["n"] in (1, 3):
                    cursor.hint.side_effect = RuntimeError("no hint")
                    return cursor
                if any("inception_public_key_hash" in key for key in query):
                    return received_docs
                return spent_docs

        with patch.object(
            self.bu.mongo,
            "get_balance_db",
            return_value=MagicMock(blocks=Coll()),
        ):
            result = self.bu._sync_tagged_balance("inc")
        self.assertEqual([doc["id"] for doc in result], ["t2"])
        self.assertEqual(self.bu._spent_ids(Coll(), []), set())

    async def test_tagged_kel_balance_and_load_utxos(self):
        with patch.object(self.bu.mongo, "balance_executor", None):
            self.assertIsNone(await self.bu._load_tagged_utxos("inc"))
            self.assertIsNone(await self.bu._tagged_utxos_for_inception("inc"))

        self.bu._sync_tagged_balance = lambda inception: [{"id": ""}]
        self.assertEqual(await self.bu._load_tagged_utxos("inc"), [{"id": ""}])

        self.bu._sync_tagged_balance = lambda inception: [
            {"id": "keep", "outputs": [{"value": 1}]},
            {"id": "drop", "outputs": [{"value": 2}]},
        ]
        mock_db = MagicMock()
        mock_db.miner_transactions.find.return_value = _AsyncIter(
            [
                {"inputs": [{"id": "drop"}, "x", {"id": "nope"}]},
                {"inputs": None},
            ]
        )
        with patch.object(self.bu.mongo, "async_db", mock_db):
            loaded = await self.bu._load_tagged_utxos("inc")
        self.assertEqual([item["id"] for item in loaded], ["keep"])

        self.bu._sync_unspent_tagged = lambda inception: [{"id": "u"}]
        self.assertEqual(
            await self.bu._tagged_utxos_for_inception("inc"), [{"id": "u"}]
        )

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.inception_for_address",
            new=AsyncMock(return_value="inc"),
        ):
            with patch.object(self.bu.mongo, "balance_executor", None):
                self.assertIsNone(await self.bu._tagged_kel_balance("addr"))
            self.bu._load_tagged_utxos = AsyncMock(return_value=[])
            self.assertEqual(await self.bu._tagged_kel_balance("addr"), 0.0)
            self.bu._load_tagged_utxos = AsyncMock(
                return_value=[{"outputs": [{"value": 2}, {"value": 1}]}]
            )
            self.assertEqual(await self.bu._tagged_kel_balance("addr"), 3.0)

    async def test_tagged_kel_utxos_branches(self):
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.inception_for_address",
            new=AsyncMock(side_effect=RuntimeError("kel")),
        ):
            self.assertIsNone(await self.bu.tagged_kel_utxos("addr"))

        utxos = [
            {"id": "a", "time": 2, "outputs": [{"value": 1.0}]},
            {"id": "b", "time": 1, "outputs": [{"value": 5.0}]},
            {"id": "c", "time": 3, "outputs": [{"value": 0.5}]},
        ]
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.inception_for_address",
            new=AsyncMock(return_value="inc"),
        ):
            self.bu._load_tagged_utxos = AsyncMock(return_value=None)
            self.assertIsNone(await self.bu.tagged_kel_utxos("addr", max_utxos=1000))
            self.bu._load_tagged_utxos = AsyncMock(return_value=utxos)
            result = await self.bu.tagged_kel_utxos(
                "addr", amount_needed=5.5, max_utxos=1000
            )
        self.assertEqual([item["id"] for item in result["unspent_utxos"]], ["b", "a"])
        self.assertAlmostEqual(result["balance"], 6.5)

    async def test_wallet_balance_fast_and_tagged_paths(self):
        self.bu._schedule_wallet_refresh = MagicMock()
        self.bu._memory_balances["a1"] = 1.0
        self.bu._memory_balances["a2"] = 2.5
        self.bu._kel_addresses_cache["addr"] = ("tip", frozenset({"a1", "a2"}))
        self.assertAlmostEqual(
            await self.bu.get_wallet_balance("addr", wait=False), 3.5
        )
        self.bu._memory_balances["solo"] = 7.0
        self.assertEqual(await self.bu.get_wallet_balance("solo", wait=False), 7.0)

        self.bu._tagged_kel_balance = AsyncMock(return_value=3.25)
        self.assertEqual(await self.bu.get_wallet_balance("addr"), 3.25)
        self.assertEqual(self.bu._memory_balances["addr"], 3.25)

        self.bu._tagged_kel_balance = AsyncMock(return_value=None)
        self.bu._cached_kel_addresses = AsyncMock(return_value=frozenset())
        self.bu.get_final_balance = AsyncMock(return_value=1.1)
        self.assertEqual(await self.bu.get_wallet_balance("addr"), 1.1)

    async def test_public_key_pairs_without_executor(self):
        self.bu._aggregate_blocks = AsyncMock(
            return_value=[{"unique_public_keys": ["pk"]}]
        )
        with patch.object(self.bu.mongo, "balance_executor", None):
            result = await self.bu.get_public_key_address_pairs("addr")
        self.assertEqual(result, [{"unique_public_keys": ["pk"]}])
        pipeline = self.bu._aggregate_blocks.await_args.args[0]
        self.assertEqual(pipeline[0]["$match"]["transactions.outputs.to"], "addr")

    async def test_unspent_outputs_returns_tagged(self):
        tagged = {
            "unspent_utxos": [],
            "balance": 1.0,
            "max_transferable_value": 1.0,
        }
        self.bu.tagged_kel_utxos = AsyncMock(return_value=tagged)
        self.assertIs(await self.bu.get_unspent_outputs("addr"), tagged)


class RemainingKelCoverage(AsyncTestCase):
    async def test_ensure_output_tags_without_inception(self):
        self.assertIsNone(await KeyEventLog.ensure_output_tags([]))
        self.assertIsNone(await KeyEventLog.ensure_output_tags([{"id": "x"}]))

    async def test_inception_for_address_block_and_mempool(self):
        self.assertIsNone(await KeyEventLog.inception_for_address(""))
        self.assertIsNone(await KeyEventLog.inception_for_address(None))
        config = Config()

        async def blocks_find_one(query, projection=None, hint=None):
            if hint:
                raise RuntimeError("hint")
            return {
                "transactions": [
                    "bad",
                    {
                        "public_key_hash": "other",
                        "inception_public_key_hash": "nope",
                    },
                    {"public_key_hash": "addr", "inception_public_key_hash": ""},
                    {"public_key_hash": "addr", "inception_public_key_hash": "inc1"},
                ]
            }

        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(side_effect=blocks_find_one)
        with patch.object(config.mongo, "async_db", mock_db):
            self.assertEqual(await KeyEventLog.inception_for_address("addr"), "inc1")

        mock_db = MagicMock()
        mock_db.blocks.find_one = AsyncMock(return_value=None)
        mock_db.miner_transactions.find_one = AsyncMock(
            return_value={
                "public_key_hash": "addr2",
                "inception_public_key_hash": "inc2",
            }
        )
        with patch.object(config.mongo, "async_db", mock_db):
            self.assertEqual(await KeyEventLog.inception_for_address("addr2"), "inc2")

    async def test_reorg_clear_and_stamp_known_outputs(self):
        config = Config()
        mock_db = MagicMock()
        mock_db.blocks.update_many = AsyncMock()
        mock_db.miner_transactions.update_many = AsyncMock()
        with patch.object(
            KeyEventLog,
            "inception_for_address",
            new=AsyncMock(side_effect=["still", None]),
        ), patch.object(config.mongo, "async_db", mock_db):
            await KeyEventLog.apply_reorg_output_tag_clear(["keep", "drop"])
        mock_db.blocks.update_many.assert_awaited()
        mock_db.miner_transactions.update_many.assert_awaited()

        class Out:
            def __init__(self, to):
                self.to = to

        class Txn:
            def __init__(self, outputs):
                self.outputs = outputs

        txn_obj = Txn([Out(None), Out("addrA"), "skip"])
        txn_dict = {"outputs": [{"to": "addrB"}, {"to": ""}, "nope"]}
        txn_empty = {"outputs": None}

        async def inception_for_address(address):
            return "inc" if address == "addrA" else None

        mock_db = MagicMock()
        mock_db.blocks.update_one = AsyncMock()
        with patch.object(
            KeyEventLog, "inception_for_address", new=inception_for_address
        ), patch.object(config.mongo, "async_db", mock_db):
            await KeyEventLog.stamp_known_block_outputs(
                5, [txn_obj, txn_dict, txn_empty]
            )
        mock_db.blocks.update_one.assert_awaited()
