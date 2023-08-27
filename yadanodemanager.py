import os
import subprocess
import time


class YadaNodeManager:
    def __init__(self):
        self.repo_path = "/etc/yadacoin"
        self.container_name = "yada-node"
        self.update_interval_seconds = 3600

    def is_container_running(self):
        try:
            output = (
                subprocess.check_output(
                    ["docker", "ps", "-q", "-f", f"name={self.container_name}"]
                )
                .decode()
                .strip()
            )
            return bool(output)
        except:
            return False

    def git_pull_latest(self):
        os.chdir(self.repo_path)
        original_commit = (
            subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        )
        subprocess.run(
            ["git", "pull", "origin", "master", "--tags"]
        )  # Pull changes from master branch and update tags
        latest_commit = (
            subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        )
        return original_commit != latest_commit

    def restart_container(self):
        subprocess.run(["docker-compose", "down"], cwd=self.repo_path)
        subprocess.run(["docker-compose", "up", "-d"], cwd=self.repo_path)

    def ensure_container_running(self):
        if not self.is_container_running():
            print(f"Container {self.container_name} is not running. Starting it up...")
            self.restart_container()

    def run(self):
        while True:
            self.ensure_container_running()
            if self.git_pull_latest():
                print("Codebase updated. Restarting Docker container...")
                self.restart_container()
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
