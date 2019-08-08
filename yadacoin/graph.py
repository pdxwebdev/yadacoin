import json
import hashlib

from yadacoin.blockchainutils import BU
from yadacoin.transactionutils import TU
from yadacoin.graphutils import GraphUtils as GU


class Graph(object):

    def __init__(self, config, mongo, bulletin_secret, ids, key_or_wif=None):
        self.config = config
        self.mongo = mongo
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
        self.all_relationships = [x for x in GU().get_all_usernames()]
        self.all_groups = [x for x in self.config.GU.get_all_groups()]

        
        self.rid_usernames = dict([(x['rid'], x['relationship']['their_username']) for x in self.all_relationships])
        if key_or_wif in [config.private_key, config.wif]:
            self.wallet_mode = True

            rids = list(set([x['rid'] for x in self.all_relationships]))
            self.rid_transactions = GU().get_transactions_by_rid(rids, bulletin_secret=config.bulletin_secret, rid=True, raw=True, returnheight=True)
        else:
            self.wallet_mode = False
            self.registered = False
            self.pending_registration = False
            self.invited = False
            bulletin_secrets = sorted([str(config.bulletin_secret), str(bulletin_secret)], key=str.lower)
            rid = hashlib.sha256((str(bulletin_secrets[0]) + str(bulletin_secrets[1])).encode('utf-8')).digest().hex()
            self.rid = rid

            res = self.mongo.site_db.usernames.find({"rid": self.rid})
            if res.count():
                self.username = res[0]['username']
            else:
                self.username = ''
            start_height = 0
            # this will get any transactions between the client and server
            nodes = GU().get_transactions_by_rid(bulletin_secret, config.bulletin_secret, raw=True, returnheight=True)
            already_done = []
            for node in nodes:
                if node.get('dh_public_key'):
                    test = {
                        'rid': node.get('rid'),
                        'requester_rid': node.get('requester_id'),
                        'requested_rid': node.get('requested_id'),
                        'id': node.get('id')
                    }
                    node['username'] = 'YadaCoin'
                    if test in already_done:
                        continue
                    else:
                        self.friends.append(node)
                        already_done.append(test)

            self.registered = False
            shared_secrets = GU().get_shared_secrets_by_rid(rid)

            if shared_secrets:
                self.registered = True

            if self.registered:
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
            else:
                # not regisered, let's check for a pending transaction
                res = self.mongo.db.miner_transactions.find_one({
                    'rid': self.rid, 
                    'public_key': {
                        '$ne': self.config.public_key
                    }
                }, {'_id': 0})
                res2 = self.mongo.db.miner_transactions.find_one({
                    'rid': self.rid,
                    'public_key': self.config.public_key
                }, {'_id': 0})

                if res and res2:
                    self.pending_registration = True
                
                elif res2:
                    res2['bulletin_secret'] = self.config.bulletin_secret
                    res2['username'] = self.config.username
                    self.invited = res2

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

    def get_friend_requests(self):
        if self.wallet_mode:
            self.friend_requests = [x for x in self.rid_transactions if x['relationship'] and x['rid'] and x['public_key'] != self.config.public_key]
            return
        else:
            friend_requests = [x for x in GU().get_friend_requests(self.rid)] # include fastgraph

        for i, friend_request in enumerate(friend_requests):
            # attach bulletin_secrets
            username_txns = [x for x in GU().search_rid(friend_request.get('requester_rid'))]
            if username_txns:
                friend_requests[i]['username'] = username_txns[0]['relationship']['their_username']

        self.friend_requests = friend_requests

    def get_sent_friend_requests(self):
        if self.wallet_mode:
            self.sent_friend_requests = [x for x in self.rid_transactions if x['relationship'] and x['rid'] and x['public_key'] == self.config.public_key]
            return
        else:
            sent_friend_requests = [x for x in GU().get_sent_friend_requests(self.rid)]

        for i, sent_friend_request in enumerate(sent_friend_requests):
            # attach usernames
            res = self.mongo.site_db.usernames.find({'rid': sent_friend_request.get('requested_rid')}, {'_id': 0})
            if res.count():
                sent_friend_requests[i]['username'] = res[0]['username']
            else:
                sent_friend_requests[i]['username'] = '[None]'
        self.sent_friend_requests = sent_friend_requests

    async def get_messages(self, not_mine=False):
        if self.wallet_mode:
            rids = list(set([x['rid'] for x in self.all_relationships if 'rid' in x] + [x['requested_rid'] for x in self.all_relationships if 'requested_rid' in x]))
            rid_transactions = GU().get_transactions_by_rid(
                rids,
                bulletin_secret=self.config.bulletin_secret,
                rid=True,
                raw=True,
                returnheight=True,
                requested_rid=True
            )
            self.messages = [x for x in rid_transactions if x['rid'] and x['relationship']]
            if not_mine:
                messages = []
                for x in self.messages:
                    if x['public_key'] != self.config.public_key:
                        messages.append(x)
                self.messages = messages
            for i, x in enumerate(self.messages):
                try:
                    self.messages[i]['username'] = self.rid_usernames[self.messages[i]['rid']]
                except:
                    pass
            res = self.config.mongo.async_db.miner_transactions.find({
                'public_key': self.config.public_key,
                'relationship': {'$ne': ''},
                '$or': [
                    {'rid': {'$in': rids}},
                    {'requester_rid': {'$in': rids}},
                    {'requested_rid': {'$in': rids}}
                ]
            }, {
                '_id': 0
            })
            self.messages.extend([txn for txn in res.to_list(length=1000)])
            return
        else:
            lookup_rids = self.get_request_rids_for_rid()
            lookup_rids[self.rid] = [self.rid]
            messages = [x for x in GU().get_messages(self.get_lookup_rids())]

            out_messages = []
            for i, message in enumerate(messages):
                # attach usernames
                res = self.mongo.site_db.usernames.find({'rid': {'$in': lookup_rids.get(message['rid'])}}, {'_id': 0})
                if res.count():
                    messages[i]['username'] = res[0]['username']
                else:
                    messages[i]['username'] = '[None]'
                exclude = self.mongo.db.exclude_messages.find({'id': message.get('id')})
                if exclude.count() > 0:
                    continue
                out_messages.append(message)
        self.messages = out_messages

    def get_new_messages(self):
        self.get_messages(not_mine=True)
        self.messages = sorted(self.messages, key=lambda x: int(x['height']), reverse=True)
        used_rids = []
        for message in self.messages:
            if message['rid'] not in used_rids:
                self.new_messages.append(message)
                used_rids.append(message['rid'])

    def get_group_messages(self):
        if self.wallet_mode:
            rids = []
            for x in self.all_groups:
                if 'rid' in x:
                    rids.append(x['rid'])
                if 'requested_rid' in x:
                    rids.append(x['requested_rid'])
                if 'requester_rid' in x:
                    rids.append(x['requester_rid'])
            self.rid_transactions = GU().get_transactions_by_rid(rids, bulletin_secret=self.config.bulletin_secret, rid=True, raw=True, returnheight=True)
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

    def get_comments(self):
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

    def get_reacts(self):
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
        if self.wallet_mode:
            return {
                'friends': self.friends,
                'sent_friend_requests': self.sent_friend_requests,
                'friend_requests': self.friend_requests,
                'posts': self.posts,
                'messages': self.messages,
                'new_messages': self.new_messages
            }
        else:
            return {
                'friends': self.friends,
                'sent_friend_requests': self.sent_friend_requests,
                'friend_requests': self.friend_requests,
                'posts': self.posts,
                'logins': self.logins,
                'messages': self.messages,
                'rid': self.rid,
                'username': self.username,
                'registered': self.registered,
                'pending_registration': self.pending_registration,
                'invited': self.invited,
                'new_messages': self.new_messages,
                'reacts': self.reacts,
                'comments': self.comments,
                'comment_reacts': self.comment_reacts
            }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)
