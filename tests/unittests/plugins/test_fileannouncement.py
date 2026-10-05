"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import hashlib
import os
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch

from plugins.fileannouncement.backends import MemoryStorageBackend, get_backend
from plugins.fileannouncement.store import _search_filter, record_from_announcement
from yadacoin.core.fileannouncement import FileAnnouncement

from ..test_setup import AsyncTestCase


class TestStreamCache(AsyncTestCase):
    async def test_list_delete_and_clear(self):
        from plugins.fileannouncement import handlers as h

        saved = dict(h._STREAM_CACHE)
        h._STREAM_CACHE.clear()
        paths = []
        try:
            for name, body in (("one", b"abc"), ("two", b"defg")):
                fd, path = tempfile.mkstemp(
                    prefix="fa_stream_test_", dir=h._STREAM_TMP_DIR
                )
                os.write(fd, body)
                os.close(fd)
                paths.append(path)
                h._STREAM_CACHE[f"sia:{name}"] = (
                    path,
                    len(body),
                    time.monotonic() + 3600,
                    f"{name}.mp4",
                    "video/mp4",
                )
            listed = h.list_stream_cache()
            self.assertEqual(listed["count"], 2)
            self.assertEqual(listed["total_bytes"], 7)
            self.assertEqual(h.delete_stream_cache("sia:one"), 1)
            self.assertFalse(os.path.exists(paths[0]))
            self.assertEqual(h.delete_stream_cache("sia:missing"), 0)
            self.assertEqual(h.clear_stream_cache(), 1)
            self.assertEqual(h._STREAM_CACHE, {})
            self.assertFalse(os.path.exists(paths[1]))
        finally:
            h._STREAM_CACHE.clear()
            h._STREAM_CACHE.update(saved)
            for path in paths:
                if os.path.exists(path):
                    os.unlink(path)


class TestUploadProgress(AsyncTestCase):
    async def test_shard_progress_and_snapshot(self):
        from plugins.fileannouncement import progress

        upload_id = "upload-test-1"
        progress._UPLOADS.pop(upload_id, None)
        self.assertFalse(progress.begin("nope"))
        self.assertEqual(progress.snapshot("missing-id")["phase"], "pending")
        self.assertTrue(progress.begin(upload_id, filename="a.bin", size=12))
        self.assertEqual(progress.snapshot(upload_id)["phase"], "receiving")
        progress.apply(upload_id, {"phase": "sia"})
        progress.apply(
            upload_id,
            {"shard_size": 4, "shard_index": 0, "slab_index": 1},
        )
        progress.apply(
            upload_id,
            {"shard_size": 8, "shard_index": 1, "slab_index": 1},
        )
        snap = progress.snapshot(upload_id)
        self.assertEqual(snap["phase"], "sia")
        self.assertEqual(snap["shards"], 2)
        self.assertEqual(snap["shard_bytes"], 12)
        self.assertEqual(snap["filename"], "a.bin")
        progress.apply(upload_id, {"phase": "announcing"})
        self.assertEqual(progress.snapshot(upload_id)["phase"], "announcing")
        progress.finish(upload_id, ok=True)
        done = progress.snapshot(upload_id)
        self.assertEqual(done["phase"], "done")
        self.assertTrue(done["ok"])
        progress.finish(upload_id, ok=False, error="boom")
        failed = progress.snapshot(upload_id)
        self.assertEqual(failed["phase"], "error")
        self.assertEqual(failed["error"], "boom")
        progress._UPLOADS.pop(upload_id, None)

    async def test_memory_upload_reports_progress(self):
        events = []
        backend = MemoryStorageBackend()
        await backend.upload(b"hello", filename="a.txt", on_progress=events.append)
        self.assertEqual(events[0]["phase"], "sia")
        self.assertEqual(events[0]["shard_size"], 5)


