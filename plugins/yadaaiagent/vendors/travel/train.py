"""
RailEuro Express — train booking vendor
Category: travel

MCP integration
---------------
Set ``TOOLS["mcp_endpoint"]`` to point at a live MCP server that exposes:
  • check_train_seat_options(cabin_class)
  • confirm_train_booking(seat_code, cabin_class, large_luggage)
"""

from ..base import VENDOR_CHAT_INSTRUCTION, gen_confirmation

VENDOR_ID = "train"

REGISTRY = {
    "name": "RailEuro Express",
    "available": True,
    "prefix": "TRN",
    "vendorPrompt": (
        "You are the reservations agent for RailEuro Express. "
        "A customer has been securely verified via YadaCoin KEL identity. "
        "Collect their train preferences ONE question at a time. "
        "Ask about: cabin class (standard / first / sleeper), "
        "seat preference (window / aisle / table), "
        "and bicycle or large luggage (yes / no). "
        "Do not ask about things already in their scope. "
        "\n" + VENDOR_CHAT_INSTRUCTION
    ),
}


def check_train_seat_options(args: dict, scope: dict) -> dict:
    """Return available seats for the requested cabin class."""
    cabin = args.get("cabin_class", "standard").lower()
    options = {
        "standard": [
            {"code": "12A", "type": "window", "extra_usd": 0},
            {"code": "12C", "type": "aisle", "extra_usd": 0},
            {"code": "14T", "type": "table", "extra_usd": 5},
        ],
        "first": [
            {"code": "3A", "type": "window", "extra_usd": 35},
            {"code": "3D", "type": "aisle", "extra_usd": 35},
        ],
        "sleeper": [
            {"code": "S2-L", "type": "lower berth", "extra_usd": 80},
            {"code": "S2-U", "type": "upper berth", "extra_usd": 60},
        ],
    }
    return {"cabin": cabin, "available_seats": options.get(cabin, options["standard"])}


def confirm_train_booking(args: dict, scope: dict) -> dict:
    """Confirm the train booking and return a confirmation record."""
    holder = scope.get("holder", args.get("seat_code", ""))
    return {
        "confirmed": True,
        "confirmation": gen_confirmation(VENDOR_ID, holder, REGISTRY["prefix"]),
        "seat": args.get("seat_code"),
        "cabin_class": args.get("cabin_class", "standard"),
        "large_luggage": args.get("large_luggage", False),
        "destination": scope.get("destination"),
        "dates": f"{scope.get('checkin')} → {scope.get('checkout')}",
    }


TOOLS = {
    "confirm_tool": "confirm_train_booking",
    # "mcp_endpoint": "http://localhost:8011/mcp",
    "schemas": [
        {
            "type": "function",
            "function": {
                "name": "check_train_seat_options",
                "description": "Check available seats on the booked train for a cabin class.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cabin_class": {
                            "type": "string",
                            "enum": ["standard", "first", "sleeper"],
                        }
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confirm_train_booking",
                "description": "Confirm the train booking once all preferences are collected.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "seat_code": {"type": "string"},
                        "cabin_class": {
                            "type": "string",
                            "enum": ["standard", "first", "sleeper"],
                        },
                        "large_luggage": {"type": "boolean"},
                    },
                    "required": ["seat_code", "cabin_class", "large_luggage"],
                },
            },
        },
    ],
    "impl": {
        "check_train_seat_options": check_train_seat_options,
        "confirm_train_booking": confirm_train_booking,
    },
}
