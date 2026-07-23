"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from collections.abc import Sequence
from enum import Enum
from hashlib import sha256
from typing import TYPE_CHECKING

from bitcoin.wallet import P2PKHBitcoinAddress

from yadacoin.core.branchannouncement import BranchAnnouncement
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
    ANCHOR_PUBLIC_KEY = "anchor_public_key"  # global (non-branch) auth ratchet
    BRANCH_INCEPTION_PUBLIC_KEY_HASH = "branch_inception_public_key_hash"
    INCEPTION_PUBLIC_KEY_HASH = "inception_public_key_hash"  # main-chain KEL
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


def is_branch_announcement(txn: Transaction) -> bool:
    """True when *txn* carries a BranchAnnouncement relationship, or the
    legacy off-chain string marker ``peer-kel-branch`` (read-tolerant)."""
    rel = getattr(txn, "relationship", None)
    if isinstance(rel, BranchAnnouncement):
        return True
    if isinstance(rel, str) and rel == "peer-kel-branch":
        return True
    return False


def get_branch_commit(txn: Transaction):
    """Return the first public peer-branch signer address (addr(Kp0)) or None.

    For a BranchAnnouncement this is ``relationship.prerotated_key_hash``.
    Legacy ``peer-kel-branch`` string bridges have no structured commit.
    """
    rel = getattr(txn, "relationship", None)
    if isinstance(rel, BranchAnnouncement):
        return rel.prerotated_key_hash
    return None


def get_branch_commit_next(txn: Transaction):
    """Return the next peer-branch hop (addr(Kp1)) or None.

    For a BranchAnnouncement this is ``relationship.twice_prerotated_key_hash``.
    """
    rel = getattr(txn, "relationship", None)
    if isinstance(rel, BranchAnnouncement):
        return rel.twice_prerotated_key_hash
    return None


