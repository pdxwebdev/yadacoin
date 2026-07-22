"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

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
    kel_anchor_private_key=None,
    kel_anchor_public_key=None,
    kel_anchor_address=None,
    kel_anchor_chain_code=None,
    config_path=None,
    modes=None,
    username="testnode",
):
    cfg = MagicMock()
    cfg.seed = seed
    cfg.private_key = private_key
    cfg.public_key = public_key
    cfg.address = address
    cfg.kel_anchor_private_key = kel_anchor_private_key
    cfg.kel_anchor_public_key = kel_anchor_public_key
    cfg.kel_anchor_address = kel_anchor_address
    cfg.kel_anchor_chain_code = kel_anchor_chain_code
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
                            "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                            new=AsyncMock(return_value=None),
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
        import bip32utils

        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(seed="bad seed phrase here")
        mgr = NodeKeyRotationManager(cfg)
        with patch.dict(os.environ, {"SECOND_FACTOR": "sf"}):
            with patch("yadacoin.core.keyrotation._fatal") as mock_fatal:
                mock_fatal.side_effect = SystemExit(1)
                # Use patch.object on the already-imported class rather than a
                # dotted string target. On Python 3.12+, unittest.mock resolves
                # dotted-string targets via pkgutil.resolve_name, which
                # eagerly re-imports "bip32utils.BIP32Key" as a submodule and
                # permanently overwrites the `BIP32Key` class attribute on the
                # `bip32utils` package namespace (bip32utils/__init__.py binds
                # the class under the same name as its containing submodule).
                # patch.object avoids that string-based re-import entirely.
                with patch.object(
                    bip32utils.BIP32Key, "fromEntropy", side_effect=Exception("bad")
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
                        "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                        new=AsyncMock(return_value=None),
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
        mock_entry.counter = 0

        with patch.dict(os.environ, {"SECOND_FACTOR": "mysecret"}):
            with patch("bip32utils.BIP32Key", self._make_bip32_mock()):
                with patch("mnemonic.Mnemonic") as mock_mn_cls:
                    mock_mn = MagicMock()
                    mock_mn.to_entropy.return_value = b"\x00" * 16
                    mock_mn_cls.return_value = mock_mn
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                        new=AsyncMock(return_value=mock_entry),
                    ):
                        with patch(
                            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
                            new=AsyncMock(return_value=mock_entry),
                        ):
                            with patch.object(
                                mgr, "_update_active_kel_key"
                            ) as mock_update:
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
        mock_entry.counter = 0

        with patch.dict(os.environ, {"SECOND_FACTOR": "mysecret"}):
            with patch("bip32utils.BIP32Key", self._make_bip32_mock()):
                with patch("mnemonic.Mnemonic") as mock_mn_cls:
                    mock_mn = MagicMock()
                    mock_mn.to_entropy.return_value = b"\x00" * 16
                    mock_mn_cls.return_value = mock_mn
                    with patch(
                        "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                        new=AsyncMock(return_value=mock_entry),
                    ):
                        with patch(
                            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
                            new=AsyncMock(return_value=mock_entry),
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
                        "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
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
                            "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
                            new=AsyncMock(return_value=None),
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
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=None),
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
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=None),
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
        mock_entry.counter = 0
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=mock_entry),
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
        mock_entry.counter = 0
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=mock_entry),
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
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=None),
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
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
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
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
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

        mgr._update_active_kel_key(1, mock_entry.public_key_hash, k0, "factor")

        # After 1 derive step, kel_anchor_private_key/public_key/address must be set
        self.assertIsNotNone(cfg.kel_anchor_private_key)
        self.assertIsNotNone(cfg.kel_anchor_public_key)
        self.assertIsNotNone(cfg.kel_anchor_address)
        self.assertIsInstance(cfg.kel_anchor_private_key, str)
        self.assertEqual(len(cfg.kel_anchor_private_key), 64)  # 32-byte hex

    def test_depth_zero_sets_k0_derived(self):
        from coincurve import PrivateKey as CK

        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)

        k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        # depth 0 — loop runs 0 times, cur stays k0

        mgr._update_active_kel_key(0, None, k0, "factor")

        # With depth=0, no derivation — kel key IS k0
        expected_pub = CK(_VALID_PRIV).public_key.format(compressed=True).hex()
        self.assertEqual(cfg.kel_anchor_public_key, expected_pub)

    def test_generate_deterministic_signature_exception_logged_not_raised(self):
        """Lines 1005-1006: when generate_deterministic_signature raises, the
        exception is caught and logged via app_log.debug — should not propagate."""
        from unittest.mock import patch

        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(username="testnode")
        mgr = NodeKeyRotationManager(cfg)

        priv_bytes = bytes.fromhex(
            "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        )
        k0 = {"private_key": priv_bytes, "chain_code": priv_bytes}

        with patch(
            "yadacoin.core.keyrotation.NodeKeyRotationManager.generate_deterministic_signature",
            side_effect=Exception("sig error"),
        ):
            # Must not raise
            mgr._update_active_kel_key(0, None, k0, "factor")

        cfg.app_log.debug.assert_called()


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
            await mgr._try_finalise(1, mock_entry.public_key_hash, {}, "sf")

        mock_update.assert_called_once()
        self.assertTrue(mgr._inception_complete)


# ---------------------------------------------------------------------------
# advance_auth_ratchet
# ---------------------------------------------------------------------------


class TestAdvanceAuthRatchet(AsyncTestCase):
    async def test_no_kel_key_calls_fatal(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                await mgr.advance_auth_ratchet()

    async def test_no_second_factor_calls_fatal(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            kel_anchor_private_key="511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694",
            kel_anchor_public_key="02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29",
        )
        mgr = NodeKeyRotationManager(cfg)

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SECOND_FACTOR", None)
            with self.assertRaises(SystemExit):
                await mgr.advance_auth_ratchet()

    async def test_derives_next_key_and_logs(self):
        import hashlib
        import hmac as _hmac

        from yadacoin.core.keyrotation import NodeKeyRotationManager, derive_secure_path

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        # Use derive_secure_path to get a proper BIP32 chain code for the test key.
        _cc = _hmac.new(bytes.fromhex(priv_hex), b"test-cc", hashlib.sha256).digest()
        _kn = derive_secure_path(bytes.fromhex(priv_hex), _cc, "mysecret")
        cc_hex = _kn["chain_code"].hex()
        cfg = _make_config(
            kel_anchor_private_key=priv_hex,
            kel_anchor_public_key=pub_hex,
            kel_anchor_chain_code=cc_hex,
        )
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.key_event_log.replace_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"

        with patch("yadacoin.core.transaction.Config", return_value=cfg):
            (
                priv_out,
                pub_out,
                conf_priv,
                conf_pub,
                tpkh,
            ) = await mgr.advance_auth_ratchet()

        # Current key (priv_out) is the anchor kel key — it signs the challenge
        self.assertEqual(priv_out, priv_hex)
        self.assertEqual(pub_out, pub_hex)
        # Confirming key is the NEXT derived key — must differ from the anchor
        self.assertIsNotNone(conf_priv)
        self.assertNotEqual(conf_priv, priv_hex)
        self.assertNotEqual(conf_pub, pub_hex)
        # Counter incremented
        self.assertEqual(mgr._auth_counter, 1)
        cfg.mongo.async_db.key_event_log.replace_one.assert_awaited_once()

    async def test_db_error_does_not_raise(self):
        import hashlib
        import hmac as _hmac

        from yadacoin.core.keyrotation import NodeKeyRotationManager, derive_secure_path

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        _cc = _hmac.new(bytes.fromhex(priv_hex), b"test-cc", hashlib.sha256).digest()
        _kn = derive_secure_path(bytes.fromhex(priv_hex), _cc, "mysecret")
        cc_hex = _kn["chain_code"].hex()
        cfg = _make_config(
            kel_anchor_private_key=priv_hex,
            kel_anchor_public_key=pub_hex,
            kel_anchor_chain_code=cc_hex,
        )
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.key_event_log.replace_one = AsyncMock(
            side_effect=Exception("db error")
        )
        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"

        # Should not raise
        with patch("yadacoin.core.transaction.Config", return_value=cfg):
            priv_out, pub_out, *_ = await mgr.advance_auth_ratchet()
        self.assertIsNotNone(priv_out)

    async def test_interval_triggers_reanchor(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        cfg = _make_config(
            kel_anchor_private_key=priv_hex, kel_anchor_public_key=pub_hex
        )
        cfg.mongo.async_db.key_event_log.replace_one = AsyncMock()
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

        with patch("yadacoin.core.transaction.Config", return_value=cfg):
            with patch.object(mgr, "_queue_reanchor", new=AsyncMock()) as mock_anchor:
                await mgr.advance_auth_ratchet()

        mock_anchor.assert_awaited_once()

    async def test_reanchor_error_does_not_raise(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        cfg = _make_config(
            kel_anchor_private_key=priv_hex, kel_anchor_public_key=pub_hex
        )
        cfg.mongo.async_db.key_event_log.replace_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"
        mgr._auth_counter = mgr.OFFCHAIN_ANCHOR_INTERVAL - 1
        mgr._auth_ratchet_key = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        mgr._auth_ratchet_pub = pub_hex

        with patch("yadacoin.core.transaction.Config", return_value=cfg):
            with patch.object(
                mgr, "_queue_reanchor", new=AsyncMock(side_effect=Exception("boom"))
            ):
                priv_out, pub_out, *_ = await mgr.advance_auth_ratchet()
        self.assertIsNotNone(priv_out)

    async def test_init_restores_from_tip(self):
        """When key_event_log has a prior tip, ratchet is fast-forwarded to it."""
        import hashlib
        import hmac as _hmac

        from yadacoin.core.keyrotation import NodeKeyRotationManager, derive_secure_path

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        _cc = _hmac.new(bytes.fromhex(priv_hex), b"test-cc", hashlib.sha256).digest()
        _base = derive_secure_path(bytes.fromhex(priv_hex), _cc, "mysecret")
        cc_hex = _base["chain_code"].hex()

        # Simulate 2 prior steps stored in key_event_log
        from bitcoin.wallet import P2PKHBitcoinAddress
        from coincurve import PrivateKey as _CK

        _step1 = derive_secure_path(
            _base["private_key"], _base["chain_code"], "mysecret"
        )
        _step2 = derive_secure_path(
            _step1["private_key"], _step1["chain_code"], "mysecret"
        )
        _step2_pub = _CK(_step2["private_key"]).public_key.format(compressed=True)
        _step2_addr = str(P2PKHBitcoinAddress.from_pubkey(_step2_pub))

        cfg = _make_config(
            kel_anchor_private_key=priv_hex,
            kel_anchor_public_key=pub_hex,
            kel_anchor_chain_code=cc_hex,
        )
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(
            return_value={
                "counter": 2,
                "public_key_hash": _step2_addr,
            }
        )
        cfg.mongo.async_db.key_event_log.replace_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"

        with patch("yadacoin.core.transaction.Config", return_value=cfg):
            await mgr.advance_auth_ratchet()

        # Counter should start from restored tip (2) + 1 advance = 3
        self.assertEqual(mgr._auth_counter, 3)
        # Ratchet key must have been initialized (not None)
        self.assertIsNotNone(mgr._auth_ratchet_key)

    async def test_init_legacy_no_chain_code_uses_k0(self):
        """Without kel_anchor_chain_code, ratchet is derived from _k0."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        # kel_anchor_chain_code NOT set → _fatal is called
        cfg = _make_config(
            kel_anchor_private_key=priv_hex, kel_anchor_public_key=pub_hex
        )
        cfg.kel_anchor_chain_code = None
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(return_value=None)
        cfg.mongo.async_db.key_event_log.replace_one = AsyncMock()

        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"
        mgr._k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        # Enable test mode so _fatal raises RuntimeError instead of sys.exit
        NodeKeyRotationManager._TEST_MODE = True
        try:
            with self.assertRaises(RuntimeError) as ctx:
                await mgr.advance_auth_ratchet()
            self.assertIn("kel_anchor_chain_code missing", str(ctx.exception))
        finally:
            NodeKeyRotationManager._TEST_MODE = False

    async def test_init_no_chain_code_no_k0_calls_fatal(self):
        """Without kel_anchor_chain_code and without _k0, _fatal is called."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        cfg = _make_config(
            kel_anchor_private_key=priv_hex, kel_anchor_public_key=pub_hex
        )
        cfg.kel_anchor_chain_code = None
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(return_value=None)

        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"
        # _k0 is None → can't derive chain code → fatal

        with self.assertRaises(SystemExit):
            await mgr.advance_auth_ratchet()


class TestAdvanceBlockRatchet(AsyncTestCase):
    async def test_sets_block_keys_calls_reanchor_and_returns_triplet(self):
        import hashlib
        import hmac as _hmac

        from yadacoin.core.keyrotation import (
            NodeKeyRotationManager,
            ReanchorTriplet,
            derive_secure_path,
        )

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        _cc = _hmac.new(bytes.fromhex(priv_hex), b"test-cc", hashlib.sha256).digest()
        _kn = derive_secure_path(bytes.fromhex(priv_hex), _cc, "mysecret")
        cc_hex = _kn["chain_code"].hex()
        cfg = _make_config(
            kel_anchor_private_key=priv_hex,
            kel_anchor_public_key=pub_hex,
            kel_anchor_chain_code=cc_hex,
        )
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(return_value=None)
        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"

        block = MagicMock()
        fake_unconfirmed = MagicMock()
        fake_confirming = MagicMock()
        fake_triplet = ReanchorTriplet(
            unconfirmed=fake_unconfirmed,
            confirming=fake_confirming,
            signer_private_key=priv_hex,
            signer_public_key=pub_hex,
            coinbase_prerotated="1next",
            coinbase_twice_prerotated="1twoahead",
            coinbase_public_key_hash="1prev",
            coinbase_prev_public_key_hash="",
        )
        with patch.object(
            mgr, "_queue_reanchor", new=AsyncMock(return_value=fake_triplet)
        ), patch("yadacoin.core.transaction.Config", return_value=cfg):
            result = await mgr.advance_block_ratchet(block=block)

        self.assertIsInstance(result, ReanchorTriplet)
        self.assertEqual(result.unconfirmed, fake_unconfirmed)
        self.assertEqual(result.confirming, fake_confirming)
        self.assertEqual(result.signer_private_key, priv_hex)
        self.assertEqual(result.signer_public_key, pub_hex)
        self.assertEqual(result.coinbase_prerotated, "1next")
        self.assertEqual(result.coinbase_twice_prerotated, "1twoahead")
        self.assertEqual(result.coinbase_public_key_hash, "1prev")
        self.assertEqual(result.coinbase_prev_public_key_hash, "")

    async def test_no_kel_key_calls_fatal(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)
        block = MagicMock()

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                await mgr.advance_block_ratchet(block=block)

    async def test_no_second_factor_calls_fatal(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(
            kel_anchor_private_key="511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694",
            kel_anchor_public_key="02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29",
        )
        mgr = NodeKeyRotationManager(cfg)
        block = MagicMock()

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SECOND_FACTOR", None)
            with self.assertRaises(SystemExit):
                await mgr.advance_block_ratchet(block=block)


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

        cfg = _make_config()  # kel_anchor_public_key is None
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": bytes(32), "chain_code": bytes(32)}
        mgr._second_factor = "sf"
        await mgr._queue_reanchor()

    async def test_no_onchain_kel_returns_early(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(kel_anchor_public_key="02pub")
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=None),
        ):
            await mgr._queue_reanchor()

    async def test_kel_build_exception_returns_early(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(kel_anchor_public_key="02pub")
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(side_effect=Exception("db error")),
        ):
            await mgr._queue_reanchor()  # must not raise

    async def test_success_submits_two_txns(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(kel_anchor_public_key="02pub")
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        cfg.mongo.async_db.key_event_log = MagicMock()
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(return_value=None)
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        mgr._second_factor = "mysecret"

        from bitcoin.wallet import P2PKHBitcoinAddress
        from coincurve import PrivateKey as CK

        from yadacoin.core.keyrotation import derive_secure_path

        _k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        step1 = derive_secure_path(_k0["private_key"], _k0["chain_code"], "mysecret")
        step1_pub = CK(step1["private_key"]).public_key.format(compressed=True)
        step1_addr = str(P2PKHBitcoinAddress.from_pubkey(step1_pub))

        mock_entry = MagicMock()
        mock_entry.public_key_hash = "1SomeAddress"
        mock_entry.prerotated_key_hash = step1_addr
        mock_entry.counter = 0

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=mock_entry),
        ):
            await mgr._queue_reanchor()

        # Both transactions should have been upserted
        self.assertEqual(
            cfg.mongo.async_db.miner_transactions.replace_one.await_count, 2
        )

    async def test_broadcasts_in_node_mode(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(kel_anchor_public_key="02pub", modes=["node"])
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        cfg.mongo.async_db.key_event_log = MagicMock()
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(return_value=None)

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

        from bitcoin.wallet import P2PKHBitcoinAddress
        from coincurve import PrivateKey as CK

        from yadacoin.core.keyrotation import derive_secure_path

        _k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        step1 = derive_secure_path(_k0["private_key"], _k0["chain_code"], "mysecret")
        step1_pub = CK(step1["private_key"]).public_key.format(compressed=True)
        step1_addr = str(P2PKHBitcoinAddress.from_pubkey(step1_pub))

        mock_entry = MagicMock()
        mock_entry.public_key_hash = "1SomeAddress"
        mock_entry.prerotated_key_hash = step1_addr
        mock_entry.counter = 0

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=mock_entry),
        ):
            await mgr._queue_reanchor()

        cfg.nodeShared.write_params.assert_awaited()

    async def test_broadcast_exception_logged(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(kel_anchor_public_key="02pub", modes=["node"])
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        cfg.mongo.async_db.key_event_log = MagicMock()
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(return_value=None)
        cfg.peer = MagicMock()
        cfg.peer.get_sync_peers = MagicMock(side_effect=Exception("peer err"))

        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        mgr._second_factor = "mysecret"

        from bitcoin.wallet import P2PKHBitcoinAddress
        from coincurve import PrivateKey as CK

        from yadacoin.core.keyrotation import derive_secure_path

        _k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        step1 = derive_secure_path(_k0["private_key"], _k0["chain_code"], "mysecret")
        step1_pub = CK(step1["private_key"]).public_key.format(compressed=True)
        step1_addr = str(P2PKHBitcoinAddress.from_pubkey(step1_pub))

        mock_entry = MagicMock()
        mock_entry.public_key_hash = "1SomeAddress"
        mock_entry.prerotated_key_hash = step1_addr
        mock_entry.counter = 0

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=mock_entry),
        ):
            await mgr._queue_reanchor()

        cfg.app_log.warning.assert_called()

    async def test_block_path_returns_reanchor_triplet(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager, ReanchorTriplet

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(kel_anchor_public_key="02pub")
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        cfg.mongo.async_db.key_event_log = MagicMock()
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(return_value=None)
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        mgr._second_factor = "mysecret"

        block = MagicMock()
        # Derive the first key so the while loop finds a match
        from bitcoin.wallet import P2PKHBitcoinAddress
        from coincurve import PrivateKey as CK

        from yadacoin.core.keyrotation import derive_secure_path

        _k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        step1 = derive_secure_path(_k0["private_key"], _k0["chain_code"], "mysecret")
        step1_pub = CK(step1["private_key"]).public_key.format(compressed=True)
        step1_addr = str(P2PKHBitcoinAddress.from_pubkey(step1_pub))

        mock_entry = MagicMock()
        mock_entry.public_key_hash = "1SomeAddress"
        mock_entry.prerotated_key_hash = step1_addr
        mock_entry.counter = 0

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=mock_entry),
        ):
            result = await mgr._queue_reanchor(
                block=block,
                signer_private_key=priv_hex,
                signer_public_key="02signer",
                relationship="block reanchor",
                coinbase_prerotated="1prerot",
                coinbase_twice_prerotated="1twice",
                coinbase_public_key_hash="1pkh",
                coinbase_prev_public_key_hash="1prevpkh",
            )

        self.assertIsInstance(result, ReanchorTriplet)
        self.assertIsNotNone(result.unconfirmed)
        self.assertIsNotNone(result.confirming)

    async def test_block_path_no_kel_returns_triplet_with_none(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager, ReanchorTriplet

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)
        block = MagicMock()

        result = await mgr._queue_reanchor(
            block=block,
            signer_private_key="priv",
            signer_public_key="pub",
        )
        self.assertIsInstance(result, ReanchorTriplet)
        self.assertIsNone(result.unconfirmed)

    async def test_block_path_no_kel_pub_returns_triplet_with_none(self):
        """When k0/second_factor are set but kel_anchor_public_key is missing,
        the block-path early return (line ~720) must still build a
        ReanchorTriplet with None fields instead of returning bare None."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager, ReanchorTriplet

        cfg = _make_config()  # kel_anchor_public_key is None
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"
        block = MagicMock()

        result = await mgr._queue_reanchor(
            block=block,
            signer_private_key="priv",
            signer_public_key="pub",
        )
        self.assertIsInstance(result, ReanchorTriplet)
        self.assertIsNone(result.unconfirmed)
        self.assertIsNone(result.confirming)

    async def test_block_path_kel_build_exception_returns_triplet_with_none(self):
        """When KeyEventLog.build_from_public_key raises, the block-path
        exception handler (line ~743) must build a ReanchorTriplet with
        None fields instead of returning bare None."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager, ReanchorTriplet

        cfg = _make_config(kel_anchor_public_key="02pub")
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"
        block = MagicMock()

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(side_effect=Exception("db error")),
        ):
            result = await mgr._queue_reanchor(
                block=block,
                signer_private_key="priv",
                signer_public_key="pub",
            )
        self.assertIsInstance(result, ReanchorTriplet)
        self.assertIsNone(result.unconfirmed)

    async def test_block_path_empty_kel_returns_triplet_with_none(self):
        """When the on-chain KEL is empty, the block-path early return
        (line ~756) must build a ReanchorTriplet with None fields instead
        of returning bare None."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager, ReanchorTriplet

        cfg = _make_config(kel_anchor_public_key="02pub")
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {"private_key": _VALID_PRIV, "chain_code": _VALID_PRIV}
        mgr._second_factor = "sf"
        block = MagicMock()

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=None),
        ):
            result = await mgr._queue_reanchor(
                block=block,
                signer_private_key="priv",
                signer_public_key="pub",
            )
        self.assertIsInstance(result, ReanchorTriplet)
        self.assertIsNone(result.unconfirmed)

    async def test_walks_kel_with_multiple_derivation_steps(self):
        """When the on-chain KEL entry's prerotated_key_hash only matches
        after more than one derivation step from K0, the inner while-loop
        that walks forward to find K_n (lines ~779-786) must iterate."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(kel_anchor_public_key="02pub")
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        cfg.mongo.async_db.key_event_log = MagicMock()
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(return_value=None)
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        mgr._second_factor = "mysecret"

        from bitcoin.wallet import P2PKHBitcoinAddress
        from coincurve import PrivateKey as CK

        from yadacoin.core.keyrotation import derive_secure_path

        _k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        step1 = derive_secure_path(_k0["private_key"], _k0["chain_code"], "mysecret")
        step2 = derive_secure_path(
            step1["private_key"], step1["chain_code"], "mysecret"
        )
        step2_pub = CK(step2["private_key"]).public_key.format(compressed=True)
        step2_addr = str(P2PKHBitcoinAddress.from_pubkey(step2_pub))

        mock_entry = MagicMock()
        mock_entry.public_key_hash = "1SomeAddress"
        # Requires TWO derivation steps from K0 to match — the first
        # derivation (before the while-loop) won't match, forcing the
        # inner while-loop body to run at least once before it breaks.
        mock_entry.prerotated_key_hash = step2_addr
        mock_entry.counter = 0

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=mock_entry),
        ):
            await mgr._queue_reanchor()

        self.assertEqual(
            cfg.mongo.async_db.miner_transactions.replace_one.await_count, 2
        )

    async def test_jump_search_finds_txn_doc_and_iterates(self):
        """When the forward-search find_one lookup returns a real anchor
        document, the code must re-query for that anchor's tip and walk
        ``jump_cur`` forward until it matches the tip's
        prerotated_key_hash (lines ~810-820)."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(kel_anchor_public_key="02pub")
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)
        mgr._k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        mgr._second_factor = "mysecret"

        from bitcoin.wallet import P2PKHBitcoinAddress
        from coincurve import PrivateKey as CK

        from yadacoin.core.keyrotation import derive_secure_path

        _k0 = {
            "private_key": bytes.fromhex(priv_hex),
            "chain_code": bytes.fromhex(priv_hex),
        }
        step1 = derive_secure_path(
            _k0["private_key"], _k0["chain_code"], "mysecret"
        )  # this becomes kn
        step2 = derive_secure_path(
            step1["private_key"], step1["chain_code"], "mysecret"
        )  # this becomes kn1 / jump_cur start
        step3 = derive_secure_path(
            step2["private_key"], step2["chain_code"], "mysecret"
        )  # one derivation past jump_cur's start — forces the while-loop

        step1_pub = CK(step1["private_key"]).public_key.format(compressed=True)
        step1_addr = str(P2PKHBitcoinAddress.from_pubkey(step1_pub))
        step3_pub = CK(step3["private_key"]).public_key.format(compressed=True)
        step3_addr = str(P2PKHBitcoinAddress.from_pubkey(step3_pub))

        mock_entry = MagicMock()
        mock_entry.public_key_hash = "1SomeAddress"
        # Matches after ONE derivation step so kn == step1 with no inner
        # while-loop iteration needed in the earlier KEL-walk block.
        mock_entry.prerotated_key_hash = step1_addr
        mock_entry.counter = 0

        cfg.mongo.async_db.key_event_log = MagicMock()
        cfg.mongo.async_db.key_event_log.find_one = AsyncMock(
            side_effect=[
                # First call: forward search by prev_public_key_hash — truthy
                # result triggers the "found an anchor" branch.
                {"anchor_public_key": "02anchor"},
                # Second call: fetch that anchor's current tip. Its
                # prerotated_key_hash is one derivation past jump_cur's
                # current address, forcing the while-loop to iterate once.
                {"prerotated_key_hash": step3_addr, "counter": 5},
            ]
        )

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=mock_entry),
        ):
            await mgr._queue_reanchor()

        self.assertEqual(cfg.mongo.async_db.key_event_log.find_one.await_count, 2)
        self.assertEqual(
            cfg.mongo.async_db.miner_transactions.replace_one.await_count, 2
        )


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

    async def test_identity_announcement_success_builds_real_hash(self):
        """When a valid ``kel_anchor_private_key`` is available on the real
        Config() singleton, ``generate_deterministic_signature`` returns a
        real signature and the IdentityAnnouncement is built and hashed
        successfully (the non-exception path through the try block)."""
        from yadacoin.core.config import Config
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        cfg = _make_config(username="testnode")
        cfg.ssl = None
        cfg.mongo.async_db.miner_transactions.replace_one = AsyncMock()
        mgr = NodeKeyRotationManager(cfg)

        priv_bytes = bytes.fromhex(priv_hex)
        k0 = {"private_key": priv_bytes, "chain_code": priv_bytes}
        from coincurve import PrivateKey as CK

        k0_pub_hex = CK(priv_bytes).public_key.format(compressed=True).hex()

        # generate_deterministic_signature() reads from the real Config()
        # singleton (not self.config), so a real kel_anchor_private_key
        # must be present there for it to sign successfully instead of
        # short-circuiting to "".
        real_config = Config()
        with patch.object(real_config, "kel_anchor_private_key", priv_hex, create=True):
            await mgr._create_inception(k0, "mysecret", k0_pub_hex)

        cfg.app_log.warning.assert_not_called()
        cfg.mongo.async_db.miner_transactions.replace_one.assert_awaited_once()
        (
            stored_filter,
            stored_doc,
            *_,
        ) = cfg.mongo.async_db.miner_transactions.replace_one.call_args.args
        self.assertNotEqual(stored_doc["relationship_hash"], "")
        self.assertEqual(stored_doc["relationship"]["identity"]["username"], "testnode")


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
            await mgr._check_and_sweep_legacy_funds(mock_entry)
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
            await mgr._check_and_sweep_legacy_funds(mock_entry)
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
            await mgr._check_and_sweep_legacy_funds(mock_entry)
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
            await mgr._check_and_sweep_legacy_funds(mock_entry)
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
            await mgr._check_and_sweep_legacy_funds(mock_entry)

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
            await mgr._check_and_sweep_legacy_funds(mock_entry)
        mock_sweep.assert_not_awaited()

    async def test_utxo_fetch_stops_at_chain_input_limit(self):
        """When more than 100 UTXOs are available, the fetch loop must
        break at exactly 100 (obeying the on-chain input limit) instead of
        collecting all of them (line ~1203)."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config(address="1LEGACY")
        cfg.LatestBlock = MagicMock()
        cfg.LatestBlock.block.index = 100
        cfg.LatestBlock.block.hash = "abc"
        mgr = NodeKeyRotationManager(cfg)

        mock_entry = MagicMock()
        mock_entry.prerotated_key_hash = "1KEL"

        yielded = []

        async def _gen(addr):
            for i in range(150):
                utxo = {
                    "id": f"utxo{i}",
                    "outputs": [{"to": "1LEGACY", "value": 1.0}],
                }
                yielded.append(utxo)
                yield utxo

        cfg.BU = MagicMock()
        cfg.BU.get_wallet_unspent_transactions_for_spending = _gen

        with patch.object(mgr, "_sweep_legacy_to_kel", new=AsyncMock()) as mock_sweep:
            await mgr._check_and_sweep_legacy_funds(mock_entry)

        mock_sweep.assert_awaited_once()
        # The break must stop consumption at 100, well short of the 150
        # the generator could have produced.
        self.assertEqual(len(yielded), 100)
        self.assertEqual(mock_sweep.call_args.kwargs["total"], 100.0)

    async def test_pool_peer_type_skips_legacy_sweep(self):
        """Lines 1660-1664: pool nodes log and return without sweeping."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager
        from yadacoin.enums.peertypes import PEER_TYPES

        cfg = _make_config(address="1LEGACY")
        cfg.peer_type = PEER_TYPES.POOL.value
        cfg.LatestBlock = MagicMock()
        cfg.LatestBlock.block.index = 100
        cfg.LatestBlock.block.hash = "abc"

        async def _gen(addr):
            yield {"id": "u1", "outputs": [{"to": "1LEGACY", "value": 5.0}]}

        cfg.BU = MagicMock()
        cfg.BU.get_wallet_unspent_transactions_for_spending = _gen
        mgr = NodeKeyRotationManager(cfg)
        mock_entry = MagicMock()
        mock_entry.prerotated_key_hash = "1KEL"

        with patch.object(mgr, "_sweep_legacy_to_kel", new=AsyncMock()) as mock_sweep:
            await mgr._check_and_sweep_legacy_funds(mock_entry)
        mock_sweep.assert_not_awaited()
        cfg.app_log.info.assert_any_call(
            "NodeKeyRotationManager: skipping legacy sweep for pool node."
        )


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
# generate_deterministic_signature
# ---------------------------------------------------------------------------


class TestGenerateDeterministicSignature(unittest.TestCase):
    def test_returns_signature_when_kel_anchor_key_present(self):
        """generate_deterministic_signature() reads from the real Config()
        singleton (not self.config). When a valid kel_anchor_private_key
        is present there, it must actually sign and return a non-empty
        base64 string (lines ~1308-1310) instead of short-circuiting to
        "" via the missing-attribute guard."""
        from yadacoin.core.config import Config
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        real_config = Config()
        with patch.object(real_config, "kel_anchor_private_key", priv_hex, create=True):
            sig = NodeKeyRotationManager.generate_deterministic_signature("hello")

        self.assertIsInstance(sig, str)
        self.assertGreater(len(sig), 0)

        # Deterministic: same message + same key => same signature.
        with patch.object(real_config, "kel_anchor_private_key", priv_hex, create=True):
            sig2 = NodeKeyRotationManager.generate_deterministic_signature("hello")
        self.assertEqual(sig, sig2)

    def test_returns_empty_string_when_no_kel_anchor_key(self):
        from yadacoin.core.config import Config
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        real_config = Config()
        # Ensure the attribute genuinely does not exist on the singleton.
        if hasattr(real_config, "kel_anchor_private_key"):
            delattr(real_config, "kel_anchor_private_key")
        sig = NodeKeyRotationManager.generate_deterministic_signature("hello")
        self.assertEqual(sig, "")


# ---------------------------------------------------------------------------
# generate_signature
# ---------------------------------------------------------------------------


class TestGenerateSignature(AsyncTestCase):
    async def test_returns_pub_and_signature(self):
        """generate_signature() delegates to advance_auth_ratchet() for the
        current KEL tip key and signs with it via _sign() (lines
        ~1336-1337)."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_config()
        mgr = NodeKeyRotationManager(cfg)

        priv_hex = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
        pub_hex = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
        fake_ratchet_result = (priv_hex, pub_hex, "confpriv", "confpub", "1twoahead")

        with patch.object(
            mgr,
            "advance_auth_ratchet",
            new=AsyncMock(return_value=fake_ratchet_result),
        ):
            result_pub, result_sig = await mgr.generate_signature("hello world")

        self.assertEqual(result_pub, pub_hex)
        self.assertIsInstance(result_sig, str)


