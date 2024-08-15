# /generate-child-wallet

Create a child wallet for a given index.

**URL** : `/generate-child-wallet`

**Method** : `POST`

**Header** : `Authorization: bearer JWT_TOKEN` // JWT_TOKEN from /unlock endpoint

**Request data** :

```typescript
{
  "index": integer
}
```

## Success Response

**Code** : `200 OK`

**Response example**

```json
{
  "address": "`address of newly created wallet`",
  "status": true
}
```

## Error Response

**Code** : `400 Invalid Request`

**Response example**

```json
{
  "status": false,
  "message": "error message"
}
```

# /generate-wallet

Generate a new seed and HD wallet

**URL** : `/generate-wallet`

**Method** : `GET`

## Success Responses

**Code** : `200 OK`

**Content example** : Response will reflect back the updated information. A
User with `id` of '1234' sets their name, passing `UAPP` header of 'ios1_2':

```json
{
  "username": "",
  "public_key": "031df11550ba23d1738d2b3227a8e8b28f7e35a1a369967ea7ebde37d5cfcabc6c",
  "private_key": "208133c5107465c328d457380d3749a3de6a6c1f29265179eddb177ad91fb4e7",
  "serve_port": 8001,
  "site_database": "yadacoinsite",
  "wif": "KxJtubo885q2qVrEf4MP6Kjtwaj5sWH4AKjMPY3eNQQk9iSm513v",
  "web_server_host": "0.0.0.0",
  "database": "yadacoin",
  "peer_port": 8000,
  "peer_host": "",
  "fcm_key": "",
  "seed": "",
  "address": "1KYZoqeQZfm3LpmL2rh5K3jhRPwN3AAU5",
  "serve_host": "0.0.0.0",
  "bulletin_secret": "MEQCIBMi1nb3/bSee5aAxAWscAL7EC855Y4w2Pq2nWIXRItMAiBtOAbgDkjJkvVTvGFFdG/gpWoESwC7CGjgslnGc9RX4w==",
  "xprv": "xprv9s21ZrQH143K3Cy78KacBtuV64s3Fi9xK3TkFzFS85Gv3Ss6MkWyzFeSaxQcjX64YsXD5YhBA3GUQRpnRn7fdi872vaQX4SGyi4psXGZ8sY",
  "callbackurl": "http://0.0.0.0:5000/create-relationship",
  "mongodb_host": "localhost"
}
```

# /wallet

Generate a new seed and HD wallet

**URL** : `/wallet`

**URL Parameters** : `?address=[P2PKH Address]`

**Example URL** : `/wallet?address=13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK`

**Method** : `GET`

## Success Responses

**Code** : `200 OK`

**Content example** : Response will reflect back the wallet ballance and uspent outputs for the given address.

```json
{
  "balance": 255.3866845565283,
  "unspent_transactions": [
    {
      "public_key": "02fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc",
      "fee": 0.0001,
      "hash": "6639e35fd0cf8149458254908ec79ce23b64f050f919fa4adb86b4d36504ad6a",
      "dh_public_key": "",
      "relationship": "",
      "inputs": [
        {
          "id": "MEQCIEi9sagTl6Iq69g9NzhfOjiJdnl4Uj+upWmTbp6wjWsXAiAGf7cPN9vJTRn/dfqAtw4XMOssPiRKaqCERcg1puFhOg=="
        }
      ],
      "outputs": [
        {
          "to": "13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK",
          "value": 21.3714287047476
        }
      ],
      "height": 23507,
      "rid": "",
      "id": "MEUCIQDRaOpsNtb4Si0zwHzflCHds4PBri2Y6QPFyurJ8MnmYQIgFQ8aAN2Ujjjndb31On2cfzW302Vl+wMk53It7awatIA="
    }
  ]
}
```

# /validate-address

Is a wallet address valid

**URL** : `/validate-address`

**URL Parameters** : `?address=[P2PKH Address]`

**Example URL** : `/validate-address?address=13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK`

**Method** : `GET`

## Success Responses

**Code** : `200 OK`

**Content example** : Response will return boolean true if address is valid, false if it is not.

```json
{
  "status": true,
  "address": "13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK"
}
```

# /unlock

Is a wallet address valid

**Method** : `POST`

**URL** : `/unlock`

**Request Content-type** : `json`

**Data**

