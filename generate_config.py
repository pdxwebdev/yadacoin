import json
import os
from coincurve import PrivateKey, PublicKey

num = os.urandom(32).encode('hex')

pk = PrivateKey.from_hex(num)

config = {
    "coinbase": pk.public_key.format().encode('hex'),
    "block_reward": 1,
    "difficulty": "000",
    "private_key": pk.to_hex(),
    "public_key": pk.public_key.format().encode('hex'),
    "port": 8000,
    "host": "0.0.0.0",
    "callbackurl": "http://0.0.0.0:5000/create-relationship",
    "fcm_key": "",
    "database": "yadacoin",
    "site_database": "yadacoinsite"
}
print json.dumps(config, indent=4)