"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import hashlib
import unittest
from logging import getLogger
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.config import Config, EmailConfig, SSLConfig

from ..test_setup import AsyncTestCase


def _ripemd160_available():
    try:
        hashlib.new("ripemd160")
        return True
    except (ValueError, Exception):
        return False


_HAS_RIPEMD160 = _ripemd160_available()


class ConfigTestCase(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        config = Config()
        if not hasattr(config, "app_log"):
            config.app_log = getLogger("tornado.application")
        self.config = config


# ---------------------------------------------------------------------------
# Config.address_is_valid
# ---------------------------------------------------------------------------


class TestAddressIsValid(unittest.TestCase):
    def test_valid_address(self):
        # P2PKH mainnet address that is base58check valid
        from bitcoin.wallet import P2PKHBitcoinAddress
        from coincurve.keys import PrivateKey

        key = PrivateKey()
        pub = key.public_key.format().hex()
        addr = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(pub)))
        self.assertTrue(Config.address_is_valid(addr))

    def test_invalid_address_short(self):
        self.assertFalse(Config.address_is_valid("abc"))

    def test_invalid_address_bad_checksum(self):
        # valid-looking base58 but wrong checksum
        self.assertFalse(Config.address_is_valid("1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf9"))

    def test_empty_string_returns_false(self):
        self.assertFalse(Config.address_is_valid(""))

    def test_non_string_returns_false(self):
        self.assertFalse(Config.address_is_valid(None))


# ---------------------------------------------------------------------------
# Config.generate_wif / Config.to_wif
# ---------------------------------------------------------------------------


class TestWIF(ConfigTestCase):
    async def test_generate_wif_returns_string(self):
        wif = Config.generate_wif(self.config.private_key)
        self.assertIsInstance(wif, str)
        self.assertGreater(len(wif), 0)

    async def test_to_wif_returns_same_as_generate_wif(self):
        wif_instance = self.config.to_wif(self.config.private_key)
        wif_class = Config.generate_wif(self.config.private_key)
        self.assertEqual(wif_instance, wif_class)

    async def test_wif_starts_with_k_or_l(self):
        wif = Config.generate_wif(self.config.private_key)
        # Compressed WIF starts with K or L (compressed) or 5 (uncompressed)
        self.assertIn(wif[0], ("K", "L", "5"))


# ---------------------------------------------------------------------------
# Config.get_username_signature
# ---------------------------------------------------------------------------


class TestGetUsernameSignature(ConfigTestCase):
    async def test_returns_base64_string(self):
        sig = self.config.get_username_signature()
        import base64

        decoded = base64.b64decode(sig)
        self.assertGreater(len(decoded), 0)

    async def test_deterministic_for_same_inputs(self):
        sig1 = self.config.get_username_signature()
        sig2 = self.config.get_username_signature()
        self.assertEqual(sig1, sig2)


# ---------------------------------------------------------------------------
# Config.get_identity
# ---------------------------------------------------------------------------


class TestGetIdentity(ConfigTestCase):
    async def test_returns_dict_with_required_keys(self):
        identity = self.config.get_identity()
        self.assertIn("username", identity)
        self.assertIn("username_signature", identity)
        self.assertIn("public_key", identity)

    async def test_public_key_matches_config(self):
        identity = self.config.get_identity()
        self.assertEqual(identity["public_key"], self.config.public_key)


# ---------------------------------------------------------------------------
# Config.to_dict / to_json
# ---------------------------------------------------------------------------


class TestToDict(ConfigTestCase):
    async def test_to_dict_has_required_keys(self):
        d = self.config.to_dict()
        for key in ["public_key", "address", "mongodb_host", "network", "database"]:
            self.assertIn(key, d)

    async def test_to_dict_no_sensitive_by_default(self):
        d = self.config.to_dict()
        self.assertNotIn("private_key", d)
        self.assertNotIn("wif", d)

    async def test_to_dict_with_sensitive(self):
        d = self.config.to_dict(include_sensitive=True)
        self.assertIn("private_key", d)
        self.assertIn("wif", d)

    async def test_to_json_is_valid_json(self):
        import json

        j = self.config.to_json()
        parsed = json.loads(j)
        self.assertIn("public_key", parsed)


