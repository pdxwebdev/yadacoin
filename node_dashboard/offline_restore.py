"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from node_dashboard.job import read_job_state, write_job_state
from node_dashboard.restore import (
    connect_client,
    mongorestore_plan,
    run_command,
    truncate_consensus,
)
from node_dashboard.settings import MongoTarget, tcp_open


def wait_until_down(host, port, probe=tcp_open, sleep=time.sleep, timeout=180):
    deadline = time.time() + timeout
    misses = 0
    while time.time() < deadline:
        if probe(host, port, timeout=0.5):
            misses = 0
        else:
            misses += 1
            if misses >= 3:
                return True
        sleep(0.4)
    return False


def _target(raw):
    return MongoTarget(
        raw.get("configured_host"),
        raw.get("connect_host"),
        raw.get("port") or 27017,
        raw.get("database"),
        raw.get("username") or "",
        raw.get("password") or "",
        raw.get("auth_source") or "admin",
        raw.get("note"),
    )


def _log(job, step, line):
    job["logs"] = list(job.get("logs") or [])
    job["logs"].append(
        {
            "id": len(job["logs"]) + 1,
            "ts": time.time(),
            "step": step,
            "line": line,
        }
    )


def _step(job, step_id, status=None, message=None):
    for step in job.get("steps") or []:
        if step.get("id") != step_id:
            continue
        if status is not None:
            step["status"] = status
        if message is not None:
            step["message"] = message
        return


def _save(path, job):
    write_job_state(path, job)


def _fail(path, job, step, message):
    job["status"] = "failed"
    job["error"] = message
    job["finished_at"] = time.time()
    _step(job, step, "failed", message)
    _log(job, step, message)
    _save(path, job)


def _restart(spec):
    argv = spec.get("argv") or []
    if not argv:
        return
    subprocess.Popen(
        argv,
        cwd=spec.get("cwd") or None,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _serve_status(path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?", 1)[0] not in ("/job", "/operator/api/job"):
                self.send_response(404)
                self.end_headers()
                return
            job = read_job_state(path) or {}
            body = json.dumps({"job": job}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    try:
        server = ThreadingHTTPServer(("127.0.0.1", 8102), Handler)
    except OSError:
        return None
    threading.Thread(
        target=server.serve_forever, name="restore-status", daemon=True
    ).start()
    return server


def run(path):
    job = read_job_state(path)
    if not job:
        print("restore worker: no job at {}".format(path), flush=True)
        return 1
    _serve_status(path)
    print("restore worker started pid {}".format(os.getpid()), flush=True)
    handoff = (job.get("result") or {}).get("handoff") or {}
    host = handoff.get("node_host") or "127.0.0.1"
    port = int(handoff.get("node_port") or 0)
    if not wait_until_down(host, port):
        _fail(path, job, "restore", "Node did not stop before mongorestore")
        _restart(handoff.get("restart") or {})
        return 1
    _log(job, "restore", "Node stopped responding. Starting mongorestore.")
    _step(job, "restore", "running", "Node is down. Starting mongorestore.")
    _save(path, job)
    target = _target(handoff.get("target") or {})
    try:
        plan = mongorestore_plan(
            handoff.get("dump_dir"), target, handoff.get("source_db")
        )
    except Exception as exc:
        _fail(path, job, "restore", str(exc))
        _restart(handoff.get("restart") or {})
        return 1
    code = run_command(plan["argv"], lambda line: _log(job, "restore", line))
    _save(path, job)
    if code != 0:
        _fail(path, job, "restore", "mongorestore exited {}".format(code))
        _restart(handoff.get("restart") or {})
        return code
    _step(job, "restore", "succeeded", "mongorestore finished")
    _log(job, "restore", "mongorestore exited 0")
    _step(job, "truncate", "running", "Deleting consensus documents")
    _save(path, job)
    client = None
    try:
        client = connect_client(target, timeout_ms=10000)
        stats = truncate_consensus(client[target.database])
    except Exception as exc:
        _fail(path, job, "truncate", str(exc))
        _restart(handoff.get("restart") or {})
        return 1
    finally:
        if client is not None:
            client.close()
    job.setdefault("result", {})
    job["result"]["consensus_before"] = stats["before"]
    job["result"]["consensus_deleted"] = stats["deleted"]
    job["result"]["consensus_after"] = stats["after"]
    job["result"]["reloaded"] = True
    message = "Removed {:,} consensus documents · remaining {:,}".format(
        stats["deleted"], stats["after"]
    )
    _log(job, "truncate", message)
    _step(job, "truncate", "succeeded", message)
    work = handoff.get("work")
    _step(job, "cleanup", "running", "Removing temporary files")
    if work:
        try:
            shutil.rmtree(work)
            _step(job, "cleanup", "succeeded", "Removed temporary files")
            _log(job, "cleanup", "Removed {}".format(work))
        except Exception as exc:
            warning = "Could not remove {}: {}".format(work, exc)
            job["warning"] = warning
            _step(job, "cleanup", "failed", warning)
            _log(job, "cleanup", warning)
    job["result"]["restarting"] = True
    job["result"]["stopping"] = False
    _step(job, "restart", "running", "Restarting the node. Do not refresh this page.")
    _log(job, "restart", "Restarting the node. Do not refresh this page.")
    job["status"] = "succeeded"
    job["finished_at"] = time.time()
    _save(path, job)
    _restart(handoff.get("restart") or {})
    return 0


def main(argv=None):
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print(
            "usage: python -m node_dashboard.offline_restore <job.json>",
            file=sys.stderr,
        )
        return 2
    try:
        return run(argv[0])
    except Exception as exc:
        print("restore worker failed: {}".format(exc), flush=True)
        job = read_job_state(argv[0])
        if job:
            _fail(argv[0], job, "restore", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
