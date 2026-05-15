"""
Grand Stay Hotels — hotel booking vendor
Category: travel

MCP integration
---------------
Set ``TOOLS["mcp_endpoint"]`` to point at a live MCP server that exposes:
  • check_room_options(room_type)
  • confirm_hotel_booking(room_id, smoking, special_requests)
"""

from ..base import VENDOR_CHAT_INSTRUCTION, gen_confirmation

VENDOR_ID = "hotel"

REGISTRY = {
    "name": "Grand Stay Hotels",
    "available": True,
    "prefix": "HTL",
    "vendorPrompt": (
        "You are the reservations agent for Grand Stay Hotels. "
        "A customer has been securely verified via YadaCoin KEL identity. "
        "Collect their room preferences ONE question at a time. "
        "Ask about: bed type (single king / double queen / twin beds), "
        "smoking or non-smoking room, "
        "and any special requests (early check-in, late check-out, etc.). "
        "Do not ask about things already in their scope. "
        "\n" + VENDOR_CHAT_INSTRUCTION
    ),
}


def check_room_options(args: dict, scope: dict) -> dict:
    """Return available rooms for the requested bed type."""
    room_type = args.get("room_type", "king").lower()
    catalog = {
        "king": [
            {"id": "301", "type": "king", "floor": 3, "rate_usd": 189, "view": "city"},
            {
                "id": "512",
                "type": "king",
                "floor": 5,
                "rate_usd": 219,
                "view": "garden",
            },
        ],
        "queen": [
            {
                "id": "201",
                "type": "double queen",
                "floor": 2,
                "rate_usd": 159,
                "view": "pool",
            },
            {
                "id": "408",
                "type": "double queen",
                "floor": 4,
                "rate_usd": 179,
                "view": "city",
            },
        ],
        "twin": [
            {
                "id": "105",
                "type": "twin",
                "floor": 1,
                "rate_usd": 139,
                "view": "garden",
            },
        ],
    }
    return {"available_rooms": catalog.get(room_type, catalog["king"])}


def confirm_hotel_booking(args: dict, scope: dict) -> dict:
    """Confirm the hotel booking and return a confirmation record."""
    holder = scope.get("holder", args.get("room_id", ""))
    return {
        "confirmed": True,
        "confirmation": gen_confirmation(VENDOR_ID, holder, REGISTRY["prefix"]),
        "room_id": args.get("room_id"),
        "smoking": args.get("smoking", False),
        "special_requests": args.get("special_requests") or "none",
        "checkin": scope.get("checkin"),
        "checkout": scope.get("checkout"),
    }


TOOLS = {
    "confirm_tool": "confirm_hotel_booking",
    # "mcp_endpoint": "http://localhost:8013/mcp",
    "schemas": [
        {
            "type": "function",
            "function": {
                "name": "check_room_options",
                "description": "Check available rooms for the customer's bed type preference.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "room_type": {
                            "type": "string",
                            "enum": ["king", "queen", "twin"],
                        }
                    },
                    "required": ["room_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confirm_hotel_booking",
                "description": "Confirm the booking once all preferences are collected.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "room_id": {"type": "string"},
                        "smoking": {"type": "boolean"},
                        "special_requests": {"type": "string"},
                    },
                    "required": ["room_id", "smoking"],
                },
            },
        },
    ],
    "impl": {
        "check_room_options": check_room_options,
        "confirm_hotel_booking": confirm_hotel_booking,
    },
}
