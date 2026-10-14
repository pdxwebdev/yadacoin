import base64
import hashlib
import os

from coincurve import PrivateKey
from Crypto.Cipher import AES

DOMAIN = b"yada-pw-box-v1"


def _key(x: bytes) -> bytes:
    return hashlib.sha256(x + DOMAIN).digest()


def seal(plaintext: bytes, recipient_pub_hex: str) -> str:
    eph = PrivateKey()
    shared = eph.ecdh(bytes.fromhex(recipient_pub_hex))
    nonce = os.urandom(12)
    cipher = AES.new(_key(shared), AES.MODE_GCM, nonce=nonce)
    ct, tag = cipher.encrypt_and_digest(plaintext)
    blob = eph.public_key.format(compressed=True) + nonce + ct + tag
    return base64.b64encode(blob).decode("ascii")


def open_box(token: str, recipient_priv_hex: str) -> bytes:
    raw = base64.b64decode(token)
    if len(raw) < 33 + 12 + 16:
        raise ValueError("truncated box")
    eph_pub, nonce, rest = raw[:33], raw[33:45], raw[45:]
    ct, tag = rest[:-16], rest[-16:]
    shared = PrivateKey(bytes.fromhex(recipient_priv_hex)).ecdh(eph_pub)
    return AES.new(_key(shared), AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag)
