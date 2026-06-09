"""sia/api.py — Sia decentralized storage SDK helpers for the YadaCoin AI Agent.

Wraps the `sia-storage` Python SDK (pip install sia-storage).

The SDK uses a BIP-39 recovery phrase only once (during onboarding) to derive
a per-app App Key.  After onboarding, only the exported App Key (32 bytes as a
hex string) is stored and passed here — the recovery phrase must NOT be stored
server-side.

Indexer URL : https://sia.storage
App ID      : Fixed 32-byte value for this YadaCoin AI Agent application.
              NEVER change this value — it determines the key derivation path
              and changing it permanently loses access to stored objects.
"""
import base64
import datetime
import json
from io import BytesIO
from typing import Optional

# Fixed App ID for the YadaCoin AI Agent — generated once, never changes.
# 32 bytes, hex-encoded: sha256("yadaaiagent-v1") truncated to 32 bytes.
_APP_ID_HEX = (
    "79616461 61696167 656e742d 76310000 00000000 00000000 00000000 00000000".replace(
        " ", ""
    )
)
_APP_ID_BYTES = bytes.fromhex(_APP_ID_HEX)

_INDEXER_URL = "https://sia.storage"


def _get_app_metadata():
    """Return the AppMetadata for this application."""
    try:
        from sia_storage import AppMetadata  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "sia-storage SDK is not installed. Run: pip install sia-storage"
        ) from exc
    return AppMetadata(
        id=_APP_ID_BYTES,
        name="YadaCoin AI Agent",
        description="YadaCoin decentralized AI agent with Sia file storage",
        service_url="https://yadacoin.io",
        logo_url=None,
        callback_url=None,
    )


async def _get_sdk(app_key_hex: str):
    """Reconnect to the Sia indexer using an existing App Key.

    Returns the SDK instance, or raises ValueError if the key is invalid /
    not recognized by the indexer.

    Parameters
    ----------
    app_key_hex:
        64-character hex string (32 bytes) — the exported App Key previously
        obtained via the one-time registration flow.
    """
    try:
        from sia_storage import AppKey, Builder  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "sia-storage SDK is not installed. Run: pip install sia-storage"
        ) from exc

    app_key_hex = app_key_hex.strip()
    if len(app_key_hex) != 64:
        raise ValueError(
            "sia_app_key must be a 64-character hex string (32 bytes). "
            "Obtain yours at https://sia.storage/dashboard"
        )
    try:
        seed = bytes.fromhex(app_key_hex)
    except ValueError:
        raise ValueError("sia_app_key contains invalid hex characters")

    app_key = AppKey(seed)
    builder = Builder(_INDEXER_URL, _get_app_metadata())
    sdk = await builder.connected(app_key)
    if sdk is None:
        raise ValueError(
            "Sia App Key not recognized by the indexer. "
            "Please register your account at https://sia.storage/dashboard "
            "and export a fresh App Key."
        )
    return sdk


