"""postboot.py — indexes + optional demo org for postquantumreadiness."""

from . import store


async def go(app):
    try:
        await store.ensure_indexes(app.config)
    except Exception as exc:
        log = getattr(getattr(app, "config", None), "app_log", None)
        if log:
            log.warning("postquantumreadiness indexes: %s", exc)
