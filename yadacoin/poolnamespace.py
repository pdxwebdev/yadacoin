"""
Web socket handler for yadacoin, /pool namespace
"""

# import json
from socketio import AsyncNamespace
from logging import getLogger

# from yadacoin.transaction import Transaction
from yadacoin.config import get_config
# from yadacoin.blockchainutils import BU
from yadacoin.miningpool import MiningPool


class PoolNamespace(AsyncNamespace):

    async def on_connect(self, sid, environ):
        if not 'config' in self.__dict__:
            # PoolNamespace is a singleton, same instance for everyone
            self.config = get_config()  # Will be done once at first request
            self.app_log = getLogger("tornado.application")
            self.mp = MiningPool(self.config, self.mongo)
        IP = environ['REMOTE_ADDR']
        if self.mp.free_inbound_slots <= 0:
            self.app_log.warning('No free slot, Miner rejected: {}'.format(IP))
            return False  # This will close the socket
        if not self.mp.allow_ip(IP):
            self.app_log.info('Miner rejected: {}'.format(IP))
            return False  # This will close the socket
        self.mp.on_new_ip(IP)  # Store the ip to avoid duplicate connections
        await self.save_session(sid, {'IP': IP})
        if self.config.debug:
            self.app_log.info('Miner connected: {} {}'.format(ip, sid))

    async def on_disconnect_request(sid):
        from yadacoin.yadawebsockethandler import SIO
        # print('Disconnect request')
        await SIO.disconnect(sid, namespace='/pool')

    async def on_disconnect(self, sid):
        if self.config.debug:
            self.app_log.info('Miner disconnected: {}'.format(sid))
        try:
            await self.mp.on_close_inbound(sid)
        except Exception as e:
            self.app_log.warning("Error on_disconnect: {}".format(e))

    async def force_close(self, sid):
        # TODO: can we force close the socket?
        from yadacoin.yadawebsockethandler import SIO
        await SIO.disconnect(sid, namespace='/pool')
        # This processes a disconnect event, but does not close the underlying socket. Client still can send messages.

