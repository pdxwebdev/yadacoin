import json
import hashlib
import os
import argparse
import qrcode
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
from pymongo import MongoClient
from pyfcm import FCMNotification


class Graph(object):

    def __init__(self, bulletin_secret, for_me=False, push_service=None, mongo_client=None):
        mongo_client = MongoClient('localhost')
        self.push_service = push_service
        self.mongo_client = mongo_client
        self.friend_requests = []
        self.sent_friend_requests = []
        self.friends = []
        self.posts = []
        self.logins = []
        self.messages = []
        self.already_added_messages = []
        rids = sorted([str(TU.get_bulletin_secret()), str(bulletin_secret)], key=str.lower)
        rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
        self.rid = rid
        res = mongo_client.yadacoinsite.graph_cache.find({'rid': self.rid})
        if False:
            self.from_dict(res[0]['graph'])
            start_height = res[0]['block_height']
        else:
            res = mongo_client.yadacoinsite.usernames.find({"rid": self.rid})
            if res.count():
                self.human_hash = res[0]['username']
            else:
                self.human_hash = humanhash.humanize(self.rid)
            start_height = 0

        if for_me:
            return self.with_private_key()
        else:
            # this will get any transactions between the client and server
            nodes = BU.get_transactions_by_rid(bulletin_secret, raw=True, returnheight=True)
            already_done = []
            for node in nodes:
                if node.get('dh_public_key'):
                    test = {'rid': node.get('rid'), 'requester_rid': node.get('requester_id'), 'requested_rid': node.get('requested_id')}
                    node['username'] = 'YadaCoin Support'
                    self.friends.append(node)
                    if test in already_done:
                        continue
                    else:
                        already_done.append(test)
                    self.without_private_key(node)
        graph_cache = {}
        graph_cache['graph'] = self.to_dict()
        graph_cache['block_height'] = BU.get_latest_block()['index']
        graph_cache['rid'] = self.rid
        res = mongo_client.yadacoinsite.graph_cache.find({'rid': self.rid})
        if res.count():
            mongo_client.yadacoinsite.graph_cache.update({'_id': res[0]['_id']}, graph_cache)
        else:
            mongo_client.yadacoinsite.graph_cache.insert(graph_cache)

    def with_private_key(self):

        mongo_client = MongoClient('localhost')
        self.friends = [x for x in self.mongo_client.yadacoinsite.friends.find()]
        self.friend_posts = [x for x in self.mongo_client.yadacoinsite.posts.find()]
        rids = []
        possible_friends = BU.get_second_degree_transactions_by_rids(rids)
        self.my_posts = [x for x in self.mongo_client.yadacoinsite.my_posts.find()]
        nodes = []
        for friend in self.friends:
            nodes.append(self.request_accept_or_request(possible_friends, friend))
        self.friends.extend(nodes)

    def get_lookup_rids(self):
        lookup_rids = [self.rid,]
        lookup_rids.extend([x['rid'] for x in BU.get_friend_requests(self.rid)])
        lookup_rids.extend([x['rid'] for x in BU.get_sent_friend_requests(self.rid)])
        return list(set(lookup_rids))

    def get_friend_requests(self):
        friend_requests = [x for x in BU.get_friend_requests(self.rid)]

        for i, friend_request in enumerate(friend_requests):
            # attach bulletin_secets
            res = self.mongo_client.yadacoinsite.friends.find({'rid': friend_request.get('requester_rid')}, {'_id': 0})
            if res.count():
                friend_requests[i]['bulletin_secret'] = res[0]['relationship']['bulletin_secret']

            # attach usernames
            res = self.mongo_client.yadacoinsite.usernames.find({'rid': friend_request.get('requester_rid')}, {'_id': 0})
            if res.count():
                friend_requests[i]['username'] = res[0]['username']
            else:
                friend_requests[i]['username'] = humanhash.humanize(friend_request.get('requester_rid'))
        return friend_requests

    def get_sent_friend_requests(self):
        sent_friend_requests = [x for x in BU.get_sent_friend_requests(self.rid)]
        for i, sent_friend_request in enumerate(sent_friend_requests):
            # attach usernames
            res = self.mongo_client.yadacoinsite.usernames.find({'rid': sent_friend_request.get('requested_rid')}, {'_id': 0})
            if res.count():
                sent_friend_requests[i]['username'] = res[0]['username']
            else:
                sent_friend_requests[i]['username'] = humanhash.humanize(sent_friend_request.get('requested_rid'))
        return sent_friend_requests

    def get_messages(self):
        return [x for x in BU.get_messages(self.get_lookup_rids())]

    def without_private_key(self, node, start_height=None):
        self.friend_requests = self.get_friend_requests()
        self.sent_friend_requests = self.get_sent_friend_requests()
        self.messages = self.get_messages()

        mutual_bulletin_secrets = []
        for transaction in BU.get_transactions_by_rid(self.get_lookup_rids(), rid=True):
            if 'bulletin_secret' in transaction['relationship']:
                mutual_bulletin_secrets.append(transaction['relationship']['bulletin_secret'])

        fcm_hits = [x for x in self.mongo_client.yadacoinsite.fcmtokens.find({'rid':{'$in': self.get_lookup_rids()}})]
        for transaction in BU.get_posts():
            exists = self.mongo_client.yadacoinsite.posts.find({
                'id': transaction.get('id')
            })
            if exists.count():
                if not exists[0]['skip']:
                    if exists[0]['bulletin_secret'] in mutual_bulletin_secrets:
                        transaction['relationship'] = {'postText': exists[0]['postText']}
                        self.posts.append(transaction)
                continue
            for bs in mutual_bulletin_secrets:
                try:
                    crypt = Crypt(hashlib.sha256(bs).hexdigest())
                    decrypted = crypt.decrypt(transaction['relationship'])
                    data = json.loads(decrypted)
                    if 'postText' in data:
                        self.mongo_client.yadacoinsite.posts.remove({'id': transaction.get('id')})
                        transaction['relationship'] = data
                        result = self.push_service.notify_multiple_devices(
                            registration_ids=[x['token'] for x in fcm_hits],
                            message_title='New Post From A Friend!',
                            message_body=data['postText'],
                            extra_kwargs={'priority': 'high'}
                        )
                        self.mongo_client.yadacoinsite.posts.remove({'id': transaction.get('id')})
                        self.mongo_client.yadacoinsite.posts.insert({
                            'bulletin_secret': bs,
                            'postText': data['postText'],
                            'rid': transaction.get('rid'),
                            'id': transaction.get('id'),
                            'requester_rid': transaction.get('requester_rid'),
                            'requested_rid': transaction.get('requested_rid'),
                            'skip': False
                        })
                        self.posts.append(transaction)
                except:
                    exists = self.mongo_client.yadacoinsite.posts.find({'id': transaction.get('id')})
                    if not exists.count():
                        self.mongo_client.yadacoinsite.posts.insert({
                            'rid': transaction.get('rid'),
                            'id': transaction.get('id'),
                            'requester_rid': transaction.get('requester_rid'),
                            'requested_rid': transaction.get('requested_rid'),
                            'skip': True
                        })



    def request_accept_or_request(self, possible_friends, node):
        mongo_client = MongoClient('localhost')
        possible_friends_indexed = {}
        for x in possible_friends:
            if x.get('rid') not in possible_friends_indexed:
                possible_friends_indexed[x.get('rid')] = []
            possible_friends_indexed[x.get('rid')].append(x)

        lookup_rids = []
        # sent friend requests
        out_sent_friend_requests = []
        requester_rids = set([x.get('rid') for x in possible_friends if x.get('requester_rid') == node['rid']])
        requested_rids = set([x.get('rid') for x in possible_friends if x.get('requester_rid') != node['rid']])
        for x in requester_rids:
            found = False
            for i in requested_rids:
                if i == x:
                    found = True
                    break
            if not found:
                friend_requests = possible_friends_indexed[x]
                for friend_request in friend_requests:
                    if friend_request.get('requester_rid') != friend_request.get('requested_rid'):
                        res = mongo_client.yadacoinsite.usernames.find({'rid': friend_request.get('requested_rid')}, {'_id': 0})
                        if res.count():
                            friend_request['username'] = res[0]['username']
                        else:
                            friend_request['username'] = humanhash.humanize(friend_request.get('requested_rid'))


        # received friend requests
        out_friend_requests = []
        requester_rids = set([x.get('rid') for x in possible_friends if x.get('requested_rid') == node['rid']])
        requested_rids = set([x.get('rid') for x in possible_friends if x.get('requested_rid') != node['rid']])
        for x in requester_rids:
            found = False
            for i in requested_rids:
                if i == x:
                    found = True
                    break
            if not found:
                friend_requests = possible_friends_indexed[x]
                for friend_request in friend_requests:
                    # only get requests where the person didn't request theself? lol
                    if friend_request.get('requester_rid') != friend_request.get('requested_rid'):
                        # attach a username to the transaction
                        res = mongo_client.yadacoinsite.usernames.find({'rid': friend_request.get('requester_rid')}, {'_id': 0})
                        if res.count():
                            friend_request['username'] = res[0]['username']
                        else:
                            friend_request['username'] = humanhash.humanize(friend_request.get('requester_rid'))
                        # attach their bulletin secret so they can accept the request
                        out_friend_requests.append(friend_request)
                        lookup_rids.append(friend_request.get('rid'))

        # sent and recieved messages
        out_messages = []
        for transaction in BU.get_transactions_by_rid(lookup_rids, rid=True, raw=True, returnheight=True):
            if transaction.get('id') not in self.already_added_messages and transaction.get('rid'):
                if not transaction.get('dh_public_key'):
                    self.already_added_messages.append(transaction.get('id'))
                    out_messages.append(transaction)

        return out_friend_requests, out_sent_friend_requests, out_messages

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
        return {
            'friends': self.friends,
            'sent_friend_requests': self.sent_friend_requests,
            'friend_requests': self.friend_requests,
            'posts': self.posts,
            'logins': self.logins,
            'messages': self.messages,
            'rid': self.rid,
            'human_hash': self.human_hash
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)
