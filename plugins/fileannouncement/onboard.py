"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""One-time Sia App Key onboarding for File Announcements.

App Keys are bound to this plugin's fixed App ID. A key from sia.storage
dashboard alone, or from another Yada plugin (e.g. AI Agent), will not work
with Builder.connected() until you complete this flow.

Usage (from repo root, with sia-storage installed):

    python -m plugins.fileannouncement.onboard

Paste the printed 64-char hex App Key into:
  /file-announcements → Settings → Sia App Key

Flow matches https://devs.sia.storage/docs/quickstart/connect-to-an-indexer
  request_connection → print URL → wait_for_approval (polls while you approve)
  → register(mnemonic) → export App Key
"""

import asyncio
import sys
import webbrowser

from plugins.fileannouncement.backends import (
    DEFAULT_INDEXER_URL,
    SIA_APP_ID_BYTES,
    SIA_APP_ID_HEX,
)


def _app_metadata():
    from sia_storage import AppMetadata

    return AppMetadata(
        id=SIA_APP_ID_BYTES,
        name="YadaCoin File Announcements",
        description="On-chain file announcements backed by Sia storage",
        service_url="https://yadacoin.io",
        logo_url=None,
        callback_url=None,
    )


async def main():
    try:
        from sia_storage import Builder, generate_recovery_phrase
    except ImportError:
        print("ERROR: sia-storage is not installed.")
        print("  Run:  pip install sia-storage")
        sys.exit(1)

    print("=" * 60)
    print("  Sia Storage — File Announcements App Key Onboarding")
    print("=" * 60)
    print()
    print(f"App ID (fixed): {SIA_APP_ID_HEX}")
    print("Free sia.storage plans allow up to 3 connected apps.")
    print("If approval fails, remove an unused app on sia.storage and retry.")
    print()

    builder = Builder(DEFAULT_INDEXER_URL, _app_metadata())

    print("Requesting connection to sia.storage…")
    await builder.request_connection()

    approval_url = builder.response_url()
    print()
    print("STEP 1 — Open this URL and approve while this script waits:")
    print()
    print(f"  {approval_url}")
    print()
    print("Do NOT close this terminal. wait_for_approval() must be running")
    print("when you click Approve (official SDK order).")
    print()
    try:
        webbrowser.open(approval_url)
        print("(Opened browser if available.)")
    except Exception:
        pass
    print()
    print("Waiting for approval…")

    try:
        # Must poll WHILE the user approves — do not block on input() first.
        await builder.wait_for_approval()
    except Exception as exc:
        print()
        print(f"ERROR: Approval failed or timed out: {exc}")
        print()
        print("Common causes:")
        print("  • Request expired before approve (re-run this script)")
        print("  • You declined the request")
        print("  • Free plan app slot limit (max 3) — revoke an old app")
        print("  • Network issue while polling")
        sys.exit(1)

    print("Approved!")
    print()

    print("STEP 2 — Enter your BIP-39 recovery phrase.")
    print("  Type 'new' or 'seed' to generate a fresh phrase.")
    print("  IMPORTANT: Write down any new phrase and keep it safe.")
    print("  Never share it — it is your master key.")
    print()
    recovery_phrase = input("Recovery phrase (or 'new'/'seed'): ").strip()

    if recovery_phrase.lower() in ("new", "seed"):
        recovery_phrase = generate_recovery_phrase()
        print()
        print("Your new recovery phrase (WRITE THIS DOWN AND KEEP IT SAFE):")
        print()
        print(f"  {recovery_phrase}")
        print()
        input("Press Enter once you have saved your recovery phrase… ")
    print()

    print("Registering with the indexer…")
    try:
        sdk = await builder.register(recovery_phrase)
    except Exception as exc:
        print(f"ERROR: Registration failed: {exc}")
        sys.exit(1)

    app_key_hex = sdk.app_key().export().hex()

    print()
    print("=" * 60)
    print("  SUCCESS — Your File Announcements Sia App Key")
    print("=" * 60)
    print()
    print("The app should now appear under connected apps on sia.storage.")
    print("Paste this 64-character hex string into:")
    print("  /file-announcements → Settings → Sia App Key")
    print()
    print(f"  {app_key_hex}")
    print()
    print("Store this key securely. Do NOT share it.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
