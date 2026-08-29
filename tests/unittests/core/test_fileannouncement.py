"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import hashlib

import yadacoin.core.config
from yadacoin.core.config import Config
from yadacoin.core.fileannouncement import (
    MAX_DESCRIPTION_LEN,
    MAX_FILE_ID_LEN,
    MAX_KEYWORD_LEN,
    MAX_KEYWORDS,
    MAX_TITLE_LEN,
    FileAnnouncement,
)
from yadacoin.core.keyrotation import NodeKeyRotationManager
from yadacoin.core.transaction import InvalidTransactionException, Transaction

from ..test_setup import AsyncTestCase


class TestFileAnnouncement(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        yadacoin.core.config.CONFIG = Config()
        yadacoin.core.config.CONFIG.network = "regnet"

    def _ann(self, **kwargs):
        data = {
            "file_id": "a" * 64,
            "title": "Report",
            "backend": "sia",
            "description": "Quarterly report",
            "keywords": ["finance", "Q1"],
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size": 1024,
        }
        data.update(kwargs)
        return FileAnnouncement(**data)

    async def test_init_and_to_dict(self):
        ann = self._ann()
        d = ann.to_dict()
        self.assertEqual(d["file_id"], "a" * 64)
        self.assertEqual(d["title"], "Report")
        self.assertEqual(d["backend"], "sia")
        self.assertEqual(d["keywords"], ["finance", "q1"])
        self.assertEqual(d["filename"], "report.pdf")
        self.assertEqual(d["size"], 1024)

    async def test_keywords_normalized_and_deduped(self):
        ann = self._ann(keywords=["Alpha", "alpha", " Beta ", ""])
        self.assertEqual(ann.keywords, ["alpha", "beta"])

    async def test_keywords_from_csv_string(self):
        ann = self._ann(keywords="one, two, TWO")
        self.assertEqual(ann.keywords, ["one", "two"])

    async def test_missing_file_id_raises(self):
        with self.assertRaises(ValueError):
            FileAnnouncement(file_id="", title="x")

    async def test_missing_title_raises(self):
        with self.assertRaises(ValueError):
            FileAnnouncement(file_id="abc", title="  ")

    async def test_title_too_long_raises(self):
        with self.assertRaises(ValueError):
            FileAnnouncement(file_id="abc", title="t" * (MAX_TITLE_LEN + 1))

    async def test_negative_size_raises(self):
        with self.assertRaises(ValueError):
            self._ann(size=-1)

    async def test_from_dict_and_relationship(self):
        inner = self._ann().to_dict()
        again = FileAnnouncement.from_dict(inner)
        self.assertEqual(again.file_id, inner["file_id"])
        rel = {FileAnnouncement.RELATIONSHIP_KEY: inner}
        parsed = FileAnnouncement.from_relationship(rel)
        self.assertEqual(parsed.title, "Report")

    async def test_from_relationship_missing_key(self):
        with self.assertRaises(ValueError):
            FileAnnouncement.from_relationship({"not_file": {}})

    async def test_to_string_deterministic(self):
        a = self._ann()
        b = self._ann()
        self.assertEqual(a.to_string(), b.to_string())
        self.assertIn("sia", a.to_string())
        self.assertIn("finance,q1", a.to_string())

    async def test_matches_query(self):
        ann = self._ann()
        self.assertTrue(ann.matches_query("report"))
        self.assertTrue(ann.matches_query("FINANCE"))
        self.assertTrue(ann.matches_query("a" * 8))
        self.assertFalse(ann.matches_query("nomatch"))
        self.assertTrue(ann.matches_query(""))

    async def test_transaction_parses_file_relationship(self):
        ann = self._ann()
        raw = {
            "time": 0,
            "id": "sigfile",
            "rid": "",
            "relationship": {FileAnnouncement.RELATIONSHIP_KEY: ann.to_dict()},
            "relationship_hash": "",
            "public_key": yadacoin.core.config.CONFIG.public_key,
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "requester_rid": "",
            "requested_rid": "",
            "hash": "",
            "inputs": [],
            "outputs": [],
            "coinbase": False,
            "version": 7,
        }
        parsed = Transaction.from_dict(raw)
        self.assertIsInstance(parsed.relationship, FileAnnouncement)
        self.assertEqual(parsed.relationship.file_id, ann.file_id)

    async def test_transaction_to_dict_wraps_file(self):
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            do_money=False,
        )
        ann = self._ann()
        txn.relationship = ann
        txn.relationship_hash = hashlib.sha256(ann.to_string().encode()).digest().hex()
        d = txn.to_dict()
        self.assertIn("file", d["relationship"])
        self.assertEqual(d["relationship"]["file"]["title"], "Report")

    async def test_generate_hash_uses_to_string(self):
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            relationship=self._ann(),
            do_money=False,
        )
        self.assertIsInstance(txn.relationship, FileAnnouncement)
        expected = hashlib.sha256(txn.relationship.to_string().encode()).digest().hex()
        self.assertEqual(txn.relationship_hash, expected)

    async def test_keywords_none_is_empty(self):
        ann = self._ann(keywords=None)
        self.assertEqual(ann.keywords, [])

    async def test_keywords_invalid_type_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self._ann(keywords=123)
        self.assertIn("list", str(ctx.exception).lower())

    async def test_keyword_too_long_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self._ann(keywords=["k" * (MAX_KEYWORD_LEN + 1)])
        self.assertIn("exceeds", str(ctx.exception))

    async def test_too_many_keywords_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self._ann(keywords=[f"k{i}" for i in range(MAX_KEYWORDS + 1)])
        self.assertIn("at most", str(ctx.exception))

    async def test_whitespace_file_id_raises(self):
        with self.assertRaises(ValueError) as ctx:
            FileAnnouncement(file_id="   ", title="x")
        self.assertIn("blank", str(ctx.exception))

    async def test_file_id_too_long_raises(self):
        with self.assertRaises(ValueError) as ctx:
            FileAnnouncement(file_id="a" * (MAX_FILE_ID_LEN + 1), title="x")
        self.assertIn("exceeds", str(ctx.exception))

    async def test_blank_backend_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self._ann(backend="   ")
        self.assertIn("backend", str(ctx.exception))

    async def test_description_too_long_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self._ann(description="d" * (MAX_DESCRIPTION_LEN + 1))
        self.assertIn("description", str(ctx.exception))

    async def test_size_not_integer_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self._ann(size="nope")
        self.assertIn("integer", str(ctx.exception))

    async def test_from_dict_not_dict_raises(self):
        with self.assertRaises(ValueError) as ctx:
            FileAnnouncement.from_dict("nope")
        self.assertIn("dict", str(ctx.exception))

    async def test_from_dict_missing_title_raises(self):
        with self.assertRaises(ValueError) as ctx:
            FileAnnouncement.from_dict({"file_id": "abc"})
        self.assertIn("title", str(ctx.exception))

    async def test_to_dict_includes_supersedes_and_extra(self):
        ann = self._ann(supersedes="prevtxn", extra="yes")
        d = ann.to_dict()
        self.assertEqual(d["supersedes"], "prevtxn")
        self.assertEqual(d["extra"], "yes")

    async def test_matches_query_whitespace_only(self):
        self.assertTrue(self._ann().matches_query("   "))

    async def test_repr_contains_fields(self):
        r = repr(self._ann())
        self.assertIn("FileAnnouncement", r)
        self.assertIn("sia", r)
        self.assertIn("Report", r)

    async def test_verify_file_announcement_uses_to_string(self):
        txn = await Transaction.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            do_money=False,
        )
        ann = self._ann()
        txn.relationship = ann
        txn.relationship_hash = hashlib.sha256(ann.to_string().encode()).digest().hex()
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = NodeKeyRotationManager._sign(
            yadacoin.core.config.CONFIG.private_key, txn.hash
        )
        try:
            await txn.verify()
        except InvalidTransactionException:
            pass
