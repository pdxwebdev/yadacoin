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
