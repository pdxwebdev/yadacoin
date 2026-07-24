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
    """Produce a real username_signature for tests (signs username with priv)."""
    import base64

    from coincurve import PrivateKey

    key = PrivateKey.from_hex(priv_hex)
    return base64.b64encode(key.sign(username.encode("utf-8"))).decode()


class TestIdentityAnnouncementInit(unittest.TestCase):
    def test_blank_username_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement(username="", username_signature="sig")

    def test_whitespace_username_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement(username="   ", username_signature="sig")

    def test_missing_username_signature_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement(username="u", username_signature="")

    def test_invalid_identity_type_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement(
                username="u", username_signature="sig", identity_type="bogus"
            )

    def test_valid_construction_defaults_to_dns(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        # A valid lower-case DNS domain keeps the default "dns" identity type.
        ia = IdentityAnnouncement(username="node.example.com", username_signature="SIG")
        self.assertEqual(ia.username, "node.example.com")
        self.assertEqual(ia.username_signature, "SIG")
        self.assertEqual(ia.identity_type, "dns")

    def test_explicit_social_identity_type(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        ia = IdentityAnnouncement(
            username="MyHandle", username_signature="SIG", identity_type="social"
        )
        self.assertEqual(ia.identity_type, "social")

    def test_explicit_ipfs_identity_type(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        ia = IdentityAnnouncement(
            username="Qm123", username_signature="SIG", identity_type="ipfs"
        )
        self.assertEqual(ia.identity_type, "ipfs")


class TestIdentityAnnouncementDnsCoercion(unittest.TestCase):
    """A ``dns`` identity whose username is not a valid lower-case domain must
    be downgraded to ``social``."""

    def _assert_coerced(self, username):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        ia = IdentityAnnouncement(username=username, username_signature="SIG")
        self.assertEqual(ia.identity_type, "social")

    def test_uppercase_domain_coerced_to_social(self):
        self._assert_coerced("CenterIdentity.com")

    def test_no_dot_domain_coerced_to_social(self):
        self._assert_coerced("foobar")

    def test_leading_hyphen_domain_coerced_to_social(self):
        self._assert_coerced("-bad.example.com")

    def test_single_char_tld_coerced_to_social(self):
        self._assert_coerced("example.c")

    def test_valid_dns_domain_stays_dns(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        for username in ("centeridentity.com", "a.b.c.example.io", "sub.example.co.uk"):
            ia = IdentityAnnouncement(username=username, username_signature="SIG")
            self.assertEqual(ia.identity_type, "dns", username)


class TestIsValidDnsUsername(unittest.TestCase):
    def test_valid_domains(self):
        from yadacoin.core.identityannouncement import is_valid_dns_username

        for username in (
            "centeridentity.com",
            "a.b.c.example.io",
            "sub.example.co.uk",
            "example.io",
        ):
            self.assertTrue(is_valid_dns_username(username), username)

    def test_invalid_domains(self):
        from yadacoin.core.identityannouncement import is_valid_dns_username

        for username in (
            "",
            "   ",
            "CenterIdentity.com",  # upper-case
            "foobar",  # no dot
            "-bad.example.com",  # leading hyphen
            "my_name.example.com",  # underscore
            "example.c",  # single-char TLD
            "a" * 70 + ".com",  # label too long
        ):
            self.assertFalse(is_valid_dns_username(username), username)


class TestIdentityAnnouncementSerialisation(unittest.TestCase):
    def _make(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        return IdentityAnnouncement(
            username="n1.example.com",
            username_signature="SIG",
            identity_type="dns",
        )

    def test_to_dict_round_trip(self):
        ia = self._make()
        d = ia.to_dict()
        ia2 = type(ia).from_dict(d)
        self.assertEqual(ia2.username, ia.username)
        self.assertEqual(ia2.username_signature, ia.username_signature)
        self.assertEqual(ia2.identity_type, ia.identity_type)

    def test_to_dict_contains_identity_fields(self):
        d = self._make().to_dict()
        self.assertEqual(d["username"], "n1.example.com")
        self.assertEqual(d["username_signature"], "SIG")
        self.assertEqual(d["identity_type"], "dns")

    def test_to_string_contains_fields(self):
        s = self._make().to_string()
        self.assertIn("n1", s)
        self.assertIn("SIG", s)
        self.assertIn("dns", s)

    def test_from_dict_missing_field_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement.from_dict({"username": "u"})

    def test_from_relationship_no_key_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement.from_relationship({"other": {}})

    def test_from_relationship_parses_identity(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        rel = {"identity": {"username": "n1", "username_signature": "SIG"}}
        ia = IdentityAnnouncement.from_relationship(rel)
        self.assertEqual(ia.username, "n1")

    def test_from_dict_non_dict_raises(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        with self.assertRaises(ValueError):
            IdentityAnnouncement.from_dict("not a dict")


class TestIdentityAnnouncementVerifySignature(unittest.TestCase):
    def test_valid_signature(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        sig = _make_valid_sig("mynode", _PRIV_HEX)
        ia = IdentityAnnouncement(username="mynode", username_signature=sig)
        self.assertTrue(ia.verify_username_signature(_PUB_HEX))

    def test_wrong_public_key_fails(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        ia = IdentityAnnouncement(username="mynode", username_signature="invalidsig")
        self.assertFalse(ia.verify_username_signature(_PUB_HEX))

    def test_invalid_sig_bytes_returns_false(self):
        import base64

        from yadacoin.core.identityannouncement import IdentityAnnouncement

        ia = IdentityAnnouncement(
            username="mynode",
            username_signature=base64.b64encode(b"\x00" * 5).decode(),
        )
        self.assertFalse(ia.verify_username_signature(_PUB_HEX))


class TestIdentityAnnouncementChainLookup(AsyncTestCase):
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

    async def test_get_by_transaction_id_mempool_hit(self):
        import yadacoin.core.config
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        mempool_doc = {
            "id": "txn123",
            "public_key": _PUB_HEX,
            "relationship": {"identity": {"username": "mynode"}},
        }
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value=mempool_doc
        )
        yadacoin.core.config.CONFIG = cfg

        with patch("yadacoin.core.config.Config", return_value=cfg):
            result = await IdentityAnnouncement.get_by_transaction_id("txn123")
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "mempool")
        self.assertEqual(result["public_key"], _PUB_HEX)

    async def test_get_by_transaction_id_not_found(self):
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
            result = await IdentityAnnouncement.get_by_transaction_id("nope")
        self.assertIsNone(result)

    async def test_get_by_transaction_id_not_found_excluded(self):
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
            result = await IdentityAnnouncement.get_by_transaction_id(
                "nope", include_mempool=False
            )
        self.assertIsNone(result)

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
        query = cfg.mongo.async_db.blocks.find_one.await_args[0][0]
        self.assertNotIn("index", query)

    async def test_exists_username_below_index_scopes_chain_query(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)

        result = await IdentityAnnouncement.exists_username(
            "taken", config=cfg, use_mempool=False, below_index=605133
        )
        self.assertFalse(result)
        query = cfg.mongo.async_db.blocks.find_one.await_args[0][0]
        self.assertEqual(query["index"], {"$lt": 605133})

    async def test_exists_username_batch_txns_true(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)

        ann = IdentityAnnouncement(
            username="taken.example",
            username_signature=_make_valid_sig("taken.example", _PRIV_HEX),
        )
        sibling = MagicMock()
        sibling.relationship = ann
        sibling.transaction_signature = "other_sig"

        result = await IdentityAnnouncement.exists_username(
            "taken.example",
            config=cfg,
            use_mempool=False,
            below_index=100,
            batch_txns=[sibling],
        )
        self.assertTrue(result)

    async def test_exists_username_batch_txns_exclude_self(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)

        ann = IdentityAnnouncement(
            username="taken.example",
            username_signature=_make_valid_sig("taken.example", _PRIV_HEX),
        )
        self_txn = MagicMock()
        self_txn.relationship = ann
        self_txn.transaction_signature = "self_sig"

        result = await IdentityAnnouncement.exists_username(
            "taken.example",
            exclude_txn_sig="self_sig",
            config=cfg,
            use_mempool=False,
            below_index=100,
            batch_txns=[self_txn],
        )
        self.assertFalse(result)

    async def test_exists_username_below_index_ignores_same_or_higher_chain_hit(self):
        """Chain docs at/above below_index must not count (query uses $lt)."""
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()

        # Simulate mongo honoring $lt by returning None when index filter present
        async def _find_one(query, *args, **kwargs):
            if "index" in query and query["index"].get("$lt") == 200:
                return None
            return {"found": True}

        cfg.mongo.async_db.blocks.find_one = AsyncMock(side_effect=_find_one)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)

        result = await IdentityAnnouncement.exists_username(
            "taken", config=cfg, use_mempool=False, below_index=200
        )
        self.assertFalse(result)

    async def test_exists_username_mempool_true(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value={"found": True}
        )

        result = await IdentityAnnouncement.exists_username(
            "taken", config=cfg, use_mempool=True
        )
        self.assertTrue(result)

    async def test_exists_username_extra_blocks_true(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)

        ann = IdentityAnnouncement(
            username="taken.example",
            username_signature=_make_valid_sig("taken.example", _PRIV_HEX),
        )
        txn = MagicMock()
        txn.relationship = ann
        txn.transaction_signature = "other_sig"
        block = MagicMock()
        block.transactions = [txn]

        result = await IdentityAnnouncement.exists_username(
            "taken.example", config=cfg, use_mempool=False, extra_blocks=[block]
        )
        self.assertTrue(result)

    async def test_exists_username_extra_blocks_exclude_sig(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)

        ann = IdentityAnnouncement(
            username="taken.example",
            username_signature=_make_valid_sig("taken.example", _PRIV_HEX),
        )
        txn = MagicMock()
        txn.relationship = ann
        txn.transaction_signature = "skip_me"
        block = MagicMock()
        block.transactions = [txn]

        result = await IdentityAnnouncement.exists_username(
            "taken.example",
            exclude_txn_sig="skip_me",
            config=cfg,
            use_mempool=False,
            extra_blocks=[block],
        )
        self.assertFalse(result)

    async def test_exists_username_mempool_with_exclude(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)

        result = await IdentityAnnouncement.exists_username(
            "taken",
            exclude_txn_sig="txn_to_skip",
            config=cfg,
            use_mempool=True,
        )
        self.assertFalse(result)
        call_args = cfg.mongo.async_db.miner_transactions.find_one.await_args
        self.assertIn("$ne", str(call_args))

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

    async def test_txn_claims_username_dict_relationship(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        txn = MagicMock()
        txn.transaction_signature = "x"
        txn.relationship = {"identity": {"username": "alice.example"}}
        self.assertTrue(IdentityAnnouncement._txn_claims_username(txn, "alice.example"))
        self.assertFalse(IdentityAnnouncement._txn_claims_username(txn, "bob.example"))

    async def test_txn_claims_username_dict_with_relationship_key(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        txn = MagicMock()
        txn.transaction_signature = "x"
        txn.relationship = {
            IdentityAnnouncement.RELATIONSHIP_KEY: {"username": "alice.example"}
        }
        self.assertTrue(IdentityAnnouncement._txn_claims_username(txn, "alice.example"))

    async def test_txn_claims_username_non_identity_false(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        txn = MagicMock()
        txn.transaction_signature = "x"
        txn.relationship = "not-an-identity"
        self.assertFalse(
            IdentityAnnouncement._txn_claims_username(txn, "alice.example")
        )

    async def test_get_by_transaction_id_blockchain_hit(self):
        import yadacoin.core.config
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)
        chain_doc = {
            "public_key": _PUB_HEX,
            "relationship": {"identity": {"username": "mynode"}},
        }

        async def _agg(pipeline):
            yield chain_doc

        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=_agg(None))
        yadacoin.core.config.CONFIG = cfg

        with patch("yadacoin.core.config.Config", return_value=cfg):
            result = await IdentityAnnouncement.get_by_transaction_id("txn123")
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "blockchain")

    def test_get_string_coerces_int_and_none(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        self.assertEqual(IdentityAnnouncement.get_string(5), "5")
        self.assertEqual(IdentityAnnouncement.get_string(None), "")


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)


class TestIdentityAnnouncementVerifyAsync(AsyncTestCase):
    async def test_verify_success(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        ann = IdentityAnnouncement(
            username="ok.example",
            username_signature=_make_valid_sig("ok.example", _PRIV_HEX),
        )
        cfg = MagicMock()
        cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.exists_username",
            new=AsyncMock(return_value=False),
        ) as exists:
            await ann.verify(_PUB_HEX, below_index=10, batch_txns=[], use_mempool=False)
            exists.assert_awaited()
            kwargs = exists.await_args.kwargs
            self.assertEqual(kwargs["below_index"], 10)
            self.assertEqual(kwargs["batch_txns"], [])
            self.assertFalse(kwargs["use_mempool"])

    async def test_verify_bad_signature(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement
        from yadacoin.core.transaction import InvalidTransactionException

        ann = IdentityAnnouncement(
            username="ok.example",
            username_signature=_make_valid_sig("ok.example", _PRIV_HEX),
        )
        with self.assertRaises(InvalidTransactionException):
            await ann.verify("00" * 33)

    async def test_verify_blank_username(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement
        from yadacoin.core.transaction import InvalidTransactionException

        ann = IdentityAnnouncement(
            username="ok.example",
            username_signature=_make_valid_sig("ok.example", _PRIV_HEX),
        )
        ann.username = ""
        with patch.object(ann, "verify_username_signature", return_value=True):
            with self.assertRaises(InvalidTransactionException) as ctx:
                await ann.verify(_PUB_HEX)
        self.assertIn("blank", str(ctx.exception).lower())

    async def test_verify_invalid_dns_username(self):
        from yadacoin.core.identityannouncement import (
            IdentityAnnouncement,
            IdentityType,
        )
        from yadacoin.core.transaction import InvalidTransactionException

        ann = IdentityAnnouncement(
            username="not a domain",
            username_signature=_make_valid_sig("not a domain", _PRIV_HEX),
            identity_type=IdentityType.SOCIAL.value,
        )
        ann.identity_type = IdentityType.DNS.value
        with self.assertRaises(InvalidTransactionException):
            await ann.verify(_PUB_HEX)

    async def test_verify_username_already_claimed(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement
        from yadacoin.core.transaction import InvalidTransactionException

        ann = IdentityAnnouncement(
            username="ok.example",
            username_signature=_make_valid_sig("ok.example", _PRIV_HEX),
        )
        with patch(
            "yadacoin.core.identityannouncement.IdentityAnnouncement.exists_username",
            new=AsyncMock(return_value=True),
        ):
            with self.assertRaises(InvalidTransactionException):
                await ann.verify(_PUB_HEX)
