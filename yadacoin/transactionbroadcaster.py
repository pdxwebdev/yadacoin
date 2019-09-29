from logging import getLogger
from yadacoin.peers import Peer
from yadacoin.transaction import Transaction


class TxnBroadcaster(object):
    def __init__(self, config, server=None):
        self.config = config
        self.app_log = getLogger('tornado.application')
        self.server = server

    async def txn_broadcast_job(self, txn, sent_to=None):
        if isinstance(txn, Transaction):
            transaction = txn
        else:
            transaction = Transaction.from_dict(0, txn)
        if self.config.network != 'regnet':

            if sum([float(x['value']) for x in transaction.outputs]) + float(transaction.fee) == 0:
                ns_records = await self.config.mongo.async_db.name_server.find({
                    '$or': [
                        {'rid': transaction.rid},
                        {'requested_rid': transaction.requested_rid},
                        {'requester_rid': transaction.requester_rid}
                    ]
                }).to_list(100)
                for ns in ns_records:
                    await self.prepare_peer(ns['peer'], transaction, sent_to)
            else:
                for peer in self.config.peers.peers:
                    await self.prepare_peer(peer, transaction, sent_to)
            
            if self.server:
                try:
                    if self.config.debug:
                        self.app_log.debug('Transmitting transaction to inbound peers')
                    await self.server.emit('newtransaction', data=transaction.to_dict(), namespace='/chat')
                    await self.config.mongo.async_db.miner_transactions.update_one({
                        'id': transaction.transaction_signature
                    }, {
                        '$addToSet': {
                            'sent_to': peer.to_string()
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
            await self.send_it(transaction.to_dict(), peer)
            await self.config.mongo.async_db.miner_transactions.update_one({
                'id': transaction.transaction_signature
            }, {
                '$addToSet': {
                    'sent_to': peer.to_string()
                }
            })
        except Exception as e:
            print("Error ", e)

    async def send_it(self, txn_dict: dict, peer: Peer):
        try:
            if self.config.debug:
                self.app_log.debug('Transmitting transaction to: {}'.format(peer.to_string()))
            await peer.client.client.emit('newtransaction', data=txn_dict, namespace='/chat')
        except Exception as e:
            if self.config.debug:
                self.app_log.debug(e)
            # peer.report()