"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from logging import getLogger

from bitcoin.wallet import P2PKHBitcoinAddress

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

    def pool_inception_address(self):
        """Stable pool identity: P2PKH of the KEL inception public key."""
        inception = getattr(self.config, "inception", None)
        if inception is not None and getattr(inception, "public_key", None):
            return str(
                P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(inception.public_key))
            )
        return None

    def payout_signer_keys(self):
        """KEL tip signing keys."""
        pub = getattr(self.config, "kel_anchor_public_key", None)
        priv = getattr(self.config, "kel_anchor_private_key", None)
        return pub, priv

    def pool_reward_value(self, coinbase):
        """Pool self-output value on a KEL coinbase (not masternode outs).

        KEL coinbases pay the miner share to ``prerotated_key_hash``.
        """
        if not coinbase or not coinbase.outputs:
            return 0.0
        prerotated = getattr(coinbase, "prerotated_key_hash", None) or ""
        if not prerotated:
            return 0.0
        return sum(float(o.value) for o in coinbase.outputs if str(o.to) == prerotated)

    def is_pool_won_coinbase(self, coinbase):
        """True when this coinbase is a KEL-tagged pool win with reward value."""
        if not coinbase:
            return False
        inception_addr = self.pool_inception_address()
        if not inception_addr:
            return False
        tagged = getattr(coinbase, "inception_public_key_hash", None) or ""
        if tagged != inception_addr:
            return False
        return self.pool_reward_value(coinbase) > 0

    async def do_payout(self, already_paid_height=None):
        # first check which blocks we won.
        # then determine if we have already paid out
        # they must be payout_frequency blocks deep
        if not already_paid_height:
            already_paid_height = (
                await self.config.mongo.async_db.share_payout.find_one(
                    {}, sort=[("index", -1)]
                )
            )
            if not already_paid_height:
                already_paid_height = {}

        inception_addr = self.pool_inception_address()
        if not inception_addr:
            self.app_log.warning("do_payout: no KEL inception — skipping")
            return

        # Every pool KEL coinbase is tagged with the stable inception address
        # (same query PoolInfoHandler uses).
        won_match = {
            "transactions": {
                "$elemMatch": {
                    "inputs.0": {"$exists": False},
                    "inception_public_key_hash": inception_addr,
                }
            },
            "index": {"$gt": already_paid_height.get("index", 0)},
        }
        unwind_match = {
            "transactions.inputs.0": {"$exists": False},
            "transactions.inception_public_key_hash": inception_addr,
            "$expr": {"$eq": ["$public_key", "$transactions.public_key"]},
        }

        won_blocks = self.config.mongo.async_db.blocks.aggregate(
            [
                {"$match": won_match},
                {"$unwind": "$transactions"},
                {"$match": unwind_match},
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
            if not self.is_pool_won_coinbase(coinbase):
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

        signer_pub, signer_priv = self.payout_signer_keys()
        if not signer_pub or not signer_priv:
            self.app_log.warning("do_payout: no signing key available")
            return

        # check if we already paid out
        outputs = {}
        coinbases = []
        last_block = None
        for block in ready_blocks:
            last_block = block
            if self.config.debug:
                self.app_log.debug(
                    "do_payout_for_blocks begin loop {}".format(block.index)
                )
            coinbase = block.get_coinbase()
            already_used = await self.already_used(coinbase)
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
                    {"inputs.id": coinbase.transaction_signature}
                )
                if pending:
                    return
                else:
                    # rebroadcast — but only if the inputs are not already confirmed-spent
                    transaction = Transaction.from_dict(existing["txn"])
                    input_ids = [i.id for i in transaction.inputs]
                    if input_ids and await self.config.BU.is_input_spent(
                        input_ids, signer_pub
                    ):
                        self.app_log.warning(
                            "share_payout for block {} references already-spent inputs, skipping rebroadcast".format(
                                block.index
                            )
                        )
                        await self.config.mongo.async_db.shares.delete_many(
                            {"index": block.index}
                        )
                        continue
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
            if not self.is_pool_won_coinbase(coinbase):
                return
            reward_value = self.pool_reward_value(coinbase)
            if reward_value <= 0:
                return
            if self.config.debug:
                self.app_log.debug(
                    "do_payout_for_blocks passed address compare {}".format(block.index)
                )
            pool_take = self.config.pool_take
            total_pool_take = reward_value * pool_take
            total_payout = reward_value - total_pool_take
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
            # Ordinary value transfer (no KEL rotation fields). Tip key spends
            # historical coinbase UTXOs via KEL cross-key authorization.
            transaction = await Transaction.generate(
                fee=0.0001,
                public_key=signer_pub,
                private_key=signer_priv,
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
            return

        try:
            await transaction.verify()
        except Exception as e:
            if self.config.debug:
                self.app_log.debug(e)
            raise
        self.app_log.debug("transaction verified")
        # Final guard: check that none of the coinbase inputs were spent in a
        # confirmed block during the time between already_used checks and now.
        # This closes the reorg race window where a payout transaction could be
        # confirmed and rolled back simultaneously with do_payout running.
        input_ids = [i.id for i in transaction.inputs]
        if input_ids and await self.config.BU.is_input_spent(input_ids, signer_pub):
            self.app_log.warning(
                "do_payout: inputs already spent in confirmed block at insert time, aborting payout"
            )
            return
        await self.config.mongo.async_db.miner_transactions.insert_one(
            transaction.to_dict()
        )
        payout_index = (
            last_block.index if last_block is not None else ready_blocks[-1].index
        )
        await self.config.mongo.async_db.share_payout.insert_one(
            {"index": payout_index, "txn": transaction.to_dict()}
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
        """True if this coinbase is already spent by any same-KEL key."""
        signer_pub, _ = self.payout_signer_keys()
        if not signer_pub:
            return False
        if await self.config.BU.is_input_spent(
            txn.transaction_signature, signer_pub, inc_mempool=True
        ):
            return True
        return False

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
