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