# ---------------------------------------------------------------------------
# EmailConfig
# ---------------------------------------------------------------------------


class TestEmailConfig(unittest.TestCase):
    def test_from_dict_with_valid_dict(self):
        ec = EmailConfig.from_dict(
            {
                "username": "u@test.com",
                "password": "pass",
                "smtp_server": "smtp.test.com",
                "smtp_port": 587,
            }
        )
        self.assertEqual(ec.username, "u@test.com")
        self.assertEqual(ec.smtp_port, 587)

    def test_from_dict_with_empty_dict(self):
        ec = EmailConfig.from_dict({})
        self.assertIsNone(ec.username)

    def test_from_dict_with_none(self):
        ec = EmailConfig.from_dict(None)
        self.assertIsNone(ec.username)

    def test_is_valid_true_when_all_set(self):
        ec = EmailConfig()
        ec.username = "u"
        ec.password = "p"
        ec.smtp_server = "smtp.test.com"
        ec.smtp_port = 587
        self.assertTrue(ec.is_valid())

    def test_is_valid_false_when_missing_field(self):
        ec = EmailConfig()
        ec.username = "u"
        ec.password = "p"
        ec.smtp_server = "smtp.test.com"
        ec.smtp_port = None
        self.assertFalse(ec.is_valid())

    def test_to_dict_has_required_keys(self):
        ec = EmailConfig.from_dict(
            {
                "username": "u",
                "password": "p",
                "smtp_server": "s",
                "smtp_port": 465,
            }
        )
        d = ec.to_dict()
        self.assertIn("username", d)
        self.assertIn("smtp_server", d)
        self.assertIn("smtp_port", d)


# ---------------------------------------------------------------------------
# SSLConfig
# ---------------------------------------------------------------------------


class TestSSLConfig(unittest.TestCase):
    def test_from_dict_with_valid_dict(self):
        sc = SSLConfig.from_dict(
            {
                "cafile": "/path/ca.crt",
                "certfile": "/path/cert.pem",
                "keyfile": "/path/key.pem",
                "port": 443,
                "common_name": "example.com",
            }
        )
        self.assertEqual(sc.ca_file, "/path/ca.crt")
        self.assertEqual(sc.port, 443)
        self.assertEqual(sc.common_name, "example.com")

    def test_from_dict_with_none(self):
        sc = SSLConfig.from_dict(None)
        self.assertIsNone(sc.ca_file)

    def test_from_dict_with_empty_dict(self):
        sc = SSLConfig.from_dict({})
        self.assertIsNone(sc.ca_file)

    def test_is_valid_true_when_all_set(self):
        sc = SSLConfig()
        sc.ca_file = "/ca.crt"
        sc.cert_file = "/cert.pem"
        sc.key_file = "/key.pem"
        sc.port = 443
        self.assertTrue(sc.is_valid())

    def test_is_valid_false_when_missing_field(self):
        sc = SSLConfig()
        sc.ca_file = "/ca.crt"
        sc.cert_file = "/cert.pem"
        sc.key_file = ""
        sc.port = 443
        self.assertFalse(sc.is_valid())

    def test_to_dict_has_keys(self):
        sc = SSLConfig.from_dict(
            {
                "cafile": "ca",
                "certfile": "cert",
                "keyfile": "key",
                "port": 443,
            }
        )
        d = sc.to_dict()
        self.assertIn("cafile", d)
        self.assertIn("certfile", d)
        self.assertIn("keyfile", d)
        self.assertIn("port", d)


# ---------------------------------------------------------------------------
# Config singleton behavior
# ---------------------------------------------------------------------------


class TestConfigSingleton(ConfigTestCase):
    async def test_same_instance_returned(self):
        c1 = Config()
        c2 = Config()
        self.assertIs(c1, c2)

    async def test_initialized_flag_set(self):
        self.assertTrue(hasattr(self.config, "initialized"))


# ---------------------------------------------------------------------------
# get_price_at_time (mocked)
# ---------------------------------------------------------------------------


