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
import unittest
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

from ..test_setup import AsyncTestCase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    seed="",
    private_key="511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694",
    public_key="02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29",
    address="1ArsFNcc5fU3cfSUiNJCu6LhT8CeZgtEcC",
    kel_private_key=None,
    kel_public_key=None,
    kel_address=None,
    config_path=None,
    modes=None,
    username="testnode",
):
    cfg = MagicMock()
    cfg.seed = seed
    cfg.private_key = private_key
    cfg.public_key = public_key
    cfg.address = address
    cfg.kel_private_key = kel_private_key
    cfg.kel_public_key = kel_public_key
    cfg.kel_address = kel_address
    cfg.config_path = config_path
    cfg.modes = modes or []
    cfg.username = username
    cfg.app_log = MagicMock()
    cfg.mongo = MagicMock()
    cfg.kel_manager = None
    return cfg


_VALID_PRIV = bytes.fromhex(
    "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
)


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


class TestDerivePureFunctions(unittest.TestCase):
    """Tests for _bip32_hardened_child, _derive_index, derive_secure_path."""

    def test_read_second_factor_from_env(self):
        from yadacoin.core.keyrotation import _read_second_factor

        with patch.dict(os.environ, {"SECOND_FACTOR": "envsecret"}, clear=False):
            os.environ.pop("SECOND_FACTOR_FILE", None)
            self.assertEqual(_read_second_factor(), "envsecret")

    def test_read_second_factor_from_file(self):
        from yadacoin.core.keyrotation import _read_second_factor

        with patch.dict(os.environ, {"SECOND_FACTOR_FILE": "/fake/sf"}, clear=False):
            with patch("builtins.open", mock_open(read_data="filesecret\n")):
                self.assertEqual(_read_second_factor(), "filesecret")

    def test_read_second_factor_file_error_returns_empty(self):
        from yadacoin.core.keyrotation import _read_second_factor

        with patch.dict(os.environ, {"SECOND_FACTOR_FILE": "/bad/path"}, clear=False):
            with patch("builtins.open", side_effect=IOError("not found")):
                self.assertEqual(_read_second_factor(), "")

    def test_read_second_factor_file_takes_priority(self):
        from yadacoin.core.keyrotation import _read_second_factor

        with patch.dict(
            os.environ,
            {"SECOND_FACTOR": "envval", "SECOND_FACTOR_FILE": "/fake/sf"},
            clear=False,
        ):
            with patch("builtins.open", mock_open(read_data="fileval")):
                self.assertEqual(_read_second_factor(), "fileval")

    def test_derive_index_deterministic(self):
        from yadacoin.core.keyrotation import _derive_index

        idx1 = _derive_index("mysecret", 0)
        idx2 = _derive_index("mysecret", 0)
        self.assertEqual(idx1, idx2)
        self.assertGreaterEqual(idx1, 0)
        self.assertLess(idx1, 2147483647)

    def test_derive_index_different_levels(self):
        from yadacoin.core.keyrotation import _derive_index

        self.assertNotEqual(_derive_index("secret", 0), _derive_index("secret", 1))

    def test_derive_index_different_factors(self):
        from yadacoin.core.keyrotation import _derive_index

        self.assertNotEqual(_derive_index("aaa", 0), _derive_index("bbb", 0))

    def test_bip32_hardened_child_returns_dict(self):
        from yadacoin.core.keyrotation import _bip32_hardened_child

        priv = os.urandom(32)
        cc = os.urandom(32)
        result = _bip32_hardened_child(priv, cc, 0)
        self.assertIn("private_key", result)
        self.assertIn("chain_code", result)
        self.assertEqual(len(result["private_key"]), 32)
        self.assertEqual(len(result["chain_code"]), 32)

    def test_derive_secure_path_deterministic(self):
        from yadacoin.core.keyrotation import derive_secure_path

        priv = bytes.fromhex(
            "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        )
        cc = os.urandom(32)
        r1 = derive_secure_path(priv, cc, "factor")
        r2 = derive_secure_path(priv, cc, "factor")
        self.assertEqual(r1["private_key"], r2["private_key"])

    def test_derive_secure_path_different_factors_differ(self):
        from yadacoin.core.keyrotation import derive_secure_path

        priv = bytes.fromhex(
            "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        )
        cc = os.urandom(32)
        r1 = derive_secure_path(priv, cc, "factorA")
        r2 = derive_secure_path(priv, cc, "factorB")
        self.assertNotEqual(r1["private_key"], r2["private_key"])


# ---------------------------------------------------------------------------
# get_node_signing_key
# ---------------------------------------------------------------------------


class TestGetNodeSigningKey(unittest.TestCase):
    def test_returns_legacy_when_no_kel(self):
        from yadacoin.core.keyrotation import get_node_signing_key

        cfg = _make_config()
        priv, pub, addr = get_node_signing_key(cfg)
        self.assertEqual(priv, cfg.private_key)
        self.assertEqual(pub, cfg.public_key)
        self.assertEqual(addr, cfg.address)

    def test_returns_kel_key_when_present(self):
        from yadacoin.core.keyrotation import get_node_signing_key

        cfg = _make_config(
            kel_private_key="aabbcc",
            kel_public_key="0abc",
            kel_address="1KelAddr",
        )
        priv, pub, addr = get_node_signing_key(cfg)
        self.assertEqual(priv, "aabbcc")
        self.assertEqual(pub, "0abc")
        self.assertEqual(addr, "1KelAddr")


# ---------------------------------------------------------------------------
# get_node_auth_key
# ---------------------------------------------------------------------------


class TestGetNodeAuthKey(AsyncTestCase):
    async def test_no_manager_returns_legacy(self):
        from yadacoin.core.keyrotation import get_node_auth_key

        cfg = _make_config()
        priv, pub, *_ = await get_node_auth_key(cfg)
        self.assertEqual(priv, cfg.private_key)
        self.assertEqual(pub, cfg.public_key)

    async def test_with_manager_delegates(self):
        from yadacoin.core.keyrotation import get_node_auth_key

        cfg = _make_config()
        manager = MagicMock()
        manager.advance_auth_ratchet = AsyncMock(
            return_value=("privhex", "pubhex", None, None)
        )
        cfg.kel_manager = manager
        priv, pub, *_ = await get_node_auth_key(cfg)
        self.assertEqual(priv, "privhex")
        self.assertEqual(pub, "pubhex")
        manager.advance_auth_ratchet.assert_awaited_once()


# ---------------------------------------------------------------------------
# save_config
# ---------------------------------------------------------------------------


class TestSaveConfig(unittest.TestCase):
    def test_no_config_path_logs_warning(self):
        from yadacoin.core.keyrotation import save_config

        cfg = _make_config()
        save_config(cfg)
        cfg.app_log.warning.assert_called_once()

    def test_writes_nothing_extra_to_file(self):
        from yadacoin.core.keyrotation import save_config

        cfg = _make_config(config_path="/fake/config.json")
        on_disk = {"network": "mainnet"}
        m = mock_open(read_data=json.dumps(on_disk))
        with patch("builtins.open", m):
            with patch("json.load", return_value=dict(on_disk)):
                with patch("json.dump") as mock_dump:
                    save_config(cfg)
        mock_dump.assert_called_once()
        written = mock_dump.call_args[0][0]
        # verify nothing KEL-specific is written
        self.assertNotIn("admin_kel", written)

    def test_io_error_logs_error(self):
        from yadacoin.core.keyrotation import save_config

        cfg = _make_config(config_path="/fake/config.json")
        with patch("builtins.open", side_effect=IOError("disk full")):
            save_config(cfg)
        cfg.app_log.error.assert_called_once()


# ---------------------------------------------------------------------------
# _fatal
# ---------------------------------------------------------------------------


class TestFatal(unittest.TestCase):
    def test_exits_with_code_1(self):
        from yadacoin.core.keyrotation import _fatal

        with self.assertRaises(SystemExit) as cm:
            _fatal("boom")
        self.assertEqual(cm.exception.code, 1)


# ---------------------------------------------------------------------------
# NodeKeyRotationManager.__init__
# ---------------------------------------------------------------------------


class TestManagerInit(unittest.TestCase):
    def test_initial_state(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)
        self.assertIsNone(mgr._inception_txn_id)
        self.assertFalse(mgr._inception_complete)
        self.assertEqual(mgr._kel_balance_cache, {})
        self.assertIsNone(mgr._k0)
        self.assertEqual(mgr._second_factor, "")
        self.assertIsNone(mgr._auth_ratchet_key)
        self.assertEqual(mgr._auth_ratchet_pub, "")
        self.assertEqual(mgr._auth_counter, 0)
        self.assertEqual(mgr.OFFCHAIN_ANCHOR_INTERVAL, 100)


# ---------------------------------------------------------------------------
# startup_check — failure paths
# ---------------------------------------------------------------------------


class TestStartupCheckFailures(AsyncTestCase):
    async def test_missing_seed_calls_fatal(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(seed="")
        mgr = NodeKeyRotationManager(cfg)
        with patch("yadacoin.core.keyrotation._fatal") as mock_fatal:
            mock_fatal.side_effect = SystemExit(1)
            with self.assertRaises(SystemExit):
                await mgr.startup_check()
        mock_fatal.assert_called_once()
        self.assertIn("seed", mock_fatal.call_args[0][0])

    async def test_missing_username_calls_fatal(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            seed="able able able able able able able able able able able able"
        )
        cfg.username = ""
        mgr = NodeKeyRotationManager(cfg)
        with patch.dict(os.environ, {"SECOND_FACTOR": "mysecret"}):
            with patch("yadacoin.core.keyrotation._fatal") as mock_fatal:
                mock_fatal.side_effect = SystemExit(1)
                with self.assertRaises(SystemExit):
                    await mgr.startup_check()
        mock_fatal.assert_called_once()
        self.assertIn("username", mock_fatal.call_args[0][0])

    async def test_missing_second_factor_calls_fatal(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(seed="word " * 24, username="testnode")
        mgr = NodeKeyRotationManager(cfg)
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SECOND_FACTOR", None)
            os.environ.pop("SECOND_FACTOR_FILE", None)
            with patch("yadacoin.core.keyrotation._fatal") as mock_fatal:
                mock_fatal.side_effect = SystemExit(1)
                with self.assertRaises(SystemExit):
                    await mgr.startup_check()
        mock_fatal.assert_called_once()
        self.assertIn("SECOND_FACTOR", mock_fatal.call_args[0][0])

    async def test_second_factor_file_read_success(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            seed="able able able able able able able able able able able able"
        )
        mgr = NodeKeyRotationManager(cfg)

        mock_root = MagicMock()
        mock_root.PrivateKey.return_value = bytes(range(1, 33))
        mock_root.ChainCode.return_value = bytes(range(1, 33))
        mock_bip32 = MagicMock()
        mock_bip32.fromEntropy.return_value = mock_root

        with patch.dict(os.environ, {"SECOND_FACTOR_FILE": "/fake/sf"}, clear=False):
            os.environ.pop("SECOND_FACTOR", None)
            with patch("builtins.open", mock_open(read_data="mysecretfromfile\n")):
                with patch("bip32utils.BIP32Key", mock_bip32):
                    with patch("mnemonic.Mnemonic") as mock_mn_cls:
                        mock_mn = MagicMock()
                        mock_mn.to_entropy.return_value = b"\x00" * 16
                        mock_mn_cls.return_value = mock_mn
                        with patch(
                            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
                            new=AsyncMock(return_value=[]),
                        ):
                            with patch.object(
                                mgr, "_create_inception", new=AsyncMock()
                            ):
                                await mgr.startup_check()
        self.assertEqual(mgr._second_factor, "mysecretfromfile")

    async def test_second_factor_file_read_error_calls_fatal(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            seed="able able able able able able able able able able able able"
        )
        mgr = NodeKeyRotationManager(cfg)

        with patch.dict(os.environ, {"SECOND_FACTOR_FILE": "/fake/sf"}, clear=False):
            os.environ.pop("SECOND_FACTOR", None)
            with patch("builtins.open", side_effect=IOError("no such file")):
                with patch("yadacoin.core.keyrotation._fatal") as mock_fatal:
                    mock_fatal.side_effect = SystemExit(1)
                    with self.assertRaises(SystemExit):
                        await mgr.startup_check()
        mock_fatal.assert_called_once()
        self.assertIn("SECOND_FACTOR_FILE", mock_fatal.call_args[0][0])

    async def test_bip32_exception_calls_fatal(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(seed="bad seed phrase here")
        mgr = NodeKeyRotationManager(cfg)
        with patch.dict(os.environ, {"SECOND_FACTOR": "sf"}):
            with patch("yadacoin.core.keyrotation._fatal") as mock_fatal:
                mock_fatal.side_effect = SystemExit(1)
                with patch(
                    "bip32utils.BIP32Key.fromEntropy", side_effect=Exception("bad")
                ):
                    with self.assertRaises(SystemExit):
                        await mgr.startup_check()
        mock_fatal.assert_called_once()


# ---------------------------------------------------------------------------
# startup_check — success paths
# ---------------------------------------------------------------------------


class TestStartupCheckSuccess(AsyncTestCase):
    def _make_bip32_mock(self):
        mock_root = MagicMock()
        mock_root.PrivateKey.return_value = bytes(32)
        mock_root.ChainCode.return_value = bytes(32)
        mock_bip32 = MagicMock()
        mock_bip32.fromEntropy.return_value = mock_root
        return mock_bip32

    async def test_no_existing_kel_creates_inception(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            seed="able able able able able able able able able able able able"
        )
        mgr = NodeKeyRotationManager(cfg)

        with patch.dict(os.environ, {"SECOND_FACTOR": "mysecret"}):
            with patch("bip32utils.BIP32Key", self._make_bip32_mock()):
                with patch("mnemonic.Mnemonic") as mock_mn_cls:
                    mock_mn = MagicMock()
                    mock_mn.to_entropy.return_value = b"\x00" * 16
                    mock_mn_cls.return_value = mock_mn
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
                        new=AsyncMock(return_value=[]),
                    ):
                        with patch.object(
                            mgr, "_create_inception", new=AsyncMock()
                        ) as mock_create:
                            await mgr.startup_check()
        mock_create.assert_awaited_once()

    async def test_mempool_only_kel_calls_update_active(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            seed="able able able able able able able able able able able able"
        )
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.transaction_signature = "TXNID"
        mock_entry.mempool = True

        with patch.dict(os.environ, {"SECOND_FACTOR": "mysecret"}):
            with patch("bip32utils.BIP32Key", self._make_bip32_mock()):
                with patch("mnemonic.Mnemonic") as mock_mn_cls:
                    mock_mn = MagicMock()
                    mock_mn.to_entropy.return_value = b"\x00" * 16
                    mock_mn_cls.return_value = mock_mn
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
                        new=AsyncMock(return_value=[mock_entry]),
                    ):
                        with patch.object(mgr, "_update_active_kel_key") as mock_update:
                            await mgr.startup_check()
        mock_update.assert_called_once()
        self.assertEqual(mgr._inception_txn_id, "TXNID")

    async def test_onchain_kel_calls_try_finalise(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            seed="able able able able able able able able able able able able"
        )
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.transaction_signature = "TXNID"
        mock_entry.mempool = False

        with patch.dict(os.environ, {"SECOND_FACTOR": "mysecret"}):
            with patch("bip32utils.BIP32Key", self._make_bip32_mock()):
                with patch("mnemonic.Mnemonic") as mock_mn_cls:
                    mock_mn = MagicMock()
                    mock_mn.to_entropy.return_value = b"\x00" * 16
                    mock_mn_cls.return_value = mock_mn
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
                        new=AsyncMock(return_value=[mock_entry]),
                    ):
                        with patch.object(
                            mgr, "_try_finalise", new=AsyncMock()
                        ) as mock_fin:
                            await mgr.startup_check()
        mock_fin.assert_awaited_once()

    async def test_kel_build_exception_treated_as_empty(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            seed="able able able able able able able able able able able able"
        )
        mgr = NodeKeyRotationManager(cfg)

        with patch.dict(os.environ, {"SECOND_FACTOR": "mysecret"}):
            with patch("bip32utils.BIP32Key", self._make_bip32_mock()):
                with patch("mnemonic.Mnemonic") as mock_mn_cls:
                    mock_mn = MagicMock()
                    mock_mn.to_entropy.return_value = b"\x00" * 16
                    mock_mn_cls.return_value = mock_mn
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
                        new=AsyncMock(side_effect=Exception("db error")),
                    ):
                        with patch.object(
                            mgr, "_create_inception", new=AsyncMock()
                        ) as mock_create:
                            await mgr.startup_check()
        mock_create.assert_awaited_once()

    async def test_identity_mismatch_calls_fatal(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            seed="able able able able able able able able able able able able"
        )
        cfg.username = "mynode"
        mgr = NodeKeyRotationManager(cfg)

        with patch.dict(os.environ, {"SECOND_FACTOR": "mysecret"}):
            with patch("bip32utils.BIP32Key", self._make_bip32_mock()):
                with patch("mnemonic.Mnemonic") as mock_mn_cls:
                    mock_mn = MagicMock()
                    mock_mn.to_entropy.return_value = b"\x00" * 16
                    mock_mn_cls.return_value = mock_mn
                    # On-chain identity has WRONG public key
                    with patch.object(
                        IdentityAnnouncement,
                        "get_by_username",
                        new=AsyncMock(return_value={"public_key": "02WRONG"}),
                    ):
                        with patch("yadacoin.core.keyrotation._fatal") as mock_fatal:
                            mock_fatal.side_effect = SystemExit(1)
                            with self.assertRaises(SystemExit):
                                await mgr.startup_check()
        mock_fatal.assert_called_once()

    async def test_identity_match_logs_and_continues(self):
        """When on-chain identity exists and K0 matches, log info and continue."""
        from yadacoin.core.identityannouncement import IdentityAnnouncement
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            seed="able able able able able able able able able able able able",
            username="mynode",
        )
        mgr = NodeKeyRotationManager(cfg)

        with patch.dict(os.environ, {"SECOND_FACTOR": "mysecret"}):
            with patch("bip32utils.BIP32Key", self._make_bip32_mock()):
                with patch("mnemonic.Mnemonic") as mock_mn_cls:
                    mock_mn = MagicMock()
                    mock_mn.to_entropy.return_value = b"\x00" * 16
                    mock_mn_cls.return_value = mock_mn

                    # Compute the actual derived K0 pub key to return as identity
                    from coincurve import PrivateKey as CK

                    from yadacoin.core.keyrotation import derive_secure_path

                    k0 = derive_secure_path(bytes(32), bytes(32), "mysecret")
                    k0_pub_hex = (
                        CK(k0["private_key"]).public_key.format(compressed=True).hex()
                    )

                    with patch.object(
                        IdentityAnnouncement,
                        "get_by_username",
                        new=AsyncMock(return_value={"public_key": k0_pub_hex}),
                    ):
                        with patch(
                            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
                            new=AsyncMock(return_value=[]),
                        ):
                            with patch.object(
                                mgr, "_create_inception", new=AsyncMock()
                            ):
                                await mgr.startup_check()
        cfg.app_log.info.assert_called()


