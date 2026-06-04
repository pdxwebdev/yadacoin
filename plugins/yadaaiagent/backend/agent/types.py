"""agent_types.py — AGENT_TYPES registry, on-chain agent helpers, search, and prompt builders."""
import json
import re as _re
import urllib.parse as _urlparse

from tornado.httpclient import AsyncHTTPClient, HTTPRequest

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
            '- "therapy": user mentions needing therapy, a therapist, mental health support, '
            "counselling, or help with OCD, ADD, ADHD, anxiety, depression, or stress\n"
            "Keep detected_agent_type as 'general' for greetings, vague questions, or topics "
            "that don't clearly fit the above.\n"
            '- "agent_registration": user wants to register or list their AI agent on the blockchain, '
            "create a new agent entry, add an agent to the on-chain registry, or asks how to make "
            "their agent discoverable. Examples: 'register my agent', 'add my AI to the blockchain', "
            "'I want to list my agent'\n"
            '- "wallet_agent": user asks about their balance, wallet funds, YDA amount, '
            "transaction history, pending transactions, sending coins, transferring YDA, "
            "or wrapping/unwrapping tokens. "
            "Examples: 'what is my balance', 'show my transactions', 'send 5 YDA to ...'\n"
            "Keep detected_agent_type as 'general' for greetings, vague questions, or topics "
            "that don't clearly fit the above.\n"
            "complete MUST always be false."
        ),
    },
    {
        "id": "travel",
        "label": "Travel Booking",
        "description": "Book flights, trains, ships, hotels, and car rentals with KEL-backed agent credentials.",
        "icon": "✈️",
        "routing_hint": (
            "user mentions wanting to go somewhere, visit a destination, travel, "
            "take a trip, book a flight/train/ship/hotel/car, or asks about travel arrangements. "
            "Examples: 'I want to go to Mexico', 'I'm planning a trip to Paris', 'book me a flight', 'book a train to Berlin', 'cruise to the Bahamas'"
        ),
        "authorizationType": "TravelBookingAuthorization",
        "fields": [
            {"key": "destination", "label": "Destination", "type": "text"},
            {"key": "checkin", "label": "Check-in", "type": "text"},
            {"key": "checkout", "label": "Check-out", "type": "text"},
            {
                "key": "services",
                "label": "Services",
                "type": "multiselect",
                "options": ["hotel", "flight", "train", "ship", "car"],
            },
        ],
        "services": ["hotel", "flight", "train", "ship", "car"],
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
            '    "services": ["hotel","flight","train","ship","car"] subset or null\n'
            "  },\n"
            '  "complete": false,\n'
            '  "detected_agent_type": "travel"\n'
            "}\n"
            "Rules:\n"
            "- Only use service values: hotel, flight, train, ship, car\n"
            '- If the user says "all": services=["hotel","flight","train","ship","car"]\n'
            "- complete MUST be false unless ALL FOUR fields are known\n"
            '- For date ranges like "May 10-16": checkin="May 10", checkout="May 16"\n'
            "- When complete=true: summarise all details and say the operator will approve\n"
            "- If the user clearly wants something other than travel (e.g. therapy, legal help, shopping), set detected_agent_type to 'general'"
        ),
    },
    {
        "id": "legal",
        "label": "Legal Services",
        "description": "Request legal document drafting and review with scoped agent credentials.",
        "icon": "⚖️",
        "routing_hint": (
            "user explicitly asks to DRAFT, REVIEW, or get help with a legal document, "
            "contract, NDA, terms of service, or privacy policy. "
            "Examples: 'draft me an NDA', 'review this contract', 'I need a privacy policy'"
        ),
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
            '  "complete": false,\n'
            '  "detected_agent_type": "legal"\n'
            "}\n"
            "complete=true only when ALL THREE fields are known.\n"
            "If the user clearly wants something other than legal services, set detected_agent_type to 'general'."
        ),
    },
    {
        "id": "ecommerce",
        "label": "E-Commerce",
        "description": "Authorise an AI agent to place orders on your behalf with scoped spending limits.",
        "icon": "🛒",
        "routing_hint": (
            "user explicitly asks to ORDER, BUY, or purchase a physical product. "
            "Examples: 'order me some shoes', 'buy this item', 'I want to purchase something'"
        ),
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
            '  "complete": false,\n'
            '  "detected_agent_type": "ecommerce"\n'
            "}\n"
            "complete=true only when ALL THREE fields are known.\n"
            "If the user clearly wants something other than shopping/orders, set detected_agent_type to 'general'."
        ),
    },
    {
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
    },
    {
        "id": "agent_registration",
        "label": "Register AI Agent",
        "description": "Register your AI agent on the YadaCoin blockchain so others can discover it automatically.",
        "icon": "📡",
        "authorizationType": "AgentRegistration",
        "fields": [
            {"key": "label", "label": "Agent Label", "type": "text"},
            {"key": "description", "label": "Description", "type": "text"},
            {"key": "agent_type", "label": "Agent Type", "type": "text"},
            {"key": "capabilities", "label": "Capabilities", "type": "text"},
            {"key": "endpoint_url", "label": "Endpoint URL", "type": "text"},
            {"key": "icon", "label": "Icon", "type": "text"},
        ],
        "services": [],
        "systemPrompt": (
            "You are an AI agent registration assistant for YadaCoin. Your job is to collect "
            "the details needed to register an AI agent on the blockchain so others can discover it.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "label": "agent name/label or null",\n'
            '    "description": "what the agent does or null",\n'
            '    "agent_type": "general|travel|legal|ecommerce or null",\n'
            '    "capabilities": "comma-separated keyword list or null",\n'
            '    "endpoint_url": "full URL or null",\n'
            '    "icon": "single emoji or null"\n'
            "  },\n"
            '  "complete": false\n'
            "}\n"
            "Rules:\n"
            "- agent_type MUST be one of: general, travel, legal, ecommerce\n"
            "- capabilities should be a comma-separated list of intent keywords (e.g. 'travel, flight, hotel')\n"
            "- endpoint_url must be a valid URL starting with http:// or https://\n"
            "- If the user doesn't provide an icon, suggest '🤖' as default\n"
            "- complete=true only when label, agent_type, capabilities, AND endpoint_url are all known\n"
            "- When complete=true, summarise all the details clearly and tell the operator "
            "they can approve to broadcast the registration on-chain\n"
            "- If the user clearly wants something other than registering an agent, set detected_agent_type to 'general'"
        ),
    },
    {
        "id": "wallet_agent",
        "label": "Wallet Assistant",
        "description": "Check balance, view on-chain and pending transaction history, send YDA, and wrap YDA to other chains.",
        "icon": "💰",
        "routing_hint": (
            "user asks about their balance, wallet, YDA amount, funds, transactions, "
            "transaction history, pending transactions, sending coins, transferring YDA, "
            "or wrapping/unwrapping tokens. "
            "Examples: 'what is my balance', 'show my transactions', 'send 5 YDA to ...', 'wrap 10 YDA to 0x...'"
        ),
        "authorizationType": "WalletAuthorization",
        "fields": [
            {
                "key": "action",
                "label": "Action",
                "type": "select",
                "options": ["send", "balance", "history", "pending", "wrap"],
            },
            {"key": "to_address", "label": "Recipient Address", "type": "text"},
            {"key": "amount", "label": "Amount (YDA)", "type": "number"},
            {
                "key": "eth_address",
                "label": "Ethereum Address (for wrap)",
                "type": "text",
            },
        ],
        "services": ["wallet"],
        "systemPrompt": (
            "You are a YadaCoin wallet assistant. You help users check their balance, "
            "view transaction history, send YDA, and wrap YDA to other chains.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "action": "send|get_balance|get_transactions|get_pending|wrap or null",\n'
            '    "to_address": "recipient YDA address or null",\n'
            '    "amount": number or null,\n'
            '    "eth_address": "0x Ethereum address for wrap, or null"\n'
            "  },\n"
            '  "complete": false,\n'
            '  "detected_agent_type": "wallet_agent"\n'
            "}\n"
            "Rules:\n"
            "- For balance requests: set action='get_balance', complete=false — "
            "the system will fetch and display the balance automatically.\n"
            "- For transaction history requests: set action='get_transactions', complete=false.\n"
            "- For pending transactions: set action='get_pending', complete=false.\n"
            "- For wrapping YDA: set action='wrap'. Collect amount AND eth_address (0x Ethereum address). "
            "The wrap sends YDA to the bridge address with the Ethereum address in the relationship field. "
            "Ask for confirmation before setting complete=true. "
            "Set complete=true only when BOTH amount and eth_address are known AND the user has confirmed.\n"
            "- For send: collect to_address AND amount. "
            "Ask for confirmation before setting complete=true. "
            "Set complete=true only when BOTH fields are known AND the user has confirmed.\n"
            "- NEVER ask for private keys, seeds, or passwords.\n"
            "- If the user wants something other than wallet operations, "
            "set detected_agent_type to 'general'."
        ),
    },
    {
        "id": "node_config",
        "label": "Node Configuration",
        "description": "Change a setting in the active node config.json and restart the node.",
        "icon": "⚙️",
        "routing_hint": (
            "user wants to change a node setting, update a config value, modify node configuration, "
            "or asks about changing combined_address, pool settings, peer limits, or any node parameter. "
            "Examples: 'change my combined address', 'update pool_take', 'set max_miners to 50'"
        ),
        "authorizationType": "NodeConfigAuthorization",
        "fields": [
            {"key": "config_key", "label": "Setting Name", "type": "text"},
            {"key": "new_value", "label": "New Value", "type": "text"},
        ],
        "services": ["NodeConfigAuthorization"],
        "systemPrompt": (
            "You are a YadaCoin node configuration assistant. "
            "Help the user change a setting in their active node config.json. "
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "config_key": "setting name or null",\n'
            '    "new_value": "new value (as a string) or null",\n'
            '    "confirmed": false\n'
            "  },\n"
            '  "complete": false,\n'
            '  "detected_agent_type": "node_config"\n'
            "}\n"
            "Allowed settings (from README):\n"
            "- combined_address (string): Wallet address to consolidate transactions. Default: node address\n"
            "- credits_per_share (integer): Credits earned per mining share. Default: 5\n"
            "- shares_required (boolean): Require shares to use node apps. Default: false\n"
            "- pool_payout (boolean): Enable pool payouts to miners. Default: false\n"
            "- pool_take (decimal): Pool operator cut as decimal (0.01 = 1%). Default: 0.01\n"
            "- payout_frequency (integer): Blocks between payouts. Default: 6\n"
            "- max_miners (integer): Max concurrent miners. Default: 100\n"
            "- max_peers (integer): Max peers that can connect. Default: 20\n"
            "- pool_diff (integer): Pool share difficulty. Default: 100000\n"
            "- stratum_pool_port (integer): Stratum pool port. Default: 3333\n"
            "- transactions_combining_wait (integer): Seconds before combining UTXOs. Default: 3600\n"
            "- restrict_graph_api (boolean): Restrict graph API access. Default: false\n"
            "- web_jwt_expiry (integer): JWT validity in seconds. Default: 23040\n"
            "- peers_wait (integer): Seconds between peer reconnect attempts. Default: 30\n"
            "- status_wait (integer): Seconds between status prints. Default: 10\n"
            "- block_checker_wait (integer): Seconds between block height checks. Default: 1\n"
            "- message_sender_wait (integer): Seconds between message retries. Default: 40\n"
            "- pool_payer_wait (integer): Seconds between payout runs. Default: 110\n"
            "- cache_validator_wait (integer): Seconds between cache validation. Default: 3550\n"
            "- mempool_cleaner_wait (integer): Seconds between mempool cleans. Default: 1200\n"
            "- nonce_processor_wait (integer): Seconds between nonce queue checks. Default: 1\n"
            "- mongo_query_timeout (integer): Max MongoDB query time in ms. Default: 30000\n"
            "- http_request_timeout (integer): Max HTTP request time in ms. Default: 3000\n"
            "- masternode_fee_minimum (integer): Min YDA fee for masternode services. Default: 1\n"
            "- balance_min_utxo (integer): Min UTXO amount to include in balance. Default: 1\n"
            "- activate_peerjs (boolean): Activate PeerJS p2p broker. Default: false\n"
            "- extended_status (boolean): Enable extended status. Default: false\n"
            "- log_health_status (boolean): Log health status. Default: false\n"
            "- docker_debug (boolean): Log docker resource usage. Default: false\n"
            "- asyncio_debug (boolean): Log slow asyncio tasks. Default: false\n"
            "- network_seeds (list): List of seed node addresses.\n"
            "- network_service_providers (list): List of service provider node addresses.\n"
            "- network_seed_gateways (list): List of seed gateway node addresses.\n"
            "- serve_host (string): Host address the node listens on for inbound peer connections. Default: 0.0.0.0\n"
            "- serve_port (integer): Port the node listens on for inbound peer connections. Default: 8005\n"
            "- peer_host (string): Public hostname or IP this node advertises to peers. Default: node's public IP\n"
            "- peer_port (integer): Port this node advertises to peers. Default: 8004\n"
            "Rules:\n"
            "- Only allow settings from the list above. Refuse requests for private_key, seed, etc.\n"
            "- For list-type settings (network_seeds, network_service_providers, "
            "  network_seed_gateways): new_value must be a valid JSON array string containing "
            "  ALL entries for the list (not just the new item to add). If the user wants to "
            "  ADD an entry, include the new entry in the array and ask the user to confirm "
            "  it's the complete new list.\n"
            "- Ask for confirmation before setting complete=true\n"
            "- confirmed must be true (the user explicitly agreed) before complete=true\n"
            "- complete=true only when config_key, new_value, AND confirmed=true are all set\n"
            "- When complete=true, set reply to a brief message like 'Applying that change now.' "
            "  Do NOT mention key rotation, authorization, or KEL transactions in your replies.\n"
            "- If the user wants something other than config changes, set detected_agent_type to 'general'"
        ),
    },
    {
        "id": "github",
        "label": "GitHub",
        "description": "Interact with GitHub: list repos, view issues/PRs, create issues, check CI status.",
        "icon": "🐙",
        "routing_hint": (
            "user asks about GitHub repos, issues, pull requests, CI status, commits, branches, "
            "code search, or wants to create/close an issue on GitHub. "
            "Examples: 'show my repos', 'list open issues in myrepo', 'create an issue', "
            "'what PRs are open', 'check my GitHub notifications'"
        ),
        "authorizationType": None,
        "fields": [],
        "services": ["github"],
        "systemPrompt": (
            "{github_context}"
            "You are a GitHub assistant. Help the user interact with their GitHub account.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "action": "list_repos|get_repo|list_issues|create_issue|list_prs|list_notifications or null",\n'
            '    "owner": "repo owner login or null",\n'
            '    "repo": "repo name or null",\n'
            '    "title": "issue title or null",\n'
            '    "body": "issue body or null",\n'
            '    "state": "open|closed|all or null",\n'
            '    "visibility": "public|private|all or null"\n'
            "  },\n"
            '  "complete": false,\n'
            '  "detected_agent_type": "github",\n'
            '  "auth_required": null\n'
            "}\n"
            "Rules:\n"
            "- If GitHub is NOT connected (see context above), set auth_required to "
            '  {"provider": "github"} and reply asking the user to connect their GitHub account.\n'
            "  Do NOT set an action until GitHub is connected.\n"
            "- For list_repos and list_notifications: no owner/repo needed.\n"
            "- For list_repos: if the user says 'public', 'only public', or 'public repos' set "
            "  visibility='public'; if they say 'private' set visibility='private'; "
            "  otherwise leave visibility=null (returns all).\n"
            "- For get_repo, list_issues, list_prs: collect owner and repo.\n"
            "- For create_issue: collect owner, repo, title, and body. "
            "  Ask for confirmation before setting complete=true.\n"
            "- complete MUST stay false for read-only actions (list_repos, get_repo, list_issues, "
            "  list_prs, list_notifications) — the system fetches and displays them automatically.\n"
            "- complete=true only for create_issue when ALL fields are known AND user confirmed.\n"
            "- If the user wants something other than GitHub actions, set detected_agent_type to 'general'."
        ),
    },
    {
        "id": "microsoft",
        "label": "Microsoft / Outlook",
        "description": "Read and send Outlook email, manage calendar events via Microsoft 365.",
        "icon": "🟦",
        "routing_hint": (
            "user asks about Outlook, Microsoft email, Microsoft 365, Office 365, Exchange, "
            "their inbox, emails, mail, calendar events, meetings, or wants to send an email, "
            "or wants to create a todo list, action items, tasks, or reminders from their emails, "
            "or wants to add a task, reminder, or to-do item to Microsoft To Do. "
            "Examples: 'check my email', 'show my inbox', 'send an email', 'read my outlook', "
            "'what meetings do I have', 'show my calendar', 'microsoft email', 'outlook email', "
            "'create a todo list from my emails', 'add something to my to do list', "
            "'add a task to To Do', 'remind me to go to the store', 'add to my tasks'"
        ),
        "authorizationType": None,
        "fields": [],
        "services": ["microsoft"],
        "systemPrompt": (
            "{microsoft_context}"
            "You are a Microsoft 365 / Outlook assistant. Help the user read email, send email, "
            "and manage calendar events.\n"
            "ALWAYS respond with ONLY a valid JSON object:\n"
            "{\n"
            '  "reply": "your conversational response",\n'
            '  "extracted": {\n'
            '    "action": "list_emails|read_email|summarize_email|create_todo|push_todo|add_todo_task|complete_todo_task|delete_todo_task|send_email|list_events|create_event or null",\n'
            '    "message_id": "email message id or null",\n'
            '    "to": "recipient email address or null",\n'
            '    "subject": "email subject or null",\n'
            '    "body": "email body or null",\n'
            '    "folder": "inbox|sentitems|drafts or null",\n'
            '    "top": number of items to fetch or null,\n'
            '    "task_title": "title of the task to add (for add_todo_task) or null"\n'
            "  },\n"
            '  "complete": false,\n'
            '  "detected_agent_type": "microsoft",\n'
            '  "auth_required": null\n'
            "}\n"
            "Rules:\n"
            "- If Microsoft is NOT connected (see context above), set auth_required to "
            '  {"provider": "microsoft"} and reply asking the user to connect their Microsoft account.\n'
            "  Do NOT set an action until Microsoft is connected.\n"
            "- For list_emails: use folder='inbox' by default unless user specifies otherwise. top defaults to 10.\n"
            "- For summarize_email: ALWAYS use this action when the user asks to summarize, review, "
            "  describe, or tell them what email(s) say. This action handles ANY number of emails — "
            "  set 'top' to the exact number requested (e.g. 'summarize latest 6' -> top=6). "
            "  Max top=10. NEVER say you can only summarize one email. "
            "  NEVER use list_emails for summarize requests. "
            "  Set reply to 'Summarizing your latest N emails...' replacing N with the count.\n"
            "- For create_todo: use when user asks to create or show a todo list, action items, or tasks "
            "  from their emails WITHOUT saving them anywhere. Set 'top' to number of emails to scan (default 10). "
            "  Set reply to 'Building your to-do list from the latest N emails...'.\n"
            "- For delete_todo_task: use when the user asks to delete, remove, or get rid of a task. "
            "  Use task_title to identify which task. Set reply to 'Deleting \"<task>\"...'.\n"
            "- For complete_todo_task: use when the user asks to mark a task as done, complete, "
            "  finished, or checked off. Use task_title to specify which task. "
            "  Set reply to 'Marking \"<task>\" as complete...'.\n"
            "- For add_todo_task: use when the user wants to add a specific task or reminder to "
            "  Microsoft To Do. Collect the task title from the user (use task_title field). "
            "  If the user hasn't stated the task yet, ask them what to add. "
            "  Set reply to 'Adding \"<task>\" to your Microsoft To Do list...'.\n"
            "- For push_todo: ALWAYS use when user asks to push, save, add, or send tasks/action items "
            "  TO Microsoft To Do. Scans emails and creates real tasks in Microsoft To Do. "
            "  Set 'top' to number of emails to scan (default 10). "
            "  Set reply to 'Extracting action items and saving them to Microsoft To Do...'.\n"
            "- For read_email: collect message_id.\n"
            "- For send_email: collect to, subject, and body. Ask for confirmation before setting complete=true.\n"
            "- For list_events: no extra fields needed (returns upcoming calendar events).\n"
            "- For create_event: not yet supported — tell the user politely.\n"
            "- complete MUST stay false for read-only actions (list_emails, read_email, summarize_email, list_events).\n"
            "- complete=true only for send_email when ALL fields are known AND user confirmed.\n"
            "- If the user wants something other than Microsoft/Outlook actions, set detected_agent_type to 'general'."
        ),
    },
]

