import json
import socket
import base64
from collections import OrderedDict
from traceback import format_exc

from tornado.tcpserver import TCPServer
from tornado.tcpclient import TCPClient
from tornado.iostream import StreamClosedError
from tornado.util import TimeoutError
from coincurve import verify_signature

from yadacoin.core.config import get_config, Config
from yadacoin.core.chain import CHAIN



class RPCSocketServer(TCPServer):
    inbound_streams = {}
    inbound_pending = {}
    config = None

    async def handle_stream(self, stream, address):
        while True:
            try:
                data = await stream.read_until(b"\n")
                body = json.loads(data)
                method = body.get('method')
                await getattr(self, method)(body, stream)
            except StreamClosedError:
                if hasattr(stream, 'peer'):
                    await self.remove_peer(stream.peer)
                    self.config.app_log.warning('Disconnected from {}: {}'.format(stream.peer.__class__.__name__, stream.peer.to_json()))
                break
            except:
                stream.close()
                self.config.app_log.warning("{}".format(format_exc()))
    
    async def write_result(self, stream, method, data):
        await SharedBaseMethods.write_result(self, stream, method, data)
    
    async def write_params(self, stream, method, data):
        await SharedBaseMethods.write_params(self, stream, method, data)

    async def remove_peer(self, peer):
        id_attr = getattr(peer, peer.id_attribute)
        if id_attr in self.inbound_streams[peer.__class__.__name__]:
            del self.inbound_streams[peer.__class__.__name__][id_attr]
        if id_attr in self.inbound_pending[peer.__class__.__name__]:
            del self.inbound_pending[peer.__class__.__name__][id_attr]


class RPCSocketClient(TCPClient):
    outbound_streams = {}
    outbound_pending = {}
    outbound_ignore = {}
    config = None

    async def connect(self, peer):
        try:
            id_attr = getattr(peer, peer.id_attribute)
            if id_attr in self.outbound_ignore[peer.__class__.__name__]:
                return
            if id_attr in self.outbound_pending[peer.__class__.__name__]:
                return
            if id_attr in self.outbound_streams[peer.__class__.__name__]:
                return
            if id_attr in self.config.nodeServer.inbound_pending[peer.__class__.__name__]:
                return
            if id_attr in self.config.nodeServer.inbound_streams[peer.__class__.__name__]:
                return
            if self.config.peer.identity.username_signature == peer.identity.username_signature:
                return
            if (self.config.peer.host, self.config.peer.host) == (peer.host, peer.port):
                return
            self.outbound_pending[peer.__class__.__name__][id_attr] = peer
            stream = await super(RPCSocketClient, self).connect(peer.host, peer.port, timeout=1)
            stream.peer = peer
            try:
                result = verify_signature(
                    base64.b64decode(stream.peer.identity.username_signature),
                    stream.peer.identity.username.encode(),
                    bytes.fromhex(stream.peer.identity.public_key)
                )
                if not result:
                    self.config.app_log.warning('new {} peer signature is invalid'.format(peer.__class__.__name__))
                    stream.close()
                    return
                self.config.app_log.info('new {} peer is valid'.format(peer.__class__.__name__))
            except:
                self.config.app_log.warning('invalid peer identity signature')
                stream.close()
                return
            if id_attr in self.outbound_pending[peer.__class__.__name__]:
                del self.outbound_pending[peer.__class__.__name__][id_attr]
            self.outbound_streams[peer.__class__.__name__][id_attr] = stream
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
                del self.outbound_streams[stream.peer.__class__.__name__][stream.peer.rid]
                break

    async def remove_peer(self, peer):
        if peer.rid in self.outbound_streams[peer.__class__.__name__]:
            del self.outbound_streams[peer.__class__.__name__][peer.rid]
        if peer.rid in self.outbound_pending[peer.__class__.__name__]:
            del self.outbound_pending[peer.__class__.__name__][peer.rid]
    
    async def write_result(self, stream, method, data):
        await SharedBaseMethods.write_result(self, stream, method, data)
    
    async def write_params(self, stream, method, data):
        await SharedBaseMethods.write_params(self, stream, method, data)


class SharedBaseMethods:
    @staticmethod
    async def write_result(self, stream, method, data):
        await SharedBaseMethods.write_as_json(stream, method, data, 'result')

    @staticmethod
    async def write_params(self, stream, method, data):
        await SharedBaseMethods.write_as_json(stream, method, data, 'params')

    @staticmethod
    async def write_as_json(stream, method, data, rpc_type):
        rpc_data = {
            'id': 1,
            'method': method,
            'jsonrpc': 2.0,
            rpc_type: data
        }
        await stream.write('{}\n'.format(json.dumps(rpc_data)).encode())

