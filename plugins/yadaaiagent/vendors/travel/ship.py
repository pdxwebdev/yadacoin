"""
BlueWave Cruises — cruise/ship booking vendor
Category: travel

MCP integration
---------------
Set ``TOOLS["mcp_endpoint"]`` to point at a live MCP server that exposes:
  • check_cabin_options(cabin_type)
  • confirm_ship_booking(cabin_id, dining_seating, shore_excursions)
"""

from ..base import VENDOR_CHAT_INSTRUCTION, gen_confirmation

VENDOR_ID = "ship"

REGISTRY = {
    "name": "BlueWave Cruises",
    "available": True,
    "prefix": "SHP",
    "vendorPrompt": (
        "You are the reservations agent for BlueWave Cruises. "
        "A customer has been securely verified via YadaCoin KEL identity. "
        "Collect their voyage preferences ONE question at a time. "
        "Ask about: cabin type (interior / oceanview / balcony / suite), "
        "dining seating (early / late / anytime), "
        "and shore excursion package (yes / no). "
        "Do not ask about things already in their scope. "
        "\n" + VENDOR_CHAT_INSTRUCTION
    ),
}


def check_cabin_options(args: dict, scope: dict) -> dict:
    """Return available cabins for the requested cabin type."""
    cabin = args.get("cabin_type", "interior").lower()
    catalog = {
        "interior": [
            {"id": "INT-204", "deck": 2, "rate_usd": 499},
            {"id": "INT-318", "deck": 3, "rate_usd": 549},
        ],
        "oceanview": [
            {"id": "OV-512", "deck": 5, "rate_usd": 749},
        ],
        "balcony": [
            {"id": "BAL-708", "deck": 7, "rate_usd": 999},
            {"id": "BAL-812", "deck": 8, "rate_usd": 1099},
        ],
        "suite": [
            {"id": "STE-1001", "deck": 10, "rate_usd": 1899},
        ],
    }
    return {
        "cabin_type": cabin,
        "available_cabins": catalog.get(cabin, catalog["interior"]),
    }


def confirm_ship_booking(args: dict, scope: dict) -> dict:
    """Confirm the cruise booking and return a confirmation record."""
    holder = scope.get("holder", args.get("cabin_id", ""))
    return {
        "confirmed": True,
        "confirmation": gen_confirmation(VENDOR_ID, holder, REGISTRY["prefix"]),
        "cabin_id": args.get("cabin_id"),
        "dining_seating": args.get("dining_seating", "anytime"),
        "shore_excursions": args.get("shore_excursions", False),
        "destination": scope.get("destination"),
        "dates": f"{scope.get('checkin')} → {scope.get('checkout')}",
    }


TOOLS = {
    "confirm_tool": "confirm_ship_booking",
    # "mcp_endpoint": "http://localhost:8012/mcp",
    "schemas": [
        {
            "type": "function",
            "function": {
                "name": "check_cabin_options",
                "description": "Check available cabins on the cruise for a cabin type.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cabin_type": {
                            "type": "string",
                            "enum": ["interior", "oceanview", "balcony", "suite"],
                        }
                    },
                    "required": ["cabin_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confirm_ship_booking",
                "description": "Confirm the cruise booking once all preferences are collected.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cabin_id": {"type": "string"},
                        "dining_seating": {
                            "type": "string",
                            "enum": ["early", "late", "anytime"],
                        },
                        "shore_excursions": {"type": "boolean"},
                    },
                    "required": ["cabin_id", "dining_seating", "shore_excursions"],
                },
            },
        },
    ],
    "impl": {
        "check_cabin_options": check_cabin_options,
        "confirm_ship_booking": confirm_ship_booking,
    },
}
