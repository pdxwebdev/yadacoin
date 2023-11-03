import sys

sys.setrecursionlimit(1000000)
import datetime
import json
import logging
from time import time
from traceback import format_exc

from tornado.iostream import StreamClosedError

from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.processingqueue import BlockProcessingQueueItem
from yadacoin.tcpsocket.pool import StratumServer


class Consensus(object):
    lowest = CHAIN.MAX_TARGET

    @classmethod
    async def init_async(
        cls, debug=False, prevent_genesis=False, target=None, special_target=None
    ):
        self = cls()
        self.app_log = logging.getLogger("tornado.application")
        self.debug = debug
        self.config = Config()
        self.mongo = self.config.mongo
        self.prevent_genesis = prevent_genesis
        self.target = target
        self.special_target = special_target
        self.syncing = False
        self.last_network_search = 0

        if self.config.LatestBlock.block:
            self.latest_block = self.config.LatestBlock.block
        else:
            if not self.prevent_genesis:
                await self.config.BU.insert_genesis()
                self.latest_block = self.config.LatestBlock.block
        return self

    async def verify_existing_blockchain(self, reset=False):
        self.app_log.info("verifying existing blockchain")
        existing_blockchain = Blockchain(
            self.config.mongo.async_db.blocks.find({}).sort([("index", 1)])
        )
        result = await existing_blockchain.verify()
        if result.get("verified"):
            print(
                "Block height: %s | time: %s"
                % (
                    self.latest_block.index,
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
            return True
        else:
            self.app_log.critical(result)
            if reset:
                if "last_good_block" in result:
                    await self.mongo.async_db.blocks.delete_many(
                        {"index": {"$gt": result["last_good_block"].index}}
                    )
                else:
                    await self.mongo.async_db.blocks.delete_many({"index": {"$gt": 0}})
                self.app_log.debug("{} {}".format(result["message"], "...truncating"))
            else:
                self.app_log.critical(
                    "{} - reset False, not truncating - DID NOT VERIFY".format(
                        result.get("message")
                    )
                )
            self.config.BU.latest_block = None

    async def process_block_queue(self):
        item = self.config.processing_queues.block_queue.pop()
        i = 0  # max loops
        while item:
            await self.process_block_queue_item(item)

            i += 1
            if i >= 100:
                self.config.app_log.info(
                    "process_block_queue: max loops exceeded, exiting"
                )
                return

            item = self.config.processing_queues.block_queue.pop()

    async def process_block_queue_item(self, item):
        self.config.processing_queues.block_queue.inc_num_items_processed()
        stream = item.stream
        body = item.body
        if body:
            if body["method"] == "blockresponse":
                payload = body.get("result", {})
                block = payload.get("block")
                if not block:
                    return
                if block["index"] > (self.config.LatestBlock.block.index + 100):
                    return
                block = await Block.from_dict(block)
                if not await self.config.consensus.insert_consensus_block(
                    block, stream.peer
                ):
                    self.config.app_log.info(
                        "newblock, error inserting consensus block"
                    )
                    return

            elif body["method"] == "newblock":
                payload = body.get("params", {}).get("payload", {})
                block = payload.get("block")
                if stream.peer.protocol_version > 1:
                    await self.config.nodeShared.write_result(
                        stream, "newblock_confirmed", body.get("params", {}), body["id"]
                    )
                if not block:
                    return

                block = await Block.from_dict(block)

                stream.peer.block = block

                if block.time > time():
                    self.config.app_log.info("newblock, block time greater than now")
                    return

                if block.index > (self.config.LatestBlock.block.index + 100):
                    self.config.app_log.info(
                        "newblock, block index greater than latest block + 100"
                    )
                    return

                if block.index < self.config.LatestBlock.block.index:
                    await self.config.nodeShared.write_params(
                        stream,
                        "newblock",
                        {"payload": {"block": self.config.LatestBlock.block.to_dict()}},
                    )
                    self.config.app_log.info(
                        f"block index less than our latest block index: {block.index} < {self.config.LatestBlock.block.index} | {stream.peer.identity.to_dict}"
                    )
                    return

                if not await self.config.consensus.insert_consensus_block(
                    block, stream.peer
                ):
                    self.config.app_log.info(
                        "newblock, error inserting consensus block"
                    )
                    return

        self.config.processing_queues.block_queue.time_sum_start()
        if isinstance(item.blockchain.init_blocks, list):
            first_block = await Block.from_dict(item.blockchain.first_block)
        else:
            first_block = await Block.from_dict(await item.blockchain.async_first_block)

        if isinstance(item.blockchain.init_blocks, list):
            final_block = await Block.from_dict(item.blockchain.final_block)
        else:
            final_block = await Block.from_dict(await item.blockchain.async_final_block)

        first_existing = await self.mongo.async_db.blocks.find_one(
            {
                "hash": first_block.hash,
            }
        )

        final_existing = await self.mongo.async_db.blocks.find_one(
            {
                "hash": final_block.hash,
            }
        )

        if first_existing and final_existing:
            return

        count = await item.blockchain.count

        if count < 1:
            return
        elif count == 1:
            await self.integrate_block_with_existing_chain(first_block, stream)
        else:
            await self.integrate_blocks_with_existing_chain(item.blockchain, stream)

    async def remove_pending_transactions_now_in_chain(self, block):
        # remove transactions from miner_transactions collection in the blockchain
        await self.mongo.async_db.miner_transactions.delete_many(
            {"id": {"$in": [x["id"] for x in block["block"]["transactions"]]}}
        )

    async def insert_consensus_block(self, block, peer):
        existing = await self.mongo.async_db.consensus.find_one(
            {
                "index": block.index,
                "peer.rid": peer.rid,
                "id": block.signature,
            }
        )
        if existing:
            return True
        try:
            await block.verify()
        except:
            return False
        self.app_log.info(
            "inserting new consensus block for height and peer: %s %s"
            % (block.index, peer.to_string())
        )
        await self.mongo.async_db.consensus.delete_many(
            {"index": block.index, "peer.rid": peer.rid}
        )
        await self.mongo.async_db.consensus.insert_one(
            {
                "block": block.to_dict(),
                "index": block.index,
                "id": block.signature,
                "peer": peer.to_dict(),
            }
        )
        return True

    async def sync_bottom_up(self, synced):
        # bottom up syncing

        last_latest = self.latest_block
        self.latest_block = self.config.LatestBlock.block
        if last_latest:
            if self.latest_block.index > last_latest.index:
                self.app_log.info(
                    "Block height: %s | time: %s"
                    % (
                        self.latest_block.index,
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    )
                )
        self.config.health.consensus.last_activity = time()
        latest_consensus = await self.mongo.async_db.consensus.find_one(
            {
                "index": self.latest_block.index + 1,
                "block.version": CHAIN.get_version_for_height(
                    self.latest_block.index + 1
                ),
                "ignore": {"$ne": True},
            }
        )
        if latest_consensus:
            await self.remove_pending_transactions_now_in_chain(latest_consensus)
            latest_consensus = await Block.from_dict(latest_consensus["block"])
            if self.debug:
                self.app_log.info(
                    "Latest consensus_block {}".format(latest_consensus.index)
                )

            records = await self.mongo.async_db.consensus.find(
                {
                    "index": self.latest_block.index + 1,
                    "block.version": CHAIN.get_version_for_height(
                        self.latest_block.index + 1
                    ),
                    "ignore": {"$ne": True},
                }
            ).to_list(length=100)
            for record in sorted(records, key=lambda x: int(x["block"]["target"], 16)):
                stream = await self.config.peer.get_peer_by_id(record["peer"]["rid"])
                if stream and hasattr(stream, "peer") and stream.peer.authenticated:
                    self.config.processing_queues.block_queue.add(
                        BlockProcessingQueueItem(Blockchain(record["block"]), stream)
                    )

            return True
        else:
            #  this path is for syncing only.
            #  Stack:
            #    search_network_for_new
            #    request_blocks
            #    getblocks <--- rpc request
            #    blocksresponse <--- rpc response
            #    process_block_queue
            if (time() - self.last_network_search) > 30 or not synced:
                self.last_network_search = time()
                return await self.search_network_for_new()

    async def search_network_for_new(self):
        if self.config.network == "regnet":
            return False

        if self.syncing:
            return False

        async for peer in self.config.peer.get_sync_peers():
            if peer.synced or peer.message_queue.get("getblocks"):
                continue
            try:
                peer.syncing = True
                await self.request_blocks(peer)
                break # there is no point in downloading the same blocks from each node, TODO use random node selection or download a different blocks interval from each of them
            except StreamClosedError:
                peer.close()
            except Exception as e:
                self.config.app_log.warning(e)
            self.config.health.consensus.last_activity = time()

    async def request_blocks(self, peer):
        await self.config.nodeShared.write_params(
            peer,
            "getblocks",
            {
                "start_index": int(self.config.LatestBlock.block.index) + 1,
                "end_index": int(self.config.LatestBlock.block.index) + 100,
            },
        )

    async def build_local_chain(self, block: Block):
        local_blocks = self.config.mongo.async_db.blocks.find(
            {"index": {"$gte": block.index}}
        ).sort([("index", 1)])
        return Blockchain(local_blocks, partial=True)

    async def build_remote_chain(self, block: Block):
        # now we just need to see how far this chain extends
        blocks = [block]
        while True:
            # get the heighest block from this chain
            local_block = await self.config.mongo.async_db.blocks.find_one(
                {"prevHash": block.hash}, {"_id": 0}
            )
            if local_block:
                local_block = await Block.from_dict(local_block)
                block = local_block
                blocks.append(local_block)
            else:
                consensus_block = await self.config.mongo.async_db.consensus.find_one(
                    {"block.prevHash": block.hash}, {"_id": 0}
                )
                if consensus_block:
                    consensus_block = await Block.from_dict(consensus_block["block"])
                    block = consensus_block
                    blocks.append(consensus_block)
            if not local_block and not consensus_block:
                break

        blocks.sort(key=lambda x: x.index)

        return Blockchain(blocks, partial=True)

    async def get_previous_consensus_block_from_local(self, block):
        # table cleanup
        new_blocks = self.mongo.async_db.consensus.find(
            {
                "block.hash": block.prev_hash,
                "block.index": (block.index - 1),
                "block.version": CHAIN.get_version_for_height((block.index - 1)),
            }
        )
        async for new_block in new_blocks:
            new_block = await Block.from_dict(new_block["block"])
            yield new_block

    async def get_previous_consensus_block(self, block, stream=None):
        had_results = False
        async for local_block in self.get_previous_consensus_block_from_local(block):
            had_results = True
            yield local_block
        if stream and not had_results:
            await self.config.nodeShared.write_params(
                stream, "getblock", {"hash": block.prev_hash, "index": block.index - 1}
            )

    async def build_backward_from_block_to_fork(
        self, block, blocks, stream=None, depth=0
    ):
        self.app_log.debug(f"build_backward_from_block_to_fork: {block.index}")

        retrace_block = await self.mongo.async_db.blocks.find_one(
            {"hash": block.prev_hash, "time": {"$lt": block.time}}
        )
        if retrace_block:
            return blocks, True

        retrace_consensus_block = [
            x async for x in self.get_previous_consensus_block(block, stream)
        ]
        if not retrace_consensus_block:
            return blocks, False

        retrace_consensus_block = retrace_consensus_block[0]

        if blocks is None:
            blocks = []

        backward_blocks, status = await self.build_backward_from_block_to_fork(
            retrace_consensus_block,
            json.loads(json.dumps([x for x in blocks])),
            stream,
            depth + 1,
        )
        backward_blocks.append(retrace_consensus_block)
        return backward_blocks, status

    async def integrate_block_with_existing_chain(self, block: Block, stream):
        self.app_log.debug("integrate_block_with_existing_chain")
        backward_blocks, status = await self.build_backward_from_block_to_fork(
            block, [], stream
        )

        if not status:
            self.app_log.debug("integrate_block_with_existing_chain: status is false")
            return

        forward_blocks_chain = await self.build_remote_chain(block)  # contains block

        inbound_blockchain = Blockchain(
            sorted(
                backward_blocks + [x async for x in forward_blocks_chain.blocks],
                key=lambda x: x.index,
            )
        )

        if not await inbound_blockchain.is_consecutive:
            self.app_log.debug(
                "integrate_block_with_existing_chain: inbound_blockchain.is_consecutive is false"
            )
            return False

        await self.integrate_blocks_with_existing_chain(inbound_blockchain, stream)

    async def integrate_blocks_with_existing_chain(self, blockchain, stream):
        self.app_log.debug("integrate_blocks_with_existing_chain")

        extra_blocks = [x async for x in blockchain.blocks]
        prev_block = None
        i = 0
        async for block in blockchain.blocks:
            if self.config.network == "regnet":
                break
            if not await Blockchain.test_block(
                block, extra_blocks=extra_blocks, simulate_last_block=prev_block
            ):
                good_blocks = [x async for x in blockchain.get_blocks(0, i)]
                if good_blocks:
                    blockchain = Blockchain(good_blocks, True)
                    break
                else:
                    return
            prev_block = block
            i += 1

        if isinstance(blockchain.init_blocks, list):
            first_block = await Block.from_dict(blockchain.first_block)
        else:
            first_block = await Block.from_dict(await blockchain.async_first_block)

        existing_blockchain = Blockchain(
            self.config.mongo.async_db.blocks.find(
                {"index": {"$gte": first_block.index}}
            ),
            partial=True,
        )

        if not await existing_blockchain.test_inbound_blockchain(blockchain):
            if isinstance(blockchain.init_blocks, list):
                final_block = blockchain.final_block
            else:
                final_block = await blockchain.async_final_block
            if stream:
                await self.config.nodeShared.write_params(
                    stream, "getblock", {"index": final_block.index + 1}
                )
            return

        async for block in blockchain.blocks:
            if (
                not await Blockchain.test_block(block)
                and self.config.network == "mainnet"
            ):
                return
            await self.insert_block(block, stream)

        if stream:
            stream.syncing = False

    async def insert_block(self, block, stream):
        self.app_log.debug("insert_block")
        try:
            await self.mongo.async_db.blocks.delete_many(
                {"index": {"$gte": block.index}}
            )

            db_block = block.to_dict()

            db_block["updated_at"] = time()

            await self.mongo.async_db.blocks.replace_one(
                {"index": block.index}, db_block, upsert=True
            )

            await self.mongo.async_db.miner_transactions.delete_many(
                {"id": {"$in": [x.transaction_signature for x in block.transactions]}}
            )

            await self.config.LatestBlock.update_latest_block()

            self.app_log.info("New block inserted for height: {}".format(block.index))

            if self.config.mp:
                if self.syncing or (hasattr(stream, "syncing") and stream.syncing):
                    return True
                try:
                    await self.config.mp.refresh()
                except Exception:
                    self.app_log.warning("{}".format(format_exc()))

                try:
                    await StratumServer.block_checker()
                except Exception:
                    self.app_log.warning("{}".format(format_exc()))

            return True
        except Exception:
            from traceback import format_exc

            self.app_log.warning("{}".format(format_exc()))
