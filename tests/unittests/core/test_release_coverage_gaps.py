"""Coverage gaps for release: KEL spend, SP selection, identity lookup, etc."""

import base64
import hashlib
import unittest
from collections import OrderedDict
from logging import getLogger
from unittest.mock import AsyncMock, MagicMock, patch

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey as CcPrivateKey

from yadacoin.core.config import Config
from yadacoin.core.keyrotation import derive_secure_path
from yadacoin.core.transactionutils import TU
from yadacoin.enums.peertypes import PEER_TYPES

from ..test_setup import AsyncTestCase

_PRIV = bytes.fromhex(
    "511d55726e3e3bf1c10b2a7202136eeaa1a17746c91a82305d6da89c8257f694"
)
_FACTOR = "release-cov-factor"


def _addr(key_dict):
    return str(
        P2PKHBitcoinAddress.from_pubkey(
            CcPrivateKey(key_dict["private_key"]).public_key.format(compressed=True)
        )
    )


def _pub(key_dict):
    return (
        CcPrivateKey(key_dict["private_key"]).public_key.format(compressed=True).hex()
    )


def _kel_chain(k0=None, factor=_FACTOR, depth=0):
    cur = k0 or {"private_key": _PRIV, "chain_code": _PRIV}
    chain = [cur]
    for _ in range(depth + 4):
        cur = derive_secure_path(cur["private_key"], cur["chain_code"], factor)
        chain.append(cur)
    return chain


class TestNodeHasActiveKel(unittest.TestCase):
    def test_false_without_manager(self):
        cfg = MagicMock(kel_manager=None)
        self.assertFalse(TU._node_has_active_kel(cfg))

    def test_true_when_k0_present(self):
        mgr = MagicMock()
        mgr._k0 = {"private_key": _PRIV}
        cfg = MagicMock(kel_manager=mgr)
        self.assertTrue(TU._node_has_active_kel(cfg))

    def test_true_when_anchor_triplet_set(self):
        mgr = MagicMock()
        mgr._k0 = None
        cfg = MagicMock()
        cfg.kel_manager = mgr
        cfg.kel_anchor_private_key = "aa"
        cfg.kel_anchor_public_key = "bb"
        cfg.kel_anchor_chain_code = "cc"
        self.assertTrue(TU._node_has_active_kel(cfg))


class TestResolveKelSpendTip(AsyncTestCase):
    async def test_no_tip_returns_nones(self):
        cfg = MagicMock()
        cfg.inception = None
        cfg.kel_anchor_public_key = None
        cfg.public_key = None
        mgr = MagicMock()
        mgr._k0 = None
        mgr._second_factor = ""
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=None),
        ), patch("yadacoin.core.keyrotation._read_second_factor", return_value=""):
            latest, tip_key, tip_pub = await TU._resolve_kel_spend_tip(cfg, mgr)
        self.assertIsNone(latest)
        self.assertIsNone(tip_key)
        self.assertIsNone(tip_pub)

    async def test_derives_tip_from_k0_walk(self):
        chain = _kel_chain(depth=1)
        tip_key = chain[1]
        tip = MagicMock()
        tip.public_key_hash = _addr(tip_key)
        tip.public_key = _pub(tip_key)

        cfg = MagicMock()
        cfg.inception = None
        cfg.kel_anchor_public_key = None
        cfg.public_key = None
        cfg.kel_anchor_private_key = None
        mgr = MagicMock()
        mgr._k0 = chain[0]
        mgr._second_factor = _FACTOR

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=tip),
        ):
            latest, resolved, tip_pub = await TU._resolve_kel_spend_tip(cfg, mgr)
        self.assertIs(latest, tip)
        self.assertEqual(resolved["private_key"], tip_key["private_key"])
        self.assertEqual(tip_pub, _pub(tip_key))

    async def test_falls_back_to_kel_anchor(self):
        chain = _kel_chain(depth=0)
        tip = MagicMock()
        tip.public_key_hash = _addr(chain[0])
        tip.public_key = _pub(chain[0])

        cfg = MagicMock()
        cfg.inception = None
        cfg.public_key = _pub(chain[0])
        cfg.kel_anchor_public_key = _pub(chain[0])
        cfg.kel_anchor_private_key = chain[0]["private_key"].hex()
        cfg.kel_anchor_chain_code = chain[0]["chain_code"].hex()
        cfg.kel_anchor_address = _addr(chain[0])
        mgr = MagicMock()
        mgr._k0 = None
        mgr._second_factor = ""

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=tip),
        ), patch("yadacoin.core.keyrotation._read_second_factor", return_value=""):
            latest, resolved, tip_pub = await TU._resolve_kel_spend_tip(cfg, mgr)
        self.assertIs(latest, tip)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["private_key"], chain[0]["private_key"])

    async def test_get_latest_exception_continues(self):
        tip = MagicMock()
        tip.public_key_hash = "1Addr"
        tip.public_key = "02ab"
        cfg = MagicMock()
        cfg.inception = tip
        cfg.kel_anchor_public_key = None
        cfg.public_key = "02ab"
        cfg.kel_anchor_private_key = None
        mgr = MagicMock()
        mgr._k0 = None
        mgr._second_factor = ""

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(side_effect=Exception("db")),
        ), patch("yadacoin.core.keyrotation._read_second_factor", return_value=""):
            latest, tip_key, tip_pub = await TU._resolve_kel_spend_tip(cfg, mgr)
        self.assertIs(latest, tip)
        self.assertIsNone(tip_key)

    async def test_inception_used_when_no_lookup_tip(self):
        inception = MagicMock()
        inception.public_key_hash = "1Inc"
        inception.public_key = "02inc"
        cfg = MagicMock()
        cfg.inception = inception
        cfg.kel_anchor_public_key = None
        cfg.public_key = None
        cfg.kel_anchor_private_key = None
        mgr = MagicMock()
        mgr._k0 = None
        mgr._second_factor = ""
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=None),
        ), patch("yadacoin.core.keyrotation._read_second_factor", return_value=""):
            latest, tip_key, tip_pub = await TU._resolve_kel_spend_tip(cfg, mgr)
        self.assertIs(latest, inception)
        self.assertIsNone(tip_key)


