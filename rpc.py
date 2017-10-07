import json
import hashlib
import os
import argparse
import qrcode
import base64

from io import BytesIO
from uuid import uuid4
from flask import Flask, request, render_template, session, redirect
from ecdsa import NIST384p, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain
from Crypto.Cipher import AES
from pbkdf2 import PBKDF2


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
    def __init__(self, bulletin_secret, shared_secret, mode='send', value=1, fee=0.1, requester_rid=None, requested_rid=None, challenge_code=None):
        print '!!!!', mode
        self.bulletin_secret = bulletin_secret
        self.mode = mode
        self.challenge_code = challenge_code
        self.requester_rid = requester_rid
        self.requested_rid = requested_rid
        self.rid = self.generate_rid()
        self.public_key = public_key
        self.private_key = private_key
        self.value = value
        self.fee = fee
        self.shared_secret = shared_secret
        self.relationship = self.generate_relationship()
        self.cipher = Crypt(private_key)
        self.encrypted_relationship = self.cipher.encrypt(self.relationship.to_json())
        self.transaction_signature = self.generate_transaction_signature()
        self.transaction = self.generate_transaction()

    def generate_rid(self):
        my_bulletin_secret = TU.generate_deterministic_signature()
        if my_bulletin_secret == self.bulletin_secret:
            raise BaseException('bulletin secrets are identical. do you love yourself so much that you want a relationship on the blockchain?')
        if self.mode == 'send':
            string = my_bulletin_secret + self.bulletin_secret
        else:
            string = self.bulletin_secret + my_bulletin_secret
        return hashlib.sha256(string).digest().encode('hex')

    def generate_relationship(self):
        return Relationship(
            self.shared_secret,
            self.bulletin_secret
        )

    def generate_transaction(self):
        return Transaction(
            self.rid,
            self.transaction_signature,
            self.encrypted_relationship,
            self.public_key,
            self.value,
            self.fee,
            self.requester_rid,
            self.requested_rid,
            self.challenge_code
        )

    def generate_transaction_signature(self):
        return TU.generate_signature(
            self.rid + self.encrypted_relationship + str(self.value) + str(self.fee)
        )


class Transaction(object):
    def __init__(self, rid, transaction_signature, relationship, public_key, value=1, fee=0.1, requester_rid=None, requested_rid=None, challenge_code=None):
        self.rid = rid
        self.transaction_signature = transaction_signature
        self.relationship = relationship
        self.public_key = public_key
        self.value = value
        self.fee = fee
        self.requester_rid = requester_rid
        self.requested_rid = requested_rid
        self.challenge_code = challenge_code

    def __dict__(self):
        ret = {
            'rid': self.rid,
            'id': self.transaction_signature,
            'relationship': self.relationship,
            'public_key': self.public_key,
            'value': self.value,
            'fee': self.fee
        }
        if self.requester_rid:
            ret['requester_rid'] = self.requester_rid
        if self.requested_rid:
            ret['requested_rid'] = self.requested_rid
        if self.challenge_code:
            ret['challenge_code'] = self.challenge_code
        return ret

    def to_json(self):
        return json.dumps(self.__dict__())


class Relationship(object):
    def __init__(self, shared_secret, bulletin_secret):
        self.shared_secret = shared_secret
        self.bulletin_secret = bulletin_secret

    def __dict__(self):
        return {
            'shared_secret': self.shared_secret,
            'bulletin_secret': self.bulletin_secret
        }

    def to_json(self):
        return json.dumps(self.__dict__())


class Crypt(object):  # Relationship Utilities
    def __init__(self, shared_secret):
        self.key = PBKDF2(shared_secret, 'salt', 400).read(32)
    def encrypt(self, s):
        from Crypto import Random
        BS = AES.block_size
        iv = Random.new().read(BS)
        s = s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return (iv + cipher.encrypt(buffer(s))).encode('hex')
    def decrypt(self, enc):
        enc = enc.decode("hex")
        iv = enc[:16]
        enc = enc[16:]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        s = cipher.decrypt(enc)
        return s[0:-ord(s[-1])]


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


class BU(object):  # Blockchain Utilities
    @staticmethod
    def get_blocks():
        with open('blockchain.json', 'r') as f:
            blocks = json.loads(f.read()).get('blocks')
        return blocks

    @staticmethod
    def get_transactions():
        transactions = []
        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                try:
                    cipher = Crypt(private_key)
                    decrypted = cipher.decrypt(transaction['relationship'])
                    relationship = json.loads(decrypted)
                    transaction['relationship'] = relationship
                    transactions.append(transaction)
                except:
                    continue
        return transactions

    @staticmethod
    def get_relationships():
        relationships = []
        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                try:
                    cipher = Crypt(private_key)
                    decrypted = cipher.decrypt(transaction['relationship'])
                    relationship = json.loads(decrypted)
                    relationships.append(relationship)
                except:
                    continue
        return relationships

    @staticmethod
    def get_transaction_by_rid(selector, rid=False, raw=False):
        ds = TU.generate_deterministic_signature()
        if not rid:
            selectors = [
                TU.hash(ds+selector),
                TU.hash(selector+ds)
            ]
        else:
            selectors = [selector, ]

        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                if transaction.get('rid') in selectors:
                    if 'relationship' in transaction:
                        if not raw:
                            try:
                                cipher = Crypt(private_key)
                                decrypted = cipher.decrypt(transaction['relationship'])
                                relationship = json.loads(decrypted)
                                transaction['relationship'] = relationship
                            except:
                                continue
                    return transaction

    @staticmethod
    def get_transactions_by_rid(selector, rid=False, raw=False):
        ds = TU.generate_deterministic_signature()
        if not rid:
            selectors = [
                TU.hash(ds+selector),
                TU.hash(selector+ds)
            ]
        else:
            selectors = [selector, ]

        transactions = []
        for block in BU.get_blocks():
            for transaction in block.get('transactions'):
                if transaction.get('rid') in selectors:
                    if 'relationship' in transaction:
                        if not raw:
                            try:
                                cipher = Crypt(private_key)
                                decrypted = cipher.decrypt(transaction['relationship'])
                                relationship = json.loads(decrypted)
                                transaction['relationship'] = relationship
                            except:
                                continue
                    transactions.append(transaction)
        return transactions


