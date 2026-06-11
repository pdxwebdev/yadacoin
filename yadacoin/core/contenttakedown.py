"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

# ── Content Takedown Announcement ────────────────────────────────────────────
#
# A ContentTakedownAnnouncement is a structured on-chain request to clear the
# ``relationship`` field of a specific transaction.  Nodes process the request
# according to their local ``content_takedown_policy`` (configured in
# config.json).
#
# On-chain wire format:
#   {"content_takedown": {"transaction_id": "<hex txn sig>", "reason_code": "<code>"}}
#
# Nodes respond to takedown requests in one of three ways, depending on their
# policy for the given reason_code:
#
#   auto_comply          – immediately clear the relationship field in the
#                          stored block document.  Default for codes that
#                          correspond to illegal content (CSAM, terrorism, …).
#
#   comply_and_save      – clear the relationship field AND archive the
#                          original relationship value locally in the
#                          ``content_takedown_archive`` collection for later
#                          review.  Disabled by default; must be explicitly
#                          listed under "content_takedown_policy.comply_and_save"
#                          in config.json.
#
#   no_comply            – ignore the request.  Must be explicitly listed
#                          under "content_takedown_policy.no_comply" in
#                          config.json.  Never the default.

from enum import Enum
from typing import FrozenSet


class TakedownReasonCode(Enum):
    """Standardised reason codes for content takedown requests.

    Values are short lowercase strings suitable for on-chain storage.
    """

    # ── Illegal / criminal content ────────────────────────────────────────
    CSAM = "csam"
    """Child Sexual Abuse Material."""

    TERRORISM = "terrorism"
    """Terrorist content or violent extremist propaganda."""

    INCITEMENT_TO_VIOLENCE = "incitement_to_violence"
    """Direct incitement to violence against persons or groups."""

    HUMAN_TRAFFICKING = "human_trafficking"
    """Content that facilitates or promotes human trafficking."""

    DRUG_TRAFFICKING = "drug_trafficking"
    """Content that facilitates or promotes illegal drug trafficking."""

    WEAPONS_TRAFFICKING = "weapons_trafficking"
    """Content that facilitates or promotes illegal weapons trafficking."""

    # ── Intellectual property / legal ────────────────────────────────────
    COPYRIGHT = "copyright"
    """DMCA / copyright infringement."""

    TRADEMARK = "trademark"
    """Trademark infringement."""

    DEFAMATION = "defamation"
    """Defamatory content."""

    PRIVACY_VIOLATION = "privacy_violation"
    """Privacy violation (e.g. GDPR right-to-erasure, unauthorised PII)."""

    # ── Abuse / harassment ────────────────────────────────────────────────
    DOXXING = "doxxing"
    """Publication of private identifying information without consent."""

    HARASSMENT = "harassment"
    """Targeted harassment or cyberstalking."""

    HATE_SPEECH = "hate_speech"
    """Content that promotes hatred against protected groups."""

    NONCONSENSUAL_INTIMATE_IMAGES = "ncii"
    """Non-consensual intimate images (revenge porn)."""

    SPAM = "spam"
    """Unsolicited bulk content / spam."""

    MALWARE = "malware"
    """Content that distributes or links to malware."""

    PHISHING = "phishing"
    """Phishing or credential-harvesting content."""

    # ── Regulatory ────────────────────────────────────────────────────────
    SANCTIONS = "sanctions"
    """Content or parties subject to international sanctions (e.g. OFAC)."""

    NATIONAL_SECURITY = "national_security"
    """Content posing a national-security risk."""

    COURT_ORDER = "court_order"
    """Removal mandated by a court order."""


# Content takedown transactions must include a non-zero fee.
# This requires the requester to spend an input, which is sufficient friction
# to deter spam without imposing a hard minimum amount.
MINIMUM_TAKEDOWN_FEE: float = 0.0

# Reason codes that nodes auto-comply with by default.
# All known reason codes are included so that nodes are maximally compliant
# out of the box.  Operators who wish to limit compliance can override this
# by setting "content_takedown_policy.auto_comply" in config.json.
DEFAULT_AUTO_COMPLY: FrozenSet[str] = frozenset(r.value for r in TakedownReasonCode)

# comply_and_save is deliberately empty by default; operators must opt in.
DEFAULT_COMPLY_AND_SAVE: FrozenSet[str] = frozenset()

# no_comply is deliberately empty by default; operators must explicitly opt out
# of compliance by listing reason codes here or in config.json.
DEFAULT_NO_COMPLY: FrozenSet[str] = frozenset()


class ContentTakedownAnnouncement:
    """A takedown request stored in a transaction relationship field.

    Instructs nodes to clear the ``relationship`` field of the transaction
    identified by ``transaction_id``.  The ``reason_code`` determines which
    compliance path each node takes based on its ``content_takedown_policy``.

    On-chain format: {"content_takedown": <to_dict()>}

    Fields
    ------
    transaction_id : hex transaction signature of the transaction to take down
    reason_code    : TakedownReasonCode describing why the takedown is requested
    """

    def __init__(self, transaction_id: str, reason_code, **kwargs):
        if not transaction_id or not isinstance(transaction_id, str):
            raise ValueError("transaction_id is required and must be a string")
        if not reason_code:
            raise ValueError("reason_code is required")

        if isinstance(reason_code, TakedownReasonCode):
            self.reason_code = reason_code
        else:
            try:
                self.reason_code = TakedownReasonCode(str(reason_code))
            except ValueError:
                valid = [r.value for r in TakedownReasonCode]
                raise ValueError(
                    f"Invalid reason_code: {reason_code!r}. " f"Must be one of: {valid}"
                )

        self.transaction_id = str(transaction_id)
        self.extra_fields = {k: v for k, v in kwargs.items()}

    @staticmethod
    def from_dict(data: dict) -> "ContentTakedownAnnouncement":
        """Create from the inner dict (value of relationship["content_takedown"])."""
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        for field in ("transaction_id", "reason_code"):
            if field not in data:
                raise ValueError(f"{field} is required")
        return ContentTakedownAnnouncement(**data)

    @staticmethod
    def from_relationship(relationship: dict) -> "ContentTakedownAnnouncement":
        """Create from the top-level relationship dict {"content_takedown": ...}."""
        if not isinstance(relationship, dict) or "content_takedown" not in relationship:
            raise ValueError("relationship must contain a 'content_takedown' key")
        return ContentTakedownAnnouncement.from_dict(relationship["content_takedown"])

    def to_dict(self) -> dict:
        """Serialise for on-chain storage."""
        result = {
            "transaction_id": self.transaction_id,
            "reason_code": self.reason_code.value,
        }
        if self.extra_fields:
            result.update(self.extra_fields)
        return result

    def get_string(self, p) -> str:
        return "" if p is None else str(p)

    def to_string(self) -> str:
        """Deterministic preimage for the relationship_hash."""
        return self.transaction_id + self.reason_code.value

    def __repr__(self) -> str:
        return (
            f"ContentTakedownAnnouncement("
            f"transaction_id={self.transaction_id!r}, "
            f"reason_code={self.reason_code.value!r})"
        )
