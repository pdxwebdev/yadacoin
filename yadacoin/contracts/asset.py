"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import hashlib

from yadacoin.core.collections import Collections
from yadacoin.core.identity import Identity


class Asset:
    def __init__(self, identity, data, checksum):
        from yadacoin.core.transaction import TransactionConsts

        self.identity = identity

        if not isinstance(data, str):
            raise Exception("Data is not type string")

        if len(data) > TransactionConsts.RELATIONSHIP_MAX_SIZE.value:
            raise Exception("Data too large")

        self.data = data
        self.checksum = checksum

    def generate(self, username, data, parent=None):
        self.identity = Identity.generate(
            username, collection=Collections.ASSET.value, parent=parent
        )
        self.data = data
        self.checksum = hashlib.sha256(data + self.identity.username_signature)

    def to_dict(self):
        return {
            "identity": self.identity.to_dict,
            "data": self.data,
            "checksum": self.checksum,
        }

    def to_string(self):
        return (
            self.identity.public_key
            + self.identity.username
            + self.identity.username_signature
            + self.data
            + self.checksum
        )
