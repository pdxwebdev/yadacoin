"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Handlers for announcing nodes to the blockchain
"""

import json
from datetime import datetime, timezone

from yadacoin.core.transaction import Transaction
from yadacoin.core.transactionutils import TU
from yadacoin.enums.peertypes import PEER_TYPES
from yadacoin.http.base import BaseHandler


class NodeAnnounceHandler(BaseHandler):
    """Display and process node announcements to the blockchain.

    This handler is restricted to local/internal access only via api_whitelist.
    Users can view their current node configuration and announce it to the blockchain.
    The node's identity and signing are handled entirely on the backend.
    """

    async def get(self):
        """Display the node announcement form with current node config."""
        try:
            # Only accessible if node mode is enabled and peer is configured
            if not hasattr(self.config, "peer") or not self.config.peer:
                self.set_status(400)
                return self.render_as_json(
                    {
                        "status": "error",
                        "message": "Node not configured. This endpoint requires NODE mode enabled.",
                    }
                )

            peer = self.config.peer

            # Gather identity info
            identity = {
                "username": peer.identity.username if peer.identity else "",
                "public_key": peer.identity.public_key if peer.identity else "",
                "username_signature": (
                    peer.identity.username_signature if peer.identity else ""
                ),
            }

            # Gather network info
            node_info = {
                "host": peer.host or self.config.peer_host or "",
                "port": peer.port or self.config.peer_port or 8003,
                "http_host": peer.http_host
                or self.config.ssl.common_name
                or self.config.peer_host
                or "",
                "http_port": peer.http_port
                or self.config.ssl.port
                or self.config.serve_port
                or 8000,
                "http_protocol": (
                    peer.http_protocol or "https"
                    if (hasattr(self.config, "ssl") and self.config.ssl.is_valid())
                    else "http"
                ),
                "secure": peer.secure
                or (hasattr(self.config, "ssl") and self.config.ssl.is_valid()),
                "peer_type": peer.peer_type or PEER_TYPES.USER.value,
            }

            self.render(
                "node_announce.html",
                **{
                    "identity": identity,
                    "node_info": node_info,
                    "peer_type_seed": PEER_TYPES.SEED.value,
                    "peer_type_gateway": PEER_TYPES.SEED_GATEWAY.value,
                    "peer_type_provider": PEER_TYPES.SERVICE_PROVIDER.value,
                },
            )
        except Exception as e:
            self.app_log.error(f"Error in NodeAnnounceHandler.get: {e}")
            self.set_status(500)
            return self.render_as_json({"status": "error", "message": str(e)})

    async def post(self):
        """Process the node announcement and broadcast to the blockchain."""
        try:
            # Validate that peer is configured
            if not hasattr(self.config, "peer") or not self.config.peer:
                self.set_status(400)
                return self.render_as_json(
                    {"status": "error", "message": "Node not configured."}
                )

            peer = self.config.peer
            if not peer.identity:
                self.set_status(400)
                return self.render_as_json(
                    {"status": "error", "message": "Node identity not configured."}
                )

            # Parse form data
            data = json.loads(self.request.body) if self.request.body else {}

            # Validate required fields
            required_fields = ["host", "port", "http_host", "http_port", "fee"]
            for field in required_fields:
                if field not in data:
                    self.set_status(400)
                    return self.render_as_json(
                        {
                            "status": "error",
                            "message": f"Missing required field: {field}",
                        }
                    )

            # Build node announcement object
            node_announcement = {
                "identity": {
                    "username": peer.identity.username,
                    "public_key": peer.identity.public_key,
                    "username_signature": peer.identity.username_signature,
                },
                "host": str(data.get("host", "")).strip(),
                "port": int(data.get("port", 8003)),
                "http_host": str(data.get("http_host", "")).strip(),
                "http_port": int(data.get("http_port", 8000)),
                "http_protocol": str(data.get("http_protocol", "https"))
                .strip()
                .lower(),
                "secure": data.get("secure", False) in (True, "true", "True", 1, "1"),
            }

            # Validate network values
            if not node_announcement["host"]:
                self.set_status(400)
                return self.render_as_json(
                    {"status": "error", "message": "Host cannot be empty"}
                )

            if node_announcement["port"] < 1 or node_announcement["port"] > 65535:
                self.set_status(400)
                return self.render_as_json(
                    {"status": "error", "message": "Port must be between 1 and 65535"}
                )

            if (
                node_announcement["http_port"] < 1
                or node_announcement["http_port"] > 65535
            ):
                self.set_status(400)
                return self.render_as_json(
                    {
                        "status": "error",
                        "message": "HTTP port must be between 1 and 65535",
                    }
                )

            if node_announcement["http_protocol"] not in ("http", "https"):
                self.set_status(400)
                return self.render_as_json(
                    {
                        "status": "error",
                        "message": "HTTP protocol must be 'http' or 'https'",
                    }
                )

            # Validate registration fee
            try:
                registration_fee = float(data.get("fee", 0))
                if registration_fee < 1:
                    self.set_status(400)
                    return self.render_as_json(
                        {
                            "status": "error",
                            "message": "Registration fee must be at least 1 YDA (1 block)",
                        }
                    )
            except (ValueError, TypeError):
                self.set_status(400)
                return self.render_as_json(
                    {"status": "error", "message": "Invalid fee value"}
                )

            # Calculate registration duration for user feedback
            blocks = int(registration_fee)
            days = blocks / 144

            # Create transaction with node announcement in relationship field
            txn = Transaction(
                txn_time=int(datetime.now(timezone.utc).timestamp()),
                public_key=peer.identity.public_key,
                relationship={"node": node_announcement},
                fee=registration_fee,
                version=7,
            )

            # Sign the transaction using the node's cipher
            try:
                # Use the node's wif to sign
                if hasattr(self.config, "cipher") and self.config.cipher:
                    txn_hash = TU.get_transaction_hash(txn)
                    signature = self.config.cipher.sign(txn_hash)
                    txn.transaction_signature = signature
                else:
                    raise Exception("Node cipher not available for signing")
            except Exception as e:
                self.app_log.error(f"Error signing transaction: {e}")
                self.set_status(500)
                return self.render_as_json(
                    {
                        "status": "error",
                        "message": f"Failed to sign announcement: {str(e)}",
                    }
                )

            # Insert into local miner_transactions collection for broadcasting
            # (The node will pick it up and broadcast to peers)
            try:
                await self.config.mongo.async_db.miner_transactions.replace_one(
                    {"id": txn.transaction_signature}, txn.to_dict(), upsert=True
                )
            except Exception as e:
                self.app_log.error(f"Error inserting transaction: {e}")
                self.set_status(500)
                return self.render_as_json(
                    {
                        "status": "error",
                        "message": f"Failed to broadcast announcement: {str(e)}",
                    }
                )

            return self.render_as_json(
                {
                    "status": "success",
                    "message": f"Node announcement broadcast successfully. Registered for {blocks} blocks (~{days:.1f} days)",
                    "transaction_signature": txn.transaction_signature,
                    "registration_blocks": blocks,
                    "registration_days": round(days, 1),
                    "fee_paid": registration_fee,
                    "timestamp": int(datetime.now(timezone.utc).timestamp()),
                }
            )

        except Exception as e:
            self.app_log.error(f"Error in NodeAnnounceHandler.post: {e}")
            self.set_status(500)
            return self.render_as_json({"status": "error", "message": str(e)})


NODE_ANNOUNCE_HANDLERS = [
    (r"/node/announce", NodeAnnounceHandler),
]