class TestFileAnnouncementBackends(AsyncTestCase):
    async def test_memory_upload_download_delete(self):
        backend = MemoryStorageBackend()
        up = await backend.upload(b"hello", filename="a.txt", mime_type="text/plain")
        self.assertEqual(len(up["file_id"]), 64)
        down = await backend.download(up["file_id"])
        self.assertEqual(down["content"], b"hello")
        self.assertEqual(down["metadata"]["filename"], "a.txt")
        await backend.delete(up["file_id"])
        with self.assertRaises(Exception):
            await backend.download(up["file_id"])

    async def test_get_backend_memory_and_unknown(self):
        b = get_backend("memory")
        self.assertEqual(b.name, "memory")
        with self.assertRaises(Exception):
            get_backend("ipfs")

    async def test_view_without_app_key_requires_sharing_credential(self):
        from plugins.fileannouncement.backends import (
            SiaStorageBackend,
            is_sharing_credential,
            sharing_credential,
        )

        cred = sharing_credential(bytes(range(32)))
        self.assertTrue(is_sharing_credential(cred))
        self.assertTrue(cred.startswith("sia-share:v1:"))
        self.assertFalse(is_sharing_credential("https://sia.storage/share/x"))
        backend = SiaStorageBackend("")
        with self.assertRaises(Exception) as ctx:
            await backend.object_size(
                "ab" * 32, share_url="https://sia.storage/share/x"
            )
        self.assertIn("sharing key", str(ctx.exception).lower())
        self.assertNotIn("64-character", str(ctx.exception))


class TestFileAnnouncementStoreHelpers(AsyncTestCase):
    async def test_search_filter_or_fields(self):
        filt = _search_filter("hello")
        self.assertIn("$or", filt)
        fields = {list(clause.keys())[0] for clause in filt["$or"]}
        self.assertIn("title", fields)
        self.assertIn("description", fields)
        self.assertIn("keywords", fields)
        self.assertIn("file_id", fields)

    async def test_search_filter_empty(self):
        self.assertEqual(_search_filter(""), {})
        self.assertEqual(
            _search_filter("x", {"status": "announced"})["status"], "announced"
        )

    async def test_is_video_file(self):
        from plugins.fileannouncement.store import is_video_file

        self.assertTrue(is_video_file({"mime_type": "video/mp4"}))
        self.assertTrue(is_video_file({"filename": "clip.WebM"}))
        self.assertFalse(is_video_file({"mime_type": "image/png", "filename": "a.png"}))
        self.assertFalse(is_video_file({}))

    async def test_video_feed_keys_collapse_reupload(self):
        from plugins.fileannouncement.store import video_feed_keys

        first = video_feed_keys(
            {
                "backend": "Sia",
                "file_id": "aaa",
                "filename": "Clip.mp4",
                "size": 100,
            },
            owner="user-a",
        )
        second = video_feed_keys(
            {
                "backend": "sia",
                "file_id": "bbb",
                "filename": "clip.mp4",
                "size": "100",
            },
            owner="user-a",
        )
        other = video_feed_keys(
            {
                "backend": "sia",
                "file_id": "ccc",
                "filename": "clip.mp4",
                "size": 100,
            },
            owner="user-b",
        )
        self.assertIn("id:sia:aaa", first)
        self.assertTrue(set(first) & set(second))
        self.assertFalse(set(first) & set(other))

    async def test_same_user_duplicate_filter(self):
        from plugins.fileannouncement.store import same_user_duplicate_filter

        filt = same_user_duplicate_filter(
            owner="user-a",
            filename="Clip.mp4",
            size=100,
            content_hash="abc",
        )
        self.assertIsNotNone(filt)
        self.assertEqual(filt["status"], {"$nin": ["taken_down"]})
        self.assertIn("$and", filt)
        self.assertIsNone(same_user_duplicate_filter())

    async def test_record_from_announcement(self):
        ann = FileAnnouncement(
            file_id="abc123",
            title="Doc",
            keywords=["k"],
            description="d",
        )
        rec = record_from_announcement(ann, transaction_id="sig")
        self.assertEqual(rec["file_id"], "abc123")
        self.assertEqual(rec["transaction_id"], "sig")
        self.assertEqual(rec["status"], "announced")
        self.assertTrue(rec["record_id"])


