from logging import getLogger

from yadacoin.core.block import Block
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.transaction import NotEnoughMoneyException, Transaction


class NonMatchingDifficultyException(Exception):
    pass


class PartialPayoutException(Exception):
    pass


class PoolPayer(object):
    def __init__(self):
        self.config = Config()
        self.app_log = getLogger("tornado.application")

    async def do_payout(self, already_paid_height=None, start_index=None):
        # first check which blocks we won.
        # then determine if we have already paid out
        # they must be 6 blocks deep

        if not start_index:
            already_paid_height = (
                await self.config.mongo.async_db.share_payout.find_one(
                    {}, sort=[("index", -1)]
                )
            )
            if not already_paid_height:
                already_paid_height = {}
            else:
                already_paid_height = {"index": max(already_paid_height.get("index", 0))}
        else:
            already_paid_height = {"index": start_index}

        won_blocks = self.config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        "transactions": {
                            "$elemMatch": {
                                "inputs.0": {"$exists": False},
                            }
                        },
                        "transactions.outputs.to": self.config.address,
                        "index": {"$gt": already_paid_height.get("index", 0)},
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        "transactions.inputs.0": {"$exists": False},
                        "transactions.outputs.to": self.config.address,
                    }
                },
                {"$sort": {"index": 1}},
            ]
        )

        ready_blocks = []
        do_payout = False
        async for won_block in won_blocks:
            won_block = await self.config.mongo.async_db.blocks.find_one(
                {
                    "index": won_block["index"],
                    "id": won_block["id"],
                    "hash": won_block["hash"],
                }
            )
            won_block = await Block.from_dict(won_block)
            coinbase = won_block.get_coinbase()
            if coinbase.outputs[0].to != self.config.address:
                continue
            if self.config.debug:
                   self.app_log.debug(won_block.index)

            confirmations = self.config.LatestBlock.block.index - won_block.index
            if confirmations < self.config.block_confirmation: # We set the block maturation
                if self.config.debug:
                    self.app_log.debug("Payment stopped, block has insufficient confirmations.")
                continue
            if self.config.debug:
                self.app_log.debug(
                    "block added for payout {}".format(won_block.index)
                )
            ready_blocks.append(won_block)

        if ready_blocks:
            do_payout = True

        if not do_payout:
            if self.config.debug:
                self.app_log.debug("No payout is required.")
            return
        else:
            if self.config.debug:
                self.app_log.debug("Payout is required.") 

        # check if we already paid out
        outputs = {}
        coinbases = []
        for block in ready_blocks:
            if self.config.debug:
                self.app_log.debug(
                    "do_payout_for_blocks begin loop {}".format(block.index)
                )
            already_used = await self.already_used(block.get_coinbase())
            if already_used:
                await self.config.mongo.async_db.shares.delete_many(
                    {"index": block.index}
                )
                continue

            if self.config.debug:
                self.app_log.debug(
                    "do_payout_for_blocks passed already_used {}".format(block.index)
                )
            existing = await self.config.mongo.async_db.share_payout.find_one(
                {"index": block.index}
            )
            if existing:
                pending = await self.config.mongo.async_db.miner_transactions.find_one(
                    {"inputs.id": block.get_coinbase().transaction_signature}
                )
                if pending:
                    return
                else:
                    # rebroadcast
                    transaction = Transaction.from_dict(existing["txn"])
                    await self.config.mongo.async_db.miner_transactions.insert_one(
                        transaction.to_dict()
                    )
                    await self.broadcast_transaction(transaction)
                    return
            if self.config.debug:
                self.app_log.debug(
                    "do_payout_for_blocks passed existing {}".format(block.index)
                )
            try:
                shares = await self.get_share_list_for_height(block.index)
                if not shares:
                    continue
            except KeyError as e:
                self.app_log.warning(e)
                return
            except Exception as e:
                self.app_log.warning(e)
                return
            if self.config.debug:
                self.app_log.debug(
                    "do_payout_for_blocks passed get_share_list_for_height {}".format(
                        block.index
                    )
                )
            coinbase = block.get_coinbase()
            if coinbase.outputs[0].to != self.config.address:
                return
            if self.config.debug:
                self.app_log.debug(
                    "do_payout_for_blocks passed address compare {}".format(block.index)
                )
            pool_take = self.config.pool_take
            if pool_take == 0:
                total_payout = coinbase.outputs[0].value - 0.0001  # We charge a transaction fee only
            else:
                total_pool_take = coinbase.outputs[0].value * (pool_take)
                total_payout = coinbase.outputs[0].value - total_pool_take
            coinbases.append(coinbase)
            if self.config.debug:
                self.app_log.debug(
                    "do_payout_for_blocks coinbases so far {}".format(coinbases)
                )

            if self.config.debug:
                self.app_log.debug(
                    "do_payout_for_blocks passed coinbase calcs {}".format(block.index)
                )
            for address, x in shares.items():
                if self.config.debug:
                    self.app_log.debug(
                        "do_payout_for_blocks shares loop {}".format(block.index)
                    )
                exists = await self.config.mongo.async_db.share_payout.find_one(
                    {"index": block.index, "txn.outputs.to": address}
                )
                if exists:
                    raise PartialPayoutException(
                        "this index has been partially paid out."
                    )

                if self.config.debug:
                    self.app_log.debug(
                        "do_payout_for_blocks passed shares exists {}".format(
                            block.index
                        )
                    )
                if address not in outputs:
                    outputs[address] = 0.0
                payout = total_payout * x["payout_share"]
                outputs[address] += payout
                if self.config.debug:
                    self.app_log.debug(
                        "do_payout_for_blocks passed adding payout to outputs {}".format(
                            block.index
                        )
                    )

        if not outputs and ready_blocks:
            await self.config.mongo.async_db.share_payout.insert_one(
                {"index": ready_blocks[-1].index}
            )

        if not coinbases:
            return

        outputs_formatted = []
        for address, output in outputs.items():
            outputs_formatted.append({"to": address, "value": output})

        if self.config.debug:
            self.app_log.debug(
                "do_payout_for_blocks done formatting outputs {}".format(
                    [{"id": coinbase.transaction_signature} for coinbase in coinbases]
                )
            )
        try:
            transaction = await Transaction.generate(
                fee=0.0001,
                public_key=self.config.public_key,
                private_key=self.config.private_key,
                inputs=[
                    {"id": coinbase.transaction_signature} for coinbase in coinbases
                ],
                outputs=outputs_formatted,
            )
            self.app_log.debug(
                "transaction generated: {}".format(transaction.transaction_signature)
            )
        except NotEnoughMoneyException as e:
            if self.config.debug:
                self.app_log.debug("not enough money yet")
                self.app_log.debug(e)
            return
        except Exception as e:
            if self.config.debug:
                self.app_log.debug(e)

        try:
            await transaction.verify()
        except Exception as e:
            if self.config.debug:
                self.app_log.debug(e)
            raise
        self.app_log.debug("transaction verified")
        await self.config.mongo.async_db.miner_transactions.insert_one(
            transaction.to_dict()
        )
        block_indexes = [block.index for block in ready_blocks]
        await self.config.mongo.async_db.share_payout.insert_one(
            {"index": block_indexes, "txn": transaction.to_dict()}
        )
        await self.broadcast_transaction(transaction)

    async def get_share_list_for_height(self, index):
        if self.config.payout_scheme == "pplns":
            previous_block_index = index - 24
            self.config.app_log.info(f"PPLNS payment scheme used.")
        else:
            previous_block_index = await self.find_previous_block_index(index)
            self.config.app_log.info(f"PROP payment scheme used.")
        
        if previous_block_index is None:
            return {}

        raw_shares = []
        async for x in self.config.mongo.async_db.shares.find(
            {"index": {"$gte": previous_block_index, "$lte": index}, "address": {"$ne": None}}
        ).sort([("index", 1)]):
            raw_shares.append(x)
        if not raw_shares:
            return False

        shares = {}
        total_weight = 0

        for share in raw_shares:
            address = share["address"].split(".")[0]
            if not self.config.address_is_valid(address):
                await self.config.mongo.async_db.shares.delete_many(
                    {"address": address}
                )
                raise Exception(
                    "get_share_list_for_height invalid address: {}, removing related shares".format(
                        address
                    )
                )

            if address not in shares:
                shares[address] = {
                    "blocks": [],
                }
            shares[address]["blocks"].append(share)
            total_weight += share["weight"]
        self.config.app_log.info(f"Share range for payout: {previous_block_index} - {index}")
        self.config.app_log.info(f"Total weight for height {index}: {total_weight}")

        for address, item in shares.items():
            item["total_weight"] = sum(share["weight"] for share in item["blocks"])
            item["payout_share"] = float(item["total_weight"]) / float(total_weight)
            self.config.app_log.info(
                f"Miner {address} - Total weight: {item['total_weight']}, Payout share: {item['payout_share']}"
            )

        self.config.app_log.debug(f"get_share_list_for_height - Returning shares: {shares}")
        return shares

    async def find_previous_block_index(self, current_block_index):
        pool_public_key = (
            self.config.pool_public_key
            if hasattr(self.config, "pool_public_key")
            else self.config.public_key
        )

        pool_blocks_found_list = (
            await self.config.mongo.async_db.blocks.find(
                {"public_key": pool_public_key, "index": {"$lt": current_block_index}},
                {"_id": 0, "index": 1},
            )
            .sort([("index", -1)])
            .limit(1)
            .to_list(1)
        )

        if pool_blocks_found_list:
            previous_block_index = pool_blocks_found_list[0]["index"] + 1
            return previous_block_index
        else:
            self.config.app_log.info(
                f"No previous block found for current block {current_block_index}"
            )
            return None

    async def already_used(self, txn):
        results = self.config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        "transactions.inputs.id": txn.transaction_signature,
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        "transactions.inputs.id": txn.transaction_signature,
                        "transactions.public_key": self.config.public_key,
                    }
                },
            ]
        )
        return [x async for x in results]

    async def broadcast_transaction(self, transaction):
        self.app_log.debug(f"broadcast_transaction {transaction.transaction_signature}")
        async for peer_stream in self.config.peer.get_sync_peers():
            await self.config.nodeShared.write_params(
                peer_stream, "newtxn", {"transaction": transaction.to_dict()}
            )
            if peer_stream.peer.protocol_version > 1:
                self.config.nodeClient.retry_messages[
                    (peer_stream.peer.rid, "newtxn", transaction.transaction_signature)
                ] = {"transaction": transaction.to_dict()}