class TestGetPriceAtTime(ConfigTestCase):
    async def test_returns_lte_and_gte_prices(self):
        mock_site_db = MagicMock()
        mock_site_db.coingecko_spot_rates.find_one = AsyncMock(
            side_effect=[
                {"yadacoin": {"usd": 0.5}, "time": 1000},
                {"yadacoin": {"usd": 0.6}, "time": 2000},
            ]
        )
        with patch.object(
            self.config.mongo, "async_site_db", new=mock_site_db, create=True
        ):
            lte_price, gte_price = await self.config.get_price_at_time(1500)
        self.assertAlmostEqual(lte_price, 0.5)
        self.assertAlmostEqual(gte_price, 0.6)


# ---------------------------------------------------------------------------
# get_highest_price / get_lowest_price (mocked)
# ---------------------------------------------------------------------------


class TestPriceMethods(ConfigTestCase):
    async def test_get_highest_price_returns_max(self):
        rates = [
            {"yadacoin": {"usd": 0.5}, "time": 1000},
            {"yadacoin": {"usd": 1.2}, "time": 1001},
            {"yadacoin": {"usd": 0.8}, "time": 1002},
        ]

        async def rate_iter():
            for r in rates:
                yield r

        mock_site_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: rate_iter()
        mock_site_db.coingecko_spot_rates.find.return_value = mock_cursor

        with patch.object(
            self.config.mongo, "async_site_db", new=mock_site_db, create=True
        ):
            result = await self.config.get_highest_price()
        self.assertAlmostEqual(result, 1.2)

    async def test_get_lowest_price_returns_min(self):
        rates = [
            {"yadacoin": {"usd": 0.5}, "time": 1000},
            {"yadacoin": {"usd": 0.2}, "time": 1001},
            {"yadacoin": {"usd": 0.8}, "time": 1002},
        ]

        async def rate_iter():
            for r in rates:
                yield r

        mock_site_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: rate_iter()
        mock_site_db.coingecko_spot_rates.find.return_value = mock_cursor

        with patch.object(
            self.config.mongo, "async_site_db", new=mock_site_db, create=True
        ):
            result = await self.config.get_lowest_price()
        self.assertAlmostEqual(result, 0.2)

    async def test_get_highest_price_returns_none_when_no_rates(self):
        async def empty_iter():
            return
            yield

        mock_site_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = lambda self: empty_iter()
        mock_site_db.coingecko_spot_rates.find.return_value = mock_cursor

        with patch.object(
            self.config.mongo, "async_site_db", new=mock_site_db, create=True
        ):
            result = await self.config.get_highest_price()
        self.assertIsNone(result)

    async def test_on_new_block_calls_set_latest_block(self):
        """Lines 193-194: covers block.to_dict() and BU.set_latest_block() calls."""
        mock_block = MagicMock()
        mock_block.to_dict.return_value = {"index": 100}
        mock_bu = MagicMock()
        self.config.BU = mock_bu
        self.config.mp = None

        await self.config.on_new_block(mock_block)

        mock_block.to_dict.assert_called_once()
        mock_bu.set_latest_block.assert_called_once_with({"index": 100})

    async def test_on_new_block_with_mp_calls_refresh(self):
        """Line 202: await self.mp.refresh() branch."""
        mock_block = MagicMock()
        mock_block.to_dict.return_value = {"index": 100}
        self.config.BU = MagicMock()
        mp = MagicMock()
        mp.refresh = AsyncMock()
        prev = self.config.mp
        self.config.mp = mp
        try:
            await self.config.on_new_block(mock_block)
            mp.refresh.assert_awaited_once()
        finally:
            self.config.mp = prev


# ---------------------------------------------------------------------------
# Config.__init__ peer_host validation (lines 87, 91, 95)
# ---------------------------------------------------------------------------


def _build_init_config(peer_host):
    """Minimum config required to drive Config.__init__ to peer_host validation."""
    return {
        "modes": ["node"],
        "public_key": "021487409d61f795be71d51f3af9b23fb08f024b51888af52edb1ad4a191c888c4",
        "private_key": "3bb355f8fff1b894320fb5764b3f16e3395d37493b87cb5889e517e0d474376a",
        "username": "",
        "mongodb_host": "localhost",
        "database": "yadacoindddddd",
        "site_database": "yadacoinsite",
        "peer_host": peer_host,
        "peer_port": 8000,
        "serve_host": "0.0.0.0",
        "serve_port": 8001,
        "callbackurl": "http://0.0.0.0:8001/create-relationship",
        "fcm_key": "",
    }


