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
