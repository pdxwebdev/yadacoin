import json

from flask import Flask, request
from ecdsa import SigningKey, VerifyingKey

key = '841984251447c81c6374d17102abb9104278cb9cc9886934'
sk = SigningKey.from_string(key.decode('hex'))
#vk2 = VerifyingKey.from_string(pk.decode('hex'))
#print vk2.verify(signature, "message")

app = Flask(__name__)

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

@app.route('/friend-request', methods=['POST'])
def friend_request():
    # add it to friend request pool to be included in a block
    signature = sk.sign(request.form.get('to'))
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

@app.route('/friend-request-search', methods=['POST'])
def friend_request_search():
    # add it to friend request pool to be included in a block

    with open('friend_requests.json', 'r') as f:
        friend_requests = json.loads(f.read())['friend_requests']

    return json.dumps(friend_requests)

app.debug = True
app.run()