# ---------------------------------------------------------------------------
# Per-peer KEL branches (advance_peer_auth_ratchet / peer_branch_anchor_pub)
# ---------------------------------------------------------------------------


class _FakeKeyEventLogCollection:
    """Minimal in-memory stand-in for the ``key_event_log`` Mongo collection,
    sufficient for exercising the peer-branch upsert/tip-lookup logic without
    a real database."""

    def __init__(self):
        self.docs = []

    async def find_one(self, filt, sort=None):
        matches = [d for d in self.docs if self._matches(d, filt)]
        if not matches:
            return None
        if sort:
            key, direction = sort[0]
            matches.sort(key=lambda d: d.get(key, 0), reverse=(direction == -1))
        return matches[0]

    async def replace_one(self, filt, doc, upsert=False):
        for i, d in enumerate(self.docs):
            if self._matches(d, filt):
                self.docs[i] = doc
                return
        if upsert:
            self.docs.append(doc)

    @staticmethod
    def _matches(doc, filt):
        return all(doc.get(k) == v for k, v in filt.items())


def _make_branch_config(priv_hex, pub_hex, cc_hex):
    cfg = _make_config(
        kel_anchor_private_key=priv_hex,
        kel_anchor_public_key=pub_hex,
        kel_anchor_chain_code=cc_hex,
    )
    cfg.mongo.async_db.key_event_log = _FakeKeyEventLogCollection()
    # bridge minting calls get_latest(self.config.inception.public_key, ...)
    cfg.inception = MagicMock()
    cfg.inception.public_key = pub_hex
    return cfg


