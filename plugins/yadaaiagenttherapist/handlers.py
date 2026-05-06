"""yadaaiagenttherapist — standalone YadaCoin plugin for the therapist agent.

This is a self-contained plugin that lives in its own repository.
To use it, clone this repo into plugins/yadaaiagenttherapist/ on your
YadaCoin node (which must already have the yadaaiagent plugin installed).

Routes added
------------
  /therapist-agent                  — vendor info / challenge token
  /therapist-agent/challenge        — challenge endpoint
  /therapist-agent/chat             — MCP-powered booking chat
  /ai-agent-auth/api/vendor/therapist          — same via standard vendor prefix
  /ai-agent-auth/api/vendor/therapist/challenge
  /ai-agent-auth/api/vendor/therapist/chat

Environment variables
---------------------
  THERAPIST_MCP_ENDPOINT
      URL of the therapist MCP server (default: "", uses built-in mock impl).
      Example: http://localhost:8010/mcp
      Run the server: python plugins/yadaaiagenttherapist/mcp_server.py
      (requires Python 3.10+ and fastmcp — see requirements.txt)
"""

import os

from plugins.yadaaiagent.handlers import (
    _AGENT_TYPE_MAP,
    _VENDOR_CHAT_INSTRUCTION,
    _VENDOR_TOOLS,
    AGENT_TYPES,
    VENDOR_REGISTRY,
    AgentChallengeHandler,
    VendorBaseHandler,
    VendorChatBaseHandler,
    _gen_confirmation,
)

# ── Mock tool implementations (fallback when MCP server is not running) ───────


def _therapist_check_availability(args: dict, scope: dict) -> dict:
    day = (args.get("day") or "").strip().lower()
    schedule = {
        "monday": ["10:00 AM", "2:00 PM", "4:30 PM"],
        "tuesday": ["9:00 AM", "11:00 AM", "3:00 PM"],
        "wednesday": ["10:00 AM", "1:00 PM"],
        "thursday": ["9:00 AM", "2:00 PM", "5:00 PM"],
        "friday": ["10:00 AM", "12:00 PM"],
    }
    if day and day in schedule:
        return {"day": day, "available_slots": schedule[day]}
    return {
        "availability": {d: slots for d, slots in schedule.items()},
        "note": "All times local. Sessions are 50 minutes (individual) or 80 minutes (couples).",
    }


def _therapist_get_info(args: dict, scope: dict) -> dict:
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


def _therapist_confirm_session(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("session_type", ""))
    is_couples = "couples" in str(args.get("session_type", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("therapist", holder),
        "day": args.get("day"),
        "slot": args.get("slot"),
        "session_type": args.get("session_type", "individual_50min"),
        "duration_minutes": 80 if is_couples else 50,
        "joining_instructions": (
            "A secure encrypted video link will be sent to your registered contact "
            "15 minutes before your session."
        ),
    }


# ── Register therapist with yadaaiagent's shared registries ──────────────────
# Both dicts are imported by reference, so mutations here are visible to
# VendorBaseHandler and VendorChatBaseHandler at request time.

VENDOR_REGISTRY["therapist"] = {
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
        "\n" + _VENDOR_CHAT_INSTRUCTION
    ),
}

_VENDOR_TOOLS["therapist"] = {
    "confirm_tool": "confirm_session",
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
        "check_availability": _therapist_check_availability,
        "get_therapist_info": _therapist_get_info,
        "confirm_session": _therapist_confirm_session,
    },
    # When THERAPIST_MCP_ENDPOINT is set, the tool loop in yadaaiagent replaces
    # the mock impl above with live async MCP calls via MCPClient.make_impl().
    # Example: export THERAPIST_MCP_ENDPOINT=http://localhost:8010/mcp
    "mcp_endpoint": os.environ.get("THERAPIST_MCP_ENDPOINT", ""),
}

# ── Generate route handlers ───────────────────────────────────────────────────

TherapistVendorHandler = type(
    "TherapistVendorHandler",
    (VendorBaseHandler,),
    {"vendor_service": "therapist"},
)

TherapistVendorChatHandler = type(
    "TherapistVendorChatHandler",
    (VendorChatBaseHandler,),
    {"vendor_service": "therapist"},
)

# ── Register therapy as a detectable agent type ───────────────────────────────
# AGENT_TYPES and _AGENT_TYPE_MAP are imported by reference from yadaaiagent.
# Mutating them here makes the therapy type visible to:
#   - GET /ai-agent-auth/api/agents  (frontend agent list)
#   - AgentChatHandler               (agent_type lookup + systemPrompt dispatch)
#   - The frontend's auto-switch on detected_agent_type

_THERAPY_AGENT_TYPE = {
    "id": "therapy",
    "label": "Therapy Booking",
    "description": "Book a therapy session with a YadaCoin-verified mental health professional.",
    "icon": "🧠",
    "routing_hint": (
        "user mentions needing therapy, a therapist, mental health support, counselling, "
        "or help with OCD, ADD, ADHD, anxiety, depression, or stress. "
        "Examples: 'I need therapy', 'I need a therapist', 'I want to see a therapist', "
        "'help with my anxiety', 'I'm struggling with OCD'"
    ),
    "authorizationType": "TherapyBookingAuthorization",
    "fields": [
        {
            "key": "session_type",
            "label": "Session Type",
            "type": "select",
            "options": ["individual_50min", "couples_80min"],
        },
        {"key": "preferred_day", "label": "Preferred Day", "type": "text"},
    ],
    "services": ["therapist"],
    "systemPrompt": (
        "You are a therapy scheduling intake assistant. Your ONLY job is to collect "
        "the session type and a preferred day for the appointment. "
        "Be warm, empathetic, and professional. "
        "You CANNOT provide therapy, clinical advice, or diagnoses.\n"
        "ALWAYS respond with ONLY a valid JSON object:\n"
        "{\n"
        '  "reply": "your conversational response",\n'
        '  "extracted": {\n'
        '    "session_type": "individual_50min|couples_80min or null",\n'
        '    "preferred_day": "day of week or null"\n'
        "  },\n"
        '  "complete": false,\n'
        '  "detected_agent_type": "therapy"\n'
        "}\n"
        "complete=true only when BOTH session_type AND preferred_day are known. "
        "When complete=true, summarise and say the operator will confirm the booking.\n"
        "If the user clearly wants something other than therapy scheduling (e.g. travel, shopping, legal help), "
        "set detected_agent_type to 'general'."
    ),
}

# Only add once (idempotent if module is re-imported)
if not any(a["id"] == "therapy" for a in AGENT_TYPES):
    AGENT_TYPES.append(_THERAPY_AGENT_TYPE)
    _AGENT_TYPE_MAP["therapy"] = _THERAPY_AGENT_TYPE

# ── Route table ───────────────────────────────────────────────────────────────

HANDLERS = [
    # Dedicated endpoint matching the on-chain registered endpoint_url
    (r"/therapist-agent/challenge", AgentChallengeHandler),
    (r"/therapist-agent/chat", TherapistVendorChatHandler),
    (r"/therapist-agent", TherapistVendorHandler),
    # Standard vendor prefix routes (same handler, alternate URLs)
    (r"/ai-agent-auth/api/vendor/therapist/challenge", AgentChallengeHandler),
    (r"/ai-agent-auth/api/vendor/therapist/chat", TherapistVendorChatHandler),
    (r"/ai-agent-auth/api/vendor/therapist", TherapistVendorHandler),
]
