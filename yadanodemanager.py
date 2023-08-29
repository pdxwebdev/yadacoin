import os
import subprocess
import time


class YadaNodeManager:
    def __init__(self):
        self.repo_path = "/etc/yadacoin"
        self.service_name = "yada-node"
        self.update_interval_seconds = 3600

    def stop_previous_containers(self):
        try:
            output = (
                subprocess.check_output(
                    ["docker", "ps", "-aq", "-f", f"name={self.service_name}"]
                )
                .decode()
                .strip()
            )
            if output:
                subprocess.run(
                    [
                        "docker",
                        "rm",
                        "-f",
                        output,
                    ],  # Stop and remove previous containers
                    cwd=self.repo_path,
                )
        except Exception as e:
            print(f"Error while stopping previous containers: {e}")

    def ensure_container_running(self):
        try:
            output = (
                subprocess.check_output(
                    ["docker", "ps", "-q", "-f", f"name={self.service_name}"]
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

    def rebuild_docker_image(self):
        subprocess.run(
            ["docker-compose", "down", self.service_name],
            cwd=self.repo_path,
        )
        subprocess.run(
            ["docker-compose", "build", self.service_name],
            cwd=self.repo_path,
        )
        subprocess.run(
            ["docker-compose", "up", "-d", self.service_name],
            cwd=self.repo_path,
        )

    def start_docker_image(self):
        subprocess.run(
            ["docker-compose", "up", "-d", self.service_name],
            cwd=self.repo_path,
        )

    def run(self):
        self.stop_previous_containers()  # Stop and remove previous containers
        while True:
            if not self.ensure_container_running():
                print(
                    f"Container {self.service_name} is not running. Starting it up..."
                )
                self.start_docker_image()
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
