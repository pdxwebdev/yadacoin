"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from time import time

from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.config import Config
from yadacoin.core.miner import Miner
from yadacoin.core.transaction import Transaction
from yadacoin.enums.modes import MODES


class ProcessingQueue:
    num_items_processed = 0
    time_sum = 0

    def time_sum_start(self):
        self.start_time = time()

    def time_sum_end(self):
        self.time_sum += time() - self.start_time

    def inc_num_items_processed(self):
        self.num_items_processed += 1

    def to_dict(self):
        return {"queue": self.queue}

    def to_status_dict(self):
        return {
            "queue_item_count": len(self.queue.values()),
            "average_processing_time": "%.4f"
            % (self.time_sum / (self.num_items_processed or 1)),
            "num_items_processed": self.num_items_processed,
        }


class BlockProcessingQueueItem:
    def __init__(self, blockchain: Blockchain, stream=None, body=None, source="unknown"):
        self.blockchain = blockchain
        self.body = body or {}
        self.stream = stream
        self.source = source


class BlockProcessingQueue(ProcessingQueue):
    def __init__(self):
        self.queue = {}
        self.last_popped = ()

    def add(self, item: BlockProcessingQueueItem):
        first_block = item.blockchain.first_block
        final_block = item.blockchain.final_block
        if isinstance(first_block, Block) and isinstance(final_block, Block):
            if (first_block.hash, final_block.hash) == self.last_popped:
                return
            self.queue.setdefault((first_block.hash, final_block.hash), item)
        else:
            if (first_block["hash"], final_block["hash"]) == self.last_popped:
                return
            self.queue.setdefault((first_block["hash"], final_block["hash"]), item)
        return True

    def pop(self):
        if not self.queue:
            return None
        key, item = self.queue.popitem()
        self.last_popped = key
        return item


class TransactionProcessingQueueItem:
    def __init__(self, transaction: Transaction, stream=None, retry_time: int = None):
        self.transaction = transaction
        self.stream = stream
        self.retry_time = retry_time


class TransactionProcessingQueue(ProcessingQueue):
    def __init__(self):
        self.queue = {}
        self.last_popped = ""

    def add(self, item: TransactionProcessingQueueItem):
        if item.transaction.transaction_signature == self.last_popped:
            return
        self.queue.setdefault(item.transaction.transaction_signature, item)
        return True

    def pop(self):
        if not self.queue:
            return None
        key, item = self.queue.popitem()
        self.last_popped = key
        return item


class NonceProcessingQueueItem:
    def __init__(self, miner: Miner = "", stream=None, body=None):
        self.miner = miner
        self.stream = stream
        self.body = body
        self.id = body["params"]["id"]
        self.nonce = body["params"]["nonce"]


class NonceProcessingQueue(ProcessingQueue):
    def __init__(self):
        self.queue = {}
        self.last_popped = ""

    def add(self, item: NonceProcessingQueueItem):
        if (item.id, item.nonce) == self.last_popped:
            return
        self.queue.setdefault((item.id, item.nonce), item)
        return True

    def pop(self):
        if not self.queue:
            return None
        key, item = self.queue.popitem()
        self.last_popped = key
        return item


class ProcessingQueues:
    def __init__(self):
        self.config = Config()
        self.block_queue = BlockProcessingQueue()
        self.transaction_queue = TransactionProcessingQueue()
        self.queues = [self.block_queue, self.transaction_queue]
        if MODES.POOL.value in self.config.modes:
            self.nonce_queue = NonceProcessingQueue()
            self.queues.append(self.nonce_queue)

    def to_dict(self):
        out = {x.__class__.__name__: x.to_dict() for x in self.queues}
        return out

    def to_status_dict(self):
        out = {x.__class__.__name__: x.to_status_dict() for x in self.queues}
        return out
