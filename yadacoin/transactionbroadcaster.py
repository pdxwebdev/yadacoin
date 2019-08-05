from logging import getLogger
from yadacoin.peers import Peer


class TxnBroadcaster(object):
    def __init__(self, config):
        self.config = config
        self.app_log = getLogger('tornado.application')

    async def txn_broadcast_job(self, transaction):
        if self.config.network != 'regnet':
            for peer in self.config.peers.peers:
                if not isinstance(peer, Peer):
                    peer = Peer(peer['host'], peer['port'])
                if peer.host in self.config.outgoing_blacklist or not (peer.client and peer.client.connected):
                    continue
                if peer.host == self.config.peer_host and peer.port == self.config.peer_port:
                    continue
                try:
                    # peer = self.config.peers.my_peer
                    await self.send_it(transaction.to_dict(), peer)
                except Exception as e:
                    print("Error ", e)

    async def send_it(self, txn_dict: dict, peer: Peer):
        try:
            if self.config.debug:
                self.app_log.debug('Transmitting pool payout transaction to: {}'.format(peer.to_string()))
            await peer.client.client.emit('newtransaction', data=txn_dict, namespace='/chat')
        except Exception as e:
            if self.config.debug:
                self.app_log.debug(e)
            # peer.report()