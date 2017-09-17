import argparse
import hashlib
import json
import requests
import time
from uuid import uuid4


def generateBlock(blocks, coinbase, block_reward, friend_requests, friend_accepts):
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
        # first thing we'll do is search for friend requests
        with open('blockchain.json', 'r') as f:
            blocks = json.loads(f.read())['blocks']

        for block in blocks:

    elif args.runtype == 'mine':

        # default run state will be to mine some blocks!

        # proof of work time!
        while 1:
            with open('config.json') as f:
                config = json.loads(f.read())
            coinbase = config.get('coinbase')
            block_reward = config.get('coinbase')
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
                print 'not genesis and no transactions'
                time.sleep(1)
                continue
            latest_block = blocks[len(blocks)-1] if len(blocks) > 1 else generateBlock([], coinbase, block_reward, [], [])
            nonce = latest_block.get('nonce')
            x = 0
            while 1:
                hash_test = hashlib.sha256("%s%s" % (nonce, x)).digest().encode('hex')
                print hash_test
                if hash_test.endswith(difficulty):
                    print 'got a block!'
                    print 'verify answer, nonce: ', nonce, 'interation: ', x, 'hash: ', hashlib.sha256("%s%s" % (nonce, x)).hexdigest()
                    # create the block with the reward
                    # gather friend requests from the network

                    block = generateBlock(blocks, coinbase, block_reward, friend_requests, friend_accepts)

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
                x += 1
            print 'block not found in ', x, ' iterations'

            time.sleep(1)
