"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Branch announcements — embedded in main-KEL rotation transactions.

A BranchAnnouncement consumes one main unconfirmed+confirming rotation and
commits the first public peer-branch signer and its next hop on-chain:

    relationship = {
        "branch": {
            "prerotated_key_hash": "<addr(Kp0)>",
            "twice_prerotated_key_hash": "<addr(Kp1)>",
            "type": "livestream"   # omitted for untyped / peer branches
        }
    }

where:
  Kp0 = derive(K_n, peer_factor)   # first public branch signer
  Kp1 = derive(Kp0, peer_factor)   # first branch entry's prerotated_key_hash

Off-chain first branch entry:
  public_key_hash      = relationship.prerotated_key_hash   # addr(Kp0)
  prerotated_key_hash  = relationship.twice_prerotated_key_hash  # addr(Kp1)
  prev_public_key_hash = main confirming.public_key_hash
"""

BRANCH_TYPE_PEER = "peer"
BRANCH_TYPE_LIVESTREAM = "livestream"
KNOWN_BRANCH_TYPES = frozenset({BRANCH_TYPE_PEER, BRANCH_TYPE_LIVESTREAM, ""})


def normalize_branch_type(type="") -> str:
    """Return canonical branch type. Untyped and ``peer`` become ``""``.

    Unknown types raise ``ValueError``.
    """
    if type is None:
        t = ""
    else:
        t = str(type).strip().lower()
    if t in ("", BRANCH_TYPE_PEER):
        return ""
    if t == BRANCH_TYPE_LIVESTREAM:
        return BRANCH_TYPE_LIVESTREAM
    raise ValueError(f"unknown branch type: {type!r}")


class BranchAnnouncement:
    """On-chain peer-branch root commitment embedded in a main KEL rotation.

    Wire format::

        {"branch": {
            "prerotated_key_hash": "<addr(Kp0)>",
            "twice_prerotated_key_hash": "<addr(Kp1)>"
        }}
    """

    RELATIONSHIP_KEY = "branch"

    def __init__(
        self, prerotated_key_hash, twice_prerotated_key_hash, type="", **kwargs
    ):
        if not prerotated_key_hash or not isinstance(prerotated_key_hash, str):
            raise ValueError(
                "prerotated_key_hash is required and must be an address string"
            )
        if not twice_prerotated_key_hash or not isinstance(
            twice_prerotated_key_hash, str
        ):
            raise ValueError(
                "twice_prerotated_key_hash is required and must be an address string"
            )
        self.prerotated_key_hash = prerotated_key_hash
        self.twice_prerotated_key_hash = twice_prerotated_key_hash
        self.branch_type = normalize_branch_type(type)
        self.extra_fields = {k: v for k, v in kwargs.items() if k != "type"}

    @staticmethod
    def get_string(value) -> str:
        if value is None:
            return ""
        return str(value)

    def is_livestream(self) -> bool:
        return self.branch_type == BRANCH_TYPE_LIVESTREAM

    def to_dict(self) -> dict:
        d = {
            "prerotated_key_hash": self.prerotated_key_hash,
            "twice_prerotated_key_hash": self.twice_prerotated_key_hash,
        }
        if self.branch_type:
            d["type"] = self.branch_type
        if self.extra_fields:
            d.update(self.extra_fields)
        return d

    def to_string(self) -> str:
        """Deterministic preimage for relationship_hash.

        Concatenates prerotated_key_hash then twice_prerotated_key_hash.
        Untyped / peer branches keep that historical preimage. Non-default
        ``type`` is appended.
        """
        preimage = self.get_string(self.prerotated_key_hash) + self.get_string(
            self.twice_prerotated_key_hash
        )
        if self.branch_type:
            preimage += self.branch_type
        return preimage

    @staticmethod
    def from_dict(data: dict) -> "BranchAnnouncement":
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        if "prerotated_key_hash" not in data:
            raise ValueError("prerotated_key_hash field is required")
        if "twice_prerotated_key_hash" not in data:
            raise ValueError("twice_prerotated_key_hash field is required")
        return BranchAnnouncement(**data)

    @staticmethod
    def from_relationship(rel: dict) -> "BranchAnnouncement":
        if not isinstance(rel, dict) or BranchAnnouncement.RELATIONSHIP_KEY not in rel:
            raise ValueError("relationship does not contain a 'branch' key")
        return BranchAnnouncement.from_dict(rel[BranchAnnouncement.RELATIONSHIP_KEY])

    def __repr__(self):
        extra = ""
        if self.branch_type:
            extra = f", type={self.branch_type!r}"
        return (
            f"BranchAnnouncement(prerotated_key_hash="
            f"{self.prerotated_key_hash!r}, twice_prerotated_key_hash="
            f"{self.twice_prerotated_key_hash!r}{extra})"
        )
