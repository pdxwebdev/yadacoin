"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from unittest.mock import MagicMock

from yadacoin.core.processingqueue import (
    BlockProcessingQueue,
    BlockProcessingQueueItem,
    NonceProcessingQueue,
    NonceProcessingQueueItem,
    ProcessingQueue,
    ProcessingQueues,
    TransactionProcessingQueue,
    TransactionProcessingQueueItem,
)

from ..test_setup import AsyncTestCase


def _make_block(hash_val, index=0):
    block = MagicMock()
    block.hash = hash_val
    block.index = index
    return block


def _make_blockchain(first_hash, final_hash):
    blockchain = MagicMock()
    from yadacoin.core.block import Block

    first_b = _make_block(first_hash)
    final_b = _make_block(final_hash)
    first_b.__class__ = Block
    final_b.__class__ = Block
    blockchain.first_block = first_b
    blockchain.final_block = final_b
    return blockchain


class TestProcessingQueue(unittest.TestCase):
    def test_time_sum_start_and_end(self):
        q = ProcessingQueue()
        q.time_sum_start()
        q.time_sum_end()
        self.assertGreaterEqual(q.time_sum, 0)

    def test_inc_num_items_processed(self):
        q = ProcessingQueue()
        q.inc_num_items_processed()
        self.assertEqual(q.num_items_processed, 1)
        q.inc_num_items_processed()
        self.assertEqual(q.num_items_processed, 2)

    def test_to_status_dict(self):
        q = ProcessingQueue()
        q.queue = {}
        d = q.to_status_dict()
        self.assertIn("queue_item_count", d)
        self.assertIn("average_processing_time", d)
        self.assertIn("num_items_processed", d)


class TestBlockProcessingQueue(unittest.TestCase):
    def setUp(self):
        self.queue = BlockProcessingQueue()

    def _make_item(self, first_hash="hash1", final_hash="hash2"):
        blockchain = MagicMock()
        first_b = _make_block(first_hash)
        final_b = _make_block(final_hash)
        # Make isinstance(block, Block) work by using spec
        blockchain.first_block = first_b
        blockchain.final_block = final_b
        # Use dict blocks path
        first_b.__class__ = dict
        final_b.__class__ = dict
        first_b_dict = {"hash": first_hash}
        final_b_dict = {"hash": final_hash}
        blockchain.first_block = first_b_dict
        blockchain.final_block = final_b_dict
        return BlockProcessingQueueItem(blockchain=blockchain)

    def test_add_item(self):
        item = self._make_item("h1", "h2")
        result = self.queue.add(item)
        self.assertTrue(result)
        self.assertEqual(len(self.queue.queue), 1)

    def test_add_duplicate_does_not_add(self):
        item = self._make_item("h1", "h2")
        self.queue.add(item)
        self.queue.add(item)
        self.assertEqual(len(self.queue.queue), 1)

    def test_pop_returns_item(self):
        item = self._make_item("h1", "h2")
        self.queue.add(item)
        popped = self.queue.pop()
        self.assertIsNotNone(popped)

    def test_pop_empty_returns_none(self):
        result = self.queue.pop()
        self.assertIsNone(result)

    def test_pop_removes_from_queue(self):
        item = self._make_item("h1", "h2")
        self.queue.add(item)
        self.queue.pop()
        self.assertEqual(len(self.queue.queue), 0)

    def test_add_last_popped_skips(self):
        item = self._make_item("h1", "h2")
        self.queue.add(item)
        self.queue.pop()
        # Re-add same item (same first/final hash) - should be skipped
        item2 = self._make_item("h1", "h2")
        result = self.queue.add(item2)
        self.assertIsNone(result)

    def test_to_dict(self):
        d = self.queue.to_dict()
        self.assertIn("queue", d)

    def test_add_with_block_instances(self):
        """Covers the isinstance(Block) path in add()."""
        blockchain = _make_blockchain("hash_a", "hash_b")
        item = BlockProcessingQueueItem(blockchain=blockchain)
        result = self.queue.add(item)
        self.assertTrue(result)
        self.assertEqual(len(self.queue.queue), 1)

    def test_add_block_instances_skip_last_popped(self):
        """Covers the early-return path in the Block isinstance branch."""
        blockchain = _make_blockchain("hash_x", "hash_y")
        item = BlockProcessingQueueItem(blockchain=blockchain)
        self.queue.add(item)
        self.queue.pop()  # sets last_popped = ("hash_x", "hash_y")
        item2 = BlockProcessingQueueItem(
            blockchain=_make_blockchain("hash_x", "hash_y")
        )
        result = self.queue.add(item2)
        self.assertIsNone(result)


