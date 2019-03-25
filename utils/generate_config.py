import json
import os
import hashlib
import binascii
import base58
# import subprocess
import requests
import argparse
import getpass
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + '/..')
# from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey, PublicKey
# from urllib2 import urlopen
from yadacoin.config import Config


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
auto_parser.add_argument('-f', '--force', help='Forcefully create file, possibly overwriting existing, use with caution!')
auto_parser.add_argument('-c', '--create', help='Create a new config file if one does not already exist')
auto_parser.add_argument('-m', '--mongo-host', help='Specify a mongodb host')

args = parser.parse_args()

"""
TODO: add other apis in case this one is down. Allow to override from optional command line param
"""
public_ip = requests.get('https://api.ipify.org').text

if args.which == 'new': 
    if args.password.value:
        num = from_wif(args.password.value)
    else:
        num = os.urandom(32).hex()
    pk = PrivateKey.from_hex(num)
    config = Config.generate(pk.to_hex())
    config.username = args.username
elif args.which == 'update':
    with open(args.config) as f:
        identity = json.loads(f.read())
        config = Config.generate(xprv=identity['xprv'])
        if 'username' in identity and identity['username']:
            username = identity['username']
        else:
            username = args.username
        config.username = username
        config.bulletin_secret = config.get_bulletin_secret()
        print(config.to_json())
elif args.which == 'auto':
    config = Config.generate()
    config.username = ''
    filename = 'config.json'
    kwargs = {}
    out = Config.generate().to_json()
    if args.force:
        with open(args.force, 'w') as f:
            f.write(out)
    elif args.create:
        if not os.path.isfile(args.create):
            with open(args.create, 'w') as f:
                f.write(out)
    else:
        print(out)




