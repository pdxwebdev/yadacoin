import binascii
import time
import json
import random
import uuid
import asyncio
import secrets

from logging import getLogger
from decimal import Decimal
from datetime import datetime, timedelta

from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.job import Job
from yadacoin.core.peer import Peer
from yadacoin.core.miner import Miner
from yadacoin.core.health import Health
from yadacoin.core.processingqueue import BlockProcessingQueueItem
from yadacoin.core.transaction import Transaction
from yadacoin.core.transactionutils import TU
from yadacoin.tcpsocket.pool import StratumServer
from tornado.iostream import StreamClosedError


class MiningPool(object):
    def __init__(self):
        self.used_extra_nonces = set()
        self.last_header = None

    @classmethod
    async def init_async(cls):
        self = cls()
        self.config = Config()
        self.mongo = self.config.mongo
        self.app_log = getLogger("tornado.application")
        self.target_block_time = CHAIN.target_block_time(self.config.network)
        self.max_target = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        self.inbound = {}
        self.connected_ips = {}
        self.last_block_time = 0
        self.index = 0
        last_block = await self.config.LatestBlock.block.copy()
        self.refreshing = False
        if last_block:
            self.last_block_time = int(last_block.time)
            self.index = last_block.index
        self.last_refresh = 0
        self.block_factory = None
        await self.refresh()
        return self

    def get_status(self):
        """Returns pool status as explicit dict"""
        status = {"miners": len(self.inbound), "ips": len(self.connected_ips)}
        return status

    async def process_nonce_queue(self):
        item = await self.config.processing_queues.nonce_queue.pop()
        i = 0  # max loops
        while item:
            await self.config.processing_queues.nonce_queue.time_sum_start()
            self.config.processing_queues.nonce_queue.inc_num_items_processed()
            body = item.body
            miner = item.miner
            stream = item.stream
            nonce = body["params"].get("nonce")
            job_id = body["params"]["id"]
            job = stream.jobs[body["params"]["id"] or body["params"]["job_id"]]
            if type(nonce) is not str:
                result = {"error": True, "message": "nonce is wrong data type"}
                self.update_failed_share_count(miner.peer_id)
            if len(nonce) > CHAIN.MAX_NONCE_LEN:
                result = {"error": True, "message": "nonce is too long"}
                self.update_failed_share_count(miner.peer_id)
            data = {
                "id": body.get("id"),
                "method": body.get("method"),
                "jsonrpc": body.get("jsonrpc"),
            }
            data["result"] = await self.process_nonce(miner, nonce, job)
            if not data["result"]:
                data["error"] = {"code": "-1", "message": "Share rejected due to invalid data or expiration."}
                self.config.processing_queues.nonce_queue.inc_num_invalid_items()
            try:
                await stream.write("{}\n".format(json.dumps(data)).encode())
            except:
                pass

            await StratumServer.block_checker()
            await self.config.processing_queues.nonce_queue.time_sum_end()
            self.config.health.nonce_processor.last_activity = int(time.time())

            i += 1
            if i >= 5000:
                self.config.app_log.info(
                    "process_nonce_queue: max loops exceeded, exiting"
                )
                return

            item = await self.config.processing_queues.nonce_queue.pop()

    async def process_nonce(self, miner, nonce, job):
        nonce = nonce + job.extra_nonce
        header = job.header
        self.config.app_log.debug(f"Extra Nonce for job {job.index}: {job.extra_nonce}")
        self.config.app_log.debug(f"Nonce for job {job.index}: {nonce}")
        hash1 = self.block_factory.generate_hash_from_header(job.index, header, nonce)
        self.config.app_log.debug(f"Hash1 for job {job.index}: {hash1}")
        if self.block_factory.index >= CHAIN.BLOCK_V5_FORK:
            hash1_test = Blockchain.little_hash(hash1)
        else:
            hash1_test = hash1

        if (
            int(hash1_test, 16) > self.block_factory.target
            and self.config.network != "regnet"
            and (
                self.block_factory.special_min
                and int(hash1, 16) > self.block_factory.special_target
            )
        ):
            return False
        block_candidate = await self.block_factory.copy()
        block_candidate.hash = hash1
        block_candidate.nonce = nonce

        if block_candidate.special_min:
            delta_t = int(block_candidate.time) - int(self.last_block_time)
            special_target = CHAIN.special_target(
                block_candidate.index,
                block_candidate.target,
                delta_t,
                self.config.network,
            )
            block_candidate.special_target = special_target

        if (
            block_candidate.index >= 35200
            and (int(block_candidate.time) - int(self.last_block_time)) < 600
            and block_candidate.special_min
            and self.config.network == "mainnet"
        ):
            self.app_log.warning(
                "Special min block too soon: hash {} header {} nonce {}".format(
                    block_candidate.hash, block_candidate.header, block_candidate.nonce
                )
            )
            return False

        accepted = False

        target = 0x0000FFFF00000000000000000000000000000000000000000000000000000000

        if block_candidate.index >= CHAIN.BLOCK_V5_FORK:
            test_hash = int(Blockchain.little_hash(block_candidate.hash), 16)
        else:
            test_hash = int(hash1, 16)

        if test_hash < target:
            # submit share only now, not to slow down if we had a block
            await self.mongo.async_db.shares.update_one(
                {"hash": block_candidate.hash},
                {
                    "$set": {
                        "address": miner.address,
                        "address_only": miner.address_only,
                        "index": block_candidate.index,
                        "hash": block_candidate.hash,
                        "nonce": nonce,
                        "weight": job.miner_diff,
                        "time": int(time.time()),
                    }
                },
                upsert=True,
            )

            accepted = True

        if block_candidate.index >= CHAIN.BLOCK_V5_FORK:
            test_hash = int(Blockchain.little_hash(block_candidate.hash), 16)
        else:
            test_hash = int(block_candidate.hash, 16)

        if test_hash < int(block_candidate.target) or self.config.network == "regnet":
            block_candidate.signature = self.config.BU.generate_signature(
                block_candidate.hash, self.config.private_key
            )

            if header != block_candidate.header:
                return {
                    "hash": block_candidate.hash,
                    "nonce": nonce,
                    "height": block_candidate.index,
                    "id": block_candidate.signature,
                }
            try:
                await block_candidate.verify()
            except Exception:
                if accepted and self.config.network == "mainnet":
                    return {
                        "hash": hash1,
                        "nonce": nonce,
                        "height": job.index,
                        "id": block_candidate.signature,
                    }

                return False
            # accept winning block
            await self.accept_block(block_candidate)
            # Conversion to dict is important, or the object may change
            self.app_log.debug("block ok")

            return {
                "accepted": accepted,
                "hash": block_candidate.hash,
                "nonce": nonce,
                "height": block_candidate.index,
                "id": block_candidate.signature,
            }
        elif (
            block_candidate.special_min
            and (int(block_candidate.special_target) > int(block_candidate.hash, 16))
            or (
                block_candidate.index >= CHAIN.BLOCK_V5_FORK
                and block_candidate.special_min
                and (
                    int(block_candidate.special_target)
                    > int(Blockchain.little_hash(block_candidate.hash), 16)
                )
            )
        ):
            block_candidate.signature = self.config.BU.generate_signature(
                block_candidate.hash, self.config.private_key
            )

            try:
                await block_candidate.verify()
            except Exception as e:
                if accepted:
                    return {
                        "hash": hash1,
                        "nonce": nonce,
                        "height": job.index,
                        "id": block_candidate.signature,
                    }
                self.app_log.warning(
                    "Verify error {} - hash {} header {} nonce {}".format(
                        e,
                        block_candidate.hash,
                        block_candidate.header,
                        block_candidate.nonce,
                    )
                )
                return False
            # accept winning block
            await self.accept_block(block_candidate)
            # Conversion to dict is important, or the object may change
            self.app_log.debug("block ok - special_min")

            return {
                "hash": block_candidate.hash,
                "nonce": nonce,
                "height": block_candidate.index,
                "id": block_candidate.signature,
            }

        if accepted:
            return {
                "hash": block_candidate.hash,
                "nonce": nonce,
                "height": block_candidate.index,
                "id": block_candidate.signature,
            }

    async def refresh(self):
        """Refresh computes a new bloc to mine. The block is stored in self.block_factory and contains
        the transactions at the time of the refresh. Since tx hash is in the header, a refresh here means we have to
        trigger the events for the pools, even if the block index did not change."""
        # TODO: to be taken care of, no refresh atm between blocks
        try:
            if self.refreshing:
                return
            self.refreshing = True
            await self.config.LatestBlock.block_checker()
            if self.block_factory:
                self.last_block_time = int(self.block_factory.time)
            self.block_factory = await self.create_block(
                await self.get_pending_transactions(),
                self.config.public_key,
                self.config.private_key,
                index=self.config.LatestBlock.block.index + 1,
            )
            self.block_factory.header = self.block_factory.generate_header()
            self.refreshing = False
        except Exception:
            self.refreshing = False
            from traceback import format_exc

            self.app_log.error("Exception {} mp.refresh".format(format_exc()))
            raise

    async def create_block(self, transactions, public_key, private_key, index):
        return await Block.generate(transactions, public_key, private_key, index=index)

    async def block_to_mine_info(self):
        """Returns info for current block to mine"""
        if self.block_factory is None:
            # await self.refresh()
            return {}
        target = hex(int(self.block_factory.target))[2:].rjust(64, "0")
        self.config.app_log.info("Target: %s", target)
        res = {
            "target": target,  # target is now in hex format
            "special_target": hex(int(self.block_factory.special_target))[2:].rjust(
                64, "0"
            ),  # target is now in hex format
            # TODO this is the network target, maybe also send some pool target?
            "special_min": self.block_factory.special_min,
            "header": self.block_factory.header,
            "version": self.block_factory.version,
            "height": self.block_factory.index,  # This is the height of the one we are mining
            "previous_time": self.config.LatestBlock.block.time,  # needed for miner to recompute the real diff
        }
        return res

    async def block_template(self, agent, custom_diff, peer_id, miner_diff):
        """Returns info for the current block to mine"""
        if self.block_factory is None:
            await self.refresh()
        if not self.block_factory.target:
            await self.set_target_from_last_non_special_min(
                self.config.LatestBlock.block
            )

        job = await self.generate_job(agent, custom_diff, peer_id, miner_diff)
        return job

    async def generate_job(self, agent, custom_diff, peer_id, miner_diff):
        difficulty = int(self.max_target / self.block_factory.target)
        seed_hash = "4181a493b397a733b083639334bc32b407915b9a82b7917ac361816f0a1f5d4d"  # sha256(yadacoin65000)
        job_id = str(uuid.uuid4())
        header = self.block_factory.header

        # Check if header has changed
        if header != self.last_header:
            self.last_header = header
            self.used_extra_nonces.clear()  # Reset used extra nonces

        self.config.app_log.info(f"Job header: {header}")

        extra_nonce = self.generate_unique_extra_nonce()
        blob = header.encode().hex().replace("7b6e6f6e63657d", "00000000" + extra_nonce)
        miner_diff = max(int(custom_diff), 70000) if custom_diff is not None else miner_diff

        if "XMRigCC/3" in agent or "XMRig/6" in agent or "xmrigcc-proxy" in agent:
            target = hex(0x10000000000000001 // miner_diff)[2:].zfill(16)
        elif miner_diff <= 69905:
            target = hex(
                0x10000000000000001 // miner_diff - 0x0000F00000000000
            )[2:].zfill(48)
        else:
            target = "-" + hex(
                0x10000000000000001 // miner_diff - 0x0000F00000000000
            )[3:].zfill(48)

        res = {
            "job_id": job_id,
            "peer_id": peer_id,
            "header": header,
            "difficulty": difficulty,
            "target": target,  # can only be 16 characters long
            "blob": blob,
            "seed_hash": seed_hash,
            "height": self.config.LatestBlock.block.index + 1,  # This is the height of the one we are mining
            "extra_nonce": extra_nonce,
            "algo": "rx/yada",
            "miner_diff": miner_diff,
            "agent": agent,
        }

        self.config.app_log.debug(f"Generated job: {res}")
        self.config.app_log.info(f"Used extra nonces: {self.used_extra_nonces}")

        return await Job.from_dict(res)

    def generate_unique_extra_nonce(self):
        extra_nonce = secrets.token_hex(1)
        while extra_nonce in self.used_extra_nonces:
            extra_nonce = secrets.token_hex(1)
        self.used_extra_nonces.add(extra_nonce)
        return extra_nonce

    async def set_target_as_previous_non_special_min(self):
        """TODO: this is not correct, should use a cached version of the current target somewhere, and recalc on
        new block event if we cross a boundary (% 2016 currently). Beware, at boundary we need to recalc the new diff one block ahead
        that is, if we insert block before a boundary, we have to calc the diff for the next one right away.
        """
        self.app_log.error(
            "set_target_as_previous_non_special_min should not be called anymore"
        )
        res = await self.mongo.async_db.blocks.find_one(
            {
                "special_min": False,
            },
            {"target": 1},
            sort=[("index", -1)],
        )

        if res:
            self.block_factory.target = int(res["target"], 16)

    async def set_target_from_last_non_special_min(self, latest_block):
        if self.index >= CHAIN.FORK_10_MIN_BLOCK:
            self.block_factory.target = await CHAIN.get_target_10min(
                latest_block, self.block_factory
            )
        else:
            self.block_factory.target = await CHAIN.get_target(
                self.index, latest_block, self.block_factory
            )

    async def get_inputs(self, inputs):
        for x in inputs:
            yield x

    async def get_pending_transactions(self):
        mempool_smart_contract_objs = {}
        transaction_objs = {}
        used_sigs = []
        async for txn in self.mongo.async_db.miner_transactions.find(
            {"relationship.smart_contract": {"$exists": True}}
        ).sort([("fee", -1), ("time", 1)]):
            transaction_obj = await self.verify_pending_transaction(txn, used_sigs)
            if not isinstance(transaction_obj, Transaction):
                continue

            if (
                transaction_obj.relationship.identity.wif in mempool_smart_contract_objs
                and int(transaction_obj.time)
                > int(
                    mempool_smart_contract_objs[
                        transaction_obj.relationship.identity.wif
                    ].time
                )
            ):
                continue

            mempool_smart_contract_objs[
                transaction_obj.relationship.identity.wif
            ] = transaction_obj

        async for txn in self.mongo.async_db.miner_transactions.find(
            {"relationship.smart_contract": {"$exists": False}}
        ).sort([("fee", -1), ("time", 1)]):
            transaction_obj = await self.verify_pending_transaction(txn, used_sigs)
            if not isinstance(transaction_obj, Transaction):
                continue
            if transaction_obj.private == True:
                transaction_obj.relationship = ""

            transaction_objs.setdefault(transaction_obj.requested_rid, [])
            transaction_objs[transaction_obj.requested_rid].append(transaction_obj)

        # process recurring payments
        generated_txns = []
        async for x in await TU.get_current_smart_contract_txns(
            self.config, self.config.LatestBlock.block.index
        ):
            try:
                smart_contract_txn = Transaction.from_dict(x["transactions"])
            except:
                continue
            try:
                async for trigger_txn_block in await TU.get_trigger_txns(
                    smart_contract_txn
                ):  # process blockchain txns
                    trigger_txn = Transaction.from_dict(
                        trigger_txn_block.get("transactions")
                    )
                    try:
                        payout_txn = await smart_contract_txn.relationship.process(
                            smart_contract_txn,
                            trigger_txn,
                            TU.get_transaction_objs_list(transaction_objs)
                            + generated_txns,
                        )
                        if payout_txn:
                            generated_txns.append(payout_txn)
                    except:
                        pass
            except:
                pass

        # process expired contracts
        used_public_keys = []
        async for x in await TU.get_expired_smart_contract_txns(
            self.config, self.config.LatestBlock.block.index
        ):
            expired_blockchain_smart_contract_obj = Transaction.from_dict(
                x.get("transactions")
            )
            if expired_blockchain_smart_contract_obj.public_key in used_public_keys:
                continue
            payout_txn = (
                await expired_blockchain_smart_contract_obj.relationship.expire(
                    expired_blockchain_smart_contract_obj
                )
            )
            if payout_txn:
                generated_txns.append(payout_txn)
                used_public_keys.append(
                    expired_blockchain_smart_contract_obj.public_key
                )

        return (
            list(mempool_smart_contract_objs.values())
            + TU.get_transaction_objs_list(transaction_objs)
            + generated_txns
        )

    async def verify_pending_transaction(self, txn, used_sigs):
        try:
            if isinstance(txn, Transaction):
                transaction_obj = txn
            elif isinstance(txn, dict):
                transaction_obj = Transaction.from_dict(txn)
            else:
                self.config.app_log.warning("transaction unrecognizable, skipping")
                return

            if (
                self.config.LatestBlock.block.index + 1 >= CHAIN.TXN_V3_FORK
                and transaction_obj.version < 3
            ):
                self.config.app_log.warning("transaction version too old, skipping")
                return

            transaction_obj.contract_generated = (
                await transaction_obj.is_contract_generated()
            )

            await transaction_obj.verify()

            if transaction_obj.transaction_signature in used_sigs:
                self.config.app_log.warning("duplicate transaction found and removed")
                return
            used_sigs.append(transaction_obj.transaction_signature)

            failed1 = False
            failed2 = False
            used_ids_in_this_txn = []

            async for x in self.get_inputs(transaction_obj.inputs):
                is_input_spent = await self.config.BU.is_input_spent(
                    x.id, transaction_obj.public_key
                )
                if is_input_spent:
                    failed1 = True
                if x.id in used_ids_in_this_txn:
                    failed2 = True
                used_ids_in_this_txn.append(x.id)
            if failed1:
                self.config.app_log.warning(
                    "transaction removed: input spent already {}".format(
                        transaction_obj.transaction_signature
                    )
                )
                await self.mongo.async_db.miner_transactions.delete_many(
                    {"id": transaction_obj.transaction_signature}
                )
                await self.mongo.async_db.failed_transactions.insert_one(
                    {"reason": "input spent already", "txn": transaction_obj.to_dict()}
                )
            elif failed2:
                self.config.app_log.warning(
                    "transaction removed: using an input used by another transaction in this block {}".format(
                        transaction_obj.transaction_signature
                    )
                )
                await self.mongo.async_db.miner_transactions.delete_many(
                    {"id": transaction_obj.transaction_signature}
                )
                await self.mongo.async_db.failed_transactions.insert_one(
                    {
                        "reason": "using an input used by another transaction in this block",
                        "txn": transaction_obj.to_dict(),
                    }
                )
            else:
                return transaction_obj

        except Exception as e:
            await Transaction.handle_exception(e, transaction_obj)

    async def update_pool_stats(self):
        await self.config.LatestBlock.block_checker()

        expected_blocks = 144
        mining_time_interval = 600

        pipeline = [
            {
                "$match": {
                    "time": {"$gte": time.time() - mining_time_interval}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_weight": {"$sum": "$weight"}
                }
            }
        ]

        result = await self.config.mongo.async_db.shares.aggregate(pipeline).to_list(1)

        if result and len(result) > 0:
            total_weight = result[0]["total_weight"]
            pool_hash_rate = total_weight / mining_time_interval
        else:
            pool_hash_rate = 0

        daily_blocks_found = await self.config.mongo.async_db.blocks.count_documents(
            {"time": {"$gte": time.time() - (600 * 144)}}
        )
        avg_block_time = daily_blocks_found / expected_blocks * 600
        if daily_blocks_found > 0:
            net_target = self.config.LatestBlock.block.target
        avg_blocks_found = self.config.mongo.async_db.blocks.find(
            {"time": {"$gte": time.time() - (600 * 36)}},
            projection={"_id": 0, "target": 1}
        )

        avg_block_targets = [block["target"] async for block in avg_blocks_found]
        if avg_block_targets:
            avg_net_target = sum(int(target, 16) for target in avg_block_targets) / len(avg_block_targets)
            avg_net_difficulty = (
                0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
                / avg_net_target
            )
            net_difficulty = (
                0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
                / net_target
            )
            avg_network_hash_rate = (
                len(avg_block_targets)
                / 36
                * avg_net_difficulty
                * 2**16
                / avg_block_time
            )
            network_hash_rate = net_difficulty * 2**16 / 600
        else:
            avg_network_hash_rate = 1
            net_difficulty = (
                0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
                / 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
            )
            network_hash_rate = 0

        await self.config.mongo.async_db.pool_info.insert_one(
            {
                "pool_hash_rate": pool_hash_rate,
                "network_hash_rate": network_hash_rate,
                "net_difficulty": net_difficulty,
                "avg_network_hash_rate": avg_network_hash_rate,
                "time": int(time.time()),
            }
        )

    async def clean_pool_info(self):
        current_time = time.time()
        retention_time = current_time - (48 * 60 * 60)  # 48 hours in seconds

        result = await self.config.mongo.async_db.pool_info.delete_many({"time": {"$lt": retention_time}})
        self.config.app_log.info(f"Deleted {result.deleted_count} documents from the pool_info collection")

    async def clean_shares(self):
        current_time = time.time()
        retention_time = current_time - (14 * 24 * 60 * 60)  # 14 days in seconds

        result = await self.config.mongo.async_db.shares.delete_many({"time": {"$lt": retention_time}})
        self.config.app_log.info(f"Deleted {result.deleted_count} documents from the shares collection")

    async def update_miners_stats(self):
        miner_hashrate_seconds = 1200
        current_time = int(time.time())

        hashrate_query = {"time": {"$gt": current_time - miner_hashrate_seconds}}

        hashrate_cursor = self.config.mongo.async_db.shares.aggregate([
            {"$match": hashrate_query},
            {"$group": {
                "_id": {
                    "address": {"$ifNull": [{"$arrayElemAt": [{"$split": ["$address", "."]}, 0]}, "No address"]},
                    "worker": {"$ifNull": [{"$arrayElemAt": [{"$split": ["$address", "."]}, 1]}, "No worker"]}
                },
                "number_of_shares": {"$sum": 1}
            }}
        ])

        worker_hashrate = {}
        miner_stats = []
        total_hashrate = 0

        async for doc in hashrate_cursor:
            address = doc["_id"]["address"]
            worker_name = doc["_id"]["worker"]
            number_of_shares = doc["number_of_shares"]

            worker_hashrate_individual = number_of_shares * self.config.pool_diff // miner_hashrate_seconds
            total_hashrate += worker_hashrate_individual

            if address not in worker_hashrate:
                worker_hashrate[address] = {}

            if worker_name not in worker_hashrate[address]:
                worker_hashrate[address][worker_name] = {
                    "worker_hashrate": 0
                }

            worker_hashrate[address][worker_name]["worker_hashrate"] += worker_hashrate_individual

        for address, worker_data in worker_hashrate.items():
            address_stats = []
            total_address_hashrate = 0
            for worker_name, data in worker_data.items():
                hashrate_data = {
                    "worker_name": worker_name,
                    "worker_hashrate": data["worker_hashrate"],
                }
                address_stats.append(hashrate_data)
                total_address_hashrate += data["worker_hashrate"]
            miner_stats.append({"miner_address": address, "worker_stats": address_stats, "total_hashrate": total_address_hashrate})

        miners_stats_data = {
            "time": int(time.time()),
            "miner_stats": miner_stats,
            "total_hashrate": total_hashrate
        }

        await self.config.mongo.async_db.miners_stats.insert_one(miners_stats_data)

    async def accept_block(self, block):
        self.app_log.info("Candidate submitted for index: {}".format(block.index))
        self.app_log.info("Transactions:")
        for x in block.transactions:
            self.app_log.info(x.transaction_signature)

        await self.config.consensus.insert_consensus_block(block, self.config.peer)

        self.config.processing_queues.block_queue.add(
            BlockProcessingQueueItem(Blockchain(block.to_dict()))
        )

        await self.config.nodeShared.send_block_to_peers(block)

        await self.config.websocketServer.send_block(block)

        await self.save_block_to_database(block)

        #await self.refresh()

    async def save_block_to_database(self, block):
        block_data = block.to_dict()
        block_data['found_time'] = int(time.time())
        block_data['status'] = "Pending"
        try:
            effort_data = await self.block_effort(block.index, block.target)
            block_data.update(effort_data)
            miner_address = await self.get_miner_address(block.hash)
            block_data['miner_address'] = miner_address
        except Exception as e:
            self.app_log.error(f"Error calculating effort: {e}")

        await self.config.mongo.async_db.pool_blocks.insert_one(block_data)

    async def get_miner_address(self, block_hash):
        share_data = await self.config.mongo.async_db.shares.find_one(
            {"hash": block_hash},
            {"_id": 0, "address": 1}
        )
        return share_data['address'] if share_data else None

    async def block_effort(self, block_index, block_target):
        latest_block = await self.config.mongo.async_db.pool_blocks.find(
            {},
            {"_id": 0, "index": 1},
        ).sort([("index", -1)]).limit(1).to_list(1)

        if latest_block:
            round_start = latest_block[0]['index'] + 1
        else:
            round_start = 0

        total_weight = await self.calculate_total_weight(round_start, block_index)

        self.config.app_log.debug(f"block_target: {block_target}")
        self.config.app_log.info(f"block_index: {block_index}")
        self.config.app_log.info(f"round_start: {round_start}")
        self.config.app_log.info(f"total_weight: {total_weight}")


        block_difficulty = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF / block_target
        total_block_hash = block_difficulty * 2**16
        block_effort = (total_weight * 100) / total_block_hash
        self.config.app_log.info(f"block_effort: {block_effort}")

        return {
            'effort': block_effort,
        }

    async def calculate_total_weight(self, round_start, round_end):
        if round_start == round_end:
            pipeline = [
                {"$match": {"index": round_start}},
                {"$group": {"_id": None, "total_weight": {"$sum": "$weight"}}}
            ]
        else:
            pipeline = [
                {"$match": {"index": {"$gte": round_start, "$lte": round_end}}},
                {"$group": {"_id": None, "total_weight": {"$sum": "$weight"}}}
            ]

        result = await self.config.mongo.async_db.shares.aggregate(pipeline).to_list(1)
        return result[0]["total_weight"] if result else 0



    async def update_block_status(self):
        pool_blocks_collection = self.config.mongo.async_db.pool_blocks
        latest_block_index = self.config.LatestBlock.block.index
        pending_blocks_list = await pool_blocks_collection.find({"status": {"$in": ["Pending", None]}}).to_list(None)
        
        for block in pending_blocks_list:
            confirmations = latest_block_index - block['index']
            
            if confirmations >= self.config.block_confirmation:
                matching_block = await self.config.mongo.async_db.blocks.find_one({"index": block['index']})
                
                if matching_block and matching_block['hash'] == block['hash']:
                    await pool_blocks_collection.update_one(
                        {"_id": block['_id']},
                        {"$set": {"status": "Accepted"}}
                    )
                else:
                    await pool_blocks_collection.update_one(
                        {"_id": block['_id']},
                        {"$set": {"status": "Orphan"}}
                    )

                self.app_log.info(f"Block with index {block['index']} updated to status: {block['status']}")
