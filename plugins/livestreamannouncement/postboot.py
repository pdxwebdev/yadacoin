"""Ensure Mongo indexes and advertise livestream capabilities."""


async def go(app):
    config = getattr(app, "config", None)
    mongo = getattr(config, "mongo", None) if config is not None else None
    if mongo is not None:
        db = mongo.async_db
        try:
            await db.livestream_channels.create_index("channel_id", unique=True)
            await db.livestream_channels.create_index("announcement_txn_id")
            await db.livestream_channels.create_index("branch_peer")
            await db.livestream_grants.create_index("channel_id")
            await db.livestream_grants.create_index(
                [("channel_id", 1), ("publisher_username_signature", 1)]
            )
            await db.livestream_blocked_branches.create_index("transaction_id")
            await db.livestream_blocked_branches.create_index("channel_id")
            await db.livestream_blocked_branches.create_index("branch_commit")
            await db.livestream_challenges.create_index("nonce", unique=True)
            await db.livestream_challenges.create_index("exp")
        except Exception:
            pass

    if config is None:
        return
    if getattr(config, "peer_type", "") != "service_provider":
        return
    ingest_url = getattr(config, "livestream_ingest_url", "") or ""
    playback_url = getattr(config, "livestream_playback_url", "") or ""
    protocol = "whip" if ingest_url.lower().startswith("http") else "rtmp"
    caps = getattr(config, "capabilities", None)
    if not isinstance(caps, dict):
        caps = {}
        config.capabilities = caps
    caps["livestream"] = {
        "ingest": bool(ingest_url),
        "protocol": protocol,
        "url": ingest_url,
        "playback_url": playback_url,
        "age_gate": True,
    }
