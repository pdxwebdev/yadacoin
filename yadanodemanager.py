import os
import subprocess
import time


def _detect_compose_cmd():
    """Return the docker compose command list for the current environment.

    Prefers Compose V2 ('docker compose') when available, falls back to the
    legacy 'docker-compose' v1 binary so existing nodes are not broken.
    """
    try:
        subprocess.check_output(
            ["docker", "compose", "version"],
            stderr=subprocess.DEVNULL,
        )
        return ["docker", "compose"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ["docker-compose"]


class YadaNodeManager:
    def __init__(self):
        self.repo_path = os.path.dirname(os.path.abspath(__file__))
        self.service_name = "yada-node"
        self.update_interval_seconds = 3600  # how often to check for git updates
        self.health_check_interval_seconds = 30  # how often to check container health
        self.compose_cmd = _detect_compose_cmd()

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

    def ensure_compose_v2(self):
        """Install Docker Compose V2 plugin if only v1 is present.

        Called automatically after a successful git update so that existing
        nodes migrate to V2 without requiring manual intervention.
        """
        try:
            subprocess.check_output(
                ["docker", "compose", "version"],
                stderr=subprocess.DEVNULL,
            )
            return  # V2 already available
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        print("Docker Compose V2 not found. Installing plugin...")
        plugin_dir = "/usr/local/lib/docker/cli-plugins"
        plugin_path = os.path.join(plugin_dir, "docker-compose")
        os.makedirs(plugin_dir, exist_ok=True)
        result = subprocess.run(
            [
                "curl",
                "-fsSL",
                "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64",
                "-o",
                plugin_path,
            ]
        )
        if result.returncode == 0:
            os.chmod(plugin_path, 0o755)
            self.compose_cmd = ["docker", "compose"]
            print("Docker Compose V2 installed successfully.")
        else:
            print("Failed to install Docker Compose V2. Continuing with v1.")

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
            self.ensure_compose_v2()
            return True

        return False

    def cleanup_docker(self):
        """Remove dangling images left over from previous builds."""
        try:
            subprocess.run(
                ["docker", "image", "prune", "-f"],
                cwd=self.repo_path,
            )
            print("Docker cleanup complete.")
        except Exception as e:
            print(f"Warning: Docker cleanup encountered an error: {e}")

    def rebuild_docker_image(self):
        subprocess.run(
            self.compose_cmd + ["down"],
            cwd=self.repo_path,
        )
        subprocess.run(
            self.compose_cmd + ["build", self.service_name],
            cwd=self.repo_path,
        )
        subprocess.run(
            self.compose_cmd + ["up", "-d", self.service_name],
            cwd=self.repo_path,
        )
        self.cleanup_docker()

    def start_docker_image(self):
        subprocess.run(
            self.compose_cmd + ["up", "-d", self.service_name],
            cwd=self.repo_path,
        )

    def is_mongodump_directory_present(self):
        mongodump_path = os.path.join(self.repo_path, "dump")
        return os.path.exists(mongodump_path)

    def start_restore_service(self):
        subprocess.run(
            self.compose_cmd + ["up", "restore"],
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
        last_update_check = 0
        while True:
            if not self.ensure_container_running():
                print(
                    f"Container {self.service_name} is not running. Starting it up..."
                )
                self.start_docker_image()
            # Only check for git updates at the longer interval
            if time.time() - last_update_check >= self.update_interval_seconds:
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
                last_update_check = time.time()

            time.sleep(self.health_check_interval_seconds)


if __name__ == "__main__":
    manager = YadaNodeManager()
    manager.run()
