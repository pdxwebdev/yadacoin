"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64
import binascii
import hashlib
import json
import time
from decimal import Decimal, getcontext
from logging import getLogger

from bitcoin.signmessage import BitcoinMessage, VerifyMessage
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve.utils import verify_signature

import pyrx
import yadacoin.core.config
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.keyeventlog import (
    DoesNotSpendEntirelyToPrerotatedKeyHashException,
    KELExceptionPreviousKeyHashReferenceMissing,
    KELHashCollection,
    KeyEvent,
    KeyEventChainStatus,
    KeyEventFieldsNotPopulatedException,
    KeyEventLog,
)
from yadacoin.core.keyrotation import NodeKeyRotationManager
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.nodestester import NodesTester
from yadacoin.core.recoveryannouncement import RecoveryProof, RecoveryTransition
from yadacoin.core.transaction import (
    InvalidTransactionException,
    Output,
    TotalValueMismatchException,
    Transaction,
    TransactionAddressInvalidException,
)


class XeggexAccountFrozenException(Exception):
    pass


def quantize_eight(value):
    getcontext().prec = len(str(value)) + 8
    if value == -0.0:
        value = 0.0
    value = Decimal(value)
    value = value.quantize(Decimal("0.00000000"))
    return value


class CoinbaseRule1(Exception):
    pass


class CoinbaseRule2(Exception):
    pass


class CoinbaseRule3(Exception):
    pass


class CoinbaseRule4(Exception):
    pass


class RelationshipRule1(Exception):
    pass


class RelationshipRule2(Exception):
    pass


class FastGraphRule1(Exception):
    pass


class FastGraphRule2(Exception):
    pass


