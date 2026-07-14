"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from enum import Enum
from hashlib import sha256
from typing import TYPE_CHECKING

from bitcoin.wallet import P2PKHBitcoinAddress

from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.locationrecovery import verify_proof as verify_recovery_proof
from yadacoin.core.recoveryannouncement import (
    RecoveryAnnouncement,
    RecoveryProof,
    RecoveryTransition,
)
from yadacoin.core.transaction import Transaction

if TYPE_CHECKING:
    from yadacoin.core.block import Block


class KELException(Exception):
    """Base KEL exception.

    Appends the offending transaction's id (its ``transaction_signature``) to
    the error message so failures can be traced back to the exact key-event
    transaction during debugging.  *txn* may be a
    :class:`~yadacoin.core.transaction.Transaction` object, a raw
    transaction_signature string, or ``None``.
    """

    def __init__(self, message, txn=None):
        if txn is not None and not isinstance(txn, str):
            txn = getattr(txn, "transaction_signature", None)
        if txn:
            message = f"{message} (txn={txn})"
        super().__init__(message)


class KELExceptionMissingInceptionKeyEvent(KELException):
    pass


class KELExceptionMissingUnconfirmedKeyEvent(KELException):
    pass


class KELExceptionMissingConfirmingKeyEvent(KELException):
    pass


class KeyEventTransactionRelationshipException(KELException):
    pass


class KELExceptionPreviousKeyHashReferenceMissing(KELException):
    pass


class PublicKeyMismatchException(Exception):
    pass


class KeyEventChainStatus(Enum):
    ONCHAIN = "onchain"
    MEMPOOL = "mempool"


class KeyEventFlag(Enum):
    CONFIRMING = "confirming"
    INCEPTION = "inception"
    UNCONFIRMED = "unconfirmed"


class BlocksQueryFields(Enum):
    TWICE_PREROTATED_KEY_HASH = "transactions.twice_prerotated_key_hash"
    PREROTATED_KEY_HASH = "transactions.prerotated_key_hash"
    PUBLIC_KEY_HASH = "transactions.public_key_hash"
    PREV_PUBLIC_KEY_HASH = "transactions.prev_public_key_hash"


class MempoolQueryFields(Enum):
    TWICE_PREROTATED_KEY_HASH = "twice_prerotated_key_hash"
    PREROTATED_KEY_HASH = "prerotated_key_hash"
    PUBLIC_KEY_HASH = "public_key_hash"
    PREV_PUBLIC_KEY_HASH = "prev_public_key_hash"


class KeyEventLogQueryFields(Enum):
    ANCHOR_PUBLIC_KEY = "anchor_public_key"
    TWICE_PREROTATED_KEY_HASH = "twice_prerotated_key_hash"
    PREROTATED_KEY_HASH = "prerotated_key_hash"
    PUBLIC_KEY_HASH = "public_key_hash"
    PREV_PUBLIC_KEY_HASH = "prev_public_key_hash"


class KeyEventException(Exception):
    pass


class KeyEventPrerotatedKeyHashException(KeyEventException):
    pass


class KeyEventSingleOutputException(KeyEventException):
    pass


class MissingKeyEventParameterException(KeyEventException):
    pass


class FatalKeyEventException(Exception):
    def __init__(self, message, other_txn_to_delete=None):
        super().__init__(message)
        self.other_txn_to_delete = other_txn_to_delete


class DoesNotSpendEntirelyToPrerotatedKeyHashException(FatalKeyEventException):
    pass


class KELSelfSendException(DoesNotSpendEntirelyToPrerotatedKeyHashException):
    """Tx outputs include its own public_key_hash instead of the prerotated_key_hash."""


class KELLogUnbuildableException(DoesNotSpendEntirelyToPrerotatedKeyHashException):
    """Key event log exists on-chain but could not be reconstructed."""


class KELOutputRoutingViolationException(
    DoesNotSpendEntirelyToPrerotatedKeyHashException
):
    """Non-rotating tx sends to an address other than the latest KEL public_key_hash."""


class KELDoesNotSpendAllUTXOsException(
    DoesNotSpendEntirelyToPrerotatedKeyHashException
):
    """Tx does not spend all available UTXOs for this key (on-chain + mempool)."""


class KELMissingParentUTXOException(DoesNotSpendEntirelyToPrerotatedKeyHashException):
    """Tx has inputs but no matching UTXOs found on-chain or in the mempool."""


class KELExceptionPredecessorNotYetInMempool(KELException):
    """Confirming entry's predecessor is committed on-chain (via prerotated commitments)
    but has not arrived in the mempool yet. Transient — retry when predecessor is present.
    """


# ── Location-recovery (KEL_RECOVERY_FORK) ────────────────────────────────────


class KELRecoveryException(KELException):
    """Base class for failures specific to location-recovery KEL delegation."""


class KELRecoveryNotActivatedException(KELRecoveryException):
    """{"recovers": ...} or {"recovery": ...} appeared before KEL_RECOVERY_FORK."""


class KELRecoveryMalformedProofException(KELRecoveryException):
    """Recovery proof is missing required fields or has wrong types."""


class KELRecoveryInvalidProofException(KELRecoveryException):
    """Schnorr verification failed, or the commitment does not match the
    announced witness hash."""


class KELRecoveryAnnouncementMissingException(KELRecoveryException):
    """No active {"recovery": witnessHash} announcement was found in the
    previous KEL for the recovers-inception to consume."""


class KELRecoveryAlreadyConsumedException(KELRecoveryException):
    """The previous KEL has already been recovered once — it is sealed."""


class KELRecoveryUnknownPreviousKELException(KELRecoveryException):
    """The recovers-inception's prev_public_key_hash does not match the
    public_key_hash of any on-chain KEL tip."""


def get_recovery_announcement_witness_hash(txn: Transaction):
    """If *txn* is a recovery announcement, return its witnessHash.

    A recovery announcement is any KEL transaction whose relationship has
    been parsed into a RecoveryAnnouncement instance by
    Transaction.__init__.  The chain only treats it as the active
    announcement after the fork height (callers should gate on
    CHAIN.KEL_RECOVERY_FORK).
    """
    rel = getattr(txn, "relationship", None)
    if isinstance(rel, RecoveryAnnouncement):
        return rel.witness_hash
    if isinstance(rel, RecoveryTransition):
        return rel.announcement.witness_hash
    return None


def get_recovers_proof(txn: Transaction):
    """If *txn* is a recovers-inception, return its proof dict.

    The proof has the shape {commitment, R, s} — all hex strings.  Returns
    None when the txn is not a recovers-inception.
    """
    rel = getattr(txn, "relationship", None)
    if isinstance(rel, RecoveryProof):
        return {"commitment": rel.commitment, "R": rel.R, "s": rel.s}
    if isinstance(rel, RecoveryTransition):
        p = rel.proof
        return {"commitment": p.commitment, "R": p.R, "s": p.s}
    return None


def is_recovery_announcement(txn: Transaction) -> bool:
    return get_recovery_announcement_witness_hash(txn) is not None


def is_recovers_inception(txn: Transaction) -> bool:
    """A recovers-inception has both prev_public_key_hash AND a {recovers: ...}
    relationship.  This is the only KEL transaction that legally carries both.
    """
    return bool(txn.prev_public_key_hash) and get_recovers_proof(txn) is not None


