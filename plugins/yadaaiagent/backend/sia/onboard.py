"""sia/onboard.py — One-time Sia App Key onboarding script.

Run this once to connect your Sia account and export a permanent App Key.
The App Key is what you paste into the Skills drawer — your recovery phrase
is never stored anywhere.

Usage:
    python -m plugins.yadaaiagent.backend.sia.onboard
    -- or --
    cd plugins/yadaaiagent/backend/sia && python onboard.py
"""
import asyncio
import sys

try:
    from sia_storage import AppMetadata, Builder, generate_recovery_phrase
except ImportError:
    print("ERROR: sia-storage is not installed.")
    print("  Run:  pip install sia-storage")
    sys.exit(1)

# Fixed App ID for the YadaCoin AI Agent — must never change.
# "yadaaiagent-v1" (14 bytes) padded to 32 bytes with zeros — 64 hex chars.
_APP_ID_HEX = "7961646161696167656e742d7631000000000000000000000000000000000000"
_APP_ID_BYTES = bytes.fromhex(_APP_ID_HEX)

_INDEXER_URL = "https://sia.storage"

APP_META = AppMetadata(
    id=_APP_ID_BYTES,
    name="YadaCoin AI Agent",
    description="YadaCoin decentralized AI agent with Sia file storage",
    service_url="https://yadacoin.io",
    logo_url=None,
    callback_url=None,
)


async def main():
    print("=" * 60)
    print("  Sia Storage — YadaCoin AI Agent App Key Onboarding")
    print("=" * 60)
    print()

    builder = Builder(_INDEXER_URL, APP_META)

    # Request a connection — this gives us a URL the user must open
    print("Requesting connection to sia.storage…")
    await builder.request_connection()

    approval_url = builder.response_url()
    print()
    print("STEP 1 — Open this URL in your browser and approve the connection:")
    print()
    print(f"  {approval_url}")
    print()
    input("Press Enter after you have approved the connection in your browser… ")
    print()

    print("Waiting for approval confirmation…")
    try:
        await builder.wait_for_approval()
    except Exception as exc:
        print(f"ERROR: Approval failed or timed out: {exc}")
        sys.exit(1)

    print("Approved!")
    print()

    # Recovery phrase
    print("STEP 2 — Enter your BIP-39 recovery phrase.")
    print("  If you don't have one yet, type 'new' to generate a fresh phrase.")
    print("  IMPORTANT: Write down any newly generated phrase and keep it safe.")
    print("  Never share it with anyone — it is your master key.")
    print()
    recovery_phrase = input("Recovery phrase (or 'new'): ").strip()

    if recovery_phrase.lower() == "new":
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

    app_key_bytes = sdk.app_key().export()
    app_key_hex = app_key_bytes.hex()

    print()
    print("=" * 60)
    print("  SUCCESS — Your Sia App Key")
    print("=" * 60)
    print()
    print("Paste this 64-character hex string into the Skills drawer")
    print("under '📁 Sia Storage':")
    print()
    print(f"  {app_key_hex}")
    print()
    print("Store this key securely (password manager recommended).")
    print("Do NOT share it. Your recovery phrase is not needed again")
    print("unless you lose this App Key.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
