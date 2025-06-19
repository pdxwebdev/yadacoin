"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import json
import random
import uuid
from datetime import datetime
from logging import getLogger
from time import time

from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.job import Job
from yadacoin.core.miner import Miner
from yadacoin.core.peer import Peer
from yadacoin.core.processingqueue import BlockProcessingQueueItem
from yadacoin.core.transaction import Transaction
from yadacoin.core.transactionutils import TU
from yadacoin.tcpsocket.pool import StratumServer


class MiningPool(object):
    @classmethod
    async def init_async(cls):
        self = cls()
        self.config = Config()
        self.mongo = self.config.mongo
        self.app_log = getLogger("tornado.application")
        self.target_block_time = CHAIN.target_block_time(self.config.network)
        self.max_target = CHAIN.MAX_TARGET
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
        item = self.config.processing_queues.nonce_queue.pop()
        i = 0  # max loops
        while item:
            self.config.processing_queues.nonce_queue.inc_num_items_processed()
            body = item.body
            stream = item.stream
            miner = item.miner
            nonce = body["params"].get("nonce")
            job = stream.jobs[body["params"]["id"] or body["params"]["job_id"]]
            if type(nonce) is not str:
                result = {"error": True, "message": "nonce is wrong data type"}
            if len(nonce) > CHAIN.MAX_NONCE_LEN:
                result = {"error": True, "message": "nonce is too long"}
            data = {
                "id": body.get("id"),
                "method": body.get("method"),
                "jsonrpc": body.get("jsonrpc"),
            }
            data["result"] = await self.process_nonce(miner, nonce, job, body)
            if not data["result"]:
                data["error"] = {"message": "Invalid hash for current block"}
            try:
                await stream.write("{}\n".format(json.dumps(data)).encode())
            except:
                pass
            if "error" in data:
                await StratumServer.send_job(stream)

            await StratumServer.block_checker()

            i += 1
            if i >= 1000:
                self.config.app_log.info(
                    "process_nonce_queue: max loops exceeded, exiting"
                )
                return

            item = self.config.processing_queues.nonce_queue.pop()

    async def process_nonce(self, miner, nonce, job, body):
        nonce = nonce + job.extra_nonce
        header = self.block_factory.header
        self.config.app_log.debug(f"Extra Nonce for job {job.index}: {job.extra_nonce}")
        self.config.app_log.debug(f"Nonce for job {job.index}: {nonce}")

        hash1 = self.block_factory.generate_hash_from_header(job.index, header, nonce)
        #self.config.app_log.info(f"Hash1 for job {job.index}: {hash1}")

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

        target = int(
            "0x"
            + (
                f"0000000000000000000000000000000000000000000000000000000000000000"
                + f"{hex(0x10000000000000001 // self.config.pool_diff)[2:64]}FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"[
                    :64
                ]
            )[-64:],
            16,
        )

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
                        "time": int(time()),
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
            if self.refreshing or not await Peer.is_synced():
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
        res = {
            "target": hex(int(self.block_factory.target))[2:].rjust(
                64, "0"
            ),  # target is now in hex format
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

    async def block_template(self, agent, peer_id):
        """Returns info for current block to mine"""
        if self.block_factory is None:
            await self.refresh()
        if not self.block_factory.target:
            await self.set_target_from_last_non_special_min(
                self.config.LatestBlock.block
            )

        job = await self.generate_job(agent, peer_id)
        return job

    async def generate_job(self, agent, peer_id):
        difficulty = int(self.max_target / (self.block_factory.target or 1))
        custom_diff = None
        miner_diff = (
            max(int(custom_diff), 50000)
            if custom_diff is not None
            else self.config.pool_diff
        )
        seed_hash = "4181a493b397a733b083639334bc32b407915b9a82b7917ac361816f0a1f5d4d"  # sha256(yadacoin65000)
        job_id = str(uuid.uuid4())
        extra_nonce = str(random.randrange(100001, 999999))
        header = self.block_factory.header
        blob = header.encode().hex().replace("7b6e6f6e63657d", "00000000" + extra_nonce)

        lower_agent = agent.lower()

        if (
            "xmrigcc/3" in lower_agent
            or "xmrigcc-proxy/3" in lower_agent
            or "xmrig/3" in lower_agent
            or "xmrig/6" in lower_agent
            or "xmrig-proxy/6" in lower_agent
        ):
            target = hex(0x10000000000000001 // miner_diff)
        elif miner_diff <= 69905:
            target = hex(0x10000000000000001 // miner_diff - 0x0000F00000000000)[
                2:
            ].zfill(48)
        else:
            target = "-" + hex(0x10000000000000001 // miner_diff - 0x0000F00000000000)[
                3:
            ].zfill(48)

        res = {
            "job_id": job_id,
            "peer_id": peer_id,
            "difficulty": difficulty,
            "target": target,  # can only be 16 characters long
            "blob": blob,
            "seed_hash": seed_hash,
            "height": self.config.LatestBlock.block.index
            + 1,  # This is the height of the one we are mining
            "extra_nonce": extra_nonce,
            "miner_diff": miner_diff,
            "algo": "rx/yada",
        }
        return await Job.from_dict(res)

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

        check_max_inputs = False
        if self.config.LatestBlock.block.index + 1 > CHAIN.CHECK_MAX_INPUTS_FORK:
            check_max_inputs = True

        check_masternode_fee = False
        if self.config.LatestBlock.block.index + 1 >= CHAIN.CHECK_MASTERNODE_FEE_FORK:
            check_masternode_fee = True

        check_kel = False
        if self.config.LatestBlock.block.index + 1 >= CHAIN.CHECK_KEL_FORK:
            check_kel = True

        async for txn in self.mongo.async_db.miner_transactions.find(
            {"relationship.smart_contract": {"$exists": True}}
        ).sort([("fee", -1), ("time", 1)]):
            transaction_obj = await self.verify_pending_transaction(
                txn,
                used_sigs,
                check_max_inputs=check_max_inputs,
                check_masternode_fee=check_masternode_fee,
                check_kel=check_kel,
            )
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

        transactions = [
            txn
            async for txn in self.mongo.async_db.miner_transactions.find(
                {"relationship.smart_contract": {"$exists": False}}
            ).sort([("fee", -1), ("time", 1)])
        ]
        transactions = [Transaction.from_dict(txn) for txn in transactions]
        if (
            self.config.LatestBlock.block.index + 1
            >= CHAIN.ALLOW_SAME_BLOCK_SPENDING_FORK
        ):
            items_indexed = {x.transaction_signature: x for x in transactions}
            for txn in transactions:
                for input_item in txn.inputs:
                    if input_item.id in items_indexed:
                        input_item.input_txn = items_indexed[input_item.id]
                        items_indexed[input_item.id].spent_in_txn = txn
        for txn in transactions[:]:
            if txn not in transactions:
                continue
            transaction_obj = await self.verify_pending_transaction(
                txn,
                used_sigs,
                transactions=transactions,
                check_max_inputs=check_max_inputs,
                check_masternode_fee=check_masternode_fee,
                check_kel=check_kel,
            )
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

    async def verify_pending_transaction(
        self,
        txn,
        used_sigs,
        transactions=None,
        check_max_inputs=False,
        check_masternode_fee=False,
        check_kel=False,
    ):
        if transactions is None:
            transactions = []
        try:
            if isinstance(txn, Transaction):
                transaction_obj = txn
            elif isinstance(txn, dict):
                transaction_obj = Transaction.from_dict(txn)
            else:
                raise Exception()
        except:
            self.config.app_log.warning("transaction unrecognizable, skipping")
            return
        try:
            if (
                self.config.LatestBlock.block.index + 1 >= CHAIN.TXN_V3_FORK
                and transaction_obj.version < 3
            ):
                self.config.app_log.warning("transaction version too old, skipping")
                return

            await transaction_obj.verify(
                check_max_inputs=check_max_inputs,
                check_masternode_fee=check_masternode_fee,
                check_kel=check_kel,
            )

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
            await Transaction.handle_exception(e, transaction_obj, transactions)

    async def accept_block(self, block):
        self.app_log.info("Candidate submitted for index: {}".format(block.index))
        self.app_log.info("Transactions:")
        for x in block.transactions:
            self.app_log.info(x.transaction_signature)

        await self.config.consensus.insert_consensus_block(block, self.config.peer)

        self.config.processing_queues.block_queue.add(
            BlockProcessingQueueItem(Blockchain(block.to_dict()))
        )

        if self.config.network != "regnet":
            await self.config.nodeShared.send_block_to_peers(block)

            await self.config.websocketServer.send_block(block)

        await self.refresh()

    async def update_pool_stats(self):
        expected_blocks = 144
        mining_time_interval = 1200
        pool_max_target = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF

        pipeline = [
            {
                "$match": {
                    "time": {"$gte": time() - mining_time_interval}
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
        pool_hash_rate = result[0]["total_weight"] / mining_time_interval if result else 0

        daily_blocks_found = await self.config.mongo.async_db.blocks.count_documents(
            {"time": {"$gte": time() - (600 * 144)}}
        )
        avg_block_time = daily_blocks_found / expected_blocks * 600

        if daily_blocks_found > 0:
            net_target = self.config.LatestBlock.block.target
        avg_blocks_found = self.config.mongo.async_db.blocks.find(
            {"time": {"$gte": time() - (600 * 36)}},
            projection={"_id": 0, "target": 1}
        )

        avg_block_targets = [block["target"] async for block in avg_blocks_found]
        if avg_block_targets:
            avg_net_target = sum(int(target, 16) for target in avg_block_targets) / len(avg_block_targets)
            avg_net_difficulty = (
                pool_max_target
                / avg_net_target
            )
            net_difficulty = (
                pool_max_target
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
                pool_max_target
                / pool_max_target
            )
            network_hash_rate = 0

        worker_count = len(StratumServer.inbound_streams[Miner.__name__].keys())
        miner_count = len(await Peer.get_miner_streams())

        timestamp = int(time())
        date_value = datetime.utcfromtimestamp(timestamp)

        await self.config.mongo.async_pool_db.pool_hashrate_stats.insert_one({
            "pool_hash_rate": pool_hash_rate,
            "network_hash_rate": network_hash_rate,
            "net_difficulty": net_difficulty,
            "avg_network_hash_rate": avg_network_hash_rate,
            "workers": worker_count,
            "miners": miner_count,
            "time": timestamp,
            "date": date_value,
        })

