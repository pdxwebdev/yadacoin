"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os
import shutil
import signal
import subprocess
import time

SYSTEMD_UNITS = ("yadanodemanager", "yadanode")


def command_kind(command):
    lowered = command.lower()
    if "python" not in lowered:
        return None
    if "yadanodemanager.py" in command:
        return "manager"
    if "yadacoin/app.py" in command or "yadacoin.app" in lowered:
        return "node"
    return None


def matching_processes(ps_output, own_pid=None):
    own_pid = os.getpid() if own_pid is None else own_pid
    found = []
    for line in ps_output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        kind = command_kind(parts[1])
        if kind and pid > 1 and pid != own_pid:
            found.append((pid, kind, parts[1]))
    return found


def _systemctl_active(unit):
    if not shutil.which("systemctl"):
        return False
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", unit],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _run(argv):
    return subprocess.run(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _ps_output():
    return subprocess.check_output(["ps", "ax", "-o", "pid=,command="], text=True)


def _running_node_containers():
    if not shutil.which("docker"):
        return None
    try:
        out = subprocess.check_output(
            [
                "docker",
                "ps",
                "-q",
                "--filter",
                "name=yada-node",
                "--filter",
                "status=running",
            ],
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.output or "").strip() or str(exc)
        raise RuntimeError("docker ps failed: {}".format(detail))
    return [line.strip() for line in out.splitlines() if line.strip()]


def _wait_until_clear(timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not matching_processes(_ps_output()):
            return True
        time.sleep(0.4)
    return not matching_processes(_ps_output())


def pause_writers(log):
    stopped = {
        "units": [],
        "containers": [],
        "pids": [],
        "changed": False,
        "blocked": None,
        "message": "",
    }
    notes = []
    try:
        for unit in SYSTEMD_UNITS:
            if not _systemctl_active(unit):
                continue
            log("stopping systemd unit {}".format(unit))
            result = _run(["systemctl", "stop", unit])
            if (result.stdout or "").strip():
                log(result.stdout.strip())
            if result.returncode != 0 or _systemctl_active(unit):
                stopped["blocked"] = (
                    "Could not stop systemd unit {}. " "Rerun ./node-dashboard as root."
                ).format(unit)
                return stopped
            stopped["units"].append(unit)
            stopped["changed"] = True
            notes.append("stopped {}".format(unit))

        containers = _running_node_containers()
        if containers is None:
            log("docker is not available; skipped container check")
        else:
            for cid in containers:
                log("stopping container {}".format(cid))
                result = _run(["docker", "stop", "-t", "20", cid])
                if (result.stdout or "").strip():
                    log(result.stdout.strip())
                if result.returncode != 0:
                    stopped["blocked"] = "docker stop failed for {}".format(cid)
                    return stopped
                stopped["containers"].append(cid)
                stopped["changed"] = True
                notes.append("stopped container {}".format(cid[:12]))

        leftover = matching_processes(_ps_output())
        for pid, kind, cmd in leftover:
            log("stopping {} pid {} ({})".format(kind, pid, cmd[:160]))
            try:
                os.kill(pid, signal.SIGTERM)
            except PermissionError:
                stopped["blocked"] = (
                    "Permission denied stopping pid {}. Rerun ./node-dashboard "
                    "as the node user or root."
                ).format(pid)
                return stopped
            except ProcessLookupError:
                continue
            stopped["pids"].append(pid)
            stopped["changed"] = True
        if leftover and not _wait_until_clear(15):
            still = matching_processes(_ps_output())
            stopped["blocked"] = "Node process still running: {}".format(
                ", ".join(str(pid) for pid, _kind, _cmd in still)
            )
            return stopped
        if leftover:
            notes.append("stopped local node process")
    except Exception as exc:
        stopped["blocked"] = str(exc)
        return stopped

    if stopped["changed"]:
        stopped["message"] = "; ".join(notes)
    else:
        stopped["message"] = "No running node or node manager found"
    return stopped


def resume_writers(paused, log):
    messages = []
    errors = []
    for cid in paused.get("containers") or []:
        result = _run(["docker", "start", cid])
        if (result.stdout or "").strip():
            log(result.stdout.strip())
        if result.returncode != 0:
            errors.append("docker start {} failed".format(cid[:12]))
        else:
            messages.append("started container {}".format(cid[:12]))
    for unit in paused.get("units") or []:
        result = _run(["systemctl", "start", unit])
        if (result.stdout or "").strip():
            log(result.stdout.strip())
        if result.returncode != 0:
            errors.append("systemctl start {} failed".format(unit))
        else:
            messages.append("started {}".format(unit))
    if paused.get("pids"):
        messages.append("local node process was not restarted")
    if errors:
        return False, "; ".join(errors + messages)
    if not messages:
        return True, "Nothing to resume"
    return True, "; ".join(messages)