class Block(object):
    # Memory optimization
    __slots__ = (
        "app_log",
        "config",
        "mongo",
        "version",
        "time",
        "index",
        "prev_hash",
        "nonce",
        "transactions",
        "txn_hashes",
        "merkle_root",
        "verify_merkle_root",
        "hash",
        "public_key",
        "signature",
        "special_min",
        "target",
        "special_target",
        "header",
        "private_key",
        "pool_settlement_meta",
    )

    @classmethod
    async def init_async(
        cls,
        version=1,
        block_time=0,
        block_index=-1,
        prev_hash="",
        nonce: str = "",
        transactions=None,
        block_hash="",
        merkle_root="",
        public_key="",
        signature="",
        special_min: bool = False,
        header="",
        target: int = 0,
        special_target: int = 0,
    ):
        self = cls()
        self.config = Config()
        self.app_log = getLogger("tornado.application")
        self.version = version
        self.time = int(block_time)
        self.index = block_index
        self.prev_hash = prev_hash
        self.nonce = nonce
        # txn_hashes = self.get_transaction_hashes()
        # self.set_merkle_root(txn_hashes)
        self.merkle_root = merkle_root
        self.verify_merkle_root = ""
        self.hash = block_hash
        self.public_key = public_key
        self.signature = signature
        self.special_min = special_min
        self.target = target
        self.special_target = special_target
        if target == 0:
            # Same call as in new block check - but there's a circular reference here.
            latest_block = LatestBlock.block
            if not latest_block:
                self.target = CHAIN.MAX_TARGET
            else:
                if self.index >= CHAIN.FORK_10_MIN_BLOCK:
                    self.target = await CHAIN.get_target_10min(latest_block, self)
                else:
                    self.target = await CHAIN.get_target(self.index, latest_block, self)
            self.special_target = self.target
            # TODO: do we need recalc special target here if special min?
        self.header = header
        self.private_key = None
        self.pool_settlement_meta = None

        self.transactions = []
        for txn in transactions or []:
            transaction = Transaction.ensure_instance(txn)
            transaction.coinbase = Block.is_coinbase(self, transaction)
            self.transactions.append(transaction)

        return self

    async def copy(self):
        return await Block.from_json(self.to_json())

    @staticmethod
    async def _maybe_attach_pool_settlement(
        block, config, pending_txns, triplet, coinbase_txn
    ):
        """Attach template pool settlement if enabled; never fail block build."""
        block.pool_settlement_meta = None
        if not (
            getattr(config, "pool_payout", False)
            and getattr(config, "pp", None) is not None
            and coinbase_txn is not None
            and triplet is not None
        ):
            return
        try:
            block.pool_settlement_meta = await config.pp.attach_template_settlement(
                pending_txns, triplet, coinbase_txn, block_time=block.time
            )
        except Exception as exc:
            config.app_log.warning(
                "Block.generate: template pool settlement skipped: %s", exc
            )

    @classmethod
    async def generate(
        cls,
        transactions=None,
        force_version=None,
        index=0,
        force_time=None,
        prev_hash=None,
        nonce=None,
        target=0,
    ):
        config = Config()
        if force_version is None:
            version = CHAIN.get_version_for_height(index)
        else:
            version = force_version
        if force_time:
            xtime = int(force_time)
        else:
            xtime = int(time.time())
        index = int(index)
        if index == 0:
            prev_hash = ""
        elif prev_hash is None and index != 0:
            prev_hash = LatestBlock.block.hash

        transaction_objs = []
        used_sigs = []
        used_inputs = {}
        pending_txns = []

        block_reward = CHAIN.get_block_reward(index)

        block = await cls.init_async(
            version=version,
            block_time=xtime,
            block_index=index,
            prev_hash=prev_hash,
            target=target,
        )

        await block.check_xeggex_hack()
        if nonce:
            block.nonce = str(nonce)

        triplet = await config.kel_manager.advance_block_ratchet(block=block)

        # Template-only coinbase confirming KEL step (no preceding block-reanchor
        # U/C pair). Parent must be the on-chain KEL tip (see advance_block_ratchet).
        if (
            triplet is not None
            and getattr(triplet, "coinbase_confirming", None) is not None
        ):
            pending_txns.append(triplet.coinbase_confirming)

        if transactions is not None:
            transactions = [Transaction.from_dict(txn) for txn in transactions]
        else:
            transactions = [
                txn
                async for txn in config.mongo.async_db.miner_transactions.find(
                    {"relationship.smart_contract": {"$exists": False}}
                )
                .sort([("fee", -1), ("time", 1)])
                .limit(1000)
            ]
            transactions = [Transaction.from_dict(txn) for txn in transactions]
        pending_txns.extend(transactions)

        coinbase_txn = await block.pay_masternodes(
            pending_txns,
            triplet,
            block_reward,
        )
        if coinbase_txn is not None:
            pending_txns.append(coinbase_txn)

        # Pool settlement is template-only: same-block KEL extension after the
        # coinbase U/C pair.  If this template loses, payout never happened.
        await Block._maybe_attach_pool_settlement(
            block, config, pending_txns, triplet, coinbase_txn
        )

        if config.LatestBlock.block.index + 1 >= CHAIN.ALLOW_SAME_BLOCK_SPENDING_FORK:
            items_indexed = {x.transaction_signature: x for x in pending_txns}
            for txn in pending_txns:
                for input_item in txn.inputs:
                    if input_item.id in items_indexed:
                        input_item.input_txn = items_indexed[input_item.id]
                        items_indexed[input_item.id].spent_in_txn = txn

        if config.log_level == "DEBUG":
            for txn in pending_txns:
                config.app_log.debug(f"Pending txn: {txn.to_json()}")

        # Build complete KEL chains from on-chain roots only; drop incomplete
        # members from the candidate set and the mempool before per-txn verify.
        if index >= CHAIN.CHECK_KEL_FORK:
            await Block.select_kel_chains_for_block(
                pending_txns,
                block_index=index,
                max_transactions=1000,
            )

        await Block.validate_transactions(
            block, pending_txns, transaction_objs, used_sigs, used_inputs, index, xtime
        )

        block.transactions = transaction_objs

        txn_hashes = block.get_transaction_hashes()
        block.set_merkle_root(txn_hashes)
        block.header = block.generate_header()
        return block

    async def check_xeggex_hack(self):
        index = self.index
        config = Config()
        if (index >= CHAIN.XEGGEX_HACK_FORK and index < CHAIN.CHECK_KEL_FORK) or (
            index >= CHAIN.XEGGEX_HACK_FORK_2
        ):
            for txn in self.transactions[:]:
                remove = False
                if (
                    txn.public_key
                    == "02fd3ad0e7a613672d9927336d511916e15c507a1fab225ed048579e9880f15fed"
                ):
                    remove = True
                if not remove:
                    for output in txn.outputs:
                        if output.to == "1Kh8tcPNxJsDH4KJx4TzLbqWwihDfhFpzj":
                            remove = True
                            break
                if remove:
                    config.app_log.info(
                        f"Txn removed from block: Xeggex wallet has been frozen."
                    )
                    self.transactions.remove(txn)

    async def pay_masternodes(self, tranaction_objs, triplet, block_reward):
        """Build the coinbase transaction.

        ``triplet`` is a :class:`ReanchorTriplet` from the key rotation manager
        which provides the KEL fields and signing key for the coinbase,
        continuing the key derivation lineage from the re-anchor pair.
        """
        index = self.index
        # Regenerate the coinbase now that all post-build transaction filtering
        # has completed. Transactions may have been removed after the coinbase
        # was first generated (Xeggex freeze, KEL failures, etc.), so the
        # original fee_sum / masternode_fee_sum baked into that coinbase may be
        # too large.  Recompute from the surviving non-coinbase transactions and
        # rebuild the coinbase in-place.
        if index >= CHAIN.PAY_MASTER_NODES_FORK:
            non_coinbase = [t for t in tranaction_objs if not t.coinbase]
            fee_sum = sum(float(t.fee) for t in non_coinbase)
            masternode_fee_sum = 0.0
            if index >= CHAIN.CHECK_MASTERNODE_FEE_FORK:
                masternode_fee_sum = sum(float(t.masternode_fee) for t in non_coinbase)

            # Only nodes with a resolved identity can receive coinbase MN
            # payments.  IA-only bootstrap/dynamic nodes still in
            # NodesTester.successful_nodes with identity=None must not shrink
            # the divisor or leave the miner at 90% with zero MN outputs
            # (verify then sees coinbase_sum+masternode_sum = 0.9*reward).
            reward_nodes = [
                n
                for n in (NodesTester.successful_nodes or [])
                if getattr(n, "identity", None) is not None
                and getattr(n.identity, "public_key", None)
            ]
            self_output = None
            updated_outputs = []
            if reward_nodes:
                self_output = Output.from_dict(
                    {
                        "value": (block_reward * 0.9) + fee_sum,
                        "to": triplet.coinbase_prerotated,
                    }
                )

                masternode_reward_divided = (
                    block_reward * 0.1 + masternode_fee_sum
                ) / len(reward_nodes)
                for successful_node in reward_nodes:
                    updated_outputs.append(
                        Output.from_dict(
                            {
                                "value": float(masternode_reward_divided),
                                "to": str(
                                    P2PKHBitcoinAddress.from_pubkey(
                                        bytes.fromhex(
                                            successful_node.identity.public_key
                                        )
                                    )
                                ),
                            }
                        )
                    )
            else:
                self_output = Output.from_dict(
                    {
                        "value": block_reward + fee_sum + masternode_fee_sum,
                        "to": triplet.coinbase_prerotated,
                    }
                )

            updated_outputs.append(self_output)
            block_time = getattr(self, "time", None)
            new_coinbase = Transaction(
                txn_time=int(block_time) if block_time else int(time.time()),
                version=7,
                outputs=updated_outputs,
                coinbase=True,
            )
        else:
            return

        new_coinbase.public_key = triplet.signer_public_key
        new_coinbase.prerotated_key_hash = triplet.coinbase_prerotated
        new_coinbase.twice_prerotated_key_hash = triplet.coinbase_twice_prerotated
        new_coinbase.public_key_hash = triplet.coinbase_public_key_hash
        new_coinbase.prev_public_key_hash = triplet.coinbase_prev_public_key_hash
        if getattr(triplet, "coinbase_counter", None) is not None:
            new_coinbase.counter = triplet.coinbase_counter
        if getattr(triplet, "coinbase_inception_public_key_hash", None):
            new_coinbase.inception_public_key_hash = (
                triplet.coinbase_inception_public_key_hash
            )
        self_output.to = triplet.coinbase_prerotated

        new_coinbase.hash = await new_coinbase.generate_hash()
        new_coinbase.transaction_signature = NodeKeyRotationManager._sign(
            triplet.signer_private_key, new_coinbase.hash
        )
        new_coinbase.template_kel = True
        return new_coinbase

    @staticmethod
    def _protect_template_kel_cascade(failed_txn, linked_txn) -> bool:
        """True if *linked_txn* must not be cascade-removed when *failed_txn* fails.

        Mining template KEL (coinbase + confirming + optional payout U/C) must
        not be stripped because an unrelated mempool KEL failed.  Failures
        inside the template chain still cascade among themselves.
        """
        linked_is_template = bool(
            getattr(linked_txn, "coinbase", False)
            or getattr(linked_txn, "template_kel", False)
        )
        if not linked_is_template:
            return False
        failed_is_template = bool(
            getattr(failed_txn, "coinbase", False)
            or getattr(failed_txn, "template_kel", False)
        )
        # Protect template members from non-template failures.
        return not failed_is_template

    @staticmethod
    def find_kel_linked_group(txn: Transaction, candidates) -> list:
        """Return every transaction in *candidates* that is transitively
        linked to *txn* via the prerotated_key_hash/twice_prerotated_key_hash
        double-commitment used throughout the KEL/ratchet chain — one
        entry's ``twice_prerotated_key_hash`` names the address the *next*
        entry commits to as its own ``prerotated_key_hash`` (the
        "unconfirmed"/"confirming" pre-commitment check).

        This used to be assumed to pair up at most one "unconfirmed" entry
        with a single "confirming" entry.  Peer-branch bridges
        (``NodeKeyRotationManager._ensure_peer_branch_ready``/
        ``advance_peer_auth_ratchet``) and multi-step re-anchor triplets
        (``_queue_reanchor`` plus its chained coinbase-confirming entry) now
        link arbitrarily many entries this same way — bridge -> branch step
        1 -> branch step 2 -> ... — so a KEL failure on any one entry must
        cascade through the *entire* chain, not just one hop.  The walk
        below is a plain BFS over that relation, symmetric in both
        directions, so it finds the whole connected component regardless of
        which entry in the chain actually failed.

        *txn* is always included in the returned list (even with no other
        linked entries), so callers can iterate the result uniformly.
        """

        def _linked(a, b):
            return (
                a.twice_prerotated_key_hash
                and a.twice_prerotated_key_hash == b.prerotated_key_hash
            ) or (
                b.twice_prerotated_key_hash
                and b.twice_prerotated_key_hash == a.prerotated_key_hash
            )

        group = {id(txn): txn}
        frontier = [txn]
        while frontier:
            current = frontier.pop()
            for candidate in candidates:
                if id(candidate) in group:
                    continue
                if _linked(current, candidate):
                    group[id(candidate)] = candidate
                    frontier.append(candidate)
        return list(group.values())

    async def remove_transaction(
        self, txn: Transaction, hash_collection: KELHashCollection = None
    ):
        """Remove *txn* — and every other transaction transitively KEL-linked
        to it (see ``find_kel_linked_group``) — from both this block's
        candidate list and the mempool.

        ``hash_collection`` is accepted for backwards compatibility with
        existing callers but is no longer required: the search now walks
        ``self.transactions`` directly so it isn't limited to a single hop.
        """
        linked_group = self.find_kel_linked_group(txn, self.transactions)
        for linked_txn in linked_group:
            label = "Txn" if linked_txn is txn else "Linked txn"
            self.config.app_log.info(
                f"Fatal - {label} removed from block: {linked_txn.transaction_signature}"
            )
            await self.config.mongo.async_db.miner_transactions.delete_one(
                {"id": linked_txn.transaction_signature}
            )
            if linked_txn in self.transactions:
                self.transactions.remove(linked_txn)

    @staticmethod
    def tag_kel_chain_entries(chain, onchain_parent=None):
        """Stamp inception_public_key_hash and counter on in-memory KEL entries.

        Block generation loads mempool txns via ``from_dict`` before any KEL walk
        has tagged them. Double-spend and tip-auth need these fields on the
        objects that enter ``validate_transactions`` / the mined block.

        *onchain_parent* is the latest on-chain tip when *chain[0]* extends it;
        ``None`` means *chain[0]* is an inception / recovers-inception root.
        Existing tags are preserved when already set; counters advance from the
        last known tagged counter in the parent→chain sequence.
        """
        if not chain:
            return

        if onchain_parent is not None:
            inception_pkh = getattr(
                onchain_parent, "inception_public_key_hash", None
            ) or getattr(onchain_parent, "public_key_hash", None)
            parent_counter = getattr(onchain_parent, "counter", None)
            next_counter = parent_counter + 1 if parent_counter is not None else None
        else:
            root = chain[0]
            inception_pkh = getattr(root, "inception_public_key_hash", None) or getattr(
                root, "public_key_hash", None
            )
            next_counter = 0

        if not inception_pkh:
            return

        for entry in chain:
            existing_inc = getattr(entry, "inception_public_key_hash", None)
            if existing_inc:
                if existing_inc != inception_pkh:
                    # Do not retag across KEL boundaries.
                    return
                inception_pkh = existing_inc
            else:
                entry.inception_public_key_hash = inception_pkh

            existing_c = getattr(entry, "counter", None)
            if existing_c is not None:
                next_counter = existing_c + 1
            else:
                if next_counter is not None:
                    entry.counter = next_counter
                    next_counter = next_counter + 1

    @staticmethod
    def clear_untrusted_kel_tags(txns):
        """Drop peer/mempool inception tags so local derivation is authoritative."""
        if not txns:
            return
        for txn in txns:
            if hasattr(txn, "inception_public_key_hash"):
                txn.inception_public_key_hash = None
            if hasattr(txn, "counter"):
                txn.counter = None

    @staticmethod
    async def ensure_kel_tags(txns, *, clear_untrusted=False):
        """Ensure KEL txns carry inception_public_key_hash and counter in-memory.

        Used at block insert (and generation) so persisted block documents
        always store these fields for double-spend / tip lookup. Walks KEL
        chains inside *txns* the same way as generation: inception roots, or
        direct children of the latest on-chain tip. Existing tags are kept
        unless *clear_untrusted* is True (peer/mempool path).
        """
        if clear_untrusted:
            Block.clear_untrusted_kel_tags(txns)
        if not txns:
            return

        from yadacoin.core.keyeventlog import (
            KeyEventFlag,
            classify_key_event_flag,
            is_mempool_kel_root,
            is_recovers_inception,
            kel_successor_flag_allowed,
            verify_kel_step,
        )

        kel_candidates = []
        for txn in txns:
            are_kel = getattr(txn, "are_kel_fields_populated", None)
            if not are_kel or not txn.are_kel_fields_populated():
                continue
            kel_candidates.append(txn)

        if not kel_candidates:
            return

        children_of = {}
        for txn in kel_candidates:
            prev = getattr(txn, "prev_public_key_hash", None) or ""
            children_of.setdefault(prev, []).append(txn)

        claimed = set()
        roots = []
        root_parents = {}
        for txn in kel_candidates:
            try:
                is_root, parent = await is_mempool_kel_root(txn)
            except Exception:
                is_root, parent = False, None
            if is_root:
                roots.append(txn)
                root_parents[txn.transaction_signature] = parent

        for root in roots:
            if root.transaction_signature in claimed:
                continue
            chain = [root]
            prev = root
            prev_flag = classify_key_event_flag(root)
            while True:
                kids = [
                    k
                    for k in children_of.get(prev.public_key_hash, [])
                    if k.transaction_signature not in claimed
                    and k.transaction_signature != prev.transaction_signature
                    and k not in chain
                ]
                if not kids:
                    break
                valid_kids = []
                for kid in kids:
                    kid_flag = classify_key_event_flag(kid)
                    if not kel_successor_flag_allowed(prev_flag, kid_flag):
                        continue
                    try:
                        verify_kel_step(prev, kid, previous_onchain=False)
                        valid_kids.append(kid)
                    except Exception:
                        continue
                if len(valid_kids) != 1:
                    break
                nxt = valid_kids[0]
                chain.append(nxt)
                prev = nxt
                prev_flag = classify_key_event_flag(nxt)

            Block.tag_kel_chain_entries(
                chain, onchain_parent=root_parents.get(root.transaction_signature)
            )
            for m in chain:
                claimed.add(m.transaction_signature)

        # Remaining unclaimed KEL entries: stamp from any already-tagged sibling
        # in a linked group (template coinbase/settlement often already tagged).
        for txn in kel_candidates:
            if txn.transaction_signature in claimed:
                continue
            if (
                getattr(txn, "inception_public_key_hash", None) is not None
                and getattr(txn, "counter", None) is not None
            ):
                claimed.add(txn.transaction_signature)
                continue
            group = Block.find_kel_linked_group(txn, kel_candidates)
            # Prefer a member that already has inception as seed for ordering.
            seed = None
            for g in group:
                if getattr(g, "inception_public_key_hash", None):
                    seed = g
                    break
            if seed is None:
                # Inception-shaped untagged root: use public_key_hash.
                flag = classify_key_event_flag(txn)
                if flag == KeyEventFlag.INCEPTION or is_recovers_inception(txn):
                    Block.tag_kel_chain_entries([txn], onchain_parent=None)
                    claimed.add(txn.transaction_signature)
                continue
            by_pkh = {
                getattr(g, "public_key_hash", None): g
                for g in group
                if getattr(g, "public_key_hash", None)
            }
            starts = [
                g
                for g in group
                if getattr(g, "prev_public_key_hash", None) not in by_pkh
            ]
            if not starts:
                starts = [seed]
            ordered = []
            seen = set()
            queue = list(starts)
            while queue:
                cur = queue.pop(0)
                if id(cur) in seen:
                    continue
                seen.add(id(cur))
                ordered.append(cur)
                pre = getattr(cur, "prerotated_key_hash", None)
                cur_pkh = getattr(cur, "public_key_hash", None)
                for g in group:
                    if id(g) in seen:
                        continue
                    if (
                        getattr(g, "prev_public_key_hash", None) == cur_pkh
                        and getattr(g, "public_key_hash", None) == pre
                    ):
                        queue.append(g)
            for g in group:
                if id(g) not in seen:
                    ordered.append(g)
            Block.tag_kel_chain_entries(ordered, onchain_parent=None)
            for g in ordered:
                claimed.add(g.transaction_signature)

    @staticmethod
    async def select_kel_chains_for_block(
        txns, block_index=None, max_transactions=1000
    ):
        """Partition and filter KEL candidates for block generation.

        1. Collect KEL candidates (``are_kel_fields_populated``).
        2. Find mempool roots (inception, or direct child of latest on-chain tip).
        3. Walk each root forward inside *txns* with pairwise ``verify_kel_step``.
        4. Accept only complete chains; drop incomplete/orphan KEL members from
           *txns* and delete them from ``miner_transactions``.
        5. Respect *max_transactions* total block size: if a complete chain would
           push the candidate set over the limit, keep the longest prefix that
           still ends on a CONFIRMING entry (or a lone INCEPTION).  Deferred
           tail members stay in the mempool for the next block (not failed).
        6. Stamp ``inception_public_key_hash`` / ``counter`` on accepted members
           so block-generation double-spend and tip-auth see KEL identity.

        Non-KEL transactions are left untouched.  Returns
        ``(accepted_kel_txns, rejected_kel_txns)``.
        """
        from yadacoin.core.keyeventlog import (
            KeyEventFlag,
            classify_key_event_flag,
            is_kel_chain_complete,
            is_mempool_kel_root,
            is_recovers_inception,
            kel_successor_flag_allowed,
            verify_kel_step,
        )

        config = Config()

        kel_candidates = []
        for txn in txns:
            if not getattr(txn, "are_kel_fields_populated", None):
                continue
            if not txn.are_kel_fields_populated():
                continue
            kel_candidates.append(txn)

        if not kel_candidates:
            return [], []

        # Index children by prev_public_key_hash for forward walks.
        children_of = {}
        by_sig = {}
        for txn in kel_candidates:
            by_sig[txn.transaction_signature] = txn
            prev = txn.prev_public_key_hash or ""
            children_of.setdefault(prev, []).append(txn)

        claimed = set()  # transaction_signature
        accepted = []
        rejected = []
        deferred = []  # valid chain tail deferred to next block (stay in mempool)

        # Capacity: non-KEL already in the candidate set consume slots.
        kel_sigs = {t.transaction_signature for t in kel_candidates}
        non_kel_count = sum(1 for t in txns if t.transaction_signature not in kel_sigs)
        # Slots remaining for KEL entries after non-KEL are reserved.
        if max_transactions is None or max_transactions < 0:
            max_transactions = 1000

        def _slots_left():
            return max(0, max_transactions - non_kel_count - len(accepted))

        def _longest_fitting_prefix(chain):
            """Longest root-first prefix that is complete and fits in remaining slots."""
            slots = _slots_left()
            if slots <= 0:
                return []
            # Prefer full chain when it fits and is complete.
            if len(chain) <= slots and is_kel_chain_complete(chain):
                return list(chain)
            # Otherwise walk back to the last confirming tip within budget.
            limit = min(len(chain), slots)
            for end in range(limit, 0, -1):
                prefix = chain[:end]
                if is_kel_chain_complete(prefix):
                    return prefix
            return []

        def _is_template_kel(m):
            # Coinbase unconfirmed, coinbase_confirming, and template pool
            # payout U/C pairs are block-local — never discard/defer them.
            return bool(
                getattr(m, "coinbase", False) or getattr(m, "template_kel", False)
            )

        async def _defer(members, reason):
            """Omit from this block but leave in mempool for a later block."""
            for m in members:
                sig = m.transaction_signature
                if sig in claimed:  # pragma: no cover
                    continue
                if _is_template_kel(m):
                    # Template KEL steps must stay in the candidate set.
                    claimed.add(sig)
                    if m not in accepted:
                        accepted.append(m)
                    continue
                claimed.add(sig)
                deferred.append(m)
                config.app_log.info(
                    f"select_kel_chains_for_block: deferring KEL txn "
                    f"{sig[:24]}... to next block ({reason})"
                )

        async def _discard(members, reason):
            for m in members:
                sig = m.transaction_signature
                if sig in claimed:
                    continue
                # Block-local coinbase / coinbase_confirming / template payout
                # are not mempool entries and must stay in the candidate set.
                if _is_template_kel(m):
                    claimed.add(sig)
                    if m not in accepted:
                        accepted.append(m)
                    config.app_log.debug(
                        f"select_kel_chains_for_block: keeping template KEL txn "
                        f"{sig[:24]}... despite: {reason}"
                    )
                    continue
                claimed.add(sig)
                rejected.append(m)
                config.app_log.info(
                    f"select_kel_chains_for_block: discarding KEL txn "
                    f"{sig[:24]}... ({reason})"
                )
                try:
                    await config.mongo.async_db.failed_transactions.insert_one(
                        {
                            "reason": "KELChainDiscard",
                            "message": str(reason),
                            "txn": m.to_dict(),
                        }
                    )
                except Exception as exc:
                    config.app_log.warning(
                        f"select_kel_chains_for_block: failed_transactions "
                        f"insert failed: {exc}"
                    )
                try:
                    await config.mongo.async_db.miner_transactions.delete_one(
                        {"id": sig}
                    )
                except Exception as exc:
                    config.app_log.warning(
                        f"select_kel_chains_for_block: mempool delete failed: {exc}"
                    )

        # Identify roots first.
        roots = []
        root_parents = {}  # sig -> onchain parent txn or None
        for txn in kel_candidates:
            try:
                is_root, parent = await is_mempool_kel_root(txn)
            except Exception as exc:
                config.app_log.warning(
                    f"select_kel_chains_for_block: root check failed for "
                    f"{txn.transaction_signature[:24]}...: {exc}"
                )
                is_root, parent = False, None
            if is_root:
                roots.append(txn)
                root_parents[txn.transaction_signature] = parent

        for root in roots:
            if root.transaction_signature in claimed:
                continue

            chain = [root]
            prev = root
            prev_flag = classify_key_event_flag(root)
            # If root is inception, validate its own shape.
            if (
                prev_flag == KeyEventFlag.INCEPTION or is_recovers_inception(root)
            ) and not getattr(root, "coinbase", False):
                try:
                    from yadacoin.core.keyeventlog import KeyEvent, KeyEventChainStatus

                    ke = KeyEvent(
                        root,
                        flag=KeyEventFlag.INCEPTION,
                        status=KeyEventChainStatus.MEMPOOL,
                    )
                    if is_recovers_inception(root):
                        ke.verify_fields(prev_public_key_hash_required=False)
                    else:
                        ke.verify_inception(onchain=False)
                except Exception as exc:
                    await _discard([root], f"invalid inception root: {exc}")
                    continue

            walk_failed = False
            while True:
                kids = [
                    k
                    for k in children_of.get(prev.public_key_hash, [])
                    if k.transaction_signature not in claimed
                    and k.transaction_signature != prev.transaction_signature
                    and k not in chain
                ]
                if not kids:
                    break
                # Evaluate each candidate successor; require exactly one valid.
                valid_kids = []
                for kid in kids:
                    kid_flag = classify_key_event_flag(kid)
                    if not kel_successor_flag_allowed(prev_flag, kid_flag):
                        continue
                    try:
                        verify_kel_step(prev, kid, previous_onchain=False)
                        valid_kids.append(kid)
                    except Exception:
                        continue
                if not valid_kids:
                    # Kids exist but none are valid successors — stop walk;
                    # invalid kids become orphans and are discarded later.
                    break
                if len(valid_kids) > 1:
                    # Ambiguous fork in mempool.
                    walk_failed = True
                    chain.extend(valid_kids)
                    break
                nxt = valid_kids[0]
                chain.append(nxt)
                prev = nxt
                prev_flag = classify_key_event_flag(nxt)

            if walk_failed or not is_kel_chain_complete(chain):
                # Also pull any unclaimed kids we didn't walk into discard set
                # when the chain is incomplete at UNCONFIRMED tip.
                await _discard(chain, "incomplete or invalid KEL chain")
                continue

            prefix = _longest_fitting_prefix(chain)
            if not prefix:
                # No complete prefix fits — defer entire chain to next block.
                await _defer(chain, "block transaction limit; no complete prefix fits")
                continue

            # Stamp inception/counter on the kept prefix before verify/double-spend.
            Block.tag_kel_chain_entries(
                prefix, onchain_parent=root_parents.get(root.transaction_signature)
            )
            for m in prefix:
                claimed.add(m.transaction_signature)
                accepted.append(m)

            tail = chain[len(prefix) :]
            if tail:
                await _defer(
                    tail,
                    f"block transaction limit; kept {len(prefix)} of {len(chain)} "
                    f"ending on confirming",
                )

        # Orphans: KEL candidates never claimed as part of a complete chain.
        for txn in kel_candidates:
            if txn.transaction_signature not in claimed:
                await _discard([txn], "orphan KEL (not reached from a root)")

        # Mutate txns: remove rejected (failed) and deferred (next block).
        remove_sigs = {t.transaction_signature for t in rejected} | {
            t.transaction_signature for t in deferred
        }
        if remove_sigs:
            for txn in list(txns):
                if txn.transaction_signature in remove_sigs:
                    txns.remove(txn)

        return accepted, rejected

    @staticmethod
    async def validate_transactions(
        block, txns, transaction_objs, used_sigs, used_inputs, index, xtime
    ):
        # SHOULD ONLY EVER BE USED FOR BLOCK GENERATION,
        # NEVER FOR BLOCK VALIDATION
        # (since mempool state is not relevant for validation and
        # can be manipulated by attackers to cause valid transactions to be rejected)
        config = Config()
        used_inputs_by_id = {}
        # Use a minimal block proxy so Transaction.verify() calls
        # has_key_event_log(block=proxy, mempool=False), mirroring Block.verify()'s
        # on-chain-only check.  Transactions whose KEL parent is only in the mempool
        # (not on-chain and not in txns) will raise
        # KELExceptionPreviousKeyHashReferenceMissing, which is caught below as a
        # transient skip — keeping the txn in the mempool for the next block cycle.
        # This prevents the block factory from embedding a transaction that
        # Block.verify() will later reject, which would silently drop a winning block.
        if index >= CHAIN.ALLOW_SAME_BLOCK_SPENDING_FORK:
            items_indexed = {x.transaction_signature: x for x in txns}
            for txn in txns:
                for input_item in txn.inputs:
                    if input_item.id in items_indexed:
                        input_item.input_txn = items_indexed[input_item.id]
                        items_indexed[input_item.id].spent_in_txn = txn

        # Track takedown targets seen so far in this block to enforce the
        # one-takedown-per-transaction rule at block-generation time.
        seen_takedown_targets: set = set()
        if index >= CHAIN.CONTENT_TAKEDOWN_FORK:
            from yadacoin.core.contenttakedown import (
                ContentTakedownAnnouncement as _CTA,
            )

            for txn in txns[:]:
                if not isinstance(txn.relationship, _CTA):
                    continue
                target_id = txn.relationship.transaction_id
                # Also reject if a takedown for this target is already on-chain.
                already_onchain = await config.mongo.async_db.blocks.find_one(
                    {
                        "transactions.relationship.content_takedown.transaction_id": target_id
                    },
                    {"_id": 1},
                )
                if target_id in seen_takedown_targets or already_onchain:
                    config.app_log.info(
                        f"Duplicate content takedown for {target_id!r} removed from block candidate."
                    )
                    txns.remove(txn)
                    continue
                seen_takedown_targets.add(target_id)

        for transaction_obj in txns[:]:
            try:
                if transaction_obj.transaction_signature in used_sigs:
                    raise InvalidTransactionException(
                        "duplicate transaction found and removed"
                    )
                check_max_inputs = False
                if index > CHAIN.CHECK_MAX_INPUTS_FORK:
                    check_max_inputs = True

                check_masternode_fee = False
                if index >= CHAIN.CHECK_MASTERNODE_FEE_FORK:
                    check_masternode_fee = True

                check_kel = False
                if index >= CHAIN.CHECK_KEL_FORK:
                    check_kel = True

                check_dynamic_nodes = False
                if index >= CHAIN.DYNAMIC_NODES_FORK:
                    check_dynamic_nodes = True

                check_content_takedown = index >= CHAIN.CONTENT_TAKEDOWN_FORK
                check_branch_announcement = index >= CHAIN.KEL_BRANCH_ANNOUNCEMENT_FORK

                await transaction_obj.verify(
                    check_max_inputs=check_max_inputs,
                    check_masternode_fee=check_masternode_fee,
                    check_kel=check_kel,
                    check_dynamic_nodes=check_dynamic_nodes,
                    check_content_takedown=check_content_takedown,
                    check_branch_announcement=check_branch_announcement,
                    block=block,
                    mempool=False,
                    batch_txns=txns,
                )
                # KEL chain assembly is done in select_kel_chains_for_block
                # before this loop.  Do not re-run KeyEventLog.init_async
                # (9-scenario) during generate.
                for output in transaction_obj.outputs:
                    if not config.address_is_valid(output.to):
                        raise TransactionAddressInvalidException(
                            "Output address is invalid"
                        )
                used_sigs.append(transaction_obj.transaction_signature)
            except (KELExceptionPreviousKeyHashReferenceMissing,) as e:
                # Transient: KEL inception not yet on-chain/in mempool; skip this
                # txn for this block cycle but leave it in the mempool for next time.
                # Remove from txns so it cannot act as a phantom batch_txns sibling
                # for any subsequent transaction in this same validation pass.
                config.app_log.warning(
                    f"validate_transactions transient KEL skip: {e} | txn={transaction_obj.transaction_signature}"
                )
                linked_group = Block.find_kel_linked_group(transaction_obj, txns)
                for linked_txn in linked_group:
                    if (
                        linked_txn is not transaction_obj
                        and Block._protect_template_kel_cascade(
                            transaction_obj, linked_txn
                        )
                    ):
                        continue
                    if linked_txn.coinbase:
                        config.app_log.warning(
                            f"validate_transactions transient KEL skip: linked coinbase txn removed from block: {linked_txn.transaction_signature}"
                        )
                    if linked_txn in txns:
                        txns.remove(linked_txn)

                    if linked_txn in transaction_objs:
                        transaction_objs.remove(linked_txn)

                    if linked_txn is not transaction_obj:
                        config.app_log.info(
                            f"KEL cascade: linked txn removed from block: "
                            f"{linked_txn.transaction_signature}"
                        )
                if transaction_obj in txns:
                    txns.remove(transaction_obj)

                if transaction_obj in transaction_objs:
                    transaction_objs.remove(transaction_obj)
                continue
            except Exception as e:
                await Transaction.handle_exception(e, transaction_obj)
                # Remove from txns so subsequent transactions cannot use this
                # failed transaction as a phantom batch_txns sibling. Also
                # cascade to every other txn transitively KEL-linked to it
                # via the prerotated_key_hash/twice_prerotated_key_hash
                # double-commitment chain — peer-branch bridges and
                # multi-step re-anchor triplets can link more than a single
                # unconfirmed/confirming pair now, so one failing entry can
                # orphan an arbitrarily long chain of siblings, not just one.
                linked_group = Block.find_kel_linked_group(transaction_obj, txns)
                for linked_txn in linked_group:
                    if (
                        linked_txn is not transaction_obj
                        and Block._protect_template_kel_cascade(
                            transaction_obj, linked_txn
                        )
                    ):
                        continue
                    if linked_txn.coinbase:
                        config.app_log.warning(
                            f"validate_transactions permanent KEL skip: linked coinbase txn removed from block: {linked_txn.transaction_signature}"
                        )
                    if linked_txn in txns:
                        txns.remove(linked_txn)

                    if linked_txn in transaction_objs:
                        transaction_objs.remove(linked_txn)

                    if linked_txn is not transaction_obj:
                        config.app_log.info(
                            f"KEL cascade: linked txn removed from block: "
                            f"{linked_txn.transaction_signature}"
                        )
                        await config.mongo.async_db.miner_transactions.delete_one(
                            {"id": linked_txn.transaction_signature}
                        )
                if (
                    transaction_obj.spent_in_txn
                    and transaction_obj.spent_in_txn in transaction_objs
                ):
                    transaction_objs.remove(transaction_obj.spent_in_txn)
                if transaction_obj.spent_in_txn in txns:
                    txns.remove(transaction_obj.spent_in_txn)
                await config.mongo.async_db.miner_transactions.delete_one(
                    {"id": transaction_obj.transaction_signature}
                )
                continue
            try:
                if int(index) > CHAIN.CHECK_TIME_FROM and (
                    int(transaction_obj.time) > int(xtime) + CHAIN.TIME_TOLERANCE
                ):
                    await config.mongo.async_db.miner_transactions.delete_many(
                        {"id": transaction_obj.transaction_signature}
                    )
                    raise InvalidTransactionException(
                        "Block embeds txn too far in the future {} {}".format(
                            xtime, transaction_obj.time
                        )
                    )

                if transaction_obj.inputs:
                    failed = False
                    input_ids = []
                    spender_inc = getattr(
                        transaction_obj, "inception_public_key_hash", None
                    )
                    for x in transaction_obj.inputs:
                        if (x.id, transaction_obj.public_key) in used_inputs:
                            failed = True
                        elif x.id in used_inputs_by_id:
                            from yadacoin.core.keyeventlog import KeyEventLog

                            prior_pk, prior_inc = used_inputs_by_id[x.id]
                            try:
                                if await KeyEventLog.kel_spend_conflict(
                                    transaction_obj.public_key,
                                    prior_pk,
                                    inception_a=spender_inc,
                                    inception_b=prior_inc,
                                    onchain_only=True,
                                ):
                                    failed = True
                            except Exception:
                                # Fail closed: cannot prove distinct KELs.
                                failed = True
                        used_inputs[
                            (x.id, transaction_obj.public_key)
                        ] = transaction_obj
                        used_inputs_by_id[x.id] = (
                            transaction_obj.public_key,
                            spender_inc,
                        )
                        input_ids.append(x.id)
                    is_input_spent = await config.BU.is_input_spent(
                        input_ids,
                        transaction_obj.public_key,
                        spender_inception=spender_inc,
                    )
                    if is_input_spent:
                        if transaction_obj.public_key == config.public_key:
                            # Silently discard this node's own duplicate transaction —
                            # inputs are already confirmed on-chain (e.g. a reorg caused
                            # a second payout to be created while the first was rolling
                            # back). The original payout succeeded; recording a failure
                            # here produces a false negative in the payout UI.
                            await config.mongo.async_db.miner_transactions.delete_many(
                                {"id": transaction_obj.transaction_signature}
                            )
                            if transaction_obj in txns:
                                txns.remove(transaction_obj)
                            continue
                        failed = True
                    if len(input_ids) != len(list(set(input_ids))):
                        failed = True
                    if failed:
                        raise InvalidTransactionException(
                            f"Transaction has inputs already spent: {transaction_obj.transaction_signature}"
                        )

            except Exception as e:
                await Transaction.handle_exception(e, transaction_obj)
                continue

            transaction_objs.append(transaction_obj)

    def generate_header(self):
        if int(self.version) < 3:
            return (
                str(self.version)
                + str(self.time)
                + self.public_key
                + str(self.index)
                + self.prev_hash
                + "{nonce}"
                + str(self.special_min)
                + str(self.target)
                + self.merkle_root
            )
        else:
            # version 3 block do not contain special_min anymore and have target as 64 hex string
            # print("target", block.target)
            # TODO: somewhere, target is calc with a / and result is float instead of int.
            return (
                str(self.version)
                + str(self.time)
                + self.public_key
                + str(self.index)
                + self.prev_hash
                + "{nonce}"
                + hex(int(self.target))[2:].rjust(64, "0")
                + self.merkle_root
            )

    def set_merkle_root(self, txn_hashes):
        self.merkle_root = self.get_merkle_root(txn_hashes)

    def get_merkle_root(self, txn_hashes):
        hashes = []
        for i in range(0, len(txn_hashes), 2):
            txn1 = txn_hashes[i]
            try:
                txn2 = txn_hashes[i + 1]
            except IndexError:
                txn2 = ""
            hashes.append(hashlib.sha256((txn1 + txn2).encode("utf-8")).digest().hex())
        if len(hashes) > 1:
            return self.get_merkle_root(hashes)
        else:
            return hashes[0]

    @classmethod
    async def from_dict(cls, block):
        if isinstance(block, Block):
            return block
        if block.get("special_target", 0) == 0:
            block["special_target"] = block.get("target")

        return await cls.init_async(
            version=block.get("version"),
            block_time=block.get("time"),
            block_index=block.get("index"),
            public_key=block.get("public_key"),
            prev_hash=block.get("prevHash"),
            nonce=block.get("nonce"),
            block_hash=block.get("hash"),
            transactions=block.get("transactions"),
            merkle_root=block.get("merkleRoot"),
            signature=block.get("id"),
            special_min=block.get("special_min"),
            header=block.get("header", ""),
            target=int(block.get("target"), 16),
            special_target=int(block.get("special_target", 0), 16),
        )

    @classmethod
    async def from_json(cls, block_json):
        return await cls.from_dict(json.loads(block_json))

    def get_coinbase(self):
        for txn in self.transactions:
            if Block.is_coinbase(self, txn):
                return txn

    @staticmethod
    def is_coinbase(block, txn):
        block_address = str(
            P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(block.public_key))
        )
        return (
            block.public_key == txn.public_key
            and len(txn.inputs) == 0
            and (
                block_address in [x.to for x in txn.outputs]
                or (
                    block_address == txn.public_key_hash
                    and txn.prerotated_key_hash in [x.to for x in txn.outputs]
                )
            )
        )

    async def generate_hash_from_header(self, height, header, nonce):
        if not hasattr(Block, "pyrx"):
            Block.pyrx = pyrx.PyRX()
        seed_hash = binascii.unhexlify(
            "4181a493b397a733b083639334bc32b407915b9a82b7917ac361816f0a1f5d4d"
        )  # sha256(yadacoin65000)
        if height >= CHAIN.BLOCK_V5_FORK:
            bh = Block.pyrx.get_rx_hash(
                header.encode().replace(b"{nonce}", binascii.unhexlify(nonce)),
                seed_hash,
                height,
            )
            hh = binascii.hexlify(bh).decode()
            return hh
        elif height >= CHAIN.RANDOMX_FORK:
            header = header.format(nonce=nonce)
            bh = Block.pyrx.get_rx_hash(header, seed_hash, height)
            hh = binascii.hexlify(bh).decode()
            return hh
        else:
            header = header.format(nonce=nonce)
            return (
                hashlib.sha256(hashlib.sha256(header.encode("utf-8")).digest())
                .digest()[::-1]
                .hex()
            )

    async def verify(self, extra_blocks=None):
        if extra_blocks is None:
            extra_blocks = []
        getcontext().prec = 8
        if int(self.version) != int(CHAIN.get_version_for_height(self.index)):
            raise Exception(
                "Wrong version for block height",
                self.version,
                CHAIN.get_version_for_height(self.index),
            )

        # Validate block does not exceed 1000 transactions (post dynamic-nodes fork only)
        if self.index >= CHAIN.DYNAMIC_NODES_FORK and len(self.transactions) > 1000:
            raise Exception(
                f"Block contains {len(self.transactions)} transactions, maximum is 1000"
            )

        coinbase_count = sum(1 for t in self.transactions if t.coinbase)
        if coinbase_count != 1:
            raise Exception(
                f"Block must contain exactly one coinbase transaction, found {coinbase_count}"
            )

        txns = self.get_transaction_hashes()
        verify_merkle_root = self.get_merkle_root(txns)
        if verify_merkle_root != self.merkle_root:
            raise Exception("Invalid block merkle root")

        header = self.generate_header()
        hashtest = await self.generate_hash_from_header(
            self.index, header, str(self.nonce)
        )
        if self.hash != hashtest:
            getLogger("tornado.application").warning(
                "Verify error hashtest {} header {} nonce {}".format(
                    hashtest, header, self.nonce
                )
            )
            raise Exception("Invalid block hash")

        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))
        self.verify_signature(address)

        if self.index >= CHAIN.ALLOW_SAME_BLOCK_SPENDING_FORK:
            items_indexed = {x.transaction_signature: x for x in self.transactions}
            for txn in self.transactions:
                for input_item in txn.inputs:
                    if input_item.id in items_indexed:
                        input_item.input_txn = items_indexed[input_item.id]
                        items_indexed[input_item.id].spent_in_txn = txn

        # verify reward
        coinbase_sum = 0.0
        fee_sum = 0.0
        masternode_fee_sum = 0.0
        masternode_sums = {}
        for txn in self.transactions:
            if int(self.index) >= CHAIN.TXN_V3_FORK and int(txn.version) < 3:
                raise Exception(
                    "block contains transaction with version too old for this height"
                )

            if self.index >= CHAIN.SMART_CONTRACT_REMOVAL_FORK:
                if (
                    isinstance(txn.relationship, dict)
                    and "smart_contract" in txn.relationship
                ):
                    raise Exception(
                        "smart contract transactions are not allowed after SMART_CONTRACT_REMOVAL_FORK"
                    )
                if await txn.contract_generated:
                    raise Exception(
                        "contract-generated transactions are not allowed after SMART_CONTRACT_REMOVAL_FORK"
                    )

            if int(self.index) > CHAIN.CHECK_TIME_FROM and (
                int(txn.time) > int(self.time) + CHAIN.TIME_TOLERANCE
            ):
                pass  # enforced in validate_transactions; verify() is also called by block_factory on its own in-progress block

            if self.index >= CHAIN.CHECK_KEL_FORK:
                # check if this transaction public key is listed in any KEL
                # if it is, check if it's a valid key event

                # KEL may only advance by the direct next hop of the current
                # tip.  A parent already has a child ⇒ this entry is a second
                # extension (fork / gap under corrupt history) and must be
                # rejected.  Skips are never valid chain motion.  Full pre/twice
                # alignment for non-coinbase stays in KeyEventLog; coinbase
                # gets explicit parent link checks here.
                #
                # Parent resolution must include same-block siblings and
                # extra_blocks (sync batch): during integrate, prior blocks in
                # the batch are not yet in Mongo, so a Mongo-only lookup false-
                # negatives "no parent" on valid continuous chains.
                if txn.are_kel_fields_populated() and txn.prev_public_key_hash:
                    prev_pkh = txn.prev_public_key_hash
                    parent_fields = None  # dict with pkh/pre/twice

                    def _fields_from_txn_obj(t):
                        return {
                            "public_key_hash": getattr(t, "public_key_hash", None)
                            or "",
                            "prerotated_key_hash": getattr(
                                t, "prerotated_key_hash", None
                            )
                            or "",
                            "twice_prerotated_key_hash": getattr(
                                t, "twice_prerotated_key_hash", None
                            )
                            or "",
                            "transaction_signature": getattr(
                                t, "transaction_signature", None
                            ),
                        }

                    # 1) Same-block sibling parent
                    for s in self.transactions:
                        if s.transaction_signature == txn.transaction_signature:
                            continue
                        if getattr(s, "public_key_hash", None) == prev_pkh:
                            parent_fields = _fields_from_txn_obj(s)
                            break

                    # 2) Prior blocks in this verify batch (not yet persisted)
                    if parent_fields is None and extra_blocks:
                        for eb in extra_blocks:
                            eb_idx = getattr(eb, "index", None)
                            if eb_idx is not None and eb_idx >= self.index:
                                continue
                            for s in getattr(eb, "transactions", []) or []:
                                if getattr(s, "public_key_hash", None) == prev_pkh:
                                    parent_fields = _fields_from_txn_obj(s)
                                    break
                            if parent_fields is not None:
                                break

                    # 3) Confirmed chain in Mongo
                    if parent_fields is None:
                        parent_doc = await self.config.mongo.async_db.blocks.find_one(
                            {
                                "index": {"$lt": self.index},
                                "transactions.public_key_hash": prev_pkh,
                            },
                            {
                                "transactions": {
                                    "$elemMatch": {"public_key_hash": prev_pkh}
                                }
                            },
                        )
                        if parent_doc and parent_doc.get("transactions"):
                            pt = parent_doc["transactions"][0]
                            parent_fields = {
                                "public_key_hash": pt.get("public_key_hash") or "",
                                "prerotated_key_hash": pt.get("prerotated_key_hash")
                                or "",
                                "twice_prerotated_key_hash": pt.get(
                                    "twice_prerotated_key_hash"
                                )
                                or "",
                                "transaction_signature": pt.get("id"),
                            }

                    if parent_fields is not None:
                        if txn.coinbase:
                            if (
                                parent_fields["prerotated_key_hash"]
                                != txn.public_key_hash
                            ):
                                raise Exception(
                                    "Coinbase skips or jumps KEL tip: parent "
                                    f"{prev_pkh} prerotated "
                                    f"{parent_fields['prerotated_key_hash']} != "
                                    f"coinbase public_key_hash {txn.public_key_hash}"
                                )
                            if (
                                parent_fields["twice_prerotated_key_hash"]
                                and parent_fields["twice_prerotated_key_hash"]
                                != txn.prerotated_key_hash
                            ):
                                raise Exception(
                                    "Coinbase KEL hash-link broken: parent "
                                    f"twice_prerotated "
                                    f"{parent_fields['twice_prerotated_key_hash']} "
                                    f"!= coinbase prerotated {txn.prerotated_key_hash}"
                                )
                        # Parent may have at most one direct child.  Direct means
                        # prev == parent.pkh or pkh == parent.pre.  Do not treat
                        # the same-block confirming hop (prev == this.pkh) as a
                        # second child of parent — that is the legal U→C pair.
                        parent_pre = parent_fields["prerotated_key_hash"]
                        parent_pkh = parent_fields["public_key_hash"] or prev_pkh
                        self_sig = txn.transaction_signature

                        def _is_direct_child_of_parent(t):
                            if getattr(t, "transaction_signature", None) == self_sig:
                                return False
                            t_pkh = getattr(t, "public_key_hash", None) or ""
                            t_prev = getattr(t, "prev_public_key_hash", None) or ""
                            if t_prev == parent_pkh:
                                return True
                            if parent_pre and t_pkh == parent_pre:
                                return True
                            return False

                        already_extended = False
                        for s in self.transactions:
                            if _is_direct_child_of_parent(s):
                                already_extended = True
                                break
                        if not already_extended and extra_blocks:
                            for eb in extra_blocks:
                                eb_idx = getattr(eb, "index", None)
                                if eb_idx is not None and eb_idx >= self.index:
                                    continue
                                for s in getattr(eb, "transactions", []) or []:
                                    if _is_direct_child_of_parent(s):
                                        already_extended = True
                                        break
                                if already_extended:
                                    break
                        if not already_extended:
                            child_or = [
                                {"transactions.prev_public_key_hash": parent_pkh},
                            ]
                            if parent_pre:
                                child_or.append(
                                    {"transactions.public_key_hash": parent_pre}
                                )
                            child_doc = (
                                await self.config.mongo.async_db.blocks.find_one(
                                    {
                                        "index": {"$lt": self.index},
                                        "$or": child_or,
                                    },
                                    {"index": 1},
                                )
                            )
                            if child_doc:
                                already_extended = True
                        if already_extended:
                            raise Exception(
                                "KEL parent is not tip (second extension rejected): "
                                f"parent {prev_pkh} already extended"
                            )
                    elif txn.coinbase:
                        raise Exception(
                            "Coinbase prev_public_key_hash has no on-chain parent "
                            f"KEL entry: {prev_pkh}"
                        )

                if self.index >= CHAIN.CHECK_KEL_SPENDS_ENTIRELY_FORK:
                    await txn.verify_kel_output_rules(block=self)
                elif txn.are_kel_fields_populated():
                    if txn.public_key_hash in [output.to for output in txn.outputs]:
                        raise DoesNotSpendEntirelyToPrerotatedKeyHashException(
                            "Key event transactions must spent entire remaining balance to prerotated_key_hash."
                        )

                has_kel = await txn.has_key_event_log(block=self)
                if has_kel and not txn.are_kel_fields_populated():
                    raise KeyEventFieldsNotPopulatedException(
                        "Transaction has a KEL but key event fields are not populated."
                    )
                if not has_kel and txn.prev_public_key_hash:
                    # The parent KEL entry may live in a sibling transaction
                    # of this same in-progress block (common when an inception
                    # and its first rotation are mined together, or when a
                    # batch of rotations queue up in the mempool).  Treat the
                    # presence of a sibling whose prerotated_key_hash or
                    # twice_prerotated_key_hash matches this txn's address as
                    # a valid KEL ancestor so that block generation does not
                    # fatally exit on transient mempool ordering.
                    for sibling in self.transactions:
                        if sibling.transaction_signature == txn.transaction_signature:
                            continue
                        if (
                            sibling.prerotated_key_hash == txn.public_key_hash
                            or sibling.twice_prerotated_key_hash == txn.public_key_hash
                        ):
                            has_kel = True
                            break
                    if extra_blocks and not has_kel:
                        for extra_block in extra_blocks:
                            if (
                                getattr(extra_block, "index", None) is not None
                                and extra_block.index > self.index
                            ):
                                continue
                            for sibling in extra_block.transactions:
                                if (
                                    sibling.transaction_signature
                                    == txn.transaction_signature
                                ):
                                    continue
                                if (
                                    sibling.prerotated_key_hash == txn.public_key_hash
                                    or sibling.twice_prerotated_key_hash
                                    == txn.public_key_hash
                                ):
                                    has_kel = True
                                    break
                            if has_kel:
                                break

                if has_kel:
                    kel_hash_collection = await KELHashCollection.init_async(
                        self, verify_only=True
                    )
                    txn_key_event = KeyEvent(txn, status=KeyEventChainStatus.MEMPOOL)
                    await txn_key_event.verify(
                        batch_txns=self.transactions,
                        block_index=self.index,
                        extra_blocks=extra_blocks,
                    )
                    await KeyEventLog.init_async(
                        txn_key_event,
                        kel_hash_collection,
                        block_index=self.index,
                        batch_txns=self.transactions,
                        use_mempool=False,
                        extra_blocks=extra_blocks,
                    )
                elif isinstance(txn.relationship, (RecoveryProof, RecoveryTransition)):
                    # A recovers-inception is signed by a brand-new K_0 whose signing
                    # key has no prior KEL — has_key_event_log returns False and the
                    # sibling-match heuristic also finds nothing.  But it carries
                    # prev_public_key_hash pointing at the lost KEL's tip and embeds
                    # the Schnorr proof that authorises the delegation.  Route it
                    # through the same pipeline; KeyEventLog.init_async has its own
                    # recovers short-circuit that calls verify_recovery_inception().
                    kel_hash_collection = await KELHashCollection.init_async(
                        self, verify_only=True
                    )
                    txn_key_event = KeyEvent(txn, status=KeyEventChainStatus.MEMPOOL)
                    await txn_key_event.verify(
                        batch_txns=self.transactions, block_index=self.index
                    )
                    await KeyEventLog.init_async(
                        txn_key_event,
                        kel_hash_collection,
                        block_index=self.index,
                        batch_txns=self.transactions,
                        use_mempool=False,
                        extra_blocks=extra_blocks,
                    )
                elif txn.prev_public_key_hash:
                    raise KELExceptionPreviousKeyHashReferenceMissing(
                        f"Key event claims to have a key event log by specifying prev_public_key_hash, but no key event log found. ({txn.prev_public_key_hash})"
                    )

            if txn.coinbase:
                if self.index >= CHAIN.PAY_MASTER_NODES_FORK:
                    # Miner share may be paid to the block public_key address
                    # and/or the coinbase KEL prerotated_key_hash (KEL rotation
                    # pays to the next key while the block is still signed by
                    # the current key).  Count either as miner share so the
                    # 90/10 split verifies.  All other coinbase outputs count
                    # as masternode payments; fee/reward totals are still
                    # enforced below.
                    miner_targets = {address}
                    if txn.prerotated_key_hash:
                        miner_targets.add(txn.prerotated_key_hash)
                    for output in txn.outputs:
                        if float(output.value) < 0:
                            raise Exception("Coinbase output value cannot be negative")
                        if output.to in miner_targets:
                            coinbase_sum += float(output.value)
                        else:
                            if output.to not in masternode_sums:
                                masternode_sums[output.to] = 0
                            masternode_sums[output.to] += output.value
                else:
                    for output in txn.outputs:
                        if float(output.value) < 0:
                            raise Exception("Coinbase output value cannot be negative")
                        coinbase_sum += float(output.value)
            elif await txn.contract_generated:
                if self.index >= CHAIN.TXN_V3_FORK_CHECK_MINER_SIGNATURE:
                    result = verify_signature(
                        base64.b64decode(txn.miner_signature),
                        hashlib.sha256(txn.transaction_signature.encode())
                        .hexdigest()
                        .encode(),
                        bytes.fromhex(self.public_key),
                    )
                    if not result:
                        raise Exception("block signature1 is invalid")
                    contract_txn = await txn.get_generating_contract()
                    await contract_txn.relationship.verify_generation(
                        self,
                        txn,
                        [
                            x
                            for x in self.transactions
                            if x.transaction_signature != txn.transaction_signature
                        ],
                    )
                fee_sum += float(txn.fee)
                if self.index >= CHAIN.CHECK_MASTERNODE_FEE_FORK:
                    masternode_fee_sum += float(txn.masternode_fee)
            else:
                if not txn.inputs and any(float(o.value) > 0 for o in txn.outputs):
                    raise Exception(
                        "Non-coinbase transaction with no inputs and non-zero outputs is not allowed"
                    )
                fee_sum += float(txn.fee)
                if self.index >= CHAIN.CHECK_MASTERNODE_FEE_FORK:
                    masternode_fee_sum += float(txn.masternode_fee)

            if (
                self.index >= CHAIN.XEGGEX_HACK_FORK
                and self.index < CHAIN.CHECK_KEL_FORK
            ) or (self.index >= CHAIN.XEGGEX_HACK_FORK_2):
                if (
                    txn.public_key
                    == "02fd3ad0e7a613672d9927336d511916e15c507a1fab225ed048579e9880f15fed"
                ):
                    raise XeggexAccountFrozenException("Xeggex wallet has been frozen.")

                for output in txn.outputs:
                    if output.to == "1Kh8tcPNxJsDH4KJx4TzLbqWwihDfhFpzj":
                        raise XeggexAccountFrozenException(
                            "Xeggex wallet has been frozen."
                        )

        reward = CHAIN.get_block_reward(self.index)

        # if Decimal(str(fee_sum)[:10]) != Decimal(str(coinbase_sum)[:10]) - Decimal(str(reward)[:10]):
        """
        KO for block 13949
        0.02099999 50.021 50.0
        Integrate block error 1 ('Coinbase output total does not equal block reward + transaction fees', 0.020999999999999998, 0.021000000000000796)
        """

        if self.index >= CHAIN.CHECK_MASTERNODE_FEE_FORK:
            masternode_sum = sum(x for x in masternode_sums.values())

            if quantize_eight(fee_sum + masternode_fee_sum) != quantize_eight(
                (coinbase_sum + masternode_sum) - reward
            ):
                if (
                    quantize_eight(coinbase_sum - fee_sum)
                    == quantize_eight(reward * 0.9)
                    and masternode_sum
                    == 0  # there was a bug where the block reward was still 90% for the miner even if no masternodes were present
                ):
                    return
                raise TotalValueMismatchException(
                    "Masternode output totals do not equal block reward + masternode transaction fees",
                    float(quantize_eight(fee_sum + masternode_fee_sum)),
                    float(quantize_eight((coinbase_sum + masternode_sum) - reward)),
                )

        elif self.index >= CHAIN.PAY_MASTER_NODES_FORK:
            masternode_sum = sum(x for x in masternode_sums.values())
            if quantize_eight(fee_sum) != quantize_eight(
                (coinbase_sum + masternode_sum) - reward
            ):
                raise TotalValueMismatchException(
                    "Coinbase output total does not equal block reward + transaction fees",
                    fee_sum,
                    (coinbase_sum - reward),
                )

        else:
            if quantize_eight(fee_sum) != quantize_eight(coinbase_sum - reward):
                raise TotalValueMismatchException(
                    "Coinbase output total does not equal block reward + transaction fees",
                    fee_sum,
                    (coinbase_sum - reward),
                )

    def verify_signature(self, address):
        try:
            result = verify_signature(
                base64.b64decode(self.signature),
                self.hash.encode("utf-8"),
                bytes.fromhex(self.public_key),
            )
            if not result:
                raise Exception("block signature1 is invalid")
        except Exception:  # pragma: no cover
            try:
                result = VerifyMessage(
                    address,
                    BitcoinMessage(self.hash.encode("utf-8"), magic=""),
                    self.signature,
                )
                if not result:
                    raise
            except Exception:
                raise Exception("block signature2 is invalid")

    def get_transaction_hashes(self):
        """Returns a sorted list of tx hash, so the merkle root is constant across nodes"""
        return sorted([str(x.hash) for x in self.transactions], key=str.lower)

    async def save(self):
        await self.verify()
        try:
            await Block.ensure_kel_tags(self.transactions)
        except Exception as exc:
            raise Exception(
                "Block.save: ensure_kel_tags failed at height {}: {}".format(
                    self.index, exc
                )
            ) from exc
        used_block_inputs = {}
        used_block_inputs_by_id = {}
        for txn in self.transactions:
            if txn.inputs:
                failed = False
                input_ids = []
                spender_inc = getattr(txn, "inception_public_key_hash", None)
                for x in txn.inputs:
                    if (x.id, txn.public_key) in used_block_inputs:
                        failed = True
                    elif x.id in used_block_inputs_by_id:
                        from yadacoin.core.keyeventlog import KeyEventLog

                        prior_pk, prior_inc = used_block_inputs_by_id[x.id]
                        try:
                            if await KeyEventLog.kel_spend_conflict(
                                txn.public_key,
                                prior_pk,
                                inception_a=spender_inc,
                                inception_b=prior_inc,
                                onchain_only=True,
                            ):
                                failed = True
                        except Exception:
                            # Fail closed: cannot prove distinct KELs.
                            failed = True
                    used_block_inputs[(x.id, txn.public_key)] = txn
                    used_block_inputs_by_id[x.id] = (txn.public_key, spender_inc)
                    input_ids.append(x.id)
                is_input_spent = await yadacoin.core.config.CONFIG.BU.is_input_spent(
                    input_ids,
                    txn.public_key,
                    spender_inception=spender_inc,
                )
                if is_input_spent:
                    failed = True
                if len(input_ids) != len(set(input_ids)):
                    failed = True
                if failed:
                    raise Exception("double spend", [x.id for x in txn.inputs])
        res = await self.config.mongo.async_db.blocks.find_one(
            {"index": (int(self.index) - 1)}
        )
        if (res and res["hash"] == self.prev_hash) or self.index == 0:
            await self.config.mongo.async_db.blocks.replace_one(
                {"index": self.index}, self.to_dict(), upsert=True
            )
        else:
            raise Exception(
                "Block rejected: prev_hash {} does not match previous block hash {}".format(
                    self.prev_hash, res["hash"] if res else "no previous block found"
                )
            )

    def to_dict(self):
        try:
            return {
                "version": self.version,
                "time": int(self.time),
                "index": self.index,
                "public_key": self.public_key,
                "prevHash": self.prev_hash,
                "nonce": self.nonce,
                "transactions": [x.to_dict() for x in self.transactions],
                "hash": self.hash,
                "merkleRoot": self.merkle_root,
                "special_min": self.special_min,
                "target": hex(self.target)[2:].rjust(64, "0"),
                "special_target": hex(self.special_target)[2:].rjust(64, "0"),
                "header": self.header,
                "id": self.signature,
            }
        except Exception as e:
            print(e)
            print("target", self.target, "spec", self.special_target)

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)

    def in_the_future(self):
        """Tells wether the block is too far away in the future"""
        return int(self.time) > time.time() + CHAIN.TIME_TOLERANCE
