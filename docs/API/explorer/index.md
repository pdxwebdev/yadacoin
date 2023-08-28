# /explorer-search

This endpoint takes a search term and responds with a block for the given hash if a block for that hash is found in the blockchain.

**URL** : `/explorer-search`

**Method** : `GET`

**URL Parameters** :

`term`: `required` : `string`

`result_type`: `optional` : `string` : `get_wallet_balance`

**Example URL** :

```
/explorer-search?term=0dd0ec9ab91e9defe535841a4c70225e3f97b7447e5358250c2dc898b8bd3139
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
  "resultType": "block_hash",
  "results": [
    {
      "nonce": 0,
      "hash": "0dd0ec9ab91e9defe535841a4c70225e3f97b7447e5358250c2dc898b8bd3139",
      "public_key": "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
      "id": "MEUCIQDDicnjg9DTSnGOMLN3rq2VQC1O9ABDiXygW7QDB6SNzwIga5ri7m9FNlc8dggJ9sDg0QXUugrHwpkVKbmr3kYdGpc=",
      "merkleRoot": "705d831ced1a8545805bbb474e6b271a28cbea5ada7f4197492e9a3825173546",
      "index": 0,
      "target": "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
      "special_min": false,
      "version": "1",
      "transactions": [
        {
          "public_key": "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
          "fee": 0.0,
          "hash": "71429326f00ba74c6665988bf2c0b5ed9de1d57513666633efd88f0696b3d90f",
          "dh_public_key": "",
          "relationship": "",
          "inputs": [],
          "outputs": [
            {
              "to": "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4",
              "value": 50.0
            }
          ],
          "rid": "",
          "id": "MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0="
        }
      ],
      "time": "1537127756",
      "prevHash": ""
    }
  ]
}
```
