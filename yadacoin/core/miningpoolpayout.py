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
        """True if this coinbase is already spent by any same-KEL key.

        Pass the pool inception tag so tip keys that are not yet resolvable
        on-chain still conflict with prior same-KEL spends of this coinbase.
        """
        if not signer_public_key or not txn:
            return False
        inception = (
            getattr(txn, "inception_public_key_hash", None)
            or self.pool_inception_address()
        )
        return await self.config.BU.is_input_spent(
            txn.transaction_signature,
            signer_public_key,
            inc_mempool=False,
            spender_inception=inception,
        )

    async def collect_settlement_batches(
        self, signer_public_key, exclude_coinbase_ids=None
    ):
        """Collect all unpaid ready coinbases, chunked by payout_frequency.

        Each batch is ``payout_frequency`` won blocks (one settlement U/C pair).
        When behind, returns multiple batches so one template can settle
        ``n * payout_frequency`` unpaid wins.

        Returns list of ``(coinbases, miner_outputs, settled_indexes)``.
        """
        exclude_coinbase_ids = set(exclude_coinbase_ids or [])
        inception_addr = self.pool_inception_address()
        if not inception_addr:
            return []

        freq = max(1, int(getattr(self.config, "payout_frequency", 6) or 6))
        max_batches = int(
            getattr(self.config, "max_payout_batches_per_block", 20) or 20
        )

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
        max_ready = freq * max_batches
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
            if (won_block.index + freq) > latest_index:
                continue
            ready_blocks.append(won_block)
            if len(ready_blocks) >= max_ready:
                break

        # Filter to payable entries first, then chunk into full *freq* batches.
        payable = []  # (block, coinbase, shares, reward_value)
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
                continue
            try:
                shares = await self.get_share_list_for_height(block.index)
                if not shares:
                    continue
            except Exception as e:
                self.app_log.warning("collect_settlement shares: %s", e)
                continue
            reward_value = self.pool_reward_value(coinbase)
            # is_pool_won_coinbase already requires reward_value > 0.
            payable.append((block, coinbase, shares, reward_value))

        n_batches = len(payable) // freq
        if n_batches <= 0:
            return []

        batches = []
        pool_take = self.config.pool_take
        for b in range(n_batches):
            chunk = payable[b * freq : (b + 1) * freq]
            outputs = {}
            coinbases = []
            settled_indexes = []
            for block, coinbase, shares, reward_value in chunk:
                total_payout = reward_value - (reward_value * pool_take)
                coinbases.append(coinbase)
                settled_indexes.append(block.index)
                for address, x in shares.items():
                    if address not in outputs:
                        outputs[address] = 0.0
                    outputs[address] += total_payout * x["payout_share"]
            batches.append((coinbases, outputs, settled_indexes))

        return batches

    async def collect_settlement(self, signer_public_key, exclude_coinbase_ids=None):
        """Back-compat: first settlement batch only."""
        batches = await self.collect_settlement_batches(
            signer_public_key, exclude_coinbase_ids=exclude_coinbase_ids
        )
        if not batches:
            return [], {}, []
        return batches[0]

    def _derive_key_material(self, priv_hex, cc_hex, second_factor):
        from yadacoin.core.keyrotation import _CoincurvePrivateKey, derive_secure_path

        nxt = derive_secure_path(
            bytes.fromhex(priv_hex), bytes.fromhex(cc_hex), second_factor
        )
        pub_bytes = _CoincurvePrivateKey(nxt["private_key"]).public_key.format(
            compressed=True
        )
        addr = str(P2PKHBitcoinAddress.from_pubkey(pub_bytes))
        return {
            "private_key": nxt["private_key"].hex(),
            "chain_code": nxt["chain_code"].hex(),
            "public_key": pub_bytes.hex(),
            "address": addr,
        }

    async def build_template_payout_pair(
        self,
        coinbase_txn,
        coinbases,
        miner_outputs,
        *,
        signer_pub,
        signer_priv,
        signer_pkh,
        prerotated,
        twice,
        prev_pkh,
        confirming_pub,
        confirming_priv,
        confirming_pkh,
        confirming_pre,
        confirming_twice,
        tip_counter,
        inception,
        batch_txns_for_auth,
        fee=0.0001,
        spend_template_coinbase=False,
        txn_time=None,
    ):
        """Build one template-only KEL U/C payout pair at a derived tip."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager
        from yadacoin.core.transaction import Input, Output

        if not coinbases or not miner_outputs:
            return None, None

        my_address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(signer_pub)))
        if my_address != signer_pkh:
            self.app_log.warning(
                "build_template_payout_pair: signer address mismatch %s != %s",
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

        input_ids = [cb.transaction_signature for cb in coinbases]
        if spend_template_coinbase and coinbase_txn is not None:
            if coinbase_txn.transaction_signature not in input_ids:
                input_ids.append(coinbase_txn.transaction_signature)
        inputs_list = [Input(signature=i) for i in input_ids]

        payout_u_counter = (tip_counter + 1) if tip_counter is not None else None
        payout_c_counter = (tip_counter + 2) if tip_counter is not None else None
        # Must not exceed block.time + TIME_TOLERANCE (settlement can take >10s).
        if txn_time is None:
            txn_time = int(time())
        else:
            txn_time = int(txn_time)

        unconfirmed = Transaction(
            txn_time=txn_time,
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

        # Value credit: these inputs are already filtered as pool-won KEL
        # coinbases (or this template's coinbase).  Do not rely on
        # sum_inputs/is_same_kel for the unused tip key (not on-chain yet).
        miner_total = sum(float(v) for v in miner_outputs.values())
        needed = miner_total + float(fee)

        parents_by_id = {cb.transaction_signature: cb for cb in coinbases}
        if coinbase_txn is not None:
            parents_by_id[coinbase_txn.transaction_signature] = coinbase_txn

        input_sum = 0.0
        evaluated = []
        for inp in list(unconfirmed.inputs):
            parent = parents_by_id.get(inp.id)
            if parent is None:
                parent = await self.config.BU.get_transaction_by_id(
                    inp.id, instance=True
                )
            if parent is None:
                self.app_log.warning(
                    "build_template_payout_pair: missing parent for input %s",
                    getattr(inp, "id", "?")[:16],
                )
                continue
            if not hasattr(parent, "outputs"):
                parent = Transaction.from_dict(parent)
            inp.input_txn = parent

            if parent is coinbase_txn or (
                coinbase_txn is not None
                and getattr(parent, "transaction_signature", None)
                == coinbase_txn.transaction_signature
            ):
                # This template's coinbase: credit outs to its prerotated.
                credited = float(self.pool_reward_value(parent))
            else:
                credited = float(self.pool_reward_value(parent))
                if credited <= 0:
                    # Fallback: sum positive outs (legacy-shaped coinbase).
                    credited = sum(
                        float(o.value)
                        for o in (parent.outputs or [])
                        if float(getattr(o, "value", 0) or 0) > 0
                    )

            if credited <= 0:
                self.app_log.warning(
                    "build_template_payout_pair: zero credit for input %s "
                    "pre=%s outs=%s",
                    getattr(inp, "id", "?")[:16],
                    getattr(parent, "prerotated_key_hash", None),
                    [(str(o.to), o.value) for o in (parent.outputs or [])],
                )
                continue

            input_sum += credited
            evaluated.append(inp)

        if input_sum + 1e-12 < needed:
            raise NotEnoughMoneyException(
                f"template payout inputs {input_sum} < miner+fee {needed} "
                f"(coinbases={len(coinbases)} evaluated={len(evaluated)} "
                f"signer={my_address})"
            )

        unconfirmed.inputs = evaluated if evaluated else list(unconfirmed.inputs)
        # input_sum >= needed is guaranteed by the NotEnoughMoneyException guard.
        unconfirmed.outputs[0].value = float(input_sum - needed)

        unconfirmed.hash = await unconfirmed.generate_hash()
        unconfirmed.transaction_signature = NodeKeyRotationManager._sign(
            signer_priv, unconfirmed.hash
        )
        unconfirmed.template_kel = True

        confirming = Transaction(
            txn_time=txn_time,
            version=7,
            public_key=confirming_pub,
            inputs=[],
            outputs=[Output(to=confirming_pre, value=0.0)],
            fee=0.0,
            masternode_fee=0.0,
            prerotated_key_hash=confirming_pre,
            twice_prerotated_key_hash=confirming_twice,
            public_key_hash=confirming_pkh,
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
            confirming_priv, confirming.hash
        )
        confirming.template_kel = True
        return unconfirmed, confirming

    async def _bump_coinbase_for_settlement_fees(
        self, coinbase_txn, triplet, batch_count, fee=0.0001
    ):
        """Add settlement payout fees to the template coinbase miner output.

        ``Block.pay_masternodes`` runs before template settlement is attached, so
        those fees are not in the original coinbase.  Mutates and re-signs
        ``coinbase_txn`` in place so later spends (first batch) see the correct
        ``pool_reward_value``.
        """
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        signer_priv = getattr(triplet, "signer_private_key", None) if triplet else None
        if (
            not coinbase_txn
            or not isinstance(signer_priv, str)
            or not signer_priv
            or batch_count <= 0
        ):
            return coinbase_txn
        total_fee = float(batch_count) * float(fee)
        if total_fee <= 0:
            return coinbase_txn
        prerotated = getattr(coinbase_txn, "prerotated_key_hash", None) or ""
        target = None
        for output in coinbase_txn.outputs or []:
            if prerotated and str(output.to) == prerotated:
                target = output
                break
        if target is None and coinbase_txn.outputs:
            target = coinbase_txn.outputs[-1]
        if target is None:
            return coinbase_txn
        try:
            target.value = float(target.value) + total_fee
            coinbase_txn.hash = await coinbase_txn.generate_hash()
            coinbase_txn.transaction_signature = NodeKeyRotationManager._sign(
                signer_priv, coinbase_txn.hash
            )
        except Exception as exc:
            self.app_log.warning("_bump_coinbase_for_settlement_fees failed: %s", exc)
            # Best-effort undo so a partial bump never leaves inconsistent value.
            try:
                target.value = float(target.value) - total_fee
            except Exception:
                pass
        return coinbase_txn

    async def attach_template_settlement(
        self, pending_txns, triplet, coinbase_txn, block_time=None
    ):
        """Attach one or more template-only payout U/C pairs (catch-up batches).

        Each batch settles ``payout_frequency`` unpaid won blocks.  Multiple
        batches chain in the same block:

          coinbase U/C → payout0 U/C → payout1 U/C → …

        Returns metadata with all settled indexes and payout txn ids, or None.
        """
        if not getattr(self.config, "pool_payout", False):
            return None
        if not triplet or not coinbase_txn:
            return None

        from yadacoin.core.keyrotation import _read_second_factor

        try:
            signer_for_spent = (
                getattr(triplet, "kn2_public_key", None) or triplet.signer_public_key
            )
            batches = await self.collect_settlement_batches(
                signer_for_spent,
                exclude_coinbase_ids={coinbase_txn.transaction_signature},
            )
            if not batches:
                return None

            second_factor = _read_second_factor()
            if not second_factor:
                self.app_log.warning(
                    "attach_template_settlement: SECOND_FACTOR missing"
                )
                return None
            if not getattr(triplet, "kn2_private_key", None) or not getattr(
                triplet, "kn2_chain_code", None
            ):
                self.app_log.warning(
                    "attach_template_settlement: triplet missing kn2 material"
                )
                return None

            confirming_parent = getattr(triplet, "coinbase_confirming", None)
            if confirming_parent is None:
                return None

            # Coinbase is built before settlement. Each payout U carries a fee
            # (default 0.0001) that verify() folds into fee_sum, so the miner
            # self-output must include those fees or TotalValueMismatchException
            # fires (fees > coinbase_sum - reward). Bump and re-sign in place
            # before building spends so pool_reward_value credits the full amount.
            # Only after preflight so a failed attach never leaves an inflated coinbase.
            settlement_fee = 0.0001
            await self._bump_coinbase_for_settlement_fees(
                coinbase_txn, triplet, len(batches), fee=settlement_fee
            )

            inception = (
                getattr(triplet, "coinbase_inception_public_key_hash", None)
                or getattr(confirming_parent, "inception_public_key_hash", None)
                or getattr(coinbase_txn, "inception_public_key_hash", None)
                or None
            )
            # Ensure template KEL parents carry the inception tag for tip-auth.
            if inception:
                if not getattr(coinbase_txn, "inception_public_key_hash", None):
                    coinbase_txn.inception_public_key_hash = inception
                if not getattr(confirming_parent, "inception_public_key_hash", None):
                    confirming_parent.inception_public_key_hash = inception

            cur_signer = {
                "private_key": triplet.kn2_private_key,
                "chain_code": triplet.kn2_chain_code,
                "public_key": triplet.kn2_public_key,
                "address": triplet.kn2_address or triplet.coinbase_twice_prerotated,
            }
            prev_pkh = triplet.coinbase_prerotated  # Kn+1
            tip_counter = getattr(confirming_parent, "counter", None)
            batch_auth = [coinbase_txn, confirming_parent]

            all_indexes = []
            payout_ids = []
            confirming_ids = []

            for batch_i, (coinbases, miner_outputs, settled_indexes) in enumerate(
                batches
            ):
                kn_c = self._derive_key_material(
                    cur_signer["private_key"], cur_signer["chain_code"], second_factor
                )
                kn_c_pre = self._derive_key_material(
                    kn_c["private_key"], kn_c["chain_code"], second_factor
                )
                kn_c_twice = self._derive_key_material(
                    kn_c_pre["private_key"], kn_c_pre["chain_code"], second_factor
                )

                unconfirmed, confirming = await self.build_template_payout_pair(
                    coinbase_txn,
                    coinbases,
                    miner_outputs,
                    signer_pub=cur_signer["public_key"],
                    signer_priv=cur_signer["private_key"],
                    signer_pkh=cur_signer["address"],
                    prerotated=kn_c["address"],
                    twice=kn_c_pre["address"],
                    prev_pkh=prev_pkh,
                    confirming_pub=kn_c["public_key"],
                    confirming_priv=kn_c["private_key"],
                    confirming_pkh=kn_c["address"],
                    confirming_pre=kn_c_pre["address"],
                    confirming_twice=kn_c_twice["address"],
                    tip_counter=tip_counter,
                    inception=inception,
                    batch_txns_for_auth=batch_auth,
                    spend_template_coinbase=(batch_i == 0),
                    txn_time=block_time,
                )
                if unconfirmed is None:
                    break

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

                all_indexes.extend(settled_indexes)
                payout_ids.append(unconfirmed.transaction_signature)
                if confirming is not None:
                    confirming_ids.append(confirming.transaction_signature)

                batch_auth.extend(
                    [x for x in (unconfirmed, confirming) if x is not None]
                )
                prev_pkh = kn_c["address"]
                tip_counter = getattr(confirming, "counter", None)
                cur_signer = kn_c_pre

            if not payout_ids:
                return None

            self.app_log.info(
                "template pool settlement attached: batches=%d indexes=%s",
                len(payout_ids),
                all_indexes,
            )
            return {
                "settled_indexes": all_indexes,
                "payout_txn_ids": payout_ids,
                "confirming_txn_ids": confirming_ids,
                "payout_txn_id": payout_ids[0],
                "confirming_txn_id": confirming_ids[0] if confirming_ids else None,
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
        payout_ids = list(meta.get("payout_txn_ids") or [])
        if meta.get("payout_txn_id") and meta["payout_txn_id"] not in payout_ids:
            payout_ids.insert(0, meta["payout_txn_id"])
        txn_docs = {}
        for t in block.transactions:
            if t.transaction_signature in payout_ids:
                txn_docs[t.transaction_signature] = t.to_dict()
        primary = None
        for pid in payout_ids:
            if pid in txn_docs:
                primary = txn_docs[pid]
                break
        for index in meta["settled_indexes"]:
            await self.config.mongo.async_db.share_payout.update_one(
                {"index": index},
                {
                    "$set": {
                        "index": index,
                        "txn": primary,
                        "payout_txn_ids": payout_ids,
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
