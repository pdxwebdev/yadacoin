"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
GET /kel-offchain-log

Serves the off-chain signing ratchet chain so that verifiers can walk from the
last on-chain anchor to the current ephemeral auth key without knowing the
node's SECOND_FACTOR.

Query parameters
----------------
anchor_public_key : str  (optional)
    Hex public key of the on-chain anchor to start from.  Defaults to the
    node's current ``config.kel_public_key``.  Only entries whose
    ``anchor_public_key`` matches are returned.

limit : int  (optional, default 100, max 200)
    Maximum number of entries to return (newest first within the anchor).

Response
--------
{
    "status": true,
    "anchor_public_key": "<hex>",
    "entries": [
        {
            "counter":        <int>,
            "public_key":     "<hex>",
            "prev_public_key": "<hex>",
            "certification":  "<base64 sig of public_key by prev_key>",
            "purpose":        "auth" | "reanchor" | ...,
            "timestamp":      <float>
        },
        ...
    ]
}

Verification algorithm (for callers)
--------------------------------------
1. Fetch the node's on-chain KEL from /key-event-log?public_key=<k0_pub>.
2. Identify the latest confirmed anchor entry; note its ``public_key``.
3. Call GET /kel-offchain-log?anchor_public_key=<anchor_pub>.
4. Verify entry[0].prev_public_key == anchor_pub.
5. For each entry[i]: verify that entry[i-1].public_key signed entry[i].public_key
   (check ``certification`` against ``entry[i-1].public_key``).
6. entry[-1].public_key is the current signing key; verify the challenge
   signature against it.
"""

from yadacoin.http.base import BaseHandler


class KelOffchainLogHandler(BaseHandler):
    """GET /kel-offchain-log — serve the off-chain signing ratchet chain."""

    async def get(self):
        config = self.config

        anchor_pub = self.get_argument(
            "anchor_public_key",
            getattr(config, "kel_public_key", "") or "",
        )

        try:
            limit = min(200, max(1, int(self.get_argument("limit", "100"))))
        except (ValueError, TypeError):
            limit = 100

        query = {}
        if anchor_pub:
            query["anchor_public_key"] = anchor_pub

        cursor = (
            config.mongo.async_db.key_event_log.find(
                query, {"_id": 0, "anchor_public_key": 0}
            )
            .sort("counter", 1)
            .limit(limit)
        )

        entries = await cursor.to_list(length=limit)

        return self.render_as_json(
            {
                "status": True,
                "anchor_public_key": anchor_pub,
                "entries": entries,
            }
        )


KEL_OFFCHAIN_HANDLERS = [
    (r"/kel-offchain-log", KelOffchainLogHandler),
]
