"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import contextlib
import io
import logging
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

from yadacoin.app import NodeApplication


class InteractiveInput(io.StringIO):
    def isatty(self):
        return True


def make_app(username="", second_factor_file="", handlers=None):
    app = NodeApplication.__new__(NodeApplication)
    app.config = types.SimpleNamespace(
        username=username,
        second_factor_file=second_factor_file,
        app_log=logging.getLogger("yadacoin.tests.operator_bootstrap"),
        operator_access_code="code",
        serve_host="127.0.0.1",
        serve_port=8001,
        root_app="",
    )
    app.default_handlers = list(handlers or [])
    return app


class OperatorRoutesTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(
            os.environ,
            {"SECOND_FACTOR": "", "SECOND_FACTOR_FILE": ""},
            clear=False,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_operator_routes_detected(self):
        app = make_app(handlers=[("/app", object), ("/operator", object)])
        self.assertTrue(app._operator_routes_registered())

    def test_operator_routes_missing(self):
        app = make_app(handlers=[("/app", object)])
        self.assertFalse(app._operator_routes_registered())

    def test_needs_setup_when_username_missing(self):
        app = make_app()
        self.assertTrue(app._node_needs_setup())

    def test_configured_with_env_second_factor(self):
        app = make_app(username="operator")
        with mock.patch.dict(os.environ, {"SECOND_FACTOR": "factor"}):
            self.assertFalse(app._node_needs_setup())

    def test_configured_with_second_factor_file(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("factor")
            name = handle.name
        self.addCleanup(os.unlink, name)
        app = make_app(username="operator", second_factor_file=name)
        self.assertFalse(app._node_needs_setup())

    def test_empty_second_factor_file_still_needs_setup(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            name = handle.name
        self.addCleanup(os.unlink, name)
        app = make_app(username="operator", second_factor_file=name)
        self.assertTrue(app._node_needs_setup())

    def test_unreadable_second_factor_file_still_needs_setup(self):
        app = make_app(username="operator", second_factor_file="/missing/second_factor")
        self.assertTrue(app._node_needs_setup())


class EnsureOperatorSetupTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(
            os.environ,
            {"SECOND_FACTOR": "", "SECOND_FACTOR_FILE": ""},
            clear=False,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        gate = mock.patch.object(NodeApplication, "_apply_operator_setup_gate")
        self.gate = gate.start()
        self.addCleanup(gate.stop)

    def test_no_prompt_when_routes_registered(self):
        app = make_app(handlers=[("/operator", object)])
        with mock.patch.object(app, "_install_operator_plugin") as install:
            app.ensure_operator_setup_available()
        install.assert_not_called()
        self.gate.assert_called_once_with()

    def test_no_prompt_when_node_is_configured(self):
        app = make_app(username="operator")
        with mock.patch.dict(os.environ, {"SECOND_FACTOR": "factor"}):
            with mock.patch.object(app, "_install_operator_plugin") as install:
                app.ensure_operator_setup_available()
        install.assert_not_called()
        self.gate.assert_called_once_with()

    def test_non_interactive_logs_install_location(self):
        app = make_app()
        with mock.patch.object(sys, "stdin", io.StringIO()):
            with self.assertLogs(app.config.app_log, level="WARNING") as logs:
                app.ensure_operator_setup_available()
        self.assertTrue(
            any("Install the operator plugin in" in line for line in logs.output)
        )

    def test_decline_does_not_install(self):
        app = make_app()
        with contextlib.redirect_stdout(io.StringIO()):
            with mock.patch.object(sys, "stdin", InteractiveInput("n\n")):
                with mock.patch.object(app, "_install_operator_plugin") as install:
                    app.ensure_operator_setup_available()
        install.assert_not_called()

    def test_eof_does_not_install(self):
        app = make_app()
        with contextlib.redirect_stdout(io.StringIO()):
            with mock.patch.object(sys, "stdin", InteractiveInput("")):
                with mock.patch.object(app, "_install_operator_plugin") as install:
                    app.ensure_operator_setup_available()
        install.assert_not_called()

    def test_accept_installs_and_activates(self):
        app = make_app()
        with contextlib.redirect_stdout(io.StringIO()):
            with mock.patch.object(sys, "stdin", InteractiveInput("yes\n")):
                with mock.patch.object(
                    app, "_install_operator_plugin", return_value=True
                ) as install:
                    with mock.patch.object(
                        app, "_activate_operator_plugin", return_value=True
                    ) as activate:
                        app.ensure_operator_setup_available()
        install.assert_called_once_with()
        activate.assert_called_once_with()

    def test_failed_install_does_not_activate(self):
        app = make_app()
        with contextlib.redirect_stdout(io.StringIO()):
            with mock.patch.object(sys, "stdin", InteractiveInput("y\n")):
                with mock.patch.object(
                    app, "_install_operator_plugin", return_value=False
                ):
                    with mock.patch.object(
                        app, "_activate_operator_plugin"
                    ) as activate:
                        app.ensure_operator_setup_available()
        activate.assert_not_called()

    def test_failed_activation_is_reported(self):
        app = make_app()
        with contextlib.redirect_stdout(io.StringIO()):
            with mock.patch.object(sys, "stdin", InteractiveInput("y\n")):
                with mock.patch.object(
                    app, "_install_operator_plugin", return_value=True
                ):
                    with mock.patch.object(
                        app, "_activate_operator_plugin", return_value=False
                    ):
                        with self.assertLogs(app.config.app_log, level="ERROR") as logs:
                            app.ensure_operator_setup_available()
        self.assertTrue(
            any(
                "installed but its routes failed to load" in line
                for line in logs.output
            )
        )


class ActivateOperatorPluginTest(unittest.TestCase):
    def test_activation_before_http_loads_dependencies_then_operator(self):
        app = make_app()
        catalog = {"operator": "url", "yadapasswordsignin": "url"}

        def dependencies(name):
            if name == "operator":
                return {"yadapasswordsignin"}
            return set()

        with mock.patch.object(app, "_plugin_search_dirs") as search:
            with mock.patch.object(app, "_plugin_catalog", return_value=catalog):
                with mock.patch.object(
                    app, "_plugin_dependencies", side_effect=dependencies
                ):
                    with mock.patch.object(
                        app, "_load_plugin", return_value=True
                    ) as load_plugin:
                        with mock.patch.object(
                            app, "_apply_operator_setup_gate"
                        ) as gate:
                            self.assertTrue(app._activate_operator_plugin())
        search.assert_called_once_with()
        gate.assert_called_once_with()
        self.assertEqual(
            load_plugin.call_args_list,
            [
                mock.call("yadapasswordsignin", run_postboot=True),
                mock.call("operator", run_postboot=True),
            ],
        )

    def test_activation_stops_when_dependency_fails(self):
        app = make_app()
        catalog = {"operator": "url", "yadapasswordsignin": "url"}

        def dependencies(name):
            if name == "operator":
                return {"yadapasswordsignin"}
            return set()

        with mock.patch.object(app, "_plugin_search_dirs"):
            with mock.patch.object(app, "_plugin_catalog", return_value=catalog):
                with mock.patch.object(
                    app, "_plugin_dependencies", side_effect=dependencies
                ):
                    with mock.patch.object(
                        app, "_load_plugin", return_value=False
                    ) as load_plugin:
                        with mock.patch.object(
                            app, "_apply_operator_setup_gate"
                        ) as gate:
                            self.assertFalse(app._activate_operator_plugin())
        load_plugin.assert_called_once_with("yadapasswordsignin", run_postboot=True)
        gate.assert_not_called()

    def test_activation_with_live_router_reloads_routes(self):
        app = make_app()
        app.wildcard_router = object()
        with mock.patch.object(app, "_plugin_search_dirs"):
            with mock.patch.object(app, "reload_http_routes") as reload_routes:
                with mock.patch.object(
                    app, "_operator_routes_registered", return_value=True
                ):
                    with mock.patch.object(app, "_apply_operator_setup_gate") as gate:
                        self.assertTrue(app._activate_operator_plugin())
        reload_routes.assert_called_once_with()
        gate.assert_called_once_with()

    def test_activation_with_live_router_reports_missing_routes(self):
        app = make_app()
        app.wildcard_router = object()
        with mock.patch.object(app, "_plugin_search_dirs"):
            with mock.patch.object(app, "reload_http_routes"):
                with mock.patch.object(
                    app, "_operator_routes_registered", return_value=False
                ):
                    with mock.patch.object(app, "_apply_operator_setup_gate") as gate:
                        self.assertFalse(app._activate_operator_plugin())
        gate.assert_not_called()

    def test_apply_setup_gate_runs_plugin_gate(self):
        app = make_app()
        calls = []
        module = types.ModuleType("plugins.operator.setup")
        module.apply_setup_gate = lambda config: calls.append(config)
        with mock.patch.dict(sys.modules, {"plugins.operator.setup": module}):
            self.assertTrue(app._apply_operator_setup_gate())
        self.assertEqual(calls, [app.config])


class LoadPluginLoggingTest(unittest.TestCase):
    def test_missing_dependency_logs_one_line_without_traceback(self):
        app = make_app()
        error = ModuleNotFoundError("No module named 'plugins.yadapasswordsignin'")
        with mock.patch("yadacoin.app.importlib.import_module", side_effect=error):
            with self.assertLogs(app.config.app_log, level="WARNING") as logs:
                self.assertFalse(app._load_plugin("operator"))
        self.assertEqual(len(logs.output), 1)
        self.assertIn("plugin operator failed to load", logs.output[0])
        self.assertIn("yadapasswordsignin", logs.output[0])
        self.assertNotIn("Traceback", logs.output[0])


class InstallOperatorPluginTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        patcher = mock.patch.dict(
            os.environ, {"YADA_PLUGINS_DIR": self.root}, clear=False
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.manifest = os.path.join(self.root, "plugins.txt")
        with open(self.manifest, "w", encoding="utf-8") as handle:
            handle.write(
                "# plugins\n"
                "operator\tgit@github.com:pdxwebdev/operator.git\n"
                "app\thttps://example.com/app.git\n"
                "yadapasswordsignin\t"
                "git@github.com:pdxwebdev/yadapasswordsignin.git\n"
            )

    def _app(self):
        app = make_app()
        app._plugin_manifest_path = lambda: self.manifest
        return app

    @staticmethod
    def _clone_ok(cmd, **kwargs):
        if cmd[:2] == ["git", "clone"]:
            os.makedirs(cmd[-1])
            with open(os.path.join(cmd[-1], "handlers.py"), "w") as handle:
                handle.write("HANDLERS = []\n")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    def test_catalog_parses_ssh_urls_and_skips_comments(self):
        catalog = self._app()._plugin_catalog()
        self.assertEqual(
            catalog["operator"], "https://github.com/pdxwebdev/operator.git"
        )
        self.assertEqual(catalog["app"], "https://example.com/app.git")
        self.assertEqual(
            catalog["yadapasswordsignin"],
            "https://github.com/pdxwebdev/yadapasswordsignin.git",
        )
        self.assertEqual(len(catalog), 3)

    def test_install_clones_operator_plugin(self):
        app = self._app()
        with mock.patch("yadacoin.app.subprocess.run", side_effect=self._clone_ok):
            self.assertTrue(app._install_operator_plugin())
        self.assertTrue(
            os.path.isfile(os.path.join(self.root, "operator", "handlers.py"))
        )

    def test_install_clones_plugin_dependencies(self):
        app = self._app()

        def clone_with_dependency(cmd, **kwargs):
            cloned = cmd[-1]
            os.makedirs(cloned)
            with open(os.path.join(cloned, "handlers.py"), "w") as handle:
                if os.path.basename(cloned) == "operator":
                    handle.write(
                        "from plugins.yadapasswordsignin.handlers import "
                        "redirect_to_signin\nHANDLERS = []\n"
                    )
                else:
                    handle.write("HANDLERS = []\n")
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch(
            "yadacoin.app.subprocess.run", side_effect=clone_with_dependency
        ) as run:
            self.assertTrue(app._install_operator_plugin())
        cloned = [call.args[0][-1] for call in run.call_args_list]
        self.assertEqual(
            [os.path.basename(item) for item in cloned],
            ["operator", "yadapasswordsignin"],
        )
        self.assertTrue(
            os.path.isfile(os.path.join(self.root, "yadapasswordsignin", "handlers.py"))
        )

    def test_install_keeps_existing_dependency_checkout(self):
        app = self._app()
        dependency = os.path.join(self.root, "yadapasswordsignin")
        os.makedirs(dependency)
        with open(os.path.join(dependency, "handlers.py"), "w") as handle:
            handle.write("HANDLERS = []\n")

        def clone_operator(cmd, **kwargs):
            cloned = cmd[-1]
            os.makedirs(cloned)
            with open(os.path.join(cloned, "handlers.py"), "w") as handle:
                handle.write(
                    "from plugins.yadapasswordsignin.handlers import "
                    "redirect_to_signin\nHANDLERS = []\n"
                )
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch(
            "yadacoin.app.subprocess.run", side_effect=clone_operator
        ) as run:
            self.assertTrue(app._install_operator_plugin())
        run.assert_called_once()
        self.assertTrue(os.path.isfile(os.path.join(dependency, "handlers.py")))

    def test_install_replaces_existing_plugin_directory(self):
        app = self._app()
        stale = os.path.join(self.root, "operator")
        os.makedirs(stale)
        with open(os.path.join(stale, "stale.txt"), "w") as handle:
            handle.write("old")
        with mock.patch("yadacoin.app.subprocess.run", side_effect=self._clone_ok):
            self.assertTrue(app._install_operator_plugin())
        self.assertFalse(os.path.exists(os.path.join(stale, "stale.txt")))
        self.assertTrue(os.path.isfile(os.path.join(stale, "handlers.py")))

    def test_install_fails_without_catalog_entry(self):
        app = self._app()
        with open(self.manifest, "w", encoding="utf-8") as handle:
            handle.write("app\thttps://example.com/app.git\n")
        with mock.patch("yadacoin.app.subprocess.run") as run:
            self.assertFalse(app._install_operator_plugin())
        run.assert_not_called()

    def test_install_fails_when_clone_fails(self):
        app = self._app()
        failed = types.SimpleNamespace(returncode=1, stdout="", stderr="no network")
        with mock.patch("yadacoin.app.subprocess.run", return_value=failed):
            self.assertFalse(app._install_operator_plugin())
        self.assertFalse(os.path.exists(os.path.join(self.root, "operator")))

    def test_install_fails_when_handlers_missing(self):
        app = self._app()

        def clone_without_handlers(cmd, **kwargs):
            os.makedirs(cmd[-1])
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch(
            "yadacoin.app.subprocess.run", side_effect=clone_without_handlers
        ):
            self.assertFalse(app._install_operator_plugin())


class StartupBannerTest(unittest.TestCase):
    def _banner(self, app):
        stream = io.StringIO()
        with contextlib.redirect_stderr(stream):
            app.print_startup_banner()
        return stream.getvalue()

    def test_registered_routes_show_setup_url(self):
        app = make_app(handlers=[("/operator/setup", object)])
        out = self._banner(app)
        self.assertIn("/operator/setup?code=code", out)

    def test_missing_routes_hide_dead_setup_url(self):
        app = make_app()
        out = self._banner(app)
        self.assertNotIn("/operator/setup?code=", out)
        self.assertIn("OPERATOR SETUP UNAVAILABLE", out)


class PluginSearchOrderTest(unittest.TestCase):
    def setUp(self):
        import yadacoin.app as app_module

        self.repo_plugins = os.path.abspath(
            os.path.join(os.path.dirname(app_module.__file__), "..", "plugins")
        )

    def _search(self, isdir, env_dir=None):
        app = make_app()
        original = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), original))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("YADA_PLUGINS_DIR", None)
            if env_dir is not None:
                os.environ["YADA_PLUGINS_DIR"] = env_dir
            with mock.patch("yadacoin.app.path.isdir", side_effect=isdir):
                return app._plugin_search_dirs()

    def _only_repo_plugins(self, candidate):
        return os.path.basename(os.path.normpath(candidate)) == "plugins"

    def test_shipped_plugins_come_before_incidental_plugins_dir(self):
        def isdir(candidate):
            return candidate == "/plugins" or self._only_repo_plugins(candidate)

        dirs = self._search(isdir)
        self.assertEqual(dirs[0], self.repo_plugins)
        self.assertEqual(dirs[1], "/plugins")

    def test_explicit_plugins_dir_still_wins(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)

        def isdir(candidate):
            return candidate == root or self._only_repo_plugins(candidate)

        dirs = self._search(isdir, env_dir=root)
        self.assertEqual(dirs[0], root)
        self.assertEqual(dirs[1], self.repo_plugins)

    def test_incidental_plugins_dir_still_contributes_extra_plugins(self):
        def isdir(candidate):
            return candidate == "/plugins" or self._only_repo_plugins(candidate)

        dirs = self._search(isdir)
        self.assertEqual(dirs, [self.repo_plugins, "/plugins"])

    def test_plugins_dir_is_skipped_when_absent(self):
        def isdir(candidate):
            return candidate != "/plugins" and self._only_repo_plugins(candidate)

        dirs = self._search(isdir)
        self.assertEqual(dirs, [self.repo_plugins])
