# /create-raw-transaction

This endpoint creates a 

**URL** : `/create-raw-transaction`

**Method** : `POST`

**URL Parameters** : 

`hash`: `SHA256 hex encoded string`

**Example URL** : 
```
/create-raw-transaction
```

**Data constraints**

The `address` property in the payload of your request will be a P2PKH encoded string.

The `outputs` property in the payload must be an array containing objects with a P2PKH `to` and a float `value` specified. These are the recipients.

The `inputs` property of the payload must be an array of objects containing an `id` property. The `id` property must reference an unspend transaction for the given `address`.

**Payload outline**

```json
{
    "public_key": string,
    "address": P2PKH string,
    "fee": float 8 precision,
    "inputs": [
        {
            "id": base64 string
        }
    ],
    "outputs": [
        {
            "to": P2PKH string
            "value": float 8 precision
        }
    ]
}
```

**Payload example**

```json
{
    "public_key": "024125b0105d26f8e7e10a6d6a06a797898ca0c6884355e7b8aff018d63368ebf1",
    "address": "12c19fpBnFR4j3PD9jRMHvwNkkuyXZ5yCb",
    "fee": 0.001,
    "inputs": [
        {
            "id": "MEUCIQDKCedPkg1pPSDOONpMlS7YZvGjlhQ4lMw84hcNDlRiNwIgavt6yROWjZ6UPSO6S13IKBnTTdWS/jCE9Lt1kIGWd6Q="
        }
    ],
    "outputs": [
        {
            "to": "12c19fpBnFR4j3PD9jRMHvwNkkuyXZ5yCb",
            "value": 0.0009
        }
    ]
}
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "header": "0.00100000MEUCIQDKCedPkg1pPSDOONpMlS7YZvGjlhQ4lMw84hcNDlRiNwIgavt6yROWjZ6UPSO6S13IKBnTTdWS/jCE9Lt1kIGWd6Q=12c19fpBnFR4j3PD9jRMHvwNkkuyXZ5yCb0.00600000",
    "hash": "0ea51fce000bcc1203c7fb9ee784e0d57b61648d7769112178c1dab047d0ba00"
}
```
## Error Response

**Code** : `400`

```json
{
    "status": string,
    "msg": string
}
```
# /get-block

This endpoint takes a block hash and responds with a block for the given hash if a block for that hash is found in the blockchain.

**URL** : `/get-block`

**Method** : `GET`

**URL Parameters** : 

`hash`: `SHA256 hex encoded string`
OR
`index`: `integer of block height`

**Example URL** : 
```
/get-block?hash=0dd0ec9ab91e9defe535841a4c70225e3f97b7447e5358250c2dc898b8bd3139
```
OR
```
/get-block?index=455210
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "nonce" : 0,
    "hash" : "0dd0ec9ab91e9defe535841a4c70225e3f97b7447e5358250c2dc898b8bd3139",
    "public_key" : "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
    "id" : "MEUCIQDDicnjg9DTSnGOMLN3rq2VQC1O9ABDiXygW7QDB6SNzwIga5ri7m9FNlc8dggJ9sDg0QXUugrHwpkVKbmr3kYdGpc=",
    "merkleRoot" : "705d831ced1a8545805bbb474e6b271a28cbea5ada7f4197492e9a3825173546",
    "index" : 0,
    "target" : "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "special_min" : false,
    "version" : "1",
    "transactions" : [ 
        {
            "public_key" : "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
            "fee" : 0.0,
            "hash" : "71429326f00ba74c6665988bf2c0b5ed9de1d57513666633efd88f0696b3d90f",
            "dh_public_key" : "",
            "relationship" : "",
            "inputs" : [],
            "outputs" : [ 
                {
                    "to" : "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4",
                    "value" : 50.0
                }
            ],
            "rid" : "",
            "id" : "MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0="
        }
    ],
    "time" : "1537127756",
    "prevHash" : ""
}
```
# /get-latest-block

This endpoint returns the latest block in the blockchain.

**URL** : `/get-latest-block`

**Method** : `GET`

**URL Parameters** : 

