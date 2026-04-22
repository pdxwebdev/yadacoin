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
                    {"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 12.5}
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
                    {"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 12.5}
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
                    {"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 12.5}
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
                    {"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 12.5}
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
                    {"to": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC", "value": 12.5}
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
        yadacoin.core.config.CONFIG = Config()
        Config().mongo = Mongo()
        Config().network = "regnet"
        self.config = Config()

        class AppLog:
            def warning(self, message):
                pass

            def info(self, message):
                pass

        Config().app_log = AppLog()
        await self._cleanup_test_blocks()

    async def _cleanup_test_blocks(self):
        for block in blocks:
            xblock = await Block.from_dict(block)
            await self.config.mongo.async_db.blocks.delete_many({"index": xblock.index})
            if "_id" in block:
                await self.config.mongo.async_db.blocks.delete_many(
                    {"_id": block["_id"]}
                )
        # Clean up synthetic pre-inception block used by routing fork tests
        await self.config.mongo.async_db.blocks.delete_many({"index": 537370})

    async def asyncTearDown(self):
        await self._cleanup_test_blocks()

    async def test_inception(self):
        xblock = await Block.from_dict(blocks[-1])
        await xblock.verify()

    async def test_inception_onchain_and_confirming(self):
        xblock = await Block.from_dict(blocks[-2])
        with self.assertRaises(KELException):
            await xblock.verify()

        await self.config.mongo.async_db.blocks.insert_one(blocks[-1])

        await xblock.verify()

    async def test_confirming_onchain_and_confirming(self):
        xblock = await Block.from_dict(blocks[-3])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-2:]:
            await self.config.mongo.async_db.blocks.insert_one(block)

        await xblock.verify()

    async def test_inception_onchain_unconfirmed_and_confirming(self):
        xblock = await Block.from_dict(blocks[-4])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-3:]:
            await self.config.mongo.async_db.blocks.insert_one(block)

        # The unconfirmed txn (txn[1]) and its confirming txn (txn[2]) are both
        # in the same block. The confirming txn needs the unconfirmed txn's
        # public_key_hash in the mempool to pass KeyEvent.verify().
        await self.config.mongo.async_db.miner_transactions.insert_one(
            xblock.transactions[1].to_dict()
        )
        try:
            await xblock.verify()
        finally:
            await self.config.mongo.async_db.miner_transactions.delete_one(
                {"id": xblock.transactions[1].transaction_signature}
            )

    async def test_confirming_onchain_unconfirmed_and_confirming(self):
        xblock = await Block.from_dict(blocks[-5])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-4:]:
            await self.config.mongo.async_db.blocks.insert_one(block)

        # txn[1] and txn[2] are both in the same block. txn[2] has
        # prev_public_key_hash pointing to txn[1]'s public_key_hash.
        # The confirming txn needs to find its predecessor in the mempool.
        await self.config.mongo.async_db.miner_transactions.insert_one(
            xblock.transactions[1].to_dict()
        )
        try:
            await xblock.verify()
        finally:
            await self.config.mongo.async_db.miner_transactions.delete_one(
                {"id": xblock.transactions[1].transaction_signature}
            )

    async def test_misalignment_of_twice_prerotated_key_hash(self):
        xblock = await Block.from_dict(blocks[-5])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-4:]:
            await self.config.mongo.async_db.blocks.insert_one(block)

        xblock.transactions[1].twice_prerotated_key_hash = "test fail"
        with self.assertRaises(FatalKeyEventException):
            await xblock.verify()

    async def test_misalignment_of_prerotated_key_hash(self):
        xblock = await Block.from_dict(blocks[-5])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-4:]:
            await self.config.mongo.async_db.blocks.insert_one(block)

        xblock.transactions[1].prerotated_key_hash = "test fail"

        with self.assertRaises(KeyEventException):
            await xblock.verify()

    async def test_misalignment_of_public_key_hash(self):
        xblock = await Block.from_dict(blocks[-5])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-4:]:
            await self.config.mongo.async_db.blocks.insert_one(block)

        xblock.transactions[1].public_key_hash = "test fail"

        with self.assertRaises(PublicKeyMismatchException):
            await xblock.verify()

    async def test_misalignment_of_prev_public_key_hash(self):
        xblock = await Block.from_dict(blocks[-5])
        with self.assertRaises(KELException):
            await xblock.verify()

        for block in blocks[-4:]:
            await self.config.mongo.async_db.blocks.insert_one(block)

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
            await self.config.mongo.async_db.blocks.insert_one(block)
        xblock = await Block.from_dict(blocks[-5])
        xblock.transactions[1].twice_prerotated_key_hash = ""
        xblock.transactions[1].prerotated_key_hash = ""
        xblock.transactions[1].public_key_hash = ""
        xblock.transactions[1].prev_public_key_hash = ""

        with self.assertRaises(PublicKeyMismatchException):
            await xblock.verify()

    async def test_transaction_spends_to_expired_key_event(self):
        # test if user will lose access to their funds by way of rotation
        await self.config.mongo.async_db.blocks.delete_one({"index": 537373})
        await self.config.mongo.async_db.blocks.insert_one(blocks[-5])
        xblock = await Block.from_dict(blocks[-1])
        xblock.transactions[0].outputs[0].to = "1DrrpfeK6eSJzDgXyQx3jwP6xwcXeNAnYi"

        with self.assertRaises(DoesNotSpendEntirelyToPrerotatedKeyHashException):
            await xblock.verify()

    async def test_check_kel_output_routing_fork_allows_send_to_latest_key(self):
        """
        Wallet 1 has a 3-entry KEL (inception + confirming + confirming).
        Wallet 2 sends funds to Wallet 1's inception address.
        Wallet 1 (using its inception key) then forwards those funds to its
        latest key log entry's public_key_hash.
        verify_kel_output_rules should allow this transaction through.

        Wallet 1 KEL chain (using existing test block data):
          - Inception  (blocks[-2], idx 537375):
              public_key_hash        = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
              prerotated_key_hash    = "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar"
              twice_prerotated       = "1NY91tSJvaFK7BYbGcXeGipoNKoqoXDSex"
          - Confirming 1 (blocks[-5], idx 537383, txn index 1):
              public_key_hash        = "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar"
              prev_public_key_hash   = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
              prerotated_key_hash    = "1NY91tSJvaFK7BYbGcXeGipoNKoqoXDSex"
              twice_prerotated       = "18Pr4uTkgLRjhopsaKrQwSgjrLXD2i2NTt"
          - Confirming 2 (blocks[-5], idx 537383, txn index 2):
              public_key_hash        = "1NY91tSJvaFK7BYbGcXeGipoNKoqoXDSex"  ← latest
              prev_public_key_hash   = "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar"
              prerotated_key_hash    = "18Pr4uTkgLRjhopsaKrQwSgjrLXD2i2NTt"

        Wallet 1 inception public_key:
            "02850674626716f3d511d51d43824057f45348154735318388d51a4d436709b83d"
        Wallet 1 inception address (= inception public_key_hash):
            "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"

        For has_key_event_log to return True for wallet 1's signing key,
        a synthetic "pre-inception" block is inserted that has
        prerotated_key_hash = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8".
        """
        from unittest.mock import MagicMock

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.transaction import Transaction

        # Insert the inception block and confirming block into the DB.
        # blocks[-3] (index 537378) contains the inception txn for
        # wallet 1 (public_key_hash = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8").
        # blocks[-5] (index 537383) contains confirming entries 2 and 3.
        await self.config.mongo.async_db.blocks.insert_one(blocks[-3])
        await self.config.mongo.async_db.blocks.insert_one(blocks[-5])

        # Insert a synthetic "pre-inception" block so that has_key_event_log
        # returns True for wallet 1's inception key address.
        # This block simulates a prior rotation that committed to rotating
        # to wallet 1's inception address.
        pre_inception_block = {
            "version": 5,
            "time": 1739295700,
            "index": 537370,
            "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
            "prevHash": "0000000000000000000000000000000000000000000000000000000000000000",
            "nonce": "000001",
            "transactions": [
                {
                    "time": 1739295700,
                    "rid": "",
                    "id": "pre_inception_txn_id",
                    "relationship": "",
                    "relationship_hash": "",
                    "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
                    "dh_public_key": "",
                    "fee": 0.0,
                    "masternode_fee": 0.0,
                    "hash": "pre_inception_hash",
                    "inputs": [],
                    "outputs": [
                        {
                            "to": "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8",
                            "value": 0,
                        }
                    ],
                    "version": 7,
                    "private": False,
                    "never_expire": False,
                    # Points to wallet 1's inception address as the next rotation target
                    "prerotated_key_hash": "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8",
                    "twice_prerotated_key_hash": "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar",
                    "public_key_hash": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC",
                    "prev_public_key_hash": "",
                }
            ],
            "hash": "pre_inception_block_hash",
            "merkleRoot": "pre_inception_merkle",
            "special_min": False,
            "target": "0000000000000000000000000000000000000000000000000000000000000001",
            "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
            "header": "header",
            "id": "pre_inception_block_id",
            "updated_at": 1739295700.0,
        }
        await self.config.mongo.async_db.blocks.insert_one(pre_inception_block)

        # Mock LatestBlock to be at a block index above CHECK_KEL_OUTPUT_ROUTING_FORK
        self.config.LatestBlock = MagicMock()
        self.config.LatestBlock.block = MagicMock()
        self.config.LatestBlock.block.index = CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK + 100

        # Wallet 1 inception key signs a spending transaction.
        # Wallet 2 previously sent 10 YDA to wallet 1's inception address
        # ("1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"). Wallet 1 now forwards
        # those funds to the latest key log entry's prerotated_key_hash.
        wallet1_inception_pubkey = (
            "02850674626716f3d511d51d43824057f45348154735318388d51a4d436709b83d"
        )
        wallet1_inception_address = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        # Latest prerotated_key_hash from key_log[-1] (Confirming 2 in blocks[-5])
        latest_prerotated_key_hash = "18Pr4uTkgLRjhopsaKrQwSgjrLXD2i2NTt"

        # Build the spending transaction (wallet 1 sending to its latest address).
        # public_key_hash is set to the inception address so that
        # is_new_key_log_entry resolves to False and the routing-fork enforcement
        # path is exercised (output must go to key_log[-1].prerotated_key_hash).
        spending_txn = Transaction(
            txn_time=1739296100,
            transaction_signature="wallet1_spending_txn_id",
            public_key=wallet1_inception_pubkey,
            fee=0.0,
            txn_hash="wallet1_spending_hash",
            inputs=[{"id": "wallet2_funding_txn_id"}],
            outputs=[{"to": latest_prerotated_key_hash, "value": 10.0}],
            version=7,
            prerotated_key_hash="",
            twice_prerotated_key_hash="",
            # Identify this tx as spending from wallet 1's inception address
            public_key_hash=wallet1_inception_address,
            prev_public_key_hash="",
        )

        # verify_kel_output_rules should NOT raise: sending to the latest
        # key log entry's prerotated_key_hash is allowed by CHECK_KEL_OUTPUT_ROUTING_FORK
        await spending_txn.verify_kel_output_rules()

    async def test_check_kel_output_routing_fork_rejects_wrong_destination(self):
        """
        Same scenario as test_check_kel_output_routing_fork_allows_send_to_latest_key,
        but wallet 1 tries to send funds to an address that is NOT the latest
        public_key_hash. This must be rejected.
        """
        from unittest.mock import MagicMock

        from yadacoin.core.chain import CHAIN
        from yadacoin.core.transaction import Transaction

        # Insert the inception block and confirming block into the DB.
        # blocks[-3] (index 537378) contains the inception txn for wallet 1.
        # blocks[-5] (index 537383) contains confirming entries 2 and 3.
        await self.config.mongo.async_db.blocks.insert_one(blocks[-3])
        await self.config.mongo.async_db.blocks.insert_one(blocks[-5])

        # Insert the synthetic pre-inception block (same as the positive test)
        pre_inception_block = {
            "version": 5,
            "time": 1739295700,
            "index": 537370,
            "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
            "prevHash": "0000000000000000000000000000000000000000000000000000000000000000",
            "nonce": "000001",
            "transactions": [
                {
                    "time": 1739295700,
                    "rid": "",
                    "id": "pre_inception_txn_id",
                    "relationship": "",
                    "relationship_hash": "",
                    "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7",
                    "dh_public_key": "",
                    "fee": 0.0,
                    "masternode_fee": 0.0,
                    "hash": "pre_inception_hash",
                    "inputs": [],
                    "outputs": [
                        {
                            "to": "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8",
                            "value": 0,
                        }
                    ],
                    "version": 7,
                    "private": False,
                    "never_expire": False,
                    "prerotated_key_hash": "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8",
                    "twice_prerotated_key_hash": "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar",
                    "public_key_hash": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC",
                    "prev_public_key_hash": "",
                }
            ],
            "hash": "pre_inception_block_hash",
            "merkleRoot": "pre_inception_merkle",
            "special_min": False,
            "target": "0000000000000000000000000000000000000000000000000000000000000001",
            "special_target": "0000000000000000000000000000000000000000000000000000000000000001",
            "header": "header",
            "id": "pre_inception_block_id",
            "updated_at": 1739295700.0,
        }
        await self.config.mongo.async_db.blocks.insert_one(pre_inception_block)

        self.config.LatestBlock = MagicMock()
        self.config.LatestBlock.block = MagicMock()
        self.config.LatestBlock.block.index = CHAIN.CHECK_KEL_OUTPUT_ROUTING_FORK + 100

        wallet1_inception_pubkey = (
            "02850674626716f3d511d51d43824057f45348154735318388d51a4d436709b83d"
        )
        # Wrong destination: wallet 1's own inception address instead of the latest
        wrong_destination = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
        wallet1_inception_address = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"

        spending_txn = Transaction(
            txn_time=1739296100,
            transaction_signature="wallet1_spending_txn_id_bad",
            public_key=wallet1_inception_pubkey,
            fee=0.0,
            txn_hash="wallet1_spending_hash_bad",
            inputs=[{"id": "wallet2_funding_txn_id"}],
            outputs=[{"to": wrong_destination, "value": 10.0}],
            version=7,
            prerotated_key_hash="",
            twice_prerotated_key_hash="",
            # Set public_key_hash so is_new_key_log_entry resolves correctly
            public_key_hash=wallet1_inception_address,
            prev_public_key_hash="",
        )

        with self.assertRaises(DoesNotSpendEntirelyToPrerotatedKeyHashException):
            await spending_txn.verify_kel_output_rules()


