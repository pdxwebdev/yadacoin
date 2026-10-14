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
import threading
import time
import uuid

from node_dashboard import restore
from node_dashboard.settings import (
    BOOTSTRAP_URL,
    load_target,
    redact_text,
    resolve_target,
    tcp_open,
)

STEPS = (
    ("prepare", "Check database"),
    ("download", "Download bootstrap"),
    ("extract", "Extract archive"),
    ("restore", "mongorestore"),
    ("truncate", "Truncate consensus"),
    ("cleanup", "Cleanup"),
    ("restart", "Restart node"),
)


class JobError(Exception):
    def __init__(self, step, message):
        super(JobError, self).__init__(message)
        self.step = step


class ReloadJob(object):
    def __init__(self, repo_root, config_path, publish, target=None, on_restart=None):
        self.repo_root = repo_root
        self.config_path = config_path
        self.publish = publish
        self._target = target
        self.on_restart = on_restart
        self.id = time.strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
        self.status = "running"
        self.error = None
        self.warning = None
        self.started_at = time.time()
        self.finished_at = None
        self.step_order = [step_id for step_id, _label in STEPS]
        self.steps = {
            step_id: {
                "id": step_id,
                "label": label,
                "status": "pending",
                "message": "",
                "progress": None,
            }
            for step_id, label in STEPS
        }
        self.logs = []
        self.result = {"bootstrap_url": BOOTSTRAP_URL}
        self.current_step = "prepare"
        self._lock = threading.Lock()
        self._log_seq = 0
        self._last_output = None
        self._secrets = []

    def public(self):
        with self._lock:
            return {
                "id": self.id,
                "status": self.status,
                "error": self.error,
                "warning": self.warning,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "steps": [
                    {
                        "id": self.steps[step_id]["id"],
                        "label": self.steps[step_id]["label"],
                        "status": self.steps[step_id]["status"],
                        "message": self.steps[step_id]["message"],
                        "progress": (
                            dict(self.steps[step_id]["progress"])
                            if self.steps[step_id]["progress"]
                            else None
                        ),
                    }
                    for step_id in self.step_order
                ],
                "logs": list(self.logs[-1500:]),
                "result": dict(self.result),
            }

    def log(self, step, line):
        text = restore.clean_line(str(line))
        if not text:
            return
        if len(text) > 2000:
            text = text[:2000] + "…"
        with self._lock:
            text = redact_text(text, self._secrets)
            self._log_seq += 1
            entry = {
                "id": self._log_seq,
                "ts": time.time(),
                "step": step,
                "line": text,
            }
            self.logs.append(entry)
            if len(self.logs) > 2000:
                del self.logs[:-2000]
        self.publish({"type": "log", "entry": entry})

    def set_step(self, step_id, status=None, message=None, progress=None):
        self.current_step = step_id
        with self._lock:
            step = self.steps[step_id]
            if status is not None:
                step["status"] = status
            if message is not None:
                step["message"] = message
            if progress is not None:
                step["progress"] = progress
            payload = {
                "id": step["id"],
                "label": step["label"],
                "status": step["status"],
                "message": step["message"],
                "progress": dict(step["progress"]) if step["progress"] else None,
            }
        self.publish({"type": "step", "step": payload})

    def _skip_after(self, step_id):
        seen = False
        for candidate in self.step_order:
            if candidate == step_id:
                seen = True
                continue
            if seen and self.steps[candidate]["status"] == "pending":
                self.set_step(candidate, "skipped", "Skipped")

    def fail(self, step, message):
        if self.status != "running":
            return
        message = redact_text(str(message), self._secrets)
        work = self.result.get("work_dir")
        if work:
            self.log(step, "Keeping {}".format(work))
        self.set_step(step, "failed", message)
        self.log(step, message)
        self._skip_after(step)
        self.status = "failed"
        self.error = message
        self.finished_at = time.time()
        self.publish(
            {
                "type": "job",
                "status": self.status,
                "error": self.error,
                "warning": self.warning,
                "finished_at": self.finished_at,
                "result": dict(self.result),
            }
        )

    def succeed(self):
        self.status = "succeeded"
        self.finished_at = time.time()
        self.publish(
            {
                "type": "job",
                "status": self.status,
                "error": None,
                "warning": self.warning,
                "finished_at": self.finished_at,
                "result": dict(self.result),
            }
        )

    def run(self):
        try:
            self._run()
        except JobError as exc:
            self.fail(exc.step, str(exc))
        except Exception as exc:
            self.fail(self.current_step or "prepare", str(exc))

    def _run(self):
        self.set_step("prepare", "running", "Reading config")
        try:
            if self._target is not None:
                target = self._target
            else:
                target = resolve_target(load_target(self.config_path))
        except Exception as exc:
            raise JobError("prepare", str(exc))
        self._secrets = target.secrets()
        self.result["database"] = target.database
        self.result["host"] = target.connect_host
        self.result["port"] = target.port
        tool = restore.restore_tool()
        self.result["tool"] = tool
        try:
            import pymongo  # noqa: F401
        except ImportError:
            raise JobError(
                "prepare",
                "pymongo is required to read status and truncate consensus",
            )
        if tool == "missing":
            raise JobError(
                "prepare",
                "mongorestore is not installed and docker is not available. "
                "Install MongoDB database tools or Docker.",
            )
        self.log(
            "prepare",
            "Target {} @ {}:{}".format(
                target.database, target.connect_host, target.port
            ),
        )
        if target.note:
            self.log("prepare", target.note)
        if not tcp_open(target.connect_host, target.port):
            raise JobError(
                "prepare",
                "MongoDB is not accepting connections at {}:{}. "
                "Start the database before reloading.".format(
                    target.connect_host, target.port
                ),
            )
        tool_label = (
            "mongorestore on PATH" if tool == "local" else "docker mongo:latest"
        )
        self.set_step(
            "prepare",
            "succeeded",
            "MongoDB reachable at {}:{} · {}".format(
                target.connect_host, target.port, tool_label
            ),
        )

        work = os.path.join(self.repo_root, ".node-dashboard-work", self.id)
        archive = os.path.join(work, "bootstrap.tar.gz")
        extracted = os.path.join(work, "extract")
        self.result["work_dir"] = work

        self.set_step("download", "running", "Connecting to bootstrap host")
        self.log("download", "GET {}".format(BOOTSTRAP_URL))

        def on_download(done, total, started, now):
            message, progress = restore.transfer_message(
                "Downloading bootstrap.tar.gz", done, total, started, now=now
            )
            self.set_step("download", message=message, progress=progress)

        try:
            done, total = restore.download_file(BOOTSTRAP_URL, archive, on_download)
        except Exception as exc:
            raise JobError("download", str(exc))
        self.result["archive_bytes"] = done
        self.log(
            "download",
            "Saved {} ({})".format(archive, restore.format_bytes(done)),
        )
        self.set_step(
            "download",
            "succeeded",
            "Downloaded {}".format(restore.format_bytes(done or total)),
        )

        self.set_step("extract", "running", "Opening archive")

        def on_extract(count, total_bytes, started, now, name, members):
            message, progress = restore.transfer_message(
                "Extracting", count, total_bytes, started, now=now
            )
            if name:
                message = "{} · {}".format(message, os.path.basename(name))
            progress["detail"] = name
            progress["members"] = members
            self.set_step("extract", message=message, progress=progress)

        def on_member(name, size):
            self.log(
                "extract",
                "{} ({})".format(name, restore.format_bytes(size)),
            )

        try:
            member_count = restore.extract_archive(
                archive, extracted, on_extract, on_member
            )
            info = restore.find_restore_target(extracted)
            source_db = restore.choose_source_db(info["databases"], target.database)
        except Exception as exc:
            raise JobError("extract", str(exc))
        self.result["source_db"] = source_db
        self.result["dump_path"] = info["path"]
        self.log(
            "extract",
            "Restore source {} · databases {}".format(
                info["path"], ", ".join(info["databases"]) or "bson files"
            ),
        )
        self.set_step(
            "extract",
            "succeeded",
            "Extracted {} file{}".format(
                member_count, "" if member_count == 1 else "s"
            ),
        )

        self.log("restore", "Node stays up during mongorestore")
        dump_dir = info["path"] if info["kind"] == "dump" else info["path"]
        if info["kind"] != "dump":
            source_db = None
        try:
            plan = restore.mongorestore_plan(dump_dir, target, source_db)
        except Exception as exc:
            raise JobError("restore", str(exc))
        self.result["restore_mode"] = plan["mode"]
        self.result["command"] = " ".join(plan["display"])
        bson_size = restore.bson_bytes(info, source_db)
        self.result["bson_bytes"] = bson_size
        self.log("restore", self.result["command"])
        if source_db and source_db != target.database:
            self.log(
                "restore",
                "Renaming {}.{} into {}".format(source_db, "*", target.database),
            )
        others = [name for name in info["databases"] if name != source_db]
        if others:
            self.log(
                "restore",
                "Ignoring other databases in the archive: {}".format(", ".join(others)),
            )
        self.set_step("restore", "running", "Starting mongorestore --drop")
        stop_poll = threading.Event()

        def poll():
            client = None
            try:
                client = restore.connect_client(target, timeout_ms=2000)
                db = client[target.database]
                while not stop_poll.wait(1):
                    snap = restore.collection_progress(db, bson_size)
                    count = snap.get("documents")
                    size = snap.get("size")
                    parts = ["mongorestore --drop"]
                    if count is not None:
                        parts.append("{:,} blocks".format(count))
                    if size:
                        parts.append(restore.format_bytes(size))
                    progress = {
                        "percent": snap.get("percent"),
                        "documents": count,
                        "size": size,
                        "total": bson_size or None,
                    }
                    self.set_step(
                        "restore", message=" · ".join(parts), progress=progress
                    )
            except Exception as exc:
                self.log("restore", "status poll failed: {}".format(exc))
            finally:
                if client is not None:
                    client.close()

        poller = threading.Thread(target=poll, name="restore-poll", daemon=True)
        poller.start()
        last_line = {"value": None}

        def on_line(line):
            text = restore.clean_line(line)
            if not text or text == last_line["value"]:
                return
            last_line["value"] = text
            self.log("restore", text)

        try:
            code = restore.run_command(plan["argv"], on_line)
        finally:
            stop_poll.set()
            poller.join(timeout=2)
        if code != 0:
            raise JobError("restore", "mongorestore exited {}".format(code))
        self.set_step("restore", "succeeded", "mongorestore finished")
        self.log("restore", "mongorestore exited 0")

        self.set_step("truncate", "running", "Deleting consensus documents")
        client = None
        try:
            client = restore.connect_client(target, timeout_ms=10000)
            stats = restore.truncate_consensus(client[target.database])
        except Exception as exc:
            raise JobError("truncate", str(exc))
        finally:
            if client is not None:
                client.close()
        self.result["consensus_before"] = stats["before"]
        self.result["consensus_deleted"] = stats["deleted"]
        self.result["consensus_after"] = stats["after"]
        message = "Removed {:,} consensus documents · remaining {:,}".format(
            stats["deleted"], stats["after"]
        )
        self.log("truncate", message)
        self.set_step("truncate", "succeeded", message)
        self.result["reloaded"] = True

        self.set_step("cleanup", "running", "Removing temporary files")
        try:
            shutil.rmtree(work)
        except Exception as exc:
            self.warning = (self.warning + "; " if self.warning else "") + (
                "Could not remove {}: {}".format(work, exc)
            )
            self.set_step("cleanup", "failed", self.warning)
            self.log("cleanup", self.warning)
        else:
            self.result.pop("work_dir", None)
            self.set_step("cleanup", "succeeded", "Removed temporary files")
            self.log("cleanup", "Removed {}".format(work))
        self.result["restarting"] = True
        self.set_step(
            "restart",
            "running",
            "Restarting the node. Do not refresh this page.",
        )
        self.log("restart", "Restarting the node. Do not refresh this page.")
        self.succeed()
        if self.on_restart:
            self.on_restart()