class TestBroadcastMempool(AsyncTestCase):
    async def test_broadcast_with_peers_and_protocol_v2(self):
        cfg = MagicMock()
        cfg.mongo.async_db.miner_transactions.insert_one = AsyncMock()
        cfg.nodeShared.write_params = AsyncMock()
        cfg.nodeClient.retry_messages = {}

        peer_stream = MagicMock()
        peer_stream.peer.protocol_version = 2
        peer_stream.peer.rid = "rid1"

        async def peers():
            yield peer_stream

        cfg.peer.get_sync_peers = peers
        txn = MagicMock()
        txn.to_dict.return_value = {"id": "t1"}
        txn.transaction_signature = "sig1"
        await TU._broadcast_mempool(cfg, txn)
        cfg.mongo.async_db.miner_transactions.insert_one.assert_awaited_once()
        cfg.nodeShared.write_params.assert_awaited_once()
        self.assertIn(("rid1", "newtxn", "sig1"), cfg.nodeClient.retry_messages)

    async def test_broadcast_no_peer_attr_returns(self):
        cfg = MagicMock(spec=["mongo"])
        cfg.mongo.async_db.miner_transactions.insert_one = AsyncMock()
        txn = MagicMock()
        txn.to_dict.return_value = {"id": "t1"}
        await TU._broadcast_mempool(cfg, txn)


