"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import asyncio
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from yadacoin.core.notifications import (
    NOTIF_ID_BLOCK,
    NOTIF_ID_TXN,
    LocalNotifier,
    NotificationConfig,
    _is_termux,
    _send_termux_notification,
)

from ..test_setup import AsyncTestCase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_block(index=42, hash_val="abcdef1234567890"):
    block = SimpleNamespace()
    block.index = index
    block.hash = hash_val
    return block


def _make_txn_obj(outputs, signature="sigABCDEFGHIJKLMNOP"):
    """Transaction-like object with .outputs list of SimpleNamespace(to, value)."""
    txn = SimpleNamespace()
    txn.outputs = [SimpleNamespace(to=o["to"], value=o["value"]) for o in outputs]
    txn.transaction_signature = signature
    return txn


def _make_txn_dict(outputs, txn_id="sigABCDEFGHIJKLMNOP"):
    """Transaction as a plain dict (no .outputs attribute)."""
    return {
        "outputs": outputs,
        "id": txn_id,
    }


def _cfg(enabled=True, new_block=True, new_transaction=True, addresses=None):
    raw = {
        "enabled": enabled,
        "new_block": new_block,
        "new_transaction": new_transaction,
        "transaction_addresses": addresses or [],
    }
    return NotificationConfig(raw)


# ---------------------------------------------------------------------------
# NotificationConfig
# ---------------------------------------------------------------------------


class TestNotificationConfig(AsyncTestCase):
    async def test_defaults_when_empty_dict(self):
        cfg = NotificationConfig({})
        self.assertFalse(cfg.enabled)
        self.assertTrue(cfg.new_block)
        self.assertTrue(cfg.new_transaction)
        self.assertEqual(cfg.transaction_addresses, [])

    async def test_explicit_values(self):
        cfg = NotificationConfig(
            {
                "enabled": True,
                "new_block": False,
                "new_transaction": False,
                "transaction_addresses": ["addr1", "addr2"],
            }
        )
        self.assertTrue(cfg.enabled)
        self.assertFalse(cfg.new_block)
        self.assertFalse(cfg.new_transaction)
        self.assertEqual(cfg.transaction_addresses, ["addr1", "addr2"])

    async def test_from_dict_none(self):
        cfg = NotificationConfig.from_dict(None)
        self.assertFalse(cfg.enabled)

    async def test_from_dict_with_values(self):
        cfg = NotificationConfig.from_dict({"enabled": True})
        self.assertTrue(cfg.enabled)

    async def test_bool_true(self):
        cfg = NotificationConfig({"enabled": True})
        self.assertTrue(bool(cfg))

    async def test_bool_false(self):
        cfg = NotificationConfig({"enabled": False})
        self.assertFalse(bool(cfg))


# ---------------------------------------------------------------------------
# _is_termux
# ---------------------------------------------------------------------------


class TestIsTermux(AsyncTestCase):
    async def test_non_linux_is_false(self):
        with patch.object(sys, "platform", "darwin"):
            self.assertFalse(_is_termux())

    async def test_linux_without_binary_is_false(self):
        with patch.object(sys, "platform", "linux"):
            with patch("shutil.which", return_value=None):
                self.assertFalse(_is_termux())

    async def test_linux_with_binary_is_true(self):
        with patch.object(sys, "platform", "linux"):
            with patch(
                "shutil.which",
                return_value="/data/data/com.termux/files/usr/bin/termux-notification",
            ):
                self.assertTrue(_is_termux())


# ---------------------------------------------------------------------------
# _send_termux_notification
# ---------------------------------------------------------------------------


