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
import re

_ID = re.compile(r"^[A-Za-z0-9]{16,128}$")


def root(config) -> str:
    custom = getattr(config, "paid_media_dir", None)
    if custom:
        return os.path.abspath(str(custom))
    return os.path.abspath(os.path.join(os.getcwd(), "data", "fileannouncement-paid"))


def _path(config, file_id: str) -> str:
    file_id = (file_id or "").strip()
    if not _ID.match(file_id):
        raise ValueError("invalid paid file id")
    return os.path.join(root(config), file_id)


def save(
    config, file_id: str, content: bytes, filename: str = "", mime_type: str = ""
) -> str:
    path = _path(config, file_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(content)
    os.replace(tmp, path)
    meta = {
        "file_id": file_id,
        "filename": filename or "",
        "mime_type": mime_type or "application/octet-stream",
        "size": len(content),
    }
    with open(path + ".json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    return path


def has(config, file_id: str) -> bool:
    try:
        path = _path(config, file_id)
    except ValueError:
        return False
    return os.path.isfile(path)


def meta(config, file_id: str) -> dict:
    path = _path(config, file_id)
    sidecar = path + ".json"
    if os.path.isfile(sidecar):
        try:
            with open(sidecar, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
    if not os.path.isfile(path):
        return {}
    return {
        "file_id": file_id,
        "filename": "",
        "mime_type": "application/octet-stream",
        "size": os.path.getsize(path),
    }


def open_file(config, file_id: str):
    path = _path(config, file_id)
    if not os.path.isfile(path):
        return None
    return open(path, "rb")
