"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64
import hashlib
import json
import time
from enum import Enum
from logging import getLogger
from traceback import format_exc

from bitcoin.signmessage import BitcoinMessage, VerifyMessage
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import verify_signature
from ecdsa import SECP256k1, VerifyingKey
from ecdsa.util import sigdecode_der

from yadacoin.core.agentannouncement import AgentAnnouncement
from yadacoin.core.chain import CHAIN
from yadacoin.core.collections import Collections
from yadacoin.core.config import Config
from yadacoin.core.contenttakedown import ContentTakedownAnnouncement
from yadacoin.core.credentialreceipt import CredentialReceipt
from yadacoin.core.identityannouncement import IdentityAnnouncement
from yadacoin.core.nodeannouncement import NodeAnnouncement
from yadacoin.core.recoveryannouncement import (
    RecoveryAnnouncement,
    RecoveryProof,
    RecoveryTransition,
)
from yadacoin.core.rotationannouncement import RotationAnnouncement


def equal(a, b, epsilon=5e-9):
    return abs(a - b) < epsilon


class TransactionAddressInvalidException(Exception):
    pass


class InvalidTransactionException(Exception):
    pass


class InvalidTransactionSignatureException(Exception):
    pass


class MissingInputTransactionException(Exception):
    pass


class NotEnoughMoneyException(Exception):
    pass


class MaxRelationshipSizeExceeded(Exception):
    pass


class TransactionInputOutputMismatchException(Exception):
    pass


class TotalValueMismatchException(Exception):
    pass


class InvalidRelationshipHashException(Exception):
    pass


class TooManyInputsException(Exception):
    pass


class TransactionConsts(Enum):
    RELATIONSHIP_MAX_SIZE = 20480


