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
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import yadanodemanager  # noqa: E402


class PluginSnapshotTest(unittest.TestCase):
    def test_manager_does_not_copy_plugins_into_container(self):
        self.assertFalse(
            hasattr(yadanodemanager.YadaNodeManager, "_install_recovered_plugins")
        )

    def test_recovery_without_legacy_image_does_not_touch_docker_cp(self):
        manager = yadanodemanager.YadaNodeManager.__new__(
            yadanodemanager.YadaNodeManager
        )
        manager.repo_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        with mock.patch.object(manager, "_legacy_plugin_image", return_value=None):
            with mock.patch.object(yadanodemanager.subprocess, "run") as run:
                self.assertFalse(manager.recover_legacy_plugins())
        for call in run.call_args_list:
            self.assertNotIn("cp", call.args[0])
