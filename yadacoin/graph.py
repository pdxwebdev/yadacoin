import json
import hashlib
import humanhash

"""from io import BytesIO
from uuid import uuid4
from ecdsa import NIST384p, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
"""
from yadacoin.blockchainutils import BU
from yadacoin.transactionutils import TU
# from yadacoin.transaction import *

#from yadacoin.crypt import Crypt
#from yadacoin.config import Config


class Graph(object):

    def __init__(self, config, mongo, bulletin_secret, ids, wallet=None):
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

        all_relationships = [x for x in BU.get_all_usernames(config, mongo)]
        self.rid_usernames = dict([(x['rid'], x['relationship']['their_username']) for x in all_relationships])
        if wallet: # disabling for now
            self.wallet_mode = True

            rids = [x['rid'] for x in all_relationships]
            self.rid_transactions = BU.get_transactions_by_rid(self.config, self.mongo, rids, bulletin_secret=wallet.bulletin_secret, rid=True, raw=True, returnheight=True)
        else:
            self.wallet_mode = False
            self.registered = False
            self.pending_registration = False
            bulletin_secrets = sorted([str(config.bulletin_secret), str(bulletin_secret)], key=str.lower)
            rid = hashlib.sha256(str(bulletin_secrets[0]) + str(bulletin_secrets[1])).digest().hex()
            self.rid = rid

            res = self.mongo.site_db.usernames.find({"rid": self.rid})
            if res.count():
                self.human_hash = res[0]['username']
            else:
                self.human_hash = humanhash.humanize(self.rid)
            start_height = 0
            # this will get any transactions between the client and server
            nodes = BU.get_transactions_by_rid(self.config, self.mongo, bulletin_secret, config.bulletin_secret, raw=True, returnheight=True)
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
            shared_secrets = TU.get_shared_secrets_by_rid(config, mongo, rid)
            if shared_secrets:
                self.registered = True

            if self.registered:
                for x in self.friends:
                    for y in x['outputs']:
                        if y['to'] != config.address:
                            self.mongo.site_db.usernames.update({
                                'rid': self.rid,
                                'username': self.human_hash,
                                },
                                {
                                'rid': self.rid,
                                'username': self.human_hash,
                                'to': y['to'],
                                'relationship': {
                                    'bulletin_secret': bulletin_secret
                                }
                            },
                            upsert=True)
            else:
                # not regisered, let's check for a pending transaction
                res = self.mongo.db.miner_transactions.find({'rid': self.rid, 'public_key': {'$ne': self.config.public_key}})
                res2 = self.mongo.db.miner_transactions.find({'rid': self.rid, 'public_key': self.config.public_key})

                if res.count() and res2.count():
                    self.pending_registration = True

    def get_lookup_rids(self):
        lookup_rids = [self.rid,]
        lookup_rids.extend([x['rid'] for x in BU.get_friend_requests(self.config, self.mongo, self.rid)])
        lookup_rids.extend([x['rid'] for x in BU.get_sent_friend_requests(self.config, self.mongo, self.rid)])
        return list(set(lookup_rids))

    def get_request_rids_for_rid(self):
        lookup_rids = {}
        for x in BU.get_friend_requests(self.config, self.mongo, self.rid):
            if x['rid'] not in lookup_rids:
                lookup_rids[x['rid']] = []
            lookup_rids[x['rid']].append(x['requester_rid'])

        for x in BU.get_sent_friend_requests(self.config, self.mongo, self.rid):
            if x['rid'] not in lookup_rids:
                lookup_rids[x['rid']] = []
            lookup_rids[x['rid']].append(x['requested_rid'])

        return lookup_rids

    def get_friend_requests(self):
        if self.wallet_mode:
            self.friend_requests = [x for x in self.rid_transactions if x['relationship'] and x['rid'] and x['public_key'] != self.config.public_key]
            return
        else:
            friend_requests = [x for x in BU.get_friend_requests(self.config, self.mongo, self.rid)] # include fastgraph

        for i, friend_request in enumerate(friend_requests):
            # attach bulletin_secets
            res = self.mongo.db.friends.find({'rid': friend_request.get('requester_rid')}, {'_id': 0})
            if res.count():
                friend_requests[i]['bulletin_secret'] = res[0]['relationship']['bulletin_secret']

        self.friend_requests = friend_requests

    def get_sent_friend_requests(self):
        if self.wallet_mode:
            self.sent_friend_requests = [x for x in self.rid_transactions if x['relationship'] and x['rid'] and x['public_key'] == self.config.public_key]
            return
        else:
            sent_friend_requests = [x for x in BU.get_sent_friend_requests(self.config, self.mongo, self.rid)]

        for i, sent_friend_request in enumerate(sent_friend_requests):
            # attach usernames
            res = self.mongo.site_db.usernames.find({'rid': sent_friend_request.get('requested_rid')}, {'_id': 0})
            if res.count():
                sent_friend_requests[i]['username'] = res[0]['username']
            else:
                sent_friend_requests[i]['username'] = humanhash.humanize(sent_friend_request.get('requested_rid'))
        self.sent_friend_requests = sent_friend_requests

    def get_messages(self, not_mine=False):
        if self.wallet_mode:
            self.messages = [x for x in self.rid_transactions if x['rid'] and x['relationship']]
            if not_mine:
                messages = []
                for x in self.messages:
                    if x['public_key'] != self.config.public_key:
                        messages.append(x)
                self.messages = messages
            for i, x in enumerate(self.messages):
                self.messages[i]['username'] = self.rid_usernames[self.messages[i]['rid']]
            return
        else:
            lookup_rids = self.get_request_rids_for_rid()
            lookup_rids[self.rid] = [self.rid]
            messages = [x for x in BU.get_messages(self.config, self.mongo, self.get_lookup_rids())]

            out_messages = []
            for i, message in enumerate(messages):
                # attach usernames
                res = self.mongo.site_db.usernames.find({'rid': {'$in': lookup_rids.get(message['rid'])}}, {'_id': 0})
                if res.count():
                    messages[i]['username'] = res[0]['username']
                else:
                    messages[i]['username'] = humanhash.humanize(message.get('rid'))
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

    def get_posts(self):
        if self.wallet_mode:
            self.posts = []
            return

        my_bulletin_secret = self.config.bulletin_secret
        posts = []
        blocked = [x['username'] for x in self.mongo.db.blocked_users.find({'bulletin_secret': self.bulletin_secret})]
        flagged = [x['id'] for x in self.mongo.db.flagged_content.find({'bulletin_secret': self.bulletin_secret})]
        for x in BU.get_posts(self.config, self.mongo, self.rid):
            rids = sorted([str(my_bulletin_secret), str(x.get('bulletin_secret'))], key=str.lower)
            rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().hex()
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
        for x in BU.get_comments(self.config, self.mongo, self.rid, self.ids):
            if x['relationship'].get('id') not in out:
                out[x['relationship'].get('id')] = []

            rids = sorted([str(my_bulletin_secret), str(x.get('bulletin_secret'))], key=str.lower)
            rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().hex()
            
            if rid in self.rid_usernames:
                x['username'] = self.rid_usernames[rid]
                if x['username'] not in blocked and x['id'] not in flagged:
                    comments.append(x)
            x['id'] = str(x['id'])
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
        for x in BU.get_reacts(self.config, self.mongo, self.rid, self.ids):
            if x['relationship'].get('id') not in out:
                out[x['relationship'].get('id')] = []

            rids = sorted([str(my_bulletin_secret), str(x.get('bulletin_secret'))], key=str.lower)
            rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().hex()
            
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
        self.human_hash = obj['human_hash']

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
                'human_hash': self.human_hash,
                'registered': self.registered,
                'pending_registration': self.pending_registration,
                'new_messages': self.new_messages,
                'reacts': self.reacts,
                'comments': self.comments,
                'comment_reacts': self.comment_reacts
            }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)
