import json
import hashlib
import requests
import logging
import time

from yadacoin.blockchainutils import BU
from yadacoin.transactionutils import TU
from yadacoin.graphutils import GraphUtils as GU
from yadacoin.crypt import Crypt


class Graph(object):

    def __init__(self, config, mongo, bulletin_secret, ids, rids, key_or_wif=None):
        self.config = config
        self.mongo = mongo
        self.app_log = logging.getLogger('tornado.application')
        self.friend_requests = []
        self.sent_friend_requests = []
        self.friends = []
        self.posts = []
        self.logins = []
        self.messages = []
        self.new_messages = []
        self.reacts = []
        self.comments = []
        self.comment_reacts = []
        self.already_added_messages = []
        self.bulletin_secret = str(bulletin_secret)
        self.ids = ids
        self.rids = rids
        bulletin_secrets = sorted([str(config.bulletin_secret), str(bulletin_secret)], key=str.lower)
        rid = hashlib.sha256((str(bulletin_secrets[0]) + str(bulletin_secrets[1])).encode('utf-8')).digest().hex()
        self.rid = rid
        self.username = ''

        if key_or_wif in [config.private_key, config.wif]:
            self.wallet_mode = True
        else:
            self.wallet_mode = False
            nodes = GU().get_transactions_by_rid(bulletin_secret, config.bulletin_secret, raw=True, returnheight=True, inc_mempool=True)
            me = None
            them = None
            for node in nodes:
                if node.get('dh_public_key') and self.rid == node.get('rid'):
                    if node.get('public_key') != self.config.public_key:
                        them = node
                        self.friends.append(node)
                    elif node.get('public_key') == self.config.public_key:
                        me = node
                        self.friends.append(node)
                if them and me:
                    break

            if them and me:
                for x in self.friends:
                    for y in x['outputs']:
                        if y['to'] != config.address:
                            self.mongo.site_db.usernames.update({
                                'rid': self.rid,
                                'username': self.username,
                                },
                                {
                                'rid': self.rid,
                                'username': self.username,
                                'to': y['to'],
                                'relationship': {
                                    'bulletin_secret': bulletin_secret
                                }
                            },
                            upsert=True)

    def get_lookup_rids(self):
        lookup_rids = [self.rid,]
        lookup_rids.extend([x['rid'] for x in GU().get_friend_requests(self.rid)])
        lookup_rids.extend([x['rid'] for x in GU().get_sent_friend_requests(self.rid)])
        return list(set(lookup_rids))

    def get_request_rids_for_rid(self):
        lookup_rids = {}
        for x in GU().get_friend_requests(self.rid):
            if x['rid'] not in lookup_rids:
                lookup_rids[x['rid']] = []
            lookup_rids[x['rid']].append(x['requester_rid'])

        for x in GU().get_sent_friend_requests(self.rid):
            if x['rid'] not in lookup_rids:
                lookup_rids[x['rid']] = []
            lookup_rids[x['rid']].append(x['requested_rid'])

        return lookup_rids
    
    async def assign_usernames(self, txns, lam=lambda x: x.get('requester_rid')):
        if not isinstance(txns, list):
            txns = [txns]
            
        for i, txn in enumerate(txns):
            ns_record = await self.config.mongo.async_db.name_server.find_one({'rid': lam(txn)})
            if ns_record and isinstance(ns_record.get('txn', {}).get('relationship'), dict):
                txns[i]['username'] = ns_record['txn']['relationship']['their_username']
            else:
                ns_record = await self.resolve_ns(
                    rid=lam(txn)
                )
                if ns_record and isinstance(ns_record.get('relationship'), dict):
                    txns[i]['username'] = ns_record['relationship']['their_username']
    
    async def resolve_ns(self, rid, username=True):
        used_peers = []
        for peer in [x for x in self.config.peers.peers[:5] if x.host not in self.config.outgoing_blacklist]: # shot in the dark
            if peer.to_string() in used_peers: continue
            if peer.to_string() in ['localhost:{}'.format(self.config.peer_port), '0.0.0.0:{}'.format(self.config.peer_port), "{}:{}".format(self.config.peer_host, self.config.peer_port)]: continue
            try:
                if peer.client and peer.client.connected:
                    await peer.client.client.emit(
                        'getns', 
                        data={
                            'requester_rid': rid,
                            'bulletin_secret': self.config.bulletin_secret
                        },
                        namespace='/chat'
                    )
                else:
                    res = requests.get(
                        'http://{}/ns?requester_rid={}&username=1&complete=1&bulletin_secret={}'.format(
                            peer.to_string(),
                            rid,
                            self.config.bulletin_secret
                        ),
                        timeout=1,
                        headers={'Connection': 'close'}
                    ).content
                    ns_record = json.loads(res.decode())
                    if ns_record.get('relationship', {}).get('their_username'):
                        return ns_record

            except Exception as e:
                await self.config.mongo.async_db.peers.update_many({
                    'host': peer.host,
                    'port': peer.port,
                    '$inc': {
                        'failed': 1
                    }
                })
                self.config.outgoing_blacklist.append(peer.host)
                self.app_log.debug(e)
            used_peers.append(peer.to_string())


    async def get_friend_requests(self):
        self.friend_requests = []
        if self.wallet_mode:
            res = await self.config.mongo.async_db.miner_transactions.find({
                'public_key': self.config.public_key,
                'relationship': {'$ne': ''},
                'rid': {'$ne': ''}
            }, {
                '_id': 0
            }).to_list(length=1000)
            for txn in res:
                txn['pending'] = True
                self.friend_requests.append(txn)
            self.all_relationships = [x for x in GU().get_all_usernames()]
            rids = []
            rids.extend([x['rid'] for x in self.all_relationships if 'rid' in x and x['rid']])
            rids.extend([x['requested_rid'] for x in self.all_relationships if 'requested_rid' in x and x['requested_rid']])
            rids.extend([x['requester_rid'] for x in self.all_relationships if 'requester_rid' in x and x['requester_rid']])
            rids.append(self.rid)
            rids = list(set(rids))
            self.rid_transactions = GU().get_transactions_by_rid(
                rids,
                bulletin_secret=self.config.bulletin_secret,
                rid=True,
                raw=True,
                returnheight=True,
                requested_rid=True,
            )
            self.friend_requests += [x for x in self.rid_transactions if x['rid'] and x['public_key'] != self.config.public_key]
        else:
            self.friend_requests += [x for x in GU().get_friend_requests(self.rid)] # include fastgraph
        
        res = await self.config.mongo.async_db.miner_transactions.find({
            'dh_public_key': {'$ne': ''},
            'relationship': {'$ne': ''},
            'requested_rid': self.rid
        }, {
            '_id': 0
        }).to_list(length=1000)
        for txn in res:
            txn['pending'] = True
            self.friend_requests.append(txn)

        await self.assign_usernames(self.friend_requests, lam=lambda x: x.get('requester_rid') or x.get('rid'))

    async def get_sent_friend_requests(self):
        self.sent_friend_requests = []
        if self.wallet_mode:
            res = await self.config.mongo.async_db.miner_transactions.find({
                'public_key': self.config.public_key,
                'relationship': {'$ne': ''},
                'rid': {'$ne': ''}
            }, {
                '_id': 0
            }).to_list(length=1000)
            for txn in res:
                txn['pending'] = True
                self.sent_friend_requests.append(txn)
            self.all_relationships = [x for x in GU().get_all_usernames()]
            rids = []
            rids.extend([x['rid'] for x in self.all_relationships if 'rid' in x and x['rid']])
            rids.extend([x['requested_rid'] for x in self.all_relationships if 'requested_rid' in x and x['requested_rid']])
            rids.extend([x['requester_rid'] for x in self.all_relationships if 'requester_rid' in x and x['requester_rid']])
            rids.append(self.rid)
            rids = list(set(rids))
            self.rid_transactions = GU().get_transactions_by_rid(
                rids,
                bulletin_secret=self.config.bulletin_secret,
                rid=True,
                raw=True,
                returnheight=True
            )
            self.sent_friend_requests += [x for x in self.rid_transactions if x['rid'] and x['public_key'] == self.config.public_key]

        else:
            self.sent_friend_requests += [x for x in GU().get_sent_friend_requests(self.rid)]
        
        res = await self.config.mongo.async_db.miner_transactions.find({
            'dh_public_key': {'$ne': ''},
            'relationship': {'$ne': ''},
            'requester_rid': self.rid
        }, {
            '_id': 0
        }).to_list(length=1000)
        for txn in res:
            txn['pending'] = True
            self.sent_friend_requests.append(txn)
        
        await self.assign_usernames(self.sent_friend_requests, lam=lambda x: x.get('requested_rid') or x.get('rid'))

    async def get_messages(self, not_mine=False):
        if self.wallet_mode:
            for transaction in self.mongo.db.miner_transactions.find({"relationship": {"$ne": ""}}):
                try:
                    decrypted = self.config.cipher.decrypt(transaction['relationship'])
                    relationship = json.loads(decrypted.decode('latin1'))
                    transaction['relationship'] = relationship
                except:
                    pass
            rid_transactions = GU().get_transactions_by_rid(
                self.rids,
                bulletin_secret=self.config.bulletin_secret,
                rid=True,
                raw=True,
                returnheight=True,
                requested_rid=True
            )
            self.messages = []
            used_ids = []
            for x in rid_transactions:
                if x.get('id') not in used_ids and x['rid'] and x['relationship']:
                    self.messages.append(x)
                    used_ids.append(x.get('id'))
            if not_mine:
                messages = []
                for x in self.messages:
                    if x['public_key'] != self.config.public_key:
                        messages.append(x)
                self.messages = messages
        else:
            rids = self.get_lookup_rids() + self.rids
            self.messages = [x for x in GU().get_messages(rids)]
        res = await self.config.mongo.async_db.miner_transactions.find({
            'relationship': {'$ne': ''},
            '$or': [
                {'rid': {'$in': self.rids}},
                {'requester_rid': {'$in': self.rids}},
                {'requested_rid': {'$in': self.rids}}
            ]
        }, {
            '_id': 0
        }).to_list(length=1000)
        for txn in res:
            txn['pending'] = True
            self.messages.append(txn)
        
        await self.assign_usernames(self.messages, lam=lambda x: x.get('requested_rid') or x.get('requester_rid') or x.get('rid'))


    async def get_new_messages(self):
        await self.get_messages(not_mine=True)
        self.messages = sorted(self.messages, key=lambda x: int(x.get('time', 0)), reverse=True)
        used_rids = []
        for message in self.messages:
            if message['rid'] not in used_rids:
                self.new_messages.append(message)
                used_rids.append(message['rid'])

    def get_group_messages(self):
        if self.wallet_mode:
            self.rid_transactions = GU().get_transactions_by_rid(self.rids, bulletin_secret=self.config.bulletin_secret, rid=True, raw=True, returnheight=True)
        else:
            my_bulletin_secret = self.config.bulletin_secret
            posts = []
            blocked = [x['username'] for x in self.mongo.db.blocked_users.find({'bulletin_secret': self.bulletin_secret})]
            flagged = [x['id'] for x in self.mongo.db.flagged_content.find({'bulletin_secret': self.bulletin_secret})]
            for x in GU().get_posts(self.rid):
                rids = sorted([str(my_bulletin_secret), str(x.get('bulletin_secret'))], key=str.lower)
                rid = hashlib.sha256((str(rids[0]) + str(rids[1])).encode('utf-8')).digest().hex()
                if rid in self.rid_usernames:
                    x['username'] = self.rid_usernames[rid]
                    if x['username'] not in blocked and x['id'] not in flagged:
                        posts.append(x)
            self.posts = posts

    async def get_comments(self):
        if self.wallet_mode:
            self.comments = []
            return

        my_bulletin_secret = self.config.bulletin_secret
        comments = []
        blocked = [x['username'] for x in self.mongo.db.blocked_users.find({'bulletin_secret': self.bulletin_secret})]
        flagged = [x['id'] for x in self.mongo.db.flagged_content.find({'bulletin_secret': self.bulletin_secret})]
        out = {}
        if not self.ids:
            return json.dumps({})
        used_ids = []
        for x in GU().get_comments(self.rid, self.ids):
            if x['relationship'].get('id') not in out:
                out[x['relationship'].get('id')] = []

            rids = sorted([str(my_bulletin_secret), str(x.get('bulletin_secret'))], key=str.lower)
            rid = hashlib.sha256((str(rids[0]) + str(rids[1])).encode('utf-8')).digest().hex()
            
            if rid in self.rid_usernames:
                x['username'] = self.rid_usernames[rid]
                if x['username'] not in blocked and x['id'] not in flagged:
                    comments.append(x)
            x['id'] = str(x['id'])
            if x['id'] in used_ids:
                continue
            used_ids.append(x['id'])
            if x['username'] not in blocked:
                out[x['relationship'].get('id')].append(x)
        self.comments = out

    async def get_reacts(self):
        if self.wallet_mode:
            self.reacts = []
            return

        my_bulletin_secret = self.config.bulletin_secret
        reacts = []
        blocked = [x['username'] for x in self.mongo.db.blocked_users.find({'bulletin_secret': self.bulletin_secret})]
        flagged = [x['id'] for x in self.mongo.db.flagged_content.find({'bulletin_secret': self.bulletin_secret})]
        out = {}
        if not self.ids:
            return json.dumps({})
        for x in GU().get_reacts(self.rid, self.ids):
            if x['relationship'].get('id') not in out:
                out[x['relationship'].get('id')] = []

            rids = sorted([str(my_bulletin_secret), str(x.get('bulletin_secret'))], key=str.lower)
            rid = hashlib.sha256((str(rids[0]) + str(rids[1])).encode('utf-8')).digest().hex()
            
            if rid in self.rid_usernames:
                x['username'] = self.rid_usernames[rid]
                if x['username'] not in blocked and x['id'] not in flagged:
                    reacts.append(x)
            x['id'] = str(x['id'])
            if x['username'] not in blocked:
                out[x['relationship'].get('id')].append(x)
        self.reacts = out

    def from_dict(self, obj):
        self.friends = obj['friends']
        self.sent_friend_requests = obj['sent_friend_requests']
        self.friend_requests = obj['friend_requests']
        self.posts = obj['posts']
        self.logins = obj['logins']
        self.messages = obj['messages']
        self.rid = obj['rid']
        self.username = obj['username']

    def to_dict(self):
        return {
            'friends': self.friends,
            'sent_friend_requests': self.sent_friend_requests,
            'friend_requests': self.friend_requests,
            'posts': self.posts,
            'messages': self.messages,
            'rid': self.rid,
            'bulletin_secret': self.bulletin_secret,
            'username': self.username,
            'new_messages': self.new_messages,
            'reacts': self.reacts,
            'comments': self.comments,
            'comment_reacts': self.comment_reacts
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)