class TestPeerBranchAuthRatchet(AsyncTestCase):
    # These represent K0 (the genesis/inception key), not K_n — peer
    # branches now root at the *current on-chain/mempool anchor*, which
    # _resolve_latest_kel_anchor derives fresh by walking `KEL_DEPTH` steps
    # forward from K0 (simulating however many rotations have already been
    # confirmed on-chain or sit in the mempool).
    PRIV_HEX = "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
    PUB_HEX = "02610faeab27d8a467c637848a6d581b9d9df9d6e7266096467e15427db698cc29"
    KEL_DEPTH = 2  # pretend 2 rotations already exist on-chain/in mempool

    def _cc_hex(self):
        import hashlib
        import hmac as _hmac

        return (
            _hmac.new(bytes.fromhex(self.PRIV_HEX), b"test-cc", hashlib.sha256)
            .digest()
            .hex()
        )

    def _make_mgr(self, cfg, kel_depth=None):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"
        mgr._k0 = {
            "private_key": bytes.fromhex(self.PRIV_HEX),
            "chain_code": bytes.fromhex(self._cc_hex()),
        }
        mgr._test_kel_depth = self.KEL_DEPTH if kel_depth is None else kel_depth
        return mgr

    def _patch_kel_depth(self, mgr):
        """Patch KeyEventLog.get_latest so
        _resolve_latest_kel_anchor sees a KEL entry with counter=depth-1.
        public_key_hash is required when minting the peer bridge entry."""
        fake_entry = MagicMock()
        fake_entry.counter = mgr._test_kel_depth - 1
        fake_entry.public_key_hash = "1LatestKelTipAddress"
        return patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=fake_entry),
        )

    async def test_peer_branch_anchor_first_use_creates_branch(self):
        """peer_branch_anchor_pub is read-only, but once
        advance_peer_auth_ratchet has established a branch, it must return
        that branch's stable anchor — unique per peer, and different from
        raw K0."""
        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())
        mgr = self._make_mgr(cfg)

        # No branch yet → read-only lookup returns ""
        self.assertEqual(await mgr.peer_branch_anchor_pub("peerA_sig"), "")

        with self._patch_kel_depth(mgr), patch(
            "yadacoin.core.transaction.Config", return_value=cfg
        ):
            await mgr.advance_peer_auth_ratchet("peerA_username_signature")
            await mgr.advance_peer_auth_ratchet("peerB_username_signature")

        anchor_a = await mgr.peer_branch_anchor_pub("peerA_username_signature")
        anchor_b = await mgr.peer_branch_anchor_pub("peerB_username_signature")

        self.assertTrue(anchor_a)
        self.assertTrue(anchor_b)
        self.assertNotEqual(anchor_a, anchor_b)
        self.assertNotEqual(anchor_a, self.PUB_HEX)

    async def test_peer_branch_anchor_no_branch_returns_empty(self):
        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())
        mgr = self._make_mgr(cfg)
        self.assertEqual(await mgr.peer_branch_anchor_pub("peerA_sig"), "")
        self.assertEqual(await mgr.peer_branch_anchor_pub(""), "")

    async def test_first_contact_creates_signed_bridge_entry(self):
        """First advance for a new peer must persist a K_n → Kp0 bridge entry
        signed by K_n (the current on-chain/mempool anchor, not raw K0),
        with counter=0 and root_depth recorded, before returning Kp0 as the
        signing key."""
        from yadacoin.core.transaction import Transaction

        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())
        mgr = self._make_mgr(cfg)

        with self._patch_kel_depth(mgr), patch(
            "yadacoin.core.transaction.Config", return_value=cfg
        ):
            (
                cur_priv,
                cur_pub,
                next_priv,
                next_pub,
                two_ahead_pkh,
                is_new_branch,
            ) = await mgr.advance_peer_auth_ratchet("peerA_username_signature")

        # First call signs with Kp0 itself (counter 0 → position 0 → position 1)
        self.assertTrue(is_new_branch)
        self.assertEqual(
            cur_pub, await mgr.peer_branch_anchor_pub("peerA_username_signature")
        )
        self.assertNotEqual(cur_pub, self.PUB_HEX)
        self.assertNotEqual(next_pub, cur_pub)

        docs = cfg.mongo.async_db.key_event_log.docs
        self.assertEqual(len(docs), 2)  # bridge (counter 0) + first advance (counter 1)

        bridge = next(d for d in docs if d["counter"] == 0)
        # public_key is K_n (K0 advanced KEL_DEPTH steps), NOT raw K0.
        self.assertNotEqual(bridge["public_key"], self.PUB_HEX)
        self.assertEqual(bridge["branch_peer"], "peerA_username_signature")
        self.assertEqual(bridge["root_depth"], self.KEL_DEPTH)
        self.assertEqual(bridge["prerotated_key_hash"], docs[0]["prerotated_key_hash"])

        # The bridge txn must carry a real signature verifiable against K_n,
        # and a hash matching a fresh recompute (the bug this fixes: a blank
        # signature/hash would make every peer reject the branch).
        bridge_txn = Transaction.from_dict(bridge["txn"])
        self.assertTrue(bridge_txn.transaction_signature)
        self.assertTrue(bridge_txn.hash)
        recomputed_hash = await bridge_txn.generate_hash()
        self.assertEqual(recomputed_hash, bridge_txn.hash)

    async def test_advance_signs_ratchet_txn(self):
        """Regression test for the missing-signature bug: every entry written
        by advance_peer_auth_ratchet must have a valid hash + signature."""
        from yadacoin.core.transaction import Transaction

        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())
        mgr = self._make_mgr(cfg)

        with self._patch_kel_depth(mgr), patch(
            "yadacoin.core.transaction.Config", return_value=cfg
        ):
            await mgr.advance_peer_auth_ratchet("peerA_username_signature")
            await mgr.advance_peer_auth_ratchet("peerA_username_signature")

        docs = cfg.mongo.async_db.key_event_log.docs
        self.assertEqual(len(docs), 3)  # bridge + 2 advances
        for doc in docs:
            txn = Transaction.from_dict(doc["txn"])
            if doc["counter"] == 0:
                continue  # bridge already checked above
            self.assertTrue(txn.transaction_signature, "entry missing signature")
            self.assertTrue(txn.hash, "entry missing hash")
            recomputed = await txn.generate_hash()
            self.assertEqual(recomputed, txn.hash)

    async def test_global_advance_auth_ratchet_signs_txn(self):
        """Same signature-bug regression, but for the global (non-branched)
        advance_auth_ratchet path used by generate_signature()/node
        announcements."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager
        from yadacoin.core.transaction import Transaction

        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())
        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"

        with patch("yadacoin.core.transaction.Config", return_value=cfg):
            await mgr.advance_auth_ratchet()

        docs = cfg.mongo.async_db.key_event_log.docs
        self.assertEqual(len(docs), 1)
        txn = Transaction.from_dict(docs[0]["txn"])
        self.assertTrue(txn.transaction_signature)
        self.assertTrue(txn.hash)
        recomputed = await txn.generate_hash()
        self.assertEqual(recomputed, txn.hash)

    async def test_peer_branches_are_isolated(self):
        """Entries written for peer A must never appear in peer B's branch
        (and vice versa) — the core scalability fix."""
        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())
        mgr = self._make_mgr(cfg)

        with self._patch_kel_depth(mgr), patch(
            "yadacoin.core.transaction.Config", return_value=cfg
        ):
            # Peer A reconnects 3 times, peer B reconnects once.
            for _ in range(3):
                await mgr.advance_peer_auth_ratchet("peerA_sig")
            await mgr.advance_peer_auth_ratchet("peerB_sig")

        anchor_a = await mgr.peer_branch_anchor_pub("peerA_sig")
        anchor_b = await mgr.peer_branch_anchor_pub("peerB_sig")
        docs = cfg.mongo.async_db.key_event_log.docs

        a_docs = [d for d in docs if d["anchor_public_key"] == anchor_a]
        b_docs = [d for d in docs if d["anchor_public_key"] == anchor_b]

        self.assertEqual(len(a_docs), 4)  # bridge + 3 advances
        self.assertEqual(len(b_docs), 2)  # bridge + 1 advance
        # No overlap between the two peers' entries at all.
        a_ids = {d["id"] for d in a_docs}
        b_ids = {d["id"] for d in b_docs}
        self.assertEqual(a_ids & b_ids, set())

    async def test_resumes_branch_tip_across_calls(self):
        """A brand new manager instance (simulating a restart) must resume
        the peer's branch from its persisted tip rather than re-minting a
        bridge entry — even though the "current" on-chain/mempool anchor may
        have moved on by the time of the restart."""
        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())

        mgr1 = self._make_mgr(cfg, kel_depth=2)
        with self._patch_kel_depth(mgr1), patch(
            "yadacoin.core.transaction.Config", return_value=cfg
        ):
            await mgr1.advance_peer_auth_ratchet("peerA_sig")
            (
                _,
                _,
                expected_next_priv,
                expected_next_pub,
                _,
                _,
            ) = await mgr1.advance_peer_auth_ratchet("peerA_sig")

        # Simulate a process restart *and* that 3 more on-chain/mempool
        # rotations have happened since (kel_depth moved from 2 → 5). The
        # resumed branch must still use the ORIGINAL root (depth 2, recorded
        # on the bridge entry), not blindly re-root at the new "latest".
        mgr2 = self._make_mgr(cfg, kel_depth=5)
        with self._patch_kel_depth(mgr2), patch(
            "yadacoin.core.transaction.Config", return_value=cfg
        ):
            cur_priv, cur_pub, *_ = await mgr2.advance_peer_auth_ratchet("peerA_sig")

        # mgr2 must resume from the tip mgr1 left behind, not restart at Kp0
        # and not re-root against the now-advanced "latest" anchor.
        self.assertEqual(cur_priv, expected_next_priv)
        self.assertEqual(cur_pub, expected_next_pub)

        docs = cfg.mongo.async_db.key_event_log.docs
        anchor = await mgr2.peer_branch_anchor_pub("peerA_sig")
        branch_docs = [d for d in docs if d["anchor_public_key"] == anchor]
        # bridge(0) + mgr1's 2 advances(1,2) + mgr2's 1 advance(3) = 4 entries
        self.assertEqual(len(branch_docs), 4)
        self.assertEqual(max(d["counter"] for d in branch_docs), 3)
        # Still exactly one bridge entry for this peer — no re-minting.
        self.assertEqual(len([d for d in branch_docs if d["counter"] == 0]), 1)

    async def test_missing_peer_username_signature_is_fatal(self):
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())
        mgr = self._make_mgr(cfg)

        NodeKeyRotationManager._TEST_MODE = True
        try:
            with self.assertRaises(RuntimeError) as ctx:
                await mgr.advance_peer_auth_ratchet("")
            self.assertIn("username_signature", str(ctx.exception))
        finally:
            NodeKeyRotationManager._TEST_MODE = False

    async def test_missing_k0_is_fatal(self):
        """If K0 hasn't been derived yet (startup_check hasn't run), minting
        a new peer branch must fail loudly rather than silently rooting at
        garbage."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())
        mgr = NodeKeyRotationManager(cfg)
        mgr._second_factor = "mysecret"
        mgr._k0 = None  # never derived

        NodeKeyRotationManager._TEST_MODE = True
        try:
            with self.assertRaises(RuntimeError) as ctx:
                await mgr.advance_peer_auth_ratchet("peerA_sig")
            self.assertIn("KEL signing key is", str(ctx.exception))
        finally:
            NodeKeyRotationManager._TEST_MODE = False

    async def test_resolve_latest_kel_anchor_missing_second_factor_returns_none(self):
        """_resolve_latest_kel_anchor must bail out cleanly (not raise) when
        K0 is available but SECOND_FACTOR cannot be resolved at all."""
        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())
        mgr = self._make_mgr(cfg)
        mgr._second_factor = ""

        with patch("yadacoin.core.keyrotation._read_second_factor", return_value=""):
            kn, depth = await mgr._resolve_latest_kel_anchor()

        self.assertIsNone(kn)
        self.assertEqual(depth, 0)

    async def test_resolve_latest_kel_anchor_build_error_falls_back_to_k0(self):
        """A KeyEventLog.get_latest error must be swallowed and
        treated as "no KEL yet" (depth 0) rather than propagating."""
        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())
        mgr = self._make_mgr(cfg)

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(side_effect=RuntimeError("mongo down")),
        ):
            kn, depth = await mgr._resolve_latest_kel_anchor()

        self.assertIsNotNone(kn)
        self.assertEqual(depth, 0)
        # depth 0 → 0 derivation steps applied → kn is just K0 itself.
        self.assertEqual(kn["private_key"], mgr._k0["private_key"])

    async def test_key_event_log_write_errors_are_swallowed(self):
        """DB errors while persisting the bridge entry and the subsequent
        advance must not raise — the in-memory branch state stays usable
        for the rest of this process even if persistence fails."""
        cfg = _make_branch_config(self.PRIV_HEX, self.PUB_HEX, self._cc_hex())
        mgr = self._make_mgr(cfg)
        cfg.mongo.async_db.key_event_log.replace_one = AsyncMock(
            side_effect=RuntimeError("write failed")
        )

        with self._patch_kel_depth(mgr), patch(
            "yadacoin.core.transaction.Config", return_value=cfg
        ):
            result = await mgr.advance_peer_auth_ratchet("peerA_username_signature")

        cur_priv, cur_pub, next_priv, next_pub, two_ahead_pkh, is_new_branch = result
        self.assertTrue(cur_priv)
        self.assertTrue(next_priv)
        self.assertTrue(is_new_branch)