def is_identity_announcement_inception(txn: Transaction) -> bool:
    """An identity-announcement inception carries an IdentityAnnouncement (or
    RotationAnnouncement) in its relationship field.  This is the only non-recovers
    case where a KEL inception is permitted to have a non-empty relationship.
    """
    from yadacoin.core.identityannouncement import IdentityAnnouncement
    from yadacoin.core.rotationannouncement import RotationAnnouncement

    rel = getattr(txn, "relationship", None)
    return isinstance(rel, (IdentityAnnouncement, RotationAnnouncement))


def find_active_recovery_witness_hash(log):
    """Return the most recent witnessHash announced in *log*.

    Walks the supplied KEL forward and returns the witnessHash from the LAST
    transaction that carries a {"recovery": ...} relationship.  A newer
    announcement supersedes any older one (per the design: only the latest
    announcement is honoured at recovery time).  Returns None when the log
    contains no announcements.
    """
    latest = None
    for entry_txn in log:
        h = get_recovery_announcement_witness_hash(entry_txn)
        if h:
            latest = h
    return latest


class KeyEvent:
    def __init__(
        self,
        txn: Transaction = None,
        flag: KeyEventFlag = None,
        status: KeyEventChainStatus = None,
        path: str = None,
    ):
        if not txn or not isinstance(txn, Transaction):
            raise MissingKeyEventParameterException(
                "Transaction parameter is invalid or missing"
            )
        self.txn = txn
        self.flag = flag
        self.status = status
        self.path = path
        self.config = Config()

    def verify_fields(self, prev_public_key_hash_required=False):
        if not Config().address_is_valid(self.txn.twice_prerotated_key_hash):
            raise KeyEventException("twice_prerotated_key_hash is not a valid hash")

        if not Config().address_is_valid(self.txn.prerotated_key_hash):
            raise KeyEventException("prerotated_key_hash is not a valid hash")

        if not Config().address_is_valid(self.txn.public_key_hash):
            raise KeyEventException("public_key_hash is not a valid hash")

        from bitcoin.wallet import P2PKHBitcoinAddress

        expected_public_key_hash = str(
            P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.txn.public_key))
        )
        if self.txn.public_key_hash != expected_public_key_hash:
            raise KeyEventException(
                "public_key_hash does not match the P2PKH address of public_key"
            )

        if prev_public_key_hash_required:  # optional for inception
            if not Config().address_is_valid(self.txn.prev_public_key_hash):
                raise KeyEventException("prev_public_key_hash is not a valid hash")

    def verify_inception(self, onchain=False):
        self.verify_fields(prev_public_key_hash_required=False)

        if len(self.txn.outputs) != 1:
            raise KeyEventSingleOutputException(
                f"{self.flag.value.upper()} key event should only have a single output"
            )
        if self.txn.outputs[0].to != self.txn.prerotated_key_hash:
            raise KeyEventPrerotatedKeyHashException(
                f"{self.flag.value.upper()} key event output should equal the prerotated_key_hash"
            )
        if (
            self.txn.relationship != ""
            and not is_recovers_inception(self.txn)
            and not is_identity_announcement_inception(self.txn)
        ):
            raise KeyEventTransactionRelationshipException(
                f"{self.flag.value.upper()} key event attempts to populate relationship field. This is not allowed."
            )

        if (onchain and self.status == KeyEventChainStatus.MEMPOOL) or (
            not onchain and self.status == KeyEventChainStatus.ONCHAIN
        ):
            raise KeyEventException("not a valid inception key event. Invalid status.")

    async def verify_recovery_inception(
        self, onchain=False, block_index=None, batch_txns=None, use_mempool=False
    ):
        """Validate a {"recovers": ...} inception that delegates ownership from
        a previous KEL whose keys were lost.

        A recovery inception is structurally an inception transaction (single
        output to its own prerotated_key_hash, no smart-contract relationship)
        with two extra constraints:

        * ``prev_public_key_hash`` MUST be the ``public_key_hash`` of the on-chain
          tip of some previous KEL (the "delegator" KEL).
        * ``relationship`` MUST contain ``{"recovers": {commitment, R, s}}``.
          The Schnorr proof is verified against the latest ``{"recovery": ...}``
          announcement in the delegator KEL, with the delegator's tip
          public_key_hash bound into the Fiat-Shamir challenge to prevent
          replay across KELs.

        Single-use semantics: once any recovery successor exists on-chain for
        the delegator KEL, no second recovery is permitted (the delegator KEL
        is sealed).
        """
        # Basic field validation — all four KEL hash fields required.
        self.verify_fields(prev_public_key_hash_required=True)

        if len(self.txn.outputs) != 1:
            raise KeyEventSingleOutputException(
                "RECOVERY inception key event should only have a single output"
            )
        if self.txn.outputs[0].to != self.txn.prerotated_key_hash:
            raise KeyEventPrerotatedKeyHashException(
                "RECOVERY inception key event output should equal the prerotated_key_hash"
            )

        proof = get_recovers_proof(self.txn)
        if proof is None:
            raise KELRecoveryMalformedProofException(
                "recovers inception missing well-formed {commitment, R, s} proof"
            )

        # Blocks accepted before CHECK_KEL_PREV_HASH_FORK (e.g. block 597214) may
        # reference a delegator KEL that cannot be found on-chain.  Skip the full
        # delegator-lookup and proof-verification for those legacy blocks.
        if block_index is not None and block_index < CHAIN.CHECK_KEL_PREV_HASH_FORK:
            return

        # Look up the delegator KEL's tip transaction by its public_key_hash
        # (== our prev_public_key_hash).
        #
        # Priority order:
        #   1. Current block's transactions (batch_txns) — the delegator KEL tip
        #      may be in the same block as the recovery inception, not yet on-chain.
        #   2. On-chain (blocks collection) — the normal case.
        #   3. Mempool (miner_transactions) — ONLY when validating a mempool
        #      submission (block_index is None).  Block verification must never
        #      trust unconfirmed mempool entries for the delegator.
        config = Config()
        delegator_tip_txn = None
        delegator_in_mempool = False

        # 1. Check the block being validated first.
        if batch_txns:
            for btxn in batch_txns:
                if btxn.public_key_hash == self.txn.prev_public_key_hash:
                    delegator_tip_txn = btxn
                    break

        # 2. Check on-chain.
        if delegator_tip_txn is None:
            cursor = config.mongo.async_db.blocks.aggregate(
                [
                    {
                        "$match": {
                            BlocksQueryFields.PUBLIC_KEY_HASH.value: self.txn.prev_public_key_hash
                        }
                    },
                    {"$unwind": "$transactions"},
                    {
                        "$match": {
                            BlocksQueryFields.PUBLIC_KEY_HASH.value: self.txn.prev_public_key_hash
                        }
                    },
                    {"$limit": 1},
                ]
            )
            rows = await cursor.to_list(length=1)
            if rows:
                delegator_tip_txn = Transaction.from_dict(rows[0]["transactions"])

        # 3. For mempool submissions (use_mempool=True), always check the
        #    miner_transactions collection.  delegator_in_mempool is set only
        #    when the delegator is confirmed to be there — it is never inferred
        #    from batch_txns, which can represent block-level data.
        if use_mempool:
            mempool_doc = await config.mongo.async_db.miner_transactions.find_one(
                {
                    MempoolQueryFields.PUBLIC_KEY_HASH.value: self.txn.prev_public_key_hash
                }
            )
            if mempool_doc:
                delegator_in_mempool = True
                if delegator_tip_txn is None:
                    delegator_tip_txn = Transaction.from_dict(mempool_doc)

        if delegator_tip_txn is None:
            raise KELRecoveryUnknownPreviousKELException(
                "recovery references prev_public_key_hash with no on-chain or mempool KEL entry",
                txn=self.txn,
            )

        # Reconstruct the delegator's full on-chain KEL and confirm the
        # referenced entry really is its tip (latest entry with no successor).
        # Use segment_only=True so the backward walk stops at a recovers-inception
        # boundary, building only the delegator's own KEL segment rather than
        # walking all the way back to the original KEL's inception.
        delegator_log = await KeyEventLog.build_from_public_key(
            delegator_tip_txn.public_key,
            onchain_only=not delegator_in_mempool,
            follow_recovery=False,
            segment_only=True,
        )
        if not delegator_log:
            raise KELRecoveryUnknownPreviousKELException(
                "could not reconstruct delegator KEL",
                txn=self.txn,
            )
        if delegator_log[-1].public_key_hash != self.txn.prev_public_key_hash:
            raise KELRecoveryUnknownPreviousKELException(
                "recovery does not point to the delegator KEL's latest entry",
                txn=self.txn,
            )

        # Single-use: reject if a recovery successor already exists on-chain or in mempool.
        # Exception: allow a second recovery when the same commitment (witness hash) is
        # reused — the Schnorr proof is still bound to prev_public_key_hash, so cross-KEL
        # replay is impossible even when the commitment is shared across recovery events.
        existing_successor = await KeyEventLog.find_recovery_successor(
            self.txn.prev_public_key_hash, onchain_only=False
        )
        if existing_successor and (
            existing_successor.transaction_signature != self.txn.transaction_signature
        ):
            existing_proof = get_recovers_proof(existing_successor)
            if existing_proof is None or existing_proof.get("commitment") != proof.get(
                "commitment"
            ):
                raise KELRecoveryAlreadyConsumedException(
                    "delegator KEL has already been recovered; it is sealed",
                    txn=self.txn,
                )

        # Resolve the active witness hash from the latest announcement in the
        # delegator KEL.  No announcement → no recovery permitted.
        announced_witness_hash = find_active_recovery_witness_hash(delegator_log)
        if not announced_witness_hash:
            raise KELRecoveryAnnouncementMissingException(
                "delegator KEL has no {recovery: witnessHash} announcement",
                txn=self.txn,
            )

        # Bind the proof's commitment to the announced witness hash:
        #   witnessHash == SHA-256(commitment_compressed_bytes)
        try:
            commitment_bytes = bytes.fromhex(proof["commitment"])
        except ValueError as exc:
            raise KELRecoveryMalformedProofException(
                f"recovers proof commitment is not valid hex: {exc}",
                txn=self.txn,
            )
        if sha256(commitment_bytes).hexdigest() != announced_witness_hash.lower():
            raise KELRecoveryInvalidProofException(
                "recovers proof commitment does not match announced witnessHash",
                txn=self.txn,
            )

        # Verify the Schnorr proof, binding the delegator's tip pkh into the
        # Fiat-Shamir challenge so the proof cannot be replayed against any
        # other KEL.
        if not verify_recovery_proof(
            commitment_hex=proof["commitment"],
            R_hex=proof["R"],
            s_hex=proof["s"],
            prev_key_hash=self.txn.prev_public_key_hash,
        ):
            raise KELRecoveryInvalidProofException(
                "Schnorr verification failed for recovers proof",
                txn=self.txn,
            )

        if (onchain and self.status == KeyEventChainStatus.MEMPOOL) or (
            not onchain and self.status == KeyEventChainStatus.ONCHAIN
        ):
            raise KeyEventException(
                "not a valid recovery inception key event. Invalid status."
            )

    def verify_unconfirmed(self):
        self.verify_fields(prev_public_key_hash_required=True)
        if (
            not self.txn.relationship
            and len(self.txn.outputs) == 1
            and self.txn.outputs[0].to == self.txn.prerotated_key_hash
            and not self.txn.coinbase  # may send only to itelf in rare circumstances
        ):
            raise KeyEventException(
                f"not a valid unconfirmed key event. invalid relationship, outputs, or prerotated_key_hash. txn={self.txn.transaction_signature}"
            )

        if self.status != KeyEventChainStatus.MEMPOOL:
            raise KeyEventException(
                "not a valid unconfirmed key event. Invalid status."
            )

    def verify_confirming(self, entire_log, onchain=False):
        self.verify_fields(prev_public_key_hash_required=True)

        if len(self.txn.outputs) != 1:
            raise KeyEventSingleOutputException(
                f"{self.flag.value.upper()} key event should only have a single output"
            )
        if (
            self.txn.outputs[0].to != self.txn.prerotated_key_hash
            and self.txn.outputs[0].to != entire_log[-1].prerotated_key_hash
        ):
            raise KeyEventPrerotatedKeyHashException(
                f"{self.flag.value.upper()} key event output should equal the prerotated_key_hash"
            )
        if self.txn.relationship != "" and not is_recovers_inception(self.txn):
            raise KeyEventTransactionRelationshipException(
                f"{self.flag.value.upper()} key event attempts to populate relationship field. This is not allowed."
            )

        if (onchain and self.status == KeyEventChainStatus.MEMPOOL) or (
            not onchain and self.status == KeyEventChainStatus.ONCHAIN
        ):
            raise KeyEventException("not a valid confirming key event. Invalid status.")

    async def verify(
        self,
        batch_txns=None,
        block_index=None,
        use_mempool=False,
        allow_offchain_parent=None,
    ):
        # When verifying historical block data the predecessor must exist
        # on-chain; off-chain key_event_log entries are not a valid parent.
        # Default: allow when use_mempool is True (P2P / mempool path),
        # disallow when block_index is provided (block verification path).
        if allow_offchain_parent is None:
            allow_offchain_parent = use_mempool and block_index is None
        address = str(
            P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.txn.public_key))
        )
        if address != self.txn.public_key_hash:
            raise PublicKeyMismatchException(
                "transaction public_key does not correspond to public_key_hash"
            )

        # Short-circuit for recovers-inception.  The generic predecessor
        # existence check below would fail because the recovering device's K_0
        # is brand-new and has no prior on-chain parent keyed by its own pkh.
        # All validation (delegator KEL lookup, Schnorr proof, single-use
        # invariant) is handled inside verify_recovery_inception().
        if is_recovers_inception(self.txn):
            await self.verify_recovery_inception(
                block_index=block_index, batch_txns=batch_txns, use_mempool=use_mempool
            )
            return

        # Only enforce the expired-key-event check for blocks at or above the
        # fork height.  Blocks accepted before this check was introduced (e.g.
        # block 597214) must still sync successfully, so we skip the check when
        # block_index is below CHECK_KEL_EXPIRED_SEND_FORK.  A None block_index
        # means the call came from mempool validation, where the check always
        # applies.
        if block_index is None or block_index >= CHAIN.CHECK_KEL_EXPIRED_SEND_FORK:
            if await self.sends_to_past_kel_entry(block_index=block_index):
                await self.config.mongo.async_db.miner_transactions.delete_one(
                    {"id": self.txn.transaction_signature}
                )
                raise KELException(
                    "Unconfirmed key event sends to an expired key event. Removing.",
                    txn=self.txn,
                )

        # Non-inception key events: enforce predecessor-existence rules.
        # Confirming entries (single output to prerotated_key_hash, no relationship) allow
        # one level of mempool chaining — their parent may be an unconfirmed entry in the
        # mempool.  Unconfirmed entries (carry relationship data or non-standard outputs)
        # always require an on-chain parent.
        if self.txn.prev_public_key_hash:
            # Derive classification from flag if already set, otherwise from txn properties.
            if self.flag is not None:
                is_confirming = self.flag == KeyEventFlag.CONFIRMING
            else:
                is_confirming = (
                    not self.txn.relationship
                    and len(self.txn.outputs) == 1
                    and self.txn.outputs[0].to == self.txn.prerotated_key_hash
                )

            onchain_parent = await self.get_onchain_parent()
            if not onchain_parent:
                if is_confirming:
                    # Confirming entries may chain off an unconfirmed mempool parent.
                    mempool_parent = await self.config.mongo.async_db.miner_transactions.find_one(
                        {
                            MempoolQueryFields.PUBLIC_KEY_HASH.value: self.txn.prev_public_key_hash
                        }
                    )
                    if not mempool_parent:
                        if batch_txns:
                            batch_parent = next(
                                (
                                    t
                                    for t in batch_txns
                                    if t.public_key_hash
                                    == self.txn.prev_public_key_hash
                                ),
                                None,
                            )
                            if batch_parent:
                                return
                        # Also accept a parent already stored in key_event_log
                        # (sent in a previous delta gossip round).
                        if allow_offchain_parent:
                            kel_parent = (
                                await self.config.mongo.async_db.key_event_log.find_one(
                                    {"public_key_hash": self.txn.prev_public_key_hash}
                                )
                            )
                            if kel_parent:
                                return
                        raise KELExceptionPredecessorNotYetInMempool(
                            "Confirming key event rejected: predecessor key event not found "
                            "on-chain or in the mempool.",
                            txn=self.txn,
                        )
                else:
                    if batch_txns:
                        batch_parent = next(
                            (
                                t
                                for t in batch_txns
                                if t.public_key_hash == self.txn.prev_public_key_hash
                            ),
                            None,
                        )
                        if batch_parent:
                            return
                    # Also allow parent already in the mempool (e.g. inception
                    # not yet mined — practical for long block times).
                    mempool_parent = await self.config.mongo.async_db.miner_transactions.find_one(
                        {
                            MempoolQueryFields.PUBLIC_KEY_HASH.value: self.txn.prev_public_key_hash
                        }
                    )
                    if mempool_parent:
                        return
                    # Also accept a parent already stored in key_event_log
                    # (sent in a previous delta gossip round).
                    if allow_offchain_parent:
                        kel_parent = (
                            await self.config.mongo.async_db.key_event_log.find_one(
                                {"public_key_hash": self.txn.prev_public_key_hash}
                            )
                        )
                        if kel_parent:
                            return
                    raise KELException(
                        "Unconfirmed key event rejected: predecessor key event is not yet "
                        "confirmed on-chain or present in the mempool.",
                        txn=self.txn,
                    )

        if await self.txn.is_already_onchain(block_index=block_index):
            key_log = await KeyEventLog.build_from_public_key(self.txn.public_key)
            if (
                len(self.txn.outputs) != 1
                or key_log[-1].prerotated_key_hash != self.txn.outputs[0].to
            ):
                raise KELException("Key event is already onchain", txn=self.txn)

    async def sends_to_past_kel_entry(self, block_index=None):
        return False  # we're no longer checking past KEL entries
        for output in self.txn.outputs:
            config = Config()
            match_clause = {
                BlocksQueryFields.PUBLIC_KEY_HASH.value: output.to,
            }
            if block_index is not None:
                match_clause["index"] = {"$lt": block_index}
            result = config.mongo.async_db.blocks.aggregate(
                [
                    {
                        "$match": match_clause,
                    },
                    {"$unwind": "$transactions"},
                    {
                        "$match": {
                            BlocksQueryFields.PUBLIC_KEY_HASH.value: output.to,
                        },
                    },
                ]
            )
            res = await result.to_list(length=1)
            if res:
                txn = Transaction.from_dict(res[0]["transactions"])
                key_event = KeyEvent(
                    txn,
                    flag=(
                        KeyEventFlag.CONFIRMING
                        if txn.prev_public_key_hash
                        else KeyEventFlag.INCEPTION
                    ),
                    status=KeyEventChainStatus.ONCHAIN,
                )
                return key_event
        return False

    async def get_onchain_parent(self):
        config = Config()
        res = config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        "$or": [
                            {
                                BlocksQueryFields.TWICE_PREROTATED_KEY_HASH.value: self.txn.prerotated_key_hash,
                            },
                            {
                                BlocksQueryFields.PREROTATED_KEY_HASH.value: self.txn.public_key_hash,
                            },
                        ]
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        "$or": [
                            {
                                BlocksQueryFields.TWICE_PREROTATED_KEY_HASH.value: self.txn.prerotated_key_hash,
                            },
                            {
                                BlocksQueryFields.PREROTATED_KEY_HASH.value: self.txn.public_key_hash,
                            },
                        ]
                    }
                },
                {"$limit": 1},
            ]
        )
        result = await res.to_list(length=None)
        if result:
            txn = Transaction.from_dict(result[0]["transactions"])
            key_event = KeyEvent(
                txn,
                flag=(
                    KeyEventFlag.INCEPTION
                    if not txn.prev_public_key_hash or is_recovers_inception(txn)
                    else KeyEventFlag.UNCONFIRMED
                    if txn.relationship
                    else KeyEventFlag.CONFIRMING
                ),
                status=KeyEventChainStatus.ONCHAIN,
            )

            return {
                "key_event": key_event,
            }

    async def get_mempool_parent(self):
        """Return the mempool parent entry for this key event, or None.

        Checks miner_transactions for an entry whose twice_prerotated_key_hash
        matches our prerotated_key_hash, or whose prerotated_key_hash matches
        our public_key_hash.  Used when the parent entry has been broadcast to
        the mempool but not yet mined (e.g. inception not yet on-chain).
        """
        config = Config()
        doc = await config.mongo.async_db.miner_transactions.find_one(
            {
                "$or": [
                    {
                        MempoolQueryFields.TWICE_PREROTATED_KEY_HASH.value: self.txn.prerotated_key_hash,
                    },
                    {
                        MempoolQueryFields.PREROTATED_KEY_HASH.value: self.txn.public_key_hash,
                    },
                ]
            }
        )
        if doc:
            txn = Transaction.from_dict(doc)
            key_event = KeyEvent(
                txn,
                flag=(
                    KeyEventFlag.CONFIRMING
                    if txn.prev_public_key_hash
                    else KeyEventFlag.INCEPTION
                ),
                status=KeyEventChainStatus.MEMPOOL,
            )
            return {"key_event": key_event}
        return None

    async def get_onchain_child(self):
        config = Config()
        res = config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        BlocksQueryFields.PREROTATED_KEY_HASH.value: self.txn.twice_prerotated_key_hash,
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        BlocksQueryFields.PREROTATED_KEY_HASH.value: self.txn.twice_prerotated_key_hash,
                    }
                },
                {"$limit": 1},
            ]
        )
        result = await res.to_list(length=None)
        if result:
            txn = Transaction.from_dict(result[0]["transactions"])
            return KeyEvent(
                txn,
                flag=(
                    KeyEventFlag.CONFIRMING
                    if self.txn.prev_public_key_hash
                    else KeyEventFlag.INCEPTION
                ),
                status=KeyEventChainStatus.ONCHAIN,
            )