# Index by id for fast lookup
_AGENT_TYPE_MAP = {a["id"]: a for a in AGENT_TYPES}


# ── On-chain agent discovery helpers ─────────────────────────────────────────

import time as _time

_ONCHAIN_AGENTS_CACHE: dict = {"ts": 0.0, "data": []}
_ONCHAIN_AGENTS_TTL = 60  # seconds


async def _fetch_onchain_agents(config) -> list:
    """Query confirmed blocks + mempool for AgentAnnouncement transactions.

    Returns a list of unique agent announcement blobs.  The most-recently-
    confirmed version of each agent_id wins; mempool entries fill in agents
    not yet included in a block.

    Results are cached for _ONCHAIN_AGENTS_TTL seconds to avoid a full
    collection scan on every page load.
    """
    now = _time.monotonic()
    if now - _ONCHAIN_AGENTS_CACHE["ts"] < _ONCHAIN_AGENTS_TTL:
        return list(_ONCHAIN_AGENTS_CACHE["data"])

    agents: dict = {}
    try:
        cursor = (
            config.mongo.async_db.blocks.find(
                {
                    "transactions": {
                        "$elemMatch": {"relationship.agent": {"$exists": True}}
                    }
                },
                {"index": 1, "transactions": 1},
            )
            .sort("index", -1)
            .limit(500)
        )
        async for block in cursor:
            for txn in block.get("transactions", []):
                rel = txn.get("relationship")
                if not isinstance(rel, dict):
                    continue
                blob = rel.get("agent")
                if not blob or not isinstance(blob, dict):
                    continue
                aid = blob.get("agent_id", "")
                if aid and aid not in agents:
                    agents[aid] = blob

        # Mempool — fill in any agents not yet confirmed in a block
        mcursor = config.mongo.async_db.miner_transactions.find(
            {"relationship.agent": {"$exists": True}},
            {"relationship": 1},
        )
        async for txn in mcursor:
            rel = txn.get("relationship")
            if not isinstance(rel, dict):
                continue
            blob = rel.get("agent")
            if not blob or not isinstance(blob, dict):
                continue
            aid = blob.get("agent_id", "")
            if aid and aid not in agents:
                agents[aid] = blob

    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("_fetch_onchain_agents: %s", exc)

    result = list(agents.values())
    _ONCHAIN_AGENTS_CACHE["data"] = result
    _ONCHAIN_AGENTS_CACHE["ts"] = _time.monotonic()
    return result


