"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os
import sys

import pytest

import yadacoin.core.config as core_config

# Add the workspace root to sys.path so yadacoin module can be imported
workspace_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)


@pytest.fixture(scope="session", autouse=True)
def initialize_config():
    """Initialize the Config singleton once for the entire test session.

    This ensures Config() always returns a fully initialized instance in any
    test file, without each test class needing its own setUpClass/generate call.
    """
    core_config.Config.generate()


@pytest.fixture(autouse=True)
def _isolate_config_singleton():
    """Config is a process-wide singleton shared by every test in the
    session. Many test classes (across many test files) reassign attributes
    on it directly (e.g. ``Config().app_log = SomeStub()``,
    ``config.public_key = "..."``) without restoring the original value, and
    some of those test classes override ``asyncSetUp``/``setUp`` without
    calling ``super().asyncSetUp()``/``super().setUp()``, so a base-class
    cleanup hook alone cannot catch every case.

    This autouse, function-scoped fixture snapshots the singleton's
    top-level attributes before every test (regardless of test class) and
    unconditionally restores them afterward, so mutations never leak into
    other tests regardless of run order.

    ``BU`` (a ``BlockChainUtils`` instance) is deliberately excluded from
    this reset: ``tests/unittests/test_setup.py::AsyncTestCase`` lazily
    creates it once ("if c.BU is None") and many test classes rely on that
    single, session-persistent instance already being present even when
    they skip calling ``super().asyncSetUp()``. We replicate that same
    lazy-init here (idempotent) before snapshotting so ``BU`` is always
    populated and is left untouched by the restore.
    """
    from yadacoin.core.blockchainutils import BlockChainUtils

    c = core_config.Config()
    if getattr(c, "BU", None) is None:
        c.BU = BlockChainUtils()
    snapshot = {k: v for k, v in vars(c).items() if k != "BU"}
    try:
        yield
    finally:
        bu = c.BU
        c.__dict__.clear()
        c.__dict__.update(snapshot)
        c.BU = bu
