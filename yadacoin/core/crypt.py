"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64
import hashlib

from Crypto.Cipher import AES
from pbkdf2 import PBKDF2


class Crypt(object):  # Relationship Utilities
    def __init__(self, shared_secret, shared=False):
        self.key = PBKDF2(
            hashlib.sha256(shared_secret.encode("utf-8")).hexdigest(), "salt", 400
        ).read(32)

    def encrypt_consistent(self, s):
        BS = AES.block_size
        s = s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
        iv = bytes.fromhex("3443cd461efa7d334e477600f25c8bb9")
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return (iv + cipher.encrypt(bytes.fromhex(s))).hex()

    def encrypt(self, s):
        from Crypto import Random

        BS = AES.block_size
        iv = Random.new().read(BS)
        s = s + (BS - len(s) % BS) * chr(BS - len(s) % BS).encode()
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return (iv + cipher.encrypt(s)).hex()

    def shared_encrypt(self, s):
        s = base64.b64encode(s)
        from Crypto import Random

        BS = AES.block_size
        iv = Random.new().read(BS)
        s = s + (BS - len(s) % BS) * chr(BS - len(s) % BS).encode()
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return (iv + cipher.encrypt(s)).hex()

    def decrypt(self, enc):
        enc = bytes.fromhex(enc)
        iv = enc[:16]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        s = cipher.decrypt(enc[16:])
        return s[0 : -ord(s.decode("latin1")[-1])]

    def shared_decrypt(self, enc):
        enc = bytes.fromhex(enc)
        iv = enc[:16]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        s = cipher.decrypt(enc[16:])
        return base64.b64decode(s[0 : -ord(s.decode("latin1")[-1])])