# ---------------------------------------------------------------------------
# Unit tests for KeyEvent synchronous validation methods
# ---------------------------------------------------------------------------


class TestKeyEventInit(unittest.TestCase):
    """Test KeyEvent.__init__ raises on invalid txn."""

    def test_init_raises_on_none_txn(self):
        from yadacoin.core.keyeventlog import (
            KeyEvent,
            MissingKeyEventParameterException,
        )

        with self.assertRaises(MissingKeyEventParameterException):
            KeyEvent(txn=None)

    def test_init_raises_on_non_transaction_txn(self):
        from yadacoin.core.keyeventlog import (
            KeyEvent,
            MissingKeyEventParameterException,
        )

        with self.assertRaises(MissingKeyEventParameterException):
            KeyEvent(txn="not a transaction")


class TestKeyEventVerifyFields(unittest.TestCase):
    """Test KeyEvent.verify_fields raises on invalid hashes."""

    def _make_key_event(
        self,
        twice_prerotated="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        prerotated="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        public_key_hash="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        prev_public_key_hash="",
    ):
        from unittest.mock import MagicMock

        from yadacoin.core.config import Config
        from yadacoin.core.keyeventlog import (
            KeyEvent,
            KeyEventChainStatus,
            KeyEventFlag,
        )
        from yadacoin.core.transaction import Transaction

        txn = MagicMock(spec=Transaction)
        txn.twice_prerotated_key_hash = twice_prerotated
        txn.prerotated_key_hash = prerotated
        txn.public_key_hash = public_key_hash
        txn.prev_public_key_hash = prev_public_key_hash

        ke = KeyEvent.__new__(KeyEvent)
        ke.txn = txn
        ke.flag = KeyEventFlag.INCEPTION
        ke.status = KeyEventChainStatus.MEMPOOL
        ke.config = Config()
        return ke

    def test_verify_fields_invalid_twice_prerotated(self):
        from yadacoin.core.keyeventlog import KeyEventException

        ke = self._make_key_event(twice_prerotated="bad")
        with self.assertRaises(KeyEventException) as ctx:
            ke.verify_fields()
        self.assertIn("twice_prerotated_key_hash", str(ctx.exception))

    def test_verify_fields_invalid_prerotated(self):
        from yadacoin.core.keyeventlog import KeyEventException

        ke = self._make_key_event(prerotated="bad")
        with self.assertRaises(KeyEventException) as ctx:
            ke.verify_fields()
        self.assertIn("prerotated_key_hash", str(ctx.exception))

    def test_verify_fields_invalid_public_key_hash(self):
        from yadacoin.core.keyeventlog import KeyEventException

        ke = self._make_key_event(public_key_hash="bad")
        with self.assertRaises(KeyEventException) as ctx:
            ke.verify_fields()
        self.assertIn("public_key_hash", str(ctx.exception))

    def test_verify_fields_invalid_prev_public_key_hash_when_required(self):
        from yadacoin.core.keyeventlog import KeyEventException

        ke = self._make_key_event(prev_public_key_hash="bad")
        with self.assertRaises(KeyEventException) as ctx:
            ke.verify_fields(prev_public_key_hash_required=True)
        self.assertIn("prev_public_key_hash", str(ctx.exception))


