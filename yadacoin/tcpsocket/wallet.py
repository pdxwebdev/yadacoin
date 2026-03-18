import json

from yadacoin.core.config import Config
from yadacoin.tcpsocket.base import RPCSocketServer


class ElectrumServer(RPCSocketServer):
    current_header = ""
    config = None

    def __init__(self):
        super(ElectrumServer, self).__init__()
        self.config = Config()

    async def server_version(self, body, stream):
        rpc_data = {
            "id": body["id"],
            "jsonrpc": "2.0",
            "method": body["method"],
            "result": ["AwesomeServer 2.2.3", "1.4"],
        }
        await stream.write("{}\n".format(json.dumps(rpc_data)).encode())

    async def blockchain_scripthash_get_balance(self, body, stream):
        rpc_data = {
            "id": body["id"],
            "jsonrpc": "2.0",
            "method": body["method"],
            "result": ["AwesomeServer 2.2.3", "1.4"],
        }
        await stream.write("{}\n".format(json.dumps(rpc_data)).encode())
