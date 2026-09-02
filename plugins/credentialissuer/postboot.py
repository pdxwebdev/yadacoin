"""Ensure Mongo indexes for issued credentials."""


async def go(app):
    mongo = getattr(getattr(app, "config", None), "mongo", None)
    if mongo is None:
        return
    db = mongo.async_db
    try:
        await db.issued_credentials.create_index("transaction_id")
        await db.issued_credentials.create_index("username")
        await db.issued_credentials.create_index("subject_username_signature")
        await db.issued_credentials.create_index("claim")
    except Exception:
        pass
