"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os


class DockerStats:
    def __init__(self, container):
        self.container = container
        self.stats = self.container.stats(stream=False)
        self.cpu_percent = self.calculate_cpu_percent(self.stats)
        self.mem_usage = self.stats["memory_stats"]["usage"]
        self.mem_limit = self.stats["memory_stats"]["limit"]
        self.mem_percent = (self.mem_usage / self.mem_limit) * 100.0

    def calculate_cpu_percent(self, stats):
        cpu_count = stats["cpu_stats"]["online_cpus"]
        cpu_percent = 0.0
        cpu_delta = float(stats["cpu_stats"]["cpu_usage"]["total_usage"]) - float(
            stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = float(stats["cpu_stats"]["system_cpu_usage"]) - float(
            stats["precpu_stats"]["system_cpu_usage"]
        )

        if system_delta > 0.0:
            cpu_percent = cpu_delta / system_delta * cpu_count * 100.0
        return cpu_percent

    def to_dict(self):
        return {
            "cpu_percent": self.cpu_percent,
            "mem_usage": self.mem_usage,
            "mem_limit": self.mem_limit,
            "mem_percent": self.mem_percent,
        }


class Docker:
    stats = {}

    def __init__(self):
        import docker as _docker

        self.docker = _docker
        self.client = self.docker.DockerClient(base_url="unix://var/run/docker.sock")

    @staticmethod
    def is_inside_docker():
        result = False
        try:
            with open("/proc/1/cgroup", "rt") as f:
                result = "docker" in f.read()
        except Exception:
            pass
        if result:
            return result
        else:
            return os.path.exists("/.dockerenv")

    def set_container_stats(self):
        for container in self.client.containers.list():
            try:
                self.stats[container.name] = DockerStats(container)
            except self.docker.errors.NotFound:
                pass

    def to_dict(self):
        return {x: y.to_dict() for x, y in self.stats.items()}
