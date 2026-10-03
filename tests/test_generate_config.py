import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


class TestGenerateConfig(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        self.sensitive = dict.fromkeys(
            ("private_key", "wif", "seed", "xprv"), "test-only-value"
        )
        self.config.to_json.side_effect = lambda include_sensitive=False: json.dumps(
            {"username": "testnode", **(self.sensitive if include_sensitive else {})}
        )
        self.config_class = MagicMock()
        self.config_class.generate.return_value = self.config
        self.modules = {
            "base58": MagicMock(),
            "coincurve": MagicMock(),
            "requests": MagicMock(),
            "yadacoin.core.config": MagicMock(Config=self.config_class),
        }

    def run_generator(self, *args):
        script = Path(__file__).resolve().parents[1] / "utils" / "generate_config.py"
        output = io.StringIO()
        with (
            patch.dict(sys.modules, self.modules),
            patch.object(sys, "argv", [str(script), *args]),
            patch.object(sys, "path", sys.path[:]),
            patch("getpass.getpass", return_value=""),
            contextlib.redirect_stdout(output),
        ):
            runpy.run_path(str(script), run_name="__main__")
        return output.getvalue()

    def assert_redacted_output(self, output):
        self.assertEqual(json.loads(output), {"username": "testnode"})
        self.config.to_json.assert_called_once_with()

    def test_new_prints_without_sensitive_fields(self):
        self.assert_redacted_output(self.run_generator("new", "testnode"))

    def test_update_prints_without_sensitive_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"xprv": "test-only-value"}))
            self.assert_redacted_output(
                self.run_generator("update", str(path), "testnode")
            )

    def test_auto_prints_without_sensitive_fields(self):
        self.assert_redacted_output(self.run_generator("auto", "-u", "testnode"))

    def test_auto_file_writes_include_sensitive_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            for option in ("--force", "--create"):
                with self.subTest(option=option):
                    self.config.to_json.reset_mock()
                    path = Path(directory) / f"{option}.json"
                    output = self.run_generator("auto", option, str(path))
                    self.assertEqual(output, "")
                    self.assertEqual(
                        json.loads(path.read_text()),
                        {"username": "testnode", **self.sensitive},
                    )
                    self.config.to_json.assert_called_once_with(include_sensitive=True)

    def test_auto_create_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("existing config")
            self.assertEqual(self.run_generator("auto", "--create", str(path)), "")
            self.assertEqual(path.read_text(), "existing config")
            self.config.to_json.assert_not_called()
