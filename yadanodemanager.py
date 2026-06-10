import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


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
        machine = os.uname().machine
        arch = "aarch64" if machine in ("aarch64", "arm64") else "x86_64"
        compose_url = (
            f"https://github.com/docker/compose/releases/latest/download/"
            f"docker-compose-linux-{arch}"
        )
        result = subprocess.run(
            [
                "curl",
                "-fsSL",
                compose_url,
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

    def get_latest_release_tag(self):
        """Return the tag_name of the latest GitHub Release, or None on failure.

        A GitHub Release only exists after CI has built and pushed the Docker
        image, so this naturally avoids the race condition of checking git tags
        directly.
        """
        try:
            url = "https://api.github.com/repos/pdxwebdev/yadacoin/releases/latest"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/vnd.github+json")
            req.add_header("X-GitHub-Api-Version", "2022-11-28")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())["tag_name"]
        except Exception as e:
            print(f"Warning: could not fetch latest release from GitHub: {e}")
            return None

    def git_pull_latest(self):
        os.chdir(self.repo_path)

        latest_tag = self.get_latest_release_tag()
        if not latest_tag:
            return False

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

        if latest_tag != current_tag:
            print(
                f"New release available: {latest_tag} (was: {current_tag}). Updating..."
            )
            subprocess.run(["git", "fetch", "origin", "--tags"])
            subprocess.run(["git", "stash"])
            subprocess.run(["git", "checkout", latest_tag])
            subprocess.run(["git", "stash", "pop"])
            self.ensure_compose_v2()
            return True

        return False

    def deduplicate_networks(self):
        """Remove duplicate Docker networks that cause 'ambiguous' errors.

        Uses exact label matching to find only networks created by this
        compose project, then removes all but the most recently created one.
        If label filtering returns nothing (older Docker), falls back to name
        filtering and removes all matches so compose can recreate cleanly.
        """
        try:
            # Prefer label-based lookup (exact project match, no substring hits)
            nets = (
                subprocess.check_output(
                    [
                        "docker",
                        "network",
                        "ls",
                        "--filter",
                        "label=com.docker.compose.project=yadacoin",
                        "--filter",
                        "label=com.docker.compose.network=default",
                        "-q",
                    ],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
                .splitlines()
            )
            if not nets:
                # Fallback for older Docker without compose labels
                nets = (
                    subprocess.check_output(
                        [
                            "docker",
                            "network",
                            "ls",
                            "--filter",
                            "name=yadacoin_default",
                            "-q",
                        ],
                        stderr=subprocess.DEVNULL,
                    )
                    .decode()
                    .strip()
                    .splitlines()
                )
            if len(nets) > 1:
                print(
                    f"Found {len(nets)} duplicate networks. Removing all so compose can recreate."
                )
                for net_id in nets:
                    subprocess.run(
                        ["docker", "network", "rm", net_id],
                        stderr=subprocess.DEVNULL,
                    )
        except Exception as e:
            print(f"Warning: network deduplication error: {e}")

    def pull_and_restart(self):
        self.deduplicate_networks()
        subprocess.run(
            self.compose_cmd + ["down", "--remove-orphans"],
            cwd=self.repo_path,
        )
        subprocess.run(
            self.compose_cmd + ["pull", self.service_name],
            cwd=self.repo_path,
        )
        subprocess.run(
            self.compose_cmd + ["up", "-d", self.service_name],
            cwd=self.repo_path,
        )
        subprocess.run(
            ["docker", "image", "prune", "-f"],
            cwd=self.repo_path,
        )

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
        self.deduplicate_networks()  # Fix any duplicate networks before touching compose
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
                        "New release detected. Pulling image and restarting container..."
                    )
                    self.pull_and_restart()
                    print("Restarting node manager to pick up source changes...")
                    os.execv(sys.executable, [sys.executable] + sys.argv)
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