class TestTUSendKelPaths(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        if not hasattr(self.config, "app_log"):
            self.config.app_log = getLogger("tornado.application")

    async def test_send_routes_to_kel_and_handles_errors(self):
        from yadacoin.core.transaction import (
            NotEnoughMoneyException,
            TooManyInputsException,
        )

        mgr = MagicMock()
        mgr._k0 = {"private_key": _PRIV}
        self.config.kel_manager = mgr

        with patch.object(
            TU,
            "_send_with_kel",
            new=AsyncMock(side_effect=NotEnoughMoneyException("x")),
        ):
            r = await TU.send(self.config, to="a", value=1.0)
        self.assertEqual(r["status"], "error")
        self.assertIn("not enough money", r["message"])

        with patch.object(
            TU,
            "_send_with_kel",
            new=AsyncMock(side_effect=TooManyInputsException("too many")),
        ):
            r = await TU.send(self.config, to="a", value=1.0)
        self.assertEqual(r["status"], "error")
        self.assertIn("too many", r["message"])

        with patch.object(
            TU, "_send_with_kel", new=AsyncMock(side_effect=RuntimeError("boom"))
        ):
            r = await TU.send(self.config, to="a", value=1.0)
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["error"], "invalid transaction")

        with patch.object(
            TU, "_send_with_kel", new=AsyncMock(side_effect=RuntimeError("boom"))
        ):
            broken_log = MagicMock()
            broken_log.exception.side_effect = Exception("log fail")
            self.config.app_log = broken_log
            r = await TU.send(self.config, to="a", value=1.0)
        self.assertEqual(r["status"], "error")

    async def test_send_legacy_child_key_and_missing_keys(self):
        self.config.kel_manager = None
        self.config.kel_anchor_private_key = None
        self.config.kel_anchor_public_key = None
        self.config.kel_anchor_chain_code = None

        mock_db = MagicMock()
        mock_db.child_keys.find_one = AsyncMock(side_effect=Exception("db down"))
        with patch.object(self.config.mongo, "async_db", new=mock_db):
            # still has public/private on config
            with patch(
                "yadacoin.core.transaction.Transaction.generate",
                new=AsyncMock(side_effect=Exception("gen")),
            ):
                with self.assertRaises(Exception):
                    await TU.send(
                        self.config,
                        to="a",
                        value=1.0,
                        from_address="other_addr",
                    )

        saved_pub, saved_priv = self.config.public_key, self.config.private_key
        try:
            self.config.public_key = ""
            self.config.private_key = ""
            r = await TU.send(self.config, to="a", value=1.0)
            self.assertIn("node signing keys", r["message"])
        finally:
            self.config.public_key = saved_pub
            self.config.private_key = saved_priv

    async def test_send_verify_exception_paths(self):
        from yadacoin.core.transaction import TooManyInputsException, Transaction

        self.config.kel_manager = None
        self.config.kel_anchor_private_key = None
        self.config.kel_anchor_public_key = None
        self.config.kel_anchor_chain_code = None

        mock_txn = MagicMock()
        mock_txn.to_dict.return_value = {"id": "x"}
        mock_txn.verify = AsyncMock(side_effect=TooManyInputsException("many"))
        mock_lb = MagicMock()
        mock_lb.block.index = 10**9

        with patch.object(
            Transaction, "generate", new=AsyncMock(return_value=mock_txn)
        ), patch.object(self.config, "LatestBlock", mock_lb, create=True):
            r = await TU.send(
                self.config, to="a", value=1.0, from_address=self.config.address
            )
        self.assertEqual(r["status"], "error")

        mock_txn.verify = AsyncMock(side_effect=ValueError("bad"))
        broken = MagicMock()
        broken.exception.side_effect = Exception("x")
        self.config.app_log = broken
        with patch.object(
            Transaction, "generate", new=AsyncMock(return_value=mock_txn)
        ), patch.object(self.config, "LatestBlock", mock_lb, create=True):
            r = await TU.send(
                self.config, to="a", value=1.0, from_address=self.config.address
            )
        self.assertEqual(r["error"], "invalid transaction")

    async def test_send_with_kel_happy_path_dry_run(self):
        chain = _kel_chain(depth=0)
        kn, kn1, kn2, kn3, kn4 = chain[0], chain[1], chain[2], chain[3], chain[4]
        tip = MagicMock()
        tip.public_key_hash = _addr(kn)
        tip.prerotated_key_hash = _addr(kn1)
        tip.twice_prerotated_key_hash = _addr(kn2)
        tip.counter = 0
        tip.inception_public_key_hash = _addr(kn)
        tip.public_key = _pub(kn)

        mgr = MagicMock()
        mgr._k0 = kn
        mgr._second_factor = _FACTOR
        self.config.kel_manager = mgr

        parent = MagicMock()
        out = MagicMock()
        out.value = 10.0
        out.to = _addr(kn)
        parent.outputs = [out]

        mock_lb = MagicMock()
        mock_lb.block.index = 0

        utxo = {"id": "utxo1", "transaction_signature": "utxo1"}

        with patch.object(
            TU,
            "_resolve_kel_spend_tip",
            new=AsyncMock(return_value=(tip, kn, _pub(kn))),
        ), patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_kel_addresses",
            new=AsyncMock(return_value=frozenset({_addr(kn)})),
        ), patch.object(
            self.config,
            "BU",
            MagicMock(
                get_unspent_outputs=AsyncMock(return_value={"unspent_utxos": [utxo]}),
                get_transaction_by_id=AsyncMock(return_value=parent),
            ),
            create=True,
        ), patch(
            "yadacoin.core.keyeventlog.verify_kel_step"
        ), patch(
            "yadacoin.core.transaction.Transaction.verify",
            new=AsyncMock(),
        ), patch.object(
            self.config, "LatestBlock", mock_lb, create=True
        ):
            result = await TU._send_with_kel(
                self.config, to="1DestAddrXXXX", value=1.0, dry_run=True
            )
        self.assertEqual(result["status"], "ok")
        self.assertIn("confirming", result)

    async def test_send_with_kel_error_branches(self):
        mgr = MagicMock()
        mgr._k0 = {"private_key": _PRIV, "chain_code": _PRIV}
        mgr._second_factor = ""
        self.config.kel_manager = mgr

        with patch("yadacoin.core.keyrotation._read_second_factor", return_value=""):
            with self.assertRaises(RuntimeError):
                await TU._send_with_kel(self.config, to="a", value=1.0)

        mgr._second_factor = _FACTOR
        with patch.object(
            TU, "_resolve_kel_spend_tip", new=AsyncMock(return_value=(None, None, None))
        ):
            with self.assertRaises(RuntimeError):
                await TU._send_with_kel(self.config, to="a", value=1.0)

        tip = MagicMock()
        tip.public_key_hash = "1x"
        tip.prerotated_key_hash = "1y"
        tip.twice_prerotated_key_hash = "1z"
        with patch.object(
            TU,
            "_resolve_kel_spend_tip",
            new=AsyncMock(return_value=(tip, None, None)),
        ):
            with self.assertRaises(RuntimeError):
                await TU._send_with_kel(self.config, to="a", value=1.0)

        bad_key = {"private_key": _PRIV, "chain_code": _PRIV}
        tip.public_key_hash = "1NotMatching"
        tip.prerotated_key_hash = "1y"
        tip.twice_prerotated_key_hash = "1z"
        with patch.object(
            TU,
            "_resolve_kel_spend_tip",
            new=AsyncMock(return_value=(tip, bad_key, _pub(bad_key))),
        ):
            with self.assertRaises(RuntimeError):
                await TU._send_with_kel(self.config, to="a", value=1.0)

        chain = _kel_chain(depth=0)
        kn, kn1, kn2 = chain[0], chain[1], chain[2]
        tip.public_key_hash = _addr(kn)
        tip.prerotated_key_hash = "1WrongPre"
        tip.twice_prerotated_key_hash = _addr(kn2)
        tip.counter = 0
        tip.inception_public_key_hash = _addr(kn)
        with patch.object(
            TU,
            "_resolve_kel_spend_tip",
            new=AsyncMock(return_value=(tip, kn, _pub(kn))),
        ):
            with self.assertRaises(RuntimeError):
                await TU._send_with_kel(self.config, to="a", value=1.0)

        tip.prerotated_key_hash = _addr(kn1)
        tip.twice_prerotated_key_hash = "1WrongTwice"
        with patch.object(
            TU,
            "_resolve_kel_spend_tip",
            new=AsyncMock(return_value=(tip, kn, _pub(kn))),
        ):
            with self.assertRaises(RuntimeError):
                await TU._send_with_kel(self.config, to="a", value=1.0)

        tip.twice_prerotated_key_hash = _addr(kn2)
        tip.public_key_hash = ""
        with patch.object(
            TU,
            "_resolve_kel_spend_tip",
            new=AsyncMock(return_value=(tip, kn, _pub(kn))),
        ):
            with self.assertRaises(RuntimeError):
                await TU._send_with_kel(self.config, to="a", value=1.0)

        with self.assertRaises(ValueError):
            await TU._send_with_kel(
                self.config, to="a", value=0, outputs=[{"to": "a", "value": 0}]
            )

        tip.public_key_hash = _addr(kn)
        tip.prerotated_key_hash = _addr(kn1)
        tip.twice_prerotated_key_hash = _addr(kn2)
        from yadacoin.core.transaction import NotEnoughMoneyException

        with patch.object(
            TU,
            "_resolve_kel_spend_tip",
            new=AsyncMock(return_value=(tip, kn, _pub(kn))),
        ), patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_kel_addresses",
            new=AsyncMock(return_value=frozenset()),
        ), patch.object(
            self.config,
            "BU",
            MagicMock(
                get_unspent_outputs=AsyncMock(return_value={"unspent_utxos": []}),
            ),
            create=True,
        ):
            with self.assertRaises(NotEnoughMoneyException):
                await TU._send_with_kel(self.config, to="a", value=1.0)

    async def test_send_with_kel_broadcast_and_input_filters(self):
        from yadacoin.core.transaction import NotEnoughMoneyException

        chain = _kel_chain(depth=0)
        kn, kn1, kn2 = chain[0], chain[1], chain[2]
        tip = MagicMock()
        tip.public_key_hash = _addr(kn)
        tip.prerotated_key_hash = _addr(kn1)
        tip.twice_prerotated_key_hash = _addr(kn2)
        tip.counter = 0
        tip.inception_public_key_hash = _addr(kn)
        tip.public_key = _pub(kn)

        mgr = MagicMock()
        mgr._k0 = kn
        mgr._second_factor = _FACTOR
        self.config.kel_manager = mgr
        mock_lb = MagicMock()
        mock_lb.block.index = 0

        parent = MagicMock()
        out = MagicMock()
        out.value = 10.0
        out.to = _addr(kn)
        parent.outputs = [out]

        utxo = {"id": "ok", "transaction_signature": "ok"}
        with patch.object(
            TU,
            "_resolve_kel_spend_tip",
            new=AsyncMock(return_value=(tip, kn, _pub(kn))),
        ), patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_kel_addresses",
            new=AsyncMock(return_value=frozenset({_addr(kn)})),
        ), patch.object(
            self.config,
            "BU",
            MagicMock(
                get_unspent_outputs=AsyncMock(
                    return_value={"unspent_utxos": [{}, {"id": "missing"}, utxo]}
                ),
                get_transaction_by_id=AsyncMock(side_effect=[None, parent]),
            ),
            create=True,
        ), patch(
            "yadacoin.core.keyeventlog.verify_kel_step",
        ), patch(
            "yadacoin.core.transaction.Transaction.verify",
            new=AsyncMock(),
        ), patch.object(
            TU, "_broadcast_mempool", new=AsyncMock()
        ) as mock_bc, patch.object(
            self.config, "LatestBlock", mock_lb, create=True
        ):
            result = await TU._send_with_kel(
                self.config, to="1Dest", value=1.0, dry_run=False
            )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(mock_bc.await_count, 2)
        self.assertEqual(self.config.kel_anchor_public_key, _pub(kn2))

        with patch.object(
            TU,
            "_resolve_kel_spend_tip",
            new=AsyncMock(return_value=(tip, kn, _pub(kn))),
        ), patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_kel_addresses",
            new=AsyncMock(return_value=frozenset({_addr(kn)})),
        ), patch.object(
            self.config,
            "BU",
            MagicMock(
                get_unspent_outputs=AsyncMock(
                    return_value={"unspent_utxos": [{"id": "small"}]}
                ),
                get_transaction_by_id=AsyncMock(
                    return_value=MagicMock(
                        outputs=[MagicMock(value=0.01, to=_addr(kn))]
                    )
                ),
            ),
            create=True,
        ):
            with self.assertRaises(NotEnoughMoneyException):
                await TU._send_with_kel(self.config, to="a", value=100.0)

        # explicit inputs= override; skip zero-value / non-KEL outs; too many inputs
        from yadacoin.core.transaction import TooManyInputsException

        zero_out = MagicMock(value=0.0, to=_addr(kn))
        foreign = MagicMock(value=5.0, to="1Foreign")
        good = MagicMock(value=2.0, to=_addr(kn))
        parents = {
            "skip0": MagicMock(outputs=[zero_out, foreign]),
            "ok0": MagicMock(outputs=[good]),
            "ok1": MagicMock(outputs=[good]),
            "ok2": MagicMock(outputs=[good]),
        }

        async def by_id(uid, instance=True):
            return parents.get(uid)

        with patch.object(
            TU,
            "_resolve_kel_spend_tip",
            new=AsyncMock(return_value=(tip, kn, _pub(kn))),
        ), patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_kel_addresses",
            new=AsyncMock(return_value=frozenset({_addr(kn)})),
        ), patch.object(
            self.config,
            "BU",
            MagicMock(
                get_unspent_outputs=AsyncMock(return_value={"unspent_utxos": []}),
                get_transaction_by_id=AsyncMock(side_effect=by_id),
            ),
            create=True,
        ), patch(
            "yadacoin.core.keyeventlog.verify_kel_step",
        ), patch(
            "yadacoin.core.transaction.Transaction.verify",
            new=AsyncMock(),
        ), patch(
            "yadacoin.core.chain.CHAIN.MAX_INPUTS", 2
        ), patch.object(
            self.config, "LatestBlock", mock_lb, create=True
        ):
            with self.assertRaises(TooManyInputsException):
                await TU._send_with_kel(
                    self.config,
                    to="1Dest",
                    value=5.0,
                    dry_run=True,
                    inputs=[
                        {"id": "skip0"},
                        {"id": "ok0"},
                        {"id": "ok1"},
                        {"id": "ok2"},
                    ],
                )

        # anchor update exception swallowed
        class _BoomCfg:
            def __init__(self, base):
                self._base = base
                self._boom = False

            def __getattr__(self, name):
                return getattr(self._base, name)

            def __setattr__(self, name, value):
                if name in ("_base", "_boom"):
                    object.__setattr__(self, name, value)
                    return
                if name.startswith("kel_anchor") and self._boom:
                    raise RuntimeError("readonly")
                setattr(self._base, name, value)

        boom_cfg = _BoomCfg(self.config)
        boom_cfg.kel_manager = mgr
        boom_cfg._boom = True
        with patch.object(
            TU,
            "_resolve_kel_spend_tip",
            new=AsyncMock(return_value=(tip, kn, _pub(kn))),
        ), patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_kel_addresses",
            new=AsyncMock(return_value=frozenset({_addr(kn)})),
        ), patch.object(
            self.config,
            "BU",
            MagicMock(
                get_unspent_outputs=AsyncMock(return_value={"unspent_utxos": [utxo]}),
                get_transaction_by_id=AsyncMock(return_value=parent),
            ),
            create=True,
        ), patch(
            "yadacoin.core.keyeventlog.verify_kel_step",
        ), patch(
            "yadacoin.core.transaction.Transaction.verify",
            new=AsyncMock(),
        ), patch.object(
            TU, "_broadcast_mempool", new=AsyncMock()
        ), patch.object(
            self.config, "LatestBlock", mock_lb, create=True
        ):
            boom_cfg.BU = self.config.BU
            boom_cfg.LatestBlock = mock_lb
            result = await TU._send_with_kel(
                boom_cfg, to="1Dest", value=1.0, dry_run=False
            )
        self.assertEqual(result["status"], "ok")


