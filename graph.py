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


class Graph(object):

    def __init__(self, bulletin_secret, for_me=False):
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
            for node in nodes:
                if 'relationship' in node and node.get('relationship'):
                    self.friends.append(node)
                    self.without_private_key(node)

    def with_private_key(self):

        self.friends = BU.get_transactions()

        rids = []
        for friend in self.friends:
            rids.append(friend['rid'])
            bulletin_secret = friend['relationship']['bulletin_secret']
            self.friend_posts.extend(BU.get_bulletins(bulletin_secret))

        possible_friends = BU.get_second_degree_transactions_by_rids(rids)

        self.my_posts.extend(BU.get_bulletins(TU.get_bulletin_secret()))
        nodes = []
        for friend in self.friends:
            nodes.append(self.request_accept_or_request(possible_friends, friend))
        self.friends.extend(nodes)

    def without_private_key(self, node):
        # now search for our rid in requester and requested transactions
        possible_friends = BU.get_second_degree_transactions_by_rids(node.get('rid'))
        friend = self.request_accept_or_request(possible_friends, node)
        to_check = [x.get('requester_rid') for x in possible_friends]
        to_check.extend([x.get('requested_rid') for x in possible_friends])

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
