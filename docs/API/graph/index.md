# /get-graph-friend-requests

Friend requests appear the in the `friend_requests` property of the graph output. The `relationship` property is not decryptable by you. Use the `dh_public_key` property to construct the shared secret for your relationship to decrypt the `relationship` property of further transactions.

**URL** : `/get-graph-friend-requests`

**Method** : `GET`

**URL Parameters** : 

`bulletin_secret=[bulletin_secret from wallet]`

**Example URL** : 
```
/get-graph-friend-requests?bulletin_secret=MEQCIAY0KK8hBM2C5mXBoAn4WCR15iaQlxrhK2G4csXwDiUbAiBpzeVotPnF1p9RZApeddsmyaSdaguGDdtxQl8tSJtiYQ==
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "logins": [], 
    "messages": [], 
    "registered": false, 
    "pending_registration": false, 
    "new_messages": [], 
    "human_hash": "oklahoma-sweet-california-rugby", 
    "rid": "d5286d56dad364086c3f2b49375247c412b5f35706c6b16c5c0aa87aa32cfc4a", 
    "friends": [], 
    "friend_requests": [{
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
    ], 
    "posts": [], 
    "sent_friend_requests": []
}
```
# /get-graph-friends

The `friends` property is not usually populated unless the graph provider determines this before sending graph output. While only one transaction is shown below, two transactions will actually be shown; one sent-friend-request transaction, and then another friend-request transaction.

**URL** : `/get-graph-friends`

**Method** : `GET`

**URL Parameters** : 

`bulletin_secret=[bulletin_secret from wallet]`

**Example URL** : 
```
/get-graph-friends?bulletin_secret=MEQCIAY0KK8hBM2C5mXBoAn4WCR15iaQlxrhK2G4csXwDiUbAiBpzeVotPnF1p9RZApeddsmyaSdaguGDdtxQl8tSJtiYQ==
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "logins": [], 
    "messages": [], 
    "registered": false, 
    "pending_registration": false, 
    "new_messages": [], 
    "human_hash": "oklahoma-sweet-california-rugby", 
    "rid": "d5286d56dad364086c3f2b49375247c412b5f35706c6b16c5c0aa87aa32cfc4a", 
    "friends": [{
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
    "friend_requests": [], 
    "posts": [], 
    "sent_friend_requests": []
}
```
# /get-graph-info

Get the basic information about the graph given a bulletin_secret.

**URL** : `/get-graph-info`

**Method** : `GET`

**URL Parameters** : 

`bulletin_secret=[bulletin_secret from wallet]`

**Example URL** : 
```
/get-graph-info?bulletin_secret=MEQCIAY0KK8hBM2C5mXBoAn4WCR15iaQlxrhK2G4csXwDiUbAiBpzeVotPnF1p9RZApeddsmyaSdaguGDdtxQl8tSJtiYQ==
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "logins": [], 
    "messages": [], 
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

## Notes

* The extra fields `rid` a
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
# /get-graph-new-messages

The `new_messages` property will contain a list of transactions containing messages in the `relationship` property sorted by block height. Only one message per RID will be placed into the list.

**URL** : `/get-graph-new-messages`

**Method** : `GET`

**URL Parameters** : 

`bulletin_secret=[bulletin_secret from wallet]`

**Example URL** : 
```
/get-graph-new-messages?bulletin_secret=MEQCIAY0KK8hBM2C5mXBoAn4WCR15iaQlxrhK2G4csXwDiUbAiBpzeVotPnF1p9RZApeddsmyaSdaguGDdtxQl8tSJtiYQ==
```

## Success Response

**Code** : `200 OK`

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
# /get-graph-posts

Posts appear the the `posts` property of the graph output. The actual post is found in the `relationship` property and is decrypted by the client using the `bulletin_secret` for that friend.

**URL** : `/get-graph-posts`

**Method** : `GET`

**URL Parameters** : 

`bulletin_secret=[bulletin_secret from wallet]`

**Example URL** : 
```
/get-graph-posts?bulletin_secret=MEQCIAY0KK8hBM2C5mXBoAn4WCR15iaQlxrhK2G4csXwDiUbAiBpzeVotPnF1p9RZApeddsmyaSdaguGDdtxQl8tSJtiYQ==
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "logins": [], 
    "messages": [], 
    "registered": false, 
    "pending_registration": false, 
    "new_messages": [], 
    "human_hash": "oklahoma-sweet-california-rugby", 
    "rid": "d5286d56dad364086c3f2b49375247c412b5f35706c6b16c5c0aa87aa32cfc4a", 
    "friends": [], 
    "friend_requests": [], 
    "posts": [{
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
    "sent_friend_requests": []
}
```
# /get-graph-sent-friend-requests

Sent friend requests appear the in the `sent_friend_requests` property of the graph output. The `relationship` property stores your diffie-hellman private key `dh_private_key`, the `bulletin_secret` of the requested friend, and their `username`.

**URL** : `/get-graph-sent-friend-requests`

**Method** : `GET`

**URL Parameters** : 

`bulletin_secret=[bulletin_secret from wallet]`

**Example URL** : 
```
/get-graph-sent-friend-requests?bulletin_secret=MEQCIAY0KK8hBM2C5mXBoAn4WCR15iaQlxrhK2G4csXwDiUbAiBpzeVotPnF1p9RZApeddsmyaSdaguGDdtxQl8tSJtiYQ==
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "logins": [], 
    "messages": [], 
    "registered": false, 
    "pending_registration": false, 
    "new_messages": [], 
    "human_hash": "oklahoma-sweet-california-rugby", 
    "rid": "d5286d56dad364086c3f2b49375247c412b5f35706c6b16c5c0aa87aa32cfc4a", 
    "friends": [], 
    "friend_requests": [], 
    "posts": [], 
    "sent_friend_requests": [{
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
    ]
}
```