class TestGetIdentityKel(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        if not hasattr(self.config, "app_log"):
            self.config.app_log = getLogger("tornado.application")

    async def test_inception_relationship_dict_and_object(self):
        inception = MagicMock()
        inception.relationship = {
            "username": "from_inc",
            "username_signature": "sig_inc",
        }
        inception.public_key = "02inc"
        inception.public_key_hash = "1IncAddr"
        self.config.inception = inception
        self.config.kel_manager = None
        ident = self.config.get_identity()
        self.assertEqual(ident["username"], "from_inc")
        self.assertEqual(ident["username_signature"], "sig_inc")
        self.assertEqual(ident["public_key"], "02inc")
        self.assertEqual(ident["address"], "1IncAddr")

        rel = MagicMock()
        rel.username = "obj_user"
        rel.username_signature = "obj_sig"
        rel.get = None
        inception.relationship = rel
        inception.public_key = None
        inception.public_key_hash = None
        self.config.username = "fallback"
        self.config.username_signature = "fb_sig"
        self.config.public_key = "02fb"
        self.config.address = "1Fb"
        ident = self.config.get_identity()
        self.assertEqual(ident["username"], "obj_user")
        self.assertEqual(ident["username_signature"], "obj_sig")

    async def test_k0_realigns_signature(self):
        k0 = {"private_key": _PRIV, "chain_code": _PRIV}
        mgr = MagicMock()
        mgr._k0 = k0
        self.config.kel_manager = mgr
        self.config.inception = None
        self.config.username = "alice"
        self.config.username_signature = "invalid"
        ident = self.config.get_identity()
        self.assertEqual(ident["public_key"], _pub(k0))
        self.assertEqual(ident["address"], _addr(k0))
        self.assertTrue(ident["username_signature"])
        # valid signature keeps usig
        good = base64.b64encode(CcPrivateKey(_PRIV).sign(b"alice")).decode("utf-8")
        self.config.username_signature = good
        ident2 = self.config.get_identity()
        self.assertEqual(ident2["username_signature"], good)
        # bad k0 material is ignored
        mgr._k0 = {"private_key": b"\x00"}
        self.config.username_signature = "x"
        self.config.public_key = "02keep"
        ident3 = self.config.get_identity()
        self.assertEqual(ident3["public_key"], "02keep")


class TestIdentityByUsernameSignature(AsyncTestCase):
    async def test_blockchain_mempool_and_none(self):
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        cfg = MagicMock()
        chain_doc = {
            "public_key": "02a",
            "relationship": {"identity": {"username": "u"}},
        }

        async def _agg(_):
            yield chain_doc

        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=_agg(None))
        result = await IdentityAnnouncement.get_by_username_signature(
            "MEUC sig", config=cfg
        )
        self.assertEqual(result["source"], "blockchain")

        async def _empty(_):
            return
            yield

        cfg.mongo.async_db.blocks.aggregate = MagicMock(return_value=_empty(None))
        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(
            return_value={
                "public_key": "02b",
                "relationship": {"identity": {"username": "u2"}},
            }
        )
        result = await IdentityAnnouncement.get_by_username_signature("sig", config=cfg)
        self.assertEqual(result["source"], "mempool")

        cfg.mongo.async_db.miner_transactions.find_one = AsyncMock(return_value=None)
        result = await IdentityAnnouncement.get_by_username_signature(
            "sig", include_mempool=False, config=cfg
        )
        self.assertIsNone(result)
        result = await IdentityAnnouncement.get_by_username_signature("sig", config=cfg)
        self.assertIsNone(result)

        with patch("yadacoin.core.config.Config", return_value=cfg):
            result = await IdentityAnnouncement.get_by_username_signature("sig")
        self.assertIsNone(result)


