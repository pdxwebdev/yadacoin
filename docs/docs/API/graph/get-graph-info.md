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