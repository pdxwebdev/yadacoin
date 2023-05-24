from logging import getLogger

from yadacoin.core.chain import CHAIN
from yadacoin.core.config import get_config
from yadacoin.core.block import Block
from yadacoin.core.transaction import (
    Transaction,
    Input,
    Output,
    NotEnoughMoneyException,
)
from yadacoin.core.transactionutils import TU


class NonMatchingDifficultyException(Exception):
    pass


class PartialPayoutException(Exception):
    pass


class PoolPayer(object):
    def __init__(self):
        self.config = get_config()
        self.app_log = getLogger("tornado.application")

    async def do_payout(self, already_paid_height=None):
        # first check which blocks we won.
        # then determine if we have already paid out
        # they must be 6 blocks deep
        if not already_paid_height:
            already_paid_height = (
                await self.config.mongo.async_db.share_payout.find_one(
                    {}, sort=[("index", -1)]
                )
            )
            if not already_paid_height:
                already_paid_height = {}

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
            if (
                won_block.index + self.config.payout_frequency
            ) <= self.config.LatestBlock.block.index:
                if len(ready_blocks) >= self.config.payout_frequency:
                    if self.config.debug:
                        self.app_log.debug(
                            "entering payout at block: {}".format(won_block.index)
                        )
                    do_payout = True
                    break
                else:
                    if self.config.debug:
                        self.app_log.debug(
                            "block added for payout {}".format(won_block.index)
                        )
                    ready_blocks.append(won_block)

        if not do_payout:
            return

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
            total_pool_take = coinbase.outputs[0].value * pool_take
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
        await self.config.mongo.async_db.share_payout.insert_one(
            {"index": block.index, "txn": transaction.to_dict()}
        )
        await self.broadcast_transaction(transaction)

    async def get_share_list_for_height(self, index):
        raw_shares = []
        async for x in self.config.mongo.async_db.shares.find(
            {"index": index, "address": {"$ne": None}}
        ).sort([("index", 1)]):
            raw_shares.append(x)
        if not raw_shares:
            return False
        total_difficulty = self.get_difficulty([x for x in raw_shares])
        shares = {}
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

        add_up = 0
        for address, item in shares.items():
            test_difficulty = self.get_difficulty(item["blocks"])
            shares[address]["payout_share"] = float(test_difficulty) / float(
                total_difficulty
            )
            add_up += test_difficulty

        if add_up == total_difficulty:
            return shares
        else:
            raise NonMatchingDifficultyException()

    def get_difficulty(self, blocks):
        difficulty = 0
        for block in blocks:
            target = int(block["hash"], 16)
            difficulty += CHAIN.MAX_TARGET - target
        return difficulty

    async def already_used(self, txn):
        return await self.config.mongo.async_db.blocks.find_one(
            {"transactions.inputs.id": txn.transaction_signature}
        )

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