class Transaction(object):
    def __init__(
        self,
        txn_time=0,
        rid="",
        transaction_signature="",
        relationship="",
        public_key="",
        dh_public_key="",
        fee=0.0,
        requester_rid="",
        requested_rid="",
        txn_hash="",
        inputs="",
        outputs="",
        coinbase=False,
        extra_blocks=None,
        seed_gateway_rid="",
        seed_rid="",
        version=None,
        miner_signature="",
        contract_generated=None,
        relationship_hash="",
        never_expire=False,
        private=False,
        masternode_fee=0.0,
        exact_match=False,
        prerotated_key_hash="",
        twice_prerotated_key_hash="",
        public_key_hash="",
        prev_public_key_hash="",
        spent_in_txn="",
    ):
        self.app_log = getLogger("tornado.application")
        self.config = Config()
        self.mongo = self.config.mongo
        if not txn_time:
            txn_time = 0
        self.time = txn_time if isinstance(txn_time, int) else int(txn_time)
        self.rid = rid
        self.transaction_signature = transaction_signature
        self.relationship = relationship
        self.relationship_hash = relationship_hash
        self.public_key = public_key
        self.dh_public_key = dh_public_key if dh_public_key else ""
        self.fee = float(fee)
        if self.fee < 0:
            raise InvalidTransactionException("fee cannot be negative")
        self.masternode_fee = float(masternode_fee)
        if self.masternode_fee < 0:
            raise InvalidTransactionException("masternode_fee cannot be negative")
        self.requester_rid = requester_rid if requester_rid else ""
        self.requested_rid = requested_rid if requested_rid else ""
        self.hash = txn_hash
        self.outputs = []
        self.extra_blocks = extra_blocks or []
        self.seed_gateway_rid = seed_gateway_rid
        self.seed_rid = seed_rid

        if version:
            self.version = version
        else:
            self.version = 1
            if self.time:
                self.version = 2

        if (
            isinstance(self.relationship, dict)
            and Collections.SMART_CONTRACT.value in self.relationship
        ):
            from yadacoin.contracts.base import Contract

            self.relationship = Contract.from_dict(
                self.relationship[Collections.SMART_CONTRACT.value]
            )
        elif (
            isinstance(self.relationship, dict)
            and NodeAnnouncement.RELATIONSHIP_KEY in self.relationship
        ):
            # Convert node announcement dict to NodeAnnouncement instance
            self.relationship = NodeAnnouncement.from_dict(
                self.relationship[NodeAnnouncement.RELATIONSHIP_KEY]
            )
        elif (
            isinstance(self.relationship, dict)
            and IdentityAnnouncement.RELATIONSHIP_KEY in self.relationship
        ):
            # Convert identity announcement dict to IdentityAnnouncement instance
            self.relationship = IdentityAnnouncement.from_dict(
                self.relationship[IdentityAnnouncement.RELATIONSHIP_KEY]
            )
        elif (
            isinstance(self.relationship, dict)
            and RotationAnnouncement.RELATIONSHIP_KEY in self.relationship
        ):
            # Rotation-only (subsequent rotations for secp256r1 nodes — no identity)
            self.relationship = RotationAnnouncement.from_dict(
                self.relationship[RotationAnnouncement.RELATIONSHIP_KEY]
            )
        elif (
            isinstance(self.relationship, dict)
            and AgentAnnouncement.RELATIONSHIP_KEY in self.relationship
        ):
            # Convert agent registration dict to AgentAnnouncement instance
            self.relationship = AgentAnnouncement.from_dict(
                self.relationship[AgentAnnouncement.RELATIONSHIP_KEY]
            )
        elif (
            isinstance(self.relationship, dict)
            and ContentTakedownAnnouncement.RELATIONSHIP_KEY in self.relationship
        ):
            # Convert content takedown dict to ContentTakedownAnnouncement instance
            self.relationship = ContentTakedownAnnouncement.from_relationship(
                self.relationship
            )
        elif (
            isinstance(self.relationship, dict)
            and RecoveryAnnouncement.RELATIONSHIP_KEY in self.relationship
            and RecoveryProof.RELATIONSHIP_KEY in self.relationship
        ):
            # Combined recovers-inception proof + new recovery announcement.
            # The dict carries both keys — detect this BEFORE the individual
            # 'recovery' and 'recovers' branches so neither eats the combined
            # form prematurely.
            self.relationship = RecoveryTransition.from_relationship(self.relationship)
        elif (
            isinstance(self.relationship, dict)
            and RecoveryAnnouncement.RELATIONSHIP_KEY in self.relationship
        ):
            # Location-recovery announcement: {"recovery": <witness_hash_hex>}
            # embedded in a regular KEL rotation by the user's current key.
            # If the payload is malformed we leave the raw dict in place so
            # downstream KEL helpers (which isinstance-check for
            # RecoveryAnnouncement) treat it as a non-recovery txn rather
            # than crashing on garbage input.
            self.relationship = RecoveryAnnouncement.from_relationship(
                self.relationship
            )
        elif (
            isinstance(self.relationship, dict)
            and RecoveryProof.RELATIONSHIP_KEY in self.relationship
        ):
            # Recovers-inception proof: {"recovers": {commitment, R, s}}
            # carried by an inception-shaped txn whose prev_public_key_hash
            # points at the lost KEL's tip pkh.  Same tolerance as above.
            self.relationship = RecoveryProof.from_relationship(self.relationship)
        elif (
            isinstance(self.relationship, dict)
            and "credential_receipt" in self.relationship
        ):
            # Data-only encrypted VC receipt: {"credential_receipt": {lookup_key, iv, ct}}
            # Not a key event — no KEL rotation, no UTXO spend.  Silently
            # leave the raw dict in place on parse failure so the txn is
            # treated as a plain relationship by downstream code.
            self.relationship = CredentialReceipt.from_relationship(self.relationship)
        elif (
            isinstance(self.relationship, str)
            and len(self.relationship) > TransactionConsts.RELATIONSHIP_MAX_SIZE.value
        ):
            raise MaxRelationshipSizeExceeded(
                f"Relationship field cannot be greater than {TransactionConsts.RELATIONSHIP_MAX_SIZE.value} bytes"
            )

        for x in outputs:
            if not isinstance(x, Output):
                x = Output.from_dict(x)
            self.outputs.append(x)

        self.inputs = []
        for x in inputs:
            if not isinstance(x, Input):
                x = Input.from_dict(x)
            self.inputs.append(x)

        self.coinbase = coinbase
        self.miner_signature = miner_signature
        self.contract_generated = contract_generated
        self.never_expire = never_expire
        self.private = private
        self.exact_match = exact_match
        self.prerotated_key_hash = prerotated_key_hash
        self.twice_prerotated_key_hash = twice_prerotated_key_hash
        self.public_key_hash = public_key_hash
        self.prev_public_key_hash = prev_public_key_hash
        self.spent_in_txn = spent_in_txn

    @classmethod
    async def generate(
        cls,
        username_signature="",
        username="",
        value=0,
        fee=0.0,
        rid="",
        requester_rid="",
        requested_rid="",
        public_key="",
        dh_public_key="",
        private_key="",
        dh_private_key="",
        to="",
        inputs="",
        outputs="",
        coinbase=False,
        chattext=None,
        signin=None,
        relationship="",
        no_relationship=False,
        exact_match=False,
        version=7,
        miner_signature="",
        contract_generated=None,
        do_money=True,
        never_expire=False,
        private=False,
        masternode_fee=0.0,
        prerotated_key_hash="",
        twice_prerotated_key_hash="",
        public_key_hash="",
        prev_public_key_hash="",
    ):
        cls_inst = cls()
        cls_inst.config = Config()
        cls_inst.mongo = cls_inst.config.mongo
        cls_inst.app_log = getLogger("tornado.application")
        cls_inst.username_signature = username_signature
        cls_inst.username = username
        cls_inst.rid = rid
        cls_inst.requester_rid = requester_rid
        cls_inst.requested_rid = requested_rid
        cls_inst.dh_public_key = dh_public_key
        cls_inst.value = value
        cls_inst.fee = float(fee)
        cls_inst.masternode_fee = float(masternode_fee)
        cls_inst.dh_private_key = dh_private_key
        cls_inst.to = to
        cls_inst.time = int(time.time())
        cls_inst.outputs = []
        cls_inst.relationship = relationship
        cls_inst.relationship_hash = (
            (hashlib.sha256(relationship.encode()).digest().hex())
            if relationship
            else ""
        )
        cls_inst.no_relationship = no_relationship
        cls_inst.exact_match = exact_match
        cls_inst.version = version
        cls_inst.miner_signature = miner_signature

        for x in outputs:
            if isinstance(x, Output):
                out = x
            else:
                out = Output.from_dict(x)
            cls_inst.outputs.append(out)

        cls_inst.inputs = []
        for x in inputs:
            if isinstance(x, Input):
                inp = x
            else:
                inp = Input.from_dict(x)
            cls_inst.inputs.append(inp)

        cls_inst.coinbase = coinbase
        cls_inst.contract_generated = contract_generated

        await cls_inst.do_money()

        cls_inst.public_key = public_key

        cls_inst.never_expire = never_expire
        cls_inst.private = private
        cls_inst.prerotated_key_hash = prerotated_key_hash
        cls_inst.twice_prerotated_key_hash = twice_prerotated_key_hash
        cls_inst.public_key_hash = public_key_hash
        cls_inst.prev_public_key_hash = prev_public_key_hash
        return cls_inst

    async def do_money(self):
        if self.coinbase:
            self.inputs = []
            return

        outputs_and_fee_total = sum([x.value for x in self.outputs]) + self.fee
        if outputs_and_fee_total == 0:
            return

        my_address = str(
            P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key))
        )

        input_sum = 0
        inputs = []
        if self.inputs:
            input_sum = await self.evaluate_inputs(  # pragma: no cover
                input_sum, my_address, inputs, outputs_and_fee_total
            )
        else:
            input_sum = await self.generate_inputs(  # pragma: no cover
                input_sum,
                my_address,
                inputs,
                outputs_and_fee_total,
            )

        self.inputs = inputs

        if not self.inputs and not self.coinbase and outputs_and_fee_total > 0:
            raise NotEnoughMoneyException(
                "No inputs, not a coinbase, and transaction amount is greater than zero"
            )

        remainder = input_sum - outputs_and_fee_total
        if equal(remainder, 0):
            remainder = 0.0

        found = False
        for x in self.outputs:
            if my_address == x.to:
                found = True
                x.value += remainder

        if not found:
            return_change_output = Output(to=my_address, value=remainder)
            self.outputs.append(return_change_output)

    async def evaluate_inputs(
        self, input_sum, my_address, inputs, outputs_and_fee_total
    ):
        async for y in self.get_inputs(self.inputs):
            txn = await self.config.BU.get_transaction_by_id(y.id, instance=True)
            if not txn:
                raise MissingInputTransactionException()

            address = my_address

            input_sum = await self.sum_inputs(
                y, txn, address, input_sum, inputs, outputs_and_fee_total
            )
            if input_sum > outputs_and_fee_total or equal(
                input_sum, outputs_and_fee_total
            ):
                return input_sum

        raise NotEnoughMoneyException("not enough money")

    async def generate_inputs(
        self, input_sum, my_address, inputs, outputs_and_fee_total
    ):
        async for (
            input_txn
        ) in self.config.BU.get_wallet_unspent_transactions_for_spending(
            my_address, inc_mempool=True
        ):
            txn = await self.config.BU.get_transaction_by_id(
                input_txn["id"], instance=True
            )
            input_sum = await self.sum_inputs(
                Input.from_dict(txn.to_dict()),
                txn,
                my_address,
                input_sum,
                inputs,
                outputs_and_fee_total,
            )
            if input_sum > outputs_and_fee_total or equal(
                input_sum, outputs_and_fee_total
            ):
                return input_sum

        raise NotEnoughMoneyException("not enough money")

    async def sum_inputs(
        self, input_obj, input_txn, my_address, input_sum, inputs, outputs_and_fee_total
    ):
        address = my_address

        for txn_output in input_txn.outputs:
            if txn_output.to == address and float(txn_output.value) > 0.0:
                if self.exact_match and not equal(
                    txn_output.value, outputs_and_fee_total
                ):
                    continue
                input_sum += txn_output.value

                if input_txn not in inputs:
                    inputs.append(input_obj)

                if input_sum > outputs_and_fee_total or equal(
                    input_sum, outputs_and_fee_total
                ):
                    return input_sum
        return input_sum

    @classmethod
    def from_dict(cls, txn):
        return cls(
            txn_time=txn.get("time"),
            transaction_signature=txn.get("id"),
            rid=txn.get("rid", ""),
            relationship=txn.get("relationship", ""),
            public_key=txn.get("public_key"),
            dh_public_key=txn.get("dh_public_key"),
            fee=float(txn.get("fee", 0)),
            requester_rid=txn.get("requester_rid", ""),
            requested_rid=txn.get("requested_rid", ""),
            txn_hash=txn.get("hash", ""),
            inputs=txn.get("inputs", []),
            outputs=txn.get("outputs", []),
            coinbase=False,  # Never trust external coinbase flag; Block.init_async recomputes it via Block.is_coinbase()
            version=txn.get("version"),
            miner_signature=txn.get("miner_signature", ""),
            contract_generated=txn.get("contract_generated"),
            relationship_hash=txn.get("relationship_hash", ""),
            private=txn.get("private", False),
            never_expire=txn.get("never_expire", False),
            masternode_fee=float(txn.get("masternode_fee", 0)),
            prerotated_key_hash=txn.get("prerotated_key_hash", ""),
            twice_prerotated_key_hash=txn.get("twice_prerotated_key_hash", ""),
            public_key_hash=txn.get("public_key_hash", ""),
            prev_public_key_hash=txn.get("prev_public_key_hash", ""),
            spent_in_txn=txn.get("spent_in_txn", ""),
        )

    def in_the_future(self):
        """Tells whether the transaction is too far away in the future"""
        return int(self.time) > time.time() + CHAIN.TIME_TOLERANCE

    async def get_inputs(self, inputs):
        for x in inputs:
            yield x

    @property
    async def contract_generated(self):
        if self._contract_generated is None:
            if await self.get_generating_contract():
                self._contract_generated = True
            else:
                self._contract_generated = False
        return self._contract_generated

    @contract_generated.setter
    def contract_generated(self, value):
        self._contract_generated = value

    async def get_generating_contract(self):
        from yadacoin.contracts.base import Contract

        smart_contract_txn_block = await self.config.mongo.async_db.blocks.find_one(
            {
                "transactions.relationship.smart_contract.identity.public_key": self.public_key
            },
            sort=[("time", 1)],
        )
        if not smart_contract_txn_block:
            return
        for txn in smart_contract_txn_block.get("transactions"):  # pragma: no cover
            txn_obj = Transaction.from_dict(txn)
            if (
                isinstance(txn_obj.relationship, Contract)
                and txn_obj.relationship.identity.public_key == self.public_key
            ):
                return txn_obj

    @staticmethod
    def ensure_instance(txn):
        if isinstance(txn, Transaction):
            return txn
        else:
            return Transaction.from_dict(txn)

    @staticmethod
    async def handle_exception(e, txn, transactions=None):
        if transactions is None:
            transactions = []
        if isinstance(e, TooManyInputsException):
            txn.inputs = []
        config = Config()
        await config.mongo.async_db.failed_transactions.insert_one(
            {
                "reason": f"{e.__class__.__name__}",
                "txn": txn.to_dict(),
                "error": format_exc(),
            }
        )
        await config.mongo.async_db.miner_transactions.delete_many(
            {"id": txn.transaction_signature}
        )
        config.app_log.warning("Exception {}".format(e))

        if txn.spent_in_txn:
            if txn.spent_in_txn in transactions:
                transactions.remove(txn.spent_in_txn)
            await config.mongo.async_db.miner_transactions.delete_many(
                {"id": txn.spent_in_txn.transaction_signature}
            )

    def verify_signature(self, address, hash_value=None):
        hash_bytes = (hash_value if hash_value is not None else self.hash).encode(
            "utf-8"
        )
        try:
            result = verify_signature(
                base64.b64decode(self.transaction_signature),
                hash_bytes,
                bytes.fromhex(self.public_key),
            )
            if not result:
                raise Exception()
        except Exception:
            try:
                vk = VerifyingKey.from_string(
                    bytes.fromhex(self.public_key), curve=SECP256k1
                )
                result = vk.verify(
                    base64.b64decode(self.transaction_signature),
                    hash_bytes,
                    hashlib.sha256,
                    sigdecode=sigdecode_der,
                )
                if not result:
                    raise Exception()
            except Exception:
                try:
                    result = VerifyMessage(
                        address,
                        BitcoinMessage(
                            hash_value if hash_value is not None else self.hash,
                            magic="",
                        ),
                        self.transaction_signature,
                    )
                    if not result:
                        raise
                except Exception:
                    raise InvalidTransactionSignatureException(
                        "transaction signature did not verify"
                    )

    async def verify(
        self,
        check_input_spent=False,
        check_max_inputs=False,
        check_masternode_fee=False,
        check_kel=False,
        check_dynamic_nodes=False,
        check_agent_registration=False,
        check_content_takedown=False,
        block=None,
        mempool=False,
        batch_txns=None,
    ):
        from yadacoin.contracts.base import Contract
        from yadacoin.core.keyeventlog import (
            KELExceptionPreviousKeyHashReferenceMissing,
        )

        if check_max_inputs and len(self.inputs) > CHAIN.MAX_INPUTS:
            raise TooManyInputsException(
                f"Maximum inputs of {CHAIN.MAX_INPUTS} exceeded."
            )

        verify_hash = await self.generate_hash()
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))

        # Reused by both verify_kel_output_rules and get_kel_cross_key_auth so
        # the KEL chain is not rebuilt twice in the same verify() call.  It is
        # populated lazily only when KEL spend rules apply (inside check_kel).
        key_log = None

        if check_kel:
            from yadacoin.core.keyeventlog import KeyEvent

            has_kel = False
            if isinstance(self.relationship, CredentialReceipt):
                # Data-only receipt: no KEL rotation, no UTXO spend.  Only
                # enforce the "no funds" invariant to prevent misuse as a
                # covert value-transfer vehicle.
                if self.inputs or any(float(o.value) > 0 for o in self.outputs):
                    raise InvalidTransactionException(
                        "CredentialReceipt transactions must not include "
                        "inputs or value-bearing outputs."
                    )
            else:
                has_kel = await self.has_key_event_log(
                    block, mempool, include_offchain=True
                )
                # If the on-chain (or mempool) check didn't find a parent,
                # also check batch_txns — the parent may be a sibling in the
                # block currently being assembled (e.g. inception + confirming
                # in the same block).  This mirrors the sibling-lookup in
                # Block.verify() and is needed when validate_transactions is
                # called with mempool=False (block proxy) so that legitimate
                # same-block KEL pairs are not incorrectly excluded.
                if not has_kel and batch_txns:
                    # address is already computed above — reuse it.
                    # Build a lookup set for O(1) per-entry checks.
                    _batch_prerotated = {
                        t.prerotated_key_hash
                        for t in batch_txns
                        if t.transaction_signature != self.transaction_signature
                    }
                    _batch_twice = {
                        t.twice_prerotated_key_hash
                        for t in batch_txns
                        if t.transaction_signature != self.transaction_signature
                    }
                    has_kel = address in _batch_prerotated or address in _batch_twice

            if has_kel:
                txn_key_event = KeyEvent(self)
                await txn_key_event.verify(
                    batch_txns=batch_txns,
                    block_index=block.index if block is not None else None,
                    use_mempool=mempool,
                )
            elif isinstance(self.relationship, (RecoveryProof, RecoveryTransition)):
                # A recovers-inception is signed by a brand-new K_0, so the
                # signing key has no prior KEL of its own — has_key_event_log
                # therefore returns False.  But it carries
                # prev_public_key_hash pointing at the LOST delegator KEL's
                # tip pkh and embeds the Schnorr proof that authorises the
                # delegation.  Route it through KeyEvent.verify so
                # KeyEventLog.init_async dispatches to
                # verify_recovery_inception, which validates the ZKP against
                # the on-chain {"recovery": <witness_hash>} announcement.
                txn_key_event = KeyEvent(self)
                await txn_key_event.verify(
                    batch_txns=batch_txns,
                    block_index=block.index if block is not None else None,
                    use_mempool=mempool,
                )
            elif self.prev_public_key_hash and (
                block is None or block.index >= CHAIN.CHECK_KEL_PREV_HASH_FORK
            ):
                raise KELExceptionPreviousKeyHashReferenceMissing(
                    "Key event claims to have a key event log by specifying prev_public_key_hash, but no key event log found.",
                    txn=self,
                )

            if has_kel:
                if block is not None:
                    _kel_index = block.index
                elif mempool:
                    _kel_index = self.config.LatestBlock.block.index + 1
                else:
                    _kel_index = self.config.LatestBlock.block.index

                if _kel_index >= CHAIN.CHECK_KEL_SPENDS_ENTIRELY_FORK:
                    from yadacoin.core.keyeventlog import KeyEventLog

                    # Build the KEL once and reuse it for both output-rule
                    # enforcement and cross-key spend authorization below,
                    # instead of rebuilding the chain twice.  Block verification
                    # must never trust the cache (use_cache=False); the mempool
                    # path may cache for the next lookup of the same key.
                    key_log = await KeyEventLog.build_from_public_key(
                        self.public_key,
                        onchain_only=(block is not None),
                        use_cache=(block is None),
                    )
                    await self.verify_kel_output_rules(
                        block=block, mempool=mempool, key_log=key_log
                    )

        if verify_hash != self.hash:
            raise InvalidTransactionException(
                f"transaction is invalid - {verify_hash} - {self.hash}"
            )

        self.verify_signature(address, hash_value=verify_hash)

        relationship = self.relationship
        if isinstance(self.relationship, Contract):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, NodeAnnouncement):
            relationship = self.relationship.to_string()
            if not check_dynamic_nodes:
                raise InvalidTransactionException(
                    f"Node announcement transactions (version 7) not allowed before fork height {CHAIN.DYNAMIC_NODES_FORK}"
                )
            # Verify collateral output: must have an output of exactly COLLATERAL_AMOUNT to collateral_address
            collateral_address = self.relationship.collateral_address
            if not collateral_address:
                raise InvalidTransactionException(
                    "Node announcement transaction missing collateral_address"
                )
            collateral_outputs = [
                o
                for o in self.outputs
                if o.to == collateral_address
                and float(o.value) == float(CHAIN.DYNAMIC_NODES_COLLATERAL_AMOUNT)
            ]
            if not collateral_outputs:
                raise InvalidTransactionException(
                    f"Node announcement transaction must include an output of {CHAIN.DYNAMIC_NODES_COLLATERAL_AMOUNT} YDA to collateral_address {collateral_address}"
                )
        elif isinstance(self.relationship, AgentAnnouncement):
            relationship = self.relationship.to_string()
            if not check_agent_registration:
                raise InvalidTransactionException(
                    f"Agent registration transactions not allowed before fork height {CHAIN.AGENT_REGISTRY_FORK}"
                )
            if not self.relationship.endpoint_url:
                raise InvalidTransactionException(
                    "Agent registration transaction missing endpoint_url"
                )
        elif isinstance(self.relationship, IdentityAnnouncement):
            relationship = self.relationship.to_string()
            await self.relationship.verify(
                self.public_key, exclude_txn_sig=self.transaction_signature
            )
        elif isinstance(self.relationship, RotationAnnouncement):
            relationship = self.relationship.to_string()
            # Rotation-only announcements must NOT be inception transactions
            if not self.prev_public_key_hash:
                raise InvalidTransactionException(
                    "Rotation announcement without 'identity' is only valid for subsequent rotations, "
                    "not inception (prev_public_key_hash is empty)"
                )
            # Validate P-256 key consistency for secp256r1 rotations
            if self.relationship.curve == "secp256r1":
                try:
                    self.relationship.validate_p256()
                except ValueError as exc:
                    raise InvalidTransactionException(
                        f"Rotation announcement: invalid P-256 key — {exc}"
                    )
        elif isinstance(self.relationship, ContentTakedownAnnouncement):
            relationship = self.relationship.to_string()
            if not check_content_takedown:
                raise InvalidTransactionException(
                    f"Content takedown transactions not allowed before fork height {CHAIN.CONTENT_TAKEDOWN_FORK}"
                )
            if self.fee <= 0.0:
                raise InvalidTransactionException(
                    "Content takedown transaction must include a non-zero fee"
                )
        elif isinstance(
            self.relationship, (RecoveryAnnouncement, RecoveryProof, RecoveryTransition)
        ):
            # Location-recovery announcements / recovers-inception proofs are
            # validated structurally by the KEL pipeline (see
            # KeyEvent.verify_recovery_inception); here we just normalise the
            # relationship to its hash preimage so the size guard below works.
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, CredentialReceipt):
            relationship = self.relationship.to_string()

        if len(relationship) > TransactionConsts.RELATIONSHIP_MAX_SIZE.value:
            raise MaxRelationshipSizeExceeded(
                f"Relationship field cannot be greater than {TransactionConsts.RELATIONSHIP_MAX_SIZE.value} bytes"
            )
        # verify spend
        total_input = 0
        exclude_recovered_ids = []

        # KEL cross-key spending: if the signer is the latest KEL key its
        # address equals kel[-1].prerotated_key_hash, and it is authorised to
        # spend UTXOs locked to any previous KEL address.
        kel_authorized_addresses, kel_authorized_pub_keys = (
            await self.get_kel_cross_key_auth(
                address, block=block, mempool=mempool, key_log=key_log
            )
            if self.inputs
            else (None, None)
        )

        async for txn in self.get_inputs(self.inputs):
            txn_input = None
            if txn.input_txn:
                input_txn = txn.input_txn
                txn_input = txn.input_txn
            else:
                input_txn = await self.config.BU.get_transaction_by_id(txn.id)

                if input_txn:
                    txn_input = Transaction.from_dict(input_txn)

            if not input_txn:
                if self.extra_blocks:
                    txn_input = await self.find_in_extra_blocks(txn)
                if not txn_input:
                    result = await self.recover_missing_transaction(
                        txn.id, exclude_recovered_ids
                    )
                    exclude_recovered_ids.append(exclude_recovered_ids)
                    raise MissingInputTransactionException(
                        "Input not found on blockchain: {}".format(txn.id)
                    )

            if check_input_spent:
                is_input_spent = await self.config.BU.is_input_spent(
                    txn_input.transaction_signature,
                    self.public_key,
                    from_index=(
                        self.extra_blocks[0].index
                        if self.extra_blocks
                        else self.config.LatestBlock.block.index
                    ),
                    extra_public_keys=(
                        kel_authorized_pub_keys - {self.public_key}
                        if kel_authorized_pub_keys
                        else None
                    ),
                )
                if is_input_spent:
                    raise Exception("Input already spent")

            found = False
            for output in txn_input.outputs:
                if kel_authorized_addresses is not None:
                    if str(output.to) in kel_authorized_addresses:
                        found = True
                        total_input += float(output.value)
                elif str(output.to) == str(address):
                    found = True
                    total_input += float(output.value)

            if not found:
                raise InvalidTransactionException(
                    "using inputs from a transaction where you were not one of the recipients."
                )

        if self.coinbase:
            return
        # Only skip input/output balance validation for contract-generated
        # transactions before the smart-contract removal fork.  After that
        # fork, contract_generated transactions are rejected at the block
        # level, so reaching this branch with a post-fork index would
        # indicate a logic error.  Keeping the guard prevents the bypass
        # from being abused after smart contracts have been disabled.
        if block is not None:
            current_index = block.index
        else:
            latest = getattr(self.config, "LatestBlock", None)
            current_index = latest.block.index if latest and latest.block else 0
        if (
            self.miner_signature
            and await self.contract_generated
            and current_index < CHAIN.SMART_CONTRACT_REMOVAL_FORK
        ):
            return

        total_output = 0
        for txn in self.outputs:
            if float(txn.value) < 0:
                raise InvalidTransactionException("Output value cannot be negative")
            total_output += float(txn.value)
        if check_masternode_fee:
            total = float(total_output) + float(self.fee) + float(self.masternode_fee)
            if not equal(total_input, total):
                raise TotalValueMismatchException(
                    "inputs and outputs sum must match %s, %s, %s, %s, %s"
                    % (
                        total_input,
                        float(total_output),
                        float(self.fee),
                        float(self.masternode_fee),
                        total,
                    )
                )
        else:
            total = float(total_output) + float(self.fee)
            if not equal(total_input, total):
                raise TotalValueMismatchException(
                    "inputs and outputs sum must match %s, %s, %s, %s"
                    % (
                        total_input,
                        float(total_output),
                        float(self.fee),
                        total,
                    )
                )

    async def generate_hash(self):
        from yadacoin.contracts.base import Contract

        inputs_concat = await self.get_input_hashes()
        outputs_concat = self.get_output_hashes()
        if isinstance(self.relationship, Contract):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, NodeAnnouncement):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, IdentityAnnouncement):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, RotationAnnouncement):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, AgentAnnouncement):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, ContentTakedownAnnouncement):
            relationship = self.relationship.to_string()
        elif isinstance(
            self.relationship, (RecoveryAnnouncement, RecoveryProof, RecoveryTransition)
        ):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, CredentialReceipt):
            relationship = self.relationship.to_string()
        else:
            relationship = self.relationship
        if self.version == 7:
            if relationship:
                relationship_hash = hashlib.sha256(relationship.encode()).digest().hex()
                if relationship_hash != self.relationship_hash:
                    raise InvalidRelationshipHashException()
            else:
                relationship_hash = self.relationship_hash
            hashout = (
                hashlib.sha256(
                    (
                        self.public_key
                        + str(self.time)
                        + self.dh_public_key
                        + self.rid
                        + relationship_hash
                        + "{0:.8f}".format(self.fee)
                        + "{0:.8f}".format(self.masternode_fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                        + str(self.version)
                        + self.prerotated_key_hash
                        + self.twice_prerotated_key_hash
                        + self.public_key_hash
                        + self.prev_public_key_hash
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        elif self.version == 6:
            if relationship:
                relationship_hash = hashlib.sha256(relationship.encode()).digest().hex()
                if relationship_hash != self.relationship_hash:
                    raise InvalidRelationshipHashException()
            else:
                relationship_hash = self.relationship_hash
            hashout = (
                hashlib.sha256(
                    (
                        self.public_key
                        + str(self.time)
                        + self.dh_public_key
                        + self.rid
                        + relationship_hash
                        + "{0:.8f}".format(self.fee)
                        + "{0:.8f}".format(self.masternode_fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                        + str(self.version)
                        + self.prerotated_key_hash
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        elif self.version == 5:
            if relationship:
                relationship_hash = hashlib.sha256(relationship.encode()).digest().hex()
                if relationship_hash != self.relationship_hash:
                    raise InvalidRelationshipHashException()
            else:
                relationship_hash = self.relationship_hash
            hashout = (
                hashlib.sha256(
                    (
                        self.public_key
                        + str(self.time)
                        + self.dh_public_key
                        + self.rid
                        + relationship_hash
                        + "{0:.8f}".format(self.fee)
                        + "{0:.8f}".format(self.masternode_fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                        + str(self.version)
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        elif self.version == 4:
            if relationship:
                relationship_hash = hashlib.sha256(relationship.encode()).digest().hex()
                if relationship_hash != self.relationship_hash:
                    raise InvalidRelationshipHashException()
            else:
                relationship_hash = self.relationship_hash
            hashout = (
                hashlib.sha256(
                    (
                        self.public_key
                        + str(self.time)
                        + self.dh_public_key
                        + self.rid
                        + relationship_hash
                        + "{0:.8f}".format(self.fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                        + str(self.version)
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        elif self.version == 3:
            hashout = (
                hashlib.sha256(
                    (
                        self.public_key
                        + str(self.time)
                        + self.dh_public_key
                        + self.rid
                        + relationship
                        + "{0:.8f}".format(self.fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                        + str(self.version)
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        elif self.version == 2:
            hashout = (
                hashlib.sha256(
                    (
                        self.public_key
                        + str(self.time)
                        + self.dh_public_key
                        + self.rid
                        + relationship
                        + "{0:.8f}".format(self.fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        else:
            hashout = (
                hashlib.sha256(
                    (
                        self.dh_public_key
                        + self.rid
                        + self.relationship
                        + "{0:.8f}".format(self.fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        return hashout

    async def get_input_hashes(self):
        return "".join(
            sorted(
                [x.id async for x in self.get_inputs(self.inputs)],
                key=lambda v: v.lower(),
            )
        )

    async def find_in_extra_blocks(self, txn_input):
        for block in self.extra_blocks:
            for xtxn in block.transactions:
                if xtxn.transaction_signature == txn_input.id:
                    return xtxn

    def get_output_hashes(self):
        outputs_sorted = sorted(
            [x.to_dict() for x in self.outputs], key=lambda x: x["to"].lower()
        )
        return "".join([x["to"] + "{0:.8f}".format(x["value"]) for x in outputs_sorted])

    async def recover_missing_transaction(self, txn_id, exclude_ids=[]):
        return False

    def are_kel_fields_populated(self):
        if self.twice_prerotated_key_hash:
            return True

        if self.prerotated_key_hash:
            return True

        if self.public_key_hash:
            return True

        if self.prev_public_key_hash:
            return True
        return False

    async def is_already_onchain(self, block_index=None):
        from yadacoin.core.keyeventlog import BlocksQueryFields

        config = Config()
        query = []
        if self.twice_prerotated_key_hash:
            query.append(
                {
                    BlocksQueryFields.TWICE_PREROTATED_KEY_HASH.value: self.twice_prerotated_key_hash
                }
            )

        if self.prerotated_key_hash:
            query.append(
                {BlocksQueryFields.PREROTATED_KEY_HASH.value: self.prerotated_key_hash}
            )

        if self.public_key_hash:
            query.append(
                {
                    BlocksQueryFields.PUBLIC_KEY_HASH.value: self.public_key_hash,
                }
            )

        # For a recovers-inception, prev_public_key_hash points to the LOST
        # delegator KEL's tip — a completely different KEL.  Once any prior
        # recovery for that same delegator has been mined, this query would
        # return True and silently discard a valid second recovery attempt.
        # The single-use invariant is already enforced by
        # verify_recovery_inception(); exclude prev_public_key_hash here so
        # the transaction is not dropped before reaching that validation.
        is_recovers = isinstance(self.relationship, (RecoveryProof, RecoveryTransition))
        if self.prev_public_key_hash and not is_recovers:
            query.append(
                {
                    BlocksQueryFields.PREV_PUBLIC_KEY_HASH.value: self.prev_public_key_hash,
                }
            )
        if not query:
            return False
        match = {"$or": query}
        if block_index is not None:
            match["index"] = {"$lt": block_index}
        result = await config.mongo.async_db.blocks.find_one(match)
        if result:
            return True
        return False

    async def is_already_in_mempool(self):
        from yadacoin.core.keyeventlog import MempoolQueryFields

        query = []
        if self.twice_prerotated_key_hash:
            query.append(
                {
                    MempoolQueryFields.TWICE_PREROTATED_KEY_HASH.value: self.twice_prerotated_key_hash
                }
            )

        if self.prerotated_key_hash:
            query.append(
                {MempoolQueryFields.PREROTATED_KEY_HASH.value: self.prerotated_key_hash}
            )

        if self.public_key_hash:
            query.append(
                {
                    MempoolQueryFields.PUBLIC_KEY_HASH.value: self.public_key_hash,
                }
            )

        if self.prev_public_key_hash:
            is_recovers = isinstance(
                self.relationship, (RecoveryProof, RecoveryTransition)
            )
            if is_recovers:
                # For recovery transactions, walk the mempool recovery chain
                # starting from prev_public_key_hash to find the current chain
                # tip.  A second recovery is valid only when prev_public_key_hash
                # IS that tip (nothing in the mempool has consumed it yet).
                # If it is stale — because a prior mempool recovery already
                # advanced the chain — treat it as a duplicate so the caller
                # knows to chain from the tip's public_key_hash instead.
                chain_tip = self.prev_public_key_hash
                seen: set = set()
                while chain_tip not in seen:
                    seen.add(chain_tip)
                    successor_doc = (
                        await self.config.mongo.async_db.miner_transactions.find_one(
                            {MempoolQueryFields.PREV_PUBLIC_KEY_HASH.value: chain_tip}
                        )
                    )
                    if not successor_doc:
                        break  # nothing consumed chain_tip → it IS the current tip
                    successor_txn = Transaction.from_dict(successor_doc)
                    if not isinstance(
                        successor_txn.relationship, (RecoveryProof, RecoveryTransition)
                    ):
                        break  # non-recovery successor — stop walking
                    if not successor_txn.public_key_hash:
                        break
                    chain_tip = successor_txn.public_key_hash

                if chain_tip != self.prev_public_key_hash:
                    # prev_public_key_hash is stale; the mempool chain has already
                    # advanced to chain_tip.  A valid second recovery must use
                    # chain_tip as its prev_public_key_hash.
                    query.append(
                        {
                            MempoolQueryFields.PREV_PUBLIC_KEY_HASH.value: self.prev_public_key_hash,
                        }
                    )
                # else: prev_public_key_hash IS the current chain tip → valid chain
            else:
                query.append(
                    {
                        MempoolQueryFields.PREV_PUBLIC_KEY_HASH.value: self.prev_public_key_hash,
                    }
                )

        if not query:
            return False
        result = await self.config.mongo.async_db.miner_transactions.find_one(
            {
                "$or": query,
            }
        )
        if result:
            return True
        return False

    async def get_kel_cross_key_auth(
        self, address, block=None, mempool=False, key_log=None
    ):
        """Return (authorized_addresses, authorized_pub_keys) when the signer is
        the latest KEL key (its address equals kel[-1].prerotated_key_hash),
        enabling it to spend UTXOs locked to any previous KEL address.

        Returns (None, None) when cross-key spending does not apply (non-KEL
        signer, or below the KEL_CROSS_KEY_SPENDING_FORK height).

        *key_log* may carry a pre-built KEL (a list of KeyEvent txns) so callers
        like Transaction.verify() can reuse the same reconstruction that
        verify_kel_output_rules already performed, rather than rebuilding the
        chain a second time.  When omitted the KEL is built on demand.
        """
        if block is not None:
            effective_index = block.index
        elif mempool:
            effective_index = self.config.LatestBlock.block.index + 1
        else:
            effective_index = self.config.LatestBlock.block.index

        if effective_index < CHAIN.KEL_CROSS_KEY_SPENDING_FORK:
            return None, None

        from yadacoin.core.keyeventlog import KeyEventLog

        kel = key_log
        if kel is None:
            kel = await KeyEventLog.build_from_public_key(
                self.public_key, onchain_only=True, use_cache=(block is None)
            )
        if kel and kel[-1].prerotated_key_hash == address:
            # Build fast membership sets once rather than scanning the whole
            # log per output during input validation.
            authorized_addresses = {entry.public_key_hash for entry in kel} | {address}
            authorized_pub_keys = {entry.public_key for entry in kel} | {
                self.public_key
            }
            return authorized_addresses, authorized_pub_keys
        return None, None

    async def has_key_event_log(
        self, block=None, mempool=False, include_offchain=False
    ):
        from yadacoin.core.keyeventlog import (
            BlocksQueryFields,
            KeyEventLogQueryFields,
            MempoolQueryFields,
        )

        # this function is the primary method for catching transactions which attempt
        # sign a transaction with a stolen key. We must check if the transaction's
        # public key is logged in the
        if not self.public_key:
            return False
        try:
            address = str(
                P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key))
            )
        except Exception:
            # Unparseable public key (e.g. a coinbase transaction which has no
            # signing public key) cannot be part of a key event log.
            return False
        query = {
            "$or": [
                {BlocksQueryFields.TWICE_PREROTATED_KEY_HASH.value: address},
                {
                    BlocksQueryFields.PREROTATED_KEY_HASH.value: address,
                },
            ],
        }
        if block:
            query["index"] = {"$lte": block.index}

        result = await self.config.mongo.async_db.blocks.find_one(query)
        if result:
            return True
        elif self.extra_blocks:
            for extra_block in self.extra_blocks:
                if extra_block.index >= block.index:
                    return False
                for xtxn in extra_block.transactions:
                    if xtxn.transaction_signature == self.transaction_signature:
                        return False
                    if (
                        xtxn.twice_prerotated_key_hash == address
                        or xtxn.prerotated_key_hash == address
                    ):
                        return True
        elif mempool:
            query = {
                "$or": [
                    {MempoolQueryFields.TWICE_PREROTATED_KEY_HASH.value: address},
                    {
                        MempoolQueryFields.PREROTATED_KEY_HASH.value: address,
                    },
                ],
            }
            result = await self.config.mongo.async_db.miner_transactions.find_one(query)
            if result:
                return True
            # Also check key_event_log — off-chain ratchet steps store parent
            # commitments there rather than in miner_transactions.
            # Only when include_offchain=True (P2P auth path); skip for UTXO
            # output rule enforcement which doesn't apply to off-chain steps.
            if include_offchain:
                kel_result = await self.config.mongo.async_db.key_event_log.find_one(
                    {KeyEventLogQueryFields.PREROTATED_KEY_HASH.value: address}
                )
                if kel_result:
                    return True
        return False

    async def verify_kel_output_rules(self, block=None, mempool=False, key_log=None):
        from yadacoin.core.keyeventlog import (
            KELDoesNotSpendAllUTXOsException,
            KELLogUnbuildableException,
            KELMissingParentUTXOException,
            KELOutputRoutingViolationException,
            KELSelfSendException,
            KeyEventLog,
        )

        # Determine effective block index for fork checks
        if block is not None:
            effective_index = block.index
        elif mempool:
            effective_index = self.config.LatestBlock.block.index + 1
        else:
            effective_index = self.config.LatestBlock.block.index

        # If KEL fields indicate this is a key event, it must not send back to its own address
        if self.are_kel_fields_populated():
            output_addresses = {output.to for output in self.outputs}
            if self.public_key_hash in output_addresses:
                raise KELSelfSendException(
                    f"Key event tx sends to its own public_key_hash ({self.public_key_hash}) instead of prerotated_key_hash."
                )

        # Only enforce spend rules when this key's address is tracked in an existing
        # on-chain or mempool log — off-chain ratchet steps have no UTXOs to check.
        if not await self.has_key_event_log(
            block=block, mempool=mempool, include_offchain=False
        ):
            return

        # Build the full log (including mempool entries) so that inception transactions
        # that are only in the mempool can still be found.  Mempool entries are tagged
        # with txn.mempool = True by build_from_public_key.  Reuse a pre-built log when
        # one was supplied (e.g. by Transaction.verify) to avoid rebuilding the chain.
        if key_log is None:
            key_log = await KeyEventLog.build_from_public_key(
                self.public_key, onchain_only=(block is not None)
            )
        if not key_log:
            raise KELLogUnbuildableException(
                f"Key event log exists for public_key={self.public_key} but could not be reconstructed."
            )

        if effective_index >= CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK:
            # For routing enforcement use only confirmed on-chain entries so that
            # stacked mempool rotations do not shift the required destination before
            # they are mined.  Fall back to the full log only when every entry is
            # still in the mempool (i.e. nothing is confirmed yet).
            onchain_key_log = [e for e in key_log if not getattr(e, "mempool", False)]
            routing_log = onchain_key_log if onchain_key_log else key_log

            # A transaction is a new key log entry if its public_key_hash is not yet
            # recorded in the confirmed (on-chain) key event log.
            # Exclude the current transaction itself to avoid falsely treating it
            # as an existing entry when it appears in the mempool routing_log.
            routing_pkh_set = {
                entry.public_key_hash
                for entry in routing_log
                if entry.transaction_signature != self.transaction_signature
            }
            is_new_key_log_entry = self.public_key_hash not in routing_pkh_set

            if not is_new_key_log_entry:
                # Not a new key log entry: all outputs must only go to the latest
                # confirmed key log entry's prerotated_key_hash.
                latest_prerotated_key_hash = routing_log[-1].prerotated_key_hash
                for output in self.outputs:
                    if output.to != latest_prerotated_key_hash:
                        raise KELOutputRoutingViolationException(
                            f"Non-rotating tx output {output.to!r} does not match latest KEL public_key_hash {latest_prerotated_key_hash!r}."
                        )
                return

        if self.public_key_hash in {
            output.to for output in self.outputs
        }:  # pragma: no cover
            raise KELSelfSendException(
                f"Key event tx sends to its own public_key_hash ({self.public_key_hash}) instead of prerotated_key_hash."
            )

        # UTXO completeness check is only meaningful for mempool submissions.
        # During block verification the miner has already assembled the transactions,
        # and counting sibling block entries creates cascading removal dependencies.
        if block is not None:
            return

        all_inputs = [
            x
            async for x in self.config.mongo.async_db.blocks.aggregate(
                [
                    {"$match": {"transactions.outputs.to": self.public_key_hash}},
                    {"$unwind": "$transactions"},
                    {
                        "$match": {
                            "transactions.outputs.to": self.public_key_hash,
                            "transactions.outputs.value": {"$gt": 0},
                        }
                    },
                ]
            )
        ]

        all_mempool_inputs = [
            x
            async for x in self.config.mongo.async_db.miner_transactions.aggregate(
                [
                    {
                        "$match": {
                            "outputs.to": self.public_key_hash,
                            "outputs.value": {"$gt": 0},
                        }
                    },
                ]
            )
        ]
        total_spent = 0
        for x in all_inputs + all_mempool_inputs:
            if x.get("transactions"):
                tx = Transaction.from_dict(x["transactions"])
            else:
                tx = Transaction.from_dict(x)
            if await self.config.BU.is_input_spent(
                tx.transaction_signature,
                self.public_key,
                inc_mempool=False,
            ):
                total_spent += 1
        mempool_chain_input_sum = len(all_inputs) + len(all_mempool_inputs)
        if (
            mempool_chain_input_sum > 0
            and mempool_chain_input_sum - total_spent != len(self.inputs)
        ):
            raise KELDoesNotSpendAllUTXOsException(
                f"Key event tx spends {len(self.inputs)} input(s) but "
                f"{mempool_chain_input_sum - total_spent} unspent UTXO(s) exist for public_key_hash={self.public_key_hash}."
            )
        if len(self.inputs) > 0 and mempool_chain_input_sum == 0:
            for inputx in self.inputs:
                if not inputx.input_txn:
                    raise KELMissingParentUTXOException(
                        f"Key event tx input {inputx.id!r} has no matching on-chain or mempool UTXO for public_key_hash={self.public_key_hash}."
                    )

    def to_dict(self):
        relationship = self.relationship
        if hasattr(relationship, "to_dict"):
            relationship = relationship.to_dict()
            if isinstance(self.relationship, NodeAnnouncement):
                relationship = {NodeAnnouncement.RELATIONSHIP_KEY: relationship}
            elif isinstance(self.relationship, AgentAnnouncement):
                relationship = {AgentAnnouncement.RELATIONSHIP_KEY: relationship}
            elif isinstance(self.relationship, ContentTakedownAnnouncement):
                relationship = {
                    ContentTakedownAnnouncement.RELATIONSHIP_KEY: relationship
                }
            elif isinstance(self.relationship, IdentityAnnouncement):
                relationship = {IdentityAnnouncement.RELATIONSHIP_KEY: relationship}
            elif isinstance(self.relationship, RotationAnnouncement):
                relationship = {RotationAnnouncement.RELATIONSHIP_KEY: relationship}
        ret = {
            "time": int(self.time),
            "rid": self.rid,
            "id": self.transaction_signature,  # Beware: changing name between object/dict view is very error prone
            "relationship": relationship,
            "relationship_hash": self.relationship_hash,
            "public_key": self.public_key,
            "dh_public_key": self.dh_public_key,
            "fee": float(self.fee),
            "masternode_fee": float(self.masternode_fee),
            "hash": self.hash,
            "inputs": [x.to_dict() for x in self.inputs],
            "outputs": [x.to_dict() for x in self.outputs],
            "version": self.version,
            "private": self.private,
            "never_expire": self.never_expire,
            "prerotated_key_hash": self.prerotated_key_hash,
            "twice_prerotated_key_hash": self.twice_prerotated_key_hash,
            "public_key_hash": self.public_key_hash,
            "prev_public_key_hash": self.prev_public_key_hash,
        }
        if self.dh_public_key:
            ret["dh_public_key"] = self.dh_public_key
        if self.requester_rid:
            ret["requester_rid"] = self.requester_rid
        if self.requested_rid:
            ret["requested_rid"] = self.requested_rid
        if self.miner_signature:
            ret["miner_signature"] = self.miner_signature
        return ret

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)


class Input(object):
    def __init__(self, signature, input_txn=None):
        self.id = signature
        self.input_txn = input_txn

    @classmethod
    def from_dict(cls, txn):
        return cls(
            signature=txn.get("id", ""),
            input_txn=txn.get("input_txn", ""),
        )

    def to_dict(self):
        return {"id": self.id}


class Output(object):
    def __init__(self, to, value):
        self.to = to
        self.value = value

    @classmethod
    def from_dict(cls, txn):
        return cls(to=txn.get("to", ""), value=txn.get("value", ""))

    def to_dict(self):
        return {"to": self.to, "value": self.value}


class Relationship(object):
    def __init__(
        self,
        dh_private_key=None,
        their_username_signature=None,
        their_username=None,
        my_username_signature=None,
        my_username=None,
        their_public_key=None,
        their_address=None,
        group=None,
        reply=None,
        topic=None,
        my_public_key=None,
    ):
        self.dh_private_key = dh_private_key
        self.their_username_signature = their_username_signature
        self.their_username = their_username
        self.my_username_signature = my_username_signature
        self.my_username = my_username
        self.their_public_key = their_public_key
        self.their_address = their_address
        self.group = group
        self.reply = reply
        self.topic = topic
        self.my_public_key = my_public_key

    def to_dict(self):
        return {
            "dh_private_key": self.dh_private_key,
            "their_username_signature": self.their_username_signature,
            "their_username": self.their_username,
            "my_username_signature": self.my_username_signature,
            "my_username": self.my_username,
            "their_public_key": self.their_public_key,
            "their_address": self.their_address,
            "group": self.group,
            "reply": self.reply,
            "topic": self.topic,
            "my_public_key": self.my_public_key,
        }

    def to_json(self):
        return json.dumps(self.to_dict())
