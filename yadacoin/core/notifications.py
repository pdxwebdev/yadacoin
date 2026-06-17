"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Local notifications for Android/Termux environments.

Requires the Termux:API app and the termux-api package installed:
    pkg install termux-api

Configuration (config.json):
    "notifications": {
        "enabled": true,
        "new_block": true,
        "new_transaction": true,
        "transaction_addresses": []   // list of addresses to watch; empty = node address only
    }
"""

import asyncio
import logging
import shutil
import sys
from typing import Optional

log = logging.getLogger(__name__)

# Stable notification IDs so Android replaces rather than stacks them
NOTIF_ID_BLOCK = 1000
NOTIF_ID_TXN = 1001


# Well-known absolute path in case Termux bin dir is not on $PATH
_TERMUX_NOTIFICATION_BIN = "/data/data/com.termux/files/usr/bin/termux-notification"


def _termux_notification_path() -> Optional[str]:
    """Return the absolute path to termux-notification, or None if unavailable."""
    # Prefer PATH lookup; fall back to the well-known Termux location
    found = shutil.which("termux-notification")
    if found:
        return found
    import os

    if os.path.isfile(_TERMUX_NOTIFICATION_BIN):
        return _TERMUX_NOTIFICATION_BIN
    return None


def _is_termux() -> bool:
    """Return True when running inside a Termux environment."""
    return (
        sys.platform.startswith(("linux", "android"))
        and _termux_notification_path() is not None
    )


async def _send_termux_notification(
    title: str,
    content: str,
    notification_id: int,
    *,
    ongoing: bool = False,
) -> None:
    """
    Fire-and-forget wrapper around the `termux-notification` CLI.
    Runs the subprocess asynchronously so it never blocks the event loop.
    """
    binary = _termux_notification_path()
    if not binary:
        log.warning("termux-notification binary not found; cannot send notification.")
        return
    cmd = [
        binary,
        "--title",
        title,
        "--content",
        content,
        "--id",
        str(notification_id),
    ]
    if ongoing:
        cmd.append("--ongoing")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        if proc.returncode != 0:
            log.warning(
                "termux-notification exited %s: %s",
                proc.returncode,
                stderr.decode().strip() if stderr else "",
            )
        else:
            log.debug(
                "termux-notification sent: id=%s title=%r", notification_id, title
            )
    except asyncio.TimeoutError:
        log.warning("termux-notification timed out")
    except Exception as exc:
        log.warning("termux-notification failed: %s", exc)


class NotificationConfig:
    """Parsed notification settings from config.json."""

    def __init__(self, raw: dict):
        self.enabled: bool = raw.get("enabled", False)
        self.new_block: bool = raw.get("new_block", True)
        self.new_transaction: bool = raw.get("new_transaction", True)
        # Addresses to watch for incoming transactions.
        # If empty the node's own address is used (populated later by Config).
        self.transaction_addresses: list = raw.get("transaction_addresses", [])

    @classmethod
    def from_dict(cls, raw: Optional[dict]) -> "NotificationConfig":
        if raw is None:
            return cls({})
        return cls(raw)

    def __bool__(self) -> bool:
        return self.enabled


class LocalNotifier:
    """
    Thin façade used by the rest of the codebase.

    Usage:
        notifier = LocalNotifier(config.notifications, config.address)
        await notifier.notify_new_block(block)
        await notifier.notify_new_transaction(txn)
    """

    def __init__(self, notification_cfg: NotificationConfig, node_address: str):
        self.cfg = notification_cfg
        self.node_address = node_address
        self._termux_available: Optional[bool] = None

    def _check_termux(self) -> bool:
        if self._termux_available is None:
            path = _termux_notification_path()
            self._termux_available = (
                sys.platform.startswith(("linux", "android")) and path is not None
            )
            if not self._termux_available:
                log.warning(
                    "termux-notification not found (PATH=%s); local notifications "
                    "disabled. Install termux-api: pkg install termux-api",
                    __import__("os").environ.get("PATH", "(unset)"),
                )
            else:
                log.info("termux-notification found at %s", path)
        return self._termux_available

    async def notify_new_block(self, block) -> None:
        if not self.cfg.enabled or not self.cfg.new_block:
            return
        if not self._check_termux():
            return
        title = "YadaCoin – New Block"
        content = f"Block #{block.index}  hash: {block.hash[:16]}…"
        await _send_termux_notification(title, content, NOTIF_ID_BLOCK)

    async def notify_new_transaction(self, txn) -> None:
        """
        Notify when a transaction involves one of the watched addresses.
        ``txn`` may be a Transaction object or a plain dict.
        """
        if not self.cfg.enabled or not self.cfg.new_transaction:
            return
        if not self._check_termux():
            return

        watch = set(self.cfg.transaction_addresses) or {self.node_address}

        # Support both Transaction objects and raw dicts
        outputs = getattr(txn, "outputs", None)
        if outputs is None:
            outputs = [
                type("_O", (), {"to": o.get("to", ""), "value": o.get("value", 0)})()
                for o in txn.get("outputs", [])
            ]

        matching = [o for o in outputs if getattr(o, "to", "") in watch]
        if not matching:
            return

        total = sum(getattr(o, "value", 0) for o in matching)
        sig = getattr(txn, "transaction_signature", None) or txn.get("id", "")
        title = "YadaCoin – New Transaction"
        content = f"+{total} YADA  txn: {sig[:16]}…"
        await _send_termux_notification(title, content, NOTIF_ID_TXN)
