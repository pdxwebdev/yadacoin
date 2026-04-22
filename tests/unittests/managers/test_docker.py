"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from unittest.mock import MagicMock, patch

from yadacoin.managers.docker import Docker, DockerStats


class TestDockerStats(unittest.TestCase):
    def _make_stats(self):
        return {
            "cpu_stats": {
                "online_cpus": 4,
                "cpu_usage": {"total_usage": 200000000},
                "system_cpu_usage": 4000000000,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100000000},
                "system_cpu_usage": 3000000000,
            },
            "memory_stats": {
                "usage": 100 * 1024 * 1024,  # 100 MB
                "limit": 1024 * 1024 * 1024,  # 1 GB
            },
        }

    def test_calculate_cpu_percent(self):
        stats = self._make_stats()
        container = MagicMock()
        container.stats.return_value = stats
        ds = DockerStats(container)
        # cpu_delta = 200M - 100M = 100M
        # system_delta = 4G - 3G = 1G
        # cpu_percent = 100M / 1G * 4 * 100 = 40%
        self.assertAlmostEqual(ds.cpu_percent, 40.0)

    def test_mem_percent(self):
        stats = self._make_stats()
        container = MagicMock()
        container.stats.return_value = stats
        ds = DockerStats(container)
        expected = (100 * 1024 * 1024) / (1024 * 1024 * 1024) * 100.0
        self.assertAlmostEqual(ds.mem_percent, expected)

    def test_to_dict(self):
        stats = self._make_stats()
        container = MagicMock()
        container.stats.return_value = stats
        ds = DockerStats(container)
        d = ds.to_dict()
        self.assertIn("cpu_percent", d)
        self.assertIn("mem_usage", d)
        self.assertIn("mem_limit", d)
        self.assertIn("mem_percent", d)

    def test_calculate_cpu_percent_zero_system_delta(self):
        stats = {
            "cpu_stats": {
                "online_cpus": 2,
                "cpu_usage": {"total_usage": 100},
                "system_cpu_usage": 1000,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100},
                "system_cpu_usage": 1000,
            },
            "memory_stats": {"usage": 1000, "limit": 10000},
        }
        container = MagicMock()
        container.stats.return_value = stats
        ds = DockerStats(container)
        # system_delta == 0, so cpu_percent stays 0
        self.assertEqual(ds.cpu_percent, 0.0)


class TestDockerIsInsideDocker(unittest.TestCase):
    def test_is_inside_docker_false_when_no_files(self):
        with patch("builtins.open", side_effect=FileNotFoundError), patch(
            "os.path.exists", return_value=False
        ):
            result = Docker.is_inside_docker()
            self.assertFalse(result)

    def test_is_inside_docker_true_from_cgroup(self):
        with patch("builtins.open", unittest.mock.mock_open(read_data="docker")):
            result = Docker.is_inside_docker()
            self.assertTrue(result)

    def test_is_inside_docker_true_from_dockerenv(self):
        with patch("builtins.open", side_effect=FileNotFoundError), patch(
            "os.path.exists", return_value=True
        ):
            result = Docker.is_inside_docker()
            self.assertTrue(result)


class TestDockerInit(unittest.TestCase):
    def _make_docker(self):
        """Create a Docker instance with mocked __init__ (docker SDK not installed)."""
        d = Docker.__new__(Docker)
        d.docker = MagicMock()
        d.stats = {}
        d.client = MagicMock()
        return d

    def test_set_container_stats(self):
        d = self._make_docker()
        container = MagicMock()
        container.name = "test_container"
        stats_data = {
            "cpu_stats": {
                "online_cpus": 2,
                "cpu_usage": {"total_usage": 200},
                "system_cpu_usage": 4000,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100},
                "system_cpu_usage": 2000,
            },
            "memory_stats": {"usage": 100, "limit": 1000},
        }
        container.stats.return_value = stats_data
        d.client.containers.list.return_value = [container]
        d.set_container_stats()
        self.assertIn("test_container", d.stats)

    def test_to_dict(self):
        d = self._make_docker()
        d.client.containers.list.return_value = []
        result = d.to_dict()
        self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