class TestPeerServiceProviderSelection(AsyncTestCase):
    async def test_service_providers_map_filters_pools(self):
        from yadacoin.core.peer import Peer

        sp = MagicMock()
        sp.host = "sp.example.com"
        sp.peer_type = PEER_TYPES.SERVICE_PROVIDER.value
        pool = MagicMock()
        pool.host = "pool.yadacoin.io"
        pool.peer_type = PEER_TYPES.POOL.value
        pool2 = MagicMock()
        pool2.host = "x.pool"
        pool2.peer_type = "user"
        pool3 = MagicMock()
        pool3.host = "host/pool"
        pool3.peer_type = ""
        # "pool.yadacoin" substring without pool. prefix / .pool suffix / /pool
        pool4 = MagicMock()
        pool4.host = "mypool.yadacoin.example"
        pool4.peer_type = "user"

        cfg = MagicMock()
        cfg.service_providers = OrderedDict(
            [("a", sp), ("b", pool), ("c", pool2), ("d", pool3), ("e", pool4)]
        )
        # successful warning path then continue (line 388)
        cfg.app_log.warning = MagicMock()
        with patch("yadacoin.core.peer.Config", return_value=cfg):
            cleaned = Peer._service_providers_map()
        self.assertEqual(list(cleaned.keys()), ["a"])
        self.assertTrue(cfg.app_log.warning.called)

        cfg.service_providers = OrderedDict([("a", sp), ("b", pool)])
        cfg.app_log.warning.side_effect = Exception("log fail")
        with patch("yadacoin.core.peer.Config", return_value=cfg):
            cleaned = Peer._service_providers_map()
        self.assertEqual(list(cleaned.keys()), ["a"])

        cfg.service_providers = None
        with patch("yadacoin.core.peer.Config", return_value=cfg), patch(
            "yadacoin.core.peer.Peers.get_config_service_providers",
            return_value=None,
        ), patch("yadacoin.core.peer.Peers.get_service_providers", return_value=None):
            self.assertIsNone(Peer._service_providers_map())

    async def test_select_service_provider_paths(self):
        from yadacoin.core.peer import Peer, ServiceProvider

        cfg = MagicMock()
        sp0 = MagicMock()
        sp0.identity = MagicMock(username_signature="sig0")
        sp1 = MagicMock()
        sp1.identity = None
        sp1.identity_announcement = "ann1"
        providers = OrderedDict([("k0", sp0), ("k1", sp1)])

        self.assertIsNone(Peer.select_service_provider(""))
        with patch.object(Peer, "_service_providers_map", return_value=None):
            self.assertIsNone(Peer.select_service_provider("usig"))

        with patch.object(
            Peer, "_service_providers_map", return_value=providers
        ), patch("yadacoin.core.peer.Config", return_value=cfg), patch(
            "yadacoin.core.peer.time"
        ) as mock_time:
            mock_time.time.return_value = Peer.epoch + Peer.ttl * 2
            chosen = Peer.select_service_provider("usig", rotate=True)
            self.assertIn(chosen, providers.values())
            fixed = Peer.select_service_provider("usig", rotate=False)
            h = hashlib.sha256(b"usig").hexdigest()
            idx = (int(h, 16) * 1) % 2
            self.assertIs(fixed, list(providers.values())[idx])

        cfg.nodeClient.outbound_ignore = {
            ServiceProvider.__name__: {"sig0": True, "ann1": True}
        }
        with patch.object(
            Peer, "_service_providers_map", return_value=providers
        ), patch("yadacoin.core.peer.Config", return_value=cfg), patch(
            "yadacoin.core.peer.is_outbound_ignored", return_value=True
        ):
            self.assertIsNone(Peer.select_service_provider("usig", skip_ignored=True))

        cfg.nodeClient = MagicMock()
        type(cfg.nodeClient).outbound_ignore = property(
            lambda self: (_ for _ in ()).throw(Exception("x"))
        )
        with patch.object(
            Peer, "_service_providers_map", return_value=providers
        ), patch("yadacoin.core.peer.Config", return_value=cfg):
            chosen = Peer.select_service_provider("usig", skip_ignored=True)
            self.assertIn(chosen, providers.values())

    async def test_calculate_service_provider(self):
        from yadacoin.core.peer import Peer

        p = Peer()
        p.identity = None
        self.assertIsNone(await p.calculate_service_provider())
        p.identity = MagicMock(username_signature="sig")
        with patch.object(
            Peer, "select_service_provider", return_value="SP"
        ) as mock_sel:
            self.assertEqual(await p.calculate_service_provider(), "SP")
            mock_sel.assert_called_once_with("sig", rotate=True, skip_ignored=True)


