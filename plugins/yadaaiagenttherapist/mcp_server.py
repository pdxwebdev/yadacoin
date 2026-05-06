"""
Therapist Agent MCP Server
==========================
Runs as a standalone process (requires Python 3.10+) exposing the therapist
scheduling tools over the MCP streamable-http transport.

Install:
    pip install "fastmcp>=2.0"   # or: uvx fastmcp

Run:
    python plugins/yadaaiagenttherapist/mcp_server.py
    # or:
    uvx fastmcp run plugins/yadaaiagenttherapist/mcp_server.py --transport streamable-http --port 8010

Then point the YadaCoin node at it:
    export THERAPIST_MCP_ENDPOINT=http://localhost:8010/mcp

Environment variables:
    THERAPIST_MCP_PORT   — listening port (default: 8010)
"""

import hashlib
import os
from typing import Optional

import fastmcp

mcp = fastmcp.FastMCP("therapist-agent")

# ── Tool implementations ──────────────────────────────────────────────────────

_SCHEDULE = {
    "monday": ["10:00 AM", "2:00 PM", "4:30 PM"],
    "tuesday": ["9:00 AM", "11:00 AM", "3:00 PM"],
    "wednesday": ["10:00 AM", "1:00 PM"],
    "thursday": ["9:00 AM", "2:00 PM", "5:00 PM"],
    "friday": ["10:00 AM", "12:00 PM"],
}


@mcp.tool()
def check_availability(day: Optional[str] = None) -> dict:
    """
    Check available therapy appointment slots.
    If day is provided (monday-friday), returns slots for that day only.
    Otherwise returns the full weekly schedule.
    """
    if day:
        day = day.strip().lower()
        if day in _SCHEDULE:
            return {"day": day, "available_slots": _SCHEDULE[day]}
        return {"error": f"No schedule for '{day}'. Valid days: monday-friday."}
    return {
        "availability": _SCHEDULE,
        "note": "All times local. Sessions: 50 min (individual) or 80 min (couples).",
    }


@mcp.tool()
def get_therapist_info() -> dict:
    """
    Return information about the therapist's specializations, treatment
    modalities, session types, and rates.
    """
    return {
        "name": "YadaCoin Therapist",
        "specializations": ["OCD", "ADD", "ADHD", "anxiety", "stress management"],
        "modalities": [
            "Cognitive Behavioral Therapy (CBT)",
            "Exposure and Response Prevention (ERP)",
            "Dialectical Behavior Therapy (DBT)",
        ],
        "session_types": {
            "individual_50min": {"duration_minutes": 50, "rate_usd": 150},
            "couples_80min": {"duration_minutes": 80, "rate_usd": 220},
        },
        "insurance": "Not accepted — sliding scale available on request.",
    }


@mcp.tool()
def confirm_session(day: str, slot: str, session_type: str) -> dict:
    """
    Book and confirm a therapy session.

    Args:
        day: Day of week e.g. 'monday'
        slot: Time slot e.g. '10:00 AM'
        session_type: 'individual_50min' or 'couples_80min'
    """
    day = day.strip().lower()
    if day not in _SCHEDULE:
        return {"confirmed": False, "error": f"Invalid day '{day}'"}
    if slot not in _SCHEDULE.get(day, []):
        return {"confirmed": False, "error": f"Slot '{slot}' not available on {day}"}
    if session_type not in ("individual_50min", "couples_80min"):
        return {"confirmed": False, "error": f"Unknown session type '{session_type}'"}

    seed = f"{day}{slot}{session_type}"
    code = "THR-" + hashlib.sha256(seed.encode()).hexdigest()[:6].upper()
    is_couples = session_type == "couples_80min"

    return {
        "confirmed": True,
        "confirmation": code,
        "day": day,
        "slot": slot,
        "session_type": session_type,
        "duration_minutes": 80 if is_couples else 50,
        "rate_usd": 220 if is_couples else 150,
        "joining_instructions": (
            "A secure encrypted video link will be sent to your registered contact "
            "15 minutes before your session."
        ),
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("THERAPIST_MCP_PORT", "8010"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