```json
{
  "key_or_wif": "`wif or private_key string from config.json`"
}
```

## Success Responses

**Code** : `200 OK`

**Content example** : Response will return boolean true if address is valid, false if it is not.

```json
{
  "token": "`encoded JWT string`"
}
```

# /send-transaction

Generate and send a transaction to the given address for the given amount.

**URL** : `/send-transaction`

**Method** : `POST`

**Header** : `Authorization: bearer JWT_TOKEN`
**Header** : `Content-type: application/json`

**Request data**

```json
{
  "address": "`string address of recipient address`",
  "value": "`int or decimal amount of YDA being sent`",
  "from": "`string address of master or child wallet`"
}
```

## Success Response

**Code** : `200 OK`

**Content example**

```json
{
  "public_key": "02fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc",
  "fee": 0.0001,
  "hash": "6639e35fd0cf8149458254908ec79ce23b64f050f919fa4adb86b4d36504ad6a",
  "dh_public_key": "",
  "relationship": "",
  "inputs": [
    {
      "id": "MEQCIEi9sagTl6Iq69g9NzhfOjiJdnl4Uj+upWmTbp6wjWsXAiAGf7cPN9vJTRn/dfqAtw4XMOssPiRKaqCERcg1puFhOg=="
    }
  ],
  "outputs": [
    {
      "to": "13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK",
      "value": 21.3714287047476
    }
  ],
  "height": 23507,
  "rid": "",
  "id": "MEUCIQDRaOpsNtb4Si0zwHzflCHds4PBri2Y6QPFyurJ8MnmYQIgFQ8aAN2Ujjjndb31On2cfzW302Vl+wMk53It7awatIA="
}
```

# /get-transaction-by-id

Get a transaction by transaction id on the blockchain or in the mempool.

**URL** : `/get-transaction-by-id`

**URL Parameters** : `?id=transaction_id`

**Example URL** : `/get-transaction-by-id?id=MEUCIQDRaOpsNtb4Si0zwHzflCHds4PBri2Y6QPFyurJ8MnmYQIgFQ8aAN2Ujjjndb31On2cfzW302Vl+wMk53It7awatIA=`

**Method** : `GET`

## Success Response

**Code** : `200 OK`

**Content example**

```json
{
  "public_key": "02fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc",
  "fee": 0.0001,
  "hash": "6639e35fd0cf8149458254908ec79ce23b64f050f919fa4adb86b4d36504ad6a",
  "dh_public_key": "",
  "relationship": "",
  "inputs": [
    {
      "id": "MEQCIEi9sagTl6Iq69g9NzhfOjiJdnl4Uj+upWmTbp6wjWsXAiAGf7cPN9vJTRn/dfqAtw4XMOssPiRKaqCERcg1puFhOg=="
    }
  ],
  "outputs": [
    {
      "to": "13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK",
      "value": 21.3714287047476
    }
  ],
  "height": 23507,
  "rid": "",
  "id": "MEUCIQDRaOpsNtb4Si0zwHzflCHds4PBri2Y6QPFyurJ8MnmYQIgFQ8aAN2Ujjjndb31On2cfzW302Vl+wMk53It7awatIA="
}
```

# /convert-public-key-to-address

Get a transaction by transaction id on the blockchain or in the mempool.

**URL** : `/convert-public-key-to-address`

**URL Parameters** : `?public_key=hex_public_key`

**Example URL** : `/convert-public-key-to-address?public_key=0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7`

**Method** : `GET`

## Success Response

**Code** : `200 OK`

**Content example**

```json
{
  "address": "1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC",
  "public_key": "0255110297d7b260a65972cd2c623996e18a6aeb9cc358ac667854af7efba4f0a7"
}
```

# /get-transaction-confirmations

Get the number of confirmations for a transaction given its transaction ID.

**URL** : `/get-transaction-confirmations`

**URL Parameters** : `?id=transaction_id`

**Example URL** : `/get-transaction-confirmations?id=MEUCIQDRaOpsNtb4Si0zwHzflCHds4PBri2Y6QPFyurJ8MnmYQIgFQ8aAN2Ujjjndb31On2cfzW302Vl+wMk53It7awatIA=`

**Method** : `GET`

## Success Response

**Code** : `200 OK`

**Content example**

```json
{
  "confirmations": 6
}
```
