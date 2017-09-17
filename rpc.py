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
    session.setdefault('rel_gen1', str(uuid4()))
    session.setdefault('rel_gen2', str(uuid4()))
    session['auth_code1'] = str(uuid4())
    session['auth_code2'] = str(uuid4())

    sk = SigningKey.from_string(key.decode('hex'))
    signature = sk.sign_deterministic(hashlib.sha256(session['rel_gen1']+key).digest().encode('hex'))  # indexer reference baked into request's "return signature"
    friend_request1 = {
        'to': session['rel_gen1'],
        'rid': signature.encode('hex')
    }
    signature = sk.sign_deterministic(hashlib.sha256(session['rel_gen2']+key).digest().encode('hex'))  # indexer reference baked into request's "return signature"
    friend_request2 = {
        'to': session['rel_gen2'],
        'rid': signature.encode('hex')
    }

    with open('miner_friend_requests.json', 'r+') as f:
        existing = json.loads(f.read())
        existing.append(friend_request1)
        existing.append(friend_request2)
        friend_requests_dict = dict([(c['rid'], c) for c in existing])
        friend_requests = [c for e, c in friend_requests_dict.iteritems()]
        print friend_requests
        f.seek(0)
        f.write(json.dumps(friend_requests, indent=4))
        f.truncate()

    return render_template(
        'index.html',
        rel_gen1=session['rel_gen1'],
        auth_code1=session['auth_code1'],
        rel_gen2=session['rel_gen2'],
        auth_code2=session['auth_code2']
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html', rel_gen=request.args['rel_gen'], auth_code=request.args['auth_code'])

    sk = SigningKey.from_string(key.decode('hex'))
    print hashlib.sha256(request.form.get('to')+key).digest().encode('hex')

    login = {
        'to': request.form.get('to'),
        'auth_code': request.form.get('auth_code')
    }
    with open('miner_logins.json', 'r+') as f:
        existing = json.loads(f.read())
        existing.append(login)
        f.seek(0)
        f.write(json.dumps(existing, indent=4))
        f.truncate()

    return json.dumps(existing)

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


@app.route('/register', methods=['GET', 'POST'])
def register():
    # add it to friend request pool to be included in a block
    if request.method == 'GET':
        return render_template('register.html', rel_gen=request.args['rel_gen'])

    sk = SigningKey.from_string(key.decode('hex'))
    print hashlib.sha256(request.form.get('to')+key).digest().encode('hex')
    signature = sk.sign_deterministic(hashlib.sha256(request.form.get('to')+key).digest().encode('hex'))  # indexer reference baked into request's "return signature"
    friend_accept = {
        'to': request.form.get('to'),
        'rid': signature.encode('hex')
    }
    with open('miner_friend_accepts.json', 'r+') as f:
        existing = json.loads(f.read())
        existing.append(friend_accept)
        f.seek(0)
        f.write(json.dumps(existing, indent=4))
        f.truncate()

    return json.dumps(existing)


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