class KELHashCollectionException(Exception):
    pass


class KELHashCollection:
    @classmethod
    async def init_async(cls, block: "Block", verify_only=False):
        self = cls()
        self.config = Config()
        self.twice_prerotated_key_hashes = {}
        self.prerotated_key_hashes = {}
        self.public_key_hashes = {}
        self.prev_public_key_hashes = {}
        for transaction in block.transactions[:]:
            try:
                self.add(transaction)
            except KELHashCollectionException as e:
                if verify_only:
                    raise e
                self.config.app_log.info(f"Txn removed from block: {e}")
                block.transactions.remove(transaction)
                await self.config.mongo.async_db.miner_transactions.delete_one(
                    {"id": transaction.transaction_signature}
                )
        return self

    def add(self, transaction):
        if transaction.twice_prerotated_key_hash:
            if (
                transaction.twice_prerotated_key_hash
                in self.twice_prerotated_key_hashes
            ):
                raise KELHashCollectionException(
                    "Duplication key event in mempool. Removing. (twice_prerotated_key_hash)"
                )
            self.twice_prerotated_key_hashes[
                transaction.twice_prerotated_key_hash
            ] = transaction

        if transaction.prerotated_key_hash:
            if transaction.prerotated_key_hash in self.prerotated_key_hashes:
                raise KELHashCollectionException(
                    "Duplication key event in mempool. Removing. (prerotated_key_hash)"
                )
            self.prerotated_key_hashes[transaction.prerotated_key_hash] = transaction

        if transaction.public_key_hash:
            if transaction.public_key_hash in self.public_key_hashes:
                raise KELHashCollectionException(
                    "Duplication key event in mempool. Removing. (public_key_hash)"
                )
            self.public_key_hashes[transaction.public_key_hash] = transaction

        if transaction.prev_public_key_hash:
            if transaction.prev_public_key_hash in self.prev_public_key_hashes:
                raise KELHashCollectionException(
                    "Duplication key event in mempool. Removing. (prev_public_key_hash)"
                )
            self.prev_public_key_hashes[transaction.prev_public_key_hash] = transaction


