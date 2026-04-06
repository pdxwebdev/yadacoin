"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Handler for the HD-wallet key rotation app.

All key derivation and signing happens client-side in JavaScript.
The server only:
  - Serves the HTML page        (GET  /key-rotation)
  - Checks if an address has been spent (GET  /key-rotation/spent?address=)
  - Broadcasts a pre-signed transaction (POST /transaction)

Private key material is never sent to the server.
"""

from yadacoin.http.base import BaseHandler


class KeyRotationHandler(BaseHandler):
    """GET /key-rotation — serve the client-side key-rotation UI."""

    async def get(self):
        self.render("key_rotation.html")


class KeyRotationPrevKeyHashHandler(BaseHandler):
    """
    GET /key-rotation/prev-key-hash?address=<P2PKH>

    For a rotation transaction being built for <address>, returns the
    prev_public_key_hash value that must go into the transaction.

    That value is the public_key_hash of the transaction whose
    prerotated_key_hash == address (i.e. the transaction that committed
    to <address> as the next signer).  For inception (no prior KEL
    entry), returns "".
    """

    async def get(self):
        address = self.get_query_argument("address", "")
        if not address:
            self.set_status(400)
            return self.render_as_json({"error": "address required"})

        projection = {"_id": 0, "public_key_hash": 1, "id": 1}

        # 1. Check mempool first
        mempool_hit = await self.config.mongo.async_db.miner_transactions.find_one(
            {"prerotated_key_hash": address}, projection
        )
        if mempool_hit:
            return self.render_as_json(
                {
                    "prev_public_key_hash": mempool_hit.get("public_key_hash", ""),
                    "source": "mempool",
                }
            )

        # 2. Check confirmed blockchain
        chain_hit = await self.config.mongo.async_db.blocks.find_one(
            {"transactions": {"$elemMatch": {"prerotated_key_hash": address}}},
            {"_id": 0, "transactions.$": 1},
        )
        if chain_hit:
            txns = chain_hit.get("transactions", [])
            txn = txns[0] if txns else {}
            return self.render_as_json(
                {
                    "prev_public_key_hash": txn.get("public_key_hash", ""),
                    "source": "blockchain",
                }
            )

        # No prior KEL entry — this is an inception transaction
        return self.render_as_json({"prev_public_key_hash": "", "source": None})


class KeyRotationSpentHandler(BaseHandler):
    """
    GET /key-rotation/spent?address=<P2PKH>

    Returns {"spent": true, "source": "mempool"|"blockchain", "txid": "..."}
    or      {"spent": false}

    "Spent" means the address has submitted a key-rotation transaction —
    i.e. a transaction exists whose public_key_hash == address.
    """

    async def get(self):
        address = self.get_query_argument("address", "")
        if not address:
            self.set_status(400)
            return self.render_as_json({"error": "address required"})

        # 1. Check mempool (miner_transactions)
        mempool_hit = await self.config.mongo.async_db.miner_transactions.find_one(
            {"public_key_hash": address},
            {
                "_id": 0,
                "id": 1,
                "prerotated_key_hash": 1,
                "twice_prerotated_key_hash": 1,
            },
        )
        if mempool_hit:
            return self.render_as_json(
                {
                    "spent": True,
                    "source": "mempool",
                    "txid": mempool_hit.get("id", ""),
                    "prerotated_key_hash": mempool_hit.get("prerotated_key_hash", ""),
                    "twice_prerotated_key_hash": mempool_hit.get(
                        "twice_prerotated_key_hash", ""
                    ),
                }
            )

        # 2. Check confirmed blockchain (blocks → transactions array)
        chain_hit = await self.config.mongo.async_db.blocks.find_one(
            {"transactions": {"$elemMatch": {"public_key_hash": address}}},
            {"_id": 0, "transactions.$": 1},
        )
        if chain_hit:
            txns = chain_hit.get("transactions", [])
            txn = txns[0] if txns else {}
            return self.render_as_json(
                {
                    "spent": True,
                    "source": "blockchain",
                    "txid": txn.get("id", ""),
                    "prerotated_key_hash": txn.get("prerotated_key_hash", ""),
                    "twice_prerotated_key_hash": txn.get(
                        "twice_prerotated_key_hash", ""
                    ),
                }
            )

        return self.render_as_json({"spent": False, "source": None, "txid": ""})


KEY_ROTATION_HANDLERS = [
    (r"/key-rotation|/yadacoin-cash", KeyRotationHandler),
    (
        r"/key-rotation/prev-key-hash|/yadacoin-cash/prev-key-hash",
        KeyRotationPrevKeyHashHandler,
    ),
    (r"/key-rotation/spent|/yadacoin-cash/spent", KeyRotationSpentHandler),
]