class TestKeyEventVerifyInception(unittest.TestCase):
    """Test KeyEvent.verify_inception exception branches."""

    def _make_ke(
        self,
        flag=None,
        status=None,
        outputs=None,
        prerotated_key_hash="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        relationship="",
    ):
        from unittest.mock import MagicMock

        from yadacoin.core.config import Config
        from yadacoin.core.keyeventlog import (
            KeyEvent,
            KeyEventChainStatus,
            KeyEventFlag,
        )
        from yadacoin.core.transaction import Transaction

        if flag is None:
            from yadacoin.core.keyeventlog import KeyEventFlag

            flag = KeyEventFlag.INCEPTION
        if status is None:
            from yadacoin.core.keyeventlog import KeyEventChainStatus

            status = KeyEventChainStatus.MEMPOOL

        if outputs is None:
            out = MagicMock()
            out.to = prerotated_key_hash
            outputs = [out]

        txn = MagicMock(spec=Transaction)
        txn.twice_prerotated_key_hash = "1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"
        txn.prerotated_key_hash = prerotated_key_hash
        txn.public_key_hash = "1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"
        txn.prev_public_key_hash = ""
        txn.outputs = outputs
        txn.relationship = relationship

        ke = KeyEvent.__new__(KeyEvent)
        ke.txn = txn
        ke.flag = flag
        ke.status = status
        ke.config = Config()
        return ke

    def test_verify_inception_multiple_outputs_raises(self):
        from unittest.mock import MagicMock

        from yadacoin.core.keyeventlog import KeyEventSingleOutputException

        ke = self._make_ke(outputs=[MagicMock(), MagicMock()])
        with self.assertRaises(KeyEventSingleOutputException):
            ke.verify_inception()

    def test_verify_inception_wrong_output_address_raises(self):
        from unittest.mock import MagicMock

        from yadacoin.core.keyeventlog import KeyEventPrerotatedKeyHashException

        out = MagicMock()
        out.to = "wrongaddr"
        ke = self._make_ke(
            outputs=[out], prerotated_key_hash="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"
        )
        with self.assertRaises(KeyEventPrerotatedKeyHashException):
            ke.verify_inception()

    def test_verify_inception_non_empty_relationship_raises(self):
        from yadacoin.core.keyeventlog import KeyEventTransactionRelationshipException

        ke = self._make_ke(relationship="some_data")
        with self.assertRaises(KeyEventTransactionRelationshipException):
            ke.verify_inception()

    def test_verify_inception_onchain_with_mempool_status_raises(self):
        from yadacoin.core.keyeventlog import KeyEventChainStatus, KeyEventException

        ke = self._make_ke(status=KeyEventChainStatus.MEMPOOL)
        with self.assertRaises(KeyEventException) as ctx:
            ke.verify_inception(onchain=True)
        self.assertIn("Invalid status", str(ctx.exception))


class TestKeyEventVerifyUnconfirmed(unittest.TestCase):
    """Test KeyEvent.verify_unconfirmed exception branches."""

    def _make_ke(
        self,
        status=None,
        outputs=None,
        prerotated_key_hash="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        relationship="no_rel",
    ):
        from unittest.mock import MagicMock

        from yadacoin.core.config import Config
        from yadacoin.core.keyeventlog import (
            KeyEvent,
            KeyEventChainStatus,
            KeyEventFlag,
        )
        from yadacoin.core.transaction import Transaction

        if status is None:
            status = KeyEventChainStatus.MEMPOOL

        if outputs is None:
            out = MagicMock()
            out.to = prerotated_key_hash
            outputs = [out]

        txn = MagicMock(spec=Transaction)
        txn.twice_prerotated_key_hash = "1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"
        txn.prerotated_key_hash = prerotated_key_hash
        txn.public_key_hash = "1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"
        txn.prev_public_key_hash = "1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"
        txn.outputs = outputs
        txn.relationship = relationship

        ke = KeyEvent.__new__(KeyEvent)
        ke.txn = txn
        ke.flag = KeyEventFlag.UNCONFIRMED
        ke.status = status
        ke.config = Config()
        return ke

    def test_verify_unconfirmed_looks_like_confirming_raises(self):
        """No relationship + 1 output to prerotated_key_hash = invalid unconfirmed."""
        from yadacoin.core.keyeventlog import KeyEventException

        ke = self._make_ke(relationship="")
        with self.assertRaises(KeyEventException) as ctx:
            ke.verify_unconfirmed()
        self.assertIn("invalid relationship", str(ctx.exception))

    def test_verify_unconfirmed_wrong_status_raises(self):
        from yadacoin.core.keyeventlog import KeyEventChainStatus, KeyEventException

        ke = self._make_ke(status=KeyEventChainStatus.ONCHAIN, relationship="data")
        with self.assertRaises(KeyEventException) as ctx:
            ke.verify_unconfirmed()
        self.assertIn("Invalid status", str(ctx.exception))


class TestKeyEventVerifyConfirming(unittest.TestCase):
    """Test KeyEvent.verify_confirming exception branches."""

    def _make_ke(
        self,
        status=None,
        outputs=None,
        prerotated_key_hash="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
        relationship="",
        prev_public_key_hash="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR",
    ):
        from unittest.mock import MagicMock

        from yadacoin.core.config import Config
        from yadacoin.core.keyeventlog import (
            KeyEvent,
            KeyEventChainStatus,
            KeyEventFlag,
        )
        from yadacoin.core.transaction import Transaction

        if status is None:
            status = KeyEventChainStatus.MEMPOOL

        if outputs is None:
            out = MagicMock()
            out.to = prerotated_key_hash
            outputs = [out]

        txn = MagicMock(spec=Transaction)
        txn.twice_prerotated_key_hash = "1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"
        txn.prerotated_key_hash = prerotated_key_hash
        txn.public_key_hash = "1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"
        txn.prev_public_key_hash = prev_public_key_hash
        txn.outputs = outputs
        txn.relationship = relationship

        ke = KeyEvent.__new__(KeyEvent)
        ke.txn = txn
        ke.flag = KeyEventFlag.CONFIRMING
        ke.status = status
        ke.config = Config()
        return ke

    def _make_entire_log(self, last_prerotated="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"):
        from unittest.mock import MagicMock

        last = MagicMock()
        last.prerotated_key_hash = last_prerotated
        return [last]

    def test_verify_confirming_multiple_outputs_raises(self):
        from unittest.mock import MagicMock

        from yadacoin.core.keyeventlog import KeyEventSingleOutputException

        ke = self._make_ke(outputs=[MagicMock(), MagicMock()])
        with self.assertRaises(KeyEventSingleOutputException):
            ke.verify_confirming(entire_log=self._make_entire_log())

    def test_verify_confirming_wrong_output_address_raises(self):
        from unittest.mock import MagicMock

        from yadacoin.core.keyeventlog import KeyEventPrerotatedKeyHashException

        out = MagicMock()
        out.to = "wrongaddr"
        ke = self._make_ke(
            outputs=[out], prerotated_key_hash="1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"
        )
        with self.assertRaises(KeyEventPrerotatedKeyHashException):
            ke.verify_confirming(
                entire_log=self._make_entire_log(last_prerotated="other")
            )

    def test_verify_confirming_non_empty_relationship_raises(self):
        from yadacoin.core.keyeventlog import KeyEventTransactionRelationshipException

        ke = self._make_ke(relationship="data")
        with self.assertRaises(KeyEventTransactionRelationshipException):
            ke.verify_confirming(entire_log=self._make_entire_log())

    def test_verify_confirming_onchain_with_mempool_status_raises(self):
        from yadacoin.core.keyeventlog import KeyEventChainStatus, KeyEventException

        ke = self._make_ke(status=KeyEventChainStatus.MEMPOOL)
        with self.assertRaises(KeyEventException) as ctx:
            ke.verify_confirming(entire_log=self._make_entire_log(), onchain=True)
        self.assertIn("Invalid status", str(ctx.exception))


class TestKELHashCollectionAdd(unittest.TestCase):
    """Test KELHashCollection.add raises on duplicate hashes."""

    def _make_txn(self, twice="", prerotated="", public_key_hash="", prev=""):
        from unittest.mock import MagicMock

        from yadacoin.core.transaction import Transaction

        txn = MagicMock(spec=Transaction)
        txn.twice_prerotated_key_hash = twice
        txn.prerotated_key_hash = prerotated
        txn.public_key_hash = public_key_hash
        txn.prev_public_key_hash = prev
        return txn

    def _make_collection(self):
        from yadacoin.core.keyeventlog import KELHashCollection

        coll = KELHashCollection.__new__(KELHashCollection)
        coll.twice_prerotated_key_hashes = {}
        coll.prerotated_key_hashes = {}
        coll.public_key_hashes = {}
        coll.prev_public_key_hashes = {}
        return coll

    def test_add_duplicate_twice_prerotated_raises(self):
        from yadacoin.core.keyeventlog import KELHashCollectionException

        coll = self._make_collection()
        txn1 = self._make_txn(twice="hash1")
        txn2 = self._make_txn(twice="hash1")
        coll.add(txn1)
        with self.assertRaises(KELHashCollectionException):
            coll.add(txn2)

    def test_add_duplicate_prerotated_raises(self):
        from yadacoin.core.keyeventlog import KELHashCollectionException

        coll = self._make_collection()
        txn1 = self._make_txn(prerotated="hash1")
        txn2 = self._make_txn(prerotated="hash1")
        coll.add(txn1)
        with self.assertRaises(KELHashCollectionException):
            coll.add(txn2)

    def test_add_duplicate_public_key_hash_raises(self):
        from yadacoin.core.keyeventlog import KELHashCollectionException

        coll = self._make_collection()
        txn1 = self._make_txn(public_key_hash="hash1")
        txn2 = self._make_txn(public_key_hash="hash1")
        coll.add(txn1)
        with self.assertRaises(KELHashCollectionException):
            coll.add(txn2)

    def test_add_duplicate_prev_public_key_hash_raises(self):
        from yadacoin.core.keyeventlog import KELHashCollectionException

        coll = self._make_collection()
        txn1 = self._make_txn(prev="hash1")
        txn2 = self._make_txn(prev="hash1")
        coll.add(txn1)
        with self.assertRaises(KELHashCollectionException):
            coll.add(txn2)


