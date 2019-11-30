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