# ---------------------------------------------------------------------------
# _walk_forward
# ---------------------------------------------------------------------------


class TestWalkForwardFromLatest(AsyncTestCase):
    """Tests for the secondary walk performed by get_latest after the
    _latest_from_inception_tag fast-path, to catch any untagged successors."""

    @patch("yadacoin.core.keyeventlog.Config")
    async def test_no_untagged_returns_original_latest(self, mock_cfg_cls):
        from yadacoin.core.keyeventlog import KeyEventLog

        cfg = MagicMock()
        mock_cfg_cls.return_value = cfg
        cfg.mongo.async_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[]
        )
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)

        latest = MagicMock()
        latest.inception_public_key_hash = "0xabc"
        latest.counter = 2
        latest.prerotated_key_hash = "1addr"

        result = await KeyEventLog._walk_forward(latest, "02pub", onchain_only=True)
        self.assertIs(result, latest)

    @patch("yadacoin.core.keyeventlog.Config")
    async def test_finds_and_tags_onchain_untagged_successor(self, mock_cfg_cls):
        from yadacoin.core.keyeventlog import KeyEventLog

        cfg = MagicMock()
        mock_cfg_cls.return_value = cfg

        candidate = MagicMock()
        candidate.inception_public_key_hash = None
        candidate.counter = None
        candidate.prerotated_key_hash = "1succ_next"
        candidate.public_key_hash = "1succ_addr"
        candidate.transaction_signature = "succ_sig"
        candidate.mempool = False

        cfg.mongo.async_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[
                {
                    "transactions": {
                        "public_key_hash": "1succ_addr",
                        "prerotated_key_hash": "1succ_next",
                        "transaction_signature": "succ_sig",
                    }
                }
            ]
        )
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)
        tag_mock = AsyncMock()
        cfg.mongo.async_db.key_event_log = MagicMock()
        cfg.mongo.async_db.key_event_log.replace_one = tag_mock

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog._tag_kel_entry_in_mongo",
            new=AsyncMock(),
        ), patch(
            "yadacoin.core.transaction.Transaction.from_dict",
            return_value=candidate,
        ):
            latest = MagicMock()
            latest.inception_public_key_hash = "0xabc"
            latest.counter = 2
            latest.prerotated_key_hash = "1succ_addr"

            result = await KeyEventLog._walk_forward(latest, "02pub", onchain_only=True)

        self.assertEqual(result.counter, 3)
        self.assertEqual(result.inception_public_key_hash, "0xabc")
        self.assertIs(result, candidate)

    @patch("yadacoin.core.keyeventlog.Config")
    async def test_finds_and_tags_mempool_untagged_successor(self, mock_cfg_cls):
        from yadacoin.core.keyeventlog import KeyEventLog

        cfg = MagicMock()
        mock_cfg_cls.return_value = cfg
        cfg.mongo.async_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[]
        )

        candidate = MagicMock()
        candidate.inception_public_key_hash = None
        candidate.counter = None
        candidate.prerotated_key_hash = "1mem_next"
        candidate.public_key_hash = "1mem_addr"
        candidate.transaction_signature = "mem_sig"
        candidate.mempool = False

        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value={
                "public_key_hash": "1mem_addr",
                "prerotated_key_hash": "1mem_next",
                "transaction_signature": "mem_sig",
            }
        )
        tag_mock = AsyncMock()
        cfg.mongo.async_db.key_event_log = MagicMock()
        cfg.mongo.async_db.key_event_log.replace_one = tag_mock

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog._tag_kel_entry_in_mongo",
            new=AsyncMock(),
        ), patch(
            "yadacoin.core.transaction.Transaction.from_dict",
            return_value=candidate,
        ):
            latest = MagicMock()
            latest.inception_public_key_hash = "0xabc"
            latest.counter = 2
            latest.prerotated_key_hash = "1mem_addr"

            result = await KeyEventLog._walk_forward(
                latest, "02pub", onchain_only=False
            )

        self.assertEqual(result.counter, 3)
        self.assertEqual(result.inception_public_key_hash, "0xabc")
        self.assertTrue(getattr(result, "mempool", False))

    @patch("yadacoin.core.keyeventlog.Config")
    async def test_onchain_only_skips_mempool(self, mock_cfg_cls):
        from yadacoin.core.keyeventlog import KeyEventLog

        cfg = MagicMock()
        mock_cfg_cls.return_value = cfg
        cfg.mongo.async_db.blocks.aggregate.return_value.to_list = AsyncMock(
            return_value=[]
        )
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value={"transaction_signature": "mem_sig"}
        )

        latest = MagicMock()
        latest.inception_public_key_hash = "0xabc"
        latest.counter = 2
        latest.prerotated_key_hash = "1addr"

        result = await KeyEventLog._walk_forward(latest, "02pub", onchain_only=True)
        self.assertIs(result, latest)
        cfg.mongo.async_db.miner_transactions.find_one.assert_not_awaited()
