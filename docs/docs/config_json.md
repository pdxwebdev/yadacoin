# Configuration file

The config file is config/config.json

A default file is auto-generated at install step via `utils/generate_config.py auto > config/config.json`  
(see setup.sh)

## Sample commented config.json

The comments are not valid json, they are only there to explain each parameter


```
{
    # These are the private and public info of your wallet (fake infos here)
    "seed": "a list of words",
    "xprv": "xprvdfgqefghsdfhsfhfghsfhfgh",
    "public_key": "05644646161616",
    "address": "1uykZoN5SuXqMkDTHf19TyiD7FpvpzRrCD",
    "private_key": "0000000000000000000000000000000000000",
    "wif": "gvybhTYiyuopiuolyjtbyiujrtyinbtyuij",
    "bulletin_secret": "Mblabla==",
    "fcm_key": "",
    
    # Here come the mongo db connection params
    "mongodb_host": "localhost",
    "username": "",
    "network": "mainnet",
    "database": "yadacoin",
    "site_database": "yadacoinsite",
    
    # The server configuration
    "web_server_host": "0.0.0.0",
    "web_server_port": 5000,
    
    # This is not used 
    "peer_host": "192.168.1.173",
    "peer_port": 8000,
    
    # IP and port the server will listen on
    "serve_host": "192.168.1.173",
    "serve_port": 8000,
    # pnp should only be used for specific configs
    "use_pnp": false,
    "callbackurl": "http://0.0.0.0:5000/create-relationship",

    # This is important, because it's no duplicate if behind a nat, and public ip != listen ip 
    "public_ip": "192.168.1.173",

    
    # New params for peer control
    "max_inbound": 10,      # max number of allowed incoming websocket connections
    "max_outbound": 10,     # max (and target) number of peers to try to connect to
    "max_miners": 100,      # max allowed miners (set to -1 to deactivate pool)
    "polling": 0,          # New node do not need polling anymore. You can set 0 to deactivate polling, 
                            # or set a value high enough (in seconds, like 60) not to generate too much load.
                            # Should be 0 once a few new nodes are up.
    
    # Debug / dev params
    
    "post_peer": false,     # If false, will not post your ip to the central API (no more needed)
    "extended_status": false,     # If true, will display full list of known peers and in/out connections.
    
    # You can optionally specify a list of seed nodes to use. If none is given, node will use the central API as seed. 
    
    "peers_seed" : [{"host": "34.237.46.10","port": 8000 }, {"host": "116.203.24.126","port": 8000 }, {"host": "51.75.68.13","port": 8000 }, {"host": "178.32.96.27","port": 8000 }],
    "outgoing_blacklist" : ["192.168.1.230"],  # debug/dev only, avoid any outgoing connection to this ip.
    "force_polling": [{"host": "34.237.46.10","port": 8000 }, {"host": "116.203.24.126","port": 8000 },{"host": "188.165.250.78","port": 8000 }, {"host": "178.32.96.27","port": 8000 }]
    # use these for polling, whatever the status is.

}
```