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


def pytest_addoption(parser):
    """Add custom command-line options for pytest."""
    parser.addoption(
        "--hash_server_domain",
        action="store",
        default=None,
        help="Hash server domain for remote hashing (e.g., http://test.com)",
    )


@pytest.fixture(scope="session")
def hash_server_domain(request):
    """Fixture to provide hash_server_domain from command-line option."""
    return request.config.getoption("--hash_server_domain")


# Store hash_server_domain globally so test setup can access it
_hash_server_domain = None
_original_generate = core_config.Config.generate


def _generate_with_hash_server_domain(*args, **kwargs):
    config = _original_generate(*args, **kwargs)
    if _hash_server_domain:
        config.hash_server_domain = _hash_server_domain
    return config


def pytest_configure(config):
    """Store hash_server_domain in global scope for test usage."""
    global _hash_server_domain
    _hash_server_domain = config.getoption("--hash_server_domain")
    if _hash_server_domain:
        core_config.Config.generate = _generate_with_hash_server_domain


@pytest.fixture(scope="session", autouse=True)
def initialize_config():
    """Initialize the Config singleton once for the entire test session.

    This ensures Config() always returns a fully initialized instance in any
    test file, without each test class needing its own setUpClass/generate call.
    """
    core_config.Config.generate()