class TestKeyEventLogVerifyLinks(unittest.TestCase):
    """Test KeyEventLog.verify_base_and_unconfirmed, verify_unconfirmed_and_confirming,
    and verify_base_and_confirming raise KELException on mismatch."""

    def _make_ke(
        self,
        twice="addr_twice",
        prerotated="addr_prerotated",
        public_key_hash="addr_pkh",
        prev_public_key_hash="addr_prev",
    ):
        from unittest.mock import MagicMock

        from yadacoin.core.keyeventlog import (
            KeyEvent,
            KeyEventChainStatus,
            KeyEventFlag,
        )
        from yadacoin.core.transaction import Transaction

        txn = MagicMock(spec=Transaction)
        txn.twice_prerotated_key_hash = twice
        txn.prerotated_key_hash = prerotated
        txn.public_key_hash = public_key_hash
        txn.prev_public_key_hash = prev_public_key_hash

        ke = KeyEvent.__new__(KeyEvent)
        ke.txn = txn
        ke.flag = KeyEventFlag.INCEPTION
        ke.status = KeyEventChainStatus.MEMPOOL
        return ke

    def _make_kel(self, base=None, unconfirmed=None, confirming=None):
        from yadacoin.core.keyeventlog import KeyEventLog

        kel = KeyEventLog.__new__(KeyEventLog)
        kel.base_key_event = base
        kel.unconfirmed_key_event = unconfirmed
        kel.confirming_key_event = confirming
        return kel

    # --- verify_base_and_unconfirmed ---

    def test_verify_base_and_unconfirmed_twice_mismatch_raises(self):
        from yadacoin.core.keyeventlog import KELException

        base = self._make_ke(twice="WRONG")
        unconfirmed = self._make_ke(prerotated="CORRECT")
        kel = self._make_kel(base=base, unconfirmed=unconfirmed)
        with self.assertRaises(KELException) as ctx:
            kel.verify_base_and_unconfirmed()
        self.assertIn("twice_prerotated_key_hash", str(ctx.exception))

    def test_verify_base_and_unconfirmed_prerotated_mismatch_raises(self):
        from yadacoin.core.keyeventlog import KELException

        # Make twice match, but prerotated mismatch
        base = self._make_ke(twice="SHARED", prerotated="BASE_PKR")
        unconfirmed = self._make_ke(prerotated="SHARED", public_key_hash="WRONG_PKH")
        kel = self._make_kel(base=base, unconfirmed=unconfirmed)
        with self.assertRaises(KELException) as ctx:
            kel.verify_base_and_unconfirmed()
        self.assertIn("prerotated_key_hash", str(ctx.exception))

    def test_verify_base_and_unconfirmed_pkh_mismatch_raises(self):
        from yadacoin.core.keyeventlog import KELException

        # Make twice and prerotated match, but public_key_hash vs prev mismatch
        base = self._make_ke(
            twice="SHARED", prerotated="SHARED_PKR", public_key_hash="BASE_PKH"
        )
        unconfirmed = self._make_ke(
            prerotated="SHARED",
            public_key_hash="SHARED_PKR",
            prev_public_key_hash="WRONG_PREV",
        )
        kel = self._make_kel(base=base, unconfirmed=unconfirmed)
        with self.assertRaises(KELException) as ctx:
            kel.verify_base_and_unconfirmed()
        self.assertIn("public_key_hash", str(ctx.exception))

    # --- verify_unconfirmed_and_confirming ---

    def test_verify_unconfirmed_and_confirming_twice_mismatch_raises(self):
        from yadacoin.core.keyeventlog import KELException

        unconfirmed = self._make_ke(twice="WRONG")
        confirming = self._make_ke(prerotated="CORRECT")
        kel = self._make_kel(unconfirmed=unconfirmed, confirming=confirming)
        with self.assertRaises(KELException) as ctx:
            kel.verify_unconfirmed_and_confirming()
        self.assertIn("twice_prerotated_key_hash", str(ctx.exception))

    def test_verify_unconfirmed_and_confirming_prerotated_mismatch_raises(self):
        from yadacoin.core.keyeventlog import KELException

        unconfirmed = self._make_ke(twice="SHARED", prerotated="WRONG")
        confirming = self._make_ke(prerotated="SHARED", public_key_hash="CORRECT")
        kel = self._make_kel(unconfirmed=unconfirmed, confirming=confirming)
        with self.assertRaises(KELException) as ctx:
            kel.verify_unconfirmed_and_confirming()
        self.assertIn("prerotated_key_hash", str(ctx.exception))

    def test_verify_unconfirmed_and_confirming_pkh_mismatch_raises(self):
        from yadacoin.core.keyeventlog import KELException

        unconfirmed = self._make_ke(
            twice="SHARED", prerotated="SHARED_PKR", public_key_hash="UNC_PKH"
        )
        confirming = self._make_ke(
            prerotated="SHARED",
            public_key_hash="SHARED_PKR",
            prev_public_key_hash="WRONG",
        )
        kel = self._make_kel(unconfirmed=unconfirmed, confirming=confirming)
        with self.assertRaises(KELException) as ctx:
            kel.verify_unconfirmed_and_confirming()
        self.assertIn("public_key_hash", str(ctx.exception))

    # --- verify_base_and_confirming ---

    def test_verify_base_and_confirming_twice_mismatch_raises(self):
        from yadacoin.core.keyeventlog import KELException

        base = self._make_ke(twice="WRONG")
        confirming = self._make_ke(prerotated="CORRECT")
        kel = self._make_kel(base=base, confirming=confirming)
        with self.assertRaises(KELException) as ctx:
            kel.verify_base_and_confirming()
        self.assertIn("twice_prerotated_key_hash", str(ctx.exception))

    def test_verify_base_and_confirming_prerotated_mismatch_raises(self):
        from yadacoin.core.keyeventlog import KELException

        base = self._make_ke(twice="SHARED", prerotated="WRONG")
        confirming = self._make_ke(prerotated="SHARED", public_key_hash="CORRECT")
        kel = self._make_kel(base=base, confirming=confirming)
        with self.assertRaises(KELException) as ctx:
            kel.verify_base_and_confirming()
        self.assertIn("prerotated_key_hash", str(ctx.exception))

    def test_verify_base_and_confirming_pkh_mismatch_raises(self):
        from yadacoin.core.keyeventlog import KELException

        base = self._make_ke(
            twice="SHARED", prerotated="SHARED_PKR", public_key_hash="BASE_PKH"
        )
        confirming = self._make_ke(
            prerotated="SHARED",
            public_key_hash="SHARED_PKR",
            prev_public_key_hash="WRONG",
        )
        kel = self._make_kel(base=base, confirming=confirming)
        with self.assertRaises(KELException) as ctx:
            kel.verify_base_and_confirming()
        self.assertIn("public_key_hash", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)


# ---------------------------------------------------------------------------
# Tests for KeyEvent.verify() missing async branches
# ---------------------------------------------------------------------------

# Real valid Bitcoin P2PKH addresses from block test data
_VALID_ADDR_A = "1HazogSuV2NUdd1Cnebw4RVLN9RS8s86yv"  # public_key_hash
_VALID_ADDR_B = "1LoXtHtuu3qabmrkPam1nfET3kcPHok9AR"  # prerotated_key_hash
_VALID_ADDR_C = "16K746UWNSzbdAAp24B9zcmdxvmpesfyPD"  # twice_prerotated_key_hash
_VALID_PUBKEY = "03cf228062cad517f99df2cb4403c84e1769c8714394dbf0ffca994de72fb0b1c1"

# A minimal transaction dict for the inception of the chain above
_INCEPTION_TXN_DICT = blocks[0]["transactions"][0]  # index 537383, txn[0]

# A second real address chain for inception tests
_VALID_ADDR_PKH2 = "1HZpCG5p3too1LxZi68ZGkUhJUJAZjDqE8"
_VALID_ADDR_PKR2 = "1Kxegt9KhD7i6EJEYvBS5pHZdGwX6BZCar"
_VALID_ADDR_TPKR2 = "1NY91tSJvaFK7BYbGcXeGipoNKoqoXDSex"
_VALID_PUBKEY2 = "02850674626716f3d511d51d43824057f45348154735318388d51a4d436709b83d"


