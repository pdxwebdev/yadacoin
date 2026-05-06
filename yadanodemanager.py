import os
import subprocess
import time


class YadaNodeManager:
    def __init__(self):
        self.repo_path = os.path.dirname(os.path.abspath(__file__))
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
        subprocess.run(["git", "fetch", "origin", "--tags"])

        # Tag the node is currently running on (None if not on a tag)
        try:
            current_tag = (
                subprocess.check_output(
                    ["git", "describe", "--tags", "--exact-match", "HEAD"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except subprocess.CalledProcessError:
            current_tag = None

        # Highest version tag available locally (after fetch)
        try:
            latest_tag = (
                subprocess.check_output(["git", "tag", "--sort=-version:refname"])
                .decode()
                .strip()
                .splitlines()[0]
            )
        except (subprocess.CalledProcessError, IndexError):
            latest_tag = None

        if latest_tag and latest_tag != current_tag:
            print(f"New tag available: {latest_tag} (was: {current_tag}). Updating...")
            subprocess.run(["git", "stash"])
            subprocess.run(["git", "checkout", latest_tag])
            subprocess.run(["git", "stash", "pop"])
            return True

        return False

    def rebuild_docker_image(self):
        subprocess.run(
            ["docker-compose", "down"],
            cwd=self.repo_path,
        )
        subprocess.run(
            ["docker-compose", "build", "--no-cache", self.service_name],
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

    def is_mongodump_directory_present(self):
        mongodump_path = os.path.join(self.repo_path, "dump")
        return os.path.exists(mongodump_path)

    def start_restore_service(self):
        subprocess.run(
            ["docker-compose", "up", "restore"],
            cwd=self.repo_path,
        )
        mongodump_path = os.path.join(self.repo_path, "dump")
        subprocess.run(
            ["rm", "-rf", mongodump_path],
            cwd=self.repo_path,
        )
        print(f"Restore from bootstrap data complete.")

    def run(self):
        self.stop_previous_containers()  # Stop and remove previous containers
        if self.is_mongodump_directory_present():
            self.start_restore_service()  # Start the restore service if directory exists
            print(f"Restoring from bootstrap data")
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