# ---------------------------------------------------------------------------
# background_kel_checker
# ---------------------------------------------------------------------------


class TestBackgroundKelChecker(AsyncTestCase):
    async def test_no_k0_returns_early(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)
        # _k0 is None by default — should return without error
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(return_value=[]),
        ):
            await mgr.background_kel_checker()  # must not raise

    async def test_no_kel_returns_early(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"
        # _inception_complete is False — takes the not-complete branch
        mgr._inception_complete = False

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(return_value=[]),
        ):
            with patch.object(mgr, "_try_finalise", new=AsyncMock()) as mock_fin:
                await mgr.background_kel_checker()
        mock_fin.assert_not_awaited()

    async def test_kel_found_calls_finalise_and_sweep(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"
        mgr._inception_complete = False  # not yet complete → finalise path

        mock_entry = MagicMock()
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(return_value=[mock_entry]),
        ):
            with patch.object(mgr, "_try_finalise", new=AsyncMock()) as mock_fin:
                with patch.object(
                    mgr, "_check_and_sweep_legacy_funds", new=AsyncMock()
                ) as mock_sweep:
                    await mgr.background_kel_checker()
        mock_fin.assert_awaited_once()
        mock_sweep.assert_awaited_once()

    async def test_inception_complete_skips_finalise_still_sweeps(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"
        mgr._inception_complete = True  # already done — skip finalise

        mock_entry = MagicMock()
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(return_value=[mock_entry]),
        ):
            with patch.object(mgr, "_try_finalise", new=AsyncMock()) as mock_fin:
                with patch.object(
                    mgr, "_check_and_sweep_legacy_funds", new=AsyncMock()
                ) as mock_sweep:
                    await mgr.background_kel_checker()
        mock_fin.assert_not_awaited()
        mock_sweep.assert_awaited_once()

    async def test_inception_complete_no_kel_skips_sweep(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"
        mgr._inception_complete = True

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(return_value=[]),
        ):
            with patch.object(
                mgr, "_check_and_sweep_legacy_funds", new=AsyncMock()
            ) as mock_sweep:
                await mgr.background_kel_checker()
        mock_sweep.assert_not_awaited()

    async def test_inception_complete_kel_exception_returns_early(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"
        mgr._inception_complete = True

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(side_effect=Exception("db error")),
        ):
            with patch.object(
                mgr, "_check_and_sweep_legacy_funds", new=AsyncMock()
            ) as mock_sweep:
                await mgr.background_kel_checker()
        mock_sweep.assert_not_awaited()

    async def test_kel_build_exception_returns_early(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"
        mgr._inception_complete = False

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(side_effect=Exception("err")),
        ):
            with patch.object(mgr, "_try_finalise", new=AsyncMock()) as mock_fin:
                await mgr.background_kel_checker()
        mock_fin.assert_not_awaited()


