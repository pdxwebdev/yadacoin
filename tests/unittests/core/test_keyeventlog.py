"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import json
import unittest
from unittest import mock
from unittest.mock import AsyncMock

from mongomock import MongoClient

import yadacoin.core.config
from yadacoin.core.block import Block
from yadacoin.core.config import Config
from yadacoin.core.keyeventlog import (
    KELExceptionMissingConfirmingKeyEvent,
    KELExceptionMissingUnconfirmedKeyEvent,
    KeyEventLog,
    KeyEventPrerotatedKeyHashException,
    KeyEventSingleOutputException,
)
from yadacoin.core.transaction import Output

from ..test_setup import AsyncTestCase

{
    "version": 5,
    "time": 1739245507,
    "index": 537164,
    "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
    "prevHash": "0e3b8b4affbd58b8dd1932add160acac4ad925683ff4078db96c3d678f260000",
    "nonce": "ed890100601419",
    "transactions": [
        {
            "time": 1739245499,
            "rid": "",
            "id": "MEUCIQC1ejPvQX/0TeyV3QfWIz9HaVp6/Ee2ImenG+370b0pbgIgGsXdy2UuThWiHsLeqxL9SgjU+p3WdGPozsb0LnvFZGw=",
            "relationship": "",
            "relationship_hash": "149936a03d3c6259f99afd5c0d25cad34b36d65a484bed94452c6b50c141d9a2",
            "public_key": "028a1a023442dd08132970178e91b7e86f78368b6d511d878b3639d63fcb92264c",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "d1eeba6e56456bbc13f03b1b3f24d1e742e234d42ee161e8c64fbaeba700d272",
            "inputs": [],
            "outputs": [{"to": "1KVR1SGHtDhrPpQYqucX7PHmU5Pc9tbpjd", "value": 0}],
            "version": 7,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "1KVR1SGHtDhrPpQYqucX7PHmU5Pc9tbpjd",
            "twice_prerotated_key_hash": "18LSCvRGyCPpPbWNQiFKXssDit41Q7AR4S",
            "public_key_hash": "1PywxM9zLAT7mfgkMbk98ngtnWnkh2PHXS",
            "prev_public_key_hash": "1K3hy2pQSNMYZHmiN7pM75cuRcS5bFLjJG",
        },
        {
            "time": 1739245507,
            "rid": "",
            "id": "MEUCIQDAFxYfXMLCwXLWgdzNXIfGtc0+DXQJYMC8M0HdYTkGwAIgch6l/0fq4jXBHh+mMLR9fv+MTOqR0H+E+Wp/J10raTw=",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "fe659c2a028d609677e18986df6da0dcebace972b5bf48336a38ed292d6e79c3",
            "inputs": [],
            "outputs": [{"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 11.25}],
            "version": 6,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "",
            "twice_prerotated_key_hash": "",
            "public_key_hash": "",
            "prev_public_key_hash": "",
        },
    ],
    "hash": "2d3a8e73bb801fa98a031bdb2647cd62af88c18572242d17ec82994ded310100",
    "merkleRoot": "d866b8a9e7ccf37d8bac9275104fef84c3abc1a2db5b0ffdfdb3d56fd027a395",
    "special_min": False,
    "target": "0000000000000000000000000000000000000000000000000000000000000001",
    "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
    "header": "517392455070255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a75371640e3b8b4affbd58b8dd1932add160acac4ad925683ff4078db96c3d678f260000{nonce}0000000000000000000000000000000000000000000000000000000000000001d866b8a9e7ccf37d8bac9275104fef84c3abc1a2db5b0ffdfdb3d56fd027a395",
    "id": "MEUCIQCO3sFTSJ7iELz3exXBu/UUw9PUQ0Nb32pFoN0v7Fi5DgIgd52/L6993XmfueNia9VCRDkr6922e2mpEI0H6HTDt3I=",
    "updated_at": 1739245518.1528718,
}
{
    "version": 5,
    "time": 1739245389,
    "index": 537160,
    "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
    "prevHash": "34562868e7c6ca6ab82f396b335b117abd6f92ffadf9b3c1c6693538fffd0200",
    "nonce": "65070100729458",
    "transactions": [
        {
            "time": 1739245383,
            "rid": "",
            "id": "MEUCIQDAWWXlQOlOrl9c2t1fRfdA0basi7QIEL5YRaAffvVZFAIgPzxkAmWiSvT/gCGScPJgtZhI367DiFkCOFmQcSHadZA=",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "02be33900bb4457c48b68338f919453a82b39c58a4d0ad7e57ca0e4e4b3dfeda33",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "c4eccb3c4fb89a3178f815dd8cad3495a66a1334f3cf6e7d8d5b11959cf6a355",
            "inputs": [],
            "outputs": [{"to": "1C89V5gXKaUS3WbHvpWkMTgMQ2xiHb92Un", "value": 0}],
            "version": 7,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "1C89V5gXKaUS3WbHvpWkMTgMQ2xiHb92Un",
            "twice_prerotated_key_hash": "122kJMfNjcTG9UynyUNQDyAm65qCPpx3ZW",
            "public_key_hash": "1885jxPWqe7TtLSnxHvgmvZuCZFajWRNFt",
            "prev_public_key_hash": "",
        },
        {
            "time": 1739245383,
            "rid": "",
            "id": "MEUCIQC8Lg/LFfK65627yEyq8WWcjCIv0afWJ/qk2wKgf+rgGQIgUQWWaJYHVA4hcMi/opb6YUnc4GLcdUGFurVu4GPUHC0=",
            "relationship": "ef854b6fb514194f3deaae76e8e70ccb0408e604720ea57ba6a4ad6fc1329a8653da378b79fe30d39b9363ed81ffaf7f86e13695884e615c70d8eb2df0bbde2634337157ce1d2dd1f7cda8cac18b0a1958f986f56d141a3c3aaaac154da7d26c88c63e4d6cecb6b0bef44acf94b7d5e7b191e968c5f0ca011d5084a03eb7cf0ffc163fec735a228fdff7f4d295e7e709b255c913029fe1c3bbd563668bc1ea84912b3a48b6ebb1526e53ddb1c4c1a65ef60783393eb81ead0fa1d3dcd1a3b0ebc1a7c3ed991a3e3b1a6c3a0c43ca990a8e9ffcbe63a63f1a1d3cff0a76fb65e5b9ac60141c1b4c95281d9203a7dd08b72a",
            "relationship_hash": "fe625cfd2650f09445dc8ffc5abc170853c31849dfa99cfde28c31bce88ed8f2",
            "public_key": "025192f43f3187191b7d6de189b7ff8fa7245f3e742c72b744c3f7a5a4e2693823",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "0091166e81892d0b91086cd08e9333f498bd9cb19a7ef178ec56dab93a0fb967",
            "inputs": [],
            "outputs": [{"to": "13KTyKrhyxC7tzojUni7hxj4JfMWXXyb3y", "value": 0}],
            "version": 7,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "1K3hy2pQSNMYZHmiN7pM75cuRcS5bFLjJG",
            "twice_prerotated_key_hash": "1PywxM9zLAT7mfgkMbk98ngtnWnkh2PHXS",
            "public_key_hash": "1Bj6FLvUzPVYsUbZrr9Cd5Csdo7TaHud9d",
            "prev_public_key_hash": "12JfRsP5ouBGyH31wraUjVq3LZ3pB5QWtG",
        },
        {
            "time": 1739245383,
            "rid": "",
            "id": "MEUCIQD4MJaJxBJzk/t7vT69hE/jzpY2fmytIh/BHDFSJr3UIAIgNthRtwugEriswtWwdXr6Fu2jNWeHy/AvXHCND+1NPwk=",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "02adf40149395b6bebd8ba643c58ebabacb111821d0eeb1da90323bd2dfc2c1b67",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "d3ad4a321c3ec4919a9784a6cbfb1e10cc72c07104f872c4f558005ce439d5dc",
            "inputs": [],
            "outputs": [{"to": "1PywxM9zLAT7mfgkMbk98ngtnWnkh2PHXS", "value": 0}],
            "version": 7,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "1PywxM9zLAT7mfgkMbk98ngtnWnkh2PHXS",
            "twice_prerotated_key_hash": "1KVR1SGHtDhrPpQYqucX7PHmU5Pc9tbpjd",
            "public_key_hash": "1K3hy2pQSNMYZHmiN7pM75cuRcS5bFLjJG",
            "prev_public_key_hash": "1Bj6FLvUzPVYsUbZrr9Cd5Csdo7TaHud9d",
        },
        {
            "time": 1739245389,
            "rid": "",
            "id": "MEQCIGDSxLcFhc3T18YzosfrYLhW36FFDvqN4p5qOXHwI7AiAiAQm7fiNTH+nFQeczXkQG58+6G2bSe89kNqQXgehgZXkA==",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "bedb07270d2e84489f9542b3aea288570a4a65c4b4b2edf6952dc5a295f41f8c",
            "inputs": [],
            "outputs": [{"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 11.25}],
            "version": 6,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "",
            "twice_prerotated_key_hash": "",
            "public_key_hash": "",
            "prev_public_key_hash": "",
        },
    ],
    "hash": "5a6544a619fe0c8399d65eeda31b78adf058b1fe6073abb18c25ff7456640000",
    "merkleRoot": "c5a68fe501b1a8b54f9e957f7e9fe83d0f33301db5c0ad3514b1ce7c5f8d2947",
    "special_min": False,
    "target": "0000000000000000000000000000000000000000000000000000000000000001",
    "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
    "header": "517392453890255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a753716034562868e7c6ca6ab82f396b335b117abd6f92ffadf9b3c1c6693538fffd0200{nonce}0000000000000000000000000000000000000000000000000000000000000001c5a68fe501b1a8b54f9e957f7e9fe83d0f33301db5c0ad3514b1ce7c5f8d2947",
    "id": "MEQCIEeFJgNrP8nbD5PhhXRYdpPAfvQbJ/2oXwttybqzBJSFAiBipYNjZZHfwGKzOwiAF897jHG8haGkEvkq8wkHG54KSw==",
    "updated_at": 1739245398.3425741,
}
{
    "version": 5,
    "time": 1739245326,
    "index": 537154,
    "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
    "prevHash": "ee085163be21b211cd8879320300f8bf2736dff84b84b8755a0d046012f30200",
    "nonce": "be990000988747",
    "transactions": [
        {
            "time": 1739245310,
            "rid": "",
            "id": "MEUCIQDcMnYPCcYN99GR74qAWRZgD8fORrDjsZJ8coO5a8qLSgIgeIkjvLCMBdKuKXRmI3YuDwwI5V3uZlaHTtyh3e8Nn5k=",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "031ba7057c4a32776779978a4c812ee23ea06f8676e3e823ca316edec267cfaa88",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "79bdc6104a640d4dc1dd157bd0016290721f55bc37578bfbdc4295081baa947d",
            "inputs": [],
            "outputs": [{"to": "1HEbamGfrPdBePYS7XKNMPQQKeZEJGTcBU", "value": 0}],
            "version": 7,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "1HEbamGfrPdBePYS7XKNMPQQKeZEJGTcBU",
            "twice_prerotated_key_hash": "1H1B1VDDtqkpymvb66shx78yqpdcA66zN9",
            "public_key_hash": "1GkkZdfgWKkrVFJJFF458VVGW6EK8vQ6Qg",
            "prev_public_key_hash": "",
        },
        {
            "time": 1739245310,
            "rid": "",
            "id": "MEQCIEMb1oe+9g20S8tRrbiz91mGS9dtevt+e/fEMvIqtkwSAiA5KZem+kslb8CNSmKgmlEGKVC7tulcGEN7OqJMyXBuvQ==",
            "relationship": "b61c4f29128b8eb59bd22d14b929f6b4043937ed79d4a6e69e2623a96730ec1911511974c80d8b1efa323ccdc41657e71f7021bfa3114b2fdc039e04484116f1b8e3d43fa6e494af3c9b85b53060e96c85a8aecac2429aa2446c8803f9147d1e2186d7058a93878a25f18a890540e982a14224bcd2178c00c3fb89cf25c39973ad3d0256dcfcad7276412bc12285b1d814a35064081949d309102b3f1af437f2bd73932630e27b45d6870e0b56b23b53373cb4340035cf3ec22dc830fe9d950645e7efbc5e7366bee15996edc2225f2a1e647c181c9e6960a505edac16214b26ef33831cb01dfff1e4fff9031fbd609fcf0c4a9689f69750991516f8a0e89a02dbd06fd4d58a802b1f3ebf66852722cc13a2559ce3a7b1e53186adb93215b7d645f0fe5c7b1da53638d425810a924c129733247c4b0b037fbaff7effa62f3d574180cd4c8a89b242eca4189fc2348576f20e373930299286587bb66ab3ebc943f43f21ed4509d671eb09e431c3638e6ee8",
            "relationship_hash": "ce14559d1f4ff3ae9ebe3a84e46b9c7c668f568d958618c62fd02d6515b14b3d",
            "public_key": "031690f3b1f13dd516ec35d37d0d2c7da8a94188aca7d2353fbf653b90b9a0d184",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "7714cd2db1da97fb6b98c661d1f59ab818354ded4e407c9799a7f60c5524c106",
            "inputs": [],
            "outputs": [{"to": "1Bj6FLvUzPVYsUbZrr9Cd5Csdo7TaHud9d", "value": 0}],
            "version": 7,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "1DJS5Bp6F3rRuRwSYaxp1jDn9eVvGgVguU",
            "twice_prerotated_key_hash": "13KTyKrhyxC7tzojUni7hxj4JfMWXXyb3y",
            "public_key_hash": "1N3b5hw4jKoRqL9kDCfGBr8vscDFrxHWw1",
            "prev_public_key_hash": "1JqJDwjWZoSS7NpsGh9UTgt9dZKzQDe76K",
        },
        {
            "time": 1739245310,
            "rid": "",
            "id": "MEUCIQCGotlXEgOY5iU1RenMQ+7YN+4004X1cXaCB3bXkbGdAAIgHq0l9H2vpCiIlUIuWdSRIxDSkcqIvjBE2rks2lfSIy0=",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "03e7ec993817e6b53e5f32742a155f199e4911d8ecbc026d53f1d03d5587213414",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "7928ae590b8c600d218523437aaca27dd2876e9c90159bbe7c1f71d569718643",
            "inputs": [],
            "outputs": [{"to": "13KTyKrhyxC7tzojUni7hxj4JfMWXXyb3y", "value": 0}],
            "version": 7,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "13KTyKrhyxC7tzojUni7hxj4JfMWXXyb3y",
            "twice_prerotated_key_hash": "1Hy2F69iufxgwWyFpmozfw1psepjn8dygc",
            "public_key_hash": "1DJS5Bp6F3rRuRwSYaxp1jDn9eVvGgVguU",
            "prev_public_key_hash": "1N3b5hw4jKoRqL9kDCfGBr8vscDFrxHWw1",
        },
        {
            "time": 1739245326,
            "rid": "",
            "id": "MEQCIHBQ3+D1a1R3KXWZ6d14l50q2/xRYMXpV53Oeqi8iEC6AiABcAGBYR5o2XROVuSbYIEacD7wtPtRZdvEInY3Fub+nA==",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "0a0a57246fc4bb0789c0c0fc8ff5b1e3f647c32eb23ae4a5f0a8d05ea519ab88",
            "inputs": [],
            "outputs": [{"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 11.25}],
            "version": 6,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "",
            "twice_prerotated_key_hash": "",
            "public_key_hash": "",
            "prev_public_key_hash": "",
        },
    ],
    "hash": "efdb79985269404b507f18db4b6fdf24606c6cba99c25a27917b5f3266850000",
    "merkleRoot": "777fda3d3a99747d5c95dc73daf3e862a9c5879a2ee4ad7c35547c8c5740dd48",
    "special_min": False,
    "target": "0000000000000000000000000000000000000000000000000000000000000001",
    "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
    "header": "517392453260255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7537154ee085163be21b211cd8879320300f8bf2736dff84b84b8755a0d046012f30200{nonce}0000000000000000000000000000000000000000000000000000000000000001777fda3d3a99747d5c95dc73daf3e862a9c5879a2ee4ad7c35547c8c5740dd48",
    "id": "MEUCIQD3RYLttD+ZMjP/c0fvYsRtz/JonBbXNni8eL0O2DchnQIgT+Ar9wgKnGxjBCFQKDuUGw8pCuJJEr/lb0QElaRNJEA=",
    "updated_at": 1739245326.6624742,
}
{
    "version": 5,
    "time": 1739245292,
    "index": 537151,
    "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
    "prevHash": "f241f1e6348a6c89d681518666cc050407597429bb6d1d7652dfd5e4b7ec0100",
    "nonce": "c3830100676324",
    "transactions": [
        {
            "time": 1739245289,
            "rid": "",
            "id": "MEUCIQC2zvmLcbQNU+DYdnVywLXOTp8YnbufYUfzftc4PCJUCAIgUao7G9KIikB3X/71sgoR09EmxOskakI/Jn8pmkRlh+I=",
            "relationship": "",
            "relationship_hash": "f0fae7d88a277d853baee0a2e2f9de65fe0a7ef566515a00da18158f8cfc1181",
            "public_key": "020b97d335d58d7244590275da97868c1cb0163796ebafd1a9b70cc4fe6af0d80a",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "228251d41d801037bbe2ca2f6706edbe4e7534d2bccd0c68ef8474bfcf416260",
            "inputs": [],
            "outputs": [{"to": "1Bj6FLvUzPVYsUbZrr9Cd5Csdo7TaHud9d", "value": 0}],
            "version": 7,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "1Bj6FLvUzPVYsUbZrr9Cd5Csdo7TaHud9d",
            "twice_prerotated_key_hash": "1K3hy2pQSNMYZHmiN7pM75cuRcS5bFLjJG",
            "public_key_hash": "12JfRsP5ouBGyH31wraUjVq3LZ3pB5QWtG",
            "prev_public_key_hash": "",
        },
        {
            "time": 1739245292,
            "rid": "",
            "id": "MEQCIGgP00Xd3YsETGh1AcTYiCV9cigCFQMwFtADLPxivJN/AiB2fPQaB9aLiWThi4mCF+XBxBHCXIdqTtidmJH78QVy2Q==",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "ac9fc9e678d0c927948df4bf63ae4702658492b8f5f2f8cc2e751f58c1696d3e",
            "inputs": [],
            "outputs": [{"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 11.25}],
            "version": 6,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "",
            "twice_prerotated_key_hash": "",
            "public_key_hash": "",
            "prev_public_key_hash": "",
        },
    ],
    "hash": "9305612f8bc9c4051422581843b1704fb7e95e894b312f2d50a100be05110200",
    "merkleRoot": "afa3e5bcd1296807f32cf27794650d9aec844cb792367968b936dbc7cc765653",
    "special_min": False,
    "target": "0000000000000000000000000000000000000000000000000000000000000001",
    "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
    "header": "517392452920255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7537151f241f1e6348a6c89d681518666cc050407597429bb6d1d7652dfd5e4b7ec0100{nonce}0000000000000000000000000000000000000000000000000000000000000001afa3e5bcd1296807f32cf27794650d9aec844cb792367968b936dbc7cc765653",
    "id": "MEQCICeBn0J/+llIk/LXXT5uIPgM3pm2/ALVQi2jMK1+EOPwAiB1TguZAPOdpB/RYQb+skcI5Z8L1toezUUWQmT7Lr5uhQ==",
    "updated_at": 1739245297.0849366,
}
{
    "version": 5,
    "time": 1739245272,
    "index": 537147,
    "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
    "prevHash": "052b5940cbc9f2e3e4a9c59f2a58837bcb771649ef825e6dd541e6d7d1530200",
    "nonce": "21000100840902",
    "transactions": [
        {
            "time": 1739245259,
            "rid": "",
            "id": "MEQCIHKukvul9pRuWwGpsSq30yJw5E2o56CZuK6FhxUNYy40AiAeyOrL1r1R/rA2tmydOFgVfZtRtVv4zjZ3C5pGHEQxRw==",
            "relationship": "",
            "relationship_hash": "bbce6808679ed2683587df6e5e2cf5e32ff4dd11baf44a01b111cd8673b5a94c",
            "public_key": "03d0c03afff36498ba292b36c058d054bd75c6ebcf308e3f1b88255e32869588cf",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "77ee9395b6c5f7ff586ff729bf55a7632ad30d393a9e8bcf59df3df0e3cfdc33",
            "inputs": [],
            "outputs": [{"to": "1N3b5hw4jKoRqL9kDCfGBr8vscDFrxHWw1", "value": 0}],
            "version": 7,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "1N3b5hw4jKoRqL9kDCfGBr8vscDFrxHWw1",
            "twice_prerotated_key_hash": "1DJS5Bp6F3rRuRwSYaxp1jDn9eVvGgVguU",
            "public_key_hash": "1JqJDwjWZoSS7NpsGh9UTgt9dZKzQDe76K",
            "prev_public_key_hash": "14Em6BTbEqXEvDfyeZzAWFUYhpddoYpz9L",
        },
        {
            "time": 1739245272,
            "rid": "",
            "id": "MEUCIQDQYws3+44Gtzr5yyNBE9LZf3es5iQKgILl8d93GI0moAIgRXeqknIPH5DmAgKqZcGEn825BBCIVFTGd0kpxRo4bdQ=",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "1bf7d1213331ca5d8c1ea7d2ebfc588bae560b37b1c9dc23b38e8385d5bbbda1",
            "inputs": [],
            "outputs": [{"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 11.25}],
            "version": 6,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "",
            "twice_prerotated_key_hash": "",
            "public_key_hash": "",
            "prev_public_key_hash": "",
        },
    ],
    "hash": "b12a5c26a1b4b96979a5b043a6a80e8e51a4d2b785350cbcc7cf12e9e6d70200",
    "merkleRoot": "c239266f7a76769df2defd6a6f779effa544a50293e92c77c7ef7d869ecd78de",
    "special_min": False,
    "target": "0000000000000000000000000000000000000000000000000000000000000001",
    "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
    "header": "517392452720255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7537147052b5940cbc9f2e3e4a9c59f2a58837bcb771649ef825e6dd541e6d7d1530200{nonce}0000000000000000000000000000000000000000000000000000000000000001c239266f7a76769df2defd6a6f779effa544a50293e92c77c7ef7d869ecd78de",
    "id": "MEQCIGj7gbawSth5OXjXOl0tJXB0Uuv7GrghudLZ3OxHwR2pAiAzGt8a9OI4qSvBX/EsZ6yddlNVYLjVwFFTMDYrhn74kg==",
    "updated_at": 1739245273.034452,
}
{
    "version": 5,
    "time": 1739245234,
    "index": 537143,
    "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
    "prevHash": "981367eef2c3ce153d4aaed926958a01842413c93f411ae718ccca4e58550100",
    "nonce": "15810100321227",
    "transactions": [
        {
            "time": 1739245189,
            "rid": "",
            "id": "MEUCIQDcFFqys390i9NAi/IuU//8OQcU2rTD73GChbMQrXsVDAIgH0Qp38ehIrKvzrDVw+JgnKSK++tTCj7A7TrEcXA/HM8=",
            "relationship": "",
            "relationship_hash": "acb86d3d334e10354efdc499afe82081d71c37fee0c06468c19db8449a42220b",
            "public_key": "02dc74d252fc56769b1e293d5767cdd5dba9dd1162bd207624cdc05b8cd96a8230",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "584e4f84b5a505785b540a11421dc1751c67f44e1c4a34814eb94fc58d02fd6d",
            "inputs": [],
            "outputs": [{"to": "1JqJDwjWZoSS7NpsGh9UTgt9dZKzQDe76K", "value": 0}],
            "version": 7,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "1JqJDwjWZoSS7NpsGh9UTgt9dZKzQDe76K",
            "twice_prerotated_key_hash": "1N3b5hw4jKoRqL9kDCfGBr8vscDFrxHWw1",
            "public_key_hash": "14Em6BTbEqXEvDfyeZzAWFUYhpddoYpz9L",
            "prev_public_key_hash": "",
        },
        {
            "time": 1739245234,
            "rid": "",
            "id": "MEQCIB5LUkqmieVfafo/t3VyIG0FshYXgNHsnZ84SY/ZkCadAiAA/ixMkD2CURak70GdXTB0pZpoCaUQipBXh+vMQst3uQ==",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "f18f29f2784b28b40d6236b5c63051240e266f413e9512a27388d6aa870a6c91",
            "inputs": [],
            "outputs": [{"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 11.25}],
            "version": 6,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "",
            "twice_prerotated_key_hash": "",
            "public_key_hash": "",
            "prev_public_key_hash": "",
        },
    ],
    "hash": "284792dc50800be044c93ed2161117b806ea840fb402ef34c50dbc96bc590000",
    "merkleRoot": "3f59ccc705799596e6aa76725c23d1e9b132053e3ef53da3a8cfe1ee63b79f4e",
    "special_min": False,
    "target": "0000000000000000000000000000000000000000000000000000000000000001",
    "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
    "header": "517392452340255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7537143981367eef2c3ce153d4aaed926958a01842413c93f411ae718ccca4e58550100{nonce}00000000000000000000000000000000000000000000000000000000000000013f59ccc705799596e6aa76725c23d1e9b132053e3ef53da3a8cfe1ee63b79f4e",
    "id": "MEQCIATFjSA9+BXxUXgEzsNPietWkv7zyZlW4jGfLq8IeYFlAiAidWHs4tp5c0tDmiYT/gI4MaK1W0DOtyYZ0+GFlGC35w==",
    "updated_at": 1739245237.0984118,
}


class TestKeyEventLog(AsyncTestCase):
    @mock.patch(
        "yadacoin.core.blockchain.Blockchain.mongo", new_callable=lambda: MongoClient
    )
    async def asyncSetUp(self, mongo):
        mongo.async_db = mock.AsyncMock()
        mongo.async_db.blocks = mock.AsyncMock()
        mongo.async_db.blocks.aggregate = mock.AsyncMock()
        yadacoin.core.config.CONFIG = Config.generate()
        Config().mongo = mongo

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_one_key_event(self, mock_aggregate):
        inception_block = await Block.from_dict(check_kel_inception_block)

        mock_cursor = mock.Mock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_aggregate.return_value = mock_cursor

        for txn in inception_block.transactions:
            await KeyEventLog.from_transaction_with_block(txn, inception_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events(self, mock_aggregate):
        single_rotation_block = await Block.from_dict(
            json.loads(json.dumps(check_kel_single_rotation_block))
        )

        for txn in single_rotation_block.transactions:
            clone_check_kel_inception_block = json.loads(
                json.dumps(check_kel_inception_block)
            )
            clone_check_kel_inception_block[
                "transactions"
            ] = clone_check_kel_inception_block["transactions"][0]
            mock_cursor = mock.Mock()
            mock_cursor.to_list = AsyncMock(
                return_value=[clone_check_kel_inception_block]
            )
            mock_aggregate.return_value = mock_cursor
            await KeyEventLog.from_transaction_with_block(txn, single_rotation_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_external_unconfirmed(
        self, mock_aggregate
    ):
        single_rotation_block_external_unconfirmed = await Block.from_dict(
            json.loads(json.dumps(check_kel_single_rotation_block_external_unconfirmed))
        )

        for txn in single_rotation_block_external_unconfirmed.transactions:
            clone_check_kel_inception_block = json.loads(
                json.dumps(check_kel_inception_block)
            )
            clone_check_kel_inception_block[
                "transactions"
            ] = clone_check_kel_inception_block["transactions"][0]
            mock_cursor = mock.Mock()
            mock_cursor.to_list = AsyncMock(
                return_value=[clone_check_kel_inception_block]
            )
            mock_aggregate.return_value = mock_cursor
            await KeyEventLog.from_transaction_with_block(
                txn, single_rotation_block_external_unconfirmed
            )

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_missing_confirming(
        self, mock_aggregate
    ):
        clone_dict = json.loads(
            json.dumps(check_kel_single_rotation_block_external_unconfirmed)
        )
        del clone_dict["transactions"][1]
        clone_block = await Block.from_dict(clone_dict)

        with self.assertRaises(KELExceptionMissingConfirmingKeyEvent):
            for txn in clone_block.transactions:
                clone_check_kel_inception_block = json.loads(
                    json.dumps(check_kel_inception_block)
                )
                clone_check_kel_inception_block[
                    "transactions"
                ] = clone_check_kel_inception_block["transactions"][0]
                mock_cursor = mock.Mock()
                mock_cursor.to_list = AsyncMock(
                    return_value=[clone_check_kel_inception_block]
                )
                mock_aggregate.return_value = mock_cursor
                await KeyEventLog.from_transaction_with_block(txn, clone_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_missing_unconfirmed(
        self, mock_aggregate
    ):
        clone_dict = json.loads(
            json.dumps(check_kel_single_rotation_block_external_unconfirmed)
        )
        del clone_dict["transactions"][0]
        clone_block = await Block.from_dict(clone_dict)
        with self.assertRaises(KELExceptionMissingUnconfirmedKeyEvent):
            for txn in clone_block.transactions:
                clone_check_kel_inception_block = json.loads(
                    json.dumps(check_kel_inception_block)
                )
                clone_check_kel_inception_block[
                    "transactions"
                ] = clone_check_kel_inception_block["transactions"][0]
                mock_cursor = mock.Mock()
                mock_cursor.to_list = AsyncMock(
                    return_value=[clone_check_kel_inception_block]
                )
                mock_aggregate.return_value = mock_cursor
                await KeyEventLog.from_transaction_with_block(txn, clone_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_external_confirming(
        self, mock_aggregate
    ):
        clone_dict = json.loads(
            json.dumps(check_kel_single_rotation_block_external_unconfirmed)
        )
        clone_block = await Block.from_dict(clone_dict)
        clone_block.transactions[1].outputs[0].to = "some external output"
        with self.assertRaises(KeyEventPrerotatedKeyHashException):
            for txn in clone_block.transactions:
                clone_check_kel_inception_block = json.loads(
                    json.dumps(check_kel_inception_block)
                )
                clone_check_kel_inception_block[
                    "transactions"
                ] = clone_check_kel_inception_block["transactions"][0]
                mock_cursor = mock.Mock()
                mock_cursor.to_list = AsyncMock(
                    return_value=[clone_check_kel_inception_block]
                )
                mock_aggregate.return_value = mock_cursor
                await KeyEventLog.from_transaction_with_block(txn, clone_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_multiple_outputs_confirming(
        self, mock_aggregate
    ):
        clone_dict = json.loads(
            json.dumps(check_kel_single_rotation_block_external_unconfirmed)
        )
        clone_block = await Block.from_dict(clone_dict)
        clone_block.transactions[1].outputs.append(
            json.loads(json.dumps(clone_block.transactions[1].outputs[0].to_dict()))
        )
        with self.assertRaises(KeyEventSingleOutputException):
            for txn in clone_block.transactions:
                clone_check_kel_inception_block = json.loads(
                    json.dumps(check_kel_inception_block)
                )
                clone_check_kel_inception_block[
                    "transactions"
                ] = clone_check_kel_inception_block["transactions"][0]
                mock_cursor = mock.Mock()
                mock_cursor.to_list = AsyncMock(
                    return_value=[clone_check_kel_inception_block]
                )
                mock_aggregate.return_value = mock_cursor
                await KeyEventLog.from_transaction_with_block(txn, clone_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_multiple_outputs_unconfirmed(
        self, mock_aggregate
    ):
        clone_dict = json.loads(
            json.dumps(check_kel_single_rotation_block_external_unconfirmed)
        )
        clone_block = await Block.from_dict(clone_dict)
        clone_block.transactions[0].outputs.append(
            Output.from_dict(
                json.loads(json.dumps(clone_block.transactions[1].outputs[0].to_dict()))
            )
        )
        clone_block.transactions[0].outputs.append(
            Output.from_dict(
                json.loads(json.dumps(clone_block.transactions[1].outputs[0].to_dict()))
            )
        )
        clone_block.transactions[0].outputs[0].to = "first external output"
        clone_block.transactions[0].outputs[1].to = "second external output"
        clone_block.transactions[0].outputs[2].to = "third external output"
        for txn in clone_block.transactions:
            clone_check_kel_inception_block = json.loads(
                json.dumps(check_kel_inception_block)
            )
            clone_check_kel_inception_block[
                "transactions"
            ] = clone_check_kel_inception_block["transactions"][0]
            mock_cursor = mock.Mock()
            mock_cursor.to_list = AsyncMock(
                return_value=[clone_check_kel_inception_block]
            )
            mock_aggregate.return_value = mock_cursor
            await KeyEventLog.from_transaction_with_block(txn, clone_block)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