async def sia_upload(
    app_key_hex: str,
    content: bytes,
    filename: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> dict:
    """Upload bytes to Sia and pin the resulting object.

    Returns
    -------
    dict with keys: ok, object_id, size, duplicate (True if already existed)
    """
    import hashlib as _hashlib

    content_sha256 = _hashlib.sha256(content).hexdigest()

    # ── Duplicate check: scan existing objects for matching sha256 ────────────
    try:
        existing = await sia_list_objects(app_key_hex)
        for item in existing.get("objects", []):
            item_meta = item.get("metadata") or {}
            if item_meta.get("sha256") == content_sha256:
                return {
                    "ok": True,
                    "object_id": item["object_id"],
                    "size": len(content),
                    "duplicate": True,
                }
    except Exception:
        pass  # if listing fails, proceed with upload

    sdk = await _get_sdk(app_key_hex)
    try:
        from sia_storage import PinnedObject, UploadOptions  # type: ignore[import]
    except ImportError as exc:
        raise ImportError("sia-storage SDK is not installed") from exc

    obj = await sdk.upload(PinnedObject(), BytesIO(content), UploadOptions())

    # Attach metadata including sha256 for future duplicate detection
    meta: dict = {"sha256": content_sha256}
    if filename:
        meta["filename"] = filename
    if mime_type:
        meta["mime_type"] = mime_type
    obj.update_metadata(json.dumps(meta).encode())

    await sdk.pin_object(obj)
    return {
        "ok": True,
        "object_id": str(obj.id()),
        "size": obj.size(),
        "duplicate": False,
    }


async def sia_download(app_key_hex: str, object_id: str) -> dict:
    """Download an object from Sia by its object ID.

    Returns
    -------
    dict with keys: ok, object_id, size, content (UTF-8 text) or content_b64
    (base64-encoded bytes when the content is not valid UTF-8), metadata
    """
    sdk = await _get_sdk(app_key_hex)
    try:
        from sia_storage import DownloadOptions  # type: ignore[import]
    except ImportError as exc:
        raise ImportError("sia-storage SDK is not installed") from exc

    obj = await sdk.object(object_id.strip())
    async with sdk.download(obj, DownloadOptions()) as d:
        raw = await d.read_all()

    meta: dict = {}
    if obj.metadata:
        try:
            meta = json.loads(obj.metadata.decode("utf-8", errors="replace"))
        except Exception:
            pass

    result = {
        "ok": True,
        "object_id": object_id,
        "size": len(raw),
        "metadata": meta,
    }
    try:
        result["content"] = raw.decode("utf-8")
    except UnicodeDecodeError:
        result["content_b64"] = base64.b64encode(raw).decode("ascii")
        result["note"] = "Binary content encoded as base64"
    return result


async def sia_download_shared(app_key_hex: str, sia_signed_url: str) -> dict:
    """Download an object from a sia:// signed URL shared by another user.

    The recipient uses their own app key to connect, but the signed URL
    grants access to the specific object without exposing the sharer's key.

    Returns
    -------
    dict with keys: ok, size, content (UTF-8 text) or content_b64, metadata
    """
    sdk = await _get_sdk(app_key_hex)
    try:
        from sia_storage import DownloadOptions  # type: ignore[import]
    except ImportError as exc:
        raise ImportError("sia-storage SDK is not installed") from exc

    obj = sdk.shared_object(sia_signed_url.strip())
    async with sdk.download(obj, DownloadOptions()) as d:
        raw = await d.read_all()

    meta: dict = {}
    try:
        meta_bytes = obj.metadata()
        if meta_bytes:
            meta = json.loads(meta_bytes.decode("utf-8", errors="replace"))
    except Exception:
        pass

    result = {
        "ok": True,
        "size": len(raw),
        "metadata": meta,
    }
    try:
        result["content"] = raw.decode("utf-8")
    except UnicodeDecodeError:
        result["content_b64"] = base64.b64encode(raw).decode("ascii")
        result["note"] = "Binary content encoded as base64"
    return result


async def sia_list_objects(app_key_hex: str) -> dict:
    """List all pinned objects in this app's account.

    Uses sdk.object_events(cursor, limit) with ObjectsCursor pagination.
    ObjectEvent fields: id (str), deleted (bool), updated_at (Timestamp),
    object (Optional[PinnedObject]).

    Returns
    -------
    dict with keys: ok, objects (list of {object_id, metadata, updated_at})
    """
    sdk = await _get_sdk(app_key_hex)
    try:
        from sia_storage import ObjectsCursor  # type: ignore[import]
    except ImportError as exc:
        raise ImportError("sia-storage SDK is not installed") from exc

    pinned = []
    cursor = None
    PAGE = 100
    while True:
        events = await sdk.object_events(cursor, PAGE)
        if not events:
            break
        for event in events:
            # Skip deleted objects
            if getattr(event, "deleted", False):
                continue
            obj = getattr(event, "object", None)
            obj_id = str(getattr(event, "id", ""))
            meta: dict = {}
            if obj is not None:
                raw_meta = None
                try:
                    raw_meta = obj.metadata()
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
                        pass
            updated_at = getattr(event, "updated_at", None)
            pinned.append(
                {
                    "object_id": obj_id,
                    "metadata": meta,
                    "updated_at": str(updated_at) if updated_at else None,
                }
            )
        # Build next cursor from last event
        if len(events) < PAGE:
            break
        last = events[-1]
        cursor = ObjectsCursor(
            id=str(getattr(last, "id", "")),
            after=getattr(last, "updated_at", None),
        )

    return {"ok": True, "objects": pinned, "count": len(pinned)}


async def sia_delete(app_key_hex: str, object_id: str) -> dict:
    """Delete (unpin) a Sia object and prune unreferenced slabs.

    Returns
    -------
    dict with keys: ok
    """
    sdk = await _get_sdk(app_key_hex)
    await sdk.delete_object(object_id.strip())
    await sdk.prune_slabs()
    return {"ok": True, "object_id": object_id}


async def sia_share(
    app_key_hex: str,
    object_id: str,
    expires_hours: int = 24,
    base_url: str = "https://yadacoin.io",
) -> dict:
    """Generate a time-limited public share URL for a Sia object.

    Stores a token in MongoDB so the download proxy can retrieve the file
    using the app key without exposing it in the URL.  The returned URL
    points to the YadaCoin node's /ai-agent-auth/sia/download/<token>
    endpoint which anyone can open in a browser.

    Returns
    -------
    dict with keys: ok, object_id, share_url, expires_at
    """
    import secrets

    import yadacoin.core.config as _cfg

    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=max(1, expires_hours)
    )
    token = secrets.token_urlsafe(32)

    # Also get the SDK's native signed URL — usable by other node operators via
    # sdk.shared_object(sia_signed_url) without needing the sharer's app key.
    sdk = await _get_sdk(app_key_hex)
    obj = await sdk.object(object_id.strip())
    sia_signed_url = str(sdk.share_object(obj, expires))

    config = _cfg.Config()
    await config.mongo.async_db.sia_share_tokens.insert_one(
        {
            "token": token,
            "object_id": object_id.strip(),
            "app_key_hex": app_key_hex,
            "expires_at": expires,
        }
    )

    share_url = f"{base_url.rstrip('/')}/ai-agent-auth/sia/download/{token}"
    return {
        "ok": True,
        "object_id": object_id,
        "share_url": share_url,
        "sia_signed_url": sia_signed_url,
        "expires_at": expires.isoformat(),
    }
