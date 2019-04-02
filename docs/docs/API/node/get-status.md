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

**Content examples**

> Placeholder, to be completed

```json
{
  "version": "0.0.8", 
  "network": "mainnet", 
  "connections": {
    "outgoing": -1, 
    "ingoing": -1, 
    "max": -1
  },
  "peers": {
    "active": -1,
    "inactive": -1
  }
}
```
