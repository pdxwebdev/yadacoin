import argparse
import hashlib
import json
import requests
import time
from uuid import uuid4
from ecdsa import SigningKey

def generate_block(blocks, coinbase, block_reward, transactions):
    block = {
        'index': len(blocks),
        'prevHash': blocks[len(blocks)-1]['hash'] if len(blocks) > 0 else '',
        'reward': {
            'to': coinbase,
            'value': block_reward
        },
        'nonce': str(uuid4()),
        'transactions': transactions
    }
    block['hash'] = hashlib.sha256(json.dumps(block)).digest().encode('hex')
    return block

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('runtype',
                    help='If you want to mine blocks')
    parser.add_argument('--conf',
                    help='set your config file')
    args = parser.parse_args()

    with open(args.conf) as f:
        config = json.loads(f.read())

    key = config.get('private_key')
    sk = SigningKey.from_string(key.decode('hex'))

    # default run state will be to mine some blocks!

    # proof of work time!
    ii = 0
    while 1:
        coinbase = config.get('coinbase')
        block_reward = config.get('block_reward')
        difficulty = config.get('difficulty')

        with open('blockchain.json') as f:
            blocks = json.loads(f.read()).get('blocks')

        with open('miner_transactions.json', 'r+') as f:
            transactions = json.loads(f.read())
            if transactions:
                f.seek(0)
                f.write('[]')
                f.truncate()

        if not transactions and len(blocks):
            print 'not genesis and no transactions. Idle time: %s\r' % ii
            ii += 1
            time.sleep(1)
            continue

        latest_block = blocks[len(blocks)-1] if len(blocks) > 1 else generate_block([], coinbase, block_reward, [])
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

                block = generate_block(blocks, coinbase, block_reward, transactions)

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
