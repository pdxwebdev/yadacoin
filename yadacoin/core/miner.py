"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import random
import string

from yadacoin.core.peer import Miner as MinerBase


class Miner(MinerBase):
    address = ""
    address_only = ""
    agent = ""
    id_attribute = "address_only"

    def __init__(self, address, agent="", peer_id=""):
        super(Miner, self).__init__()
        if "." in address:
            self.address = address
            self.address_only = address.split(".")[0]
            self.worker = address.split(".")[1]
            if not self.config.address_is_valid(self.address_only):
                raise InvalidAddressException()
        else:
            from yadacoin.tcpsocket.pool import StratumServer

            N = 17
            StratumServer.inbound_streams[Miner.__name__].setdefault(address, {})
            self.worker = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=N)
            )
            self.address = address
            self.address_only = address
            if not self.config.address_is_valid(self.address):
                raise InvalidAddressException()
        self.agent = agent
        self.peer_id = peer_id

    def to_json(self):
        return {
            "address": self.address_only,
            "worker": self.worker,
            "agent": self.agent,
            "peer_id": self.peer_id,
        }


class InvalidAddressException(Exception):
    pass