def _make_mock_ke(
    flag=None,
    status=None,
    prev_public_key_hash="",
    relationship="",
    prerotated_key_hash=_VALID_ADDR_B,
    twice_prerotated_key_hash=_VALID_ADDR_C,
    public_key_hash=_VALID_ADDR_A,
    outputs_to=_VALID_ADDR_B,
    public_key=_VALID_PUBKEY,
):
    from unittest.mock import MagicMock

    from yadacoin.core.config import Config
    from yadacoin.core.keyeventlog import KeyEvent, KeyEventChainStatus
    from yadacoin.core.transaction import Transaction

    if status is None:
        status = KeyEventChainStatus.MEMPOOL

    txn = MagicMock(spec=Transaction)
    txn.public_key = public_key
    txn.public_key_hash = public_key_hash
    txn.prev_public_key_hash = prev_public_key_hash
    txn.transaction_signature = "test_sig"
    txn.relationship = relationship
    txn.prerotated_key_hash = prerotated_key_hash
    txn.twice_prerotated_key_hash = twice_prerotated_key_hash
    out = MagicMock()
    out.to = outputs_to
    txn.outputs = [out]

    ke = KeyEvent.__new__(KeyEvent)
    ke.txn = txn
    ke.flag = flag
    ke.status = status
    ke.config = Config()
    return ke


def _make_hash_collection(
    prerotated=None,
    twice_prerotated=None,
    public_key_hashes=None,
    prev_public_key_hashes=None,
):
    from yadacoin.core.keyeventlog import KELHashCollection

    coll = KELHashCollection.__new__(KELHashCollection)
    coll.prerotated_key_hashes = prerotated or {}
    coll.twice_prerotated_key_hashes = twice_prerotated or {}
    coll.public_key_hashes = public_key_hashes or {}
    coll.prev_public_key_hashes = prev_public_key_hashes or {}
    return coll


class TestKeyEventVerifyAsyncBranches(AsyncTestCase):
    """Cover async KeyEvent.verify() missing branches."""

    async def asyncSetUp(self):
        import yadacoin.core.config

        yadacoin.core.config.CONFIG = Config()
        Config().mongo = Mongo()
        Config().network = "regnet"
        self.config = Config()

        class AppLog:
            def warning(self, msg):
                pass

            def info(self, msg):
                pass

        Config().app_log = AppLog()

    async def test_verify_sends_to_past_entry_deletes_and_raises(self):
        """Lines 236-239: sends_to_past_kel_entry returns truthy → delete + raise KELException."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KELException

        ke = _make_mock_ke()

        with patch("yadacoin.core.keyeventlog.P2PKHBitcoinAddress") as mock_btc:
            mock_btc.from_pubkey.return_value = _VALID_ADDR_A
            ke.sends_to_past_kel_entry = AsyncMock(return_value=MagicMock())

            with self.assertRaises(KELException) as ctx:
                await ke.verify()
            self.assertIn("expired", str(ctx.exception))

    async def test_verify_flag_confirming_no_parent_raises_predecessor(self):
        """Line 251, 281-284: flag=CONFIRMING, no onchain/mempool parent → raises KELExceptionPredecessorNotYetInMempool."""
        from unittest.mock import AsyncMock, patch

        from yadacoin.core.keyeventlog import (
            KELExceptionPredecessorNotYetInMempool,
            KeyEventFlag,
        )

        ke = _make_mock_ke(
            flag=KeyEventFlag.CONFIRMING, prev_public_key_hash="PREV_ADDR"
        )

        with patch("yadacoin.core.keyeventlog.P2PKHBitcoinAddress") as mock_btc:
            mock_btc.from_pubkey.return_value = _VALID_ADDR_A
            ke.sends_to_past_kel_entry = AsyncMock(return_value=False)
            ke.get_onchain_parent = AsyncMock(return_value=None)
            ke.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
                return_value=None
            )

            with self.assertRaises(KELExceptionPredecessorNotYetInMempool):
                await ke.verify()

    async def test_verify_confirming_batch_txns_match_returns(self):
        """Lines 269-280: confirming, batch_txns match → return early without raising."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KeyEventFlag

        ke = _make_mock_ke(
            flag=KeyEventFlag.CONFIRMING, prev_public_key_hash="PREV_ADDR"
        )

        batch_txn = MagicMock()
        batch_txn.public_key_hash = "PREV_ADDR"

        with patch("yadacoin.core.keyeventlog.P2PKHBitcoinAddress") as mock_btc:
            mock_btc.from_pubkey.return_value = _VALID_ADDR_A
            ke.sends_to_past_kel_entry = AsyncMock(return_value=False)
            ke.get_onchain_parent = AsyncMock(return_value=None)
            ke.config.mongo.async_db.miner_transactions.find_one = AsyncMock(
                return_value=None
            )

            # Should NOT raise
            await ke.verify(batch_txns=[batch_txn])

    async def test_verify_unconfirmed_no_onchain_parent_raises(self):
        """Lines 285-297: unconfirmed, no onchain parent, no batch → raises KELException."""
        from unittest.mock import AsyncMock, patch

        from yadacoin.core.keyeventlog import KELException, KeyEventFlag

        ke = _make_mock_ke(
            flag=KeyEventFlag.UNCONFIRMED,
            prev_public_key_hash="PREV_ADDR",
            relationship="some_data",
            outputs_to="SOME_ADDR",
        )

        with patch("yadacoin.core.keyeventlog.P2PKHBitcoinAddress") as mock_btc:
            mock_btc.from_pubkey.return_value = _VALID_ADDR_A
            ke.sends_to_past_kel_entry = AsyncMock(return_value=False)
            ke.get_onchain_parent = AsyncMock(return_value=None)

            with self.assertRaises(KELException):
                await ke.verify()

    async def test_verify_unconfirmed_batch_txns_match_returns(self):
        """Lines 285-296: unconfirmed, batch_txns match → return early."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KeyEventFlag

        ke = _make_mock_ke(
            flag=KeyEventFlag.UNCONFIRMED,
            prev_public_key_hash="PREV_ADDR",
            relationship="some_data",
            outputs_to="SOME_ADDR",
        )

        batch_txn = MagicMock()
        batch_txn.public_key_hash = "PREV_ADDR"

        with patch("yadacoin.core.keyeventlog.P2PKHBitcoinAddress") as mock_btc:
            mock_btc.from_pubkey.return_value = _VALID_ADDR_A
            ke.sends_to_past_kel_entry = AsyncMock(return_value=False)
            ke.get_onchain_parent = AsyncMock(return_value=None)

            # Should NOT raise
            await ke.verify(batch_txns=[batch_txn])

    async def test_verify_already_onchain_output_mismatch_raises(self):
        """Lines 303-308: is_already_onchain()=True, output mismatch → KELException."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KELException, KeyEventLog

        ke = _make_mock_ke(outputs_to="WRONG_ADDR")
        ke.txn.is_already_onchain = AsyncMock(return_value=True)

        last_entry = MagicMock()
        last_entry.prerotated_key_hash = "CORRECT_ADDR"

        with patch("yadacoin.core.keyeventlog.P2PKHBitcoinAddress") as mock_btc:
            mock_btc.from_pubkey.return_value = _VALID_ADDR_A
            ke.sends_to_past_kel_entry = AsyncMock(return_value=False)

            with patch.object(
                KeyEventLog,
                "build_from_public_key",
                new=AsyncMock(return_value=[last_entry]),
            ):
                with self.assertRaises(KELException) as ctx:
                    await ke.verify()
                self.assertIn("already onchain", str(ctx.exception))


# ---------------------------------------------------------------------------
# Tests for sends_to_past_kel_entry and get_onchain_parent using real DB
# ---------------------------------------------------------------------------


