import argparse
import json
import os
import subprocess
import time


class DockerManager:
    def __init__(self, repo_path, service_name, config_path):
        self.repo_path = repo_path
        self.service_name = service_name
        self.config = self.load_config(config_path)

    def load_config(self, path):
        with open(path, "r") as file:
            return json.load(file)

    def update_and_restart(self):
        os.chdir(self.repo_path)
        result = subprocess.run(["git", "pull"], capture_output=True, text=True)
        if "Already up to date." not in result.stdout:
            self.restart_container()
        else:
            print("No need to restart, codebase is up to date.")

    def restart_container(self):
        subprocess.run(["docker-compose", "down"], cwd=self.repo_path)
        subprocess.run(["docker-compose", "up", "-d"], cwd=self.repo_path)

    def is_container_running(self):
        result = subprocess.run(
            ["docker", "ps", "-f", f"name={self.service_name}"],
            capture_output=True,
            text=True,
        )
        return self.service_name in result.stdout

    def ensure_container_running(self):
        if not self.is_container_running():
            print(f"Container {self.service_name} is not running. Starting it up...")
            self.restart_container()

    def run(self):
        try:
            self.ensure_container_running()
            while True:
                self.update_and_restart()
                time.sleep(3600)  # hardcoded interval of 1 hour
        except KeyboardInterrupt:
            print("Script terminated by user.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Docker Manager script.")
    parser.add_argument(
        "config_file",
        type=str,
        help="Path to the config file relative to the script directory.",
    )
    args = parser.parse_args()

    script_directory = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_directory, args.config_file)

    manager = DockerManager(script_directory, "yada-node", config_path)
    manager.run()
