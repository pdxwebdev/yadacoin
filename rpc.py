import json
import hashlib
import os
import argparse

from uuid import uuid4
from flask import Flask, request, render_template, session
from ecdsa import NIST384p, SigningKey
from ecdsa.util import randrange_from_seed__trytryagain



parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('--conf',
                help='set your config file')
args = parser.parse_args()

with open(args.conf) as f:
    config = json.loads(f.read())

key = config.get('private_key')
# print sk.get_verifying_key().to_string().encode('hex')
# vk2 = VerifyingKey.from_string(pk.decode('hex'))
# print vk2.verify(signature, "message")

app = Flask(__name__)


def generate_signature():
    sk = SigningKey.from_string(key.decode('hex'))
    signature = sk.sign_deterministic(hashlib.sha256(key).digest().encode('hex'))
    return hashlib.sha256(signature.encode('hex')).digest().encode('hex')


@app.route('/')
def index():
    hashsig = generate_signature()
    print hashsig
    with open('friend_requests-5000.json', 'r') as f:
        try:
            friend_requests = json.loads(f.read())
            friend_request = friend_requests[len(friend_requests)-1]
        except:
            friend_request = {}
    if friend_request.get('signature'):
        requester_rid = hashlib.sha256(friend_request.get('signature')+hashsig).digest().encode('hex')
    else:
        requester_rid = None

    return render_template(
        'index.html',
        rel_gen=hashsig,
        requested_rid=friend_request.get('requested_rid'),
        requester_rid=requester_rid,
        input_signature=friend_request.get('signature')
    )


@app.route('/send-friend-request', methods=['GET', 'POST'])
def send_friend_request():
    hashsig = generate_signature()
    return render_template(
        'send-friend-request.html',
        ref=request.args.get('ref'),
        signature=hashsig,
        requested_rid=request.args.get('requested_rid'))


@app.route('/sign')
def sign():
    hashsig = generate_signature()
    rid = hashlib.sha256(hashsig+request.args['input_signature']).digest().encode('hex')
    print 'sign signature: ', hashsig
    print 'sign input_signature: ', request.args['input_signature']
    return render_template('sign.html', ref=request.args['ref'], final_signature=rid)


@app.route('/create-login')
def create_login():
    hashsig = generate_signature()
    print 'create_login signature: ', hashsig
    return render_template('create-login.html', ref=request.args['ref'], signature=hashsig)


@app.route('/login', methods=['POST'])
def login():
    hashsig = generate_signature()
    rid = hashlib.sha256(request.form['input_signature']+hashsig).digest().encode('hex')
    print 'login signature: ', hashsig
    print 'login input_signature: ', request.form['input_signature']
    with open('blockchain.json', 'r') as f:
        blocks = json.loads(f.read()).get('blocks')
    for block in blocks:
        for relationship in block.get('relationships'):
            if rid == relationship['rid']:
                return json.dumps({'authenticated': True})
    return json.dumps({'authenticated': False})


@app.route('/relate', methods=['POST'])
def relate():
    # idempotent
    relationship = {'rid': request.form['final_signature']}
    with open('miner_relationships.json', 'a+') as f:
        try:
            existing = json.loads(f.read())
        except:
            existing = []
        existing.append(relationship)
        f.seek(0)
        f.truncate()
        relationships_dict = dict([(c['rid'], c) for c in existing])
        relationships = [c for e, c in relationships_dict.iteritems()]
        f.write(json.dumps(relationships, indent=4))
        f.truncate()
    return json.dumps(relationship)


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


@app.route('/friend-request', methods=['GET', 'POST'])
def friend_request():
    # add it to friend request pool to be included in a block
    friend_request = {
        'signature': request.form.get('signature'),
        'requested_rid': request.form.get('requested_rid')
    }
    with open('friend_requests-5000.json', 'a+') as f:
        try:
            existing = json.loads(f.read())
        except:
            existing = []
        existing.append(friend_request)
        f.seek(0)
        f.truncate()
        f.write(json.dumps(existing, indent=4))
        f.truncate()

    return json.dumps(existing)


@app.route('/accept-friend-request', methods=['GET', 'POST'])
def accept_friend_request():
    # add it to friend request pool to be included in a block
    if request.method == 'GET':
        return render_template(
            'accept-friend-request.html',
            requester_rid=request.args['requester_rid'],
            requested_rid=request.args['requested_rid'],
            input_signature=request.args['input_signature'],
        )
    hashsig = generate_signature()
    relationship = {
        'rid': hashlib.sha256(request.form['input_signature']+hashsig).digest().encode('hex'),
        'requester_rid': request.form['requester_rid'],
        'requested_rid': request.form['requested_rid']
    }
    with open('miner_relationships.json', 'a+') as f:
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

app.debug = True
app.secret_key = '23ljk2l3k4j'
app.run(port=config.get('port'))