class TestKeyEventSendsAndParent(AsyncTestCase):
    """Cover sends_to_past_kel_entry (lines 330-340) and get_onchain_parent (lines 412-413) using mocks."""

    async def asyncSetUp(self):
        import yadacoin.core.config

        yadacoin.core.config.CONFIG = Config()
        Config().mongo = Mongo()
        Config().network = "regnet"
        self.config = Config()

        class AppLog:
            def warning(self, msg):
                pass

            def info(self, msg):
                pass

        Config().app_log = AppLog()

    def _make_cursor(self, docs):
        from unittest.mock import AsyncMock, MagicMock

        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=docs)
        return cursor

    async def test_sends_to_past_kel_entry_returns_key_event(self):
        """Lines 330-340: aggregate returns a block txn → returns a KeyEvent."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KeyEvent

        block_doc = {"transactions": dict(_INCEPTION_TXN_DICT)}

        ke = _make_mock_ke(outputs_to=_VALID_ADDR_A)

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[block_doc])

        with patch("yadacoin.core.keyeventlog.Config") as mock_config_cls:
            mock_cfg = MagicMock()
            mock_config_cls.return_value = mock_cfg
            mock_cfg.mongo.async_db.blocks.aggregate.return_value = mock_cursor
            result = await ke.sends_to_past_kel_entry()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, KeyEvent)

    async def test_get_onchain_parent_returns_key_event(self):
        """get_onchain_parent: aggregate returns a block txn → returns dict with KeyEvent."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KeyEvent

        block_doc = {"transactions": dict(_INCEPTION_TXN_DICT)}

        ke = _make_mock_ke(
            public_key_hash=_VALID_ADDR_PKR2,
            prerotated_key_hash=_VALID_ADDR_TPKR2,
        )

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[block_doc])

        with patch("yadacoin.core.keyeventlog.Config") as mock_config_cls:
            mock_cfg = MagicMock()
            mock_config_cls.return_value = mock_cfg
            mock_cfg.mongo.async_db.blocks.aggregate.return_value = mock_cursor
            result = await ke.get_onchain_parent()

        self.assertIsNotNone(result)
        self.assertIn("key_event", result)
        self.assertIsInstance(result["key_event"], KeyEvent)

    async def test_get_onchain_child_returns_key_event(self):
        """Lines 412-413: get_onchain_child aggregate returns a block txn → returns KeyEvent."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KeyEvent

        block_doc = {"transactions": dict(_INCEPTION_TXN_DICT)}

        ke = _make_mock_ke(
            public_key_hash=_VALID_ADDR_A,
            prerotated_key_hash=_VALID_ADDR_B,
            twice_prerotated_key_hash=_VALID_ADDR_C,
        )

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[block_doc])

        with patch("yadacoin.core.keyeventlog.Config") as mock_config_cls:
            mock_cfg = MagicMock()
            mock_config_cls.return_value = mock_cfg
            mock_cfg.mongo.async_db.blocks.aggregate.return_value = mock_cursor
            result = await ke.get_onchain_child()

        self.assertIsNotNone(result)
        self.assertIsInstance(result, KeyEvent)


# ---------------------------------------------------------------------------
# Tests for KELHashCollection.init_async with verify_only=False (lines 440-445)
# ---------------------------------------------------------------------------


class TestKELHashCollectionInitNotVerifyOnly(AsyncTestCase):
    """Cover KELHashCollection.init_async with verify_only=False."""

    async def asyncSetUp(self):
        import yadacoin.core.config

        yadacoin.core.config.CONFIG = Config()
        Config().mongo = Mongo()
        Config().network = "regnet"
        self.config = Config()

        class AppLog:
            def warning(self, msg):
                pass

            def info(self, msg):
                pass

        Config().app_log = AppLog()

    async def test_init_async_not_verify_only_removes_duplicate(self):
        """Lines 440-445: duplicate transaction in block → removed from block.transactions, delete_one called."""
        from unittest.mock import MagicMock

        from yadacoin.core.keyeventlog import KELHashCollection
        from yadacoin.core.transaction import Transaction

        # Create two transactions with the same twice_prerotated_key_hash (causes duplicate exception)
        txn1 = MagicMock(spec=Transaction)
        txn1.twice_prerotated_key_hash = "SAME_HASH"
        txn1.prerotated_key_hash = "PKR1"
        txn1.public_key_hash = "PKH1"
        txn1.prev_public_key_hash = ""
        txn1.transaction_signature = "sig1"

        txn2 = MagicMock(spec=Transaction)
        txn2.twice_prerotated_key_hash = "SAME_HASH"  # duplicate
        txn2.prerotated_key_hash = "PKR2"
        txn2.public_key_hash = "PKH2"
        txn2.prev_public_key_hash = ""
        txn2.transaction_signature = "sig2"

        block = MagicMock()
        block.transactions = [txn1, txn2]

        result = await KELHashCollection.init_async(block, verify_only=False)

        # txn2 should have been removed from block.transactions
        self.assertNotIn(txn2, block.transactions)

    async def test_init_async_verify_only_raises_on_duplicate(self):
        """verify_only=True path: raises KELHashCollectionException on duplicate."""
        from unittest.mock import MagicMock

        from yadacoin.core.keyeventlog import (
            KELHashCollection,
            KELHashCollectionException,
        )
        from yadacoin.core.transaction import Transaction

        txn1 = MagicMock(spec=Transaction)
        txn1.twice_prerotated_key_hash = "SAME_HASH"
        txn1.prerotated_key_hash = ""
        txn1.public_key_hash = ""
        txn1.prev_public_key_hash = ""
        txn1.transaction_signature = "sig1"

        txn2 = MagicMock(spec=Transaction)
        txn2.twice_prerotated_key_hash = "SAME_HASH"
        txn2.prerotated_key_hash = ""
        txn2.public_key_hash = ""
        txn2.prev_public_key_hash = ""
        txn2.transaction_signature = "sig2"

        block = MagicMock()
        block.transactions = [txn1, txn2]

        with self.assertRaises(KELHashCollectionException):
            await KELHashCollection.init_async(block, verify_only=True)


# ---------------------------------------------------------------------------
# Tests for KeyEventLog.init_async missing branches
# ---------------------------------------------------------------------------


class TestKeyEventLogInitAsyncBranches(AsyncTestCase):
    """Cover missing branches in KeyEventLog.init_async."""

    async def asyncSetUp(self):
        import yadacoin.core.config

        yadacoin.core.config.CONFIG = Config()
        Config().mongo = Mongo()
        Config().network = "regnet"
        self.config = Config()

        class AppLog:
            def warning(self, msg):
                pass

            def info(self, msg):
                pass

        Config().app_log = AppLog()

    async def test_init_async_onchain_child_mismatch_raises(self):
        """Lines 503-511: onchain_child found but hashes mismatch → FatalKeyEventException."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import (
            FatalKeyEventException,
            KeyEventChainStatus,
            KeyEventFlag,
            KeyEventLog,
        )

        # Parent key event
        parent_ke = _make_mock_ke(
            flag=KeyEventFlag.INCEPTION,
            status=KeyEventChainStatus.ONCHAIN,
            public_key_hash="PARENT_PKH",
        )
        # Onchain child (existing) with specific hashes
        child_ke = _make_mock_ke(
            twice_prerotated_key_hash="CHILD_TWICE",
            prerotated_key_hash="CHILD_PKR",
            public_key_hash="CHILD_PKH",
        )
        parent_ke.get_onchain_child = AsyncMock(return_value=child_ke)

        # New key event that claims to be next but has WRONG hashes
        ke = _make_mock_ke(
            prev_public_key_hash="PARENT_PKH",
            twice_prerotated_key_hash="WRONG_TWICE",  # mismatch with child
            prerotated_key_hash="WRONG_PKR",
            public_key_hash="WRONG_PKH",
        )
        ke.get_onchain_parent = AsyncMock(return_value={"key_event": parent_ke})
        parent_ke.txn.public_key_hash = "PARENT_PKH"

        hash_collection = _make_hash_collection()

        with patch.object(
            KeyEventLog,
            "build_from_public_key",
            new=AsyncMock(return_value=[MagicMock(prerotated_key_hash="SOME_PKR")]),
        ):
            with self.assertRaises(FatalKeyEventException) as ctx:
                await KeyEventLog.init_async(ke, hash_collection)
            self.assertIn("onchain child", str(ctx.exception))

    async def test_init_async_no_confirming_in_hash_collection_raises(self):
        """FatalKeyEventException: unconfirmed key event but no confirming entry in hash_collection."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import (
            FatalKeyEventException,
            KeyEventChainStatus,
            KeyEventFlag,
            KeyEventLog,
        )

        parent_ke = _make_mock_ke(
            flag=KeyEventFlag.INCEPTION,
            status=KeyEventChainStatus.ONCHAIN,
            public_key_hash="PARENT_PKH",
            prerotated_key_hash=_VALID_ADDR_B,
            twice_prerotated_key_hash="UNCONF_PKR",
        )
        parent_ke.get_onchain_child = AsyncMock(return_value=None)
        parent_ke.txn.public_key_hash = "PARENT_PKH"

        # Key event that looks like unconfirmed (has relationship)
        ke = _make_mock_ke(
            prev_public_key_hash="PARENT_PKH",
            relationship="some_relationship_data",
            outputs_to="SOMEWHERE_ELSE",
            twice_prerotated_key_hash="UNCONF_TWICE",
        )
        ke.txn.relationship = "some_relationship_data"
        ke.get_onchain_parent = AsyncMock(return_value={"key_event": parent_ke})
        ke.sends_to_past_kel_entry = AsyncMock(return_value=False)

        # hash_collection does NOT have the confirming key event (UNCONF_TWICE not in prerotated_key_hashes)
        hash_collection = _make_hash_collection()

        entire_log_entry = MagicMock()
        entire_log_entry.prerotated_key_hash = "SOME_PKR"

        with patch.object(
            KeyEventLog,
            "build_from_public_key",
            new=AsyncMock(return_value=[entire_log_entry]),
        ):
            with self.assertRaises(FatalKeyEventException) as ctx:
                await KeyEventLog.init_async(ke, hash_collection)
            self.assertIn("confirming key event", str(ctx.exception))

    async def test_init_async_unconfirmed_sends_to_past_entry_raises(self):
        """Line 552: unconfirmed key event where sends_to_past_kel_entry is truthy → FatalKeyEventException."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import (
            FatalKeyEventException,
            KeyEventChainStatus,
            KeyEventFlag,
            KeyEventLog,
        )

        parent_ke = _make_mock_ke(
            flag=KeyEventFlag.INCEPTION,
            status=KeyEventChainStatus.ONCHAIN,
            public_key_hash="PARENT_PKH",
        )
        parent_ke.get_onchain_child = AsyncMock(return_value=None)
        parent_ke.txn.public_key_hash = "PARENT_PKH"

        # Unconfirmed key event (has relationship → not confirming)
        ke = _make_mock_ke(
            prev_public_key_hash="PARENT_PKH",
            relationship="some_data",
            outputs_to="SOMEWHERE_ELSE",
        )
        ke.txn.relationship = "some_data"
        ke.get_onchain_parent = AsyncMock(return_value={"key_event": parent_ke})
        # sends_to_past_kel_entry returns truthy → should raise
        ke.sends_to_past_kel_entry = AsyncMock(return_value=MagicMock())

        hash_collection = _make_hash_collection()
        entire_log_entry = MagicMock()
        entire_log_entry.prerotated_key_hash = "SOME_PKR"

        with patch.object(
            KeyEventLog,
            "build_from_public_key",
            new=AsyncMock(return_value=[entire_log_entry]),
        ):
            with self.assertRaises(FatalKeyEventException) as ctx:
                await KeyEventLog.init_async(ke, hash_collection)
            self.assertIn("sends to past key event", str(ctx.exception))

    async def test_init_async_step2_inception(self):
        """Lines 595-596, 657: no onchain parent, no hash_collection conflicts, no prev → inception scenario."""
        from unittest.mock import AsyncMock, patch

        from yadacoin.core.keyeventlog import (
            KeyEventChainStatus,
            KeyEventFlag,
            KeyEventLog,
        )

        # Inception key event with valid addresses for verify_inception
        ke = _make_mock_ke(
            status=KeyEventChainStatus.MEMPOOL,
            twice_prerotated_key_hash=_VALID_ADDR_C,
            prerotated_key_hash=_VALID_ADDR_B,
            public_key_hash=_VALID_ADDR_A,
            prev_public_key_hash="",
            relationship="",
            outputs_to=_VALID_ADDR_B,  # output goes to prerotated_key_hash
        )
        ke.get_onchain_parent = AsyncMock(return_value=None)

        # Empty hash_collection → no conflicts
        hash_collection = _make_hash_collection()

        with patch.object(
            KeyEventLog,
            "build_from_public_key",
            new=AsyncMock(return_value=[]),
        ):
            kel = await KeyEventLog.init_async(ke, hash_collection)

        self.assertIsNotNone(kel.base_key_event)
        self.assertEqual(kel.base_key_event.flag, KeyEventFlag.INCEPTION)

    async def test_init_async_step2_grandparent_in_hash_collection_raises(self):
        """Line 605: step 2.2 where public_key_hash is in twice_prerotated_key_hashes → KELException."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KELException, KeyEventLog

        ke = _make_mock_ke(
            public_key_hash="ADDR_PKH",
            prerotated_key_hash="ADDR_PKR",
            twice_prerotated_key_hash="ADDR_TPKR",
            prev_public_key_hash="",  # no prev
        )
        ke.get_onchain_parent = AsyncMock(return_value=None)

        # public_key_hash IS in twice_prerotated_key_hashes → grandparent collision
        hash_collection = _make_hash_collection(
            twice_prerotated={"ADDR_PKH": MagicMock()},
            prerotated={"ADDR_PKR": MagicMock()},  # prerotated also there → step 2.2
        )

        with patch.object(
            KeyEventLog,
            "build_from_public_key",
            new=AsyncMock(return_value=[MagicMock()]),
        ):
            with self.assertRaises(KELException) as ctx:
                await KeyEventLog.init_async(ke, hash_collection)
            self.assertIn("cannot have inception", str(ctx.exception))

    async def test_init_async_step2_invalid_txn_raises(self):
        """Line 614: step 2.2 with txn that has relationship → KELException 'No onchain key event'."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KELException, KeyEventLog

        # txn with relationship (looks unconfirmed, not confirming)
        ke = _make_mock_ke(
            public_key_hash="ADDR_PKH",
            prerotated_key_hash="ADDR_PKR",
            twice_prerotated_key_hash="ADDR_TPKR",
            prev_public_key_hash="",
            relationship="some_relationship",
            outputs_to="ADDR_PKR",
        )
        ke.get_onchain_parent = AsyncMock(return_value=None)

        # Step 2.2: public_key_hash IS in prerotated_key_hashes but NOT in twice_prerotated_key_hashes
        # → goes to step 2.2 else branch
        hash_collection = _make_hash_collection(
            prerotated={"ADDR_PKH": MagicMock()},
            twice_prerotated={},
        )

        with patch.object(
            KeyEventLog,
            "build_from_public_key",
            new=AsyncMock(return_value=[MagicMock()]),
        ):
            with self.assertRaises(KELException) as ctx:
                await KeyEventLog.init_async(ke, hash_collection)
            self.assertIn("No onchain key event", str(ctx.exception))

    async def test_init_async_step2_no_unconfirmed_in_hash_collection_raises(self):
        """Line 633: step 2.2 confirming txn but no unconfirmed in hash_collection → FatalKeyEventException."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import FatalKeyEventException, KeyEventLog

        # A valid confirming txn: no relationship, 1 output to prerotated_key_hash
        ke = _make_mock_ke(
            public_key_hash="ADDR_PKH",
            prerotated_key_hash="ADDR_PKR",
            twice_prerotated_key_hash="ADDR_TPKR",
            prev_public_key_hash="",
            relationship="",
            outputs_to="ADDR_PKR",
        )
        ke.get_onchain_parent = AsyncMock(return_value=None)

        # Step 2.2: public_key_hash in prerotated_key_hashes → confirms step 2.2
        # prerotated_key_hash NOT in twice_prerotated_key_hashes → no unconfirmed found
        hash_collection = _make_hash_collection(
            prerotated={"ADDR_PKH": MagicMock()},
            twice_prerotated={},  # ADDR_PKR not here → no unconfirmed
        )

        with patch.object(
            KeyEventLog,
            "build_from_public_key",
            new=AsyncMock(return_value=[MagicMock()]),
        ):
            with self.assertRaises(FatalKeyEventException) as ctx:
                await KeyEventLog.init_async(ke, hash_collection)
            self.assertIn("unconfirmed key event", str(ctx.exception))

    async def test_init_async_step2_no_onchain_parent_for_unconfirmed_raises(self):
        """Line 646: step 2.2 unconfirmed found but get_onchain_parent returns None → KELException."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyeventlog import KELException, KeyEventLog
        from yadacoin.core.transaction import Transaction

        # A valid confirming txn
        ke = _make_mock_ke(
            public_key_hash="ADDR_PKH",
            prerotated_key_hash="ADDR_PKR",
            twice_prerotated_key_hash="ADDR_TPKR",
            prev_public_key_hash="",
            relationship="",
            outputs_to="ADDR_PKR",
        )
        ke.get_onchain_parent = AsyncMock(return_value=None)

        # Unconfirmed txn mock
        unconf_txn = MagicMock(spec=Transaction)
        unconf_txn.twice_prerotated_key_hash = "UNCONF_TWICE"
        unconf_txn.prerotated_key_hash = (
            "ADDR_PKR"  # matches ke.txn.prerotated_key_hash
        )
        unconf_txn.public_key_hash = "ADDR_PKH"
        unconf_txn.prev_public_key_hash = "SOME_PREV"
        unconf_txn.relationship = "some_rel"
        unconf_txn.transaction_signature = "unconf_sig"
        out = MagicMock()
        out.to = "SOME_OTHER"
        unconf_txn.outputs = [out]

        # Step 2.2: prerotated_key_hash IS in twice_prerotated_key_hashes → unconfirmed found
        # But get_onchain_parent for unconfirmed returns None
        hash_collection = _make_hash_collection(
            prerotated={"ADDR_PKH": MagicMock()},
            twice_prerotated={"ADDR_PKR": unconf_txn},
        )

        from yadacoin.core.keyeventlog import (
            KeyEvent,
            KeyEventChainStatus,
            KeyEventFlag,
        )

        unconf_ke = KeyEvent.__new__(KeyEvent)
        unconf_ke.txn = unconf_txn
        unconf_ke.flag = KeyEventFlag.UNCONFIRMED
        unconf_ke.status = KeyEventChainStatus.MEMPOOL
        unconf_ke.config = Config()
        unconf_ke.get_onchain_parent = AsyncMock(return_value=None)

        with patch(
            "yadacoin.core.keyeventlog.KeyEvent",
            side_effect=lambda txn, flag, status: unconf_ke,
        ):
            with patch.object(
                KeyEventLog,
                "build_from_public_key",
                new=AsyncMock(return_value=[MagicMock()]),
            ):
                with self.assertRaises(KELException) as ctx:
                    await KeyEventLog.init_async(ke, hash_collection)
                self.assertIn("No onchain key event", str(ctx.exception))

    async def test_init_async_invalid_scenario_raises(self):
        """Line 724: KEL that doesn't match any of the 5 valid scenarios → KELException('Invalid KEL scenario')."""
        from yadacoin.core.keyeventlog import (
            KELException,
            KeyEventChainStatus,
            KeyEventFlag,
            KeyEventLog,
        )

        # Manually construct a KeyEventLog with an invalid state
        # (e.g., base is CONFIRMING + MEMPOOL with no unconfirmed, which is not scenario 3)
        kel = KeyEventLog.__new__(KeyEventLog)
        kel.config = Config()
        kel.base_key_event = _make_mock_ke(
            flag=KeyEventFlag.CONFIRMING,
            status=KeyEventChainStatus.MEMPOOL,  # invalid: confirming base should be ONCHAIN
        )
        kel.unconfirmed_key_event = None
        kel.confirming_key_event = None  # no confirming

        # Call verify_links — it won't help here. We need to hit the else branch of scenario checks.
        # The simplest way: call init_async with a setup that falls through all 5 scenarios.
        # We do this by directly testing the else branch logic:
        # Build a KEL where base is CONFIRMING+MEMPOOL (not ONCHAIN) and no confirming → invalid.
        from unittest.mock import AsyncMock, MagicMock, patch

        parent_ke = _make_mock_ke(
            flag=KeyEventFlag.CONFIRMING,
            status=KeyEventChainStatus.MEMPOOL,  # MEMPOOL base → invalid
            public_key_hash="PARENT_PKH",
        )
        parent_ke.get_onchain_child = AsyncMock(return_value=None)
        parent_ke.txn.public_key_hash = "PARENT_PKH"

        # A confirming ke (no relationship, 1 output to prerotated)
        ke = _make_mock_ke(
            prev_public_key_hash="PARENT_PKH",
            relationship="",
            outputs_to=_VALID_ADDR_B,
            prerotated_key_hash=_VALID_ADDR_B,
        )
        ke.get_onchain_parent = AsyncMock(return_value={"key_event": parent_ke})

        hash_collection = _make_hash_collection()

        with patch.object(
            KeyEventLog,
            "build_from_public_key",
            new=AsyncMock(return_value=[MagicMock(prerotated_key_hash=_VALID_ADDR_B)]),
        ):
            with self.assertRaises(KELException) as ctx:
                await KeyEventLog.init_async(ke, hash_collection)
            self.assertIn("Invalid KEL scenario", str(ctx.exception))


