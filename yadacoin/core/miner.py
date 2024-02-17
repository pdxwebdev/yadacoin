import time
import random
import string

from logging import getLogger
from yadacoin.core.peer import Miner as MinerBase

class Miner(MinerBase):
    address = ""
    address_only = ""
    agent = ""
    custom_diff = ""
    miner_diff = ""
    id_attribute = "address_only"

    def __init__(self, address, agent="", custom_diff="", peer_id="", miner_diff=""):
        super(Miner, self).__init__()
        self.miner_diff = miner_diff
        self.shares_history = []
        self.agent = agent
        self.peer_id = peer_id
        self.miner_diff = miner_diff
        if "@" in address:
            parts = address.split("@")
            address = parts[0]
            self.custom_diff = int(parts[1]) if len(parts) > 1 else 0
        if "." in address:
            self.address = address
            self.address_only = address.split(".")[0]
            self.worker = address.split(".")[1]
            if not self.config.address_is_valid(self.address_only):
                raise InvalidAddressException()
        else:
            from yadacoin.tcpsocket.pool import StratumServer

            N = 17
            StratumServer.inbound_streams[Miner.__name__].setdefault(peer_id, {})
            self.worker = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=N)
            )
            self.address = address
            self.address_only = address
            if not self.config.address_is_valid(self.address):
                raise InvalidAddressException()

    def to_json(self):
        return {
            "address": self.address_only,
            "worker": self.worker,
            "agent": self.agent,
            "custom_diff": self.custom_diff,
            "miner_diff": self.miner_diff,
            "peer_id": self.peer_id,
        }

    def add_share_to_history(self, share):
        self.shares_history.append(share)
        self.app_log.debug(f"Shares history for {self.peer_id}: {self.shares_history}")

    def calculate_new_miner_diff(self):
        self.shares_history = [share for share in self.shares_history if share["timestamp"] > (time.time() - 600)]

        if any(share["timestamp"] < (time.time() - 300) for share in self.shares_history):
            recent_shares = [share for share in self.shares_history]

            total_share_size = sum(share["miner_diff"] for share in recent_shares)
            average_share_size = total_share_size / 10 / ( 60 / self.config.expected_share_time)
            new_miner_diff = max(average_share_size, 70000)
            new_miner_diff = round(new_miner_diff / 1000) * 1000

            if self.custom_diff is not None:
                new_miner_diff = self.custom_diff

            self.config.app_log.info(f"New miner_diff calculated: {new_miner_diff} for Miner:{self.peer_id}")
            self.miner_diff = new_miner_diff

            return new_miner_diff
        else:
            self.config.app_log.info(f"Using current miner_diff: {self.miner_diff}")
            return self.miner_diff

class InvalidAddressException(Exception):
    pass