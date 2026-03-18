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

import hashlib
import json
from datetime import datetime, timezone

from yadacoin.core.chain import CHAIN
from yadacoin.core.nodeannouncement import NodeAnnouncement
from yadacoin.core.transaction import Output, Transaction
from yadacoin.core.transactionutils import TU
from yadacoin.enums.peertypes import PEER_TYPES
from yadacoin.http.base import BaseHandler


class NodeAnnounceHandler(BaseHandler):
    """Display and process node announcements to the blockchain.

    POST is restricted to local access only (127.0.0.1 / ::1).
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
                "peer_type": peer.peer_type or PEER_TYPES.USER.value,
                "collateral_address": getattr(peer, "collateral_address", ""),
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
            # Restrict to local access only
            if self.request.remote_ip not in ("127.0.0.1", "::1"):
                self.set_status(403)
                return self.render_as_json(
                    {
                        "status": "error",
                        "message": "This endpoint is only accessible locally.",
                    }
                )

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
            required_fields = ["host", "port", "http_host", "http_port"]
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
                "collateral_address": str(data.get("collateral_address", "")).strip(),
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

            if not node_announcement["collateral_address"]:
                self.set_status(400)
                return self.render_as_json(
                    {
                        "status": "error",
                        "message": "collateral_address is required for node announcements",
                    }
                )

            # Create transaction with node announcement in relationship field
            node_announcement_str = NodeAnnouncement.from_dict(
                node_announcement
            ).to_string()
            relationship_hash = (
                hashlib.sha256(node_announcement_str.encode()).digest().hex()
            )
            txn = Transaction(
                txn_time=int(datetime.now(timezone.utc).timestamp()),
                public_key=peer.identity.public_key,
                relationship={"node": node_announcement},
                relationship_hash=relationship_hash,
                outputs=[
                    Output(
                        to=node_announcement["collateral_address"],
                        value=float(CHAIN.DYNAMIC_NODES_COLLATERAL_AMOUNT),
                    )
                ],
                inputs=[],
                fee=0.0,
                version=7,
            )

            # Gather inputs from wallet and return change to sender automatically
            try:
                await txn.do_money()
            except Exception as e:
                self.app_log.error(f"Error gathering inputs: {e}")
                self.set_status(400)
                return self.render_as_json(
                    {"status": "error", "message": f"Insufficient funds: {str(e)}"}
                )

            # Sign the transaction using the node's private key
            try:
                txn.hash = await txn.generate_hash()
                txn.transaction_signature = TU.generate_signature_with_private_key(
                    self.config.private_key, txn.hash
                )
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
                    "message": f"Node announcement broadcast successfully. Collateral of {CHAIN.DYNAMIC_NODES_COLLATERAL_AMOUNT} YDA sent to {node_announcement['collateral_address']}",
                    "transaction_signature": txn.transaction_signature,
                    "collateral_amount": CHAIN.DYNAMIC_NODES_COLLATERAL_AMOUNT,
                    "collateral_address": node_announcement["collateral_address"],
                    "timestamp": int(datetime.now(timezone.utc).timestamp()),
                }
            )

        except Exception as e:
            self.app_log.error(f"Error in NodeAnnounceHandler.post: {e}")
            self.set_status(500)
            return self.render_as_json({"status": "error", "message": str(e)})


NODE_ANNOUNCE_HANDLERS = [
    (r"/node-announce", NodeAnnounceHandler),
]
