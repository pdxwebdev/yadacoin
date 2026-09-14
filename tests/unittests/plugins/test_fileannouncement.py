"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from plugins.fileannouncement.backends import MemoryStorageBackend, get_backend
from plugins.fileannouncement.store import _search_filter, record_from_announcement
from yadacoin.core.fileannouncement import FileAnnouncement

from ..test_setup import AsyncTestCase


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
        fake_txn.to_dict.return_value = {"id": "txn-sig", "relationship": {"file": {}}}

        with patch.object(
            service.store, "get_settings", AsyncMock(return_value={"backend": "memory"})
        ), patch.object(
            service.store, "insert_file", AsyncMock(side_effect=lambda c, r: r)
        ), patch.object(
            service.store, "add_history", AsyncMock(return_value={})
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
        self.assertTrue(rec["file_id"])


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
