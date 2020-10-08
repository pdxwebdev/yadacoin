from logging import getLogger
from yadacoin.peers import Peer
from yadacoin.transaction import Transaction


class NSBroadcaster(object):
    def __init__(self, config, server=None):
        self.config = config
        self.app_log = getLogger('tornado.application')
        self.server = server

    async def ns_broadcast_job(self, nstxn, sent_to=None):
        if isinstance(nstxn, Transaction):
            transaction = nstxn
        else:
            transaction = Transaction.from_dict(self.config.LatestBlock.block.index, nstxn)

        if self.config.network != 'regnet':
            for peer in self.config.peers.peers:
                await self.prepare_peer(peer, transaction, sent_to)
            
            if self.server:
                try:
                    if not sent_to:
                        sent_to = []
                    if '*' in sent_to:
                        return
                    if self.config.debug:
                        self.app_log.debug('Transmitting ns to inbound peers')
                    to_send = {
                        'host': self.config.peer_host,
                        'port': self.config.peer_port
                    }
                    to_send.update(transaction.to_dict())
                    await self.server.emit('newns', data=to_send, namespace='/chat')
                    await self.config.mongo.async_db.name_server.update_many({
                        'txn.id': transaction.transaction_signature
                    }, {
                        '$addToSet': {
                            'sent_to': '*'
                        }
                    })
                except Exception as e:
                    if self.config.debug:
                        self.app_log.debug(e)
    
    async def prepare_peer(self, peer, transaction, sent_to):
        if not isinstance(peer, Peer):
            peer = Peer(peer['host'], peer['port'])
        if sent_to and peer.to_string() in sent_to:
            return
        if peer.to_string() in self.config.outgoing_blacklist or not (peer.client and peer.client.connected):
            return
        if peer.host == self.config.peer_host and peer.port == self.config.peer_port:
            return
        try:
            # peer = self.config.peers.my_peer
            to_send = {                            
                'host': self.config.peer_host,
                'port': self.config.peer_port
            }
            to_send.update(transaction.to_dict())
            await self.send_it(to_send, peer)
            await self.config.mongo.async_db.name_server.update_many({
                'txn.id': transaction.transaction_signature
            }, {
                '$addToSet': {
                    'sent_to': peer.to_string()
                }
            })
        except Exception as e:
            self.app_log.debug(e)

    async def send_it(self, txn_dict: dict, peer: Peer):
        try:
            if self.config.debug:
                self.app_log.debug('Transmitting ns to: {}'.format(peer.to_string()))
            await peer.client.client.emit('newns', data=txn_dict, namespace='/chat')
        except Exception as e:
            if self.config.debug:
                self.app_log.debug(e)
            # peer.report()