class KeyEventLog:
    base_key_event: KeyEvent = None
    unconfirmed_key_event: KeyEvent = None
    confirming_key_event: KeyEvent = None
    path: str = None

    @staticmethod
    async def init_async(
        key_event: KeyEvent = None,
        hash_collection: KELHashCollection = None,
        block_index: int = None,
        batch_txns=None,
    ):
        self = KeyEventLog()
        self.config = Config()

        # Recovery short-circuit: a {"recovers": ...} inception is a brand new
        # KEL whose only structural link to the prior KEL is via
        # prev_public_key_hash + the embedded ZKP.  Validate it specially so
        # the normal parent/child / hash-collection checks do not reject it.
        if is_recovers_inception(key_event.txn):
            latest_index = self.config.LatestBlock.block.index
            if latest_index < CHAIN.KEL_RECOVERY_FORK:
                raise KELRecoveryNotActivatedException(
                    "KEL recovery is not yet active at this block height"
                )
            await key_event.verify_recovery_inception(
                block_index=block_index, batch_txns=batch_txns
            )
            key_event.flag = KeyEventFlag.INCEPTION
            key_event.path = "recovery"
            self.base_key_event = key_event
            self.path = "recovery"
            return self

        # step 1: if transaction is tracked on-chain in an existing key event log
        result = await key_event.get_onchain_parent()
        # Only look for a mempool parent when there is no on-chain parent and
        # this is not an inception (prev_public_key_hash must be set).
        mempool_result = None
        if not result and key_event.txn.prev_public_key_hash:
            mempool_result = await key_event.get_mempool_parent()
        entire_log = await KeyEventLog.build_from_public_key(key_event.txn.public_key)
        if result and result["key_event"]:
            # step 1.1: If found, check that this entry is the latest entry, if not, raise exception
            onchain_child = await result["key_event"].get_onchain_child()
            if onchain_child:
                if (
                    key_event.txn.twice_prerotated_key_hash
                    != onchain_child.txn.twice_prerotated_key_hash
                    or key_event.txn.prerotated_key_hash
                    != onchain_child.txn.prerotated_key_hash
                    or key_event.txn.public_key_hash
                    != onchain_child.txn.public_key_hash
                ):
                    raise FatalKeyEventException(
                        "key_event.txn has onchain parent that already has an onchain child.",
                        other_txn_to_delete=hash_collection.prerotated_key_hashes.get(  # get the confirming key event if present
                            key_event.txn.twice_prerotated_key_hash
                        ),
                    )

            # check if public key hash and prev public key hash match
            if (
                result["key_event"].txn.public_key_hash
                != key_event.txn.prev_public_key_hash
            ):
                raise FatalKeyEventException(
                    "key_event.txn onchain parent public_key_hash does not equal key_event.txn.prev_public_key_hash",
                    other_txn_to_delete=hash_collection.prerotated_key_hashes.get(  # get the confirming key event if present
                        key_event.txn.twice_prerotated_key_hash
                    ),
                )

            # step 1.2: if not onchain child is found then check if it's confirming or unconfirmed

            # assign confirming key event and flag
            if (
                not key_event.txn.relationship
                and len(key_event.txn.outputs) == 1
                and (
                    key_event.txn.outputs[0].to == key_event.txn.prerotated_key_hash
                    or key_event.txn.outputs[0].to == entire_log[-1].prerotated_key_hash
                )
                and key_event.txn.prev_public_key_hash
            ):
                key_event.flag = KeyEventFlag.CONFIRMING
                key_event.path = "1"
                self.confirming_key_event = key_event

                # assign inception/onchain key event and flag
                result["key_event"].path = "1"
                self.base_key_event = result["key_event"]
                self.path = "1"

            # assign unconfirmed key event and flag
            else:
                past_key_event = await key_event.sends_to_past_kel_entry(
                    block_index=block_index
                )
                if past_key_event:
                    raise FatalKeyEventException(
                        "Unconfirmed key event sends to past key event.",
                        other_txn_to_delete=hash_collection.prerotated_key_hashes.get(  # get the confirming key event if present
                            key_event.txn.twice_prerotated_key_hash
                        ),
                    )
                parent_event = result["key_event"]
                key_event.flag = KeyEventFlag.UNCONFIRMED
                key_event.path = "1.5"
                self.unconfirmed_key_event = key_event
                parent_event.path = "1.5"
                self.base_key_event = parent_event
                self.path = "1.5"

                # assign confirming key event and flag
                if (
                    key_event.txn.twice_prerotated_key_hash
                    in hash_collection.prerotated_key_hashes
                ):
                    self.confirming_key_event = KeyEvent(
                        hash_collection.prerotated_key_hashes[
                            key_event.txn.twice_prerotated_key_hash
                        ],
                        KeyEventFlag.CONFIRMING,
                        KeyEventChainStatus.MEMPOOL,
                        "1",
                    )
                else:
                    raise FatalKeyEventException(
                        "No confirming key event present in hash_collection.",
                        other_txn_to_delete=hash_collection.prerotated_key_hashes.get(  # get the confirming key event if present
                            key_event.txn.twice_prerotated_key_hash
                        ),
                    )

        # step 1.5: mempool parent found — inception (or previous rotation) not yet mined.
        # Allows chaining KEL entries in the mempool before the parent is confirmed on-chain.
        # Skip if the hash_collection already has a non-inception entry at
        # key_event.txn.prerotated_key_hash — that means step 2.2 (hash_collection path)
        # should handle it instead (e.g. unconfirmed + confirming in the same block).
        elif (
            mempool_result
            and mempool_result["key_event"]
            and not (
                key_event.txn.prerotated_key_hash
                in hash_collection.twice_prerotated_key_hashes
                and hash_collection.twice_prerotated_key_hashes[
                    key_event.txn.prerotated_key_hash
                ].prev_public_key_hash
            )
        ):
            parent_event = mempool_result["key_event"]

            if parent_event.txn.public_key_hash != key_event.txn.prev_public_key_hash:
                raise FatalKeyEventException(
                    "key_event.txn mempool parent public_key_hash does not equal key_event.txn.prev_public_key_hash",
                    other_txn_to_delete=hash_collection.prerotated_key_hashes.get(
                        key_event.txn.twice_prerotated_key_hash
                    ),
                )

            if (
                not key_event.txn.relationship
                and len(key_event.txn.outputs) == 1
                and (
                    key_event.txn.outputs[0].to == key_event.txn.prerotated_key_hash
                    or (
                        entire_log
                        and key_event.txn.outputs[0].to
                        == entire_log[-1].prerotated_key_hash
                    )
                )
                and key_event.txn.prev_public_key_hash
            ):
                key_event.flag = KeyEventFlag.CONFIRMING
                key_event.path = "1.5"
                self.confirming_key_event = key_event
                parent_event.path = "1.5"
                self.base_key_event = parent_event
                self.path = "1.5"
            else:
                past_key_event = await key_event.sends_to_past_kel_entry(
                    block_index=block_index
                )
                if past_key_event:
                    raise FatalKeyEventException(
                        "Unconfirmed key event sends to past key event.",
                        other_txn_to_delete=hash_collection.prerotated_key_hashes.get(
                            key_event.txn.twice_prerotated_key_hash
                        ),
                    )

                key_event.flag = KeyEventFlag.UNCONFIRMED
                key_event.path = "1.6"
                self.unconfirmed_key_event = key_event
                parent_event.path = "1.6"
                self.base_key_event = parent_event

                if (
                    key_event.txn.twice_prerotated_key_hash
                    in hash_collection.prerotated_key_hashes
                ):
                    self.confirming_key_event = KeyEvent(
                        hash_collection.prerotated_key_hashes[
                            key_event.txn.twice_prerotated_key_hash
                        ],
                        KeyEventFlag.CONFIRMING,
                        KeyEventChainStatus.MEMPOOL,
                        "1.5",
                    )
                else:
                    raise FatalKeyEventException(
                        "No confirming key event present in hash_collection.",
                        other_txn_to_delete=hash_collection.prerotated_key_hashes.get(
                            key_event.txn.twice_prerotated_key_hash
                        ),
                    )

        # step 2: If onchain parent not found
        # Check within this hash_collection for an off-chain parent
        elif (
            key_event.txn.public_key_hash not in hash_collection.prerotated_key_hashes
            and key_event.txn.prerotated_key_hash
            not in hash_collection.twice_prerotated_key_hashes
            and key_event.txn.public_key_hash
            not in hash_collection.twice_prerotated_key_hashes
            and not key_event.txn.prev_public_key_hash
        ):
            # step 2.1 if parent is not found, this is an inception key event
            # assign inception key event and flag
            key_event.flag = KeyEventFlag.INCEPTION
            key_event.path = "2.1"
            self.base_key_event = key_event
            self.path = "2.1"
        else:
            # step 2.2 if parent is not found in blockchain, this should be a confirming key event
            # with an unconfirmed key event in the mempool as well.
            #
            # Historically we rejected the case where the grandparent (an
            # inception or previous confirming) was also present in the
            # same hash_collection.  That restriction is no longer valid:
            # the block-generation fixpoint cleanup pass intentionally
            # admits inception + unconfirmed + confirming triplets in a
            # single block, and the lookup below (prerotated_key_hash in
            # twice_prerotated_key_hashes) still selects the correct
            # unconfirmed parent in that case.

            # Figure out if this event looks like a confirming event by its own
            # txn properties: no relationship, single output that ends at its
            # prerotated_key_hash.  Hash-collection cross-links can be
            # ambiguous in long chains (a txn can appear on both sides
            # simultaneously), so we use txn-properties to choose the role.
            looks_confirming = (
                not key_event.txn.relationship
                and len(key_event.txn.outputs) == 1
                and key_event.txn.outputs[0].to == key_event.txn.prerotated_key_hash
                and not getattr(key_event.txn, "coinbase", False)
            )

            if looks_confirming and (
                key_event.txn.prerotated_key_hash
                in hash_collection.twice_prerotated_key_hashes
            ):
                key_event.flag = KeyEventFlag.CONFIRMING
                key_event.path = "2.2"
                self.confirming_key_event = key_event

                unconfirmed_key_event = KeyEvent(
                    hash_collection.twice_prerotated_key_hashes[
                        key_event.txn.prerotated_key_hash
                    ],
                    KeyEventFlag.UNCONFIRMED,
                    KeyEventChainStatus.MEMPOOL,
                    "2.2",
                )

                self.unconfirmed_key_event = unconfirmed_key_event
                self.path = "2.2"
                result = await unconfirmed_key_event.get_onchain_parent()
                if result and result["key_event"]:
                    result["key_event"].path = "2.2"
                    self.base_key_event = result["key_event"]
                else:
                    mempool_base = await unconfirmed_key_event.get_mempool_parent()
                    if mempool_base and mempool_base["key_event"]:
                        mempool_base["key_event"].path = "2.2"
                        self.base_key_event = mempool_base["key_event"]
                    else:
                        raise KELException(
                            "No on-chain or mempool key event found for unconfirmed key event.",
                            txn=key_event.txn,
                        )

            elif (
                key_event.txn.twice_prerotated_key_hash
                in hash_collection.prerotated_key_hashes
            ):
                # This is an unconfirmed rotation whose confirming child is
                # present in the same hash_collection.
                key_event.flag = KeyEventFlag.UNCONFIRMED
                key_event.path = "2.5"
                self.unconfirmed_key_event = key_event
                self.path = "2.5"

                confirming_txn = hash_collection.prerotated_key_hashes[
                    key_event.txn.twice_prerotated_key_hash
                ]
                self.confirming_key_event = KeyEvent(
                    confirming_txn,
                    KeyEventFlag.CONFIRMING,
                    KeyEventChainStatus.MEMPOOL,
                    "2.5",
                )

                if (
                    key_event.txn.prerotated_key_hash
                    in hash_collection.twice_prerotated_key_hashes
                ):
                    parent_txn = hash_collection.twice_prerotated_key_hashes[
                        key_event.txn.prerotated_key_hash
                    ]
                    self.base_key_event = KeyEvent(
                        parent_txn,
                        flag=(
                            KeyEventFlag.INCEPTION
                            if not parent_txn.prev_public_key_hash
                            else KeyEventFlag.CONFIRMING
                        ),
                        status=KeyEventChainStatus.MEMPOOL,
                        path="2.5",
                    )
                else:
                    raise KELException(
                        "No on-chain or mempool key event found for unconfirmed key event.",
                        txn=key_event.txn,
                    )

            elif not getattr(key_event.txn, "coinbase", False):
                raise KELException(
                    "No onchain key event for unconfirmed key event.",
                    txn=key_event.txn,
                )

            else:
                raise FatalKeyEventException(
                    "No unconfirmed or confirming key event present in hash_collection.",
                    other_txn_to_delete=hash_collection.prerotated_key_hashes.get(
                        key_event.txn.twice_prerotated_key_hash
                    ),
                )

        # check that KEL is one of five scenarios.
        # 1. Inception
        if (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.INCEPTION
            and self.base_key_event.status == KeyEventChainStatus.MEMPOOL
            and not self.unconfirmed_key_event
            and not self.confirming_key_event
        ):
            self.base_key_event.verify_inception()

        # 2. Inception and confirming
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.INCEPTION
            and self.base_key_event.status == KeyEventChainStatus.ONCHAIN
            and not self.unconfirmed_key_event
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            # we don't need to check if the onchain key event is an inception or not.
            # If prev_hash has is not set, then it must be an inception which is enforced by rule 1
            self.base_key_event.verify_inception(onchain=True)
            self.confirming_key_event.verify_confirming(entire_log)
            self.verify_links()

        # 3. onchain confirming and confirming
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.CONFIRMING
            and self.base_key_event.status == KeyEventChainStatus.ONCHAIN
            and not self.unconfirmed_key_event
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            self.base_key_event.verify_confirming(entire_log, onchain=True)
            self.confirming_key_event.verify_confirming(entire_log)
            self.verify_links()

        # 3b. Onchain unconfirmed base + confirming (mempool).
        # Occurs in fork scenarios where the unconfirmed event was already mined
        # (along with its original confirming pair) in a different block at the same
        # height.  The on-chain unconfirmed base has already been validated; only the
        # incoming confirming event needs to be checked.
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.UNCONFIRMED
            and self.base_key_event.status == KeyEventChainStatus.ONCHAIN
            and not self.unconfirmed_key_event
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            self.confirming_key_event.verify_confirming(entire_log)
            self.verify_links()

        # 4. Inception, unconfirmed, and confirming
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.INCEPTION
            and self.base_key_event.status == KeyEventChainStatus.ONCHAIN
            and self.unconfirmed_key_event
            and self.unconfirmed_key_event.flag == KeyEventFlag.UNCONFIRMED
            and self.unconfirmed_key_event.status == KeyEventChainStatus.MEMPOOL
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            self.base_key_event.verify_inception(onchain=True)
            self.unconfirmed_key_event.verify_unconfirmed()
            self.confirming_key_event.verify_confirming(entire_log)
            self.verify_links()

        # 5. Onchain confirming, unconfirmed, and confirming
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.CONFIRMING
            and self.base_key_event.status == KeyEventChainStatus.ONCHAIN
            and self.unconfirmed_key_event
            and self.unconfirmed_key_event.flag == KeyEventFlag.UNCONFIRMED
            and self.unconfirmed_key_event.status == KeyEventChainStatus.MEMPOOL
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            self.base_key_event.verify_confirming(entire_log, onchain=True)
            self.unconfirmed_key_event.verify_unconfirmed()
            self.confirming_key_event.verify_confirming(entire_log)
            self.verify_links()

        # 6. Mempool inception + confirming (mempool) — inception not yet mined
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.INCEPTION
            and self.base_key_event.status == KeyEventChainStatus.MEMPOOL
            and not self.unconfirmed_key_event
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            self.base_key_event.verify_inception()
            self.confirming_key_event.verify_confirming(entire_log)
            self.verify_links()

        # 7. Mempool inception + unconfirmed (mempool) + confirming (mempool)
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.INCEPTION
            and self.base_key_event.status == KeyEventChainStatus.MEMPOOL
            and self.unconfirmed_key_event
            and self.unconfirmed_key_event.flag == KeyEventFlag.UNCONFIRMED
            and self.unconfirmed_key_event.status == KeyEventChainStatus.MEMPOOL
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            self.base_key_event.verify_inception()
            self.unconfirmed_key_event.verify_unconfirmed()
            self.confirming_key_event.verify_confirming(entire_log)
            self.verify_links()

        # 8. Mempool confirming base (prev rotation unconfirmed/not yet mined) + confirming (mempool)
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.CONFIRMING
            and self.base_key_event.status == KeyEventChainStatus.MEMPOOL
            and not self.unconfirmed_key_event
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            self.base_key_event.verify_confirming(entire_log)
            self.confirming_key_event.verify_confirming(entire_log)
            self.verify_links()

        # 9. Mempool confirming base + unconfirmed (mempool) + confirming (mempool)
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.CONFIRMING
            and self.base_key_event.status == KeyEventChainStatus.MEMPOOL
            and self.unconfirmed_key_event
            and self.unconfirmed_key_event.flag == KeyEventFlag.UNCONFIRMED
            and self.unconfirmed_key_event.status == KeyEventChainStatus.MEMPOOL
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            self.base_key_event.verify_confirming(entire_log)
            self.unconfirmed_key_event.verify_unconfirmed()
            self.confirming_key_event.verify_confirming(entire_log)
            self.verify_links()

        else:
            raise KELException(
                "Invalid KEL scenario",
                txn=(
                    self.confirming_key_event.txn
                    if self.confirming_key_event
                    else (self.base_key_event.txn if self.base_key_event else None)
                ),
            )
        return self

    def verify_links(self):
        if (
            self.base_key_event
            and self.unconfirmed_key_event
            and self.confirming_key_event
        ):
            self.verify_base_and_unconfirmed()
            self.verify_unconfirmed_and_confirming()
            return

        if self.base_key_event and self.confirming_key_event:
            self.verify_base_and_confirming()
            return

    def verify_base_and_unconfirmed(self):
        if (
            self.base_key_event.txn.twice_prerotated_key_hash
            != self.unconfirmed_key_event.txn.prerotated_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.twice_prerotated_key_hash does not match unconfirmed_key_event.txn.prerotated_key_hash",
                txn=self.base_key_event.txn,
            )
        if (
            self.base_key_event.txn.prerotated_key_hash
            != self.unconfirmed_key_event.txn.public_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.prerotated_key_hash does not match unconfirmed_key_event.txn.public_key_hash",
                txn=self.base_key_event.txn,
            )
        if (
            self.base_key_event.txn.public_key_hash
            != self.unconfirmed_key_event.txn.prev_public_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.public_key_hash does not match unconfirmed_key_event.txn.prev_public_key_hash",
                txn=self.base_key_event.txn,
            )

    def verify_unconfirmed_and_confirming(self):
        if (
            self.unconfirmed_key_event.txn.twice_prerotated_key_hash
            != self.confirming_key_event.txn.prerotated_key_hash
        ):
            raise KELException(
                "Mismatch: unconfirmed_key_event.txn.twice_prerotated_key_hash does not match confirming_key_event.txn.prerotated_key_hash",
                txn=self.unconfirmed_key_event.txn,
            )
        if (
            self.unconfirmed_key_event.txn.prerotated_key_hash
            != self.confirming_key_event.txn.public_key_hash
        ):
            raise KELException(
                "Mismatch: unconfirmed_key_event.txn.prerotated_key_hash does not match confirming_key_event.txn.public_key_hash",
                txn=self.unconfirmed_key_event.txn,
            )
        if (
            self.unconfirmed_key_event.txn.public_key_hash
            != self.confirming_key_event.txn.prev_public_key_hash
        ):
            raise KELException(
                "Mismatch: unconfirmed_key_event.txn.public_key_hash does not match confirming_key_event.txn.prev_public_key_hash",
                txn=self.unconfirmed_key_event.txn,
            )

    def verify_base_and_confirming(self):
        if (
            self.base_key_event.txn.twice_prerotated_key_hash
            != self.confirming_key_event.txn.prerotated_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.twice_prerotated_key_hash does not match confirming_key_event.txn.prerotated_key_hash",
                txn=self.base_key_event.txn,
            )
        if (
            self.base_key_event.txn.prerotated_key_hash
            != self.confirming_key_event.txn.public_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.prerotated_key_hash does not match confirming_key_event.txn.public_key_hash",
                txn=self.base_key_event.txn,
            )
        if (
            self.base_key_event.txn.public_key_hash
            != self.confirming_key_event.txn.prev_public_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.public_key_hash does not match confirming_key_event.txn.prev_public_key_hash",
                txn=self.base_key_event.txn,
            )

    @staticmethod
    async def find_recovery_successor(public_key_hash, onchain_only=False):
        """Return the recovers-inception that succeeds the KEL whose tip is
        *public_key_hash*, or None.

        The successor is uniquely identified by:
          * ``prev_public_key_hash == public_key_hash``
          * a well-formed ``{"recovers": ...}`` relationship

        Searches the mempool first (unless *onchain_only*), then on-chain
        blocks.  Checking mempool first ensures that a pending recovery whose
        KEL tip is still unconfirmed is found correctly after multiple
        consecutive recoveries.  Returns the Transaction object or None.
        """
        config = Config()

        if not onchain_only:
            mempool_cursor = config.mongo.async_db.miner_transactions.find(
                {MempoolQueryFields.PREV_PUBLIC_KEY_HASH.value: public_key_hash}
            )
            async for doc in mempool_cursor:
                txn = Transaction.from_dict(doc)
                if is_recovers_inception(txn):
                    txn.mempool = True
                    return txn

        cursor = config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        BlocksQueryFields.PREV_PUBLIC_KEY_HASH.value: public_key_hash
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        BlocksQueryFields.PREV_PUBLIC_KEY_HASH.value: public_key_hash
                    }
                },
            ]
        )
        rows = await cursor.to_list(length=None)
        for row in rows:
            txn = Transaction.from_dict(row["transactions"])
            if is_recovers_inception(txn):
                return txn

        return None

    @staticmethod
    async def build_from_public_key(
        public_key, onchain_only=False, follow_recovery=True, segment_only=False
    ):
        """Build the ordered KEL for *public_key*.

        When *onchain_only* is True the forward-walk stops at the confirmed
        blockchain tip: mempool entries are never appended.  This is important
        for output-routing validation so that a pending (unconfirmed) rotation
        sitting in the mempool is never mistaken for the "latest" KEL entry.

        When *follow_recovery* is True (default) the forward-walk crosses
        ``{"recovers": ...}`` recovery boundaries: once the natural rotation
        chain exhausts, the search looks for a recovers-inception whose
        ``prev_public_key_hash`` equals the current tip's ``public_key_hash``
        and continues walking into the new KEL.  Set False when validating a
        recovery itself (to avoid feedback loops) or when consumers want only
        the segment up to the first recovery boundary.
        """
        config = Config()
        log = []
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        inception = None
        while True:
            result = config.mongo.async_db.blocks.aggregate(
                [
                    {
                        "$match": {
                            "$or": [
                                {BlocksQueryFields.PUBLIC_KEY_HASH.value: address},
                                {BlocksQueryFields.PREROTATED_KEY_HASH.value: address},
                                {
                                    BlocksQueryFields.TWICE_PREROTATED_KEY_HASH.value: address
                                },
                            ]
                        },
                    },
                    {
                        "$unwind": "$transactions",
                    },
                    {
                        "$match": {
                            "$or": [
                                {BlocksQueryFields.PUBLIC_KEY_HASH.value: address},
                                {BlocksQueryFields.PREROTATED_KEY_HASH.value: address},
                                {
                                    BlocksQueryFields.TWICE_PREROTATED_KEY_HASH.value: address
                                },
                            ]
                        },
                    },
                ]
            )
            res = await result.to_list(length=1)
            if res:
                txn = Transaction.from_dict(res[0]["transactions"])
                # When segment_only is True, treat a recovers-inception as the
                # inception boundary for this KEL segment so the backward walk
                # does not cross into the delegator KEL's history.  When
                # segment_only is False (default), follow prev_public_key_hash
                # across recovery boundaries to reach the original inception.
                if not txn.prev_public_key_hash or (
                    segment_only and is_recovers_inception(txn)
                ):
                    inception = txn
                    break
                address = txn.prev_public_key_hash
            else:
                # This case for pending inception transactions
                if onchain_only:
                    break
                result_mempool = await config.mongo.async_db.miner_transactions.find_one(
                    {
                        "$or": [
                            {MempoolQueryFields.PUBLIC_KEY_HASH.value: address},
                            {MempoolQueryFields.PREROTATED_KEY_HASH.value: address},
                            {
                                MempoolQueryFields.TWICE_PREROTATED_KEY_HASH.value: address
                            },
                        ]
                    },
                )
                if not result_mempool:
                    break
                txn = Transaction.from_dict(result_mempool)
                txn.mempool = True
                if not txn.prev_public_key_hash or (
                    segment_only and is_recovers_inception(txn)
                ):
                    inception = txn
                    break
                address = txn.prev_public_key_hash
        if inception:
            log.append(inception)
            txn = inception
            while True:
                address = txn.prerotated_key_hash
                result = config.mongo.async_db.blocks.aggregate(
                    [
                        {
                            "$match": {
                                BlocksQueryFields.PUBLIC_KEY_HASH.value: address
                            },
                        },
                        {
                            "$unwind": "$transactions",
                        },
                        {
                            "$match": {
                                BlocksQueryFields.PUBLIC_KEY_HASH.value: address
                            },
                        },
                    ]
                )
                res = await result.to_list(length=1)
                if res:
                    txn = Transaction.from_dict(res[0]["transactions"])
                    log.append(txn)
                    continue

                if not onchain_only:
                    result_mempool = (
                        await config.mongo.async_db.miner_transactions.find_one(
                            {MempoolQueryFields.PUBLIC_KEY_HASH.value: address},
                        )
                    )
                    if result_mempool:
                        txn = Transaction.from_dict(result_mempool)
                        txn.mempool = True
                        log.append(txn)
                        continue

                # Natural rotation chain exhausted.  If recovery-following is
                # enabled, look for a {"recovers": ...} successor whose
                # prev_public_key_hash references the current tip's pkh and
                # continue walking forward from there.
                if follow_recovery:
                    successor = await KeyEventLog.find_recovery_successor(
                        log[-1].public_key_hash, onchain_only=onchain_only
                    )
                    if successor is not None:
                        log.append(successor)
                        txn = successor
                        continue
                break  # pragma: no cover

        return log
