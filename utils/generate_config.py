import json
import os
import hashlib
import binascii
import base58
import subprocess
import requests
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey, PublicKey
from urllib2 import urlopen


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
        "username": ""
    }
    return json.dumps(config, indent=4)

num = os.urandom(32).encode('hex')

pk = PrivateKey.from_hex(num)

public_ip = requests.get('https://api.ipify.org').text

print generate()