class TestSendTermuxNotification(AsyncTestCase):
    def _make_proc(self, returncode=0, stderr=b""):
        proc = MagicMock()
        proc.returncode = returncode
        proc.communicate = AsyncMock(return_value=(None, stderr))
        return proc

    async def test_success_no_ongoing(self):
        proc = self._make_proc()
        with patch(
            "asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)
        ) as mock_exec:
            with patch("asyncio.wait_for", new=AsyncMock(return_value=(None, b""))):
                await _send_termux_notification("Title", "Body", 1)
        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        self.assertIn("termux-notification", args)
        self.assertNotIn("--ongoing", args)

    async def test_success_with_ongoing(self):
        proc = self._make_proc()
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            with patch(
                "asyncio.wait_for", new=AsyncMock(return_value=(None, b""))
            ) as mock_wait:
                await _send_termux_notification("Title", "Body", 1, ongoing=True)
        # ongoing flag should be in the command
        call_args = mock_wait.call_args  # wait_for wraps communicate
        exec_args = asyncio.create_subprocess_exec  # already checked above

    async def test_nonzero_returncode_logs_debug(self):
        proc = self._make_proc(returncode=1, stderr=b"some error")
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            with patch(
                "asyncio.wait_for", new=AsyncMock(return_value=(None, b"some error"))
            ):
                with patch("yadacoin.core.notifications.log") as mock_log:
                    await _send_termux_notification("T", "C", 1)
        mock_log.debug.assert_called()

    async def test_timeout_logs_debug(self):
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=asyncio.TimeoutError),
        ):
            with patch("yadacoin.core.notifications.log") as mock_log:
                await _send_termux_notification("T", "C", 1)
        mock_log.debug.assert_called_with("termux-notification timed out")

    async def test_generic_exception_logs_debug(self):
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=OSError("no such file")),
        ):
            with patch("yadacoin.core.notifications.log") as mock_log:
                await _send_termux_notification("T", "C", 1)
        mock_log.debug.assert_called()

    async def test_wait_for_timeout_logs_debug(self):
        proc = self._make_proc()
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
            with patch(
                "asyncio.wait_for", new=AsyncMock(side_effect=asyncio.TimeoutError)
            ):
                with patch("yadacoin.core.notifications.log") as mock_log:
                    await _send_termux_notification("T", "C", 1)
        mock_log.debug.assert_called_with("termux-notification timed out")


# ---------------------------------------------------------------------------
# LocalNotifier._check_termux
# ---------------------------------------------------------------------------


class TestLocalNotifierCheckTermux(AsyncTestCase):
    async def test_caches_true_result(self):
        notifier = LocalNotifier(_cfg(enabled=True), "addr1")
        with patch("yadacoin.core.notifications._is_termux", return_value=True):
            result1 = notifier._check_termux()
            result2 = notifier._check_termux()
        self.assertTrue(result1)
        self.assertTrue(result2)
        self.assertTrue(notifier._termux_available)

    async def test_caches_false_result_and_logs(self):
        notifier = LocalNotifier(_cfg(enabled=True), "addr1")
        with patch("yadacoin.core.notifications._is_termux", return_value=False):
            with patch("yadacoin.core.notifications.log") as mock_log:
                result = notifier._check_termux()
        self.assertFalse(result)
        mock_log.info.assert_called()

    async def test_does_not_call_is_termux_twice(self):
        notifier = LocalNotifier(_cfg(enabled=True), "addr1")
        with patch(
            "yadacoin.core.notifications._is_termux", return_value=True
        ) as mock_is:
            notifier._check_termux()
            notifier._check_termux()
        mock_is.assert_called_once()


# ---------------------------------------------------------------------------
# LocalNotifier.notify_new_block
# ---------------------------------------------------------------------------


class TestNotifyNewBlock(AsyncTestCase):
    async def test_disabled_cfg_skips(self):
        notifier = LocalNotifier(_cfg(enabled=False), "addr1")
        with patch(
            "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
        ) as mock_send:
            await notifier.notify_new_block(_make_block())
        mock_send.assert_not_called()

    async def test_new_block_false_skips(self):
        notifier = LocalNotifier(_cfg(enabled=True, new_block=False), "addr1")
        with patch(
            "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
        ) as mock_send:
            await notifier.notify_new_block(_make_block())
        mock_send.assert_not_called()

    async def test_no_termux_skips(self):
        notifier = LocalNotifier(_cfg(enabled=True, new_block=True), "addr1")
        with patch.object(notifier, "_check_termux", return_value=False):
            with patch(
                "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
            ) as mock_send:
                await notifier.notify_new_block(_make_block())
        mock_send.assert_not_called()

    async def test_sends_correct_payload(self):
        notifier = LocalNotifier(_cfg(enabled=True, new_block=True), "addr1")
        block = _make_block(index=99, hash_val="deadbeef12345678extra")
        with patch.object(notifier, "_check_termux", return_value=True):
            with patch(
                "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
            ) as mock_send:
                await notifier.notify_new_block(block)
        mock_send.assert_awaited_once()
        title, content, notif_id = mock_send.call_args[0]
        self.assertEqual(notif_id, NOTIF_ID_BLOCK)
        self.assertIn("99", content)
        self.assertIn("deadbeef12345678", content)
        self.assertIn("YadaCoin", title)


# ---------------------------------------------------------------------------
# LocalNotifier.notify_new_transaction
# ---------------------------------------------------------------------------