def _sanitize_messages(messages: list) -> list:
    """Ensure every message has a string content field.

    Some LLM APIs reject requests where content is null, a number, or a nested
    object.  Coerce anything non-string to its JSON or str() representation so
    the upstream call never fails with a type error.
    """
    sanitized = []
    for m in messages:
        content = m.get("content")
        if not isinstance(content, str):
            if content is None:
                content = ""
            elif isinstance(content, (dict, list)):
                content = json.dumps(content, separators=(",", ":"))
            else:
                content = str(content)
        sanitized.append({**m, "content": content})
    return sanitized


import re as _re

# Patterns that commonly appear in prompt-injection payloads.
# We don't try to enumerate all attacks — we remove structural markers that
# could break out of the data context and into the instruction context.
_INJECTION_PATTERNS = _re.compile(
    r"(system\s*:|user\s*:|assistant\s*:|<\s*/?\s*(s|inst|sys)\s*>|\[INST\]|\[/INST\]|"
    r"ignore\s+(previous|all|prior)\s+instructions?|"
    r"you\s+are\s+now|from\s+now\s+on\s+you|your\s+new\s+(role|instructions?)|"
    r"disregard\s+(your|the|all)|forget\s+(your|the|all|previous))",
    _re.IGNORECASE,
)


def _sanitize_onchain_str(value, max_len: int = 200) -> str:
    """Sanitize a string coming from on-chain before inserting into a prompt.

    - Collapses all whitespace/newlines to single spaces (prevents newline injection)
    - Strips known prompt-injection patterns
    - Truncates to max_len characters
    """
    if not isinstance(value, str):
        value = str(value)
    # Collapse newlines/tabs/runs of whitespace
    value = " ".join(value.split())
    # Remove injection patterns
    value = _INJECTION_PATTERNS.sub("[…]", value)
    # Truncate
    return value[:max_len]


