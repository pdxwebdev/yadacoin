import json
import hashlib
import os
import argparse

from uuid import uuid4
from flask import Flask, request, render_template, session
from ecdsa import NIST384p, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from simplecrypt import encrypt, decrypt, DecryptionException


parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--conf',
                help='set your config file')
args = parser.parse_args()

with open(args.conf) as f:
    config = json.loads(f.read())

public_key = config.get('public_key')
private_key = config.get('private_key')
# print sk.get_verifying_key().to_string().encode('hex')
# vk2 = VerifyingKey.from_string(pk.decode('hex'))
# print vk2.verify(signature, "message")

app = Flask(__name__)


class TransacationFactory(object):
    def __init__(self, receiver_sig, shared_secret, value=1, fee=0.1):
        self.sender_sig = TU.generate_deterministic_signature()
        self.public_key = public_key
        self.private_key = private_key
        self.value = value
        self.fee = fee
        self.shared_secret = shared_secret
        relationship = self.generate_relationship()
        self.encrypted_relationship = self.encrypt(relationship.to_json())
        self.transaction_signature = self.generate_transaction_signature()
        return self.generate_transaction()

    def generate_relationship(self):
        return Relationship(self.rid, self.shared_secret)

    def generate_transaction(self):
        return Transaction(
            self.transaction_signature,
            self.relationship,
            self.public_key,
            self.value,
            self.fee
        )

    def generate_transaction_signature(self):
        TU.generate_signature(
            self.encrypted_relationship +
            self.value +
            self.fee
        )


class Transaction(object):
    def __init__(self, signature, relationship, public_key, value=1, fee=0.1):
        self.signature = signature
        self.relationship = relationship
        self.public_key = public_key
        self.value = value
        self.fee = fee

    def __dict__(self):
        return {
            'id': self.signature,
            'relationship': self.relationship,
            'public_key': self.public_key,
            'value': self.value,
            'fee': self.fee
        }

    def to_json(self):
        return json.dumps(self.__dict__())


class Relationship(object):
    def __init__(self, rid, shared_secret):
        self.rid = rid
        self.shared_secret = shared_secret

    def __dict__(self):
        return {
            'rid': self.rid,
            'shared_secret': self.shared_secret
        }

    def to_json(self):
        return json.dumps(self.__dict__())


class TU(object):  # Transaction Utilities
    @staticmethod
    def hash(message):
        return hashlib.sha256(message).digest().encode('hex')

    @staticmethod
    def generate_deterministic_signature():
        sk = SigningKey.from_string(private_key.decode('hex'))
        signature = sk.sign_deterministic(hashlib.sha256(private_key).digest().encode('hex'))
        return hashlib.sha256(signature.encode('hex')).digest().encode('hex')

    @staticmethod
    def generate_signature(message):
        sk = SigningKey.from_string(private_key.decode('hex'))
        signature = sk.sign(message)
        return signature.encode('hex')

    @staticmethod
    def encrypt(message):
        return encrypt(key, message).encode('hex')

    @staticmethod
    def save(items):
        if not isinstance(items, list):
            items = [items.__dict__(), ]
        else:
            items = [item.__dict__() for item in items]

        with open('miner_transactions.json', 'a+') as f:
            try:
                existing = json.loads(f.read())
            except:
                existing = []
            existing.extend(items)
            f.seek(0)
            f.truncate()
            f.write(json.dumps(existing, indent=4))
            f.truncate()


@app.route('/')
def index():
    hashsig = TU.generate_deterministic_signature()
    print hashsig

    return render_template(
        'index.html',
        rel_gen=hashsig,
        shared_secret=str(uuid4())
    )


@app.route('/send-friend-request', methods=['GET', 'POST'])
def send_friend_request():
    transaction = TransacationFactory(
        request.args['input_signature'],
        request.args['shared_secret']
    )
    TU.save(transaction)
    return render_template(
        'send-friend-request.html',
        ref=request.args.get('ref'),
        signature=hashsig,
        requested_rid=request.args.get('requested_rid'))


@app.route('/accept-friend-request', methods=['GET', 'POST'])
def accept_friend_request():
    # add it to friend request pool to be included in a block
    if request.method == 'GET':
        return render_template(
            'accept-friend-request.html',
            shared_secret=shared_secret,
        )
    hashsig = generate_deterministic_signature()
    relationship = {
        'rid': hashlib.sha256(request.form['input_signature']+hashsig).digest().encode('hex'),
        'requester_rid': request.form['requester_rid'],
        'requested_rid': request.form['requested_rid']
    }
    with open('miner_transactions.json', 'a+') as f:
        try:
            existing = json.loads(f.read())
        except:
            existing = []
        existing.append(relationship)
        f.seek(0)
        f.truncate()
        f.write(json.dumps(existing, indent=4))
        f.truncate()

    return json.dumps(existing)


@app.route('/login', methods=['POST'])
def login():
    hashsig = TU.generate_deterministic_signature()
    rid = hashlib.sha256(request.form['input_signature']+hashsig).digest().encode('hex')
    print 'login signature: ', hashsig
    print 'login input_signature: ', request.form['input_signature']
    with open('blockchain.json', 'r') as f:
        blocks = json.loads(f.read()).get('blocks')
    for block in blocks:
        for relationship in block.get('transactions'):
            try:
                decrypted = decrypt(key, relationship['body'].decode('hex'))
            except DecryptionException:
                continue

            transaction = json.loads(decrypted)
            if rid == transaction['rid']:
                return json.dumps({'authenticated': True})
    return json.dumps({'authenticated': False})


@app.route('/get-block/<index>')
def get_block(index=None):
    return json.dumps({'hi':index})


@app.route('/get-latest-block')
def get_latest_block():
    return json.dumps({'hi':'latest block'})


@app.route('/get-chain')
def get_chain():
    # some type of generator
    return json.dumps()


@app.route('/get-peers')
def get_peers():
    with open('peers.json') as f:
        peers = f.read()
    return json.dumps({'peers': peers})


@app.route('/post-block', methods=['POST'])
def post_block():
    print request.content_type
    print request.get_json()
    return json.dumps(request.get_json())

app.debug = True
app.secret_key = '23ljk2l3k4j'
app.run(port=config.get('port'))
