"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ..test_setup import AsyncTestCase

_PRIV_HEX = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
_PUB_HEX = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"


def _make_valid_sig(username: str, priv_hex: str) -> str:
    """Produce a real username_signature for tests."""
    from yadacoin.core.transactionutils import TU

    return TU.generate_deterministic_signature.__func__(TU, None, username, priv_hex)


class TestIdentityAnnouncementInit(unittest.TestCase):
    def test_blank_username_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement(
                username="", username_signature="sig", host="h", port=1
            )

    def test_whitespace_username_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement(
                username="   ", username_signature="sig", host="h", port=1
            )

    def test_missing_username_signature_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement(username="u", username_signature="", host="h", port=1)

    def test_missing_host_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement(
                username="u", username_signature="sig", host="", port=1
            )

    def test_missing_port_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement(
                username="u", username_signature="sig", host="h", port=None
            )

    def test_valid_construction(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        ia = IdentityAnnouncement(
            username="mynode",
            username_signature="SIG",
            host="1.2.3.4",
            port=8000,
        )
        self.assertEqual(ia.username, "mynode")
        self.assertEqual(ia.host, "1.2.3.4")
        self.assertEqual(ia.port, 8000)
        self.assertEqual(ia.http_protocol, "https")
        self.assertEqual(ia.peer_type, "service_provider")


class TestIdentityAnnouncementSerialisation(unittest.TestCase):
    def _make(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        return IdentityAnnouncement(
            username="n1",
            username_signature="SIG",
            host="h",
            port=9,
            http_protocol="http",
            http_port=80,
            peer_type="seed",
        )

    def test_to_dict_round_trip(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        ia = self._make()
        d = ia.to_dict()
        ia2 = IdentityAnnouncement.from_dict(d)
        self.assertEqual(ia2.username, ia.username)
        self.assertEqual(ia2.peer_type, ia.peer_type)

    def test_to_string_contains_identity_key(self):
        ia = self._make()
        s = ia.to_string()
        self.assertIn('"identity"', s)

    def test_to_relationship(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        ia = self._make()
        rel = ia.to_relationship()
        self.assertIn(IdentityAnnouncement.RELATIONSHIP_KEY, rel)

    def test_from_dict_missing_field_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement.from_dict({"username": "u"})

    def test_from_relationship_no_key_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement.from_relationship({"other": {}})

    def test_from_dict_non_dict_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement.from_dict("not a dict")


class TestIdentityAnnouncementVerifySignature(unittest.TestCase):
    def test_valid_signature(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement
        from yadacoin.core.transactionutils import TU

        sig = TU.generate_deterministic_signature.__func__(
            TU, None, "mynode", _PRIV_HEX
        )
        ia = IdentityAnnouncement(
            username="mynode",
            username_signature=sig,
            host="h",
            port=1,
        )
        self.assertTrue(ia.verify_username_signature(_PUB_HEX))

    def test_wrong_public_key_fails(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        ia = IdentityAnnouncement(
            username="mynode",
            username_signature="invalidsig",
            host="h",
            port=1,
        )
        self.assertFalse(ia.verify_username_signature(_PUB_HEX))

    def test_invalid_sig_bytes_returns_false(self):
        import base64

        from yadacoin.core.identityannouncement import IdentityAnnouncement

        ia = IdentityAnnouncement(
            username="mynode",
            username_signature=base64.b64encode(b"\x00" * 5).decode(),
            host="h",
            port=1,
        )
        self.assertFalse(ia.verify_username_signature(_PUB_HEX))


class TestIdentityAnnouncementChainLookup(AsyncTestCase):
    async def _mock_config(self, chain_docs=None, mempool_doc=None):
        import yadacoin.core.config

        cfg = MagicMock()

        async def _agg(pipeline):
            for doc in chain_docs or []:
                yield doc

        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=_agg(None))

        async def _agg2(pipeline):
            for doc in chain_docs or []:
                yield doc

        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=MagicMock())
        cfg.mongo.async_db.blocks.aggregate.return_value.__aiter__ = lambda s: iter(
            chain_docs or []
        )

        # Use AsyncMock for find_one
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value=mempool_doc
        )
        yadacoin.core.config.CONFIG = cfg
        return cfg

    async def test_get_by_username_not_found(self):
        import yadacoin.core.config
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()

        async def _empty_agg(pipeline):
            return
            yield  # pragma: no cover

        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=_empty_agg(None))
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)
        yadacoin.core.config.CONFIG = cfg

        with patch("yadacoin.core.config.Config", return_value=cfg):
            result = await IdentityAnnouncement.get_by_username("nobody")
        self.assertIsNone(result)

    async def test_get_by_username_mempool_hit(self):
        import yadacoin.core.config
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()

        async def _empty_agg(pipeline):
            return
            yield  # pragma: no cover

        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=_empty_agg(None))
        mempool_doc = {
            "public_key": _PUB_HEX,
            "relationship": {"identity": {"username": "mynode"}},
        }
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value=mempool_doc
        )
        yadacoin.core.config.CONFIG = cfg

        with patch("yadacoin.core.config.Config", return_value=cfg):
            result = await IdentityAnnouncement.get_by_username("mynode")
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "mempool")
        self.assertEqual(result["public_key"], _PUB_HEX)

    async def test_get_by_username_blockchain_hit(self):
        import yadacoin.core.config
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()

        chain_doc = {
            "public_key": _PUB_HEX,
            "relationship": {"identity": {"username": "mynode"}},
        }

        async def _agg(pipeline):
            yield chain_doc

        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=_agg(None))
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)
        yadacoin.core.config.CONFIG = cfg

        with patch("yadacoin.core.config.Config", return_value=cfg):
            result = await IdentityAnnouncement.get_by_username("mynode")
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "blockchain")

    async def test_exists_username_false(self):
        import yadacoin.core.config
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)
        yadacoin.core.config.CONFIG = cfg

        result = await IdentityAnnouncement.exists_username("nobody", config=cfg)
        self.assertFalse(result)

    async def test_exists_username_blockchain_true(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"found": True})
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)

        result = await IdentityAnnouncement.exists_username("taken", config=cfg)
        self.assertTrue(result)

    async def test_exists_username_mempool_true(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value={"found": True}
        )

        result = await IdentityAnnouncement.exists_username("taken", config=cfg)
        self.assertTrue(result)

    async def test_get_by_username_no_mempool(self):
        import yadacoin.core.config
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()

        async def _empty_agg(pipeline):
            return
            yield  # pragma: no cover

        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=_empty_agg(None))
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)
        yadacoin.core.config.CONFIG = cfg

        with patch("yadacoin.core.config.Config", return_value=cfg):
            result = await IdentityAnnouncement.get_by_username(
                "nobody", include_mempool=False
            )
        self.assertIsNone(result)
        cfg.mongo.async_db.miner_transactions.find_one.assert_not_awaited()

    async def test_get_by_username_blockchain_hit(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()

        chain_doc = {
            "public_key": _PUB_HEX,
            "relationship": {"identity": {"username": "mynode"}},
            "id": "txn123",
        }

        async def _agg(pipeline):
            yield chain_doc

        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=_agg(None))

        with patch("yadacoin.core.config.Config", return_value=cfg):
            result = await IdentityAnnouncement.get_by_username("mynode")
        self.assertIsNotNone(result)
        self.assertEqual(result["public_key"], _PUB_HEX)
        self.assertEqual(result["source"], "blockchain")

    async def test_exists_username_with_exclude(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)

        result = await IdentityAnnouncement.exists_username(
            "taken", exclude_txn_sig="txn_to_skip", config=cfg
        )
        self.assertFalse(result)
        # verify exclude_txn_sig was forwarded in the query
        call_args = cfg.mongo.async_db.blocks.find_one.await_args
        self.assertIn("$ne", str(call_args))

    async def test_exists_username_uses_config_instance_when_none(self):
        """When config=None, exists_username instantiates Config() internally."""
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)

        with patch("yadacoin.core.config.Config", return_value=cfg):
            result = await IdentityAnnouncement.exists_username("nobody")
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# RotationAnnouncement
# ---------------------------------------------------------------------------


