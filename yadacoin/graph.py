import json
import hashlib
import os
import argparse
import base64
import humanhash
import time

from io import BytesIO
from uuid import uuid4
from ecdsa import NIST384p, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from blockchainutils import BU
from transactionutils import TU
from transaction import *
from crypt import Crypt
from config import Config
from mongo import Mongo


class Graph(object):

    def __init__(self, bulletin_secret, wallet_mode=False):
        Mongo.init()
        self.wallet_mode = wallet_mode
        self.friend_requests = []
        self.sent_friend_requests = []
        self.friends = []
        self.posts = []
        self.logins = []
        self.messages = []
        self.new_messages = []
        self.already_added_messages = []
        self.bulletin_secret = str(bulletin_secret)

        if self.wallet_mode:
            return self.with_private_key()
        else:
            self.registered = False
            self.pending_registration = False
            bulletin_secrets = sorted([str(Config.get_bulletin_secret()), str(bulletin_secret)], key=str.lower)
            rid = hashlib.sha256(str(bulletin_secrets[0]) + str(bulletin_secrets[1])).digest().encode('hex')
            self.rid = rid

            res = Mongo.site_db.usernames.find({"rid": self.rid})
            if res.count():
                self.human_hash = res[0]['username']
            else:
                self.human_hash = humanhash.humanize(self.rid)
            start_height = 0
            # this will get any transactions between the client and server
            nodes = BU.get_transactions_by_rid(bulletin_secret, raw=True, returnheight=True)
            already_done = []
            for node in nodes:
                if node.get('dh_public_key'):
                    test = {'rid': node.get('rid'), 'requester_rid': node.get('requester_id'), 'requested_rid': node.get('requested_id'), 'id': node.get('id')}
                    node['username'] = 'YadaCoin'
                    if test in already_done:
                        continue
                    else:
                        self.friends.append(node)
                        already_done.append(test)

            registered = Mongo.site_db.friends.find({'relationship.bulletin_secret': bulletin_secret})
            if registered.count():
                self.registered = True

            if not self.registered:
                # not regisered, let's check for a pending transaction
                res = Mongo.db.miner_transactions.find({'rid': self.rid, 'public_key': {'$ne': Config.public_key}})
                res2 = Mongo.db.miner_transactions.find({'rid': self.rid, 'public_key': Config.public_key})

                if res.count() and res2.count():
                    self.pending_registration = True

            if self.registered:
                for x in self.friends:
                    for y in x['outputs']:
                        if y['to'] != Config.address:
                            Mongo.site_db.usernames.update({
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

    def with_private_key(self):
        all_relationships = [x for x in BU.get_transactions() if x['rid']]
        self.rid_usernames = dict((x['rid'], x['relationship']['their_username']) for x in all_relationships)

        rids = [x['rid'] for x in all_relationships]
        self.rid_transactions = BU.get_transactions_by_rid(rids, bulletin_secret=self.bulletin_secret, rid=True, raw=True, returnheight=True)

    def get_lookup_rids(self):
        lookup_rids = [self.rid,]
        lookup_rids.extend([x['rid'] for x in BU.get_friend_requests(self.rid)])
        lookup_rids.extend([x['rid'] for x in BU.get_sent_friend_requests(self.rid)])
        return list(set(lookup_rids))

    def get_request_rids_for_rid(self):
        lookup_rids = {}
        for x in BU.get_friend_requests(self.rid):
            if x['rid'] not in lookup_rids:
                lookup_rids[x['rid']] = []
            lookup_rids[x['rid']].append(x['requester_rid'])

        for x in BU.get_sent_friend_requests(self.rid):
            if x['rid'] not in lookup_rids:
                lookup_rids[x['rid']] = []
            lookup_rids[x['rid']].append(x['requested_rid'])

        return lookup_rids

    def get_friend_requests(self):
        if self.wallet_mode:
            self.friend_requests = [x for x in self.rid_transactions if x['relationship'] and x['rid'] and x['public_key'] != Config.public_key]
            return
        else:
            friend_requests = [x for x in BU.get_friend_requests(self.rid)]

        for i, friend_request in enumerate(friend_requests):
            # attach bulletin_secets
            res = Mongo.db.friends.find({'rid': friend_request.get('requester_rid')}, {'_id': 0})
            if res.count():
                friend_requests[i]['bulletin_secret'] = res[0]['relationship']['bulletin_secret']

        self.friend_requests = friend_requests

    def get_sent_friend_requests(self):
        if self.wallet_mode:
            self.sent_friend_requests = [x for x in self.rid_transactions if x['relationship'] and x['rid'] and x['public_key'] == Config.public_key]
            return
        else:
            sent_friend_requests = [x for x in BU.get_sent_friend_requests(self.rid)]

        for i, sent_friend_request in enumerate(sent_friend_requests):
            # attach usernames
            res = Mongo.site_db.usernames.find({'rid': sent_friend_request.get('requested_rid')}, {'_id': 0})
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
                    if x['public_key'] != Config.public_key:
                        messages.append(x)
                self.messages = messages
            for i, x in enumerate(self.messages):
                self.messages[i]['username'] = self.rid_usernames[self.messages[i]['rid']]
            return
        else:
            lookup_rids = self.get_request_rids_for_rid()
            lookup_rids[self.rid] = [self.rid]
            messages = [x for x in BU.get_messages(self.get_lookup_rids())]

            out_messages = []
            for i, message in enumerate(messages):
                # attach usernames
                res = Mongo.site_db.usernames.find({'rid': {'$in': lookup_rids.get(message['rid'])}}, {'_id': 0})
                if res.count():
                    messages[i]['username'] = res[0]['username']
                else:
                    messages[i]['username'] = humanhash.humanize(message.get('rid'))
                exclude = Mongo.db.exclude_messages.find({'id': message.get('id')})
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

        my_bulletin_secret = Config.get_bulletin_secret()
        posts = []
        blocked = [x['username'] for x in Mongo.db.blocked_users.find({'bulletin_secret': self.bulletin_secret})]
        flagged = [x['id'] for x in Mongo.db.flagged_content.find({'bulletin_secret': self.bulletin_secret})]
        for x in BU.get_posts(self.rid):
            rids = sorted([str(my_bulletin_secret), str(x.get('bulletin_secret'))], key=str.lower)
            rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
            res = Mongo.site_db.usernames.find({'rid': rid}, {'_id': 0})
            if res.count():
                x['username'] = res[0]['username']
                if x['username'] not in blocked and x['id'] not in flagged:
                    posts.append(x)
        self.posts = posts

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
                'new_messages': self.new_messages
            }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)
