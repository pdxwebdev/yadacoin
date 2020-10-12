import json
import socket

from tornado.tcpserver import TCPServer
from tornado.tcpclient import TCPClient
from tornado.iostream import StreamClosedError
from tornado.gen import TimeoutError

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
                method = body.get('method')
                await getattr(self, method)(body, stream)
            except StreamClosedError:
                break

    async def write_result(self, stream, method, data):
        await self.write_as_json(stream, method, data, 'result')

    async def write_params(self, stream, method, data):
        await self.write_as_json(stream, method, data, 'params')

    async def write_as_json(self, stream, method, data, rpc_type):
        rpc_data = {
            'id': 1,
            'method': method,
            'jsonrpc': 2.0,
            rpc_type: data
        }
        await stream.write('{}\n'.format(json.dumps(rpc_data)).encode())

class RPCSocketClient(TCPClient):
    streams = {}
    pending = {}
    config = None

    async def connect(self, peer):
        try:
            if peer.identity.username_signature in self.pending:
                return
            if peer.identity.username_signature in self.streams:
                return
            if self.config.peer.identity.username_signature == peer.identity.username_signature:
                return
            if (self.config.peer.host, self.config.peer.host) == (peer.host, peer.port):
                return
            self.pending[peer.identity.username_signature] = peer
            stream = await super(RPCSocketClient, self).connect(peer.host, peer.port, timeout=1)
            if peer.identity.username_signature in self.pending:
                del self.pending[peer.identity.username_signature]
            self.streams[peer.identity.username_signature] = stream
            self.config.app_log.info('Connected to {}: {}'.format(peer.__class__.__name__, peer.to_json()))
            return stream
        except StreamClosedError:
            await self.remove_peer(peer)
            raise
        except TimeoutError:
            await self.remove_peer(peer)
            raise
    
    async def wait_for_data(self, stream):
        while True:
            try:
                body = json.loads(await stream.read_until(b"\n"))
                await getattr(self, body.get('method'))(body, stream)
            except StreamClosedError:
                del self.streams[stream.peer.identity.username_signature]
                break

    async def remove_peer(self, stream):
        if stream.peer.identity.username_signature in self.streams:
            del self.streams[stream.peer.identity.username_signature]
        if stream.peer.identity.username_signature in self.pending:
            del self.pending[stream.peer.identity.username_signature]

    async def write_result(self, stream, method, data):
        await self.write_as_json(stream, method, data, 'result')

    async def write_params(self, stream, method, data):
        await self.write_as_json(stream, method, data, 'params')

    async def write_as_json(self, stream, method, data, rpc_type):
        rpc_data = {
            'id': 1,
            'method': method,
            'jsonrpc': 2.0,
            rpc_type: data
        }
        await stream.write('{}\n'.format(json.dumps(rpc_data)).encode())