def _build_generic_intake_prompt(agent_type_id: str, agents: list) -> str:
    """Generate a generic intake system prompt for an on-chain-only agent type."""
    rep = agents[0] if agents else {}
    label = _sanitize_onchain_str(
        rep.get("label") or agent_type_id.replace("_", " ").title(), 80
    )
    description = _sanitize_onchain_str(rep.get("description", ""), 300)
    caps = rep.get("capabilities") or []
    cap_str = (
        ", ".join(_sanitize_onchain_str(str(c), 40) for c in caps[:8]) if caps else ""
    )
    # Sanitize agent_type_id itself — only allow alphanum + underscore
    safe_type_id = _re.sub(r"[^a-z0-9_]", "_", agent_type_id.lower())[:64]
    return (
        f"You are an intake assistant for {label}. "
        + (f"{description} " if description else "")
        + "Understand what the user needs and collect their preferences "
        "ONE question at a time.\n"
        "ALWAYS respond with ONLY a valid JSON object:\n"
        "{\n"
        '  "reply": "your conversational response",\n'
        '  "extracted": {},\n'
        '  "complete": false,\n'
        f'  "detected_agent_type": "{safe_type_id}"\n'
        "}\n"
        + (f"Relevant topics: {cap_str}.\n" if cap_str else "")
        + "complete=true only when you have gathered enough information to proceed.\n"
        + "If the user clearly wants something outside this domain, set detected_agent_type to 'general'."
    )