# ---------------------------------------------------------------------------
# Tests for KeyEventLog.build_from_public_key missing branches
# ---------------------------------------------------------------------------

_UNSET = object()  # sentinel for "argument not provided"


class TestBuildFromPublicKeyBranches(AsyncTestCase):
    """Cover missing branches in KeyEventLog.build_from_public_key using module-level Config mock."""

    async def asyncSetUp(self):
        pass

    def _make_cursor(self, docs):
        """Return a mock aggregate cursor whose to_list returns docs."""
        from unittest.mock import AsyncMock, MagicMock

        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=docs)
        return cursor

    def _setup_mock_config(
        self,
        mock_config_cls,
        aggregate_side_effect=None,
        aggregate_return=None,
        find_one_return=_UNSET,
        find_one_side_effect=None,
    ):
        """Configure a mock Config with controllable DB behavior."""
        from unittest.mock import AsyncMock, MagicMock

        mock_cfg = MagicMock()
        mock_config_cls.return_value = mock_cfg

        if aggregate_side_effect is not None:
            mock_cfg.mongo.async_db.blocks.aggregate.side_effect = aggregate_side_effect
        elif aggregate_return is not None:
            mock_cfg.mongo.async_db.blocks.aggregate.return_value = aggregate_return

        if find_one_side_effect is not None:
            mock_cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
                side_effect=find_one_side_effect
            )
        elif find_one_return is not _UNSET:
            mock_cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
                return_value=find_one_return
            )

        return mock_cfg

    async def test_build_onchain_only_no_blocks_returns_empty(self):
        """Line 863: onchain_only=True, no blocks → if onchain_only: break → []."""
        from unittest.mock import patch

        from yadacoin.core.keyeventlog import KeyEventLog

        with patch("yadacoin.core.keyeventlog.Config") as mock_config_cls:
            self._setup_mock_config(
                mock_config_cls, aggregate_return=self._make_cursor([])
            )
            result = await KeyEventLog.build_from_public_key(
                _VALID_PUBKEY, onchain_only=True
            )

        self.assertEqual(result, [])

    async def test_build_no_blocks_no_mempool_returns_empty(self):
        """Lines 882-883: no blocks and no mempool → else:break → returns []."""
        from unittest.mock import patch

        from yadacoin.core.keyeventlog import KeyEventLog

        with patch("yadacoin.core.keyeventlog.Config") as mock_config_cls:
            self._setup_mock_config(
                mock_config_cls,
                aggregate_return=self._make_cursor([]),
                find_one_return=None,
            )
            result = await KeyEventLog.build_from_public_key(_VALID_PUBKEY)

        self.assertEqual(result, [])

    async def test_build_mempool_inception_found(self):
        """Lines 876-880: no blocks, mempool has inception txn → returns [inception_txn]."""
        from unittest.mock import patch

        from yadacoin.core.keyeventlog import KeyEventLog

        call_count = [0]

        async def find_one_side_effect(query):
            call_count[0] += 1
            # First call: backward walk finds inception in mempool
            # Second call: forward walk finds no next entry → break
            return dict(_INCEPTION_TXN_DICT) if call_count[0] == 1 else None

        agg_call_count = [0]

        def agg_side_effect(*args, **kwargs):
            agg_call_count[0] += 1
            return self._make_cursor([])

        with patch("yadacoin.core.keyeventlog.Config") as mock_config_cls:
            self._setup_mock_config(
                mock_config_cls,
                aggregate_side_effect=agg_side_effect,
                find_one_side_effect=find_one_side_effect,
            )
            result = await KeyEventLog.build_from_public_key(_VALID_PUBKEY)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].public_key_hash, _VALID_ADDR_A)
        self.assertTrue(getattr(result[0], "mempool", False))

    async def test_build_mempool_non_inception_then_no_more(self):
        """Line 881: mempool txn has prev_public_key_hash → address updated → no more → empty."""
        from unittest.mock import patch

        from yadacoin.core.keyeventlog import KeyEventLog

        non_inception = {
            **_INCEPTION_TXN_DICT,
            "prev_public_key_hash": "SOME_PREV_ADDR",
        }
        call_count = [0]

        async def find_one_side_effect(query):
            call_count[0] += 1
            return non_inception if call_count[0] == 1 else None

        with patch("yadacoin.core.keyeventlog.Config") as mock_config_cls:
            self._setup_mock_config(
                mock_config_cls,
                aggregate_return=self._make_cursor([]),
                find_one_side_effect=find_one_side_effect,
            )
            result = await KeyEventLog.build_from_public_key(_VALID_PUBKEY)

        self.assertEqual(result, [])

    async def test_build_forward_walk_mempool_txn_appended(self):
        """Line 921: forward walk: inception in blocks, no next block, mempool txn found → appended."""
        from unittest.mock import patch

        from yadacoin.core.keyeventlog import KeyEventLog

        inception_doc = {"transactions": dict(_INCEPTION_TXN_DICT)}
        next_txn_dict = {
            **_INCEPTION_TXN_DICT,
            "public_key_hash": _VALID_ADDR_B,
            "prerotated_key_hash": _VALID_ADDR_C,
            "twice_prerotated_key_hash": _VALID_ADDR_A,
            "prev_public_key_hash": _VALID_ADDR_A,
        }
        agg_call_count = [0]

        def agg_side_effect(*args, **kwargs):
            agg_call_count[0] += 1
            return (
                self._make_cursor([inception_doc])
                if agg_call_count[0] == 1
                else self._make_cursor([])
            )

        mempool_call_count = [0]

        async def find_one_side_effect(query):
            mempool_call_count[0] += 1
            return next_txn_dict if mempool_call_count[0] == 1 else None

        with patch("yadacoin.core.keyeventlog.Config") as mock_config_cls:
            self._setup_mock_config(
                mock_config_cls,
                aggregate_side_effect=agg_side_effect,
                find_one_side_effect=find_one_side_effect,
            )
            result = await KeyEventLog.build_from_public_key(_VALID_PUBKEY)

        self.assertEqual(len(result), 2)
        self.assertTrue(getattr(result[1], "mempool", False))

    async def test_build_forward_walk_no_blocks_no_mempool_breaks(self):
        """Forward walk: inception in blocks, no next block, no inception in miner_transactions → break."""
        from unittest.mock import patch

        from yadacoin.core.keyeventlog import KeyEventLog

        inception_doc = {"transactions": dict(_INCEPTION_TXN_DICT)}
        agg_call_count = [0]

        def agg_side_effect(*args, **kwargs):
            agg_call_count[0] += 1
            return (
                self._make_cursor([inception_doc])
                if agg_call_count[0] == 1
                else self._make_cursor([])
            )

        with patch("yadacoin.core.keyeventlog.Config") as mock_config_cls:
            self._setup_mock_config(
                mock_config_cls,
                aggregate_side_effect=agg_side_effect,
                find_one_return=None,
            )
            result = await KeyEventLog.build_from_public_key(_VALID_PUBKEY)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].public_key_hash, _VALID_ADDR_A)

    async def test_build_onchain_only_with_inception_stops_forward_walk(self):
        """Line 912: inception found in backward walk, onchain_only=True, no next block → if onchain_only: break."""
        from unittest.mock import patch

        from yadacoin.core.keyeventlog import KeyEventLog

        inception_doc = {"transactions": dict(_INCEPTION_TXN_DICT)}
        agg_call_count = [0]

        def agg_side_effect(*args, **kwargs):
            agg_call_count[0] += 1
            return (
                self._make_cursor([inception_doc])
                if agg_call_count[0] == 1
                else self._make_cursor([])
            )

        with patch("yadacoin.core.keyeventlog.Config") as mock_config_cls:
            self._setup_mock_config(
                mock_config_cls, aggregate_side_effect=agg_side_effect
            )
            result = await KeyEventLog.build_from_public_key(
                _VALID_PUBKEY, onchain_only=True
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].public_key_hash, _VALID_ADDR_A)