class RIPEMD160:
    # Message schedule indexes for the left path.
    ML = [
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        7,
        4,
        13,
        1,
        10,
        6,
        15,
        3,
        12,
        0,
        9,
        5,
        2,
        14,
        11,
        8,
        3,
        10,
        14,
        4,
        9,
        15,
        8,
        1,
        2,
        7,
        0,
        6,
        13,
        11,
        5,
        12,
        1,
        9,
        11,
        10,
        0,
        8,
        12,
        4,
        13,
        3,
        7,
        15,
        14,
        5,
        6,
        2,
        4,
        0,
        5,
        9,
        7,
        12,
        2,
        10,
        14,
        1,
        3,
        8,
        11,
        6,
        15,
        13,
    ]

    # Message schedule indexes for the right path.
    MR = [
        5,
        14,
        7,
        0,
        9,
        2,
        11,
        4,
        13,
        6,
        15,
        8,
        1,
        10,
        3,
        12,
        6,
        11,
        3,
        7,
        0,
        13,
        5,
        10,
        14,
        15,
        8,
        12,
        4,
        9,
        1,
        2,
        15,
        5,
        1,
        3,
        7,
        14,
        6,
        9,
        11,
        8,
        12,
        2,
        10,
        0,
        4,
        13,
        8,
        6,
        4,
        1,
        3,
        11,
        15,
        0,
        5,
        12,
        2,
        13,
        9,
        7,
        10,
        14,
        12,
        15,
        10,
        4,
        1,
        5,
        8,
        7,
        6,
        2,
        13,
        14,
        0,
        3,
        9,
        11,
    ]

    # Rotation counts for the left path.
    RL = [
        11,
        14,
        15,
        12,
        5,
        8,
        7,
        9,
        11,
        13,
        14,
        15,
        6,
        7,
        9,
        8,
        7,
        6,
        8,
        13,
        11,
        9,
        7,
        15,
        7,
        12,
        15,
        9,
        11,
        7,
        13,
        12,
        11,
        13,
        6,
        7,
        14,
        9,
        13,
        15,
        14,
        8,
        13,
        6,
        5,
        12,
        7,
        5,
        11,
        12,
        14,
        15,
        14,
        15,
        9,
        8,
        9,
        14,
        5,
        6,
        8,
        6,
        5,
        12,
        9,
        15,
        5,
        11,
        6,
        8,
        13,
        12,
        5,
        12,
        13,
        14,
        11,
        8,
        5,
        6,
    ]

    # Rotation counts for the right path.
    RR = [
        8,
        9,
        9,
        11,
        13,
        15,
        15,
        5,
        7,
        7,
        8,
        11,
        14,
        14,
        12,
        6,
        9,
        13,
        15,
        7,
        12,
        8,
        9,
        11,
        7,
        7,
        12,
        7,
        6,
        15,
        13,
        11,
        9,
        7,
        15,
        11,
        8,
        6,
        6,
        14,
        12,
        13,
        5,
        14,
        13,
        13,
        7,
        5,
        15,
        5,
        8,
        11,
        14,
        14,
        6,
        14,
        6,
        9,
        12,
        9,
        12,
        5,
        15,
        8,
        8,
        5,
        12,
        9,
        12,
        5,
        14,
        6,
        8,
        13,
        6,
        5,
        15,
        13,
        11,
        11,
    ]

    # K constants for the left path.
    KL = [0, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E]

    # K constants for the right path.
    KR = [0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0]

    def fi(x, y, z, i):
        """The f1, f2, f3, f4, and f5 functions from the specification."""
        if i == 0:
            return x ^ y ^ z
        elif i == 1:
            return (x & y) | (~x & z)
        elif i == 2:
            return (x | ~y) ^ z
        elif i == 3:
            return (x & z) | (y & ~z)
        elif i == 4:
            return x ^ (y | ~z)
        else:
            assert False

    def rol(x, i):
        """Rotate the bottom 32 bits of x left by i bits."""
        return ((x << i) | ((x & 0xFFFFFFFF) >> (32 - i))) & 0xFFFFFFFF

    def compress(h0, h1, h2, h3, h4, block):
        """Compress state (h0, h1, h2, h3, h4) with block."""
        # Left path variables.
        al, bl, cl, dl, el = h0, h1, h2, h3, h4
        # Right path variables.
        ar, br, cr, dr, er = h0, h1, h2, h3, h4
        # Message variables.
        x = [int.from_bytes(block[4 * i : 4 * (i + 1)], "little") for i in range(16)]

        # Iterate over the 80 rounds of the compression.
        for j in range(80):
            rnd = j >> 4
            # Perform left side of the transformation.
            al = (
                RIPEMD160.rol(
                    al
                    + RIPEMD160.fi(bl, cl, dl, rnd)
                    + x[RIPEMD160.ML[j]]
                    + RIPEMD160.KL[rnd],
                    RIPEMD160.RL[j],
                )
                + el
            )
            al, bl, cl, dl, el = el, al, bl, RIPEMD160.rol(cl, 10), dl
            # Perform right side of the transformation.
            ar = (
                RIPEMD160.rol(
                    ar
                    + RIPEMD160.fi(br, cr, dr, 4 - rnd)
                    + x[RIPEMD160.MR[j]]
                    + RIPEMD160.KR[rnd],
                    RIPEMD160.RR[j],
                )
                + er
            )
            ar, br, cr, dr, er = er, ar, br, RIPEMD160.rol(cr, 10), dr

        # Compose old state, left transform, and right transform into new state.
        return h1 + cl + dr, h2 + dl + er, h3 + el + ar, h4 + al + br, h0 + bl + cr

    def ripemd160(data):
        data = hashlib.sha256(data).digest()
        """Compute the RIPEMD-160 hash of data."""
        # Initialize state.
        state = (0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0)
        # Process full 64-byte blocks in the input.
        for b in range(len(data) >> 6):
            state = RIPEMD160.compress(*state, data[64 * b : 64 * (b + 1)])
        # Construct final blocks (with padding and size).
        pad = b"\x80" + b"\x00" * ((119 - len(data)) & 63)
        fin = data[len(data) & ~63 :] + pad + (8 * len(data)).to_bytes(8, "little")
        # Process final blocks.
        for b in range(len(fin) >> 6):
            state = RIPEMD160.compress(*state, fin[64 * b : 64 * (b + 1)])
        # Produce output.
        return b"".join((h & 0xFFFFFFFF).to_bytes(4, "little") for h in state)