class TestConfigInitPeerHostValidation(unittest.TestCase):
    def _fresh_init(self, cfg):
        # Bypass the singleton by creating a raw object and invoking __init__.
        fake = object.__new__(Config)
        Config.__init__(fake, cfg)

    def test_localhost_raises(self):
        with self.assertRaises(Exception) as ctx:
            self._fresh_init(_build_init_config("localhost"))
        self.assertIn("localhost", str(ctx.exception))

    def test_zero_ip_raises(self):
        with self.assertRaises(Exception) as ctx:
            self._fresh_init(_build_init_config("0.0.0.0"))
        self.assertIn("localhost", str(ctx.exception).lower() + str(ctx.exception))

    def test_placeholder_raises(self):
        with self.assertRaises(Exception) as ctx:
            self._fresh_init(_build_init_config("[my public ip]"))
        self.assertIn("public ipv4", str(ctx.exception))

    def test_ipv6_raises(self):
        with self.assertRaises(Exception) as ctx:
            self._fresh_init(_build_init_config("2600:387:15:241b::4"))
        self.assertIn("IPv6", str(ctx.exception))


# ---------------------------------------------------------------------------
# Config.__init__ combined_address override (line 202 path of __init__ — actually
# captures the explicit-value branch of `combined_address = config.get(..., self.address)`).
# ---------------------------------------------------------------------------


class TestConfigInitCombinedAddress(unittest.TestCase):
    def test_combined_address_uses_explicit_value(self):
        cfg = _build_init_config("70.166.222.226")
        cfg["combined_address"] = "1ExplicitAddress"
        fake = object.__new__(Config)
        Config.__init__(fake, cfg)
        self.assertEqual(fake.combined_address, "1ExplicitAddress")


# ---------------------------------------------------------------------------
# Config.get_status (lines 205-248)
# ---------------------------------------------------------------------------


class TestGetStatus(ConfigTestCase):
    def _make_streams(self):
        # Returns nodeServer-like, websocketServer-like, nodeClient-like mocks.
        ws = MagicMock()
        ws.inbound_streams = {"a": [1, 2], "b": [3]}
        ws.inbound_pending = {"a": [4]}
        ns = MagicMock()
        ns.inbound_streams = {"k": [10]}
        ns.inbound_pending = {"k": [11, 12]}
        nc = MagicMock()
        nc.outbound_streams = {"k": [20]}
        nc.outbound_ignore = {"k": [21]}
        nc.outbound_pending = {"k": [22, 23]}
        return ws, ns, nc

    async def test_get_status_without_pool_server(self):
        ws, ns, nc = self._make_streams()
        latest_block = MagicMock()
        latest_block.block.index = 42
        with patch.object(
            self.config, "websocketServer", ws, create=True
        ), patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ), patch.object(
            self.config, "LatestBlock", latest_block, create=True
        ):
            status = await self.config.get_status()
        self.assertEqual(status["pool"], "N/A")
        self.assertEqual(status["height"], 42)
        self.assertEqual(status["websocket_inbound_peers"], 3)
        self.assertEqual(status["websocket_inbound_pending"], 1)
        self.assertEqual(status["inbound_peers"], 1)
        self.assertEqual(status["inbound_pending"], 2)
        self.assertEqual(status["outbound_peers"], 1)
        self.assertEqual(status["outbound_ignore"], 1)
        self.assertEqual(status["outbound_pending"], 2)
        self.assertIn("uptime", status)

    async def test_get_status_with_pool_server(self):
        ws, ns, nc = self._make_streams()
        latest_block = MagicMock()
        latest_block.block.index = 1
        ps = MagicMock()
        ps.status = AsyncMock(return_value="OK")
        with patch.object(
            self.config, "websocketServer", ws, create=True
        ), patch.object(self.config, "nodeServer", ns, create=True), patch.object(
            self.config, "nodeClient", nc, create=True
        ), patch.object(
            self.config, "LatestBlock", latest_block, create=True
        ), patch.object(
            self.config, "pool_server", ps, create=True
        ):
            status = await self.config.get_status()
        self.assertEqual(status["pool"], "OK")