class TestWalletBalanceKelGaps(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        from yadacoin.core.blockchainutils import BlockChainUtils

        self.config = Config()
        if not hasattr(self.config, "app_log"):
            self.config.app_log = MagicMock()
        self.bu = BlockChainUtils()

    async def test_get_wallet_balance_exception_and_empty(self):
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_kel_addresses",
            new=AsyncMock(side_effect=Exception("x")),
        ):
            self.bu.get_final_balance = AsyncMock(return_value=3.0)
            self.assertEqual(await self.bu.get_wallet_balance("addr"), 3.0)

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_kel_addresses",
            new=AsyncMock(return_value=frozenset()),
        ):
            self.bu.get_final_balance = AsyncMock(return_value=1.5)
            self.assertEqual(await self.bu.get_wallet_balance("addr"), 1.5)

    async def test_get_unspent_outputs_kel_aggregate(self):
        from yadacoin.core.blockchainutils import BlockChainUtils

        real = BlockChainUtils.get_unspent_outputs

        # exception expanding KEL → single-address path
        self.bu.get_reverse_public_key = AsyncMock(return_value="02pk")
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "h", "index": 1}
        )
        self.bu.get_wallet_balance = AsyncMock(return_value=0.0)
        self.bu.get_final_balance = AsyncMock(return_value=0.0)
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=None)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=False)
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=0.0)
        self.bu._select_spendable_utxos = AsyncMock(return_value=([], 0.0))
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        self.bu.floor_to_two_decimal_places = lambda v: float(v)
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_kel_addresses",
            new=AsyncMock(side_effect=Exception("x")),
        ):
            await real(self.bu, "addr", amount_needed=0)

        calls = {"n": 0}

        async def side(self, address, **kwargs):
            if not kwargs.get("_kel_expanded"):
                return await real(self, address, **kwargs)
            calls["n"] += 1
            return {
                "unspent_utxos": [
                    {
                        "id": f"{address}-u",
                        "time": calls["n"],
                        "outputs": [{"value": 2.0}],
                    },
                    {
                        "id": "dup",
                        "time": 0,
                        "outputs": [{"value": 1.0}],
                    },
                ],
                "max_transferable_value": 3.0,
            }

        self.bu.get_wallet_balance = AsyncMock(return_value=9.0)
        self.bu._utxo_value = lambda u: float(
            (u.get("outputs") or [{"value": 0}])[0].get("value") or 0
        )
        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_kel_addresses",
            new=AsyncMock(return_value=frozenset({"a1", "a2"})),
        ), patch.object(BlockChainUtils, "get_unspent_outputs", side):
            result = await real(self.bu, "a1", amount_needed=2.5, max_utxos=10)
        self.assertGreaterEqual(len(result["unspent_utxos"]), 1)
        self.assertAlmostEqual(result["balance"], 9.0)

        with patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_kel_addresses",
            new=AsyncMock(return_value=frozenset({"a1", "a2"})),
        ), patch.object(BlockChainUtils, "get_unspent_outputs", side):
            result = await real(self.bu, "a1", amount_needed=0, max_utxos=10)
        self.assertEqual(result["unspent_utxos"], [])

        # _kel_expanded uses get_final_balance
        self.bu.get_final_balance = AsyncMock(return_value=4.0)
        self.bu.get_reverse_public_key = AsyncMock(return_value="02pk")
        self.bu.get_latest_block_async = AsyncMock(
            return_value={"hash": "h", "index": 1}
        )
        self.bu._get_wallet_unspent_cache = AsyncMock(return_value=None)
        self.bu._wallet_unspent_cache_is_valid = AsyncMock(return_value=False)
        self.bu._save_wallet_unspent_cache = AsyncMock(return_value=0.0)
        self.bu._select_spendable_utxos = AsyncMock(return_value=([], 0.0))
        self.bu.get_mempool_spent_inputs = AsyncMock(return_value=[])
        result = await real(self.bu, "addr", amount_needed=0, _kel_expanded=True)
        self.bu.get_final_balance.assert_awaited()


