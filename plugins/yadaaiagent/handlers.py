"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

yadaaiagent — KEL-backed AI agent platform plugin.

Architecture:  human → KEL pre-commitment → challenge-response → external service

Flow
----
1. Operator visits /ai-agent-auth and initialises their key in localStorage.
2. They select an agent type and start a conversation; the agent collects the
   required fields for that agent type via multi-turn chat.
3. On approval the browser:
     a. Derives the next child key client-side (second_factor stays in browser).
     b. Broadcasts a rotation transaction with a structured JSON scope committed
        in the ``relationship`` field.
     c. Receives ``prerotated_private_key`` — the one-time agent credential.
4. The browser then does a challenge-response with each vendor service:
     a. GET /ai-agent-auth/api/vendor/<service>/challenge?public_key=<hex>
     b. Signs SHA256(challenge_utf8 + canonical_vp_bytes) client-side.
     c. POST /ai-agent-auth/api/vendor/<service>  {public_key, challenge, vp}
5. The server independently validates each VP against the KEL.

Endpoints
---------
GET  /ai-agent-auth                                — SPA shell
GET  /ai-agent-auth/api/agents                     — list registered agent types
GET  /ai-agent-auth/api/challenge                  — stateless HMAC challenge
POST /ai-agent-auth/api/chat                       — LLM proxy (agent_type aware)
POST /ai-agent-auth/api/travel                     — legacy combined travel endpoint
GET  /ai-agent-auth/api/vendor/<svc>/challenge     — per-vendor challenge
POST /ai-agent-auth/api/vendor/<svc>               — per-vendor VP booking
"""

import hashlib
import json
import os

import tornado.web
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from yadacoin_agent_auth import AgentAuthValidator, AuthError, YadaCoinNodeKelProvider

from yadacoin.http.base import BaseHandler

# ── Challenge secret ──────────────────────────────────────────────────────────
# Override with YADACOIN_AGENT_SECRET env-var in production.
_CHALLENGE_SECRET = os.environ.get(
    "YADACOIN_AGENT_SECRET", "yadacoin-demo-agent-secret-2026"
).encode("utf-8")

_validator = AgentAuthValidator(
    challenge_secret=_CHALLENGE_SECRET,
    kel_provider=YadaCoinNodeKelProvider(),
)


# ── Agent type registry ───────────────────────────────────────────────────────
# Each entry describes an agent type available in the UI.
# Keys used by the SPA: id, label, description, authorizationType, fields, services
#
# fields: list of {key, label, type} — the scope fields the agent collects.
# services: list of vendor service ids that can fulfil this agent type's requests.

AGENT_TYPES = [
    {
        "id": "general",
        "label": "General Chat",
        "description": "Open-ended conversation. Ask anything — no structured booking flow.",
        "icon": "💬",
        "authorizationType": None,
        "fields": [],
        "services": [],
        "systemPrompt": (
            "You are a helpful AI assistant powered by the YadaCoin KEL identity system. "
            "Answer the user's questions conversationally.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your response",\n'
            '  "extracted": {},\n'
            '  "complete": false,\n'
            '  "detected_agent_type": "general"\n'
            "}\n"
            "detected_agent_type rules — change from 'general' when the user's intent clearly fits:\n"
            '- "travel": user mentions wanting to go somewhere, visit a destination, travel, '
            "take a trip, book a flight/hotel/car, or asks about travel arrangements. "
            "Examples: 'I want to go to Mexico', 'I'm planning a trip to Paris', 'book me a flight'\n"
            '- "legal": user explicitly asks to DRAFT, REVIEW, or get help with a legal document, '
            "contract, NDA, terms of service, or privacy policy\n"
            '- "ecommerce": user explicitly asks to ORDER, BUY, or purchase a physical product\n'
            "Keep detected_agent_type as 'general' for greetings, vague questions, or topics "
            "that don't clearly fit the above.\n"
            "complete MUST always be false."
        ),
    },
    {
        "id": "travel",
        "label": "Travel Booking",
        "description": "Book flights, hotels, and car rentals with KEL-backed agent credentials.",
        "icon": "✈️",
        "authorizationType": "TravelBookingAuthorization",
        "fields": [
            {"key": "destination", "label": "Destination", "type": "text"},
            {"key": "checkin", "label": "Check-in", "type": "text"},
            {"key": "checkout", "label": "Check-out", "type": "text"},
            {
                "key": "services",
                "label": "Services",
                "type": "multiselect",
                "options": ["hotel", "flight", "car"],
            },
        ],
        "services": ["hotel", "flight", "car"],
        "systemPrompt": (
            "You are a travel booking assistant. Your ONLY job is to collect travel details.\n"
            "You CANNOT book anything, confirm any reservation, or process any payment.\n"
            "NEVER ask for credit card details, payment info, or personal identification.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "destination": "city/destination or null",\n'
            '    "checkin": "check-in date (e.g. May 10) or null",\n'
            '    "checkout": "check-out date (e.g. May 16) or null",\n'
            '    "services": ["hotel","flight","car"] subset or null\n'
            "  },\n"
            '  "complete": false\n'
            "}\n"
            "Rules:\n"
            "- Only use service values: hotel, flight, car\n"
            '- If the user says "all": services=["hotel","flight","car"]\n'
            "- complete MUST be false unless ALL FOUR fields are known\n"
            '- For date ranges like "May 10-16": checkin="May 10", checkout="May 16"\n'
            "- When complete=true: summarise all details and say the operator will approve"
        ),
    },
    {
        "id": "legal",
        "label": "Legal Services",
        "description": "Request legal document drafting and review with scoped agent credentials.",
        "icon": "⚖️",
        "authorizationType": "LegalServiceAuthorization",
        "fields": [
            {
                "key": "serviceType",
                "label": "Service Type",
                "type": "select",
                "options": [
                    "contract_review",
                    "nda_draft",
                    "terms_of_service",
                    "privacy_policy",
                ],
            },
            {"key": "jurisdiction", "label": "Jurisdiction", "type": "text"},
            {"key": "deadline", "label": "Deadline", "type": "text"},
        ],
        "services": ["legal"],
        "systemPrompt": (
            "You are a legal services intake assistant. Your ONLY job is to collect details "
            "for a legal services request. You CANNOT provide legal advice or draft documents.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "serviceType": "contract_review|nda_draft|terms_of_service|privacy_policy or null",\n'
            '    "jurisdiction": "jurisdiction/country or null",\n'
            '    "deadline": "deadline date or null"\n'
            "  },\n"
            '  "complete": false\n'
            "}\n"
            "complete=true only when ALL THREE fields are known."
        ),
    },
    {
        "id": "ecommerce",
        "label": "E-Commerce",
        "description": "Authorise an AI agent to place orders on your behalf with scoped spending limits.",
        "icon": "🛒",
        "authorizationType": "ECommerceAuthorization",
        "fields": [
            {"key": "items", "label": "Items", "type": "text"},
            {"key": "maxAmount", "label": "Max Spend (USD)", "type": "number"},
            {"key": "deliveryAddress", "label": "Delivery Address", "type": "text"},
        ],
        "services": ["ecommerce"],
        "systemPrompt": (
            "You are an e-commerce shopping assistant. Collect the items to purchase, "
            "maximum spend limit, and delivery address. You CANNOT place orders yourself.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "items": "comma-separated item list or null",\n'
            '    "maxAmount": number or null,\n'
            '    "deliveryAddress": "full address or null"\n'
            "  },\n"
            '  "complete": false\n'
            "}\n"
            "complete=true only when ALL THREE fields are known."
        ),
    },
]

# Index by id for fast lookup
_AGENT_TYPE_MAP = {a["id"]: a for a in AGENT_TYPES}


# ── Vendor registry ───────────────────────────────────────────────────────────
# Maps service id → {name, available, confirmationPrefix}
# Add new services here; a VendorHandler subclass is auto-generated below.

_VENDOR_CHAT_INSTRUCTION = (
    "ALWAYS respond with ONLY a valid JSON object — no markdown, no extra text:\n"
    '{"reply": "your message to the customer", "complete": false}\n'
    "Set complete=true ONLY when you have received all needed answers and are "
    "ready to confirm the booking. When setting complete=true your reply must "
    "include a friendly booking confirmation message."
)

VENDOR_REGISTRY = {
    "flight": {
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
            "\n" + _VENDOR_CHAT_INSTRUCTION
        ),
    },
    "hotel": {
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
            "\n" + _VENDOR_CHAT_INSTRUCTION
        ),
    },
    "car": {
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
            "\n" + _VENDOR_CHAT_INSTRUCTION
        ),
    },
    "legal": {
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
            "\n" + _VENDOR_CHAT_INSTRUCTION
        ),
    },
    "ecommerce": {
        "name": "QuickCart",
        "available": True,
        "prefix": "ORD",
        "vendorPrompt": (
            "You are the order agent for QuickCart. "
            "A customer has been securely verified via YadaCoin KEL identity. "
            "Collect order preferences ONE question at a time. "
            "Ask about: color / size / variant for each item, "
            "gift wrapping (yes / no), "
            "and delivery speed (standard / express / overnight). "
            "Do not ask about things already in their scope. "
            "\n" + _VENDOR_CHAT_INSTRUCTION
        ),
    },
}


def _gen_confirmation(service: str, seed: str) -> str:
    pfx = VENDOR_REGISTRY.get(service, {}).get("prefix", "SVC")
    h = hashlib.sha256(f"{seed}{service}".encode()).hexdigest()[:6].upper()
    return f"{pfx}-{h}"


# ── Vendor MCP tool registry ──────────────────────────────────────────────────
# Each entry: schemas (OpenAI function-calling format, compatible with Anthropic
# and Ollama with tool-capable models) + mock impl callables.
# Swap impl callables for real MCP server calls / external API requests.


def _flight_check_seats(args: dict, scope: dict) -> dict:
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


def _flight_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("seat_code", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("flight", holder),
        "seat": args.get("seat_code"),
        "meal": args.get("meal_preference", "standard"),
        "extra_baggage": args.get("extra_baggage", False),
        "destination": scope.get("destination"),
        "dates": f"{scope.get('checkin')} → {scope.get('checkout')}",
    }


def _hotel_check_rooms(args: dict, scope: dict) -> dict:
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


def _hotel_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("room_id", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("hotel", holder),
        "room_id": args.get("room_id"),
        "smoking": args.get("smoking", False),
        "special_requests": args.get("special_requests") or "none",
        "checkin": scope.get("checkin"),
        "checkout": scope.get("checkout"),
    }


def _car_check_vehicles(args: dict, scope: dict) -> dict:
    size = args.get("vehicle_size", "standard").lower()
    fleet = {
        "economy": [{"id": "eco-01", "model": "Toyota Corolla", "rate_usd": 45}],
        "compact": [{"id": "cmp-01", "model": "Honda Civic", "rate_usd": 55}],
        "standard": [{"id": "std-01", "model": "Toyota Camry", "rate_usd": 70}],
        "suv": [{"id": "suv-01", "model": "Ford Explorer", "rate_usd": 95}],
        "luxury": [{"id": "lux-01", "model": "BMW 5 Series", "rate_usd": 150}],
    }
    return {"available_vehicles": fleet.get(size, fleet["standard"])}


def _car_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("vehicle_id", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("car", holder),
        "vehicle_id": args.get("vehicle_id"),
        "gps": args.get("gps", False),
        "extra_driver": args.get("extra_driver", False),
        "pickup": scope.get("checkin"),
    }


def _legal_check_templates(args: dict, scope: dict) -> dict:
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
        "terms_of_service": [{"id": "saas-tos-v4", "name": "SaaS ToS", "hours": 6}],
        "privacy_policy": [
            {"id": "gdpr-pp-v3", "name": "GDPR Privacy Policy", "hours": 5}
        ],
    }
    return {"templates": catalog.get(svc, []), "service_type": svc}


def _legal_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("template_id", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("legal", holder),
        "template_id": args.get("template_id"),
        "urgency": args.get("urgency", "standard"),
        "parties": args.get("parties") or [],
    }


def _ecommerce_check_variants(args: dict, scope: dict) -> dict:
    item = (args.get("item_name") or "item")[:4].upper()
    return {
        "item": args.get("item_name"),
        "variants": [
            {"sku": f"{item}-S-BLK", "size": "S", "color": "black", "stock": 5},
            {"sku": f"{item}-M-BLK", "size": "M", "color": "black", "stock": 12},
            {"sku": f"{item}-M-WHT", "size": "M", "color": "white", "stock": 8},
            {"sku": f"{item}-L-BLK", "size": "L", "color": "black", "stock": 3},
        ],
    }


def _ecommerce_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("sku", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("ecommerce", holder),
        "sku": args.get("sku"),
        "gift_wrap": args.get("gift_wrap", False),
        "delivery_speed": args.get("delivery_speed", "standard"),
        "delivery_address": scope.get("deliveryAddress"),
    }


_VENDOR_TOOLS = {
    "flight": {
        "confirm_tool": "confirm_flight_booking",
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
            "check_seat_options": _flight_check_seats,
            "confirm_flight_booking": _flight_confirm,
        },
    },
    "hotel": {
        "confirm_tool": "confirm_hotel_booking",
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
            "check_room_options": _hotel_check_rooms,
            "confirm_hotel_booking": _hotel_confirm,
        },
    },
    "car": {
        "confirm_tool": "confirm_car_rental",
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
                                "enum": [
                                    "economy",
                                    "compact",
                                    "standard",
                                    "suv",
                                    "luxury",
                                ],
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
            "check_vehicle_options": _car_check_vehicles,
            "confirm_car_rental": _car_confirm,
        },
    },
    "legal": {
        "confirm_tool": "confirm_legal_order",
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
            "check_document_templates": _legal_check_templates,
            "confirm_legal_order": _legal_confirm,
        },
    },
    "ecommerce": {
        "confirm_tool": "confirm_order",
        "schemas": [
            {
                "type": "function",
                "function": {
                    "name": "check_item_variants",
                    "description": "Look up available variants (size, color, SKU) for an item.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_name": {"type": "string"},
                        },
                        "required": ["item_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_order",
                    "description": "Place the order once variant and delivery preferences are confirmed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sku": {"type": "string"},
                            "gift_wrap": {"type": "boolean"},
                            "delivery_speed": {
                                "type": "string",
                                "enum": ["standard", "express", "overnight"],
                            },
                        },
                        "required": ["sku", "gift_wrap", "delivery_speed"],
                    },
                },
            },
        ],
        "impl": {
            "check_item_variants": _ecommerce_check_variants,
            "confirm_order": _ecommerce_confirm,
        },
    },
}


class AgentListHandler(BaseHandler):
    """GET /ai-agent-auth/api/agents — return the registered agent types."""

    async def get(self):
        # Strip systemPrompt from the public response (internal detail)
        public = [
            {k: v for k, v in a.items() if k != "systemPrompt"} for a in AGENT_TYPES
        ]
        return self.render_as_json(public)


class AgentChatHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/chat

    Proxies the conversation to a configurable LLM and returns a
    structured JSON response for driving the agent UI.

    Body (JSON)
    -----------
    agent_type : str  (optional — defaults to "travel" for backwards compat)
    messages   : list[{role: "user"|"assistant", content: str}]
    llm        : {
        provider    : "ollama" | "openai" | "anthropic" | "openai_compat"
        model       : str (optional — falls back to sensible defaults)
        api_key     : str (required for openai / anthropic / openai_compat)
        ollama_host : str (ollama only, default "http://localhost:11434")
        base_url    : str (openai_compat only)
      }

    The api_key is supplied by the browser from localStorage and is never
    stored on the YadaCoin server.
    """

    # ── Default models per provider ───────────────────────────────────────────
    _DEFAULT_MODELS = {
        "ollama": "llama3.2",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-haiku-20240307",
        "openai_compat": "gpt-3.5-turbo",
    }

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid json body"})

        messages = body.get("messages", [])
        if not isinstance(messages, list):
            self.set_status(400)
            return self.render_as_json({"error": "messages must be a list"})

        # ── Resolve agent type and its system prompt ──────────────────────── #
        agent_type_id = (body.get("agent_type") or "general").strip()
        agent_type = _AGENT_TYPE_MAP.get(agent_type_id)
        if not agent_type:
            self.set_status(400)
            return self.render_as_json(
                {"error": f"unknown agent_type '{agent_type_id}'"}
            )
        system_prompt = agent_type["systemPrompt"]

        # ── Read per-request LLM config sent from the browser ─────────────── #
        llm_cfg = body.get("llm") or {}
        provider = (llm_cfg.get("provider") or "ollama").lower().strip()
        model = (llm_cfg.get("model") or "").strip() or self._DEFAULT_MODELS.get(
            provider, "gpt-4o-mini"
        )
        api_key = (llm_cfg.get("api_key") or "").strip()
        ollama_host = (
            llm_cfg.get("ollama_host")
            or getattr(self.config, "ollama_host", None)
            or "http://localhost:11434"
        ).rstrip("/")
        base_url = (llm_cfg.get("base_url") or "").rstrip("/")

        full_messages = [{"role": "system", "content": system_prompt}] + messages

        try:
            if provider == "ollama":
                content = await self._call_ollama(ollama_host, model, full_messages)
            elif provider == "openai":
                content = await self._call_openai_compat(
                    "https://api.openai.com/v1", model, api_key, full_messages
                )
            elif provider == "anthropic":
                content = await self._call_anthropic(model, api_key, full_messages)
            elif provider == "openai_compat":
                if not base_url:
                    self.set_status(400)
                    return self.render_as_json(
                        {"error": "base_url required for openai_compat provider"}
                    )
                content = await self._call_openai_compat(
                    base_url, model, api_key, full_messages
                )
            else:
                self.set_status(400)
                return self.render_as_json({"error": f"unknown provider '{provider}'"})
        except Exception as exc:
            self.set_status(502)
            return self.render_as_json(
                {"error": f"LLM unreachable ({provider}): {exc}"}
            )

        # Strip any accidental markdown code fences the model might add
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(content)
            reply = str(parsed.get("reply", ""))
            extracted = parsed.get("extracted") or {}
            complete = bool(parsed.get("complete", False))
        except Exception:
            parsed = {}
            reply = content
            extracted = {}
            complete = False

        detected_agent_type = (
            parsed.get("detected_agent_type", agent_type_id)
            if isinstance(parsed, dict)
            else agent_type_id
        )
        return self.render_as_json(
            {
                "reply": reply,
                "extracted": extracted,
                "complete": complete,
                "detected_agent_type": detected_agent_type,
            }
        )

    async def _call_ollama(self, host: str, model: str, messages: list) -> str:
        client = AsyncHTTPClient()
        req = HTTPRequest(
            url=f"{host}/api/chat",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(
                {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "keep_alive": "10m",  # keep model loaded for 10 minutes after last request
                }
            ),
            request_timeout=480.0,
        )
        resp = await client.fetch(req, raise_error=False)
        if resp.code != 200:
            msg = resp.body.decode("utf-8", errors="replace")
            raise ValueError(f"Ollama {resp.code}: {msg}")
        data = json.loads(resp.body)
        return data["message"]["content"].strip()

    async def _call_openai_compat(
        self, base_url: str, model: str, api_key: str, messages: list
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        client = AsyncHTTPClient()
        req = HTTPRequest(
            url=f"{base_url}/chat/completions",
            method="POST",
            headers=headers,
            body=json.dumps({"model": model, "messages": messages, "temperature": 0.2}),
            request_timeout=120.0,
        )
        resp = await client.fetch(req, raise_error=False)
        if resp.code != 200:
            try:
                err = json.loads(resp.body)
                msg = err.get("error", {}).get("message") or resp.body.decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                msg = resp.body.decode("utf-8", errors="replace")
            raise ValueError(f"OpenAI {resp.code}: {msg}")
        data = json.loads(resp.body)
        return data["choices"][0]["message"]["content"].strip()

    async def _call_anthropic(self, model: str, api_key: str, messages: list) -> str:
        # Anthropic uses a separate system parameter instead of a system role message
        system_content = ""
        filtered = []
        for m in messages:
            if m.get("role") == "system":
                system_content = m.get("content", "")
            else:
                filtered.append(m)

        # Anthropic requires the conversation to start with a user message
        if not filtered or filtered[0].get("role") != "user":
            raise ValueError("Anthropic requires the first message to have role 'user'")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            # Enable prompt caching so the system prompt is cached across turns.
            # The cache_control block on the system message marks it as cacheable.
            "anthropic-beta": "prompt-caching-2024-07-31",
        }
        body: dict = {
            "model": model,
            "max_tokens": 1024,
            "messages": filtered,
        }
        if system_content:
            # Use the extended content-block format so we can attach cache_control.
            body["system"] = [
                {
                    "type": "text",
                    "text": system_content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        client = AsyncHTTPClient()
        req = HTTPRequest(
            url="https://api.anthropic.com/v1/messages",
            method="POST",
            headers=headers,
            body=json.dumps(body),
            request_timeout=120.0,
        )
        resp = await client.fetch(req, raise_error=False)
        if resp.code != 200:
            try:
                err = json.loads(resp.body)
                msg = err.get("error", {}).get("message") or resp.body.decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                msg = resp.body.decode("utf-8", errors="replace")
            raise ValueError(f"Anthropic {resp.code}: {msg}")
        data = json.loads(resp.body)
        return data["content"][0]["text"].strip()

    # ── Tool-calling loops ──────────────────────────────────────────────────── #

    async def _ollama_tool_loop(
        self,
        host: str,
        model: str,
        messages: list,
        tools: list,
        tool_impl: dict,
        confirm_tool: str,
        scope: dict,
        max_rounds: int = 8,
    ):
        """Ollama /api/chat tool-calling loop. Returns (reply, confirmation|None)."""
        client = AsyncHTTPClient()
        confirmation = None
        for _ in range(max_rounds):
            req = HTTPRequest(
                url=f"{host}/api/chat",
                method="POST",
                headers={"Content-Type": "application/json"},
                body=json.dumps(
                    {
                        "model": model,
                        "messages": messages,
                        "tools": tools,
                        "stream": False,
                    }
                ),
                request_timeout=480.0,
            )
            resp = await client.fetch(req, raise_error=False)
            if resp.code != 200:
                raise ValueError(
                    f"Ollama {resp.code}: {resp.body.decode('utf-8', errors='replace')[:200]}"
                )
            data = json.loads(resp.body)
            msg = data.get("message", {})
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return msg.get("content", ""), confirmation
            messages.append(msg)
            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                args = tc["function"].get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                fn = tool_impl.get(fn_name)
                result = (
                    fn(args, scope) if fn else {"error": f"unknown tool: {fn_name}"}
                )
                if fn_name == confirm_tool and result.get("confirmed"):
                    confirmation = result.get("confirmation")
                messages.append({"role": "tool", "content": json.dumps(result)})
        return "Unable to complete the booking at this time.", confirmation

    async def _openai_tool_loop(
        self,
        base_url: str,
        model: str,
        api_key: str,
        messages: list,
        tools: list,
        tool_impl: dict,
        confirm_tool: str,
        scope: dict,
        max_rounds: int = 8,
    ):
        """OpenAI-compat /chat/completions tool-calling loop. Returns (reply, confirmation|None)."""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        client = AsyncHTTPClient()
        confirmation = None
        for _ in range(max_rounds):
            req = HTTPRequest(
                url=f"{base_url}/chat/completions",
                method="POST",
                headers=headers,
                body=json.dumps(
                    {
                        "model": model,
                        "messages": messages,
                        "tools": tools,
                        "tool_choice": "auto",
                        "temperature": 0.3,
                    }
                ),
                request_timeout=120.0,
            )
            resp = await client.fetch(req, raise_error=False)
            if resp.code != 200:
                raise ValueError(
                    f"LLM {resp.code}: {resp.body.decode('utf-8', errors='replace')[:200]}"
                )
            data = json.loads(resp.body)
            choice = data["choices"][0]
            msg = choice["message"]
            finish_reason = choice.get("finish_reason", "stop")
            if finish_reason != "tool_calls" or not msg.get("tool_calls"):
                return msg.get("content") or "", confirmation
            messages.append(msg)
            for tc in msg["tool_calls"]:
                fn_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"].get("arguments", "{}"))
                except Exception:
                    args = {}
                fn = tool_impl.get(fn_name)
                result = (
                    fn(args, scope) if fn else {"error": f"unknown tool: {fn_name}"}
                )
                if fn_name == confirm_tool and result.get("confirmed"):
                    confirmation = result.get("confirmation")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result),
                    }
                )
        return "Unable to complete the booking at this time.", confirmation

    async def _anthropic_tool_loop(
        self,
        model: str,
        api_key: str,
        messages: list,
        tools: list,
        tool_impl: dict,
        confirm_tool: str,
        scope: dict,
        system_content: str = "",
        max_rounds: int = 8,
    ):
        """Anthropic tool-use loop. Returns (reply, confirmation|None)."""
        # Convert OpenAI-format schemas → Anthropic format
        anthropic_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"],
            }
            for t in tools
        ]
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        # Strip system messages; Anthropic takes system separately
        filtered = [m for m in messages if m.get("role") != "system"]
        confirmation = None
        for _ in range(max_rounds):
            body: dict = {
                "model": model,
                "max_tokens": 1024,
                "tools": anthropic_tools,
                "messages": filtered,
            }
            if system_content:
                body["system"] = system_content
            req = HTTPRequest(
                url="https://api.anthropic.com/v1/messages",
                method="POST",
                headers=headers,
                body=json.dumps(body),
                request_timeout=120.0,
            )
            resp = await AsyncHTTPClient().fetch(req, raise_error=False)
            if resp.code != 200:
                raise ValueError(
                    f"Anthropic {resp.code}: {resp.body.decode('utf-8', errors='replace')[:200]}"
                )
            data = json.loads(resp.body)
            stop_reason = data.get("stop_reason")
            content_blocks = data.get("content", [])
            if stop_reason != "tool_use":
                text = "".join(
                    b.get("text", "") for b in content_blocks if b.get("type") == "text"
                )
                return text.strip(), confirmation
            filtered.append({"role": "assistant", "content": content_blocks})
            tool_results = []
            for block in content_blocks:
                if block.get("type") != "tool_use":
                    continue
                fn_name = block["name"]
                args = block.get("input") or {}
                fn = tool_impl.get(fn_name)
                result = (
                    fn(args, scope) if fn else {"error": f"unknown tool: {fn_name}"}
                )
                if fn_name == confirm_tool and result.get("confirmed"):
                    confirmation = result.get("confirmation")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": json.dumps(result),
                    }
                )
            filtered.append({"role": "user", "content": tool_results})
        return "Unable to complete the booking at this time.", confirmation

    async def _run_tool_loop(
        self,
        provider: str,
        model: str,
        api_key: str,
        ollama_host: str,
        base_url: str,
        system_prompt: str,
        messages: list,
        vendor_tools: dict,
        scope: dict,
        max_rounds: int = 8,
    ):
        """
        Dispatch to the appropriate provider tool loop.
        Returns (reply: str, confirmation: str|None).
        """
        tools = vendor_tools["schemas"]
        tool_impl = vendor_tools["impl"]
        confirm_tool = vendor_tools.get("confirm_tool", "")
        full_messages = [{"role": "system", "content": system_prompt}] + list(messages)

        if provider == "ollama":
            return await self._ollama_tool_loop(
                ollama_host,
                model,
                full_messages,
                tools,
                tool_impl,
                confirm_tool,
                scope,
                max_rounds,
            )
        elif provider in ("openai", "openai_compat"):
            base = "https://api.openai.com/v1" if provider == "openai" else base_url
            return await self._openai_tool_loop(
                base,
                model,
                api_key,
                full_messages,
                tools,
                tool_impl,
                confirm_tool,
                scope,
                max_rounds,
            )
        elif provider == "anthropic":
            filtered = [m for m in full_messages if m.get("role") != "system"]
            return await self._anthropic_tool_loop(
                model,
                api_key,
                filtered,
                tools,
                tool_impl,
                confirm_tool,
                scope,
                system_content=system_prompt,
                max_rounds=max_rounds,
            )
        else:
            raise ValueError(f"unknown provider '{provider}'")


