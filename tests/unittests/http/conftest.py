"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

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
