"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import json
import os
import socket
from urllib.parse import unquote, urlparse

BOOTSTRAP_URL = "https://yadacoin.io/yadacoinstatic/bootstrap.tar.gz"
CONFIRM_PHRASE = "reload"
CONSENSUS_COLLECTION = "consensus"


class MongoTarget(object):
    def __init__(
        self,
        configured_host,
        connect_host,
        port,
        database,
        username,
        password,
        auth_source,
        note,
    ):
        self.configured_host = configured_host
        self.connect_host = connect_host
        self.port = int(port)
        self.database = database
        self.username = username or ""
        self.password = password or ""
        self.auth_source = auth_source or "admin"
        self.note = note

    def public(self):
        return {
            "configured_host": self.configured_host,
            "host": self.connect_host,
            "port": self.port,
            "database": self.database,
            "authenticated": bool(self.username),
            "note": self.note,
        }

    def secrets(self):
        if self.password:
            return [self.password]
        return []


def parse_host(value):
    raw = (value or "localhost").strip()
    if "://" in raw:
        parsed = urlparse(raw)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 27017,
            "username": unquote(parsed.username) if parsed.username else "",
            "password": unquote(parsed.password) if parsed.password else "",
            "database": (parsed.path or "").lstrip("/"),
        }
    if raw.startswith("[") and "]" in raw:
        host, _, rest = raw[1:].partition("]")
        port = 27017
        if rest.startswith(":") and rest[1:].isdigit():
            port = int(rest[1:])
        return {
            "host": host,
            "port": port,
            "username": "",
            "password": "",
            "database": "",
        }
    if raw.count(":") == 1:
        host, port = raw.rsplit(":", 1)
        if port.isdigit():
            return {
                "host": host or "localhost",
                "port": int(port),
                "username": "",
                "password": "",
                "database": "",
            }
    return {
        "host": raw or "localhost",
        "port": 27017,
        "username": "",
        "password": "",
        "database": "",
    }


def target_from_config(config):
    if not isinstance(config, dict):
        raise ValueError("Config must be a JSON object")
    parsed = parse_host(config.get("mongodb_host") or "localhost")
    database = config.get("database") or parsed["database"] or "yadacoin"
    username = config.get("mongodb_username") or parsed["username"] or ""
    password = config.get("mongodb_password") or parsed["password"] or ""
    auth_source = config.get("mongodb_auth_source") or "admin"
    return MongoTarget(
        configured_host=parsed["host"],
        connect_host=parsed["host"],
        port=parsed["port"],
        database=database,
        username=username,
        password=password,
        auth_source=auth_source,
        note=None,
    )


def load_target(path):
    if not os.path.isfile(path):
        raise FileNotFoundError("Config not found: {}".format(path))
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return target_from_config(data)


def tcp_open(host, port, timeout=1.5):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def resolve_target(target, probe=tcp_open):
    if probe(target.configured_host, target.port):
        target.connect_host = target.configured_host
        target.note = None
        return target
    if target.configured_host in ("mongodb", "mongo") and probe(
        "127.0.0.1", target.port
    ):
        target.connect_host = "127.0.0.1"
        target.note = (
            "Using 127.0.0.1 because {} is only reachable inside Docker.".format(
                target.configured_host
            )
        )
        return target
    target.connect_host = target.configured_host
    target.note = None
    return target


def redact_text(text, secrets):
    redacted = text
    for secret in secrets or []:
        if not secret:
            continue
        if redacted == secret or (len(secret) >= 4 and secret in redacted):
            redacted = redacted.replace(secret, "***")
    return redacted


def redact_argv(argv, secrets):
    redacted = []
    for arg in argv:
        redacted.append(redact_text(arg, secrets))
    return redacted
