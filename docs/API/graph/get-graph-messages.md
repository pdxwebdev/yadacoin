# /get-graph-messages

Messages are revealed with the relationship property is decrypted using the `dh_private_key` of the friend-request transaction (the transaction you can decrypt) and the `dh_public_key` from the transaction you cannot decrypt. Do not use the `dh_public_key` and `dh_private_key` from the same transaction, as it will yield the incorrect shared secret. When you have the correct shared secret then you can decrypt the `relationship` property.

**URL** : `/get-graph-messages`

**Method** : `GET`

**URL Parameters** : 

`bulletin_secret=[bulletin_secret from wallet]`

**Example URL** : 
```
/get-graph-messages?bulletin_secret=MEQCIAY0KK8hBM2C5mXBoAn4WCR15iaQlxrhK2G4csXwDiUbAiBpzeVotPnF1p9RZApeddsmyaSdaguGDdtxQl8tSJtiYQ==
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "logins": [], 
    "messages": [{
            "public_key": "02fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc", 
            "fee": 0.0001, 
            "hash": "061857e0d8b4c9564e5bf2c5cca1cf9d10ecd97994d1a334713be1941d2c0ba5", 
            "dh_public_key": "", 
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
    ], 
    "registered": false, 
    "pending_registration": false, 
    "new_messages": [], 
    "human_hash": "oklahoma-sweet-california-rugby", 
    "rid": "d5286d56dad364086c3f2b49375247c412b5f35706c6b16c5c0aa87aa32cfc4a", 
    "friends": [], 
    "friend_requests": [], 
    "posts": [], 
    "sent_friend_requests": []
}
```
