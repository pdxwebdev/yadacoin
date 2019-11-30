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
    "serve_port": 8000, 
    "site_database": "yadacoinsite", 
    "wif": "KxJtubo885q2qVrEf4MP6Kjtwaj5sWH4AKjMPY3eNQQk9iSm513v", 
    "web_server_host": "0.0.0.0", 
    "database": "yadacoin", 
    "web_server_port": 5000, 
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
