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
from yadacoin.core.branchannouncement import BranchAnnouncement
from yadacoin.core.chain import CHAIN
from yadacoin.core.collections import Collections
from yadacoin.core.config import Config
from yadacoin.core.contenttakedown import (
    MINIMUM_TAKEDOWN_FEE,
    ContentTakedownAnnouncement,
)
from yadacoin.core.credentialannouncement import CredentialAnnouncement
from yadacoin.core.credentialreceipt import CredentialReceipt
from yadacoin.core.fileannouncement import FileAnnouncement
from yadacoin.core.identityannouncement import IdentityAnnouncement
from yadacoin.core.nodeannouncement import NodeAnnouncement
from yadacoin.core.recoveryannouncement import (
    RecoveryAnnouncement,
    RecoveryProof,
    RecoveryTransition,
)
from yadacoin.core.rotationannouncement import RotationAnnouncement


def _relationship_verify_height(block):
    """Height used for relationship-type fork gates.

    Prefer the verifying block; otherwise LatestBlock.
    """
    if block is not None and getattr(block, "index", None) is not None:
        try:
            return int(block.index)
        except (TypeError, ValueError):
            pass
    try:
        latest = Config().LatestBlock
        if latest is not None and getattr(latest, "block", None) is not None:
            return int(latest.block.index)
    except Exception:
        pass
    return 0


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
        counter=None,
        inception_public_key_hash=None,
        branch_public_key_hash_path=None,
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
        if counter is not None:
            self.counter = counter
        if inception_public_key_hash is not None:
            self.inception_public_key_hash = inception_public_key_hash
        if branch_public_key_hash_path is not None:
            self.branch_public_key_hash_path = branch_public_key_hash_path

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
            and BranchAnnouncement.RELATIONSHIP_KEY in self.relationship
        ):
            # Peer-branch root commitment on a main-KEL unconfirmed rotation.
            self.relationship = BranchAnnouncement.from_dict(
                self.relationship[BranchAnnouncement.RELATIONSHIP_KEY]
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
            and FileAnnouncement.RELATIONSHIP_KEY in self.relationship
        ):
            self.relationship = FileAnnouncement.from_relationship(self.relationship)
        elif (
            isinstance(self.relationship, dict)
            and CredentialAnnouncement.RELATIONSHIP_KEY in self.relationship
        ):
            self.relationship = CredentialAnnouncement.from_relationship(
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
        if relationship:
            if hasattr(relationship, "to_string") and callable(
                getattr(relationship, "to_string")
            ):
                rel_preimage = relationship.to_string()
            else:
                rel_preimage = relationship
            cls_inst.relationship_hash = (
                hashlib.sha256(rel_preimage.encode()).digest().hex()
            )
        else:
            cls_inst.relationship_hash = ""
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
        cls_inst.public_key = public_key
        cls_inst.never_expire = never_expire
        cls_inst.private = private
        cls_inst.prerotated_key_hash = prerotated_key_hash
        cls_inst.twice_prerotated_key_hash = twice_prerotated_key_hash
        cls_inst.public_key_hash = public_key_hash
        cls_inst.prev_public_key_hash = prev_public_key_hash

        if do_money:
            await cls_inst.do_money()

        if private_key and public_key:
            from yadacoin.core.keyrotation import NodeKeyRotationManager

            cls_inst.hash = await cls_inst.generate_hash()
            cls_inst.transaction_signature = NodeKeyRotationManager._sign(
                private_key, cls_inst.hash
            )
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
        self,
        input_obj,
        input_txn,
        my_address,
        input_sum,
        inputs,
        outputs_and_fee_total,
        batch_txns=None,
    ):
        address = my_address
        # Prior-KEL-address value only when this txn is a key-log entry
        # (one-time keys: plain tip spends are not authorized).
        kel_log_spend = False
        try:
            if self.are_kel_fields_populated() and self.public_key:
                kel_log_spend = await self.get_kel_cross_key_auth(
                    address,
                    mempool=True,
                    batch_txns=batch_txns,
                    extra_blocks=getattr(self, "extra_blocks", None),
                )
        except Exception:
            kel_log_spend = False

        for txn_output in input_txn.outputs:
            if float(txn_output.value) <= 0.0:
                continue
            out_to = str(txn_output.to)
            owns = await self._output_owned_by_kel_spender(
                out_to,
                address,
                kel_log_spend,
                extra_blocks=getattr(self, "extra_blocks", None),
                batch_txns=batch_txns,
            )
            if not owns and kel_log_spend:
                parent_inc = getattr(input_txn, "inception_public_key_hash", None)
                my_inc = getattr(self, "inception_public_key_hash", None)
                pre = getattr(input_txn, "prerotated_key_hash", None) or ""
                if (
                    parent_inc
                    and my_inc
                    and parent_inc == my_inc
                    and pre
                    and out_to == pre
                ):
                    owns = True
            if not owns:
                continue
            if self.exact_match and not equal(txn_output.value, outputs_and_fee_total):
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
            counter=txn.get("counter", None),
            inception_public_key_hash=txn.get("inception_public_key_hash", None),
            branch_public_key_hash_path=txn.get("branch_public_key_hash_path", None),
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
        check_branch_announcement=False,
        check_credential_announcement=False,
        block=None,
        mempool=False,
        batch_txns=None,
        extra_blocks=None,
    ):
        from yadacoin.contracts.base import Contract
        from yadacoin.core.keyeventlog import (
            KELExceptionPreviousKeyHashReferenceMissing,
        )

        if check_max_inputs and len(self.inputs) > CHAIN.MAX_INPUTS:
            raise TooManyInputsException(
                f"Maximum inputs of {CHAIN.MAX_INPUTS} exceeded."
            )

        if extra_blocks is not None:
            self.extra_blocks = extra_blocks

        verify_hash = await self.generate_hash()
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))

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
                if not has_kel and extra_blocks:
                    for extra_block in extra_blocks:
                        if (
                            block is not None
                            and getattr(extra_block, "index", None) is not None
                            and extra_block.index > block.index
                        ):
                            continue
                        _batch_prerotated = {
                            t.prerotated_key_hash
                            for t in extra_block.transactions
                            if t.transaction_signature != self.transaction_signature
                        }
                        _batch_twice = {
                            t.twice_prerotated_key_hash
                            for t in extra_block.transactions
                            if t.transaction_signature != self.transaction_signature
                        }
                        has_kel = (
                            has_kel
                            or address in _batch_prerotated
                            or address in _batch_twice
                        )
                        if has_kel:
                            break

            if has_kel:
                txn_key_event = KeyEvent(self)
                await txn_key_event.verify(
                    batch_txns=batch_txns,
                    block_index=block.index if block is not None else None,
                    use_mempool=mempool,
                    extra_blocks=extra_blocks,
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
                    extra_blocks=extra_blocks,
                )
            elif self.prev_public_key_hash and (
                block is None or block.index >= CHAIN.CHECK_KEL_PREV_HASH_FORK
            ):
                raise KELExceptionPreviousKeyHashReferenceMissing(
                    "Key event claims to have a key event log by specifying prev_public_key_hash, but no key event log found.",
                    txn=self,
                )

            # Unique inception: no second KEL root for the same public_key_hash
            # / inception tag (covers re-included identical ids and fresh ids).
            _uniq_idx = block.index if block is not None else None
            if _uniq_idx is None or _uniq_idx >= CHAIN.KEL_UNIQUE_INCEPTION_FORK:
                await self.assert_unique_inception(
                    block_index=_uniq_idx,
                    batch_txns=batch_txns,
                    extra_blocks=extra_blocks,
                    use_mempool=mempool,
                )

            if has_kel:
                if block is not None:
                    _kel_index = block.index
                elif mempool:
                    _kel_index = self.config.LatestBlock.block.index + 1
                else:
                    _kel_index = self.config.LatestBlock.block.index

                if _kel_index >= CHAIN.CHECK_KEL_SPENDS_ENTIRELY_FORK:
                    # Build the KEL once and reuse it for both output-rule
                    # enforcement and cross-key spend authorization below,
                    # instead of rebuilding the chain twice.  Block verification
                    # reads fresh from Mongo via the tagging system; the mempool
                    # path benefits from the same tagging fast-path.
                    await self.verify_kel_output_rules(block=block, mempool=mempool)

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
                self.public_key,
                exclude_txn_sig=self.transaction_signature,
                extra_blocks=extra_blocks,
                use_mempool=mempool,
                below_index=block.index if block is not None else None,
                batch_txns=batch_txns,
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
        elif isinstance(self.relationship, BranchAnnouncement):
            relationship = self.relationship.to_string()
            if not check_branch_announcement:
                raise InvalidTransactionException(
                    f"Branch announcement transactions not allowed before fork height "
                    f"{CHAIN.KEL_BRANCH_ANNOUNCEMENT_FORK}"
                )
            if not self.prev_public_key_hash:
                raise InvalidTransactionException(
                    "Branch announcement is only valid for subsequent rotations, "
                    "not inception (prev_public_key_hash is empty)"
                )
            if self.relationship.branch_type:
                height = _relationship_verify_height(block)
                if height < CHAIN.KEL_BRANCH_TYPE_FORK:
                    raise InvalidTransactionException(
                        f"Typed branch announcement transactions not allowed before "
                        f"fork height {CHAIN.KEL_BRANCH_TYPE_FORK}"
                    )
        elif isinstance(self.relationship, ContentTakedownAnnouncement):
            relationship = self.relationship.to_string()
            if not check_content_takedown:
                raise InvalidTransactionException(
                    f"Content takedown transactions not allowed before fork height {CHAIN.CONTENT_TAKEDOWN_FORK}"
                )
            if self.fee < MINIMUM_TAKEDOWN_FEE:
                raise InvalidTransactionException(
                    f"Content takedown transaction fee must be at least {MINIMUM_TAKEDOWN_FEE}"
                )
        elif isinstance(self.relationship, FileAnnouncement):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, CredentialAnnouncement):
            relationship = self.relationship.to_string()
            if not check_credential_announcement:
                height = _relationship_verify_height(block)
                check_credential_announcement = (
                    height >= CHAIN.CREDENTIAL_ANNOUNCEMENT_FORK
                )
            if not check_credential_announcement:
                raise InvalidTransactionException(
                    f"Credential announcement transactions not allowed before fork "
                    f"height {CHAIN.CREDENTIAL_ANNOUNCEMENT_FORK}"
                )
            await self.assert_unique_credential_issuance(
                block_index=block.index if block is not None else None,
                batch_txns=batch_txns,
                extra_blocks=extra_blocks,
                use_mempool=mempool,
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

        # Prior KEL addresses may only be spent by a key-log entry (KEL fields
        # populated). Keys are one-time-use: a plain tip transfer cannot pull
        # value from older KEL outs. Double-spend detection still uses
        # is_same_kel inside is_input_spent.
        kel_log_spend = (
            self.are_kel_fields_populated()
            and await self.get_kel_cross_key_auth(
                address,
                block=block,
                mempool=mempool,
                batch_txns=batch_txns,
                extra_blocks=extra_blocks or getattr(self, "extra_blocks", None),
            )
            if self.inputs
            else False
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
                if block is not None:
                    spent_from_index = block.index
                elif self.extra_blocks:
                    spent_from_index = self.extra_blocks[0].index
                else:
                    spent_from_index = self.config.LatestBlock.block.index
                is_input_spent = await self.config.BU.is_input_spent(
                    txn_input.transaction_signature,
                    self.public_key,
                    from_index=spent_from_index,
                    extra_blocks=self.extra_blocks or None,
                    spender_inception=getattr(self, "inception_public_key_hash", None),
                )
                if is_input_spent:
                    raise Exception("Input already spent")

            found = False
            for output in txn_input.outputs:
                out_to = str(output.to)
                owned = await self._output_owned_by_kel_spender(
                    out_to,
                    address,
                    kel_log_spend,
                    extra_blocks=extra_blocks or getattr(self, "extra_blocks", None),
                    batch_txns=batch_txns,
                    block=block,
                )
                if not owned and kel_log_spend:
                    # Same-block / tagged parent coinbase: pool self-out is
                    # prerotated_key_hash; MN outs stay foreign.
                    parent_inc = getattr(txn_input, "inception_public_key_hash", None)
                    my_inc = getattr(self, "inception_public_key_hash", None)
                    pre = getattr(txn_input, "prerotated_key_hash", None) or ""
                    if (
                        parent_inc
                        and my_inc
                        and parent_inc == my_inc
                        and pre
                        and out_to == pre
                    ):
                        owned = True
                if owned:
                    found = True
                    total_input += float(output.value)

            if not found:
                raise InvalidTransactionException(
                    "using inputs from a transaction where you were not one of the recipients."
                )

        if block is not None and not self.coinbase:
            from yadacoin.core.block import Block

            self.coinbase = Block.is_coinbase(block, self)
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
        elif isinstance(self.relationship, BranchAnnouncement):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, AgentAnnouncement):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, ContentTakedownAnnouncement):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, FileAnnouncement):
            relationship = self.relationship.to_string()
        elif isinstance(self.relationship, CredentialAnnouncement):
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

    async def assert_unique_inception(
        self,
        block_index=None,
        batch_txns=None,
        extra_blocks=None,
        use_mempool=True,
    ):
        """Reject a second inception for this public_key_hash / inception tag.

        An inception has empty ``prev_public_key_hash`` (non-recovery).  Once any
        on-chain (or same-batch) KEL entry exists for the same
        ``public_key_hash`` — or tags this address as
        ``inception_public_key_hash`` — a further inception is refused, even if
        the transaction id differs.
        """
        from yadacoin.core.keyeventlog import BlocksQueryFields

        if not self.are_kel_fields_populated():
            return
        # Recovery / rotation entries carry prev; only bare inceptions.
        if self.prev_public_key_hash:
            return
        from yadacoin.core.recoveryannouncement import RecoveryProof, RecoveryTransition

        if isinstance(self.relationship, (RecoveryProof, RecoveryTransition)):
            return

        pkh = getattr(self, "public_key_hash", None) or ""
        if not pkh:
            return

        my_sig = self.transaction_signature or ""
        inception_tag = getattr(self, "inception_public_key_hash", None) or pkh

        def _other_inception(txn):
            if not txn or getattr(txn, "transaction_signature", None) == my_sig:
                return False
            if not getattr(txn, "are_kel_fields_populated", lambda: False)():
                return False
            if getattr(txn, "prev_public_key_hash", None):
                return False
            t_pkh = getattr(txn, "public_key_hash", None) or ""
            t_inc = getattr(txn, "inception_public_key_hash", None) or ""
            return t_pkh == pkh or t_inc == inception_tag or t_pkh == inception_tag

        for txn in batch_txns or []:
            if _other_inception(txn):
                raise InvalidTransactionException(
                    f"Duplicate KEL inception for public_key_hash={pkh}: "
                    f"another inception is present in the same block/batch"
                )

        fork_indices = set()
        for eb in extra_blocks or []:
            eb_idx = getattr(eb, "index", None)
            if eb_idx is not None:
                fork_indices.add(int(eb_idx))
            if block_index is not None and eb_idx is not None and eb_idx >= block_index:
                continue
            for txn in getattr(eb, "transactions", None) or []:
                if _other_inception(txn):
                    raise InvalidTransactionException(
                        f"Duplicate KEL inception for public_key_hash={pkh}: "
                        f"already present in candidate chain"
                    )

        # On-chain: any prior entry with this public_key_hash, or any entry that
        # tags this address as the KEL inception. Heights covered by
        # extra_blocks are replaced by the inbound fork view and must not
        # count as an existing KEL.
        match = {
            "$or": [
                {BlocksQueryFields.PUBLIC_KEY_HASH.value: pkh},
                {"transactions.inception_public_key_hash": inception_tag},
                {"transactions.inception_public_key_hash": pkh},
            ]
        }
        if block_index is not None:
            match["index"] = {"$lt": int(block_index)}
        cursor = self.config.mongo.async_db.blocks.find(
            match, {"index": 1, "transactions": 1}
        )
        async for doc in cursor:
            idx = doc.get("index")
            if idx is not None and int(idx) in fork_indices:
                continue
            raise InvalidTransactionException(
                f"Duplicate KEL inception for public_key_hash={pkh}: "
                f"KEL already exists on-chain (block {doc.get('index')})"
            )

        # Mempool: another pending inception for the same pkh (not us).
        # Skip during block validation — mempool state is irrelevant once a
        # txn is in a candidate/confirmed block (mirrors use_mempool elsewhere).
        if not use_mempool:
            return
        mem_q = {
            "$or": [
                {"public_key_hash": pkh},
                {"inception_public_key_hash": inception_tag},
                {"inception_public_key_hash": pkh},
            ],
            "prev_public_key_hash": {"$in": [None, ""]},
        }
        if my_sig:
            mem_q["id"] = {"$ne": my_sig}
        mem = await self.config.mongo.async_db.miner_transactions.find_one(mem_q)
        if mem:
            raise InvalidTransactionException(
                f"Duplicate KEL inception for public_key_hash={pkh}: "
                f"another inception is already in the mempool"
            )

    @staticmethod
    def _credential_issuance_combo(rel):
        """(issuer, claim, subject) or None."""
        if isinstance(rel, CredentialAnnouncement):
            issuer = rel.issuer_username_signature
            claim = rel.claim
            subject = rel.subject_username_signature
        elif isinstance(rel, dict):
            inner = rel.get(CredentialAnnouncement.RELATIONSHIP_KEY, rel)
            if not isinstance(inner, dict):
                return None
            issuer = inner.get("issuer_username_signature") or ""
            claim = inner.get("claim") or ""
            subject = inner.get("subject_username_signature") or ""
        else:
            return None
        if not issuer or not claim or not subject:
            return None
        return (issuer, claim, subject)

    async def assert_unique_credential_issuance(
        self,
        block_index=None,
        batch_txns=None,
        extra_blocks=None,
        use_mempool=True,
    ):
        """One issuer may issue a given claim to a given recipient only once."""
        combo = Transaction._credential_issuance_combo(self.relationship)
        if not combo:
            return
        issuer, claim, subject = combo
        my_sig = self.transaction_signature or ""

        def _other_same(txn):
            if not txn:
                return False
            if getattr(txn, "transaction_signature", None) == my_sig:
                return False
            rel = getattr(txn, "relationship", None)
            if rel is None and isinstance(txn, dict):
                rel = txn.get("relationship")
                oid = txn.get("id") or txn.get("transaction_signature") or ""
                if oid == my_sig:
                    return False
            other = Transaction._credential_issuance_combo(rel)
            return other == combo

        for txn in batch_txns or []:
            if _other_same(txn):
                raise InvalidTransactionException(
                    "Duplicate credential issuance: this issuer already issued "
                    f"{claim!r} to this recipient in the same block/batch"
                )

        fork_indices = set()
        for eb in extra_blocks or []:
            eb_idx = getattr(eb, "index", None)
            if eb_idx is not None:
                fork_indices.add(int(eb_idx))
            if block_index is not None and eb_idx is not None and eb_idx >= block_index:
                continue
            for txn in getattr(eb, "transactions", None) or []:
                if _other_same(txn):
                    raise InvalidTransactionException(
                        "Duplicate credential issuance: this issuer already issued "
                        f"{claim!r} to this recipient in the candidate chain"
                    )

        match = {
            "transactions.relationship.credential.issuer_username_signature": issuer,
            "transactions.relationship.credential.claim": claim,
            "transactions.relationship.credential.subject_username_signature": subject,
        }
        if block_index is not None:
            match["index"] = {"$lt": int(block_index)}
        cursor = self.config.mongo.async_db.blocks.find(
            match, {"index": 1, "transactions": 1}
        )
        async for doc in cursor:
            idx = doc.get("index")
            if idx is not None and int(idx) in fork_indices:
                continue
            for stored in doc.get("transactions") or []:
                if stored.get("id") == my_sig:
                    continue
                if (
                    Transaction._credential_issuance_combo(stored.get("relationship"))
                    == combo
                ):
                    raise InvalidTransactionException(
                        "Duplicate credential issuance: this issuer already issued "
                        f"{claim!r} to this recipient on-chain "
                        f"(block {doc.get('index')})"
                    )

        if not use_mempool:
            return
        mem_q = {
            "relationship.credential.issuer_username_signature": issuer,
            "relationship.credential.claim": claim,
            "relationship.credential.subject_username_signature": subject,
        }
        if my_sig:
            mem_q["id"] = {"$ne": my_sig}
        mem = await self.config.mongo.async_db.miner_transactions.find_one(mem_q)
        if mem:
            raise InvalidTransactionException(
                "Duplicate credential issuance: this issuer already issued "
                f"{claim!r} to this recipient in the mempool"
            )

    async def is_already_onchain(self, block_index=None, extra_blocks=None):
        """True if this KEL entry already exists on the effective chain.

        When verifying an inbound / fork batch, pass ``extra_blocks``. Heights
        covered by those blocks are replaced by the fork view and must not
        count as an existing on-chain key event.
        """
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

        fork_indices = set()
        for eb in extra_blocks or []:
            idx = getattr(eb, "index", None)
            if idx is not None:
                fork_indices.add(int(idx))

        my_sig = getattr(self, "transaction_signature", None) or ""
        my_twice = getattr(self, "twice_prerotated_key_hash", None) or ""
        my_pre = getattr(self, "prerotated_key_hash", None) or ""
        my_pkh = getattr(self, "public_key_hash", None) or ""
        my_prev = (
            "" if is_recovers else (getattr(self, "prev_public_key_hash", None) or "")
        )

        def _txn_matches(t):
            if not isinstance(t, dict):
                return False
            if my_sig and t.get("id") == my_sig:
                # Same entry re-validation is not a conflicting on-chain hit.
                return False
            if my_twice and t.get("twice_prerotated_key_hash") == my_twice:
                return True
            if my_pre and t.get("prerotated_key_hash") == my_pre:
                return True
            if my_pkh and t.get("public_key_hash") == my_pkh:
                return True
            if my_prev and t.get("prev_public_key_hash") == my_prev:
                return True
            return False

        match = {"$or": query}
        if block_index is not None:
            match["index"] = {"$lt": block_index}
        cursor = config.mongo.async_db.blocks.find(
            match, {"index": 1, "transactions": 1}
        )
        async for doc in cursor:
            idx = doc.get("index")
            if idx is not None and int(idx) in fork_indices:
                continue
            for t in doc.get("transactions") or []:
                if _txn_matches(t):
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

    def _kel_walk_candidates(
        self, batch_txns=None, extra_blocks=None, block_index=None
    ):
        """KEL entries that may extend the tip (same-block + inbound fork)."""
        remaining = []
        seen_sigs = set()
        my_sig = getattr(self, "transaction_signature", None)

        def _add(t):
            if t is None or t is self:
                return
            if not getattr(t, "are_kel_fields_populated", lambda: False)():
                return
            sig = getattr(t, "transaction_signature", None)
            if my_sig and sig == my_sig:
                return
            if sig is not None:
                if sig in seen_sigs:
                    return
                seen_sigs.add(sig)
            remaining.append(t)

        for t in batch_txns or []:
            _add(t)

        for block in extra_blocks or []:
            idx = getattr(block, "index", None)
            if block_index is not None and idx is not None and idx > block_index:
                continue
            for t in getattr(block, "transactions", None) or []:
                _add(t)

        return remaining

    def _inception_tag_of(self, txn):
        if txn is None:
            return None
        return getattr(txn, "inception_public_key_hash", None) or getattr(
            txn, "public_key_hash", None
        )

    def _kel_tip_states_from_candidates(self, inception_pkh, candidates, mongo_latest):
        """Tip (pkh, pre) states for *inception_pkh* under a fork-aware view.

        Prefer tips present in inbound candidates. Fall back to the mongo tip
        when the inbound set has no entry for this inception.
        """

        starts = []
        if mongo_latest is not None:
            starts.append(
                (
                    getattr(mongo_latest, "public_key_hash", None),
                    getattr(mongo_latest, "prerotated_key_hash", None),
                )
            )

        matching = []
        for t in candidates:
            tag = getattr(t, "inception_public_key_hash", None)
            if tag and tag != inception_pkh:
                continue
            # Untagged inbound KEL entries still participate in the walk; they
            # are linked by prev/public_key_hash rather than inception tag.
            matching.append(t)

        # Seed from candidate entries that look like roots relative to matching:
        # no parent inside matching (prev not equal to some entry's pkh).
        pkhs = {
            getattr(t, "public_key_hash", None)
            for t in matching
            if getattr(t, "public_key_hash", None)
        }
        for t in matching:
            prev = getattr(t, "prev_public_key_hash", None) or ""
            if prev and prev in pkhs:
                continue
            starts.append(
                (
                    getattr(t, "public_key_hash", None),
                    getattr(t, "prerotated_key_hash", None),
                )
            )
            # Also allow walking from parent tip state into this entry.
            if prev:
                starts.append((prev, getattr(t, "public_key_hash", None)))

        # Dedup starts
        tip_states = []
        seen = set()
        for state in starts:
            if not state[0] and not state[1]:
                continue
            if state in seen:
                continue
            seen.add(state)
            tip_states.append(state)
        return tip_states, matching

    async def get_kel_cross_key_auth(
        self,
        address,
        block=None,
        mempool=False,
        batch_txns=None,
        extra_blocks=None,
    ):
        """Return True when this KEL-log txn may credit prior same-KEL UTXOs.

        Requires:
        * KEL fields populated (one-time-use keys — plain spends never qualify);
        * fork height;
        * signer *address* is the effective tip prerotated key after walking
          on-chain tip + same-block *batch_txns* + inbound *extra_blocks*
          (fork / sync batch).

        Inception is taken from this txn / batch tags first so unused tip keys
        (not yet on-chain as public_key_hash) still authorize.
        """
        if not self.are_kel_fields_populated():
            return False

        if block is not None:
            effective_index = block.index
        elif mempool:
            effective_index = self.config.LatestBlock.block.index + 1
        else:
            effective_index = self.config.LatestBlock.block.index

        if effective_index < CHAIN.KEL_CROSS_KEY_SPENDING_FORK:
            return False

        from collections import deque

        from yadacoin.core.keyeventlog import KeyEventLog

        if extra_blocks is None:
            extra_blocks = getattr(self, "extra_blocks", None) or []

        block_index = getattr(block, "index", None) if block is not None else None

        inception_pkh = getattr(self, "inception_public_key_hash", None) or None
        if not inception_pkh and batch_txns:
            for t in batch_txns:
                tag = getattr(t, "inception_public_key_hash", None)
                if tag:
                    inception_pkh = tag
                    break
        if not inception_pkh and extra_blocks:
            for block_obj in extra_blocks:
                idx = getattr(block_obj, "index", None)
                if block_index is not None and idx is not None and idx > block_index:
                    continue
                for t in getattr(block_obj, "transactions", None) or []:
                    tag = getattr(t, "inception_public_key_hash", None)
                    if tag:
                        inception_pkh = tag
                        break
                if inception_pkh:
                    break

        inception = None
        if not inception_pkh:
            for cand in (
                address,
                getattr(self, "prev_public_key_hash", None),
                getattr(self, "public_key_hash", None),
            ):
                if not cand:
                    continue
                inception = await KeyEventLog.get_inception(
                    address=cand, onchain_only=True
                )
                if inception is not None:
                    break
            if inception is None and batch_txns:
                for t in batch_txns:
                    for cand in (
                        getattr(t, "prev_public_key_hash", None),
                        getattr(t, "public_key_hash", None),
                        getattr(t, "prerotated_key_hash", None),
                    ):
                        if not cand:
                            continue
                        inception = await KeyEventLog.get_inception(
                            address=cand, onchain_only=True
                        )
                        if inception is not None:
                            break
                    if inception is not None:
                        break
            if inception is None and extra_blocks:
                for block_obj in extra_blocks:
                    idx = getattr(block_obj, "index", None)
                    if (
                        block_index is not None
                        and idx is not None
                        and idx > block_index
                    ):
                        continue
                    for t in getattr(block_obj, "transactions", None) or []:
                        for cand in (
                            getattr(t, "prev_public_key_hash", None),
                            getattr(t, "public_key_hash", None),
                            getattr(t, "prerotated_key_hash", None),
                        ):
                            if not cand:
                                continue
                            inception = await KeyEventLog.get_inception(
                                address=cand, onchain_only=True
                            )
                            if inception is not None:
                                break
                        if inception is not None:
                            break
                    if inception is not None:
                        break
            if inception is None:
                return False
            inception_pkh = getattr(
                inception, "inception_public_key_hash", None
            ) or getattr(inception, "public_key_hash", None)
        if not inception_pkh:
            return False

        latest = await KeyEventLog._latest_from_inception_tag(
            inception_pkh, onchain_only=True
        )
        if (
            latest is None
            and inception is not None
            and getattr(inception, "public_key", None)
        ):
            latest = await KeyEventLog.get_latest(
                public_key=inception.public_key, onchain_only=True
            )

        remaining = self._kel_walk_candidates(
            batch_txns=batch_txns,
            extra_blocks=extra_blocks,
            block_index=block_index,
        )

        # When verifying an inbound fork, tip may only exist in extra_blocks.
        tip_states, walk_txns = self._kel_tip_states_from_candidates(
            inception_pkh, remaining, latest
        )
        if not tip_states:
            return False

        queue = deque(tip_states)
        seen = set(tip_states)
        while queue:
            cur_pkh, cur_pre = queue.popleft()
            if cur_pre == address:
                return True
            if cur_pkh == address:
                # Signer may be the tip public_key_hash itself (coinbase path).
                return True
            for t in walk_txns:
                if (
                    getattr(t, "prev_public_key_hash", None) == cur_pkh
                    and getattr(t, "public_key_hash", None) == cur_pre
                ):
                    state = (t.public_key_hash, t.prerotated_key_hash)
                    if state not in seen:
                        seen.add(state)
                        queue.append(state)
                # Also accept direct prev==cur_pre when cur_pre is the live tip key
                # (some coinbase rotations only set prev to tip prerotated).
                elif getattr(t, "prev_public_key_hash", None) == cur_pre and getattr(
                    t, "public_key_hash", None
                ):
                    state = (t.public_key_hash, t.prerotated_key_hash)
                    if state not in seen:
                        seen.add(state)
                        queue.append(state)
        return False

    def _kel_txn_matching_address(
        self, address, batch_txns=None, extra_blocks=None, block=None
    ):
        """Find a KEL txn in inbound view that involves *address*."""
        block_index = getattr(block, "index", None) if block is not None else None

        def _matches(t):
            if not t or not getattr(t, "are_kel_fields_populated", lambda: False)():
                return False
            return address in (
                getattr(t, "public_key_hash", None),
                getattr(t, "prerotated_key_hash", None),
                getattr(t, "twice_prerotated_key_hash", None),
                getattr(t, "prev_public_key_hash", None),
            )

        for t in batch_txns or []:
            if _matches(t):
                return t
        for block_obj in extra_blocks or []:
            idx = getattr(block_obj, "index", None)
            if block_index is not None and idx is not None and idx > block_index:
                continue
            for t in getattr(block_obj, "transactions", None) or []:
                if _matches(t):
                    return t
        return None

    async def _output_owned_by_kel_spender(
        self,
        out_to,
        spender_address,
        kel_log_spend,
        extra_blocks=None,
        batch_txns=None,
        block=None,
    ):
        """True if *out_to* is spendable by this KEL-log txn's signer."""
        if out_to == str(spender_address):
            return True
        if not kel_log_spend:
            return False

        from yadacoin.core.keyeventlog import KeyEventLog

        if extra_blocks is None:
            extra_blocks = getattr(self, "extra_blocks", None) or []

        # Fast path: same inception tag on this txn vs output address.
        my_inc = getattr(self, "inception_public_key_hash", None)
        if my_inc:
            # Inbound fork first: parent coinbase/UTXO may only exist there.
            inbound = self._kel_txn_matching_address(
                out_to, batch_txns=batch_txns, extra_blocks=extra_blocks, block=block
            )
            if inbound is not None:
                out_tag = getattr(
                    inbound, "inception_public_key_hash", None
                ) or getattr(inbound, "public_key_hash", None)
                if out_tag == my_inc:
                    return True
                # Output is this entry's prerotated / pkh under same walk.
                if out_to in (
                    getattr(inbound, "prerotated_key_hash", None),
                    getattr(inbound, "public_key_hash", None),
                ):
                    inb_inc = getattr(inbound, "inception_public_key_hash", None)
                    if not inb_inc or inb_inc == my_inc:
                        return True

            # Output may itself be a KEL-tagged coinbase with inception field.
            # Prefer that over get_inception when the parent is in-memory.
            out_inc = await KeyEventLog.get_inception(address=out_to, onchain_only=True)
            if out_inc is not None:
                out_tag = getattr(
                    out_inc, "inception_public_key_hash", None
                ) or getattr(out_inc, "public_key_hash", None)
                if out_tag == my_inc:
                    return True

        # is_same_kel works when both addresses resolve on-chain.
        if await KeyEventLog.is_same_kel(
            out_to, str(spender_address), onchain_only=True
        ):
            return True

        # Last resort: if spender doesn't resolve but my_inc matches out via
        # prerotated/public_key_hash appearance on any tagged entry.
        if my_inc:
            # Direct equality: coinbase prerotated often equals a prior tip.
            # Already handled by out_to == spender.  Check parent inception
            # field when input_txn is available is caller's job.
            pass
        return False

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

    async def verify_kel_output_rules(self, block=None, mempool=False):
        from yadacoin.core.keyeventlog import (
            KELDoesNotSpendAllUTXOsException,
            KELMissingParentUTXOException,
            KELSelfSendException,
        )

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

        if self.public_key_hash in {output.to for output in self.outputs}:
            raise KELSelfSendException(
                f"Key event tx sends to its own public_key_hash ({self.public_key_hash}) instead of prerotated_key_hash."
            )

        # UTXO completeness check is only meaningful for mempool submissions.
        # During block verification the miner has already assembled the transactions,
        # and counting sibling block entries creates cascading removal dependencies.
        if block is not None:
            return

        if mempool:
            effective_index = self.config.LatestBlock.block.index + 1
        else:
            effective_index = self.config.LatestBlock.block.index

        # After cross-key spending: value may sit on earlier same-KEL tip
        # addresses. Tip-local "spend all UTXOs at public_key_hash" is no longer
        # required. Only ensure each declared input resolves to a real parent;
        # ownership / same-KEL auth is enforced in normal input verification.
        if effective_index >= CHAIN.KEL_CROSS_KEY_SPENDING_FORK:
            for inputx in self.inputs:
                if getattr(inputx, "input_txn", None):
                    continue
                parent = await self.config.BU.get_transaction_by_id(inputx.id)
                if not parent:
                    parent = (
                        await self.config.mongo.async_db.miner_transactions.find_one(
                            {"id": inputx.id}
                        )
                    )
                if not parent:
                    raise KELMissingParentUTXOException(
                        f"Key event tx input {inputx.id!r} not found on-chain or in mempool "
                        f"(spender public_key_hash={self.public_key_hash})."
                    )
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
                spender_inception=getattr(self, "inception_public_key_hash", None),
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
            elif isinstance(self.relationship, BranchAnnouncement):
                relationship = {BranchAnnouncement.RELATIONSHIP_KEY: relationship}
            elif isinstance(self.relationship, FileAnnouncement):
                relationship = {FileAnnouncement.RELATIONSHIP_KEY: relationship}
            elif isinstance(self.relationship, CredentialAnnouncement):
                relationship = {CredentialAnnouncement.RELATIONSHIP_KEY: relationship}
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
        if getattr(self, "counter", None) is not None:
            ret["counter"] = self.counter
        if getattr(self, "inception_public_key_hash", None):
            ret["inception_public_key_hash"] = self.inception_public_key_hash
        if getattr(self, "branch_public_key_hash_path", None):
            ret["branch_public_key_hash_path"] = self.branch_public_key_hash_path
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