None

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "nonce" : 0,
    "hash" : "0dd0ec9ab91e9defe535841a4c70225e3f97b7447e5358250c2dc898b8bd3139",
    "public_key" : "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
    "id" : "MEUCIQDDicnjg9DTSnGOMLN3rq2VQC1O9ABDiXygW7QDB6SNzwIga5ri7m9FNlc8dggJ9sDg0QXUugrHwpkVKbmr3kYdGpc=",
    "merkleRoot" : "705d831ced1a8545805bbb474e6b271a28cbea5ada7f4197492e9a3825173546",
    "index" : 0,
    "target" : "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "special_min" : false,
    "version" : "1",
    "transactions" : [ 
        {
            "public_key" : "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
            "fee" : 0.0,
            "hash" : "71429326f00ba74c6665988bf2c0b5ed9de1d57513666633efd88f0696b3d90f",
            "dh_public_key" : "",
            "relationship" : "",
            "inputs" : [],
            "outputs" : [ 
                {
                    "to" : "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4",
                    "value" : 50.0
                }
            ],
            "rid" : "",
            "id" : "MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0="
        }
    ],
    "time" : "1537127756",
    "prevHash" : ""
}
```
# /get-peers

This endpoint returns the list of active peers known by the local node.

> Since async tnode.py v0.0.7

**URL** : `/get-peers`

**Method** : `GET`

**URL Parameters** : 

None

**Example URL** : 
```
/get-peers
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
  "num_peers": 3, 
  "peers": [
    {
      "host": "34.237.46.10", 
      "port": 8000, 
      "bulletin_secret": null, 
      "is_me": false
    }, {
      "host": "116.203.24.126", 
      "port": 8000, 
      "bulletin_secret": null, 
      "is_me": false
    }, {
      "host": "178.32.96.27", 
      "port": 8000, 
      "bulletin_secret": null, 
      "is_me": false}
  ]
}
```
# /get-status

This endpoint returns the status of the node.

> Since async tnode.py v0.0.8

**URL** : `/get-status`

**Method** : `GET`

**URL Parameters** : 

None

**Example URL** : 
```
/get-status
```

## Success Response

**Code** : `200 OK`

**Content example**

```json
{
    "version": "5.7.2",
    "protocol_version": 3,
    "network": "mainnet",
    "peer_type": "seed",
    "username": "",
    "websocket_inbound_peers": 4802,
    "websocket_inbound_pending": 0,
    "inbound_peers": 1,
    "inbound_pending": 0,
    "outbound_peers": 1,
    "outbound_ignore": 0,
    "outbound_pending": 0,
    "pool": "N/A",
    "uptime": "310:19:18",
    "height": 427750,
    "health": {
        "ConsenusHealth": {
            "last_activity  ": 1679891003,
            "status         ": true,
            "time_until_fail": 120,
            "ignore         ": false
        },
        "TCPServerHealth": {
            "last_activity  ": 1679890994,
            "status         ": true,
            "time_until_fail": 111,
            "ignore         ": true
        },
        "TCPClientHealth": {
            "last_activity  ": 1679890998,
            "status         ": true,
            "time_until_fail": 115,
            "ignore         ": false
        },
        "PeerHealth": {
            "last_activity  ": 1679891000,
            "status         ": true,
            "time_until_fail": 117,
            "ignore         ": false
        },
        "BlockCheckerHealth": {
            "last_activity  ": 1679891003,
            "status         ": true,
            "time_until_fail": 120,
            "ignore         ": false
        },
        "MessageSenderHealth": {
            "last_activity  ": 1679891000,
            "status         ": true,
            "time_until_fail": 117,
            "ignore         ": false
        },
        "BlockInserterHealth": {
            "last_activity  ": 1679891003,
            "status         ": true,
            "time_until_fail": 120,
            "ignore         ": false
        },
        "TransactionProcessorHealth": {
            "last_activity  ": 1679891003,
            "status         ": true,
            "time_until_fail": 120,
            "ignore         ": false
        },
        "PoolPayerHealth": {
            "last_activity  ": 1679890964,
            "status         ": true,
            "time_until_fail": 81,
            "ignore         ": false
        },
        "CacheValidatorHealth": {
            "last_activity  ": 1679890883,
            "status         ": true,
            "time_until_fail": 0,
            "ignore         ": false
        },
        "MempoolCleanerHealth": {
            "last_activity  ": 1679890237,
            "status         ": true,
            "time_until_fail": 2834,
            "ignore         ": false
        },
        "status": true
    },
    "latest_block": {
        "version": 5,
        "time": 1679889834,
        "index": 427750,
        "public_key": "03dc4edf90c1c60c79e557d833031360ac9581d078beff7668f95f05d5f64a9fab",
        "prevHash": "84b9e7111f001c904324ee88e730b2b74f92f02fc4ed1c3e4885669a02000000",
        "nonce": "d971027d33313662313532353838623135",
        "transactions": [
            {
                "time": 1679889834,
                "rid": "",
                "id": "MEQCID/rxhNJOTie40cqKA6afr0eqm+Mhwa9s5tGtzhcf0W7AiADxbhDgbCPjyRgKkG75SwkG+xVgGn2kcIbFTTd/R38BA==",
                "relationship": "",
                "public_key": "03dc4edf90c1c60c79e557d833031360ac9581d078beff7668f95f05d5f64a9fab",
                "dh_public_key": "",
                "fee": 0.0,
                "hash": "dc762b5291a18186ae7158b299abed69237b837df00ca351fab1c02f977c04be",
                "inputs": [],
                "outputs": [
                    {
                        "to": "1Jkeiz8z94m12hh426wz6dnUkU5fN5RYhp",
                        "value": 12.5
                    }
                ],
                "version": 3
            }
        ],
        "hash": "04d48313d159fea661f7c4f15a16da6ff501dc480dc4776f850da7b002000000",
        "merkleRoot": "c3524fed1d0c0f0359d5d08bf880728f4100fa482d8bf509a976f774daf4dc9d",
        "special_min": false,
        "target": "00000005b3239469452340000000000000000000000000000000000000000000",
        "special_target": "00000005b3239469452340000000000000000000000000000000000000000000",
        "header": "5167988983403dc4edf90c1c60c79e557d833031360ac9581d078beff7668f95f05d5f64a9fab42775084b9e7111f001c904324ee88e730b2b74f92f02fc4ed1c3e4885669a02000000{nonce}00000005b3239469452340000000000000000000000000000000000000000000c3524fed1d0c0f0359d5d08bf880728f4100fa482d8bf509a976f774daf4dc9d",
        "id": "MEQCIDUduiXvbDAsZPUNKtmB0bPivxC5iAwogJm+SXW6kaJ7AiAczZNmbgriUSTA8elyY9Bb48JIa5NvjooH05nqtMTHnA=="
    },
    "queues": {
        "BlockProcessingQueue": {
            "queue_item_count": 0,
            "average_processing_time": "2.4385",
            "num_items_processed": 3641
        },
        "TransactionProcessingQueue": {
            "queue_item_count": 0,
            "average_processing_time": "0.3142",
            "num_items_processed": 11911
        }
    },
    "message_sender": {
        "nodeServer": {
            "num_messages": 0
        },
        "nodeClient": {
            "num_messages": 550
        }
    },
    "slow_queries": {
        "count": 0,
        "detail": []
    }
}
```
# /sign-raw-transaction

This endpoint signs a transaction hash created by `/create-raw-transaction`

**URL** : `/sign-raw-transaction`

**Method** : `POST`

**URL Parameters** : 

`None`

**Example URL** : 
```
/sign-raw-transaction
```

**Data constraints**

The `private_key` property in the payload of your request will be the hex encoded DER string of your private key.

The `hash` property in the payload of your request will be the hex encoded SHA256 digested string of your transaction header.

**Payload outline**

```json
{
    "private_key": string,
    "hash": string,
}
```

**Payload example**

```json
{
    "private_key": "024125b0105d26f8e7e10a6d6a06a797898ca0c6884355e7b8aff018d63368ebf1",
    "hash": "0ea51fce000bcc1203c7fb9ee784e0d57b61648d7769112178c1dab047d0ba00"
    
}
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "transaction_signature": "MEQCIAY0KK8hBM2C5mXBoAn4WCR15iaQlxrhK2G4csXwDiUbAiBpzeVotPnF1p9RZApeddsmyaSdaguGDdtxQl8tSJtiYQ=="
}
```
## Error Response

**Code** : `400`

```json
{
    "status": string,
    "msg": string
}
```
# /transaction

This endpoint accepts transactions. It is currently the only endpoint evailable for accepting trasnactions for consideration to be included in a block by a miner. The transactions accepted by this endpoint are stored in the `miner_transactions` collection in your local MongoDB instance. The transaction is also disseminated to the network for other miners to incorporate into mined blocks.

**URL** : `/transaction`

**Method** : `POST`

**URL Parameters** : 

`rid`

**Example URL** : 
```
/transaction
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "public_key": "02fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc", 
    "fee": 0.0001, 
    "hash": "061857e0d8b4c9564e5bf2c5cca1cf9d10ecd97994d1a334713be1941d2c0ba5", 
    "dh_public_key": "8b4c9564e5bf264e5bf2c5cca1cf9d10ecd97994d1a3347138b4c9564e5bf2", 
    "relationship": "MEUCIQDPkS0JQj92l68xal9Xy6qD2DJEra9BleJ2xZJoImVHQgIgfAVy+003qm1WeqnwcOz+XjhzgJgI4E3POIFBwoonBkcMEUCIQDPkS0JQj92l68xal9Xy6qD2DJEra9BleJ2xZJoImVHQgIgfAVy+003qm1WeqnwcOz+XjhzgJgI4E3POIFBwoonBkc=", 
    "inputs": [
        {
            "id": "MEUCIQDPkS0JQj92l68xal9Xy6qD2DJEra9BleJ2xZJoImVHQgIgfAVy+003qm1WeqnwcOz+XjhzgJgI4E3POIFBwoonBkc="
        }
    ], 
    "outputs": [
        {
            "to": "1ADY5MY8cZhLRhYAcaG7VVax73juXfAiJy", 
            "value": 7.21874955854638
        }
    ],
    "rid": "9d10ecd97994d1a334713be1941d2c0ba5ecd97994d1a334713be1941d2c0ba5", 
    "id": "MEQCIFl7ekjQ9LT72bK1nvms7nbQv4M73nG1K7zk6Oo1lJBdAiApLqpKHWol2JarNEwtdl/TfSzewShz17IovfYHmqLi+Q=="
}
```
