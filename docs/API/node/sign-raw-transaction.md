# /sign-raw-transaction

This endpoint signs a transaction hash created by `/create-raw-transaction`

**URL** : `/sign-raw-transaction`

**Method** : `POST`

**URL Parameters** : 

`None`

**Example URL** : 
```
/sign-raw-transaction
```

**Data constraints**

The `private_key` property in the payload of your request will be the hex encoded DER string of your private key.

The `hash` property in the payload of your request will be the hex encoded SHA256 digested string of your transaction header.

**Payload outline**

```json
{
    "private_key": string,
    "hash": string,
}
```

**Payload example**

```json
{
    "private_key": "024125b0105d26f8e7e10a6d6a06a797898ca0c6884355e7b8aff018d63368ebf1",
    "hash": "0ea51fce000bcc1203c7fb9ee784e0d57b61648d7769112178c1dab047d0ba00"
    
}
```

## Success Response

**Code** : `200 OK`

**Content examples**

```json
{
    "transaction_signature": "MEQCIAY0KK8hBM2C5mXBoAn4WCR15iaQlxrhK2G4csXwDiUbAiBpzeVotPnF1p9RZApeddsmyaSdaguGDdtxQl8tSJtiYQ=="
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