class TestFileAnnouncementService(AsyncTestCase):
    async def test_create_file_with_memory_backend(self):
        from plugins.fileannouncement import service

        config = MagicMock()
        config.public_key = "pk"
        config.private_key = "sk"
        config.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        config.peer = None
        config.nodeShared = None

        fake_txn = MagicMock()
        fake_txn.transaction_signature = "txn-sig"
        fake_txn.inception_public_key_hash = "user-a"
        fake_txn.confirming_txn = None
        fake_txn.to_dict.return_value = {"id": "txn-sig", "relationship": {"file": {}}}

        with patch.object(
            service.store, "get_settings", AsyncMock(return_value={"backend": "memory"})
        ), patch.object(
            service.store, "insert_file", AsyncMock(side_effect=lambda c, r: r)
        ), patch.object(
            service.store, "add_history", AsyncMock(return_value={})
        ), patch.object(
            service.store, "find_same_user_duplicate", AsyncMock(return_value=None)
        ), patch.object(
            service.store, "clear_retraction", AsyncMock()
        ), patch.object(
            service, "_operator_id", AsyncMock(return_value="user-a")
        ), patch.object(
            service, "_generate_txn", AsyncMock(return_value=fake_txn)
        ):
            rec = await service.create_file(
                config,
                title="Hello",
                description="world",
                keywords=["demo"],
                content=b"payload",
                filename="hello.txt",
                mime_type="text/plain",
                backend_name="memory",
            )
        self.assertEqual(rec["title"], "Hello")
        self.assertEqual(rec["backend"], "memory")
        self.assertEqual(rec["transaction_id"], "txn-sig")
        self.assertEqual(rec["owner"], "user-a")
        self.assertTrue(rec["content_hash"])
        self.assertTrue(rec["file_id"])

    async def test_create_file_stores_thumbnail_id(self):
        from plugins.fileannouncement import service

        config = MagicMock()
        config.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        config.peer = None
        config.nodeShared = None
        fake_txn = MagicMock()
        fake_txn.transaction_signature = "txn-sig"
        fake_txn.inception_public_key_hash = "user-a"
        fake_txn.confirming_txn = None
        fake_txn.to_dict.return_value = {"id": "txn-sig"}
        with patch.object(
            service.store, "get_settings", AsyncMock(return_value={"backend": "memory"})
        ), patch.object(
            service.store, "insert_file", AsyncMock(side_effect=lambda c, r: r)
        ), patch.object(
            service.store, "add_history", AsyncMock(return_value={})
        ), patch.object(
            service.store, "find_same_user_duplicate", AsyncMock(return_value=None)
        ), patch.object(
            service.store, "clear_retraction", AsyncMock()
        ), patch.object(
            service, "_operator_id", AsyncMock(return_value="user-a")
        ), patch.object(
            service, "_generate_txn", AsyncMock(return_value=fake_txn)
        ) as generate:
            rec = await service.create_file(
                config,
                title="Clip",
                content=b"video-bytes",
                thumbnail=b"jpeg-bytes",
                filename="clip.mp4",
                mime_type="video/mp4",
                backend_name="memory",
            )
        ann = generate.call_args[0][1]
        self.assertTrue(ann.thumbnail_file_id)
        self.assertNotEqual(ann.thumbnail_file_id, rec["file_id"])
        self.assertEqual(rec["thumbnail_file_id"], ann.thumbnail_file_id)

    async def test_create_file_rejects_same_user_duplicate(self):
        from plugins.fileannouncement import service

        config = MagicMock()
        with patch.object(
            service.store, "get_settings", AsyncMock(return_value={"backend": "memory"})
        ), patch.object(
            service.store,
            "find_same_user_duplicate",
            AsyncMock(return_value={"title": "Welcome", "file_id": "old"}),
        ), patch.object(
            service.store, "add_history", AsyncMock(return_value={})
        ), patch.object(
            service, "_operator_id", AsyncMock(return_value="user-a")
        ), patch.object(
            service, "_generate_txn", AsyncMock()
        ) as generate:
            with self.assertRaises(service.DuplicateFileAnnouncementError) as ctx:
                await service.create_file(
                    config,
                    title="Welcome",
                    content=b"payload",
                    filename="clip.mp4",
                    mime_type="video/mp4",
                    backend_name="memory",
                )
        self.assertIn("already announced", str(ctx.exception))
        generate.assert_not_called()