# ---------------------------------------------------------------------------
# (TestVerifyAdminKelMatchesK0 removed — verification now uses
#  IdentityAnnouncement.get_by_username)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# _update_active_kel_key
# ---------------------------------------------------------------------------


class TestUpdateActiveKelKey(unittest.TestCase):
    def test_sets_kel_keys_on_config(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)

        priv_bytes = bytes.fromhex(
            "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        )
        k0 = {"private_key": priv_bytes, "chain_code": priv_bytes}
        mock_entry = MagicMock()
        kel = [mock_entry]  # depth 1

        mgr._update_active_kel_key(kel, k0, "factor")

        # After 1 derive step, kel_private_key/public_key/address must be set
        self.assertIsNotNone(cfg.kel_private_key)
        self.assertIsNotNone(cfg.kel_public_key)
        self.assertIsNotNone(cfg.kel_address)
        self.assertIsInstance(cfg.kel_private_key, str)
        self.assertEqual(len(cfg.kel_private_key), 64)  # 32-byte hex

    def test_depth_zero_sets_k0_derived(self):
        from coincurve import PrivateKey as CK

        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)

        k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        kel = []  # depth 0 — loop runs 0 times, cur stays k0

        mgr._update_active_kel_key(kel, k0, "factor")

        # With depth=0, no derivation — kel key IS k0
        expected_pub = CK(_VALID_PRIV).public_key.format(compressed=True).hex()
        self.assertEqual(cfg.kel_public_key, expected_pub)


