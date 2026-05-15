"""
SkyLink Airlines — flight booking vendor
Category: travel

This module registers the flight vendor with the yadaaiagent plugin.

MCP integration
---------------
To replace the mock implementation with a live MCP server, set
``mcp_endpoint`` in the ``TOOLS`` dict below:

    TOOLS["mcp_endpoint"] = "http://my-flight-mcp-server:8010/mcp"

The MCP server must expose two tools whose names match ``TOOLS["schemas"]``:
  • check_seat_options(cabin_class)
  • confirm_flight_booking(seat_code, meal_preference, extra_baggage)

When ``mcp_endpoint`` is set, the ``impl`` callables are replaced at runtime
by async wrappers that call the MCP server (see MCPClient.make_impl in
handlers.py).

Adding a new travel vendor
--------------------------
Copy this file, update VENDOR_ID, REGISTRY, the impl functions, and TOOLS.
Drop the new file into this directory and it will be auto-registered.
"""

from ..base import VENDOR_CHAT_INSTRUCTION, gen_confirmation

# ── Vendor identity ────────────────────────────────────────────────────────────

VENDOR_ID = "flight"

REGISTRY = {
    "name": "SkyLink Airlines",
    "available": True,
    "prefix": "FLT",
    "vendorPrompt": (
        "You are the reservations agent for SkyLink Airlines. "
        "A customer has been securely verified via YadaCoin KEL identity. "
        "Collect their flight preferences ONE question at a time. "
        "Ask about: seat preference (window / middle / aisle), "
        "meal preference (standard / vegetarian / vegan / none), "
        "and extra checked baggage (yes / no). "
        "Do not ask about things already in their scope. "
        "\n" + VENDOR_CHAT_INSTRUCTION
    ),
}

# ── Tool implementations (mock) ────────────────────────────────────────────────
# Replace with real API calls or point TOOLS["mcp_endpoint"] at an MCP server.


def check_seat_options(args: dict, scope: dict) -> dict:
    """Return available seats for the requested cabin class."""
    cabin = args.get("cabin_class", "economy").lower()
    options = {
        "economy": [
            {"code": "23A", "type": "window", "extra_usd": 0},
            {"code": "23B", "type": "middle", "extra_usd": 0},
            {"code": "23C", "type": "aisle", "extra_usd": 0},
        ],
        "business": [
            {"code": "4A", "type": "window", "extra_usd": 50},
            {"code": "4D", "type": "aisle", "extra_usd": 50},
        ],
    }
    return {"cabin": cabin, "available_seats": options.get(cabin, options["economy"])}


def confirm_flight_booking(args: dict, scope: dict) -> dict:
    """Confirm the flight booking and return a confirmation record."""
    holder = scope.get("holder", args.get("seat_code", ""))
    return {
        "confirmed": True,
        "confirmation": gen_confirmation(VENDOR_ID, holder, REGISTRY["prefix"]),
        "seat": args.get("seat_code"),
        "meal": args.get("meal_preference", "standard"),
        "extra_baggage": args.get("extra_baggage", False),
        "destination": scope.get("destination"),
        "dates": f"{scope.get('checkin')} → {scope.get('checkout')}",
    }


# ── MCP tool registry ──────────────────────────────────────────────────────────
# ``schemas`` follow the OpenAI function-calling format (compatible with
# Anthropic and Ollama tool-capable models).
#
# To switch to a live MCP server, uncomment and set:
#   "mcp_endpoint": "http://localhost:8010/mcp",

TOOLS = {
    "confirm_tool": "confirm_flight_booking",
    # "mcp_endpoint": "http://localhost:8010/mcp",
    "schemas": [
        {
            "type": "function",
            "function": {
                "name": "check_seat_options",
                "description": "Check available seats on the booked flight.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cabin_class": {
                            "type": "string",
                            "enum": ["economy", "business"],
                        }
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confirm_flight_booking",
                "description": "Confirm the booking once all preferences are collected.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "seat_code": {"type": "string"},
                        "meal_preference": {
                            "type": "string",
                            "enum": ["standard", "vegetarian", "vegan", "none"],
                        },
                        "extra_baggage": {"type": "boolean"},
                    },
                    "required": ["seat_code", "meal_preference", "extra_baggage"],
                },
            },
        },
    ],
    "impl": {
        "check_seat_options": check_seat_options,
        "confirm_flight_booking": confirm_flight_booking,
    },
}
