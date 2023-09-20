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
        cpu_count = len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"])
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


class Docker:
    stats = {"yada-node": None, "mongodb": None}

    def __init__(self):
        import docker

        self.docker = docker
        self.client = self.docker.DockerClient(base_url="unix://var/run/docker.sock")

    @staticmethod
    def is_inside_docker():
        return os.path.exists("/.dockerenv")

    def set_container_stats(self):
        for service_name in self.stats.keys():
            try:
                container = self.client.containers.get(service_name)
                self.stats[service_name] = DockerStats(container)
            except self.docker.errors.NotFound:
                self.stats[service_name] = "Container not found"
