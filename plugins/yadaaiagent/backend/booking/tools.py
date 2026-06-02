"""booking_tools.py — Booking-credential helpers, vendor registry, and tool schemas."""
import hashlib
import os

_UI_HINT_SUFFIX = (
    '\n\nFor EVERY response you MUST include a top-level "choices" field in your JSON.\n'
    "choices schema:\n"
    '  "choices": [   <-- array of input groups, or empty [] when nothing to collect\n'
    "    {\n"
    '      "id": "snake_case_identifier",\n'
    '      "choice_text": "The question or prompt shown to the user",\n'
    '      "multi": false,          <-- true = checkboxes, false = radio buttons\n'
    '      "options": [             <-- for select-type inputs\n'
    '        {"id": "opt_id", "text": "Display label"}\n'
    "      ]\n"
    "      // OR for free-text / date inputs, omit options and add:\n"
    '      "input_type": "text" | "date"\n'
    "    }\n"
    "  ]\n"
    "Rules:\n"
    "- Add one entry per question you are asking right now.\n"
    "- Use options[] when asking the user to pick from a finite set (e.g. seat type, room type, yes/no).\n"
    "- Use input_type='date' for check-in, check-out, departure, return dates.\n"
    "- Use input_type='text' for open text answers such as destination or special requests.\n"
    "- Set choices=[] (empty array) for purely conversational turns where no input is needed.\n"
    "- Never mix options[] and input_type in the same entry."
)

_VENDOR_CHAT_INSTRUCTION = (
    "ALWAYS respond with ONLY a valid JSON object — no markdown, no extra text.\n"
    "The JSON MUST include: reply, complete, exit_vendor, and choices (see schema below).\n"
    'Example: {"reply": "...", "complete": false, "exit_vendor": false, "choices": []}\n'
    "choices follows the same schema described above (array of choice group objects).\n"
    "Set complete=true ONLY when you have received all needed answers and are "
    "ready to confirm the booking. When setting complete=true your reply must "
    "include a friendly booking confirmation message.\n"
    "Set exit_vendor=true (and complete=false) ONLY if the user clearly wants to stop "
    "this booking and switch to a completely different topic or service "
    "(e.g. therapy, travel, shopping, legal help). "
    "In that case reply with a brief acknowledgement such as "
    "'Sure, let me hand you back to the main assistant.'"
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
    "train": {
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
            "\n" + _VENDOR_CHAT_INSTRUCTION
        ),
    },
    "ship": {
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
    "therapist": {
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
    },
}


def _gen_confirmation(service: str, seed: str) -> str:
    pfx = VENDOR_REGISTRY.get(service, {}).get("prefix", "SVC")
    h = hashlib.sha256(f"{seed}{service}".encode()).hexdigest()[:6].upper()
    return f"{pfx}-{h}"


def _did_web_id(config) -> str:
    """Derive a did:web identifier from the node's wallet_host_port."""
    from urllib.parse import urlparse

    parsed = urlparse(getattr(config, "wallet_host_port", "") or "")
    host = parsed.hostname or ""
    port = parsed.port
    if port and port not in (80, 443):
        return f"did:web:{host}%3A{port}"
    return f"did:web:{host}"


def _gen_booking_credential(
    service: str,
    holder_address: str,
    scope: dict,
    confirmation: str,
    vendor_name: str,
    booking_details=None,
    config=None,
) -> dict:
    """Return a signed W3C VC 2.0 Verifiable Credential for a completed booking."""
    import datetime

    from plugins.yadaaiagent.vc_support import BOOKING_V1_CONTEXT_URL, sign_credential

    subject = {
        "id": f"did:yadakel:{holder_address}",
        "service": service,
        "vendor": vendor_name,
        "confirmation": confirmation,
        "scope": scope,
    }
    if booking_details:
        # Strip internal fields; keep the human-readable booking data
        skip = {"confirmed", "confirmation"}
        subject["bookingDetails"] = {
            k: v for k, v in booking_details.items() if k not in skip
        }

    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Use did:web when config is present (resolvable); fall back to did:yadakel
    if config is not None:
        issuer_did = _did_web_id(config)
    else:
        issuer_did = f"did:yadakel:{service}"

    credential = {
        "@context": [
            "https://www.w3.org/ns/credentials/v2",
            BOOKING_V1_CONTEXT_URL,
        ],
        "id": f"urn:yadakel:booking:{confirmation}",
        "type": ["VerifiableCredential", "BookingConfirmationCredential"],
        "issuer": {
            "id": issuer_did,
            "name": vendor_name,
        },
        "validFrom": now,
        "credentialSubject": subject,
    }

    if config is not None:
        try:
            credential["proof"] = {
                "type": "DataIntegrityProof",
                "cryptosuite": "ecdsa-secp256k1-2019",
                "created": now,
                "verificationMethod": f"{issuer_did}#key-1",
                "proofPurpose": "assertionMethod",
            }
            credential = sign_credential(credential, config.private_key)
        except Exception:
            credential.pop("proof", None)  # remove incomplete proof on failure

    return credential


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


def _train_check_seats(args: dict, scope: dict) -> dict:
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


def _train_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("seat_code", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("train", holder),
        "seat": args.get("seat_code"),
        "cabin_class": args.get("cabin_class", "standard"),
        "large_luggage": args.get("large_luggage", False),
        "destination": scope.get("destination"),
        "dates": f"{scope.get('checkin')} → {scope.get('checkout')}",
    }


def _ship_check_cabins(args: dict, scope: dict) -> dict:
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


def _ship_confirm(args: dict, scope: dict) -> dict:
    holder = scope.get("holder", args.get("cabin_id", ""))
    return {
        "confirmed": True,
        "confirmation": _gen_confirmation("ship", holder),
        "cabin_id": args.get("cabin_id"),
        "dining_seating": args.get("dining_seating", "anytime"),
        "shore_excursions": args.get("shore_excursions", False),
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
    "train": {
        "confirm_tool": "confirm_train_booking",
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
            "check_train_seat_options": _train_check_seats,
            "confirm_train_booking": _train_confirm,
        },
    },
    "ship": {
        "confirm_tool": "confirm_ship_booking",
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
            "check_cabin_options": _ship_check_cabins,
            "confirm_ship_booking": _ship_confirm,
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
    "therapist": {
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
        # Set THERAPIST_MCP_ENDPOINT env-var to use a live MCP server instead of the mock impl.
        # Example: export THERAPIST_MCP_ENDPOINT=http://localhost:8010/mcp
        # Run the server: python plugins/yadaaiagent/mcp_server_therapist.py
        "mcp_endpoint": os.environ.get("THERAPIST_MCP_ENDPOINT", ""),
    },
}
