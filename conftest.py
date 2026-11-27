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

# Add the workspace root to sys.path so yadacoin and plugin tests can be
# imported regardless of which test directory pytest is pointed at.
workspace_root = os.path.dirname(os.path.abspath(__file__))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

# pytest + tornado.testing.AsyncHTTPTestCase incompatibility fix.
#
# pytest discovers test classes by instantiating them with no arguments, which
# defaults to methodName='runTest'.  AsyncHTTPTestCase's __init__ calls
# setattr(self, methodName, ...) and raises AttributeError when there is no
# 'runTest' method on the class.
#
# The standard pytest unittest integration handles this by using
# UnitTestCase instead of the generic Class collector when it detects a
# unittest.TestCase subclass.  However, tornado.testing.AsyncHTTPTestCase
# overrides __init__ in a way that triggers the error before pytest's
# unittest collector can intercept it.
#
# Fix: patch tornado.testing.AsyncHTTPTestCase.__init__ so that a missing
# 'runTest' method doesn't raise, allowing pytest's unittest collector to
# proceed normally and discover all test_ methods on the class.

import tornado.testing


def _make_patched_init(original_init):
    def _patched_init(self, methodName="runTest", **kwargs):
        if methodName == "runTest" and not hasattr(self, "runTest"):
            self.runTest = lambda: None
        original_init(self, methodName=methodName, **kwargs)

    return _patched_init


tornado.testing.AsyncTestCase.__init__ = _make_patched_init(
    tornado.testing.AsyncTestCase.__init__
)
tornado.testing.AsyncHTTPTestCase.__init__ = _make_patched_init(
    tornado.testing.AsyncHTTPTestCase.__init__
)


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
