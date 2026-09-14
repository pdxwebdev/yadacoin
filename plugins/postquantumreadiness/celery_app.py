"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.
"""

import os


def broker_url():
    return (
        os.environ.get("PQR_CELERY_BROKER")
        or os.environ.get("CELERY_BROKER_URL")
        or _cfg("post_quantum_readiness_celery_broker")
        or "redis://localhost:6379/0"
    )


def result_backend():
    return (
        os.environ.get("PQR_CELERY_BACKEND")
        or os.environ.get("CELERY_RESULT_BACKEND")
        or _cfg("post_quantum_readiness_celery_backend")
        or broker_url()
    )


def _cfg(name):
    try:
        from yadacoin.core.config import Config

        cfg = Config()
        return getattr(cfg, name, None)
    except Exception:
        return None


def create_celery():
    from celery import Celery

    app = Celery(
        "postquantumreadiness",
        broker=broker_url(),
        backend=result_backend(),
        include=["plugins.postquantumreadiness.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=int(os.environ.get("PQR_SOFT_LIMIT", "600")),
        task_time_limit=int(os.environ.get("PQR_HARD_LIMIT", "720")),
    )
    return app


try:
    celery_app = create_celery()
except Exception:
    celery_app = None
