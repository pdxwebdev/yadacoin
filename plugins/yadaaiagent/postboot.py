"""postboot.py — startup hook for the yadaaiagentauth plugin."""

import logging

_LOG = logging.getLogger(__name__)


async def go(app):
    """Create indexes required by the Web 2.0 OAuth session store."""
    try:
        config = app.config
        col = config.mongo.async_db.web2_oauth_sessions
        # TTL index: MongoDB automatically removes expired session documents.
        await col.create_index("expires_at", expireAfterSeconds=0)
        # Lookup index on nonce (the client-visible session token)
        await col.create_index(
            [("nonce", 1), ("provider", 1)], unique=True, sparse=True
        )
        _LOG.info("web2_oauth_sessions indexes ensured")
    except Exception as exc:
        # Non-fatal — the collection will still work without the TTL index,
        # it just won't auto-expire stale sessions.
        _LOG.warning("postboot: could not create web2_oauth_sessions indexes: %s", exc)
