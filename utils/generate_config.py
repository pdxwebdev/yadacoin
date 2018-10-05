import json
import os
import hashlib
import binascii
import base58
import subprocess
import requests
import sys
import argparse
import getpass
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + '/..')
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey, PublicKey
from urllib2 import urlopen
from yadacoin import Config


class Wif:

    DEFAULT = 'Prompt if not specified'

    def __init__(self, value):
        if value == self.DEFAULT:
            value = getpass.getpass('WIF/Secret key [Enter to auto-generate]: ')
        self.value = value

    def __str__(self):
        return self.value

def from_wif(wif):
    return binascii.hexlify(base58.b58decode(wif))[2:-10]

def to_wif(private_key_static):
    extended_key = "80"+private_key_static+"01"
    first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key)).hexdigest()
    second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
    final_key = extended_key+second_sha256[:8]
    wif = base58.b58encode(binascii.unhexlify(final_key))
    return wif

def generate():
    config = {
        "private_key": pk.to_hex(),
        "wif": to_wif(pk.to_hex()),
        "public_key": pk.public_key.format().encode('hex'),
        "address": str(P2PKHBitcoinAddress.from_pubkey(pk.public_key.format())),
        "serve_host": "0.0.0.0",
        "serve_port": 8000,
        "peer_host": public_ip,
        "peer_port": 8000,
        "web_server_host": "0.0.0.0",
        "web_server_port": 5000,
        "peer": "http://localhost:8000",
        "callbackurl": "http://0.0.0.0:5000/create-relationship",
        "fcm_key": "",
        "database": "yadacoin",
        "site_database": "yadacoinsite",
        "mongodb_host": "localhost",
        "mixpanel": "",
        "username": Config.username
    }
    Config.from_dict(config)
    return json.dumps(Config.to_dict(), indent=4)

parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

subparsers = parser.add_subparsers()
new_parser = subparsers.add_parser('new')
new_parser.set_defaults(which='new')
new_parser.add_argument('username', help='Specify username')
new_parser.add_argument('-p', '--password', type=Wif, help='Specify wif/Secret key [Enter to auto-generate]',
    default=Wif.DEFAULT)

update_parser = subparsers.add_parser('update')
update_parser.set_defaults(which='update')
update_parser.add_argument('config', help='config file')
update_parser.add_argument('username', help='Specify username')

auto_parser = subparsers.add_parser('auto')
auto_parser.set_defaults(which='auto')

args = parser.parse_args()

public_ip = requests.get('https://api.ipify.org').text
if args.which == 'new': 
    if args.password.value:
        num = from_wif(args.password.value)
    else:
        num = os.urandom(32).encode('hex')
    Config.username = args.username
    pk = PrivateKey.from_hex(num)
    print generate()
elif args.which == 'update':
    with open(args.config) as f:
        identity = json.loads(f.read())
        pk = PrivateKey.from_hex(identity['private_key'])
        if 'username' in identity:
            username = identity['username']
        else:
            username = args.username
        Config.username = username
        print generate()
elif args.which == 'auto':
    num = os.urandom(32).encode('hex')
    pk = PrivateKey.from_hex(num)
    Config.username = ''
    print generate()