class TestFileAnnouncementKEL(AsyncTestCase):
    async def test_generate_txn_requires_kel(self):
        from plugins.fileannouncement import service
        from yadacoin.core.fileannouncement import FileAnnouncement

        config = MagicMock()
        config.kel_manager = None
        with self.assertRaises(service.FileAnnouncementServiceError):
            await service._generate_txn(
                config,
                FileAnnouncement(file_id="abc", title="t"),
            )

    async def test_generate_txn_builds_unconfirmed_and_confirming(self):
        from plugins.fileannouncement import service
        from yadacoin.core.fileannouncement import FileAnnouncement

        k0_priv = bytes.fromhex("11" * 32)
        child_priv = bytes.fromhex("22" * 32)
        gc_priv = bytes.fromhex("33" * 32)
        ggc_priv = bytes.fromhex("44" * 32)
        signer_priv = bytes.fromhex("55" * 32)

        def key(priv):
            return {"private_key": priv, "chain_code": b"\x00" * 32}

        signer_pub, signer_addr = service._key_pub_addr(key(signer_priv))
        _cpub, child_addr = service._key_pub_addr(key(child_priv))
        _gpub, gc_addr = service._key_pub_addr(key(gc_priv))
        _ggpub, ggc_addr = service._key_pub_addr(key(ggc_priv))

        latest = MagicMock()
        latest.prerotated_key_hash = signer_addr
        latest.public_key_hash = "prevaddr"
        latest.inception_public_key_hash = "inception"
        latest.counter = 3
        kel = [MagicMock(), latest]

        config = MagicMock()
        config.kel_manager = MagicMock()
        config.kel_manager._k0 = key(k0_priv)
        config.kel_manager._second_factor = "sf"

        derived = [key(signer_priv), key(child_priv), key(gc_priv), key(ggc_priv)]

        with patch.object(
            service.KeyEventLog, "build_from_public_key", AsyncMock(return_value=kel)
        ), patch.object(
            service,
            "classify_key_event_flag",
            return_value=service.KeyEventFlag.CONFIRMING,
        ), patch.object(
            service, "derive_secure_path", side_effect=derived
        ):
            txn = await service._generate_txn(
                config, FileAnnouncement(file_id="abc123", title="Doc")
            )

        self.assertEqual(txn.public_key_hash, signer_addr)
        self.assertEqual(txn.prerotated_key_hash, child_addr)
        self.assertEqual(txn.twice_prerotated_key_hash, gc_addr)
        self.assertEqual(txn.prev_public_key_hash, "prevaddr")
        self.assertTrue(txn.relationship)
        confirming = txn.confirming_txn
        self.assertEqual(confirming.public_key_hash, child_addr)
        self.assertEqual(confirming.prerotated_key_hash, gc_addr)
        self.assertEqual(confirming.twice_prerotated_key_hash, ggc_addr)
        self.assertEqual(confirming.prev_public_key_hash, signer_addr)
        self.assertEqual(confirming.relationship, "")


class _Cursor:
    def __init__(self, rows):
        self._rows = list(rows)
        self._i = 0

    def sort(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def __aiter__(self):
        self._i = 0
        return self

    async def __anext__(self):
        if self._i >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._i]
        self._i += 1
        return row


class _Coll:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def find(self, query=None, projection=None):
        return _Cursor(self.rows)

    async def find_one(self, query=None, projection=None):
        return self.rows[0] if self.rows else None


class _DB:
    def __init__(self):
        self.blocks = _Coll()
        self.miner_transactions = _Coll()
        self.file_announcements = _Coll()
        self.file_announcement_retractions = _Coll()

    def __getitem__(self, name):
        return getattr(self, name)