class TestRotationAnnouncementInit(unittest.TestCase):
    def test_valid_secp256k1_construction(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        ra = RotationAnnouncement(curve="secp256k1")
        self.assertEqual(ra.curve, "secp256k1")

    def test_unsupported_curve_raises(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        with self.assertRaises(ValueError):
            RotationAnnouncement(curve="ed25519")

    def test_to_dict_includes_optional_fields(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        ra = RotationAnnouncement(
            curve="secp256r1",
            public_key="0400",
            key_hash="1abc",
            dtls_fingerprint="sha-256:AA:BB",
        )
        d = ra.to_dict()
        self.assertEqual(d["curve"], "secp256r1")
        self.assertEqual(d["public_key"], "0400")
        self.assertEqual(d["key_hash"], "1abc")
        self.assertEqual(d["dtls_fingerprint"], "sha-256:AA:BB")

    def test_to_string_contains_rotation_key(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        ra = RotationAnnouncement(curve="secp256k1")
        s = ra.to_string()
        self.assertIn('"rotation"', s)

    def test_to_relationship(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        ra = RotationAnnouncement(curve="secp256k1")
        rel = ra.to_relationship()
        self.assertIn("rotation", rel)

    def test_from_dict_non_dict_raises(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        with self.assertRaises(ValueError):
            RotationAnnouncement.from_dict("bad")

    def test_from_dict_valid(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        ra = RotationAnnouncement.from_dict({"curve": "secp256k1"})
        self.assertEqual(ra.curve, "secp256k1")

    def test_from_relationship_missing_key_raises(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        with self.assertRaises(ValueError):
            RotationAnnouncement.from_relationship({"other": {}})

    def test_from_relationship_valid(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        ra = RotationAnnouncement.from_relationship(
            {"rotation": {"curve": "secp256k1"}}
        )
        self.assertEqual(ra.curve, "secp256k1")

    def test_validate_p256_secp256k1_returns_true(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        ra = RotationAnnouncement(curve="secp256k1")
        self.assertTrue(ra.validate_p256())

    def test_validate_p256_missing_public_key_raises(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        ra = RotationAnnouncement(curve="secp256r1", public_key="")
        with self.assertRaises(ValueError):
            ra.validate_p256()

    def test_validate_p256_invalid_hex_raises(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        ra = RotationAnnouncement(curve="secp256r1", public_key="ZZZZ")
        with self.assertRaises(ValueError):
            ra.validate_p256()

    def test_validate_p256_wrong_key_hash_raises(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        # Use a real compressed secp256k1 pubkey as a stand-in for bytes
        pub_hex = _PUB_HEX  # 33-byte compressed key
        ra = RotationAnnouncement(
            curve="secp256r1", public_key=pub_hex, key_hash="1WRONGHASH"
        )
        with self.assertRaises(ValueError):
            ra.validate_p256()

    def test_validate_p256_correct_key_hash_passes(self):
        from bitcoin.wallet import P2PKHBitcoinAddress

        from yadacoin.core.identityannouncement import RotationAnnouncement

        pub_bytes = bytes.fromhex(_PUB_HEX)
        expected = str(P2PKHBitcoinAddress.from_pubkey(pub_bytes))
        ra = RotationAnnouncement(
            curve="secp256r1", public_key=_PUB_HEX, key_hash=expected
        )
        self.assertTrue(ra.validate_p256())


class TestDerivep256FromK0(unittest.TestCase):
    def test_returns_rotation_announcement(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        priv = bytes.fromhex(_PRIV_HEX)
        ra = RotationAnnouncement.derive_p256_from_k0(priv)
        self.assertIsInstance(ra, RotationAnnouncement)
        self.assertEqual(ra.curve, "secp256r1")
        self.assertTrue(ra.public_key.startswith("04"))
        self.assertTrue(ra.dtls_fingerprint.startswith("sha-256:"))

    def test_deterministic(self):
        from yadacoin.core.identityannouncement import RotationAnnouncement

        priv = bytes.fromhex(_PRIV_HEX)
        ra1 = RotationAnnouncement.derive_p256_from_k0(priv)
        ra2 = RotationAnnouncement.derive_p256_from_k0(priv)
        self.assertEqual(ra1.public_key, ra2.public_key)
        self.assertEqual(ra1.key_hash, ra2.key_hash)


class TestIdentityAnnouncementFromRelationshipWithRotation(unittest.TestCase):
    def test_from_relationship_parses_rotation_sibling(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        sig = _make_valid_sig("mynode", _PRIV_HEX)
        rel = {
            "identity": {
                "username": "mynode",
                "username_signature": sig,
                "host": "1.2.3.4",
                "port": 8000,
            },
            "rotation": {"curve": "secp256k1"},
        }
        ia = IdentityAnnouncement.from_relationship(rel)
        self.assertIsNotNone(ia.rotation)
        self.assertEqual(ia.rotation.curve, "secp256k1")

    def test_from_relationship_invalid_rotation_ignored(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        sig = _make_valid_sig("mynode", _PRIV_HEX)
        rel = {
            "identity": {
                "username": "mynode",
                "username_signature": sig,
                "host": "1.2.3.4",
                "port": 8000,
            },
            "rotation": "bad_value",  # not a dict — should be ignored
        }
        ia = IdentityAnnouncement.from_relationship(rel)
        self.assertIsNone(ia.rotation)
