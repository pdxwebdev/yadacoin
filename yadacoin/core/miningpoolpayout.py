"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from logging import getLogger
from time import time

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
    """Pool miner settlement.

    Payouts are **template-only**: settled inside a block the pool is mining.
    If the template loses, the payout never happened.  No mempool KEL
    rotation is created for payouts (that would race the mining U/C pair).
    """

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

    def pool_reward_value(self, coinbase):
        """Pool self-output value on a KEL coinbase (not masternode outs)."""
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

    async def already_used(self, txn, signer_public_key):
        """True if this coinbase is already spent by any same-KEL key."""
        if not signer_public_key or not txn:
            return False
        return await self.config.BU.is_input_spent(
            txn.transaction_signature, signer_public_key, inc_mempool=False
        )

    async def collect_settlement(self, signer_public_key, exclude_coinbase_ids=None):
        """Collect unpaid pool-won coinbases ready to settle in a template.

        Returns ``(coinbases, miner_outputs, settled_indexes)`` or
        ``([], {}, [])`` when nothing is ready.
        """
        exclude_coinbase_ids = set(exclude_coinbase_ids or [])
        inception_addr = self.pool_inception_address()
        if not inception_addr:
            return [], {}, []

        already_paid_height = await self.config.mongo.async_db.share_payout.find_one(
            {}, sort=[("index", -1)]
        )
        if not already_paid_height:
            already_paid_height = {}

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
        latest_index = self.config.LatestBlock.block.index
        async for won_block in won_blocks:
            won_block = await self.config.mongo.async_db.blocks.find_one(
                {
                    "index": won_block["index"],
                    "id": won_block["id"],
                    "hash": won_block["hash"],
                }
            )
            if not won_block:
                continue
            won_block = await Block.from_dict(won_block)
            coinbase = won_block.get_coinbase()
            if not self.is_pool_won_coinbase(coinbase):
                continue
            if coinbase.transaction_signature in exclude_coinbase_ids:
                continue
            if (won_block.index + self.config.payout_frequency) > latest_index:
                continue
            ready_blocks.append(won_block)
            if len(ready_blocks) >= self.config.payout_frequency:
                break

        if len(ready_blocks) < self.config.payout_frequency:
            return [], {}, []

        outputs = {}
        coinbases = []
        settled_indexes = []
        for block in ready_blocks:
            coinbase = block.get_coinbase()
            if await self.already_used(coinbase, signer_public_key):
                await self.config.mongo.async_db.shares.delete_many(
                    {"index": block.index}
                )
                continue
            existing = await self.config.mongo.async_db.share_payout.find_one(
                {"index": block.index}
            )
            if existing and existing.get("txn"):
                # Already recorded as paid (won template previously confirmed).
                continue
            try:
                shares = await self.get_share_list_for_height(block.index)
                if not shares:
                    continue
            except Exception as e:
                self.app_log.warning("collect_settlement shares: %s", e)
                continue

            reward_value = self.pool_reward_value(coinbase)
            if reward_value <= 0:
                continue
            pool_take = self.config.pool_take
            total_payout = reward_value - (reward_value * pool_take)
            coinbases.append(coinbase)
            settled_indexes.append(block.index)
            for address, x in shares.items():
                if address not in outputs:
                    outputs[address] = 0.0
                outputs[address] += total_payout * x["payout_share"]

        return coinbases, outputs, settled_indexes

    async def build_template_payout_pair(
        self, triplet, coinbase_txn, coinbases, miner_outputs, fee=0.0001
    ):
        """Build template-only KEL U/C that extends the coinbase confirming tip.

        Parent chain in the same block:
          on-chain tip → coinbase (U, Kn) → coinbase_confirming (C, Kn+1)
            → payout U (Kn+2) → payout C (Kn+3)

        No mempool insert.  Lives only if this block template wins.
        """
        from yadacoin.core.keyrotation import NodeKeyRotationManager
        from yadacoin.core.transaction import Input, Output

        if not triplet or not coinbase_txn:
            return None, None
        if not getattr(triplet, "kn2_private_key", None) or not triplet.kn3_address:
            self.app_log.warning(
                "build_template_payout_pair: triplet missing kn2/kn3 material"
            )
            return None, None
        if not coinbases or not miner_outputs:
            return None, None

        confirming_parent = getattr(triplet, "coinbase_confirming", None)
        if confirming_parent is None:
            return None, None

        # Payout unconfirmed signed by Kn+2 (addr = coinbase twice = confirming pre)
        signer_pub = triplet.kn2_public_key
        signer_priv = triplet.kn2_private_key
        signer_pkh = triplet.coinbase_twice_prerotated  # Kn+2 address
        prerotated = triplet.kn3_address  # Kn+3
        twice = triplet.kn4_address  # Kn+4
        prev_pkh = triplet.coinbase_prerotated  # Kn+1 = confirming public_key_hash

        my_address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(signer_pub)))
        if my_address != signer_pkh:
            self.app_log.warning(
                "build_template_payout_pair: kn2 address mismatch %s != %s",
                my_address,
                signer_pkh,
            )
            return None, None

        outputs_list = [Output(to=prerotated, value=0.0)]
        for address, value in miner_outputs.items():
            if value > 0:
                outputs_list.append(Output(to=address, value=float(value)))
        if len(outputs_list) < 2:
            return None, None

        # Spend prior unpaid coinbases + this template's coinbase reward out.
        input_ids = [cb.transaction_signature for cb in coinbases]
        if coinbase_txn.transaction_signature not in input_ids:
            input_ids.append(coinbase_txn.transaction_signature)
        inputs_list = [Input(signature=i) for i in input_ids]

        tip_counter = getattr(confirming_parent, "counter", None)
        payout_u_counter = (tip_counter + 1) if tip_counter is not None else None
        payout_c_counter = (tip_counter + 2) if tip_counter is not None else None
        inception = (
            getattr(triplet, "coinbase_inception_public_key_hash", None)
            or getattr(confirming_parent, "inception_public_key_hash", None)
            or None
        )

        unconfirmed = Transaction(
            txn_time=int(time()),
            version=7,
            public_key=signer_pub,
            inputs=inputs_list,
            outputs=outputs_list,
            fee=float(fee),
            masternode_fee=0.0,
            prerotated_key_hash=prerotated,
            twice_prerotated_key_hash=twice,
            public_key_hash=signer_pkh,
            prev_public_key_hash=prev_pkh,
            relationship="",
            relationship_hash="",
            rid="",
            dh_public_key="",
            counter=payout_u_counter,
            inception_public_key_hash=inception,
        )

        # Sum value: prior coinbases via is_same_kel; this block coinbase via
        # input_txn link (same-block spend).
        input_sum = 0.0
        evaluated = []
        miner_total = sum(float(v) for v in miner_outputs.values())
        needed = miner_total + float(fee)

        parents_by_id = {}
        for cb in coinbases:
            parents_by_id[cb.transaction_signature] = cb
        parents_by_id[coinbase_txn.transaction_signature] = coinbase_txn

        batch_for_auth = [coinbase_txn, confirming_parent, unconfirmed]
        for inp in list(unconfirmed.inputs):
            parent = parents_by_id.get(inp.id)
            if parent is None:
                parent = await self.config.BU.get_transaction_by_id(
                    inp.id, instance=True
                )
            if parent is None:
                continue
            if not hasattr(parent, "outputs"):
                parent = Transaction.from_dict(parent)
            inp.input_txn = parent
            input_sum = await unconfirmed.sum_inputs(
                inp,
                parent,
                my_address,
                input_sum,
                evaluated,
                needed,
                batch_txns=batch_for_auth,
            )

        # Also credit this block's coinbase prerotated out if sum_inputs missed
        # it (signer is Kn+2; coinbase pays Kn+1 prerotated — same KEL).
        if input_sum + 1e-12 < needed:
            # Force-credit pool reward outs on each parent via is_same_kel path
            # by ensuring kel auth works; if still short, abort settlement.
            raise NotEnoughMoneyException(
                f"template payout inputs {input_sum} < miner+fee {needed}"
            )

        unconfirmed.inputs = evaluated if evaluated else list(unconfirmed.inputs)
        change = input_sum - needed
        if change < 0:
            change = 0.0
        unconfirmed.outputs[0].value = float(change)

        unconfirmed.hash = await unconfirmed.generate_hash()
        unconfirmed.transaction_signature = NodeKeyRotationManager._sign(
            signer_priv, unconfirmed.hash
        )

        # Confirming sibling Kn+3 → Kn+4/Kn+5
        confirming = Transaction(
            txn_time=int(time()),
            version=7,
            public_key=triplet.kn3_public_key,
            inputs=[],
            outputs=[Output(to=triplet.kn4_address, value=0.0)],
            fee=0.0,
            masternode_fee=0.0,
            prerotated_key_hash=triplet.kn4_address,
            twice_prerotated_key_hash=triplet.kn5_address,
            public_key_hash=triplet.kn3_address,
            prev_public_key_hash=signer_pkh,
            relationship="",
            relationship_hash="",
            rid="",
            dh_public_key="",
            counter=payout_c_counter,
            inception_public_key_hash=inception,
        )
        confirming.hash = await confirming.generate_hash()
        confirming.transaction_signature = NodeKeyRotationManager._sign(
            triplet.kn3_private_key, confirming.hash
        )
        return unconfirmed, confirming

    async def attach_template_settlement(self, pending_txns, triplet, coinbase_txn):
        """If pool_payout is enabled, append template-only payout U/C to *pending_txns*.

        Returns metadata dict for the template (settled indexes) or None.
        """
        if not getattr(self.config, "pool_payout", False):
            return None
        if not triplet or not coinbase_txn:
            return None
        try:
            # Payout signer is Kn+2; spent-check can use kn2 or coinbase signer.
            signer_for_spent = (
                getattr(triplet, "kn2_public_key", None) or triplet.signer_public_key
            )
            coinbases, miner_outputs, settled_indexes = await self.collect_settlement(
                signer_for_spent,
                exclude_coinbase_ids={coinbase_txn.transaction_signature},
            )
            if not coinbases:
                return None
            unconfirmed, confirming = await self.build_template_payout_pair(
                triplet, coinbase_txn, coinbases, miner_outputs
            )
            if unconfirmed is None:
                return None
            # Same-block input links for coinbase → payout
            items = {t.transaction_signature: t for t in pending_txns}
            items[coinbase_txn.transaction_signature] = coinbase_txn
            items[unconfirmed.transaction_signature] = unconfirmed
            for inp in unconfirmed.inputs:
                if inp.id in items:
                    inp.input_txn = items[inp.id]
                    items[inp.id].spent_in_txn = unconfirmed
            pending_txns.append(unconfirmed)
            if confirming is not None:
                pending_txns.append(confirming)
            self.app_log.info(
                "template pool settlement attached: indexes=%s u=%s",
                settled_indexes,
                unconfirmed.transaction_signature[:16],
            )
            return {
                "settled_indexes": settled_indexes,
                "payout_txn_id": unconfirmed.transaction_signature,
                "confirming_txn_id": (
                    confirming.transaction_signature if confirming else None
                ),
            }
        except NotEnoughMoneyException as e:
            self.app_log.debug("template settlement skipped: %s", e)
            return None
        except Exception as e:
            self.app_log.warning("template settlement failed: %s", e)
            return None

    async def record_template_settlement(self, meta, block):
        """After a template wins, record share_payout rows for settled heights."""
        if not meta or not meta.get("settled_indexes"):
            return
        payout_id = meta.get("payout_txn_id")
        txn_doc = None
        if payout_id:
            for t in block.transactions:
                if t.transaction_signature == payout_id:
                    txn_doc = t.to_dict()
                    break
        for index in meta["settled_indexes"]:
            await self.config.mongo.async_db.share_payout.update_one(
                {"index": index},
                {
                    "$set": {
                        "index": index,
                        "txn": txn_doc,
                        "block_index": block.index,
                        "block_hash": block.hash,
                    }
                },
                upsert=True,
            )
            await self.config.mongo.async_db.shares.delete_many({"index": index})

    async def do_payout(self, already_paid_height=None):
        """Deprecated mempool path — payouts are template-only now."""
        self.app_log.info(
            "do_payout: mempool payout disabled; settlement is attached to "
            "mining templates when the pool wins a block"
        )
        return None

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