class TestNotifyNewTransaction(AsyncTestCase):
    async def test_disabled_cfg_skips(self):
        notifier = LocalNotifier(_cfg(enabled=False), "addr1")
        with patch(
            "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
        ) as mock_send:
            await notifier.notify_new_transaction(
                _make_txn_obj([{"to": "addr1", "value": 5}])
            )
        mock_send.assert_not_called()

    async def test_new_transaction_false_skips(self):
        notifier = LocalNotifier(_cfg(enabled=True, new_transaction=False), "addr1")
        with patch(
            "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
        ) as mock_send:
            await notifier.notify_new_transaction(
                _make_txn_obj([{"to": "addr1", "value": 5}])
            )
        mock_send.assert_not_called()

    async def test_no_termux_skips(self):
        notifier = LocalNotifier(_cfg(enabled=True), "addr1")
        with patch.object(notifier, "_check_termux", return_value=False):
            with patch(
                "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
            ) as mock_send:
                await notifier.notify_new_transaction(
                    _make_txn_obj([{"to": "addr1", "value": 5}])
                )
        mock_send.assert_not_called()

    async def test_no_matching_output_skips(self):
        notifier = LocalNotifier(_cfg(enabled=True), "addr1")
        with patch.object(notifier, "_check_termux", return_value=True):
            with patch(
                "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
            ) as mock_send:
                await notifier.notify_new_transaction(
                    _make_txn_obj([{"to": "other_addr", "value": 5}])
                )
        mock_send.assert_not_called()

    async def test_matches_node_address_by_default(self):
        notifier = LocalNotifier(_cfg(enabled=True, addresses=[]), "myaddr")
        txn = _make_txn_obj(
            [{"to": "myaddr", "value": 10}], signature="sig1234567890123456"
        )
        with patch.object(notifier, "_check_termux", return_value=True):
            with patch(
                "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
            ) as mock_send:
                await notifier.notify_new_transaction(txn)
        mock_send.assert_awaited_once()
        _, content, notif_id = mock_send.call_args[0]
        self.assertEqual(notif_id, NOTIF_ID_TXN)
        self.assertIn("10", content)
        self.assertIn("sig1234567890123456"[:16], content)

    async def test_matches_configured_watch_address(self):
        notifier = LocalNotifier(_cfg(enabled=True, addresses=["watchaddr"]), "myaddr")
        txn = _make_txn_obj(
            [{"to": "watchaddr", "value": 7}], signature="sigWATCHADDR1234567"
        )
        with patch.object(notifier, "_check_termux", return_value=True):
            with patch(
                "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
            ) as mock_send:
                await notifier.notify_new_transaction(txn)
        mock_send.assert_awaited_once()

    async def test_dict_txn_matching(self):
        """Plain dict transactions (no .outputs attr) are handled."""
        notifier = LocalNotifier(_cfg(enabled=True, addresses=[]), "myaddr")
        txn = _make_txn_dict(
            [{"to": "myaddr", "value": 3}, {"to": "other", "value": 1}],
            txn_id="dictSig1234567890",
        )
        with patch.object(notifier, "_check_termux", return_value=True):
            with patch(
                "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
            ) as mock_send:
                await notifier.notify_new_transaction(txn)
        mock_send.assert_awaited_once()
        _, content, _ = mock_send.call_args[0]
        self.assertIn("3", content)

    async def test_dict_txn_no_match_skips(self):
        notifier = LocalNotifier(_cfg(enabled=True, addresses=[]), "myaddr")
        txn = _make_txn_dict([{"to": "stranger", "value": 5}])
        with patch.object(notifier, "_check_termux", return_value=True):
            with patch(
                "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
            ) as mock_send:
                await notifier.notify_new_transaction(txn)
        mock_send.assert_not_called()

    async def test_total_value_summed_across_multiple_matching_outputs(self):
        notifier = LocalNotifier(_cfg(enabled=True, addresses=[]), "myaddr")
        txn = _make_txn_obj(
            [
                {"to": "myaddr", "value": 4},
                {"to": "myaddr", "value": 6},
                {"to": "other", "value": 99},
            ],
            signature="multiSig1234567890",
        )
        with patch.object(notifier, "_check_termux", return_value=True):
            with patch(
                "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
            ) as mock_send:
                await notifier.notify_new_transaction(txn)
        _, content, _ = mock_send.call_args[0]
        self.assertIn("10", content)

    async def test_dict_txn_uses_id_field_for_sig(self):
        notifier = LocalNotifier(_cfg(enabled=True, addresses=[]), "myaddr")
        txn = _make_txn_dict([{"to": "myaddr", "value": 1}], txn_id="idField12345678")
        # no transaction_signature attribute
        with patch.object(notifier, "_check_termux", return_value=True):
            with patch(
                "yadacoin.core.notifications._send_termux_notification", new=AsyncMock()
            ) as mock_send:
                await notifier.notify_new_transaction(txn)
        _, content, _ = mock_send.call_args[0]
        self.assertIn("idField12345678"[:16], content)


if __name__ == "__main__":
    unittest.main()
