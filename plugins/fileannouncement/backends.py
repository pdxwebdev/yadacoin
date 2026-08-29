"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""Pluggable file storage backends. Sia (https://sia.storage) is implemented now."""

import hashlib
import json
from abc import ABC, abstractmethod
from io import BytesIO
from typing import Dict, Optional

# Fixed 32-byte App ID for this plugin. NEVER change after release.
SIA_APP_ID_HEX = hashlib.sha256(b"yadacoin-fileannouncement-v1").digest().hex()
SIA_APP_ID_BYTES = bytes.fromhex(SIA_APP_ID_HEX)
DEFAULT_INDEXER_URL = "https://sia.storage"


class StorageBackendError(Exception):
    pass


class StorageBackend(ABC):
    """Interface every file storage backend must implement."""

    name = ""

    @abstractmethod
    async def upload(
        self,
        content: bytes,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Store ``content`` and return {file_id, size, ...}."""

    @abstractmethod
    async def download(self, file_id: str) -> dict:
        """Return {file_id, content: bytes, metadata: dict, size: int}."""

    @abstractmethod
    async def delete(self, file_id: str) -> dict:
        """Remove or unpin the object. Return {file_id, ok}."""


class MemoryStorageBackend(StorageBackend):
    """In-process backend used by tests and as a fallback."""

    name = "memory"

    def __init__(self):
        self._objects: Dict[str, dict] = {}

    async def upload(
        self,
        content: bytes,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        file_id = hashlib.sha256(content).hexdigest()
        meta = dict(metadata or {})
        if filename:
            meta["filename"] = filename
        if mime_type:
            meta["mime_type"] = mime_type
        self._objects[file_id] = {
            "content": bytes(content),
            "metadata": meta,
            "size": len(content),
        }
        return {"file_id": file_id, "size": len(content), "duplicate": False}

    async def download(self, file_id: str) -> dict:
        obj = self._objects.get(file_id)
        if not obj:
            raise StorageBackendError(f"object not found: {file_id}")
        return {
            "file_id": file_id,
            "content": obj["content"],
            "metadata": dict(obj["metadata"]),
            "size": obj["size"],
        }

    async def delete(self, file_id: str) -> dict:
        self._objects.pop(file_id, None)
        return {"file_id": file_id, "ok": True}


class SiaStorageBackend(StorageBackend):
    """Upload/download via the sia.storage indexer (sia-storage Python SDK)."""

    name = "sia"

    def __init__(self, app_key_hex: str, indexer_url: str = DEFAULT_INDEXER_URL):
        self.app_key_hex = (app_key_hex or "").strip()
        self.indexer_url = (indexer_url or DEFAULT_INDEXER_URL).rstrip("/")

    def _app_metadata(self):
        try:
            from sia_storage import AppMetadata
        except ImportError as exc:
            raise StorageBackendError(
                "sia-storage SDK is not installed. Run: pip install sia-storage"
            ) from exc
        return AppMetadata(
            id=SIA_APP_ID_BYTES,
            name="YadaCoin File Announcements",
            description="On-chain file announcements backed by Sia storage",
            service_url="https://yadacoin.io",
            logo_url=None,
            callback_url=None,
        )

    async def _sdk(self):
        try:
            from sia_storage import AppKey, Builder
        except ImportError as exc:
            raise StorageBackendError(
                "sia-storage SDK is not installed. Run: pip install sia-storage"
            ) from exc
        if len(self.app_key_hex) != 64:
            raise StorageBackendError(
                "sia_app_key must be a 64-character hex string (32 bytes). "
                "Obtain yours at https://sia.storage"
            )
        try:
            seed = bytes.fromhex(self.app_key_hex)
        except ValueError as exc:
            raise StorageBackendError("sia_app_key contains invalid hex") from exc
        builder = Builder(self.indexer_url, self._app_metadata())
        sdk = await builder.connected(AppKey(seed))
        if sdk is None:
            raise StorageBackendError(
                "Sia App Key not recognized by the indexer. "
                "Register at https://sia.storage and export a fresh App Key."
            )
        return sdk

    async def upload(
        self,
        content: bytes,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        try:
            from sia_storage import PinnedObject, UploadOptions
        except ImportError as exc:
            raise StorageBackendError(
                "sia-storage SDK is not installed. Run: pip install sia-storage"
            ) from exc
        sdk = await self._sdk()
        obj = await sdk.upload(PinnedObject(), BytesIO(content), UploadOptions())
        meta = dict(metadata or {})
        meta["sha256"] = hashlib.sha256(content).hexdigest()
        if filename:
            meta["filename"] = filename
        if mime_type:
            meta["mime_type"] = mime_type
        obj.update_metadata(json.dumps(meta).encode())
        await sdk.pin_object(obj)
        size = obj.size() if hasattr(obj, "size") else len(content)
        return {"file_id": str(obj.id()), "size": size, "duplicate": False}

    async def download(self, file_id: str) -> dict:
        try:
            from sia_storage import DownloadOptions
        except ImportError as exc:
            raise StorageBackendError(
                "sia-storage SDK is not installed. Run: pip install sia-storage"
            ) from exc
        sdk = await self._sdk()
        obj = await sdk.object(file_id.strip())
        async with sdk.download(obj, DownloadOptions()) as d:
            raw = await d.read_all()
        meta = {}
        raw_meta = getattr(obj, "metadata", None)
        if callable(raw_meta):
            try:
                raw_meta = raw_meta()
            except Exception:
                raw_meta = None
        if raw_meta:
            try:
                meta = json.loads(
                    raw_meta.decode("utf-8", errors="replace")
                    if isinstance(raw_meta, (bytes, bytearray))
                    else str(raw_meta)
                )
            except Exception:
                meta = {}
        return {
            "file_id": file_id,
            "content": raw,
            "metadata": meta,
            "size": len(raw),
        }

    async def delete(self, file_id: str) -> dict:
        sdk = await self._sdk()
        await sdk.delete_object(file_id.strip())
        try:
            await sdk.prune_slabs()
        except Exception:
            pass
        return {"file_id": file_id, "ok": True}


_MEMORY = MemoryStorageBackend()


def get_backend(
    name: str, app_key_hex: str = "", indexer_url: str = ""
) -> StorageBackend:
    name = (name or "sia").strip().lower()
    if name == "memory":
        return _MEMORY
    if name == "sia":
        return SiaStorageBackend(
            app_key_hex=app_key_hex,
            indexer_url=indexer_url or DEFAULT_INDEXER_URL,
        )
    raise StorageBackendError(f"unknown storage backend: {name}")


def available_backends():
    return [
        {
            "name": "sia",
            "label": "Sia Storage",
            "url": "https://sia.storage",
            "implemented": True,
        },
        {
            "name": "memory",
            "label": "In-memory (tests)",
            "url": "",
            "implemented": True,
        },
    ]