class TestLiveAnnouncement(AsyncTestCase):
    def _config(self):
        config = MagicMock()
        config.mongo.async_db = _DB()
        return config

    async def test_local_only_is_not_playable(self):
        from plugins.fileannouncement.store import live_announcement

        config = self._config()
        config.mongo.async_db.file_announcements.rows = [
            {"file_id": "abc", "status": "announced", "transaction_id": "sig"}
        ]
        self.assertIsNone(await live_announcement(config, "abc"))

    async def test_chain_announcement_is_playable(self):
        from plugins.fileannouncement.store import live_announcement

        config = self._config()
        config.mongo.async_db.blocks.rows = [
            {
                "index": 9,
                "transactions": [
                    {
                        "id": "sig",
                        "inception_public_key_hash": "owner",
                        "relationship": {
                            "file": {
                                "file_id": "abc",
                                "backend": "sia",
                                "title": "Clip",
                                "filename": "clip.mp4",
                                "mime_type": "video/mp4",
                            }
                        },
                    }
                ],
            }
        ]
        live = await live_announcement(config, "abc", "sia")
        self.assertEqual(live["source"], "chain")
        self.assertEqual(live["transaction_id"], "sig")

    async def test_takedown_in_mempool_blocks_playback(self):
        from plugins.fileannouncement.store import live_announcement

        config = self._config()
        config.mongo.async_db.blocks.rows = [
            {
                "index": 9,
                "transactions": [
                    {
                        "id": "sig",
                        "relationship": {
                            "file": {
                                "file_id": "abc",
                                "backend": "sia",
                                "title": "Clip",
                            }
                        },
                    }
                ],
            }
        ]
        config.mongo.async_db.miner_transactions.rows = [
            {"relationship": {"content_takedown": {"transaction_id": "sig"}}}
        ]
        self.assertIsNone(await live_announcement(config, "abc"))

    async def test_owner_retraction_blocks_chain_copy(self):
        from plugins.fileannouncement.store import live_announcement

        config = self._config()
        config.mongo.async_db.blocks.rows = [
            {
                "index": 9,
                "transactions": [
                    {
                        "id": "sig",
                        "relationship": {
                            "file": {
                                "file_id": "abc",
                                "backend": "sia",
                                "title": "Clip",
                            }
                        },
                    }
                ],
            }
        ]
        config.mongo.async_db.file_announcement_retractions.rows = [
            {"file_id": "abc", "transaction_id": "sig"}
        ]
        self.assertIsNone(await live_announcement(config, "abc"))

    async def test_list_live_files_ignores_local_collection(self):
        from plugins.fileannouncement.store import list_live_files

        config = self._config()
        config.mongo.async_db.file_announcements.rows = [
            {
                "file_id": "only-local",
                "title": "Local only",
                "status": "announced",
                "filename": "a.mp4",
            }
        ]
        config.mongo.async_db.blocks.rows = [
            {
                "index": 3,
                "time": 50,
                "transactions": [
                    {
                        "id": "chain-sig",
                        "time": 50,
                        "relationship": {
                            "file": {
                                "file_id": "on-chain",
                                "title": "On chain",
                                "backend": "sia",
                                "filename": "b.mp4",
                            }
                        },
                    }
                ],
            }
        ]
        rows = await list_live_files(config)
        self.assertEqual([row["file_id"] for row in rows], ["on-chain"])
        self.assertEqual(rows[0]["status"], "confirmed")
        self.assertEqual(rows[0]["transaction_id"], "chain-sig")

    async def test_prune_drops_cache_when_not_live(self):
        from plugins.fileannouncement import handlers as h

        saved = dict(h._STREAM_CACHE)
        h._STREAM_CACHE.clear()
        fd, path = tempfile.mkstemp(prefix="fa_stream_test_", dir=h._STREAM_TMP_DIR)
        os.write(fd, b"vid")
        os.close(fd)
        h._STREAM_CACHE["sia:abc"] = (
            path,
            3,
            time.monotonic() + 3600,
            "clip.mp4",
            "video/mp4",
        )
        try:
            with patch.object(
                h.store, "live_announcement", AsyncMock(return_value=None)
            ):
                await h.prune_stream_cache(MagicMock())
            self.assertEqual(h._STREAM_CACHE, {})
            self.assertFalse(os.path.exists(path))
        finally:
            h._STREAM_CACHE.clear()
            h._STREAM_CACHE.update(saved)
            if os.path.exists(path):
                os.unlink(path)


