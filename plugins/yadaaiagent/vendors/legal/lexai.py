"""
LexAI Legal — legal services vendor
Category: legal

MCP integration
---------------
Set ``TOOLS["mcp_endpoint"]`` to point at a live MCP server that exposes:
  • check_document_templates(service_type)
  • confirm_legal_order(template_id, urgency, parties)

Adding a new legal vendor
-------------------------
Copy this file, update VENDOR_ID, REGISTRY, the impl functions, and TOOLS.
Drop the new file into this directory and it will be auto-registered.
"""

from ..base import VENDOR_CHAT_INSTRUCTION, gen_confirmation

VENDOR_ID = "legal"

REGISTRY = {
    "name": "LexAI Legal",
    "available": True,
    "prefix": "LEX",
    "vendorPrompt": (
        "You are the intake agent for LexAI Legal. "
        "A customer has been securely verified via YadaCoin KEL identity. "
        "Collect intake details ONE question at a time. "
        "Ask about: governing law / jurisdiction preference, "
        "names of specific parties to include, "
        "and urgency level (standard 5 days / expedited 48 h / urgent same-day). "
        "Do not ask about things already in their scope. "
        "\n" + VENDOR_CHAT_INSTRUCTION
    ),
}


def check_document_templates(args: dict, scope: dict) -> dict:
    """Return available document templates for the requested service type."""
    svc = args.get("service_type") or scope.get("serviceType", "contract_review")
    catalog = {
        "contract_review": [
            {"id": "std-review-v2", "name": "Standard Review", "hours": 4},
            {"id": "exp-review-v1", "name": "Expedited Review", "hours": 2},
        ],
        "nda_draft": [
            {"id": "mutual-nda-v3", "name": "Mutual NDA", "hours": 3},
            {"id": "oneway-nda-v2", "name": "One-way NDA", "hours": 2},
        ],
        "terms_of_service": [
            {"id": "saas-tos-v4", "name": "SaaS ToS", "hours": 6},
        ],
        "privacy_policy": [
            {"id": "gdpr-pp-v3", "name": "GDPR Privacy Policy", "hours": 5},
        ],
    }
    return {"templates": catalog.get(svc, []), "service_type": svc}


def confirm_legal_order(args: dict, scope: dict) -> dict:
    """Confirm the legal service order and return a confirmation record."""
    holder = scope.get("holder", args.get("template_id", ""))
    return {
        "confirmed": True,
        "confirmation": gen_confirmation(VENDOR_ID, holder, REGISTRY["prefix"]),
        "template_id": args.get("template_id"),
        "urgency": args.get("urgency", "standard"),
        "parties": args.get("parties") or [],
    }


TOOLS = {
    "confirm_tool": "confirm_legal_order",
    # "mcp_endpoint": "http://localhost:8020/mcp",
    "schemas": [
        {
            "type": "function",
            "function": {
                "name": "check_document_templates",
                "description": "Retrieve available document templates for the service type.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service_type": {
                            "type": "string",
                            "enum": [
                                "contract_review",
                                "nda_draft",
                                "terms_of_service",
                                "privacy_policy",
                            ],
                        }
                    },
                    "required": ["service_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confirm_legal_order",
                "description": "Confirm the legal service order once all details are gathered.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template_id": {"type": "string"},
                        "urgency": {
                            "type": "string",
                            "enum": ["standard", "expedited", "urgent"],
                        },
                        "parties": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["template_id", "urgency"],
                },
            },
        },
    ],
    "impl": {
        "check_document_templates": check_document_templates,
        "confirm_legal_order": confirm_legal_order,
    },
}