class TestKeyEventLogAddressHelpers(AsyncTestCase):
    async def test_addresses_from_log_and_get_kel_addresses(self):
        from yadacoin.core.keyeventlog import KeyEventLog

        log = [
            {
                "public_key_hash": "a1",
                "prerotated_key_hash": "a2",
                "twice_prerotated_key_hash": "",
                "prev_public_key_hash": "a3",
            },
            MagicMock(
                public_key_hash="b1",
                prerotated_key_hash=None,
                twice_prerotated_key_hash="b2",
                prev_public_key_hash="b3",
            ),
        ]
        addrs = KeyEventLog.addresses_from_log(log)
        self.assertIn("a1", addrs)
        self.assertIn("b2", addrs)
        self.assertEqual(KeyEventLog.addresses_from_log(None), frozenset())

        self.assertEqual(
            await KeyEventLog.get_kel_addresses(address=None, public_key=None),
            frozenset(),
        )
        with patch(
            "yadacoin.core.keyeventlog.P2PKHBitcoinAddress.from_pubkey",
            side_effect=Exception("bad"),
        ):
            self.assertEqual(
                await KeyEventLog.get_kel_addresses(public_key="zz"),
                frozenset(),
            )
        with patch(
            "yadacoin.core.keyeventlog.P2PKHBitcoinAddress.from_pubkey",
            return_value=type("A", (), {"__str__": lambda s: "1FromPub"})(),
        ), patch.object(
            KeyEventLog, "get_log", new=AsyncMock(side_effect=Exception("x"))
        ):
            self.assertEqual(
                await KeyEventLog.get_kel_addresses(public_key="aa" * 33),
                frozenset({"1FromPub"}),
            )
        with patch.object(KeyEventLog, "get_log", new=AsyncMock(return_value=[])):
            self.assertEqual(
                await KeyEventLog.get_kel_addresses(address="1Only"),
                frozenset({"1Only"}),
            )
        with patch.object(
            KeyEventLog,
            "get_log",
            new=AsyncMock(
                return_value=[{"public_key_hash": "x1", "prerotated_key_hash": "x2"}]
            ),
        ):
            got = await KeyEventLog.get_kel_addresses(address="x0")
            self.assertEqual(got, frozenset({"x0", "x1", "x2"}))

        self.assertEqual(await KeyEventLog.get_log(), [])
        inc = MagicMock()
        inc.inception_public_key_hash = None
        inc.public_key_hash = "1Inc"
        cfg = MagicMock()
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[])
        cfg.mongo.async_db.blocks.aggregate.return_value = cursor
        with patch.object(
            KeyEventLog, "get_inception", new=AsyncMock(return_value=inc)
        ), patch("yadacoin.core.keyeventlog.Config", return_value=cfg):
            result = await KeyEventLog.get_log(address="1x", onchain_only=True)
        self.assertEqual(result, [])


