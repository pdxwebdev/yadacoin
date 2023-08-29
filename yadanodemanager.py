import os
import subprocess
import time
import uuid


class YadaNodeManager:
    def __init__(self):
        self.repo_path = "/etc/yadacoin"
        self.base_project_name = "yadanodemanager"  # Base project name.
        self.project_name = self.generate_project_name()  # Generate project name once
        self.service_name = "yada-node"
        self.update_interval_seconds = 3600

    def generate_project_name(self):
        unique_id = uuid.uuid4().hex
        return f"{self.base_project_name}_{unique_id}"

    def is_project_running(self):
        try:
            output = (
                subprocess.check_output(
                    [
                        "docker-compose",
                        "-p",
                        self.project_name,
                        "ps",
                        "-q",
                        self.service_name,
                    ]
                )
                .decode()
                .strip()
            )
            return bool(output)
        except:
            return False

    def git_pull_latest(self):
        os.chdir(self.repo_path)
        subprocess.run(
            ["git", "fetch", "origin", "master", "--tags"]
        )  # Fetch changes from master branch and update tags
        original_commit = (
            subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        )
        subprocess.run(["git", "stash"])  # Stash any uncommitted changes
        subprocess.run(
            ["git", "pull", "origin", "master"]
        )  # Pull latest changes from master branch
        subprocess.run(["git", "stash", "pop"])  # Pop the stashed changes
        latest_commit = (
            subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        )
        return original_commit != latest_commit

    def docker_compose_up(self):
        subprocess.run(
            ["docker-compose", "-p", self.project_name, "up", "-d", self.service_name],
            cwd=self.repo_path,
        )

    def rebuild_docker_image(self):
        subprocess.run(
            ["docker-compose", "-p", self.project_name, "down", "yada-node"],
            cwd=self.repo_path,
        )
        subprocess.run(
            ["docker-compose", "-p", self.project_name, "build", "yada-node"],
            cwd=self.repo_path,
        )
        subprocess.run(
            ["docker-compose", "-p", self.project_name, "up", "-d", "yada-node"],
            cwd=self.repo_path,
        )

    def start_docker_image(self):
        subprocess.run(
            ["docker-compose", "-p", self.project_name, "up", "-d", "yada-node"],
            cwd=self.repo_path,
        )

    def ensure_project_running(self):
        if not self.is_project_running():
            print(f"Project {self.project_name} is not running. Starting it up...")
            self.start_docker_image()

    def run(self):
        while True:
            self.ensure_project_running()
            if self.git_pull_latest():
                print(
                    "Codebase updated. Rebuilding Docker image and restarting container..."
                )
                self.rebuild_docker_image()
            else:
                print(
                    "No updates found. Checking again in {} seconds.".format(
                        self.update_interval_seconds
                    )
                )

            time.sleep(self.update_interval_seconds)


if __name__ == "__main__":
    manager = YadaNodeManager()
    manager.run()