# ---------------------------------------------------------------------------
# _try_finalise
# ---------------------------------------------------------------------------


class TestTryFinalise(AsyncTestCase):
    async def test_sets_inception_complete_and_updates_key(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.transaction_signature = "INCEPTION_ID"

        with patch.object(mgr, "_update_active_kel_key") as mock_update:
            await mgr._try_finalise([mock_entry], {}, "sf")

        mock_update.assert_called_once()
        self.assertTrue(mgr._inception_complete)

    async def test_no_save_config_called(self):
        """save_config must not call json.dump with any KEL-specific fields."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.transaction_signature = "INCEPTION_ID"

        with patch("yadacoin.core.keyrotation.save_config") as mock_save:
            with patch.object(mgr, "_update_active_kel_key"):
                await mgr._try_finalise([mock_entry], {}, "sf")

        mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# advance_auth_ratchet
# ---------------------------------------------------------------------------


class TestAdvanceAuthRatchet(AsyncTestCase):
    async def test_no_kel_key_returns_legacy(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)

        priv, pub, *_ = await mgr.advance_auth_ratchet()
        self.assertEqual(priv, cfg.private_key)
        self.assertEqual(pub, cfg.public_key)

    async def test_no_second_factor_returns_legacy(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            kel_private_key="511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694",
            kel_public_key="02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29",
        )
        mgr = NodeKeyRotationManager(cfg)

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SECOND_FACTOR", None)
            priv, pub, *_ = await mgr.advance_auth_ratchet()

        self.assertEqual(priv, cfg.private_key)

    async def test_derives_next_key_and_logs(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        cfg = _make_config(kel_private_key=priv_hex, kel_public_key=pub_hex)
        cfg.mongo.async_db.kel_signing_log.insert_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"

        priv_out, pub_out, conf_priv, conf_pub = await mgr.advance_auth_ratchet()

        # Current key (priv_out) is the anchor kel key — it signs the challenge
        self.assertEqual(priv_out, priv_hex)
        self.assertEqual(pub_out, pub_hex)
        # Confirming key is the NEXT derived key — must differ from the anchor
        self.assertIsNotNone(conf_priv)
        self.assertNotEqual(conf_priv, priv_hex)
        self.assertNotEqual(conf_pub, pub_hex)
        # Counter incremented
        self.assertEqual(mgr._auth_counter, 1)
        cfg.mongo.async_db.kel_signing_log.insert_one.assert_awaited_once()

    async def test_db_error_does_not_raise(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        cfg = _make_config(kel_private_key=priv_hex, kel_public_key=pub_hex)
        cfg.mongo.async_db.kel_signing_log.insert_one = AsyncMock(
            side_effect=Exception("db error")
        )
        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"

        # Should not raise
        priv_out, pub_out, *_ = await mgr.advance_auth_ratchet()
        self.assertIsNotNone(priv_out)

    async def test_interval_triggers_reanchor(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        cfg = _make_config(kel_private_key=priv_hex, kel_public_key=pub_hex)
        cfg.mongo.async_db.kel_signing_log.insert_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"
        # Seed counter so the NEXT call hits the interval
        mgr._auth_counter = mgr.OFFCHAIN_ANCHOR_INTERVAL - 1
        # Pre-set ratchet state to avoid re-init branch
        mgr._auth_ratchet_key = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        mgr._auth_ratchet_pub = pub_hex

        with patch.object(mgr, "_queue_reanchor", new=AsyncMock()) as mock_anchor:
            await mgr.advance_auth_ratchet()

        mock_anchor.assert_awaited_once()

    async def test_reanchor_error_does_not_raise(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        cfg = _make_config(kel_private_key=priv_hex, kel_public_key=pub_hex)
        cfg.mongo.async_db.kel_signing_log.insert_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"
        mgr._auth_counter = mgr.OFFCHAIN_ANCHOR_INTERVAL - 1
        mgr._auth_ratchet_key = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        mgr._auth_ratchet_pub = pub_hex

        with patch.object(
            mgr, "_queue_reanchor", new=AsyncMock(side_effect=Exception("boom"))
        ):
            priv_out, pub_out, *_ = await mgr.advance_auth_ratchet()
        self.assertIsNotNone(priv_out)


# ---------------------------------------------------------------------------
# _queue_reanchor
# ---------------------------------------------------------------------------


class TestQueueReanchor(AsyncTestCase):
    async def test_no_k0_returns_early(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)
        # _k0 is None — should exit silently
        await mgr._queue_reanchor()  # must not raise

    async def test_no_kel_pub_returns_early(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()  # kel_public_key is None
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": bytes(32), "chain_code": bytes(32)}
        mgr._second_factor = "sf"
        await mgr._queue_reanchor()

    async def test_no_onchain_kel_returns_early(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(kel_public_key="02pub")
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(return_value=[]),
        ):
            await mgr._queue_reanchor()

    async def test_kel_build_exception_returns_early(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(kel_public_key="02pub")
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(side_effect=Exception("db error")),
        ):
            await mgr._queue_reanchor()  # must not raise

    async def test_success_submits_two_txns(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(kel_public_key="02pub")
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        mgr._second_factor = "mysecret"

        mock_entry = MagicMock()
        mock_entry.public_key_hash = "1SomeAddress"

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(return_value=[mock_entry]),
        ):
            await mgr._queue_reanchor()

        # Both transactions should have been upserted
        self.assertEqual(
            cfg.mongo.async_db.miner_transactions.replace_one.await_count, 2
        )

    async def test_broadcasts_in_node_mode(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(kel_public_key="02pub", modes=["node"])
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()

        peer_stream = MagicMock()
        peer_stream.peer.protocol_version = 2
        peer_stream.peer.rid = "rid1"

        async def _get_peers():
            yield peer_stream

        cfg.peer = MagicMock()
        cfg.peer.get_sync_peers = _get_peers
        cfg.nodeShared = MagicMock()
        cfg.nodeShared.write_params = AsyncMock()
        cfg.nodeClient = MagicMock()
        cfg.nodeClient.retry_messages = {}

        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        mgr._second_factor = "mysecret"

        mock_entry = MagicMock()
        mock_entry.public_key_hash = "1SomeAddress"

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(return_value=[mock_entry]),
        ):
            await mgr._queue_reanchor()

        cfg.nodeShared.write_params.assert_awaited()

    async def test_broadcast_exception_logged(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(kel_public_key="02pub", modes=["node"])
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        cfg.peer = MagicMock()
        cfg.peer.get_sync_peers = MagicMock(side_effect=Exception("peer err"))

        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        mgr._second_factor = "mysecret"

        mock_entry = MagicMock()
        mock_entry.public_key_hash = "1SomeAddress"

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.build_from_public_key",
            new=AsyncMock(return_value=[mock_entry]),
        ):
            await mgr._queue_reanchor()

        cfg.app_log.warning.assert_called()


# ---------------------------------------------------------------------------
# _create_inception
# ---------------------------------------------------------------------------


class TestCreateInception(AsyncTestCase):
    async def test_creates_and_stores_txn(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config()
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)

        priv_bytes = bytes.fromhex(priv_hex)
        k0 = {"private_key": priv_bytes, "chain_code": priv_bytes}

        from coincurve import PrivateKey as CK

        k0_pub_hex = CK(priv_bytes).public_key.format(compressed=True).hex()

        await mgr._create_inception(k0, "mysecret", k0_pub_hex)

        cfg.mongo.async_db.miner_transactions.replace_one.assert_awaited_once()
        self.assertIsNotNone(mgr._inception_txn_id)

    async def test_creates_with_identity_announcement(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config()
        cfg.username = "testnode"
        cfg.peer_host = "1.2.3.4"
        cfg.peer_port = 8000
        cfg.serve_port = 8005
        cfg.peer_type = "service_provider"
        cfg.ssl = MagicMock()
        cfg.ssl.port = None
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)

        priv_bytes = bytes.fromhex(priv_hex)
        k0 = {"private_key": priv_bytes, "chain_code": priv_bytes}

        from coincurve import PrivateKey as CK

        k0_pub_hex = CK(priv_bytes).public_key.format(compressed=True).hex()

        await mgr._create_inception(k0, "mysecret", k0_pub_hex)

        cfg.mongo.async_db.miner_transactions.replace_one.assert_awaited_once()
        self.assertIsNotNone(mgr._inception_txn_id)

    async def test_broadcasts_in_node_mode(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(modes=["node"])
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()

        peer_stream = MagicMock()
        peer_stream.peer.protocol_version = 2
        peer_stream.peer.rid = "rid1"

        async def _get_peers():
            yield peer_stream

        cfg.peer = MagicMock()
        cfg.peer.get_sync_peers = _get_peers
        cfg.nodeShared = MagicMock()
        cfg.nodeShared.write_params = AsyncMock()
        cfg.nodeClient = MagicMock()
        cfg.nodeClient.retry_messages = {}

        mgr = NodeKeyRotationManager(cfg)
        priv_bytes = bytes.fromhex(priv_hex)
        k0 = {"private_key": priv_bytes, "chain_code": priv_bytes}
        from coincurve import PrivateKey as CK

        k0_pub_hex = CK(priv_bytes).public_key.format(compressed=True).hex()

        await mgr._create_inception(k0, "mysecret", k0_pub_hex)

        cfg.nodeShared.write_params.assert_awaited()

    async def test_broadcast_exception_logged(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(modes=["node"])
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        cfg.peer = MagicMock()
        cfg.peer.get_sync_peers = MagicMock(side_effect=Exception("peer err"))

        mgr = NodeKeyRotationManager(cfg)
        priv_bytes = bytes.fromhex(priv_hex)
        k0 = {"private_key": priv_bytes, "chain_code": priv_bytes}
        from coincurve import PrivateKey as CK

        k0_pub_hex = CK(priv_bytes).public_key.format(compressed=True).hex()

        await mgr._create_inception(k0, "mysecret", k0_pub_hex)

        cfg.app_log.warning.assert_called()

    async def test_identity_announcement_exception_logged_and_continues(self):
        """When IdentityAnnouncement construction raises, warning is logged and inception still created."""
        from yadacoin.core.identityannouncement import IdentityAnnouncement
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(username="testnode")
        cfg.peer_host = "1.2.3.4"
        cfg.peer_port = 8000
        cfg.serve_port = 8005
        cfg.peer_type = "service_provider"
        cfg.ssl = None
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)

        priv_bytes = bytes.fromhex(priv_hex)
        k0 = {"private_key": priv_bytes, "chain_code": priv_bytes}
        from coincurve import PrivateKey as CK

        k0_pub_hex = CK(priv_bytes).public_key.format(compressed=True).hex()

        with patch.object(
            IdentityAnnouncement, "__init__", side_effect=Exception("boom")
        ):
            await mgr._create_inception(k0, "mysecret", k0_pub_hex)

        cfg.app_log.warning.assert_called()
        # Inception txn is still created despite the announcement failure
        cfg.mongo.async_db.miner_transactions.replace_one.assert_awaited_once()


# ---------------------------------------------------------------------------
# _check_and_sweep_legacy_funds
# ---------------------------------------------------------------------------


class TestCheckAndSweepLegacyFunds(AsyncTestCase):
    async def test_same_address_skips(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(address="1SAME")
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.prerotated_key_hash = "1SAME"  # same as config.address

        with patch.object(mgr, "_sweep_legacy_to_kel", new=AsyncMock()) as mock_sweep:
            await mgr._check_and_sweep_legacy_funds([mock_entry])
        mock_sweep.assert_not_awaited()

    async def test_no_utxos_skips_sweep(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(address="1LEGACY")
        cfg.LatestBlock = MagicMock()
        cfg.LatestBlock.block.index = 100
        cfg.LatestBlock.block.hash = "abc"
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.prerotated_key_hash = "1KEL"

        async def _empty_gen(addr):
            return
            yield  # pragma: no cover

        cfg.BU = MagicMock()
        cfg.BU.get_wallet_unspent_transactions_for_spending = _empty_gen

        with patch.object(mgr, "_sweep_legacy_to_kel", new=AsyncMock()) as mock_sweep:
            await mgr._check_and_sweep_legacy_funds([mock_entry])
        mock_sweep.assert_not_awaited()

    async def test_with_utxos_calls_sweep(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(address="1LEGACY")
        cfg.LatestBlock = MagicMock()
        cfg.LatestBlock.block.index = 100
        cfg.LatestBlock.block.hash = "abc"
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.prerotated_key_hash = "1KEL"

        utxo = {"id": "utxo1", "outputs": [{"to": "1LEGACY", "value": 5.0}]}

        async def _gen(addr):
            yield utxo

        cfg.BU = MagicMock()
        cfg.BU.get_wallet_unspent_transactions_for_spending = _gen

        with patch.object(mgr, "_sweep_legacy_to_kel", new=AsyncMock()) as mock_sweep:
            await mgr._check_and_sweep_legacy_funds([mock_entry])
        mock_sweep.assert_awaited_once()
        # Cache must be invalidated after sweep
        self.assertNotIn("1LEGACY", mgr._kel_balance_cache)

    async def test_utxo_fetch_exception_skips_sweep(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(address="1LEGACY")
        cfg.LatestBlock = MagicMock()
        cfg.LatestBlock.block.index = 100
        cfg.LatestBlock.block.hash = "abc"
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.prerotated_key_hash = "1KEL"

        async def _bad_gen(addr):
            raise Exception("fetch error")
            yield  # pragma: no cover

        cfg.BU = MagicMock()
        cfg.BU.get_wallet_unspent_transactions_for_spending = _bad_gen

        with patch.object(mgr, "_sweep_legacy_to_kel", new=AsyncMock()) as mock_sweep:
            await mgr._check_and_sweep_legacy_funds([mock_entry])
        mock_sweep.assert_not_awaited()

    async def test_uses_cache_on_same_block(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(address="1LEGACY")
        cfg.LatestBlock = MagicMock()
        cfg.LatestBlock.block.index = 100
        cfg.LatestBlock.block.hash = "abc"
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.prerotated_key_hash = "1KEL"

        # Pre-populate cache
        mgr._kel_balance_cache["1LEGACY"] = {
            "utxos": [],
            "block_height": 100,
            "block_hash": "abc",
        }

        fetch_called = []

        async def _gen(addr):
            fetch_called.append(addr)
            yield {"id": "x", "outputs": [{"to": "1LEGACY", "value": 1.0}]}

        cfg.BU = MagicMock()
        cfg.BU.get_wallet_unspent_transactions_for_spending = _gen

        with patch.object(mgr, "_sweep_legacy_to_kel", new=AsyncMock()):
            await mgr._check_and_sweep_legacy_funds([mock_entry])

        # Cache hit — should not have called the generator
        self.assertEqual(fetch_called, [])

    async def test_latest_block_unavailable_returns_early(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(address="1LEGACY")
        # Make block.index raise when accessed as a property
        mock_block = MagicMock()
        type(mock_block).index = property(
            lambda self: (_ for _ in ()).throw(Exception("not ready"))
        )
        cfg.LatestBlock = MagicMock()
        cfg.LatestBlock.block = mock_block
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.prerotated_key_hash = "1KEL"

        with patch.object(mgr, "_sweep_legacy_to_kel", new=AsyncMock()) as mock_sweep:
            await mgr._check_and_sweep_legacy_funds([mock_entry])
        mock_sweep.assert_not_awaited()


# ---------------------------------------------------------------------------
# _sweep_legacy_to_kel
# ---------------------------------------------------------------------------


class TestSweepLegacyToKel(AsyncTestCase):
    async def test_submits_txn_to_mempool(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        cfg = _make_config(private_key=priv_hex, public_key=pub_hex)
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)

        mock_txn = MagicMock()
        mock_txn.hash = "HASH"
        mock_txn.transaction_signature = "SIG"
        mock_txn.to_dict.return_value = {"id": "SIG"}

        with patch("yadacoin.core.transaction.Transaction.do_money", new=AsyncMock()):
            with patch(
                "yadacoin.core.transaction.Transaction.generate_hash",
                new=AsyncMock(return_value="HASH"),
            ):
                await mgr._sweep_legacy_to_kel(sweep_target="1KELTarget", total=5.0)

        cfg.mongo.async_db.miner_transactions.replace_one.assert_awaited_once()

    async def test_exception_is_logged_not_raised(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock(
            side_effect=Exception("db error")
        )
        mgr = NodeKeyRotationManager(cfg)

        with patch("yadacoin.core.transaction.Transaction.do_money", new=AsyncMock()):
            with patch(
                "yadacoin.core.transaction.Transaction.generate_hash",
                new=AsyncMock(return_value="HASH"),
            ):
                # Should not raise
                await mgr._sweep_legacy_to_kel(sweep_target="1KEL", total=1.0)
        cfg.app_log.error.assert_called()

    async def test_broadcasts_when_node_mode(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        cfg = _make_config(private_key=priv_hex, public_key=pub_hex, modes=["node"])
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()

        peer_stream = MagicMock()
        peer_stream.peer.protocol_version = 2
        peer_stream.peer.rid = "rid1"

        async def _get_peers():
            yield peer_stream

        cfg.peer = MagicMock()
        cfg.peer.get_sync_peers = _get_peers
        cfg.nodeShared = MagicMock()
        cfg.nodeShared.write_params = AsyncMock()
        cfg.nodeClient = MagicMock()
        cfg.nodeClient.retry_messages = {}

        mgr = NodeKeyRotationManager(cfg)

        with patch("yadacoin.core.transaction.Transaction.do_money", new=AsyncMock()):
            with patch(
                "yadacoin.core.transaction.Transaction.generate_hash",
                new=AsyncMock(return_value="HASH"),
            ):
                await mgr._sweep_legacy_to_kel(sweep_target="1KEL", total=1.0)

        cfg.nodeShared.write_params.assert_awaited()

    async def test_broadcast_exception_logged_not_raised(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        cfg = _make_config(private_key=priv_hex, public_key=pub_hex, modes=["node"])
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        cfg.peer = MagicMock()
        cfg.peer.get_sync_peers = MagicMock(side_effect=Exception("peer error"))

        mgr = NodeKeyRotationManager(cfg)

        with patch("yadacoin.core.transaction.Transaction.do_money", new=AsyncMock()):
            with patch(
                "yadacoin.core.transaction.Transaction.generate_hash",
                new=AsyncMock(return_value="HASH"),
            ):
                await mgr._sweep_legacy_to_kel(sweep_target="1KEL", total=1.0)

        cfg.app_log.warning.assert_called()


# ---------------------------------------------------------------------------
# _update_active_kel_key — ratchet log pruning
# ---------------------------------------------------------------------------


class TestUpdateActiveKelKey(unittest.TestCase):
    def test_prunes_old_anchor_when_key_changes(self):
        """When kel_public_key changes, old anchor entries are pruned."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_bytes = bytes.fromhex(
            "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        )
        cfg = _make_config()
        cfg.kel_public_key = "OLD_PUB"  # pre-existing anchor
        cfg.mongo.async_db.kel_signing_log.delete_many = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.transaction_signature = "TXNID"
        mock_entry.mempool = False

        with patch("asyncio.ensure_future") as mock_ef:
            mgr._update_active_kel_key(
                [mock_entry],
                {"private_key": priv_bytes, "chain_code": priv_bytes},
                "sf",
            )

        # ensure_future was called with the prune coroutine
        mock_ef.assert_called_once()

    def test_no_prune_when_key_unchanged(self):
        """When old and new kel_public_key are the same, no prune is scheduled."""
        from unittest.mock import patch

        from coincurve import PrivateKey as CK

        from yadacoin.core.keyrotation import NodeKeyRotationManager, derive_secure_path

        priv_bytes = bytes.fromhex(
            "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        )
        k0 = {"private_key": priv_bytes, "chain_code": priv_bytes}
        # Compute what K1 will be (depth=1 entry in kel)
        k1 = derive_secure_path(priv_bytes, priv_bytes, "sf")
        k1_pub = CK(k1["private_key"]).public_key.format(compressed=True).hex()

        cfg = _make_config()
        cfg.kel_public_key = k1_pub  # already at the new value
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.transaction_signature = "TXNID"
        mock_entry.mempool = False

        with patch("asyncio.ensure_future") as mock_ef:
            mgr._update_active_kel_key([mock_entry], k0, "sf")

        mock_ef.assert_not_called()
