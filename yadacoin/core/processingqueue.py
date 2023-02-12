from time import time
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.transaction import Transaction
from yadacoin.core.job import Job
from yadacoin.core.miner import Miner
from yadacoin.core.block import Block
from yadacoin.core.config import get_config


class ProcessingQueue:
    num_items_processed = 0
    time_sum = 0

    def time_sum_start(self):
        self.start_time = time()

    def time_sum_end(self):
        self.time_sum += time() - self.start_time

    def pop(self):
        self.inc_num_items_processed()

    def inc_num_items_processed(self):
        self.num_items_processed += 1

    def to_dict(self):
        return {
            'queue': self.queue
        }

    def to_status_dict(self):
        return {
            'queue_item_count': len(self.queue.values()),
            'average_processing_time': '%.4f' % (self.time_sum / (self.num_items_processed or 1)),
            'num_items_processed': self.num_items_processed
        }


class BlockProcessingQueueItem:
    def __init__(self, blockchain: Blockchain, stream=None, body=None):
        self.blockchain = blockchain
        self.body = body or {}
        self.stream = stream


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
            if (first_block['hash'], final_block['hash']) == self.last_popped:
                return
            self.queue.setdefault((first_block['hash'], final_block['hash']), item)

    def pop(self):
        super().pop()
        if not self.queue:
            return None
        key, item = self.queue.popitem()
        self.last_popped = key
        return item


class TransactionProcessingQueueItem:
    def __init__(self, transaction: Transaction, stream=None):
        self.transaction = transaction
        self.stream = stream


class TransactionProcessingQueue(ProcessingQueue):
    def __init__(self):
        self.queue = {}
        self.last_popped = ''

    def add(self, item: TransactionProcessingQueueItem):
        if item.transaction.transaction_signature == self.last_popped:
            return
        self.queue.setdefault(item.transaction.transaction_signature, item)

    def pop(self):
        super().pop()
        if not self.queue:
            return None
        key, item = self.queue.popitem()
        self.last_popped = key
        return item


class NonceProcessingQueueItem:
    def __init__(self, miner: Miner='', stream=None, body=None):
        self.miner = miner
        self.stream = stream
        self.body = body
        self.id = body['params']['id']
        self.nonce = body['params']['nonce']


class NonceProcessingQueue(ProcessingQueue):
    def __init__(self):
        self.queue = {}
        self.last_popped = ''

    def add(self, item: NonceProcessingQueueItem):
        if (item.id, item.nonce) == self.last_popped:
            return
        self.queue.setdefault((item.id, item.nonce), item)

    def pop(self):
        super().pop()
        if not self.queue:
            return None
        key, item = self.queue.popitem()
        self.last_popped = key
        return item


class ProcessingQueues:
    def __init__(self):
        self.config = get_config()
        self.block_queue = BlockProcessingQueue()
        self.transaction_queue = TransactionProcessingQueue()
        self.queues = [
            self.block_queue,
            self.transaction_queue
        ]
        if 'pool' in self.config.modes:
            self.nonce_queue = NonceProcessingQueue()
            self.queues.append(self.nonce_queue)

    def to_dict(self):
        out = {x.__class__.__name__: x.to_dict() for x in self.queues}
        return out

    def to_status_dict(self):
        out = {x.__class__.__name__: x.to_status_dict() for x in self.queues}
        return out
