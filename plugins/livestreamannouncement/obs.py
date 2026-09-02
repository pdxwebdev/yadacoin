"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64
import hashlib
import json
import uuid


class OBSWebSocketError(Exception):
    pass


def obs_auth_string(password: str, salt: str, challenge: str) -> str:
    """OBS 5 Identify authentication string (static password, not per-start)."""
    secret = base64.b64encode(
        hashlib.sha256((password + salt).encode("utf-8")).digest()
    )
    auth = base64.b64encode(hashlib.sha256(secret + challenge.encode("utf-8")).digest())
    return auth.decode("ascii")


async def _recv_json(ws):
    raw = await ws.recv()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


async def _send_request(ws, request_type, request_data=None):
    payload = {
        "op": 6,
        "d": {
            "requestType": request_type,
            "requestId": uuid.uuid4().hex,
            "requestData": request_data or {},
        },
    }
    await ws.send(json.dumps(payload))
    while True:
        msg = await _recv_json(ws)
        if msg.get("op") == 7:
            return msg.get("d") or {}


async def _identify(ws, password: str):
    hello = await _recv_json(ws)
    data = hello.get("d") or {}
    identify = {"op": 1, "d": {"rpcVersion": int(data.get("rpcVersion") or 1)}}
    auth = data.get("authentication") or {}
    if auth:
        identify["d"]["authentication"] = obs_auth_string(
            password or "", auth.get("salt") or "", auth.get("challenge") or ""
        )
    await ws.send(json.dumps(identify))
    identified = await _recv_json(ws)
    if identified.get("op") != 2:
        raise OBSWebSocketError("OBS Identify failed")
    return identified


async def configure_and_start(host, port, password, server_url, stream_key, timeout=5):
    """SetStreamServiceSettings + StartStream. Raises if the socket is down."""
    import websockets

    uri = f"ws://{host}:{int(port)}"
    async with websockets.connect(uri, open_timeout=timeout) as ws:
        await _identify(ws, password)
        await _send_request(
            ws,
            "SetStreamServiceSettings",
            {
                "streamServiceType": "rtmp_custom",
                "streamServiceSettings": {
                    "server": server_url,
                    "key": stream_key,
                },
            },
        )
        await _send_request(ws, "StartStream")


async def stop_stream(host, port, password, timeout=5):
    import websockets

    uri = f"ws://{host}:{int(port)}"
    async with websockets.connect(uri, open_timeout=timeout) as ws:
        await _identify(ws, password)
        await _send_request(ws, "StopStream")


async def try_start(host, port, password, server_url, stream_key):
    try:
        await configure_and_start(host, port, password, server_url, stream_key)
        return True, ""
    except Exception as exc:
        return False, str(exc)


async def try_stop(host, port, password):
    try:
        await stop_stream(host, port, password)
        return True, ""
    except Exception as exc:
        return False, str(exc)
