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
        if self.config.network == 'regnet':
            return
        if sum([float(x.value) for x in transaction.outputs]) + float(transaction.fee) == 0:
            rids = [transaction.rid, transaction.requested_rid, transaction.requester_rid]
            ns_records = await self.config.mongo.async_db.name_server.find({
                '$or': [
                    {'rid': {'$in': rids}},
                    {'requested_rid': {'$in': rids}},
                    {'requester_rid': {'$in': rids}}
                ]
            }).to_list(100)
            peers_indexed = {}
            for peer in self.config.peers.peers:
                peers_indexed[peer.to_string()] = peer
            for ns in ns_records:
                peer = peers_indexed.get('{}:{}'.format(ns['peer']['host'], ns['peer']['port']))
                if peer:
                    await self.prepare_peer(peer, transaction, sent_to)
        else:
            for peer in self.config.peers.peers:
                await self.prepare_peer(peer, transaction, sent_to)
            
            for ip, peer in self.config.peers.outbound.items():
                peer = Peer(peer['ip'], peer['port'], client=peer['client'])
                await self.prepare_peer(peer, transaction, sent_to)
        
        if self.server:
            try:
                if not sent_to:
                    sent_to = []
                if '*' in sent_to:
                    raise Exception('Already sent to all connected peers.')
                if self.config.debug:
                    self.app_log.debug('sent_to {}'.format(sent_to))
                    self.app_log.debug('Transmitting transaction to all inbound peers')
                await self.server.emit('newtransaction', data=transaction.to_dict(), namespace='/chat')
                await self.config.mongo.async_db.miner_transactions.update_many({
                    'id': transaction.transaction_signature
                }, {
                    '$addToSet': {
                        'sent_to': '*'
                    }
                })
            except Exception as e:
                if self.config.debug:
                    self.app_log.debug(e)
            try:
                for sid, peer in self.config.peers.inbound.items():
                    peer = Peer(peer['ip'], peer['port'], sid=sid)
                    await self.server.emit('newtransaction', data=transaction.to_dict(), room=peer.sid)
                    await self.config.mongo.async_db.miner_transactions.update_many({
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
            peer = Peer(peer['host'], peer['port'], peer['client'])
        if sent_to and peer.to_string() in sent_to:
            return
        if peer.to_string() in self.config.outgoing_blacklist or not (peer.client and peer.client.client and peer.client.client.connected):
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
            self.app_log.warning('Transmitting transaction to: {} {}'.format(peer.to_string(), txn_dict['id']))
            await peer.client.client.emit('newtransaction', data=txn_dict, namespace='/chat')
        except Exception as e:
            self.app_log.warning(e)
            # peer.report()
