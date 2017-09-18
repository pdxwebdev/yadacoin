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

@app.route('/')
def index():
    sk = SigningKey.from_string(key.decode('hex'))
    signature = sk.sign_deterministic(hashlib.sha256(key).digest().encode('hex'))
    hashsig1 = hashlib.sha256(signature.encode('hex')).digest().encode('hex')
    signature = sk.sign_deterministic(hashlib.sha256(key).digest().encode('hex'))
    hashsig2 = hashlib.sha256(signature.encode('hex')).digest().encode('hex')
    print hashsig1
    return render_template(
        'index.html',
        rel_gen1=hashsig1,
        rel_gen2=hashsig2,
    )


@app.route('/sign')
def sign():
    sk = SigningKey.from_string(key.decode('hex'))
    signature = sk.sign_deterministic(hashlib.sha256(key).digest().encode('hex'))
    hashsig = hashlib.sha256(signature.encode('hex')).digest().encode('hex')
    rid = hashlib.sha256(hashsig+request.args['input_signature']).digest().encode('hex')
    print 'sign signature: ', hashsig
    print 'sign input_signature: ', request.args['input_signature']
    return render_template('sign.html', ref=request.args['ref'], final_signature=rid)


@app.route('/create-login')
def create_login():
    sk = SigningKey.from_string(key.decode('hex'))
    signature = sk.sign_deterministic(hashlib.sha256(key).digest().encode('hex'))
    hashsig = hashlib.sha256(signature.encode('hex')).digest().encode('hex')
    print 'create_login signature: ', hashsig
    return render_template('create-login.html', ref=request.args['ref'], signature=hashsig)


@app.route('/login', methods=['POST'])
def login():
    sk = SigningKey.from_string(key.decode('hex'))
    signature = sk.sign_deterministic(hashlib.sha256(key).digest().encode('hex'))
    hashsig = hashlib.sha256(signature.encode('hex')).digest().encode('hex')
    rid = hashlib.sha256(request.form['input_signature']+hashsig).digest().encode('hex')
    print 'login signature: ', hashsig
    print 'login input_signature: ', request.form['input_signature']
    with open('blockchain.json', 'r') as f:
        blocks = json.loads(f.read()).get('blocks')
    for block in blocks:
        if rid in block.get('relationships'):
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
    if request.method == 'GET':
        return render_template('friend-request.html', rel_gen=request.args['rel_gen'])
    sk = SigningKey.from_string(key.decode('hex'))
    print hashlib.sha256(request.form.get('to')+key).digest().encode('hex')
    signature = sk.sign_deterministic(hashlib.sha256(request.form.get('to')+key).digest().encode('hex'))  # indexer reference baked into request's "return signature"
    friend_request = {
        'to': request.form.get('to'),
        'rid': signature.encode('hex')
    }
    with open('miner_friend_requests.json', 'r+') as f:
        existing = json.loads(f.read())
        existing.append(friend_request)
        f.seek(0)
        f.write(json.dumps(existing, indent=4))
        f.truncate()

    return json.dumps(existing)


@app.route('/friend-accept', methods=['POST'])
def friend_accept():
    # add it to friend request pool to be included in a block
    signature = sk.sign(request.form.get('to'))
    friend_accepts = {
        'to': request.form.get('to'),
        'rid': signature.encode('hex')
    }
    with open('miner_friend_accepts.json', 'r+') as f:
        existing = json.loads(f.read())
        existing.append(friend_request)
        f.seek(0)
        f.write(json.dumps(existing, indent=4))
        f.truncate()

    return json.dumps(existing)

app.debug = True
app.secret_key = '23ljk2l3k4j'
app.run(port=config.get('port'))