def _build_general_prompt_dynamic(onchain_agents: list) -> str:
    """Build the general agent system prompt, injecting all known agent types.

    Hardcoded non-meta types (travel, legal, etc.) are always included.
    On-chain types not already in AGENT_TYPES are layered in automatically.
    Each AGENT_TYPES entry may provide a ``routing_hint`` string for richer
    detection rules; on-chain-only types fall back to description/capabilities.
    """
    _META_IDS = {"general", "agent_registration"}

    # Start with hardcoded non-meta types — preserve ordering
    type_entries: dict = {}  # type_id -> {label, routing_hint}
    for entry in AGENT_TYPES:
        if entry["id"] not in _META_IDS:
            hint = entry.get("routing_hint") or entry.get("description") or ""
            type_entries[entry["id"]] = {"label": entry["label"], "hint": hint}

    # Layer in on-chain types not already present
    for blob in onchain_agents:
        at = blob.get("agent_type") or "general"
        # Sanitize agent_type key — only allow alphanum + underscore
        at = _re.sub(r"[^a-z0-9_]", "_", at.lower())[:64]
        if at in _META_IDS or at in type_entries:
            continue
        caps = blob.get("capabilities") or []
        raw_hint = blob.get("description") or (
            ", ".join(str(c) for c in caps[:5]) if caps else ""
        )
        hint = _sanitize_onchain_str(raw_hint, 200)
        label = _sanitize_onchain_str(
            blob.get("label") or at.replace("_", " ").title(), 80
        )
        type_entries[at] = {"label": label, "hint": hint}

    lines = []
    for type_id, info in type_entries.items():
        line = (
            f'- "{type_id}": {info["hint"]}'
            if info["hint"]
            else f'- "{type_id}": {info["label"]}'
        )
        lines.append(line)

    types_block = "\n".join(lines) + "\n" if lines else ""
    return (
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
        + types_block
        + '- "agent_registration": user wants to register or list their AI agent on the blockchain, '
        "create a new agent entry, add an agent to the on-chain registry, or asks how to make "
        "their agent discoverable. Examples: 'register my agent', 'add my AI to the blockchain', "
        "'I want to list my agent'\n"
        "Keep detected_agent_type as 'general' for greetings, vague questions, or topics "
        "that don't clearly fit the above.\n"
        "complete MUST always be false."
    )


