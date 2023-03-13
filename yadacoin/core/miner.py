from yadacoin.core.peer import Miner as MinerBase


class Miner(MinerBase):
    address = ''
    address_only = ''
    agent = ''
    id_attribute = 'address'

    def __init__(self, address, agent=''):
        super(Miner, self).__init__()
        if '.' in address:
            self.address = address
            self.address_only = address.split('.')[0]
            self.worker = address.split('.')[1]
            if not self.config.address_is_valid(self.address_only):
                raise InvalidAddressException()
        else:
            from yadacoin.tcpsocket.pool import StratumServer
            StratumServer.inbound_streams[Miner.__name__].setdefault(address, {})
            i = 0
            while True:
                if not str(i) in StratumServer.inbound_streams[Miner.__name__][address]:
                    self.worker = str(i)
                    break
                i += 1
            self.address = address
            self.address_only = address
            if not self.config.address_is_valid(self.address):
                raise InvalidAddressException()
        self.agent = agent

    def to_json(self):
        return {
            'address': self.address_only,
            'worker': self.worker
        }


class InvalidAddressException(Exception):
    pass