# ---------------------------------------------------------------------------
# Config.generate (lines 287-291, 294-302, 305-313, 333, 335-336)
# ---------------------------------------------------------------------------


class TestGenerateBranches(unittest.TestCase):
    def _patch_urlopen(self, ip):
        m = MagicMock()
        m.read.return_value = ip.encode()
        cm = MagicMock()
        cm.__enter__ = lambda self: m
        cm.__exit__ = lambda *a: None
        return patch("urllib.request.urlopen", return_value=m)

    def test_generate_with_prv(self):
        # Use the test config private key.
        prv = "3bb355f8fff1b894320fb5764b3f16e3395d37493b87cb5889e517e0d474376a"
        with self._patch_urlopen("70.166.222.226"):
            result = Config.generate(prv=prv)
        self.assertIsInstance(result, Config)

    def test_generate_with_xprv(self):
        xprv = "xprv9s21ZrQH143K2aPGPoRFW3xS379ajgDFzPtPd1Er3UMtVRexjWgf7nHRjsJMD9msDmudJv1C2wduLTtBNuLipjKdUBxiv6sJ8UQq5v7BDHL"
        with self._patch_urlopen("70.166.222.226"):
            result = Config.generate(xprv=xprv)
        self.assertIsInstance(result, Config)

    def test_generate_with_xprv_and_child(self):
        if not _HAS_RIPEMD160:
            self.skipTest("ripemd160 not available in this OpenSSL build")
        xprv = "xprv9s21ZrQH143K2aPGPoRFW3xS379ajgDFzPtPd1Er3UMtVRexjWgf7nHRjsJMD9msDmudJv1C2wduLTtBNuLipjKdUBxiv6sJ8UQq5v7BDHL"
        with self._patch_urlopen("70.166.222.226"):
            result = Config.generate(xprv=xprv, child=[0, 1])
        self.assertIsInstance(result, Config)

    def test_generate_loopback_ip_falls_back_to_empty(self):
        # ipaddress validates 127.0.0.1 as loopback — branch on lines 335-336.
        with self._patch_urlopen("127.0.0.1"):
            result = Config.generate(
                prv="3bb355f8fff1b894320fb5764b3f16e3395d37493b87cb5889e517e0d474376a"
            )
        self.assertIsInstance(result, Config)

    def test_generate_private_ip_falls_back_to_empty(self):
        with self._patch_urlopen("10.0.0.1"):
            result = Config.generate(
                prv="3bb355f8fff1b894320fb5764b3f16e3395d37493b87cb5889e517e0d474376a"
            )
        self.assertIsInstance(result, Config)

    def test_generate_no_key_raises(self):
        # All key inputs evaluated falsy after generation: patch mnemonic to
        # produce empty seed so the `if seed:` branch is skipped, leaving
        # private_key = None -> reaches `raise Exception("No key")`.
        with patch("yadacoin.core.config.Mnemonic") as mn:
            mn.return_value.generate.return_value = ""
            with self.assertRaises(Exception) as ctx:
                Config.generate()
            self.assertIn("No key", str(ctx.exception))


# ---------------------------------------------------------------------------
# Config.from_dict (lines 393-486) — pollutes class attrs; snapshot/restore.
# ---------------------------------------------------------------------------