class AgentAuthAppHandler(BaseHandler):
    """GET /ai-agent-auth[/.*] — serve the Vue SPA shell."""

    _DIST = os.path.join(os.path.dirname(__file__), "dist")

    async def get(self):
        index = os.path.join(self._DIST, "index.html")
        if not os.path.exists(index):
            self.set_status(503)
            return self.finish(
                "<pre>SPA not built yet.\n"
                "Run:  cd plugins/yadaaiagent/ui && npm run build</pre>"
            )
        with open(index, "rb") as fh:
            self.set_header("Content-Type", "text/html; charset=utf-8")
            return self.finish(fh.read())


class AgentChallengeHandler(BaseHandler):
    """
    GET /ai-agent-auth/api/challenge?public_key=<hex>

    Returns a short-lived stateless HMAC-SHA256 challenge tied to the
    supplied public key.  Valid for the current 30-second window plus the
    previous one (up to ~60 s total).  The client must sign
    ``sha256(challenge_utf8_bytes)`` with the provisioned secp256k1 key and
    present the compact signature to the travel booking endpoint.
    """

    async def get(self):
        public_key = (self.get_argument("public_key", "") or "").strip()
        if not public_key:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "public_key query parameter required"}
            )
        return self.render_as_json(_validator.make_challenge(public_key))


class TravelBookingHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/travel

    Mock travel-booking service that authenticates the caller via a
    KEL-backed challenge-response.  The private key is NEVER sent to this
    server — the caller signs the challenge client-side and submits only the
    public key + signature.

    Body (JSON)
    -----------
    public_key  : hex compressed secp256k1 public key (the provisioned agent key)
    challenge   : hex string received from GET /api/challenge
    signature   : hex compact secp256k1 signature of sha256(challenge_utf8)
    services    : list[str]   e.g. ["hotel", "flight", "car"]
    dest        : str         destination
    checkin     : str         check-in date
    checkout    : str         check-out date

    Auth flow
    ---------
    1. Validate HMAC challenge (stateless, 30-second windows).
    2. Verify secp256k1 signature against public_key.
    3. Build KEL for public_key.
    4. Revocation check: public_key address must NOT appear as public_key_hash
       in any existing KEL entry.
    5. Pre-commitment check: kel[-1].prerotated_key_hash must equal address.
    6. Read authorised scope from ``relationship`` field of the latest KEL entry.
    7. Book each requested service if it is within scope and available.

    HTTP status codes
    -----------------
    200  All requested services booked successfully.
    206  Partial: some services booked, others unavailable or out of stock.
    401  Challenge expired/invalid or signature verification failed.
    403  KEL pre-commitment mismatch, revoked key, or scope violation.
    422  Request understood but nothing could be fulfilled (all unavailable).
    """

    async def post(self):
        pass

        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )

        public_key = (body.get("public_key") or "").strip()
        challenge = (body.get("challenge") or "").strip()
        signature = (body.get("signature") or "").strip()
        services = [s.lower() for s in (body.get("services") or [])]
        dest = (body.get("dest") or "").strip()

        # ── Authenticate: challenge, sig, KEL, revocation, pre-commitment ─── #
        try:
            auth = await _validator.validate(public_key, challenge, signature)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"status": False, "message": str(exc)})

        # ── Destination scope check ────────────────────────────────────────── #
        try:
            AgentAuthValidator.enforce_scope(auth, dest=dest)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json(
                {"status": False, "message": str(exc), "scope": auth.scope}
            )

        scope_services = [s.lower() for s in auth.scope.get("services", [])]

        # ── Mock booking ────────────────────────────────────────────────────── #
        completed = []
        failed = []

        for svc in services:
            inv = _MOCK_INVENTORY.get(svc)
            if scope_services and svc not in scope_services:
                failed.append(
                    {
                        "service": svc,
                        "reason": "not_authorized",
                        "message": f"'{svc}' is not in the authorised scope",
                    }
                )
            elif inv is None:
                failed.append(
                    {
                        "service": svc,
                        "reason": "unknown_service",
                        "message": f"'{svc}' is not a service this provider offers",
                    }
                )
            elif not inv["available"]:
                failed.append(
                    {
                        "service": svc,
                        "reason": "no_availability",
                        "message": inv.get("reason", f"No {svc} available"),
                    }
                )
            else:
                completed.append(
                    {
                        "service": svc,
                        "confirmation": _gen_confirmation(svc, auth.address),
                    }
                )

        n_ok = len(completed)
        n_fail = len(failed)

        if n_ok == 0:
            scope_fail_count = sum(1 for f in failed if f["reason"] == "not_authorized")
            if scope_fail_count == n_fail:
                self.set_status(403)
            else:
                self.set_status(422)
        elif n_fail > 0:
            self.set_status(206)
        else:
            self.set_status(200)

        return self.render_as_json(
            {
                "status": n_ok > 0,
                "completed": completed,
                "failed": failed,
                "scope_used": auth.scope,
                "authorized_address": auth.address,
                "kel_depth": len(auth.kel),
                "kel_txid": auth.kel_txid,
            }
        )


# ── Per-vendor VP-based handlers ──────────────────────────────────────────────


class VendorBaseHandler(BaseHandler):
    """
    Base class for individual vendor booking endpoints.

    Subclasses set ``vendor_service`` to one of the keys in VENDOR_REGISTRY.
    All auth, scope checking, and booking logic is handled here.

    Body (JSON)
    -----------
    public_key : hex compressed secp256k1 public key
    challenge  : hex string from GET /api/vendor/<service>/challenge
    vp         : W3C VP object  {type, holder, verifiableCredential, proof}
    """

    vendor_service: str = ""

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )

        public_key = (body.get("public_key") or "").strip()
        challenge = (body.get("challenge") or "").strip()
        vp = body.get("vp")

        if not public_key or not challenge or not vp:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "public_key, challenge, and vp are required",
                }
            )

        try:
            auth = await _validator.validate_vp(public_key, challenge, vp)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"status": False, "message": str(exc)})

        try:
            AgentAuthValidator.enforce_scope(auth, services=[self.vendor_service])
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json(
                {"status": False, "message": str(exc), "scope": auth.scope}
            )

        vendor = VENDOR_REGISTRY.get(self.vendor_service, {})
        if not vendor.get("available", False):
            self.set_status(422)
            return self.render_as_json(
                {
                    "status": False,
                    "service": self.vendor_service,
                    "message": f"No {self.vendor_service} available at this time",
                }
            )

        confirmation = _gen_confirmation(self.vendor_service, auth.address)
        return self.render_as_json(
            {
                "status": True,
                "service": self.vendor_service,
                "vendor": vendor.get("name", self.vendor_service),
                "confirmation": confirmation,
                "authorized_address": auth.address,
                "kel_depth": len(auth.kel),
                "kel_txid": auth.kel_txid,
                "payment_method": auth.scope.get("paymentMethod") or {},
            }
        )


class VendorChatBaseHandler(AgentChatHandler):
    """
    POST /ai-agent-auth/api/vendor/<svc>/chat

    LLM-powered vendor follow-up conversation.  After the VP has been validated
    the vendor's LLM asks the customer clarifying questions (bed type, seat
    preference, etc.) before issuing a confirmation.

    Body (JSON)
    -----------
    public_key : hex compressed secp256k1 public key
    challenge  : hex string from GET /api/vendor/<service>/challenge
    vp         : W3C VP object (signed)
    messages   : list[{role, content}]  — conversation history (no system msg)
    llm        : same LLM config block as /api/chat
    """

    vendor_service: str = ""

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )

        public_key = (body.get("public_key") or "").strip()
        challenge = (body.get("challenge") or "").strip()
        vp = body.get("vp")
        messages = body.get("messages") or []
        llm_cfg = body.get("llm") or {}

        if not public_key or not challenge or not vp:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "public_key, challenge, and vp are required",
                }
            )

        try:
            auth = await _validator.validate_vp(public_key, challenge, vp)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"status": False, "message": str(exc)})

        try:
            AgentAuthValidator.enforce_scope(auth, services=[self.vendor_service])
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json(
                {"status": False, "message": str(exc), "scope": auth.scope}
            )

        vendor = VENDOR_REGISTRY.get(self.vendor_service, {})
        if not vendor.get("available", False):
            self.set_status(422)
            return self.render_as_json(
                {
                    "status": False,
                    "service": self.vendor_service,
                    "message": f"No {self.vendor_service} available at this time",
                }
            )

        # LLM config
        provider = (llm_cfg.get("provider") or "ollama").lower().strip()
        model = (llm_cfg.get("model") or "").strip() or self._DEFAULT_MODELS.get(
            provider, "gpt-4o-mini"
        )
        api_key = (llm_cfg.get("api_key") or "").strip()
        ollama_host = (
            llm_cfg.get("ollama_host")
            or getattr(self.config, "ollama_host", None)
            or "http://localhost:11434"
        ).rstrip("/")
        base_url = (llm_cfg.get("base_url") or "").rstrip("/")

        vendor_tools = _VENDOR_TOOLS.get(self.vendor_service)

        if vendor_tools:
            # ── MCP tool-calling mode ──────────────────────────────────────── #
            scope_ctx = json.dumps(auth.scope, separators=(",", ":"))
            system_prompt = (
                f"You are the reservations agent for {vendor['name']}. "
                f"The customer has been verified via YadaCoin KEL identity. "
                f"Use the available tools to look up options and confirm the booking. "
                f"Ask ONE question at a time. Be warm and professional. "
                f"Customer's authorized scope: {scope_ctx}"
            )
            try:
                reply, confirmation = await self._run_tool_loop(
                    provider,
                    model,
                    api_key,
                    ollama_host,
                    base_url,
                    system_prompt,
                    messages,
                    vendor_tools,
                    auth.scope,
                )
            except Exception as exc:
                self.set_status(502)
                return self.render_as_json(
                    {"status": False, "message": f"LLM unreachable ({provider}): {exc}"}
                )
            complete = confirmation is not None
        else:
            # ── JSON fallback mode ─────────────────────────────────────────── #
            scope_ctx = json.dumps(auth.scope, separators=(",", ":"))
            base_prompt = vendor.get(
                "vendorPrompt",
                (
                    "You are a booking agent. Collect preferences ONE question at a time. "
                    'ALWAYS respond with ONLY valid JSON: {"reply": "...", "complete": false}'
                ),
            )
            system_prompt = f"{base_prompt}\n\nCustomer's authorized scope: {scope_ctx}"
            full_messages = [{"role": "system", "content": system_prompt}] + messages
            try:
                if provider == "ollama":
                    content = await self._call_ollama(ollama_host, model, full_messages)
                elif provider == "openai":
                    content = await self._call_openai_compat(
                        "https://api.openai.com/v1", model, api_key, full_messages
                    )
                elif provider == "anthropic":
                    content = await self._call_anthropic(model, api_key, full_messages)
                elif provider == "openai_compat":
                    if not base_url:
                        self.set_status(400)
                        return self.render_as_json(
                            {"error": "base_url required for openai_compat provider"}
                        )
                    content = await self._call_openai_compat(
                        base_url, model, api_key, full_messages
                    )
                else:
                    self.set_status(400)
                    return self.render_as_json(
                        {"error": f"unknown provider '{provider}'"}
                    )
            except Exception as exc:
                self.set_status(502)
                return self.render_as_json(
                    {"status": False, "message": f"LLM unreachable ({provider}): {exc}"}
                )
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            try:
                parsed = json.loads(content)
                reply = str(parsed.get("reply", ""))
                complete = bool(parsed.get("complete", False))
            except Exception:
                reply = content
                complete = False
            confirmation = (
                _gen_confirmation(self.vendor_service, auth.address)
                if complete
                else None
            )

        result = {
            "status": True,
            "reply": reply,
            "complete": complete,
            "service": self.vendor_service,
            "vendor": vendor.get("name", self.vendor_service),
        }
        if confirmation:
            result["confirmation"] = confirmation

        return self.render_as_json(result)


# ── Dynamically generate a VendorHandler subclass for every registered service ─
# Adding a new entry to VENDOR_REGISTRY automatically creates its handler.

_VENDOR_HANDLERS: dict = {}
_VENDOR_CHAT_HANDLERS: dict = {}
for _svc_id in VENDOR_REGISTRY:
    _VENDOR_HANDLERS[_svc_id] = type(
        f"{_svc_id.capitalize()}VendorHandler",
        (VendorBaseHandler,),
        {"vendor_service": _svc_id},
    )
    _VENDOR_CHAT_HANDLERS[_svc_id] = type(
        f"{_svc_id.capitalize()}VendorChatHandler",
        (VendorChatBaseHandler,),
        {"vendor_service": _svc_id},
    )

# Named aliases for backwards compat
FlightVendorHandler = _VENDOR_HANDLERS["flight"]
HotelVendorHandler = _VENDOR_HANDLERS["hotel"]
CarVendorHandler = _VENDOR_HANDLERS["car"]


# ── Route table ───────────────────────────────────────────────────────────────
# Vendor challenge + booking routes are generated from VENDOR_REGISTRY.

_vendor_routes = []
for _svc_id, _handler in _VENDOR_HANDLERS.items():
    _vendor_routes += [
        (rf"/ai-agent-auth/api/vendor/{_svc_id}/challenge", AgentChallengeHandler),
        (rf"/ai-agent-auth/api/vendor/{_svc_id}/chat", _VENDOR_CHAT_HANDLERS[_svc_id]),
        (rf"/ai-agent-auth/api/vendor/{_svc_id}", _handler),
    ]

HANDLERS = [
    # SPA shell — catch-all for client-side routes (must be last)
    (
        r"/ai-agent-auth/assets/(.*)",
        tornado.web.StaticFileHandler,
        {"path": os.path.join(os.path.dirname(__file__), "dist", "assets")},
    ),
    (r"/ai-agent-auth", AgentAuthAppHandler),
    (r"/ai-agent-auth/", AgentAuthAppHandler),
    (r"/ai-agent-auth/api/agents", AgentListHandler),
    (r"/ai-agent-auth/api/chat", AgentChatHandler),
    (r"/ai-agent-auth/api/challenge", AgentChallengeHandler),
    (r"/ai-agent-auth/api/travel", TravelBookingHandler),  # legacy endpoint
    *_vendor_routes,
]
