import json
import os
import shutil
import subprocess
import sys
import tempfile
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

    def _legacy_plugin_image(self):
        try:
            rows = (
                subprocess.check_output(
                    ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"]
                )
                .decode()
                .splitlines()
            )
        except Exception:
            return None
        for name in ("yadacoin_yada-node:latest", "yadacoin-yada-node:latest"):
            if name in rows:
                return name
        for row in rows:
            if row.startswith("yadacoin_yada-node:"):
                return row
        return None

    def _plugin_catalog(self):
        path = os.path.join(self.repo_path, "plugins.txt")
        entries = []
        if not os.path.isfile(path):
            return entries
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "\t" not in line:
                    continue
                name, url = line.split("\t", 1)
                name = name.strip()
                url = url.strip()
                if not name or not url:
                    continue
                if url.startswith("git@github.com:"):
                    url = "https://github.com/" + url[len("git@github.com:") :]
                entries.append((name, url))
        return entries

    def _is_plugin_checkout(self, dest):
        return os.path.isdir(os.path.join(dest, ".git")) or os.path.isfile(
            os.path.join(dest, ".git")
        )

    def ensure_plugin_repos(self):
        """Install every catalog plugin as a git checkout.

        A copied directory is not current just because it has handlers.py.
        A failed clone leaves the existing directory in place and does not
        stop the deploy.
        """
        dest_root = os.path.join(self.repo_path, "plugins")
        os.makedirs(dest_root, exist_ok=True)
        for name, url in self._plugin_catalog():
            dest = os.path.join(dest_root, name)
            if self._is_plugin_checkout(dest):
                subprocess.run(
                    ["git", "-C", dest, "pull", "--ff-only"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                continue
            tmp = tempfile.mkdtemp()
            try:
                cloned = os.path.join(tmp, name)
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", url, cloned],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if result.returncode != 0 or not os.path.isfile(
                    os.path.join(cloned, "handlers.py")
                ):
                    print(f"skip {name} (clone failed)")
                    continue
                if os.path.isdir(dest):
                    shutil.rmtree(dest)
                shutil.copytree(cloned, dest)
                print(f"installed plugin {name}")
            except Exception as e:
                print(f"Warning: plugin {name} install failed: {e}")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        self._install_recovered_plugins(dest_root)
        self.install_plugin_requirements()

    def install_plugin_requirements(self):
        """Install each plugin requirements.txt inside the running node.

        Packages land in plugins/.pydeps, which the app adds to sys.path.
        A failed install does not stop the deploy.
        """
        try:
            cid = (
                subprocess.check_output(
                    ["docker", "ps", "-q", "-f", f"name={self.service_name}"]
                )
                .decode()
                .strip()
                .splitlines()
            )
        except Exception:
            return
        if not cid:
            return
        cid = cid[0]
        dest_root = os.path.join(self.repo_path, "plugins")
        if not os.path.isdir(dest_root):
            return
        subprocess.run(
            ["docker", "exec", cid, "mkdir", "-p", "/app/plugins/.pydeps"],
            stderr=subprocess.DEVNULL,
        )
        for name in os.listdir(dest_root):
            if not os.path.isfile(os.path.join(dest_root, name, "requirements.txt")):
                continue
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    cid,
                    "pip",
                    "install",
                    "-r",
                    f"/app/plugins/{name}/requirements.txt",
                    "--target",
                    "/app/plugins/.pydeps",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if result.returncode != 0:
                print(f"Warning: plugin {name} requirements failed")
            else:
                print(f"installed requirements for {name}")

    def recover_legacy_plugins(self):
        """Copy /app/plugins out of the pre-split image before it is removed.

        Missing plugin directories are filled in. Existing directories are left
        alone. No old image, or a failed copy, does not stop the deploy.
        """
        image = self._legacy_plugin_image()
        if not image:
            return False
        dest = os.path.join(self.repo_path, "plugins")
        os.makedirs(dest, exist_ok=True)
        copied = False
        name = "yada-plugin-recover"
        try:
            subprocess.run(["docker", "rm", "-f", name], stderr=subprocess.DEVNULL)
            created = subprocess.run(
                ["docker", "create", "--name", name, image],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if created.returncode != 0:
                return False
            with tempfile.TemporaryDirectory() as tmp:
                extracted = os.path.join(tmp, "plugins")
                copied_out = subprocess.run(
                    ["docker", "cp", name + ":/app/plugins", extracted],
                    stderr=subprocess.DEVNULL,
                )
                if copied_out.returncode != 0 or not os.path.isdir(extracted):
                    return False
                for plugin_name in os.listdir(extracted):
                    src = os.path.join(extracted, plugin_name)
                    target = os.path.join(dest, plugin_name)
                    if not os.path.isdir(src) or os.path.exists(target):
                        continue
                    shutil.copytree(src, target)
                    copied = True
                    print(f"Recovered plugin {plugin_name} from {image}")
        except Exception as e:
            print(f"Warning: legacy plugin recovery failed: {e}")
            return False
        finally:
            subprocess.run(["docker", "rm", "-f", name], stderr=subprocess.DEVNULL)
        if copied:
            self._install_recovered_plugins(dest)
        return copied

    def _install_recovered_plugins(self, dest):
        try:
            cid = (
                subprocess.check_output(
                    ["docker", "ps", "-q", "-f", f"name={self.service_name}"]
                )
                .decode()
                .strip()
                .splitlines()
            )
        except Exception:
            return
        if not cid:
            return
        cid = cid[0]
        installed = False
        for mount in ("/app/plugins", "/plugins"):
            for plugin_name in os.listdir(dest):
                src = os.path.join(dest, plugin_name)
                if not os.path.isdir(src):
                    continue
                exists = subprocess.run(
                    ["docker", "exec", cid, "test", "-e", f"{mount}/{plugin_name}"],
                    stderr=subprocess.DEVNULL,
                )
                if exists.returncode == 0:
                    continue
                subprocess.run(
                    ["docker", "exec", cid, "mkdir", "-p", mount],
                    stderr=subprocess.DEVNULL,
                )
                result = subprocess.run(
                    ["docker", "cp", src, f"{cid}:{mount}/{plugin_name}"],
                    stderr=subprocess.DEVNULL,
                )
                installed = installed or result.returncode == 0
        if installed:
            subprocess.run(["docker", "restart", cid], stderr=subprocess.DEVNULL)

    def pull_and_restart(self):
        self.recover_legacy_plugins()
        self.ensure_plugin_repos()
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
        self._install_recovered_plugins(os.path.join(self.repo_path, "plugins"))
        self.install_plugin_requirements()
        subprocess.run(
            ["docker", "image", "prune", "-f"],
            cwd=self.repo_path,
        )

    def start_docker_image(self):
        subprocess.run(
            self.compose_cmd + ["up", "-d", self.service_name],
            cwd=self.repo_path,
        )
        self._install_recovered_plugins(os.path.join(self.repo_path, "plugins"))
        self.install_plugin_requirements()

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
        self.recover_legacy_plugins()
        self.ensure_plugin_repos()
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
