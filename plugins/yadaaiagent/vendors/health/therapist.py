"""
YadaCoin Therapist — mental health scheduling vendor
Category: health

MCP integration
---------------
Set ``TOOLS["mcp_endpoint"]`` (or the ``THERAPIST_MCP_ENDPOINT`` env-var) to
point at a live MCP server that exposes:
  • check_availability(day?)
  • get_therapist_info()
  • confirm_session(day, slot, session_type)

Run the standalone MCP server:
    python plugins/yadaaiagent/mcp_server_therapist.py
    # or:
    uvx fastmcp run plugins/yadaaiagent/mcp_server_therapist.py --transport streamable-http --port 8010

Then point the YadaCoin node at it:
    export THERAPIST_MCP_ENDPOINT=http://localhost:8010/mcp

Adding a new health vendor
--------------------------
Copy this file, update VENDOR_ID, REGISTRY, the impl functions, and TOOLS.
Drop the new file into this directory and it will be auto-registered.
"""

import os

from ..base import VENDOR_CHAT_INSTRUCTION, gen_confirmation

VENDOR_ID = "therapist"

REGISTRY = {
    "name": "YadaCoin Therapist",
    "available": True,
    "prefix": "THR",
    "vendorPrompt": (
        "You are a scheduling assistant for a mental health therapist "
        "specializing in OCD, ADD, and ADHD. "
        "A client has been securely verified via YadaCoin KEL identity. "
        "Be warm, empathetic, and professional. Ask ONE question at a time. "
        "Use the available tools to check availability and confirm a session. "
        "Do NOT provide therapy, diagnoses, or clinical advice — you only handle scheduling. "
        "\n" + VENDOR_CHAT_INSTRUCTION
    ),
}

_SCHEDULE = {
    "monday": ["10:00 AM", "2:00 PM", "4:30 PM"],
    "tuesday": ["9:00 AM", "11:00 AM", "3:00 PM"],
    "wednesday": ["10:00 AM", "1:00 PM"],
    "thursday": ["9:00 AM", "2:00 PM", "5:00 PM"],
    "friday": ["10:00 AM", "12:00 PM"],
}


def check_availability(args: dict, scope: dict) -> dict:
    """Return available appointment slots, optionally filtered by day."""
    day = (args.get("day") or "").strip().lower()
    if day and day in _SCHEDULE:
        return {"day": day, "available_slots": _SCHEDULE[day]}
    return {
        "availability": {d: slots for d, slots in _SCHEDULE.items()},
        "note": "All times local. Sessions are 50 minutes (individual) or 80 minutes (couples).",
    }


def get_therapist_info(args: dict, scope: dict) -> dict:
    """Return information about the therapist's specializations, modalities, and rates."""
    return {
        "name": "YadaCoin Therapist",
        "specializations": ["OCD", "ADD", "ADHD", "anxiety", "stress management"],
        "modalities": [
            "Cognitive Behavioral Therapy (CBT)",
            "Exposure and Response Prevention (ERP)",
            "Dialectical Behavior Therapy (DBT)",
        ],
        "session_types": ["individual_50min", "couples_80min"],
        "rate_usd": {"individual_50min": 150, "couples_80min": 220},
    }


def confirm_session(args: dict, scope: dict) -> dict:
    """Book and confirm a therapy session."""
    holder = scope.get("holder", args.get("session_type", ""))
    is_couples = "couples" in str(args.get("session_type", ""))
    return {
        "confirmed": True,
        "confirmation": gen_confirmation(VENDOR_ID, holder, REGISTRY["prefix"]),
        "day": args.get("day"),
        "slot": args.get("slot"),
        "session_type": args.get("session_type", "individual_50min"),
        "duration_minutes": 80 if is_couples else 50,
        "joining_instructions": (
            "A secure encrypted video link will be sent to your registered contact "
            "15 minutes before your session."
        ),
    }


TOOLS = {
    "confirm_tool": "confirm_session",
    "mcp_endpoint": os.environ.get("THERAPIST_MCP_ENDPOINT", ""),
    "schemas": [
        {
            "type": "function",
            "function": {
                "name": "check_availability",
                "description": (
                    "Check available therapy appointment slots. "
                    "Optionally filter by day of week."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "day": {
                            "type": "string",
                            "description": "Optional day of week (monday, tuesday, wednesday, thursday, friday)",
                        }
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_therapist_info",
                "description": (
                    "Get information about the therapist's specializations, "
                    "treatment modalities, session types, and rates."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confirm_session",
                "description": "Book and confirm a therapy session once the client has chosen a day, time slot, and session type.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "day": {
                            "type": "string",
                            "description": "Day of the week e.g. 'monday'",
                        },
                        "slot": {
                            "type": "string",
                            "description": "Time slot e.g. '10:00 AM'",
                        },
                        "session_type": {
                            "type": "string",
                            "enum": ["individual_50min", "couples_80min"],
                            "description": "Session format and duration",
                        },
                    },
                    "required": ["day", "slot", "session_type"],
                },
            },
        },
    ],
    "impl": {
        "check_availability": check_availability,
        "get_therapist_info": get_therapist_info,
        "confirm_session": confirm_session,
    },
}