# ── Brave Search helper ───────────────────────────────────────────────────────

import urllib.parse as _urlparse


async def _brave_web_search(api_key: str, query: str, count: int = 5) -> list:
    """
    Call the Brave Search API and return a list of result dicts.
    Each dict has keys: title, url, description.
    Returns an empty list on any error so callers can treat search as best-effort.
    """
    params = _urlparse.urlencode(
        {
            "q": query,
            "count": count,
            "text_decorations": "false",
            "search_lang": "en",
            "safesearch": "moderate",
            "freshness": "pm",  # prefer results from the past month
        }
    )
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"
    client = AsyncHTTPClient()
    req = HTTPRequest(
        url=url,
        method="GET",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "X-Subscription-Token": api_key,
        },
        request_timeout=8.0,
    )
    resp = await client.fetch(req, raise_error=False)
    if resp.code != 200:
        return []
    try:
        data = json.loads(resp.body)
        raw = data.get("web", {}).get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("description", ""),
            }
            for r in raw[:count]
        ]
    except Exception:
        return []


def _build_search_context(results: list, query: str) -> str:
    """Format Brave search results as a context block for the system prompt."""
    lines = [
        f'[Web search results for "{query}" — use these to answer factual/current-events questions. '
        "Cite sources when helpful.]",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   URL: {r['url']}")
        if r.get("description"):
            lines.append(f"   {r['description']}")
    return "\n".join(lines)


# ── Vendor registry ───────────────────────────────────────────────────────────
# Maps service id → {name, available, confirmationPrefix}
# Add new services here; a VendorHandler subclass is auto-generated below.

# Appended to every agent system prompt so the model returns structured UI hints.