def is_branch_root_entry(txn: Transaction) -> bool:
    """Forward-looking: first on-chain branch-lineage entry.

    A branch-root entry's public_key_hash equals the announcement's
    relationship.prerotated_key_hash (addr(Kp0)) and its prev_public_key_hash
    equals the announcement's confirming public_key_hash.  Detection of the
    confirming sibling is left to callers; this helper only checks whether
    the txn looks like a branch-lineage root (non-empty
    branch_public_key_hash_path with counter semantics deferred).
    """
    path = getattr(txn, "branch_public_key_hash_path", None)
    if path:
        return True
    return False


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
        # walking all the way back to the original KEL's inception.  The full
        # log (not just the tip) is required below to scan every entry for a
        # {"recovery": ...} announcement.
        delegator_log = await KeyEventLog.get_latest(
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

        if is_branch_announcement(self.txn) and isinstance(
            self.txn.relationship, BranchAnnouncement
        ):
            self.verify_branch_announcement_payload()

        if self.status != KeyEventChainStatus.MEMPOOL:
            raise KeyEventException(
                "not a valid unconfirmed key event. Invalid status."
            )

    def verify_branch_announcement_payload(self):
        """Validate BranchAnnouncement relationship payload on an unconfirmed.

        Does not alter main pre/twice pairing — only checks both peer commit
        addresses and that neither collides with main-line hashes.
        """
        commit = get_branch_commit(self.txn)
        commit_next = get_branch_commit_next(self.txn)
        if not commit or not isinstance(commit, str):
            raise KeyEventException(
                "branch announcement missing prerotated_key_hash commit"
            )
        if not commit_next or not isinstance(commit_next, str):
            raise KeyEventException(
                "branch announcement missing twice_prerotated_key_hash commit"
            )
        if not Config().address_is_valid(commit):
            raise KeyEventException(
                f"branch announcement prerotated_key_hash is not a valid "
                f"address: {commit!r}"
            )
        if not Config().address_is_valid(commit_next):
            raise KeyEventException(
                f"branch announcement twice_prerotated_key_hash is not a valid "
                f"address: {commit_next!r}"
            )
        if commit == commit_next:
            raise KeyEventException(
                "branch announcement prerotated_key_hash and "
                "twice_prerotated_key_hash must differ"
            )

        main_hashes = {
            self.txn.public_key_hash,
            self.txn.prerotated_key_hash,
            self.txn.twice_prerotated_key_hash,
        }
        if commit in main_hashes or commit_next in main_hashes:
            raise KeyEventException(
                "branch announcement commit collides with a main-line key hash"
            )

    def verify_confirming(self, latest_entry, onchain=False):
        self.verify_fields(prev_public_key_hash_required=True)

        if len(self.txn.outputs) != 1:
            raise KeyEventSingleOutputException(
                f"{self.flag.value.upper()} key event should only have a single output"
            )
        if (
            self.txn.outputs[0].to != self.txn.prerotated_key_hash
            and self.txn.outputs[0].to != latest_entry.prerotated_key_hash
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
            # The txn is already on-chain, so re-accepting it as a new key event
            # is an error.  We only require that the txn spends its balance to a
            # single output whose destination belongs to the same KEL as the
            # sender — not that it sends to the final KEL entry specifically.
            # key_log.addresses is the set of every address that has ever
            # appeared in this KEL (built during the walk), so the membership
            # test is O(1) without re-scanning the log.
            for output in self.txn.outputs:
                same_kel = await KeyEventLog.is_same_kel(
                    public_key_hash_a=self.txn.public_key_hash,
                    public_key_hash_b=output.to,
                    onchain_only=False,
                )
                if not same_kel:
                    raise KELException("Key event is already onchain", txn=self.txn)

    async def sends_to_past_kel_entry(self, block_index=None):
        return False  # we're no longer checking past KEL entries

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
                    KeyEventFlag.INCEPTION
                    if not txn.prev_public_key_hash or is_recovers_inception(txn)
                    else KeyEventFlag.UNCONFIRMED
                    if txn.relationship
                    else KeyEventFlag.CONFIRMING
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


class KELResult(Sequence):
    """Ordered KEL plus the set of addresses that have appeared in it.

    ``build_from_public_key`` returns one of these instead of a bare list so
    that consumers (e.g. ``KeyEvent.verify``) can test membership in the KEL's
    address space in O(1) without re-scanning the log.  It is a
    :class:`collections.abc.Sequence` over the underlying transaction list, so
    existing call sites that use ``kel[-1]``, ``len(kel)``, ``for e in kel``,
    and list comprehensions keep working unchanged.
    """

    __slots__ = ("_log", "addresses")

    def __init__(self, log):
        self._log = log

    def __getitem__(self, index):
        return self._log[index]

    def __len__(self):
        return len(self._log)

    def __iter__(self):
        return iter(self._log)

    def __eq__(self, other):
        if isinstance(other, KELResult):
            return self._log == other._log
        if isinstance(other, list):
            return self._log == other
        return NotImplemented

    def __hash__(self):
        return hash(tuple(self._log))

    def __repr__(self):
        return f"KELResult(len={len(self._log)})"


class KELHashCollection:
    def __init__(self):
        self.twice_prerotated_key_hashes = {}
        self.prerotated_key_hashes = {}
        self.public_key_hashes = {}
        self.prev_public_key_hashes = {}

    @classmethod
    async def init_async(cls, block: "Block", verify_only=False):
        self = cls()
        self.config = Config()
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
            # Branch-root entries (forward-looking on-chain first branch txn)
            # and recovers-inceptions intentionally share a prev_public_key_hash
            # with main-line structure; exclude them from the blunt uniqueness rule.
            if (
                not is_recovers_inception(transaction)
                and not is_branch_root_entry(transaction)
                and transaction.prev_public_key_hash in self.prev_public_key_hashes
            ):
                raise KELHashCollectionException(
                    "Duplication key event in mempool. Removing. (prev_public_key_hash)"
                )
            if not is_recovers_inception(transaction) and not is_branch_root_entry(
                transaction
            ):
                self.prev_public_key_hashes[
                    transaction.prev_public_key_hash
                ] = transaction


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
        use_mempool=False,
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
                block_index=block_index, batch_txns=batch_txns, use_mempool=use_mempool
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
        # Only the tip of key_event.txn's own KEL is ever needed below (every
        # use is entire_log[-1]), so get_latest is used instead of rebuilding
        # the whole chain.
        latest_entry = await KeyEventLog.get_latest(key_event.txn.public_key)
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
                    or key_event.txn.outputs[0].to == latest_entry.prerotated_key_hash
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
                        latest_entry
                        and key_event.txn.outputs[0].to
                        == latest_entry.prerotated_key_hash
                    )
                )
                and key_event.txn.prev_public_key_hash
            ):
                # If the mempool parent is itself an UNCONFIRMED key event
                # (it carries a relationship), then key_event is the confirming
                # child of that unconfirmed event, not the direct confirming
                # child of the base.  The lineage is
                # base -> unconfirmed(parent) -> confirming(key_event).  Thread
                # the parent in as the unconfirmed_key_event and resolve the
                # grandparent as the base so the standard scenarios apply.
                if (
                    parent_event.flag == KeyEventFlag.UNCONFIRMED
                    or parent_event.txn.relationship
                ):
                    parent_event.flag = KeyEventFlag.UNCONFIRMED
                    parent_event.path = "1.5b"
                    key_event.flag = KeyEventFlag.CONFIRMING
                    key_event.path = "1.5b"
                    self.unconfirmed_key_event = parent_event
                    self.confirming_key_event = key_event
                    grandparent = await parent_event.get_onchain_parent()
                    if not grandparent and use_mempool:
                        grandparent = await parent_event.get_mempool_parent()

                    if not grandparent and batch_txns:
                        grandparent = next(
                            (
                                t
                                for t in batch_txns
                                if t.public_key_hash
                                == parent_event.txn.prev_public_key_hash
                            ),
                            None,
                        )
                    if grandparent and grandparent["key_event"]:
                        grandparent["key_event"].path = "1.5b"
                        self.base_key_event = grandparent["key_event"]
                        self.path = "1.5b"
                    else:
                        raise FatalKeyEventException(
                            f"Unconfirmed key event has no on-chain or mempool base key event. {key_event.txn.transaction_signature}",
                            other_txn_to_delete=hash_collection.prerotated_key_hashes.get(
                                key_event.txn.twice_prerotated_key_hash
                            ),
                        )
                else:
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
                    # Check batch_txns for the parent — it may be in the same
                    # block being validated, not yet on-chain.
                    parent_in_batch = None
                    if batch_txns:
                        parent_in_batch = next(
                            (
                                t
                                for t in batch_txns
                                if t.public_key_hash
                                == unconfirmed_key_event.txn.prev_public_key_hash
                            ),
                            None,
                        )
                    if parent_in_batch:
                        self.base_key_event = KeyEvent(
                            parent_in_batch,
                            flag=(
                                KeyEventFlag.INCEPTION
                                if not parent_in_batch.prev_public_key_hash
                                or is_recovers_inception(parent_in_batch)
                                else KeyEventFlag.CONFIRMING
                            ),
                            status=KeyEventChainStatus.MEMPOOL,
                            path="2.2",
                        )
                    elif use_mempool and block_index is None:
                        mempool_base = await unconfirmed_key_event.get_mempool_parent()
                        if mempool_base and mempool_base["key_event"]:
                            mempool_base["key_event"].path = "2.2"
                            self.base_key_event = mempool_base["key_event"]
                        else:
                            raise KELException(
                                "No on-chain or mempool key event found for unconfirmed key event.",
                                txn=key_event.txn,
                            )
                    else:
                        raise KELException(
                            "No on-chain key event found for unconfirmed key event.",
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
                    # Check batch_txns for the parent — it may be in the same
                    # block being validated, not yet tracked in hash_collection.
                    parent_in_batch = None
                    if batch_txns:
                        parent_in_batch = next(
                            (
                                t
                                for t in batch_txns
                                if t.public_key_hash
                                == key_event.txn.prev_public_key_hash
                            ),
                            None,
                        )
                    if parent_in_batch:
                        self.base_key_event = KeyEvent(
                            parent_in_batch,
                            flag=(
                                KeyEventFlag.INCEPTION
                                if not parent_in_batch.prev_public_key_hash
                                or is_recovers_inception(parent_in_batch)
                                else KeyEventFlag.CONFIRMING
                            ),
                            status=KeyEventChainStatus.MEMPOOL,
                            path="2.5",
                        )
                    elif use_mempool and block_index is None:
                        mempool_base = await key_event.get_mempool_parent()
                        if mempool_base and mempool_base["key_event"]:
                            mempool_base["key_event"].path = "2.5"
                            self.base_key_event = mempool_base["key_event"]
                        else:
                            raise KELException(
                                "No on-chain or mempool key event found for unconfirmed key event.",
                                txn=key_event.txn,
                            )
                    else:
                        raise KELException(
                            "No on-chain key event found for unconfirmed key event.",
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
            self.confirming_key_event.verify_confirming(latest_entry)
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
            self.base_key_event.verify_confirming(latest_entry, onchain=True)
            self.confirming_key_event.verify_confirming(latest_entry)
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
            self.confirming_key_event.verify_confirming(latest_entry)
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
            self.confirming_key_event.verify_confirming(latest_entry)
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
            self.base_key_event.verify_confirming(latest_entry, onchain=True)
            self.unconfirmed_key_event.verify_unconfirmed()
            self.confirming_key_event.verify_confirming(latest_entry)
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
            self.confirming_key_event.verify_confirming(latest_entry)
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
            self.confirming_key_event.verify_confirming(latest_entry)
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
            self.base_key_event.verify_confirming(latest_entry)
            self.confirming_key_event.verify_confirming(latest_entry)
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
            self.base_key_event.verify_confirming(latest_entry)
            self.unconfirmed_key_event.verify_unconfirmed()
            self.confirming_key_event.verify_confirming(latest_entry)
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
        public_key,
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

        log = await KeyEventLog.get_log(
            public_key,
        )

        result = KELResult(log)
        if hasattr(config, "key_log_debug") and config.key_log_debug:
            config.app_log.debug(
                "build_from_public_key done public_key=%s log_len=%d",
                public_key[:16],
                len(log),
            )

        return result

    @staticmethod
    async def get_log(
        public_key,
    ):
        """Return the ordered KEL for *public_key* and a given username"""
        config = Config()
        latest = await KeyEventLog.get_latest(public_key=public_key, onchain_only=False)
        if latest is None:
            return KELResult([])
        cursor = config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        "transactions.public_key_hash": latest.inception_public_key_hash
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        "transactions.public_key_hash": latest.inception_public_key_hash
                    }
                },
                {"$sort": {"transactions.counter": -1}},
            ]
        )
        rows = await cursor.to_list(length=None)
        log = [Transaction.from_dict(row["transactions"]) for row in rows]

        mempool_cursor = config.mongo.async_db.miner_transactions.find(
            {"inception_public_key_hash": latest.inception_public_key_hash}
        )
        async for doc in mempool_cursor:
            log.append(Transaction.from_dict(doc))

        return log

    @staticmethod
    async def is_same_kel(public_key_hash_a, public_key_hash_b, onchain_only=False):
        """Return True if *public_key_a* and *public_key_b* are in the same
        KEL (i.e., share the same inception), False otherwise.

        This is a convenience wrapper around ``get_inception`` that avoids
        building the full KELs for both keys.
        """
        inception_a = await KeyEventLog.get_inception(
            address=public_key_hash_a, onchain_only=onchain_only
        )
        inception_b = await KeyEventLog.get_inception(
            address=public_key_hash_b, onchain_only=onchain_only
        )
        if inception_a is None or inception_b is None:
            return False
        return getattr(inception_a, "inception_public_key_hash", None) == getattr(
            inception_b, "inception_public_key_hash", None
        )

    @staticmethod
    async def get_latest(
        public_key, onchain_only=False, follow_recovery=True, segment_only=False
    ):
        """Return the latest (tip) KEL entry for *public_key* — the mirror
        image of ``get_inception``.

        Locates the entry whose own ``public_key_hash`` equals this key's
        address (checking ``blocks`` then ``miner_transactions``, exactly
        like a single step of the forward walk).  If that entry is already
        tagged with ``inception_public_key_hash``/``counter``, the tip is
        fetched directly via :meth:`_latest_from_inception_tag` — a single
        sorted query, no walking required.

        If the entry has not been tagged yet, ``get_inception`` is used to
        walk back to the true inception, the KEL is then walked forward and
        tagged end to end (the same bookkeeping ``build_from_public_key``
        performs), and the last entry reached is returned.  Once this has
        run once for a given KEL, every subsequent ``get_latest`` call for
        any key in that KEL hits the fast path above.
        """
        config = Config()
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))

        result = config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {BlocksQueryFields.PUBLIC_KEY_HASH.value: address},
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {BlocksQueryFields.PUBLIC_KEY_HASH.value: address},
                },
            ]
        )
        res = await result.to_list(length=1)
        if res:
            txn = Transaction.from_dict(res[0]["transactions"])
        else:
            if onchain_only:
                return None
            result_mempool = await config.mongo.async_db.miner_transactions.find_one(
                {MempoolQueryFields.PUBLIC_KEY_HASH.value: address},
            )
            if not result_mempool:
                return None
            txn = Transaction.from_dict(result_mempool)
            txn.mempool = True

        if (
            getattr(txn, "inception_public_key_hash", None)
            and getattr(txn, "counter", None) is not None
        ):
            if hasattr(config, "key_log_debug") and config.key_log_debug:
                config.app_log.debug(
                    "get_latest public_key=%s address=%s already tagged "
                    "inception_public_key_hash=%s counter=%s — fast lookup",
                    public_key[:16],
                    address,
                    txn.inception_public_key_hash,
                    txn.counter,
                )
            latest = await KeyEventLog._latest_from_inception_tag(
                txn.inception_public_key_hash, onchain_only=onchain_only
            )
            if latest is not None:
                walked = await KeyEventLog._walk_forward(
                    latest, public_key, onchain_only=onchain_only
                )
                return walked
            # Tag existed but the sorted lookup came up empty (shouldn't
            # normally happen) — fall through to the slow path below.

        if hasattr(config, "key_log_debug") and config.key_log_debug:
            config.app_log.debug(
                "get_latest public_key=%s address=%s untagged — walking back "
                "via get_inception to orient and tag the KEL",
                public_key[:16],
                address,
            )
        inception = await KeyEventLog.get_inception(
            public_key,
            onchain_only=onchain_only,
            follow_recovery=follow_recovery,
            segment_only=segment_only,
        )
        if inception is None:
            return txn

        if hasattr(config, "key_log_debug") and config.key_log_debug:
            config.app_log.debug(
                "get_latest public_key=%s inception_tagged=%s — walking forward "
                "and tagging every entry",
                public_key[:16],
                bool(getattr(inception, "inception_public_key_hash", None)),
            )
        return await KeyEventLog._walk_forward(
            inception,
            public_key,
            onchain_only=onchain_only,
            follow_recovery=follow_recovery,
        )

    @staticmethod
    async def _walk_forward(
        start_entry, public_key, onchain_only=False, follow_recovery=True
    ):
        """Walk forward from *start_entry* via ``prerotated_key_hash`` links,
        tagging any untagged successors until the chain is exhausted.

        If *start_entry* is not yet tagged (no ``inception_public_key_hash``),
        it is tagged as the inception (counter=0) before the walk begins.
        Already-tagged entries (e.g. the tip returned by
        ``_latest_from_inception_tag``) are not retagged — the walk starts
        from ``start_entry.prerotated_key_hash`` and continues with
        ``start_entry.counter + 1``, ``start_entry.counter + 2``, etc.

        Returns the final tip entry reached (which may be *start_entry*
        itself if there are no untagged successors).
        """
        config = Config()
        inception_pkh = getattr(start_entry, "inception_public_key_hash", None)
        counter = getattr(start_entry, "counter", None)

        if inception_pkh is None or counter is None:
            inception_pkh = start_entry.public_key_hash
            start_entry.inception_public_key_hash = inception_pkh
            start_entry.counter = 0
            await KeyEventLog._tag_kel_entry_in_mongo(start_entry)
            counter = 0

        txn = start_entry
        forward_iter = 0

        while True:
            forward_iter += 1
            address = txn.prerotated_key_hash

            result = config.mongo.async_db.blocks.aggregate(
                [
                    {
                        "$match": {BlocksQueryFields.PUBLIC_KEY_HASH.value: address},
                    },
                    {"$unwind": "$transactions"},
                    {
                        "$match": {BlocksQueryFields.PUBLIC_KEY_HASH.value: address},
                    },
                ]
            )
            res = await result.to_list(length=1)
            if res:
                candidate = Transaction.from_dict(res[0]["transactions"])
                candidate_inception = getattr(
                    candidate, "inception_public_key_hash", None
                )
                if candidate_inception == inception_pkh:
                    if hasattr(config, "key_log_debug") and config.key_log_debug:
                        config.app_log.debug(
                            "_walk_forward iter=%d address=%s "
                            "already_tagged counter=%d — stop",
                            forward_iter,
                            address,
                            candidate.counter,
                        )
                    break
                if candidate_inception is not None:
                    if hasattr(config, "key_log_debug") and config.key_log_debug:
                        config.app_log.debug(
                            "_walk_forward iter=%d address=%s "
                            "different_inception=%s — stop",
                            forward_iter,
                            address,
                            candidate_inception[:16],
                        )
                    break
                else:
                    counter += 1
                    candidate.inception_public_key_hash = inception_pkh
                    candidate.counter = counter
                    await KeyEventLog._tag_kel_entry_in_mongo(candidate)
                    if hasattr(config, "key_log_debug") and config.key_log_debug:
                        config.app_log.debug(
                            "_walk_forward iter=%d address=%s "
                            "found_onchain txn=%s counter=%d",
                            forward_iter,
                            address,
                            candidate.transaction_signature[:16],
                            counter,
                        )
                    txn = candidate
                    continue

            if not onchain_only:
                result_mempool = (
                    await config.mongo.async_db.miner_transactions.find_one(
                        {MempoolQueryFields.PUBLIC_KEY_HASH.value: address},
                    )
                )
                if result_mempool:
                    candidate = Transaction.from_dict(result_mempool)
                    candidate.mempool = True
                    candidate_inception = getattr(
                        candidate, "inception_public_key_hash", None
                    )
                    if candidate_inception == inception_pkh:
                        if hasattr(config, "key_log_debug") and config.key_log_debug:
                            config.app_log.debug(
                                "_walk_forward iter=%d address=%s "
                                "mempool already_tagged counter=%d — stop",
                                forward_iter,
                                address,
                                candidate.counter,
                            )
                        break
                    if candidate_inception is not None:
                        if hasattr(config, "key_log_debug") and config.key_log_debug:
                            config.app_log.debug(
                                "_walk_forward iter=%d address=%s "
                                "mempool different_inception=%s — stop",
                                forward_iter,
                                address,
                                candidate_inception[:16],
                            )
                        break
                    counter += 1
                    candidate.inception_public_key_hash = inception_pkh
                    candidate.counter = counter
                    await KeyEventLog._tag_kel_entry_in_mongo(candidate)
                    if hasattr(config, "key_log_debug") and config.key_log_debug:
                        config.app_log.debug(
                            "_walk_forward iter=%d address=%s "
                            "found_mempool txn=%s counter=%d",
                            forward_iter,
                            address,
                            candidate.transaction_signature[:16],
                            counter,
                        )
                    txn = candidate
                    continue

            if follow_recovery:
                successor = await KeyEventLog.find_recovery_successor(
                    txn.public_key_hash, onchain_only=onchain_only
                )
                if successor is not None:
                    counter += 1
                    successor.inception_public_key_hash = inception_pkh
                    successor.counter = counter
                    await KeyEventLog._tag_kel_entry_in_mongo(successor)
                    if hasattr(config, "key_log_debug") and config.key_log_debug:
                        config.app_log.debug(
                            "_walk_forward iter=%d address=%s "
                            "follow_recovery successor=%s counter=%d",
                            forward_iter,
                            address,
                            successor.transaction_signature[:16],
                            counter,
                        )
                    txn = successor
                    continue

            if hasattr(config, "key_log_debug") and config.key_log_debug:
                config.app_log.debug(
                    "_walk_forward iter=%d address=%s chain_exhausted",
                    forward_iter,
                    address,
                )
            break

        return txn

    @staticmethod
    async def _latest_from_inception_tag(inception_pkh, onchain_only=False):
        """Return the highest-``counter`` entry tagged with *inception_pkh*.

        Checks ``blocks`` (confirmed, sorted by ``counter`` descending) and,
        unless *onchain_only*, ``miner_transactions`` (mempool) — returning
        whichever of the two has the higher counter.  This is the fast path
        ``get_latest`` uses once a KEL has been fully tagged: no walking is
        needed, just one sorted query per collection.

        Entries with a non-empty ``branch_public_key_hash_path`` are ignored so
        peer-branch lineage cannot steal the main tip via shared inception and
        counter values.  Legacy missing/empty path means main chain.
        """
        config = Config()
        latest = None

        # Main tip only: empty / missing branch_public_key_hash_path.
        main_path_or = {
            "$or": [
                {"transactions.branch_public_key_hash_path": {"$exists": False}},
                {"transactions.branch_public_key_hash_path": None},
                {"transactions.branch_public_key_hash_path": []},
                {"transactions.branch_public_key_hash_path": ""},
            ]
        }

        cursor = config.mongo.async_db.blocks.aggregate(
            [
                {"$match": {"transactions.inception_public_key_hash": inception_pkh}},
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        "transactions.inception_public_key_hash": inception_pkh,
                        **main_path_or,
                    }
                },
                {"$sort": {"transactions.counter": -1}},
                {"$limit": 1},
            ]
        )
        rows = await cursor.to_list(length=1)
        if rows:
            latest = Transaction.from_dict(rows[0]["transactions"])

        if not onchain_only:
            mempool_txn = await config.mongo.async_db.miner_transactions.find_one(
                {
                    "inception_public_key_hash": inception_pkh,
                    "$or": [
                        {"branch_public_key_hash_path": {"$exists": False}},
                        {"branch_public_key_hash_path": None},
                        {"branch_public_key_hash_path": []},
                        {"branch_public_key_hash_path": ""},
                    ],
                },
                sort=[("counter", -1)],
            )
            if mempool_txn:
                mempool_txn = Transaction.from_dict(mempool_txn)
                mempool_txn.mempool = True
                if latest is None or mempool_txn.counter > latest.counter:
                    latest = mempool_txn

        return latest

    @staticmethod
    async def get_inception(
        public_key=None,
        address=None,
        onchain_only=False,
        follow_recovery=True,
        segment_only=False,
    ):
        """Return the inception transaction for *public_key*.

        Fast path: if any entry for this public_key already has
        ``inception_public_key_hash`` set, query for ``counter == 0`` on
        that tag and return the inception directly.

        Slow path: walk backward via ``prev_public_key_hash`` to find the
        inception.  The caller is responsible for tagging the full KEL after
        the forward walk.
        """
        config = Config()
        if not public_key and not address:
            raise ValueError("Either public_key or address must be provided")
        if not address:
            address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))

        if hasattr(config, "key_log_debug") and config.key_log_debug:
            config.app_log.debug(
                "get_inception: public_key=%s address=%s onchain_only=%s",
                public_key[:16] if public_key else None,
                address,
                onchain_only,
            )

        tagged = await config.mongo.async_db.blocks.find_one(
            {
                BlocksQueryFields.PUBLIC_KEY_HASH.value: address,
                "transactions.inception_public_key_hash": {"$exists": True},
            },
            {"transactions": 1},
        )
        if isinstance(tagged, dict) and tagged.get("transactions"):
            tagged_txns = [
                t
                for t in tagged["transactions"]
                if t.get("inception_public_key_hash") == address
            ]
            inception_pkh = None
            if not tagged_txns:
                if hasattr(config, "key_log_debug") and config.key_log_debug:
                    config.app_log.debug(
                        "get_inception: fast_path block matched but no transaction has inception_public_key_hash"
                    )
                tagged = None
            else:
                tagged_txn = tagged_txns[0]
                inception_pkh = tagged_txn.get("inception_public_key_hash")
                if hasattr(config, "key_log_debug") and config.key_log_debug:
                    config.app_log.debug(
                        "get_inception: fast_path tagged_txn=%s inception_pkh=%s",
                        tagged_txn.get("transaction_signature", "?")[:16],
                        inception_pkh[:16] if inception_pkh else None,
                    )
            if inception_pkh:
                inception_doc = await config.mongo.async_db.blocks.find_one(
                    {
                        "transactions.inception_public_key_hash": inception_pkh,
                        "transactions.counter": 0,
                    },
                    {"transactions": 1},
                )
                if isinstance(inception_doc, dict) and inception_doc.get(
                    "transactions"
                ):
                    matching_txns = [
                        t
                        for t in inception_doc["transactions"]
                        if t.get("inception_public_key_hash") == inception_pkh
                        and t.get("counter") == 0
                    ]
                    if not matching_txns:
                        if hasattr(config, "key_log_debug") and config.key_log_debug:
                            config.app_log.debug(
                                "get_inception: fast_path no matching inception txn found in block"
                            )
                        inception = None
                    else:
                        inception = Transaction.from_dict(matching_txns[0])
                        inception.inception_public_key_hash = inception_pkh
                        if hasattr(config, "key_log_debug") and config.key_log_debug:
                            config.app_log.debug(
                                "get_inception: fast_path returning inception txn=%s public_key=%s",
                                inception.transaction_signature[:16],
                                inception.public_key[:16]
                                if inception.public_key
                                else None,
                            )
                        if inception.public_key != public_key:
                            config.app_log.warning(
                                "get_inception: fast_path inception public_key=%s does not match requested public_key=%s — discarding",
                                inception.public_key[:32]
                                if inception.public_key
                                else None,
                                public_key[:32] if public_key else None,
                            )
                            inception = None
                    return inception

        if hasattr(config, "key_log_debug") and config.key_log_debug:
            config.app_log.debug("get_inception: fast_path miss, walking backward")

        while True:
            result = config.mongo.async_db.blocks.aggregate(
                [
                    {
                        "$match": {BlocksQueryFields.PUBLIC_KEY_HASH.value: address},
                    },
                    {"$unwind": "$transactions"},
                    {
                        "$match": {BlocksQueryFields.PUBLIC_KEY_HASH.value: address},
                    },
                ]
            )
            res = await result.to_list(length=1)
            if res:
                txn = Transaction.from_dict(res[0]["transactions"])
                if hasattr(config, "key_log_debug") and config.key_log_debug:
                    config.app_log.debug(
                        "get_inception: slow_path onchain txn=%s public_key=%s prev_pkh=%s",
                        txn.transaction_signature[:16],
                        txn.public_key[:16] if txn.public_key else None,
                        txn.prev_public_key_hash[:16]
                        if txn.prev_public_key_hash
                        else None,
                    )
                if not txn.prev_public_key_hash or (
                    segment_only and is_recovers_inception(txn)
                ):
                    await config.mongo.async_db.blocks.update_one(
                        {"transactions.id": txn.transaction_signature},
                        {
                            "$set": {
                                "transactions.$[elem].inception_public_key_hash": txn.public_key_hash,
                                "transactions.$[elem].counter": 0,
                            }
                        },
                        array_filters=[{"elem.id": txn.transaction_signature}],
                    )
                    if hasattr(config, "key_log_debug") and config.key_log_debug:
                        config.app_log.debug(
                            "get_inception: slow_path returning inception (onchain, no prev_pkh)"
                        )
                    return txn
                address = txn.prev_public_key_hash
            else:
                if onchain_only:
                    if hasattr(config, "key_log_debug") and config.key_log_debug:
                        config.app_log.debug(
                            "get_inception: slow_path onchain_only miss"
                        )
                    return None
                result_mempool = (
                    await config.mongo.async_db.miner_transactions.find_one(
                        {MempoolQueryFields.PUBLIC_KEY_HASH.value: address},
                    )
                )
                if not result_mempool:
                    if hasattr(config, "key_log_debug") and config.key_log_debug:
                        config.app_log.debug("get_inception: slow_path mempool miss")
                    return None
                txn = Transaction.from_dict(result_mempool)
                txn.mempool = True
                if hasattr(config, "key_log_debug") and config.key_log_debug:
                    config.app_log.debug(
                        "get_inception: slow_path mempool txn=%s public_key=%s prev_pkh=%s",
                        txn.transaction_signature[:16],
                        txn.public_key[:16] if txn.public_key else None,
                        txn.prev_public_key_hash[:16]
                        if txn.prev_public_key_hash
                        else None,
                    )
                if not txn.prev_public_key_hash or (
                    segment_only and is_recovers_inception(txn)
                ):
                    if hasattr(config, "key_log_debug") and config.key_log_debug:
                        config.app_log.debug(
                            "get_inception: slow_path returning inception (mempool, no prev_pkh)"
                        )
                    if txn.public_key != public_key:
                        if hasattr(config, "key_log_debug") and config.key_log_debug:
                            config.app_log.debug(
                                "get_inception: slow_path mempool inception public_key=%s does not match requested public_key=%s — discarding",
                                txn.public_key[:32] if txn.public_key else None,
                                public_key[:32] if public_key else None,
                            )
                        return None
                    await config.mongo.async_db.miner_transactions.update_one(
                        {"id": txn.transaction_signature},
                        {
                            "$set": {
                                "inception_public_key_hash": txn.public_key_hash,
                                "counter": 0,
                            }
                        },
                    )
                    return txn
                address = txn.prev_public_key_hash

    @staticmethod
    async def _tag_kel_entry_in_mongo(entry):
        """Persist the node-side KEL bookkeeping fields for *entry* so that
        future ``build_from_public_key`` walks can use them as short-cuts.

        Writes ``inception_public_key_hash``, ``counter``, and optional
        ``branch_public_key_hash_path`` to whichever collection holds the
        canonical copy of the transaction: ``miner_transactions`` for mempool
        entries, ``blocks`` for confirmed entries.  ``key_event_log`` is
        intentionally excluded because it can contain inter-anchor rotations
        whose counters would be out of sequence with the main KEL.
        """
        config = Config()
        try:
            set_fields = {
                "inception_public_key_hash": entry.inception_public_key_hash,
                "counter": entry.counter,
            }
            path = getattr(entry, "branch_public_key_hash_path", None)
            if path is not None:
                set_fields["branch_public_key_hash_path"] = path
            if getattr(entry, "mempool", False):
                await config.mongo.async_db.miner_transactions.update_one(
                    {"id": entry.transaction_signature},
                    {"$set": set_fields},
                )
            else:
                block_set = {
                    f"transactions.$[elem].{k}": v for k, v in set_fields.items()
                }
                await config.mongo.async_db.blocks.update_one(
                    {"transactions.id": entry.transaction_signature},
                    {"$set": block_set},
                    array_filters=[{"elem.id": entry.transaction_signature}],
                )
        except Exception:
            pass
