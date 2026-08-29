"""Ensure Mongo indexes for file announcements."""


async def go(app):
    mongo = getattr(getattr(app, "config", None), "mongo", None)
    if mongo is None:
        return
    db = mongo.async_db
    try:
        await db.file_announcements.create_index("record_id", unique=True)
        await db.file_announcements.create_index("file_id")
        await db.file_announcements.create_index("transaction_id")
        await db.file_announcements.create_index(
            [
                ("title", "text"),
                ("description", "text"),
                ("keywords", "text"),
                ("file_id", "text"),
            ]
        )
        await db.file_upload_history.create_index([("timestamp", -1)])
        await db.file_upload_history.create_index("record_id")
        await db.file_upload_history.create_index("file_id")
    except Exception:
        pass
