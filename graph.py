import json
import hashlib
import os
import argparse
import qrcode
import base64
import humanhash

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
        self.push_service = push_service
        self.mongo_client = mongo_client
        self.friend_requests = []
        self.sent_friend_requests = []
        self.friends = []
        self.my_posts = []
        self.friend_posts = []
        self.logins = []
        self.messages = []
        rids = sorted([str(TU.get_bulletin_secret()), str(bulletin_secret)], key=str.lower)
        rid = hashlib.sha256(str(rids[0]) + str(rids[1])).digest().encode('hex')
        self.rid = rid
        self.human_hash = humanhash.humanize(self.rid)

        if for_me:
            return self.with_private_key()
        else:
            nodes = BU.get_transactions_by_rid(bulletin_secret, raw=True)
            # select the transaction that is not created by me
            friend_posts = {}
            for node in nodes:
                if 'relationship' in node and node.get('relationship'):
                    self.friends.append(node)
                    self.without_private_key(node, friend_posts)
            self.friend_posts.extend([x for i, x in friend_posts.items()])

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

    def without_private_key(self, node, friend_posts):
        # now search for our rid in requester and requested transactions
        possible_friends = BU.get_second_degree_transactions_by_rids(node.get('rid'))
        friend = self.request_accept_or_request(possible_friends, node)
        to_check = [x.get('requester_rid') for x in possible_friends]
        to_check.extend([x.get('requested_rid') for x in possible_friends])
        mongo_client = MongoClient('localhost')
        more = mongo_client.yadacoin.blocks.find({'transactions.requested_rid': node.get('rid')})
        for x in more:
            for t in x['transactions']:
                if 'requester_rid' in t and t['requester_rid'] == node.get('rid'):
                    to_check.append(t['requester_rid'])
        more = mongo_client.yadacoin.blocks.find({'transactions.requester_rid': node.get('rid')})
        for x in more:
            for t in x['transactions']:
                if 'requested_rid' in t and t['requested_rid'] == node.get('rid'):
                    to_check.append(t['requested_rid'])
        to_check = list(set(to_check))
        fcm_hits = [x for x in mongo_client.yadacoinsite.fcmtokens.find({'rid':{'$in': to_check}})]
        mutual_bulletin_secrets = []
        for transaction in BU.get_transactions_by_rid(to_check, rid=True):
            if 'relationship' in transaction:
                if 'bulletin_secret' in transaction['relationship']:
                    mutual_bulletin_secrets.append(transaction['relationship']['bulletin_secret'])

        for block in BU.collection.find({"transactions": {"$elemMatch": {"relationship": {"$ne": ""}}}}):
            for transaction in block['transactions']:
                if not  transaction.get('relationship'):
                    continue
                exists = mongo_client.yadacoinsite.posts.find({
                    'id': transaction.get('id')
                })
                if exists.count():
                    if not exists[0]['skip']:
                        if exists[0]['bulletin_secret'] in mutual_bulletin_secrets:
                            transaction['relationship'] = {'postText': exists[0]['postText']}
                            friend_posts[transaction['relationship']['postText']] = transaction
                    continue

                for bs in mutual_bulletin_secrets:
                    try:
                        crypt = Crypt(hashlib.sha256(bs).hexdigest())
                        decrypted = crypt.decrypt(transaction['relationship'])
                        data = json.loads(decrypted)
                        if 'postText' in data:
                            mongo_client.yadacoinsite.posts.remove({'id': transaction.get('id')})
                            transaction['relationship'] = data
                            friend_posts[transaction['relationship']['postText']] = transaction
                            result = self.push_service.notify_multiple_devices(
                                registration_ids=[x['token'] for x in fcm_hits],
                                message_title='New Post From A Friend!',
                                message_body=data['postText'],
                                extra_kwargs={'priority': 'high'}
                            )
                            mongo_client.yadacoinsite.posts.remove({'id': transaction.get('id')})
                            mongo_client.yadacoinsite.posts.insert({
                                'bulletin_secret': bs,
                                'postText': data['postText'],
                                'rid': transaction.get('rid'),
                                'id': transaction.get('id'),
                                'requester_rid': transaction.get('requester_rid'),
                                'requested_rid': transaction.get('requested_rid'),
                                'skip': False
                            })
                    except:
                        exists = mongo_client.yadacoinsite.posts.find({'id': transaction.get('id')})
                        if not exists.count():
                            mongo_client.yadacoinsite.posts.insert({
                                'rid': transaction.get('rid'),
                                'id': transaction.get('id'),
                                'requester_rid': transaction.get('requester_rid'),
                                'requested_rid': transaction.get('requested_rid'),
                                'skip': True
                            })



    def request_accept_or_request(self, possible_friends, node):
        possible_friends_indexed = {}
        for x in possible_friends:
            if x.get('rid') not in possible_friends_indexed:
                possible_friends_indexed[x.get('rid')] = []
            possible_friends_indexed[x.get('rid')].append(x)

        lookup_rids = []
        # sent friend requests
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
                        self.sent_friend_requests.append(friend_request)
                        lookup_rids.append(friend_request.get('rid'))

        # received friend requests
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
                    if friend_request.get('requester_rid') != friend_request.get('requested_rid'):
                        self.friend_requests.append(friend_request)
                        lookup_rids.append(friend_request.get('rid'))

        already_added = []
        for transaction in BU.get_transactions_by_rid(lookup_rids, rid=True, raw=True):
            if transaction.get('hash') not in already_added:
                already_added.append(transaction.get('hash'))
                self.messages.append(transaction)

        return node

    def to_dict(self):
        return {
            'friends': self.friends,
            'sent_friend_requests': self.sent_friend_requests,
            'friend_requests': self.friend_requests,
            'my_posts': self.my_posts,
            'friend_posts': self.friend_posts,
            'logins': self.logins,
            'messages': self.messages,
            'rid': self.rid,
            'human_hash': self.human_hash
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)
