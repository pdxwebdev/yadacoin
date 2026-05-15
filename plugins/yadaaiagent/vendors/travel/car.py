"""
DriveEasy Rentals — car rental vendor
Category: travel

MCP integration
---------------
Set ``TOOLS["mcp_endpoint"]`` to point at a live MCP server that exposes:
  • check_vehicle_options(vehicle_size)
  • confirm_car_rental(vehicle_id, gps, extra_driver)
"""

from ..base import VENDOR_CHAT_INSTRUCTION, gen_confirmation

VENDOR_ID = "car"

REGISTRY = {
    "name": "DriveEasy Rentals",
    "available": True,
    "prefix": "CAR",
    "vendorPrompt": (
        "You are the rental agent for DriveEasy Rentals. "
        "A customer has been securely verified via YadaCoin KEL identity. "
        "Collect their rental preferences ONE question at a time. "
        "Ask about: vehicle size (economy / compact / standard / SUV / luxury), "
        "GPS add-on (yes / no), "
        "and additional driver (yes / no). "
        "Do not ask about things already in their scope. "
        "\n" + VENDOR_CHAT_INSTRUCTION
    ),
}


def check_vehicle_options(args: dict, scope: dict) -> dict:
    """Return available rental vehicles of the requested size."""
    size = args.get("vehicle_size", "standard").lower()
    fleet = {
        "economy": [{"id": "eco-01", "model": "Toyota Corolla", "rate_usd": 45}],
        "compact": [{"id": "cmp-01", "model": "Honda Civic", "rate_usd": 55}],
        "standard": [{"id": "std-01", "model": "Toyota Camry", "rate_usd": 70}],
        "suv": [{"id": "suv-01", "model": "Ford Explorer", "rate_usd": 95}],
        "luxury": [{"id": "lux-01", "model": "BMW 5 Series", "rate_usd": 150}],
    }
    return {"available_vehicles": fleet.get(size, fleet["standard"])}


def confirm_car_rental(args: dict, scope: dict) -> dict:
    """Confirm the car rental and return a confirmation record."""
    holder = scope.get("holder", args.get("vehicle_id", ""))
    return {
        "confirmed": True,
        "confirmation": gen_confirmation(VENDOR_ID, holder, REGISTRY["prefix"]),
        "vehicle_id": args.get("vehicle_id"),
        "gps": args.get("gps", False),
        "extra_driver": args.get("extra_driver", False),
        "pickup": scope.get("checkin"),
    }


TOOLS = {
    "confirm_tool": "confirm_car_rental",
    # "mcp_endpoint": "http://localhost:8014/mcp",
    "schemas": [
        {
            "type": "function",
            "function": {
                "name": "check_vehicle_options",
                "description": "Check available rental vehicles of the requested size.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vehicle_size": {
                            "type": "string",
                            "enum": ["economy", "compact", "standard", "suv", "luxury"],
                        }
                    },
                    "required": ["vehicle_size"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confirm_car_rental",
                "description": "Confirm the rental once all preferences are collected.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vehicle_id": {"type": "string"},
                        "gps": {"type": "boolean"},
                        "extra_driver": {"type": "boolean"},
                    },
                    "required": ["vehicle_id", "gps", "extra_driver"],
                },
            },
        },
    ],
    "impl": {
        "check_vehicle_options": check_vehicle_options,
        "confirm_car_rental": confirm_car_rental,
    },
}
