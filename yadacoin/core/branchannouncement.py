"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

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


class BranchAnnouncement:
    """On-chain peer-branch root commitment embedded in a main KEL rotation.

    Wire format::

        {"branch": {
            "prerotated_key_hash": "<addr(Kp0)>",
            "twice_prerotated_key_hash": "<addr(Kp1)>"
        }}
    """

    RELATIONSHIP_KEY = "branch"

    def __init__(self, prerotated_key_hash, twice_prerotated_key_hash, **kwargs):
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
        self.extra_fields = {k: v for k, v in kwargs.items()}

    @staticmethod
    def get_string(value) -> str:
        if value is None:
            return ""
        return str(value)

    def to_dict(self) -> dict:
        d = {
            "prerotated_key_hash": self.prerotated_key_hash,
            "twice_prerotated_key_hash": self.twice_prerotated_key_hash,
        }
        if self.extra_fields:
            d.update(self.extra_fields)
        return d

    def to_string(self) -> str:
        """Deterministic preimage for relationship_hash.

        Concatenates prerotated_key_hash then twice_prerotated_key_hash.
        """
        return self.get_string(self.prerotated_key_hash) + self.get_string(
            self.twice_prerotated_key_hash
        )

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
        return (
            f"BranchAnnouncement(prerotated_key_hash="
            f"{self.prerotated_key_hash!r}, twice_prerotated_key_hash="
            f"{self.twice_prerotated_key_hash!r})"
        )