class TestFromDict(unittest.TestCase):
    def setUp(self):
        # Snapshot any class-level attrs we might mutate.
        self._cls_snapshot = {
            k: v for k, v in Config.__dict__.items() if not k.startswith("__")
        }

    def tearDown(self):
        # Remove any new class attributes added by from_dict.
        for k in list(Config.__dict__.keys()):
            if k.startswith("__"):
                continue
            if k not in self._cls_snapshot:
                try:
                    delattr(Config, k)
                except AttributeError:
                    pass

    def _base_dict(self):
        return {
            "modes": ["node"],
            "public_key": "021487409d61f795be71d51f3af9b23fb08f024b51888af52edb1ad4a191c888c4",
            "private_key": "3bb355f8fff1b894320fb5764b3f16e3395d37493b87cb5889e517e0d474376a",
            "username": "",
            "mongodb_host": "localhost",
            "database": "ydb",
            "site_database": "yds",
            "peer_host": "70.166.222.226",
            "peer_port": 8000,
            "serve_host": "0.0.0.0",
            "serve_port": 8001,
            "callbackurl": "cb",
            "fcm_key": "",
        }

    def test_from_dict_success(self):
        Config.from_dict(self._base_dict())
        self.assertEqual(Config.peer_host, "70.166.222.226")
        self.assertEqual(Config.network, "mainnet")

    def test_from_dict_localhost_raises(self):
        d = self._base_dict()
        d["peer_host"] = "localhost"
        with self.assertRaises(Exception):
            Config.from_dict(d)

    def test_from_dict_placeholder_raises(self):
        d = self._base_dict()
        d["peer_host"] = "[my public ip]"
        with self.assertRaises(Exception):
            Config.from_dict(d)

    def test_from_dict_ipv6_raises(self):
        d = self._base_dict()
        d["peer_host"] = "2600:387:15:241b::4"
        with self.assertRaises(Exception):
            Config.from_dict(d)

    def test_from_dict_with_email(self):
        d = self._base_dict()
        d["email"] = {
            "username": "u",
            "password": "p",
            "smtp_server": "s",
            "smtp_port": 587,
        }
        Config.from_dict(d)
        self.assertEqual(Config.email.username, "u")


# ---------------------------------------------------------------------------
# Config.refresh_price (lines 558-573)
# ---------------------------------------------------------------------------


class TestRefreshPrice(ConfigTestCase):
    async def test_initial_call_fetches_ticker(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"yadacoin": {"usd": 1.23}}
        mock_site_db = MagicMock()
        mock_site_db.coingecko_spot_rates.insert_one = AsyncMock()
        # Ensure self.ticker not yet set.
        for attr in ("ticker", "last_update"):
            if hasattr(self.config, attr):
                delattr(self.config, attr)
        with patch(
            "yadacoin.core.config.requests.get", return_value=mock_resp
        ), patch.object(
            self.config.mongo, "async_site_db", new=mock_site_db, create=True
        ):
            await self.config.refresh_price()
        mock_site_db.coingecko_spot_rates.insert_one.assert_awaited_once()
        self.assertTrue(hasattr(self.config, "last_update"))

    async def test_refresh_price_when_stale(self):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"yadacoin": {"usd": 2.34}}
        mock_site_db = MagicMock()
        mock_site_db.coingecko_spot_rates.insert_one = AsyncMock()
        self.config.ticker = True
        self.config.last_update = 0  # very old
        with patch(
            "yadacoin.core.config.requests.get", return_value=mock_resp
        ), patch.object(
            self.config.mongo, "async_site_db", new=mock_site_db, create=True
        ):
            await self.config.refresh_price()
        mock_site_db.coingecko_spot_rates.insert_one.assert_awaited_once()

    async def test_refresh_price_skips_when_recent(self):
        from time import time as _t

        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"yadacoin": {"usd": 3.45}}
        mock_site_db = MagicMock()
        mock_site_db.coingecko_spot_rates.insert_one = AsyncMock()
        self.config.ticker = True
        self.config.last_update = _t()  # fresh
        with patch(
            "yadacoin.core.config.requests.get", return_value=mock_resp
        ), patch.object(
            self.config.mongo, "async_site_db", new=mock_site_db, create=True
        ):
            await self.config.refresh_price()
        mock_site_db.coingecko_spot_rates.insert_one.assert_not_called()

    async def test_refresh_price_non_200_status(self):
        mock_resp = MagicMock(status_code=500)
        mock_site_db = MagicMock()
        mock_site_db.coingecko_spot_rates.insert_one = AsyncMock()
        for attr in ("ticker", "last_update"):
            if hasattr(self.config, attr):
                delattr(self.config, attr)
        with patch(
            "yadacoin.core.config.requests.get", return_value=mock_resp
        ), patch.object(
            self.config.mongo, "async_site_db", new=mock_site_db, create=True
        ):
            await self.config.refresh_price()
        mock_site_db.coingecko_spot_rates.insert_one.assert_not_called()


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