class TestKeyRotationCoverageExtras(AsyncTestCase):
    async def test_update_active_kel_key_and_sweep_edges(self):
        from yadacoin.core.chain import CHAIN
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = MagicMock()
        cfg.username = "node"
        cfg.app_log = MagicMock()
        cfg.address = "1LEGACY"
        cfg.peer_type = "node"
        mgr = NodeKeyRotationManager(cfg)
        self.assertIsNone(mgr._legacy_sweep_lock)

        k0 = {"private_key": _PRIV, "chain_code": _PRIV}
        mgr._update_active_kel_key(1, "1pkh", k0, _FACTOR)
        self.assertTrue(cfg.kel_anchor_private_key)
        self.assertEqual(mgr._auth_ratchet_prev_pkh, "1pkh")

        with patch.object(
            NodeKeyRotationManager,
            "generate_deterministic_signature",
            side_effect=Exception("sig"),
        ):
            mgr._update_active_kel_key(0, None, k0, _FACTOR)
        cfg.app_log.debug.assert_called()

        # lock already held
        import asyncio

        mgr._legacy_sweep_lock = asyncio.Lock()
        await mgr._legacy_sweep_lock.acquire()
        latest = MagicMock(prerotated_key_hash="1KEL")
        await mgr._check_and_sweep_legacy_funds(latest)
        mgr._legacy_sweep_lock.release()

        # total <= 0 at max inputs
        cfg.LatestBlock = MagicMock()
        cfg.LatestBlock.block.index = 1
        cfg.LatestBlock.block.hash = "h"

        async def zero_utxos(addr, **kwargs):
            for i in range(CHAIN.MAX_INPUTS):
                yield {"id": f"u{i}", "outputs": [{"to": "other", "value": 1.0}]}

        cfg.BU = MagicMock()
        cfg.BU.get_wallet_unspent_transactions_for_spending = zero_utxos
        with patch.object(mgr, "_sweep_legacy_to_kel", new=AsyncMock()) as sw:
            await mgr._check_and_sweep_legacy_funds(latest)
        sw.assert_not_awaited()

        # submitted False pops cache (fresh tip so cache is rebuilt)
        mgr._kel_balance_cache.clear()
        cfg.LatestBlock.block.index = 2
        cfg.LatestBlock.block.hash = "h2"

        async def full_utxos(addr, **kwargs):
            for i in range(CHAIN.MAX_INPUTS):
                yield {
                    "id": f"u{i}",
                    "outputs": [{"to": "1LEGACY", "value": 1.0}],
                }

        cfg.BU.get_wallet_unspent_transactions_for_spending = full_utxos
        with patch.object(
            mgr, "_sweep_legacy_to_kel", new=AsyncMock(return_value=False)
        ):
            await mgr._check_and_sweep_legacy_funds(latest)
        self.assertNotIn("1LEGACY", mgr._kel_balance_cache)

    async def test_startup_keeps_valid_username_signature(self):
        """Cover ok=True branch when inception usig verifies under K0."""
        from yadacoin.core.keyrotation import NodeKeyRotationManager

        cfg = MagicMock()
        cfg.seed = "able able able able able able able able able able able able"
        cfg.username = "mynode"
        cfg.modes = []
        cfg.app_log = MagicMock()
        cfg.mongo = MagicMock()
        cfg.private_key = _PRIV.hex()
        cfg.public_key = _pub({"private_key": _PRIV})
        cfg.address = _addr({"private_key": _PRIV})
        cfg.kel_anchor_private_key = None
        cfg.kel_anchor_public_key = None
        cfg.kel_anchor_address = None
        cfg.kel_anchor_chain_code = None
        cfg.config_path = None
        mgr = NodeKeyRotationManager(cfg)

        k0 = derive_secure_path(bytes(32), bytes(32), "mysecret")
        _pub(k0)
        uname = "mynode"
        usig = base64.b64encode(
            CcPrivateKey(k0["private_key"]).sign(uname.encode("utf-8"))
        ).decode("utf-8")

        inception = MagicMock()
        inception.relationship = MagicMock(username=uname, username_signature=usig)
        inception.public_key_hash = _addr(k0)
        inception.transaction_signature = "incsig"
        inception.counter = 0

        with patch.dict("os.environ", {"SECOND_FACTOR": "mysecret"}), patch(
            "bip32utils.BIP32Key"
        ) as bip, patch("mnemonic.Mnemonic") as mn_cls, patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_inception",
            new=AsyncMock(return_value=inception),
        ), patch(
            "yadacoin.core.keyeventlog.KeyEventLog.get_latest",
            new=AsyncMock(return_value=inception),
        ), patch.object(
            mgr, "_try_finalise", new=AsyncMock()
        ), patch.object(
            mgr, "_update_active_kel_key"
        ):
            mock_key = MagicMock()
            mock_key.ChildKey.return_value = mock_key
            mock_key.PrivateKey.return_value = bytes(32)
            mock_key.ChainCode.return_value = bytes(32)
            bip.fromEntropy.return_value = mock_key
            mn = MagicMock()
            mn.to_entropy.return_value = b"\x00" * 16
            mn_cls.return_value = mn
            # force k0 used in startup to match our signed key
            with patch(
                "yadacoin.core.keyrotation.derive_secure_path",
                return_value=k0,
            ), patch(
                "yadacoin.core.identityannouncement.IdentityAnnouncement.get_by_username",
                new=AsyncMock(return_value=None),
            ):
                await mgr.startup_check()
        self.assertEqual(cfg.username_signature, usig)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