@app.route('/')
def index():  # demo site
    bulletin_secret = TU.generate_deterministic_signature()
    print bulletin_secret
    shared_secret = str(uuid4())
    print 'shared_secret: ', shared_secret
    existing = BU.get_transactions()

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps({
        'shared_secret': shared_secret,
        'bulletin_secret': bulletin_secret,
        'blockchainurl': 'http://{host}:{post}/transaction'.format(
            host=config.get('host'),
            post=config.get('port'),
        ),
        'callbackurl': 'http://{host}:{post}/create-relationship'.format(
            host=config.get('host'),
            post=config.get('port')
        )
    }))
    qr.make(fit=True)

    out = BytesIO()
    qr_img = qr.make_image()
    qr_img = qr_img.convert("RGBA")
    qr_img.save(out, 'PNG')
    out.seek(0)
    return render_template(
        'index.html',
        bulletin_secret=bulletin_secret,
        shared_secret=shared_secret,
        existing=existing,
        qrcode=u"data:image/png;base64," + base64.b64encode(out.getvalue()).decode('ascii')
    )

@app.route('/create-relationship', methods=['GET', 'POST'])
def create_relationship():  # demo site
    if request.method == 'GET':
        bulletin_secret = request.args.get('bulletin_secret')
        shared_secret = request.args.get('shared_secret')
        requester_rid = request.args.get('requester_rid')
        requested_rid = request.args.get('requested_rid')
    else:
        bulletin_secret = request.json.get('bulletin_secret')
        shared_secret = request.json.get('shared_secret')
        requester_rid = request.json.get('requester_rid')
        requested_rid = request.json.get('requested_rid')

    test = BU.get_transactions_by_rid(bulletin_secret)  # temporary duplicate prevention
    if len(test) > 1:
        return json.dumps(test)

    existing = BU.get_transaction_by_rid(bulletin_secret)

    state = 'receive'  # forcing receive until a real workflow is created

    transaction = TransacationFactory(
        bulletin_secret,
        shared_secret,
        state,
        1,
        0.1,
        requester_rid,
        requested_rid
    )

    TU.save(transaction.transaction)

    my_bulletin_secret = TU.generate_deterministic_signature()
    if state == 'send':
        return render_template(
            'create-relationship.html',
            ref=request.args.get('ref'),
            shared_secret=shared_secret,
            bulletin_secret=my_bulletin_secret)
    #else:
        #cipher = Crypt(shared_secret)
        #challenge = cipher.encrypt(session['challenge_code']).encode('hex')
        #return redirect(
        #    'http://localhost:5001/process-challenge?challenge=%s&bulletin_secret=%s&ref=%s' % (
        #        challenge,
        #        my_bulletin_secret,
        #        'http%3A%2F%2Flocalhost%3A5000%2Flogin')
        #)
    return ''


@app.route('/login', methods=['GET', 'POST'])
def login():  # demo site
    session['challenge_code'] = str(uuid4())
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(json.dumps({
        'callbackurl': 'http://{host}:{post}/transaction'.format(
            host=config.get('host'),
            post=config.get('port')
        ),
        'challenge_code': session['challenge_code'],
        'bulletin_secret': TU.generate_deterministic_signature()
    }))
    qr.make(fit=True)

    out = BytesIO()
    qr_img = qr.make_image()
    qr_img = qr_img.convert("RGBA")
    qr_img.save(out, 'PNG')
    out.seek(0)
    return render_template('process-challenge.html',
        qrcode=u"data:image/png;base64," + base64.b64encode(out.getvalue()).decode('ascii')
    )

@app.route('/login-status')
def login_status():
    for block in BU.get_blocks():
        for transaction in block['transactions']:
            if 'challenge_code' in transaction and session['challenge_code'] == transaction['challenge_code']:
                tests = BU.get_transactions_by_rid(transaction['rid'], rid=True)
                for test in tests:
                    if 'relationship' in test and 'shared_secret' in test['relationship']:
                        friend = test
                cipher = Crypt(hashlib.sha256(friend['relationship']['shared_secret']).digest().encode('hex'))
                answer = cipher.decrypt(transaction['answer'])
                if answer == transaction['challenge_code']:
                    return json.dumps({'authenticated': True, 'rid': transaction['rid']})
    return session['challenge_code']



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


@app.route('/transaction', methods=['GET', 'POST'])
def transaction():
    if request.method == 'POST':
        items = request.json
        if not isinstance(items, list):
            items = [items, ]
        else:
            items = [item for item in items]
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
        print request.content_type
        print request.get_json()
        return json.dumps(request.get_json())
    else:
        rid = request.args.get('rid')
        print rid
        transaction = BU.get_transaction_by_rid(rid, rid=True, raw=True)
        print transaction
        return json.dumps(transaction)


app.debug = True
app.secret_key = '23ljk2l3k4j'
app.run(host=config.get('host'), port=config.get('port'))
