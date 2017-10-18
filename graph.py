import json
import hashlib
import os
import argparse
import qrcode
import base64

from io import BytesIO
from uuid import uuid4
from ecdsa import NIST384p, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2
from blockchainutils import BU
from transactionutils import TU
from transaction import *


class Graph(object):

    def __init__(self, bulletin_secret, for_me=False):
        self.friend_requests = []
        self.sent_friend_requests = []
        self.friends = []
        self.my_posts = []
        self.friend_posts = []
        self.logins = []

        if for_me:
            return self.with_private_key()
        else:
            nodes = BU.get_transactions_by_rid(bulletin_secret, raw=True)
            # select the transaction that is not created by me
            for node in nodes:
                # print json.dumps(node, indent=4)
                if 'relationship' in node and 'bulletin_secret' not in node['relationship']:
                    self.node = node
                    return self.without_private_key()

    def with_private_key(self):
        self.friends = BU.get_transactions()

        rids = []
        for friend in self.friends:
            rids.append(friend['rid'])
            bulletin_secret = friend['relationship']['bulletin_secret']
            self.friend_posts.extend(BU.get_bulletins(bulletin_secret))

        possible_friends = BU.get_second_degree_transactions_by_rids(rids)

        self.my_posts.extend(BU.get_bulletins(TU.get_bulletin_secret()))

        for friend in self.friends:
            self.request_accept_or_request(possible_friends, friend)

    def without_private_key(self):
        # now search for our rid in requester and requested transactions
        possible_friends = BU.get_second_degree_transactions_by_rids(self.node.get('rid'))
        self.request_accept_or_request(possible_friends, self.node)

    def request_accept_or_request(self, possible_friends, node):
        possible_friends_indexed = dict([(x.get('rid'), x) for x in possible_friends])

        # sent friend requests
        sent_friend_requests = []
        requester_rids = set([x.get('rid') for x in possible_friends if x.get('requester_rid') == node['rid']])
        requested_rids = set([x.get('rid') for x in possible_friends if x.get('requester_rid') != node['rid']])
        for x in requester_rids:
            found = False
            for i in requested_rids:
                if i == x:
                    found = True
                    break
            if not found:
                friend_request = possible_friends_indexed[x]
                if friend_request.get('requester_rid') != friend_request.get('requested_rid'):
                    sent_friend_requests.append(possible_friends_indexed[x])

        # received friend requests
        friend_requests = []
        requester_rids = set([x.get('rid') for x in possible_friends if x.get('requested_rid') == node['rid']])
        requested_rids = set([x.get('rid') for x in possible_friends if x.get('requested_rid') != node['rid']])
        for x in requester_rids:
            found = False
            for i in requested_rids:
                if i == x:
                    found = True
                    break
            if not found:
                friend_request = possible_friends_indexed[x]
                if friend_request.get('requester_rid') != friend_request.get('requested_rid'):
                    friend_requests.append(friend_request)

        for x in sent_friend_requests:
            if len(BU.get_transactions_by_rid(x['rid'], rid=True, raw=True)):
                self.friends.append(x)
            else:
                self.sent_friend_requests.append(x)

        for x in friend_requests:
            if len(BU.get_transactions_by_rid(x['rid'], rid=True, raw=True)):
                self.friends.append(x)
            else:
                self.friend_requests.append(x)

        # get bulletins posted by friends
        for friend in self.friends:
            if 'requested_rid' not in friend and 'requester_rid' not in friend:
                continue
            if node['rid'] == friend['requested_rid']:
                rid = friend['requester_rid']
            else:
                rid = friend['requested_rid']
            server_friend = BU.get_transaction_by_rid(rid, rid=True)
            bulletin_secret = server_friend['relationship']['bulletin_secret']
            self.friend_posts.extend(BU.get_bulletins(bulletin_secret))

        self.friends.append(node)

    def toDict(self):
        return {
            'friends': self.friends,
            'sent_friend_requests': self.sent_friend_requests,
            'friend_requests': self.friend_requests,
            'my_posts': self.my_posts,
            'friend_posts': self.friend_posts,
            'logins': self.logins
        }

    def toJson(self):
        return json.dumps(self.toDict(), indent=4)