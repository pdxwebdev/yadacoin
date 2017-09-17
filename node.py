import argparse
import hashlib
import json
import requests
import time
from uuid import uuid4
from ecdsa import SigningKey

with open('config.json') as f:
    config = json.loads(f.read())

key = config.get('private_key')
sk = SigningKey.from_string(key.decode('hex'))

def generate_block(blocks, coinbase, block_reward, friend_requests, friend_accepts):
    block = {
        'index': len(blocks),
        'prevHash': blocks[len(blocks)-1]['hash'] if len(blocks) > 0 else '',
        'reward': {
            'to': coinbase,
            'value': block_reward
        },
        'nonce': str(uuid4()),
        'friend_requests': friend_requests,
        'friend_accepts': friend_accepts
    }
    block['hash'] = hashlib.sha256(json.dumps(block)).digest().encode('hex')
    return block

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('runtype',
                    help='If you want to mine blocks')
    args = parser.parse_args()
    if args.runtype == 'node':
        block_height = 0
        while 1:
            # first thing we'll do is search for friend requests
            with open('blockchain.json', 'r') as f:
                blocks = json.loads(f.read())['blocks']

            for i, block in enumerate(blocks):
                if block_height >= i:
                    continue
                block_height = i
                for friend_request in block.get('friend_requests'):
                    sig = sk.sign_deterministic(hashlib.sha256(friend_request['to']+key).digest().encode('hex'))
                    if friend_request['rid'] == sig.encode('hex'):
                        print 'FOUND'
                        with open('friend_requests.json', 'a+') as f:
                            try:
                                existing = json.loads(f.read())
                            except:
                                existing = []
                            existing.append(friend_request)
                            f.seek(0)
                            f.truncate()
                            friend_requests_dict = dict([(c['rid'], c) for c in existing])
                            friend_requests = [c for e, c in friend_requests.iteritems()]
                            f.write(json.dumps(friend_requests, indent=4))
                            f.truncate()
                    else:
                        friend_requests = {}
                        print 'NOT FOUND'
                        print friend_request['rid']
                        print friend_request['to']
                        print sk.sign(friend_request['to']).encode('hex')
                        print sk.get_verifying_key().to_string().encode('hex')

                with open('friend_requests.json', 'r') as f:                    
                    try:
                        friend_requests = json.loads(f.read())
                    except:
                        friend_requests = []

                for friend_accept in block.get('friend_accepts'):
                    for friend_request in friend_requests:
                        sig = sk.sign_deterministic(hashlib.sha256(friend_request['to']+key).digest().encode('hex'))
                        if friend_accept['rid'] == sig.encode('hex'):
                            print 'FOUND'
                            with open('friend_accepts.json', 'a+') as f:
                                try:
                                    existing = json.loads(f.read())
                                except:
                                    existing = []
                                existing.append(friend_request)
                                f.seek(0)
                                f.truncate()
                                friend_requests = dict([(c['rid'], c) for c in existing])
                                f.write(json.dumps([c for e, c in friend_requests.iteritems()], indent=4))
                                f.truncate()
                        else:
                            print 'NOT FOUND'
                            print friend_request['rid']
                            print friend_request['to']
                            print sk.sign(friend_request['to']).encode('hex')
                            print sk.get_verifying_key().to_string().encode('hex')

            time.sleep(1)
    elif args.runtype == 'mine':

        # default run state will be to mine some blocks!

        # proof of work time!
        ii = 0
        while 1:
            coinbase = config.get('coinbase')
            block_reward = config.get('block_reward')
            difficulty = config.get('difficulty')

            with open('blockchain.json') as f:
                blocks = json.loads(f.read()).get('blocks')

            with open('miner_friend_requests.json', 'r+') as f:
                friend_requests = json.loads(f.read())
                if friend_requests:
                    f.seek(0)
                    f.write('[]')
                    f.truncate()

            # gather friend acceptances from the network
            with open('miner_friend_accepts.json', 'r+') as f:
                friend_accepts = json.loads(f.read())
                if friend_accepts:
                    f.seek(0)
                    f.write('[]')
                    f.truncate()

            if not friend_requests and not friend_accepts and len(blocks):
                print 'not genesis and no transactions. Idle time: %s\r' % ii
                ii += 1
                time.sleep(1)
                continue

            latest_block = blocks[len(blocks)-1] if len(blocks) > 1 else generate_block([], coinbase, block_reward, [], [])
            nonce = latest_block.get('nonce')
            i = 0
            while 1:
                hash_test = hashlib.sha256("%s%s" % (nonce, i)).digest().encode('hex')
                print hash_test
                if hash_test.endswith(difficulty):
                    print 'got a block!'
                    print 'verify answer, nonce: ', nonce, 'interation: ', i, 'hash: ', hashlib.sha256("%s%s" % (nonce, i)).hexdigest()
                    # create the block with the reward
                    # gather friend requests from the network

                    block = generate_block(blocks, coinbase, block_reward, friend_requests, friend_accepts)

                    with open('blockchain.json', 'r+') as f:
                        blocks = json.loads(f.read()).get('blocks')
                        blocks.append(block)
                        f.seek(0)
                        f.write(json.dumps({'blocks': blocks}, indent=4))
                        f.truncate()

                    # now communicate that out to the network
                    with open('peers.json') as f:
                        peers = json.loads(f.read()).get('peers')
                    for ip in [x.get('ip') for x in peers]:
                        res = requests.post(
                            'http://%s/post-block' % ip,
                            json.dumps(block),
                            headers={'Content-type': 'application/json'}
                        )
                        print res.content
                    break
                i += 1
            ii = 0
            time.sleep(1)