class TestByteRange(AsyncTestCase):
    async def test_parse_open_and_suffix_ranges(self):
        from plugins.fileannouncement.handlers import parse_byte_range

        self.assertEqual(parse_byte_range("", 100), (0, 99))
        self.assertEqual(parse_byte_range("bytes=0-1", 100), (0, 1))
        self.assertEqual(parse_byte_range("bytes=0-", 100), (0, 99))
        self.assertEqual(parse_byte_range("bytes=-8", 100), (92, 99))
        self.assertIsNone(parse_byte_range("bytes=100-110", 100))

    async def test_memory_open_download_does_not_return_whole_object(self):
        backend = MemoryStorageBackend()
        body = b"abcdefghij"
        uploaded = await backend.upload(body, filename="a.mp4", mime_type="video/mp4")
        total, chunks = await backend.open_download(
            uploaded["file_id"], offset=2, length=3
        )
        self.assertEqual(total, 10)
        got = b""
        async for chunk in chunks:
            got += chunk
        self.assertEqual(got, b"cde")
        self.assertEqual(
            await backend.object_size(uploaded["file_id"]),
            len(body),
        )
        self.assertEqual(uploaded["file_id"], hashlib.sha256(body).hexdigest())


class TestProfileLookup(AsyncTestCase):
    def _config(self):
        config = MagicMock()
        config.mongo.async_db = _DB()
        return config

    async def test_identity_and_files_for_inception(self):
        from plugins.fileannouncement.store import (
            files_for_inception,
            identity_for_inception,
        )

        config = self._config()
        config.mongo.async_db.blocks.rows = [
            {
                "index": 4,
                "time": 40,
                "transactions": [
                    {
                        "id": "id-txn",
                        "public_key_hash": "rotated-key",
                        "inception_public_key_hash": "owner-a",
                        "relationship": {
                            "identity": {
                                "username": "alice",
                                "username_signature": "sig",
                            }
                        },
                    },
                    {
                        "id": "file-txn",
                        "inception_public_key_hash": "owner-a",
                        "time": 50,
                        "relationship": {
                            "file": {
                                "file_id": "vid1",
                                "backend": "sia",
                                "title": "Clip",
                                "filename": "clip.mp4",
                                "mime_type": "video/mp4",
                            }
                        },
                    },
                    {
                        "id": "other-file",
                        "inception_public_key_hash": "owner-b",
                        "time": 60,
                        "relationship": {
                            "file": {
                                "file_id": "vid2",
                                "backend": "sia",
                                "title": "Other",
                                "filename": "other.mp4",
                                "mime_type": "video/mp4",
                            }
                        },
                    },
                ],
            }
        ]
        ident = await identity_for_inception(config, "owner-a")
        self.assertEqual(ident["username"], "alice")
        self.assertEqual(ident["inception_public_key_hash"], "owner-a")
        files = await files_for_inception(config, "owner-a")
        self.assertEqual([row["file_id"] for row in files], ["vid1"])
        missing = await identity_for_inception(config, "nobody")
        self.assertEqual(missing["username"], "")

    async def test_string_relationship_does_not_drop_username(self):
        from plugins.fileannouncement.store import identity_for_inception

        config = self._config()
        config.mongo.async_db.blocks.rows = [
            {
                "index": 1,
                "transactions": [
                    {"id": "reanchor", "relationship": "reanchor"},
                    {
                        "id": "id-txn",
                        "public_key_hash": "1FPVi9gaMB9xqtKCTwD5ABBW1XziRzMttq",
                        "inception_public_key_hash": "1FPVi9gaMB9xqtKCTwD5ABBW1XziRzMttq",
                        "relationship": {
                            "identity": {
                                "username": "yadacoin.io",
                                "username_signature": "sig",
                            }
                        },
                    },
                ],
            }
        ]
        ident = await identity_for_inception(
            config, "1FPVi9gaMB9xqtKCTwD5ABBW1XziRzMttq"
        )
        self.assertEqual(ident["username"], "yadacoin.io")

    async def test_inception_for_username(self):
        from plugins.fileannouncement.store import inception_for_username

        config = self._config()
        config.mongo.async_db.blocks.rows = [
            {
                "transactions": [
                    {
                        "inception_public_key_hash": "1FPVi9gaMB9xqtKCTwD5ABBW1XziRzMttq",
                        "public_key_hash": "1FPVi9gaMB9xqtKCTwD5ABBW1XziRzMttq",
                        "relationship": {"identity": {"username": "yadacoin.io"}},
                    }
                ]
            }
        ]
        self.assertEqual(
            await inception_for_username(config, "@YadaCoin.io"),
            "1FPVi9gaMB9xqtKCTwD5ABBW1XziRzMttq",
        )
        self.assertEqual(await inception_for_username(config, "missing"), "")
