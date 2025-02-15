"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

import yadacoin.core.config
from yadacoin.core.block import Block
from yadacoin.core.config import Config
from yadacoin.core.keyeventlog import (
    DoesNotSpendEntirelyToPrerotatedKeyHashException,
    FatalKeyEventException,
    KELException,
    KeyEventException,
    PublicKeyMismatchException,
)
from yadacoin.core.mongo import Mongo

from ..test_setup import AsyncTestCase

blocks = [
    {
        "version": 5,
        "time": 1739296037,
        "index": 537383,
        "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
        "prevHash": "11fce710021be56cb335c4de8b29c593895582d31341166b6938b06916960200",
        "nonce": "52c00100440339",
        "transactions": [
            {
                "time": 1739296002,
                "rid": "",
                "id": "MEUCIQD/91eMQGwNM8lGq8XtcjgmwIybfb7LwvetrFv3edOl8wIgDKi5g2IrjT5aBfdX4rsBX2CUCcdthWMoMKtiIh4b2NM=",
                "relationship": "",
                "relationship_hash": "",
                "public_key": "03cf228062cad517f99df2cb4403c84e1769c8714394dbf0ffca994de72fb0b1c1",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "1c9f8b56b90f8268ade4e34d45eecd8c9c3ca3342a0640a1e4e54e6ed1545797",
                "inputs": [],
                "outputs": [{"to": "1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR", "value": 0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
                "twice_prerotated_key_hash": "16K746UWNSzbdAAp24B9zcmdxvmpesfyPD",
                "public_key_hash": "1HazogSuV2NUdd1Cnebw4RVLN9RS8s86yv",
                "prev_public_key_hash": "",
            },
            {
                "time": 1739296002,
                "rid": "",
                "id": "MEQCIE8tb27EhCPDJJjs+NvEiEfYzMAcxQSr0wy1XlbswcLcAiBL867mmx55USwlDgHABq/aBQbbRgGRqcHs0lcmVl1KNw==",
                "relationship": "862bd46e1c5c9daa3df500929c4edb19047e4a63790906ce702f1945304e94c95b627030df190f6411585a3749dd7587179c03eba595cc9a3db70b8b27a4383f5ac541bf7a0c1b8edb0db0549f81addf243ac578f4146b4d24ec22d8584bbdfdbcfb9343d481e7b12f6a0019c361473c0021c08964102f57292d9fc69bc21f33dcd6eec7d4e33302f3fa3e667dc194a89f65278eaeb3c262ac7a83b1551d04c8ac9810023fbadc8ad03886583b42ea501e33266953cbaa3da84ac4aabebad5987470e0d37e6e062ba9361239a7f05a2653bd1736d8cafdb2f42ec7699f7715a3bac5cc59b2716a1970d5f210babc489b2c",
                "relationship_hash": "b721ee73977c27a3c04422ba6a311ce7eab0afb243d836172c3422e5a33350e8",
                "public_key": "02f1e1c362e47b89e6f0ad969f8d9dadfc30863b9cbb24b7568c6ba19705839094",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "ea41aeb00cadd1e624a9977e8958b4401de0c189713c19a5c29e5613cb756aed",
                "inputs": [],
                "outputs": [{"to": "1GnLjY6HmBJfwh5CaXbH1QtYpYGovkeNeX", "value": 0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "1NY91tSJvaFK7BYbGcXeGipoNKoqoXDSex",
                "twice_prerotated_key_hash": "18Pr4uTkgLRjhopsaKrQwSgjrLXD2i2NTt",
                "public_key_hash": "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar",
                "prev_public_key_hash": "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8",
            },
            {
                "time": 1739296002,
                "rid": "",
                "id": "MEQCIAKK9O98h7RwakV53yVX5P05Uh6Q1MUWnjQ8pcn4HEfYAiA3zdPhVT9xLY3rPVkO0u1g91qxHjKt4qwn+fhhEs1c/A==",
                "relationship": "",
                "relationship_hash": "",
                "public_key": "024acbfc45e0a1be8343c39b131cfb2b40ed7e9fdcbace150348d63d3e7789ba9e",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "59cce6fe3eaf610a4a394c888a4773f9f02c722339815ac11a8a005781e46c54",
                "inputs": [],
                "outputs": [{"to": "18Pr4uTkgLRjhopsaKrQwSgjrLXD2i2NTt", "value": 0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "18Pr4uTkgLRjhopsaKrQwSgjrLXD2i2NTt",
                "twice_prerotated_key_hash": "19ixX33USx7q7UAWkfHUwy9kZe2M6jtw7s",
                "public_key_hash": "1NY91tSJvaFK7BYbGcXeGipoNKoqoXDSex",
                "prev_public_key_hash": "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar",
            },
            {
                "time": 1739296037,
                "rid": "",
                "id": "MEUCIQCK2e1o2lGtH01fMAiMnrGeg698Bx7lqqHA0VM+kDDZeQIgBR5ICHE/QzW/OufdTOud3g/uV3nMJRQt0t6eX6BZsHQ=",
                "relationship": "",
                "relationship_hash": "",
                "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "ca2da4d4b925faaef7f9184d63e9bc23815071877d1fe659c6751e485a292e65",
                "inputs": [],
                "outputs": [
                    {"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 11.25}
                ],
                "version": 6,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "",
                "twice_prerotated_key_hash": "",
                "public_key_hash": "",
                "prev_public_key_hash": "",
            },
        ],
        "hash": "c2be5addd67df9ccf8791025fde30d62ec680c4bef38f11a17f9fce2f1360100",
        "merkleRoot": "902fc4d06ba900bd362dd14a156e01ff6472fd9cad646166ed2c55535515484a",
        "special_min": False,
        "target": "0000000000000000000000000000000000000000000000000000000000000001",
        "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
        "header": "517392960370255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a753738311fce710021be56cb335c4de8b29c593895582d31341166b6938b06916960200{nonce}0000000000000000000000000000000000000000000000000000000000000001902fc4d06ba900bd362dd14a156e01ff6472fd9cad646166ed2c55535515484a",
        "id": "MEUCIQC9HPObIQ9yWoYhRsWTuCBtASMl5kUhv/g7VS7VL+jRfQIgV9k+Yeuu+04P96FcYlWud5VjW2DKqlzpqLsPU9Wwsb8=",
        "updated_at": 1739296100.7011893,
    },
    {
        "version": 5,
        "time": 1739295979,
        "index": 537381,
        "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
        "prevHash": "32b79965adb9de3fdc624a5c43134a1444d5328595d5de96e753354508c80200",
        "nonce": "41110100557716",
        "transactions": [
            {
                "time": 1739295913,
                "rid": "",
                "id": "MEUCIQDu1/xO0A30GEMjNekhqUrYSJNcN2AGqCYeK6PeHPFPOgIgWUFA7JjYkmtatCcM2ZIpSsZ00vTbAeIxhQibbIkq+4U=",
                "relationship": "",
                "relationship_hash": "",
                "public_key": "02eeba6e0e5456170ae3a4b00b5c05e96cbad093d44eda2ad586db0d240df3d222",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "a0567d810e60307735d8f6f77429b9d6e89c2b1d659c0af2ecfe3366285387ef",
                "inputs": [],
                "outputs": [{"to": "19oT4UmfBDYZaPxZNEEXNS4uURpW8GAfN", "value": 0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "19oT4UmfBDYZaPxZNEEXNS4uURpW8GAfN",
                "twice_prerotated_key_hash": "1JKRuAtMQ1JXkt5jrig58TV2YohJ6h6fDA",
                "public_key_hash": "12W3sApeAr8RwUhWHZZPAe56pa7MojKuKm",
                "prev_public_key_hash": "",
            },
            {
                "time": 1739295913,
                "rid": "",
                "id": "MEQCIHRMB2JRNoOOoZxpEqbMs4b0q8uekQ3aV0hWiS4XoVjDAiBtNCTnhWgXMnXTf9KBj32LZ6u//l5T8aIkPtTnvafCzw==",
                "relationship": "6f4997a332103722a806d0395c875c8c04db12c97327889df8a023e36975c28157de11e74f5043e9aeec2fbe69660195c2159e3dcdaddbe959866a6edeed88b6ed4d3547a4ddd16de696b5418022028efd3f89c97d4da0141395ab96f2b7317a7eec814bb4d2b875b4e6c7b77bdc78bbbcdf871f027abbc42117dba39abdc15888feb330113c99ceb9168043740ce49ad2051864feedf1309b25ede6a6dfc60015e039d68241c188dfdd0e02d0543ba3e04f4b597b3f56a874012ef6ed835cc17ddaf26c91a9ce73ede2ea3fa57eb4ea4248e1bbf98eb7cdcc6a49cc82151a6af623c159ce25474c0dab1f484aca95e8b6f9c975ce7a36c77a0fc8c0e4ecf2b7f802562cc7cd496d3ab813b5db570bbc27cfb96d66886133d5c75a69c3a5799deae9b7498e9783a1096b12baf6fbee6f9eea6cc33cea25a95674826e40bbea8c59b868455f63def79a644906e6ba567cc86f6c1d406f4fe0c59d25523599bcbadd779f931b0f5cdc028c7fb0d92e02b1c0",
                "relationship_hash": "483191a2573efbaf5a9cb8f2d64958bbbe806e84e166f0c17b5a346321719e17",
                "public_key": "029703efa6ec92ffc02b37cbbb6c0eba64259a30d0ee3ba2137cfbc7437a33ac0c",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "fa7c5ae5228a0a6d7e93bf7cfaabc8967f716e29ff891baca302c5ef0e4c0214",
                "inputs": [],
                "outputs": [{"to": "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar", "value": 0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "1NFno8hDcr7WeogZLtuvbUwprLNnRfxuJp",
                "twice_prerotated_key_hash": "1GnLjY6HmBJfwh5CaXbH1QtYpYGovkeNeX",
                "public_key_hash": "1Ai8ozMzUHNreMh3Tg3cZEHexP4qMytMhi",
                "prev_public_key_hash": "1GUmkx3RGNS5cRJUDah2vN47un3GKebWFZ",
            },
            {
                "time": 1739295913,
                "rid": "",
                "id": "MEQCICDsj3mwviF4vItbsZKtykCRaqsF2Wton+N7Lzmhjz1SAiBT1POOLlQuY28gN0U4hzkh2Uv/9v+mWI6SoQ+uL3i3vQ==",
                "relationship": "",
                "relationship_hash": "",
                "public_key": "02a3951ce29d0235a2fe98e33acfd122da2c2c7ebf0bbcb611483d22e41edec688",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "a9a5368b913327c368cddf6f7b663e9bce5ba0e8316a57fa54d757620eea9f51",
                "inputs": [],
                "outputs": [{"to": "1GnLjY6HmBJfwh5CaXbH1QtYpYGovkeNeX", "value": 0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "1GnLjY6HmBJfwh5CaXbH1QtYpYGovkeNeX",
                "twice_prerotated_key_hash": "1KueSQKP2eoXpwuEzbx2sdtTQu5Daoiq9j",
                "public_key_hash": "1NFno8hDcr7WeogZLtuvbUwprLNnRfxuJp",
                "prev_public_key_hash": "1Ai8ozMzUHNreMh3Tg3cZEHexP4qMytMhi",
            },
            {
                "time": 1739295979,
                "rid": "",
                "id": "MEQCIH/Jj8/Q69E3zbc0tzj+5PROZpnJGZ/kKvI6+FYKmughAiAkINtbWNWkemNY1zSUE9l1sZIgOs0kA1HUC5C0kj0nDg==",
                "relationship": "",
                "relationship_hash": "",
                "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "86ff398b77a75cd918ed4d80e62360b0967de13c130bb3ae7518c675a3d63c1f",
                "inputs": [],
                "outputs": [
                    {"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 11.25}
                ],
                "version": 6,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "",
                "twice_prerotated_key_hash": "",
                "public_key_hash": "",
                "prev_public_key_hash": "",
            },
        ],
        "hash": "260d3ee92b4e82e3e7624a155f52dd7b548d4d2e3ff82c0f32cee06097b70200",
        "merkleRoot": "f8d5d18abae0cab01080030835d4537d01a7215b05a5295634d61705a01b3d2b",
        "special_min": False,
        "target": "0000000000000000000000000000000000000000000000000000000000000001",
        "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
        "header": "517392959790255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a753738132b79965adb9de3fdc624a5c43134a1444d5328595d5de96e753354508c80200{nonce}0000000000000000000000000000000000000000000000000000000000000001f8d5d18abae0cab01080030835d4537d01a7215b05a5295634d61705a01b3d2b",
        "id": "MEQCIF+2mTfDqOmx3saNuY6h4uYotTep7h369/a+JbA0M2FAAiBjWeejjUumb1nFq1NNtucvR4A2LTD7SZ5p4eIZcXFbyQ==",
        "updated_at": 1739295997.706077,
    },
    {
        "version": 5,
        "time": 1739295880,
        "index": 537378,
        "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
        "prevHash": "97ce16ce54ab79cc9f0142ccf93e67359983dd93afad31932d001881766b0100",
        "nonce": "ad080100125027",
        "transactions": [
            {
                "time": 1739295860,
                "rid": "",
                "id": "MEQCIBwvoTy6nNcViCnB+pn2TzWqTmSqYRQBgvgvRRR3ROktAiBXx4dQUbOAFM9mEwGn1KNjZeEhrIBRmVFZ8S3m1BrCHg==",
                "relationship": "",
                "relationship_hash": "f746cbfcbaf4da3a1d2cf228fad59108f16df6d9caa617bc45bd497326b771e2",
                "public_key": "02850674626716f3d511d51d43824057f45348154735318388d51a4d436709b83d",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "45d42240937a8d6cbacce054ad6e59190184f5fc77f9c8a039b849094123acf9",
                "inputs": [],
                "outputs": [{"to": "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar", "value": 0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar",
                "twice_prerotated_key_hash": "1NY91tSJvaFK7BYbGcXeGipoNKoqoXDSex",
                "public_key_hash": "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8",
                "prev_public_key_hash": "",
            },
            {
                "time": 1739295872,
                "rid": "",
                "id": "MEUCIQCslmNfKjOtOhwknU/tZXg1bljYboqtDlRo2cNvgSHTNAIge67l61ypF4P2rjFLDCK37glqXDS4OBScY4I5EN4GlQw=",
                "relationship": "",
                "relationship_hash": "cd5eb09d4c33f876231bbc2c436556f53aaee446dd813ecf4a56a98bc7a18b3b",
                "public_key": "0220c4e9256d948142bf511c89a5dbedf9b094a16c169ee72ec15298500fa297f5",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "0ae4f64efe3d1a615b35ac01e36598e180c7c9bb3f328c477eaefe86f17f9c51",
                "inputs": [],
                "outputs": [{"to": "1Ai8ozMzUHNreMh3Tg3cZEHexP4qMytMhi", "value": 0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "1Ai8ozMzUHNreMh3Tg3cZEHexP4qMytMhi",
                "twice_prerotated_key_hash": "1NFno8hDcr7WeogZLtuvbUwprLNnRfxuJp",
                "public_key_hash": "1GUmkx3RGNS5cRJUDah2vN47un3GKebWFZ",
                "prev_public_key_hash": "1M9cbjGePcd4RMQY9ntqBkzY6DPyBCwTpc",
            },
            {
                "time": 1739295880,
                "rid": "",
                "id": "MEUCIQD5Ugf8Cqzo90aXFBp6xLJilXGT1FyZ5HQWBnpfnaM8HAIgdwwBLXjKkquUuxYw3qYCRyV9pm7Ummh1N1+sO4ULv+0=",
                "relationship": "",
                "relationship_hash": "",
                "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "2c35364435eb073ae97de8b49c09bdb0b0c89b68709686dff5a16f25a195f8bb",
                "inputs": [],
                "outputs": [
                    {"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 11.25}
                ],
                "version": 6,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "",
                "twice_prerotated_key_hash": "",
                "public_key_hash": "",
                "prev_public_key_hash": "",
            },
        ],
        "hash": "e6c45d2d987971242db19c3b7c74fe174e950f49602ec902294670bc6e020100",
        "merkleRoot": "aab47ce6648659a9a2dcf787bac17650800c684cc125ae3394984333570f707c",
        "special_min": False,
        "target": "0000000000000000000000000000000000000000000000000000000000000001",
        "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
        "header": "517392958800255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a753737897ce16ce54ab79cc9f0142ccf93e67359983dd93afad31932d001881766b0100{nonce}0000000000000000000000000000000000000000000000000000000000000001aab47ce6648659a9a2dcf787bac17650800c684cc125ae3394984333570f707c",
        "id": "MEUCIQDRthS2JIlKa+EvPV4z95a7fWOh7umTrJtSmDuZa6nzIAIgWBiaD9b5qThCBgsID2Gqxe0debcHfK8uVRreNYAk0NM=",
        "updated_at": 1739295893.603682,
    },
    {
        "version": 5,
        "time": 1739295822,
        "index": 537375,
        "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
        "prevHash": "ce760c9106dcc51663a21085c478cc192c2f00ef2e825238e337ab6ee2bf0000",
        "nonce": "d3140100849241",
        "transactions": [
            {
                "time": 1739295811,
                "rid": "",
                "id": "MEUCIQDdbWtF7UDoP9JHYhc4bYdebWK07I+hHYcQEkJQi7/3SAIgcjuVviFkShRtlPBiotCr6saeQ6XOvRXujoxBDUU88kc=",
                "relationship": "",
                "relationship_hash": "dd4900ceeaee014b4bc4ce0576a5beafc2ce919daa67e01d47eb1d9f39a8e2c8",
                "public_key": "03b62ac7478f30fd8a6a92b5e5bd2158e05d9f8efb41bcfc2e201238972c28a730",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "55b9f96bb5795a9e7b98bbfa5ad83a43e4395b63c0655641bae0ed3faeb32d41",
                "inputs": [],
                "outputs": [{"to": "1GUmkx3RGNS5cRJUDah2vN47un3GKebWFZ", "value": 0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "1GUmkx3RGNS5cRJUDah2vN47un3GKebWFZ",
                "twice_prerotated_key_hash": "1Ai8ozMzUHNreMh3Tg3cZEHexP4qMytMhi",
                "public_key_hash": "1M9cbjGePcd4RMQY9ntqBkzY6DPyBCwTpc",
                "prev_public_key_hash": "1DrrpfeK6eSJzDgXyQx3jwP6xwcXeNAnYi",
            },
            {
                "time": 1739295822,
                "rid": "",
                "id": "MEUCIQD4Cq8gRqYpi81KyFKp4EU6qL5GhDDpFRonYTpOJhN82gIgYDw6/ngZgO7SYNNDoDTdH6Jt7IPhq9HBdDv8o08SWtE=",
                "relationship": "",
                "relationship_hash": "",
                "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "04371d2b1d5e8e9485a78818582c125c51285137da6901f0d178f9b6c6270642",
                "inputs": [],
                "outputs": [
                    {"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 11.25}
                ],
                "version": 6,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "",
                "twice_prerotated_key_hash": "",
                "public_key_hash": "",
                "prev_public_key_hash": "",
            },
        ],
        "hash": "9590395ef6ea2858e23073ee598d4c3e2f103cf6790ad4e674c4fd8dfd280000",
        "merkleRoot": "c8f13eee7b9f1b5fcc52f78552a5a7765e154b177f59515bfc82223f44af6fcc",
        "special_min": False,
        "target": "0000000000000000000000000000000000000000000000000000000000000001",
        "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
        "header": "517392958220255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7537375ce760c9106dcc51663a21085c478cc192c2f00ef2e825238e337ab6ee2bf0000{nonce}0000000000000000000000000000000000000000000000000000000000000001c8f13eee7b9f1b5fcc52f78552a5a7765e154b177f59515bfc82223f44af6fcc",
        "id": "MEQCICUXfTSGn6YcW83zjmsHqY0bUM176Ik1eCTb1+f4h5A/AiAmTIm5l3DTPVRNb1ITMx0USMj0LfXdqziYNV+kGRWvZA==",
        "updated_at": 1739295844.4960084,
    },
    {
        "version": 5,
        "time": 1739295801,
        "index": 537373,
        "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
        "prevHash": "116d4baa67fc905152b107cc2f3f0b1bb3c2246cff47a236a9536fed4b390000",
        "nonce": "57840000266139",
        "transactions": [
            {
                "time": 1739295791,
                "rid": "",
                "id": "MEUCIQDXYVOxR1WmhabY8JD2QXf+kLCUtUkh5JgZh1pKOWmzVAIgH4lcHm3yblbOC1ZOsv1E4e1C79X2PIPTqT9RnToMjbU=",
                "relationship": "",
                "relationship_hash": "e1b1bf42680b5bc0b53cc0eeda8907dd58cedd76156c1f77cf59bde89c51d93b",
                "public_key": "038eb62674f66368a7e436931f6907220d3dc97900cb0d926a45b191e5a6478559",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "d8d75248d96eb946c7f767fecdafe5dc2c9784c2886bea9de793db663cafede1",
                "inputs": [],
                "outputs": [{"to": "1M9cbjGePcd4RMQY9ntqBkzY6DPyBCwTpc", "value": 0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "1M9cbjGePcd4RMQY9ntqBkzY6DPyBCwTpc",
                "twice_prerotated_key_hash": "1GUmkx3RGNS5cRJUDah2vN47un3GKebWFZ",
                "public_key_hash": "1DrrpfeK6eSJzDgXyQx3jwP6xwcXeNAnYi",
                "prev_public_key_hash": "",
            },
            {
                "time": 1739295801,
                "rid": "",
                "id": "MEUCIQCjzlmVGhZF79Cm8pdS0Cp5nCLKWCFptR+OvwIrnnjr+QIgdVuVjRk3T3DGhxPkyPAWyC9Hp847jZInaUJ436DL/I8=",
                "relationship": "",
                "relationship_hash": "",
                "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "e468bd2b9714dd7c2b46d823a4247e2c40dcf8e23679a8f549f452d40c9a5454",
                "inputs": [],
                "outputs": [
                    {"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 11.25}
                ],
                "version": 6,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "",
                "twice_prerotated_key_hash": "",
                "public_key_hash": "",
                "prev_public_key_hash": "",
            },
        ],
        "hash": "56e3db70d901210ff6fb7505350b23e2b9bb9c1f78272988adbd5ca688680000",
        "merkleRoot": "5e8543da5dd93f2690f3d11e0d10afd81acab770d6e8fc0790743d2e434178bd",
        "special_min": False,
        "target": "0000000000000000000000000000000000000000000000000000000000000001",
        "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
        "header": "517392958010255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7537373116d4baa67fc905152b107cc2f3f0b1bb3c2246cff47a236a9536fed4b390000{nonce}00000000000000000000000000000000000000000000000000000000000000015e8543da5dd93f2690f3d11e0d10afd81acab770d6e8fc0790743d2e434178bd",
        "id": "MEQCIG9hpZwjOQuyVsReR9YQFtpFA0Nz4z3eV4BRNBSQ90YqAiB7rQsXb1bNKue5ugmPpLljVHjg4RNJJrJcV1q2VBAyaw==",
        "updated_at": 1739295809.324036,
    },
]


class TestKeyEventLog(AsyncTestCase):
    async def asyncSetUp(self):
        yadacoin.core.config.CONFIG = Config.generate()
        Config().mongo = Mongo()
        self.config = Config()

        class AppLog:
            def warning(self, message):
                pass

            def info(self, message):
                pass

        Config().app_log = AppLog()
        for block in blocks:
            xblock = await Block.from_dict(block)
            self.config.mongo.async_db.blocks.delete_one({"index": xblock.index})

    async def test_inception(self):
        xblock = await Block.from_dict(blocks[-1])
        await xblock.verify()

    async def test_inception_onchain_and_confirming(self):
        xblock = await Block.from_dict(blocks[-2])
        with self.assertRaises(KELException):
            await xblock.verify()

        self.config.mongo.async_db.blocks.insert_one(blocks[-1])

        await xblock.verify()

    async def test_confirming_onchain_and_confirming(self):
        xblock = await Block.from_dict(blocks[-3])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-2:]:
            self.config.mongo.async_db.blocks.insert_one(block)

        await xblock.verify()

    async def test_inception_onchain_unconfirmed_and_confirming(self):
        xblock = await Block.from_dict(blocks[-4])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-3:]:
            self.config.mongo.async_db.blocks.insert_one(block)

        await xblock.verify()

    async def test_confirming_onchain_unconfirmed_and_confirming(self):
        xblock = await Block.from_dict(blocks[-5])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-4:]:
            self.config.mongo.async_db.blocks.insert_one(block)

        await xblock.verify()

    async def test_misalignment_of_twice_prerotated_key_hash(self):
        xblock = await Block.from_dict(blocks[-5])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-4:]:
            self.config.mongo.async_db.blocks.insert_one(block)

        xblock.transactions[1].twice_prerotated_key_hash = "test fail"
        with self.assertRaises(FatalKeyEventException):
            await xblock.verify()

    async def test_misalignment_of_prerotated_key_hash(self):
        xblock = await Block.from_dict(blocks[-5])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-4:]:
            self.config.mongo.async_db.blocks.insert_one(block)

        xblock.transactions[1].prerotated_key_hash = "test fail"

        with self.assertRaises(KeyEventException):
            await xblock.verify()

    async def test_misalignment_of_public_key_hash(self):
        xblock = await Block.from_dict(blocks[-5])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-4:]:
            self.config.mongo.async_db.blocks.insert_one(block)

        xblock.transactions[1].public_key_hash = "test fail"

        with self.assertRaises(PublicKeyMismatchException):
            await xblock.verify()

    async def test_misalignment_of_prev_public_key_hash(self):
        xblock = await Block.from_dict(blocks[-5])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-4:]:
            self.config.mongo.async_db.blocks.insert_one(block)

        xblock.transactions[1].prev_public_key_hash = "test fail"

        with self.assertRaises(FatalKeyEventException):
            await xblock.verify()

    async def test_transaction_spends_public_key_with_kel(self):
        # This is the salient test for a transaction
        # that attempts to spend from a KEL while
        # masquerading as a non-KEL transaction.
        # if this exception is raised, it means a KEL was found
        # for the public key, as it should.
        for block in blocks[-4:]:
            self.config.mongo.async_db.blocks.insert_one(block)
        xblock = await Block.from_dict(blocks[-5])
        xblock.transactions[1].twice_prerotated_key_hash = ""
        xblock.transactions[1].prerotated_key_hash = ""
        xblock.transactions[1].public_key_hash = ""
        xblock.transactions[1].prev_public_key_hash = ""

        with self.assertRaises(PublicKeyMismatchException):
            await xblock.verify()

    async def test_transaction_spends_to_expired_key_event(self):
        # test if user will lose access to their funds by way of rotation
        self.config.mongo.async_db.blocks.delete_one({"index": 537373})
        self.config.mongo.async_db.blocks.insert_one(blocks[-5])
        xblock = await Block.from_dict(blocks[-1])
        xblock.transactions[0].outputs[0].to = "1DrrpfeK6eSJzDgXyQx3jwP6xwcXeNAnYi"

        with self.assertRaises(DoesNotSpendEntirelyToPrerotatedKeyHashException):
            await xblock.verify()


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