class TestTransactionProcessingQueue(unittest.TestCase):
    def setUp(self):
        self.queue = TransactionProcessingQueue()

    def _make_item(self, sig="sig1"):
        txn = MagicMock()
        txn.transaction_signature = sig
        return TransactionProcessingQueueItem(transaction=txn)

    def test_add_item(self):
        item = self._make_item("sig1")
        result = self.queue.add(item)
        self.assertTrue(result)
        self.assertEqual(len(self.queue.queue), 1)

    def test_add_duplicate_not_added(self):
        item = self._make_item("sig1")
        self.queue.add(item)
        self.queue.add(item)
        self.assertEqual(len(self.queue.queue), 1)

    def test_pop_returns_item(self):
        item = self._make_item("sig1")
        self.queue.add(item)
        popped = self.queue.pop()
        self.assertIsNotNone(popped)

    def test_pop_empty_returns_none(self):
        result = self.queue.pop()
        self.assertIsNone(result)

    def test_add_with_ignore_last_popped(self):
        item = self._make_item("sig1")
        self.queue.add(item)
        self.queue.pop()
        # ignore_last_popped=True allows re-adding
        item2 = self._make_item("sig1")
        result = self.queue.add(item2, ignore_last_popped=True)
        self.assertTrue(result)

    def test_pop_sets_last_popped(self):
        item = self._make_item("sig_abc")
        self.queue.add(item)
        self.queue.pop()
        self.assertEqual(self.queue.last_popped, "sig_abc")

    def test_add_returns_none_when_matches_last_popped(self):
        """Covers the early-return path when sig matches last_popped."""
        item = self._make_item("sig1")
        self.queue.add(item)
        self.queue.pop()  # sets last_popped = "sig1"
        item2 = self._make_item("sig1")
        # Without ignore_last_popped, should skip because sig1 == last_popped
        result = self.queue.add(item2)
        self.assertIsNone(result)


class TestNonceProcessingQueue(unittest.TestCase):
    def setUp(self):
        self.queue = NonceProcessingQueue()

    def _make_item(self, peer_id="peer1", nonce="nonce1"):
        body = {"params": {"id": peer_id, "nonce": nonce}}
        miner = MagicMock()
        return NonceProcessingQueueItem(miner=miner, body=body)

    def test_add_item(self):
        item = self._make_item("peer1", "nonce1")
        result = self.queue.add(item)
        self.assertTrue(result)

    def test_add_duplicate_not_added(self):
        item = self._make_item("peer1", "nonce1")
        self.queue.add(item)
        self.queue.add(item)
        self.assertEqual(len(self.queue.queue), 1)

    def test_pop_returns_item(self):
        item = self._make_item("peer1", "nonce1")
        self.queue.add(item)
        popped = self.queue.pop()
        self.assertIsNotNone(popped)

    def test_pop_empty_returns_none(self):
        result = self.queue.pop()
        self.assertIsNone(result)

    def test_add_after_pop_same_skips(self):
        item = self._make_item("peer1", "nonce1")
        self.queue.add(item)
        self.queue.pop()
        item2 = self._make_item("peer1", "nonce1")
        result = self.queue.add(item2)
        self.assertIsNone(result)


class TestProcessingQueues(AsyncTestCase):
    async def test_init(self):
        pq = ProcessingQueues()
        self.assertIsNotNone(pq.block_queue)
        self.assertIsNotNone(pq.transaction_queue)

    async def test_to_dict(self):
        pq = ProcessingQueues()
        d = pq.to_dict()
        self.assertIsInstance(d, dict)

    async def test_to_status_dict(self):
        pq = ProcessingQueues()
        d = pq.to_status_dict()
        self.assertIsInstance(d, dict)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
