import json
import socket

from tornado.tcpserver import TCPServer
from tornado.tcpclient import TCPClient
from tornado.iostream import StreamClosedError

from yadacoin.core.config import get_config, Config
from yadacoin.core.chain import CHAIN



class RPCSocketServer(TCPServer):
    streams = {}
    config = get_config()

    @classmethod
    async def clean_peers(cls):
        to_delete = []
        for stream in cls.__class__.streams:
            if stream.closed():
                to_delete.append(stream)
        for stream in to_delete:
            del RPCSocketServer.streams[peer.identity.username_signature]

    async def handle_stream(self, stream, address):
        while True:
            try:
                body = json.loads(await stream.read_until(b"\n"))
                username_signature = body.get('params', {}).get('identity', {}).get('username_signature')
                method = body.get('method')
                if 'params' in body:
                    method += 'request'
                elif 'result' in body:
                    method += 'result'
                if not (set([username_signature]) & set(self.__class__.streams)) and method != 'connect':
                    stream.close()
                    break
                await getattr(self, method)(body, stream)
            except StreamClosedError:
                break

    async def write_as_json(self, stream, method, result):
        rpc_data = {
            'id': 1,
            'method': method,
            'jsonrpc': 2.0,
            'result': result
        }
        await stream.write('{}\n'.format(json.dumps(rpc_data)).encode())

class RPCSocketClient(TCPClient):
    config = get_config()
    streams = {}

    async def connect(self, peer):
        try:
            stream = await super(RPCSocketClient, self).connect(peer.host, peer.port)
            RPCSocketServer.streams[peer.identity.username_signature] = stream
        except StreamClosedError:
            del RPCSocketServer.streams[peer.identity.username_signature]
            return
        while True:
            try:
                body = json.loads(await stream.read_until(b"\n"))
                await getattr(self, body.get('method'))(body, stream)
            except StreamClosedError:
                del RPCSocketServer.streams[peer.identity.username_signature]
                break