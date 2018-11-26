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
