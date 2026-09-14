"""postboot.py — indexes for password auth sessions / home claims."""


async def go(app):
    try:
        from plugins.passwordrotation import auth_session as asess

        await asess.ensure_indexes()
    except Exception:
        pass
