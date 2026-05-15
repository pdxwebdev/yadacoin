"""
Shared utilities for yadaaiagent vendor modules.

Each vendor file imports from here:
    from ..base import VENDOR_CHAT_INSTRUCTION, gen_confirmation
"""

import hashlib

VENDOR_CHAT_INSTRUCTION = (
    "ALWAYS respond with ONLY a valid JSON object — no markdown, no extra text:\n"
    '{"reply": "your message to the customer", "complete": false, "exit_vendor": false}\n'
    "Set complete=true ONLY when you have received all needed answers and are "
    "ready to confirm the booking. When setting complete=true your reply must "
    "include a friendly booking confirmation message.\n"
    "Set exit_vendor=true (and complete=false) ONLY if the user clearly wants to stop "
    "this booking and switch to a completely different topic or service "
    "(e.g. therapy, travel, shopping, legal help). "
    "In that case reply with a brief acknowledgement such as "
    "'Sure, let me hand you back to the main assistant.'"
)


def gen_confirmation(vendor_id: str, seed: str, prefix: str) -> str:
    """Return a short deterministic confirmation code, e.g. 'FLT-A3B7C2'."""
    h = hashlib.sha256(f"{seed}{vendor_id}".encode()).hexdigest()[:6].upper()
    return f"{prefix}-{h}"
