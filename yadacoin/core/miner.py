import random
import string

from yadacoin.core.peer import Miner as MinerBase


class Miner(MinerBase):
    address = ""
    address_only = ""
    agent = ""
    custom_diff = ""
    id_attribute = "address_only"

    def __init__(self, address, agent="", custom_diff="", peer_id=""):
        super(Miner, self).__init__()
        self.peer_id = peer_id
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
            StratumServer.inbound_streams[Miner.__name__].setdefault(address, {})
            self.worker = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=N)
            )
            self.address = address
            self.address_only = address
            if not self.config.address_is_valid(self.address):
                raise InvalidAddressException()
        self.agent = agent

    def to_json(self):
        return {"address": self.address_only, "worker": self.worker, "agent": self.agent, "custom_diff": self.custom_diff, "peer_id": self.peer_id}


class InvalidAddressException(Exception):
    pass
