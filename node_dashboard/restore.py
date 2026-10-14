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
import re
import shutil
import signal
import subprocess
import tarfile
import threading
import time
import urllib.request

from node_dashboard.settings import CONSENSUS_COLLECTION, redact_argv

ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_PROCS = []
_PROCS_LOCK = threading.Lock()


def format_bytes(n):
    value = float(n or 0)
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024.0
        index += 1
    if index == 0:
        return "{} {}".format(int(value), units[index])
    return "{:.1f} {}".format(value, units[index])


def format_duration(seconds):
    if seconds is None:
        return ""
    remaining = max(0, int(round(seconds)))
    hours, rest = divmod(remaining, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return "{}h {}m {}s".format(hours, minutes, secs)
    if minutes:
        return "{}m {}s".format(minutes, secs)
    return "{}s".format(secs)


def transfer_progress(done, total, started, now=None):
    now = time.time() if now is None else now
    elapsed = max(now - started, 0.001)
    speed = (done / elapsed) if done else 0
    percent = (done * 100.0 / total) if total else None
    eta = None
    if speed and total and done < total:
        eta = (total - done) / speed
    return {
        "percent": percent,
        "current": done,
        "total": total or None,
        "speed": speed,
        "eta_seconds": eta,
    }


def transfer_message(label, done, total, started, now=None):
    progress = transfer_progress(done, total, started, now=now)
    parts = [label]
    if progress["percent"] is not None:
        parts.append("{:.0f}%".format(progress["percent"]))
        parts.append("{} / {}".format(format_bytes(done), format_bytes(total)))
    else:
        parts.append(format_bytes(done))
    if progress["speed"]:
        parts.append("{}/s".format(format_bytes(progress["speed"])))
    if progress["eta_seconds"] is not None:
        parts.append("ETA {}".format(format_duration(progress["eta_seconds"])))
    return " · ".join(parts), progress


def restore_tool():
    if shutil.which("mongorestore"):
        return "local"
    if shutil.which("docker"):
        return "docker"
    return "missing"


def clean_line(line):
    text = ANSI_RE.sub("", line or "")
    text = text.replace("\x00", "")
    text = "".join(ch for ch in text if ch == "\t" or ord(ch) >= 32)
    return text.strip()


def split_lines(chunks):
    buf = ""
    for chunk in chunks:
        buf += chunk
        buf = buf.replace("\r\n", "\n").replace("\x00", "")
        while "\n" in buf or "\r" in buf:
            newline = buf.find("\n")
            carriage = buf.find("\r")
            if newline == -1 or (carriage != -1 and carriage < newline):
                cut = carriage
            else:
                cut = newline
            yield buf[:cut]
            buf = buf[cut + 1 :]
    if buf:
        yield buf


def safe_member(dest, name):
    if not name or name.startswith("/") or name.startswith("\\"):
        raise ValueError("Unsafe path in archive: {}".format(name))
    dest_real = os.path.realpath(dest)
    target = os.path.realpath(os.path.join(dest, name))
    if target != dest_real and not target.startswith(dest_real + os.sep):
        raise ValueError("Unsafe path in archive: {}".format(name))
    return target


class CountingReader(object):
    def __init__(self, raw, on_bytes):
        self.raw = raw
        self.on_bytes = on_bytes
        self.read_bytes = 0

    def read(self, n=-1):
        data = self.raw.read(n)
        if data:
            self.read_bytes += len(data)
            self.on_bytes(self.read_bytes)
        return data


def download_file(url, dest, on_progress, timeout=120):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "yadacoin-node-dashboard",
            "Accept-Encoding": "identity",
        },
    )
    started = time.time()
    last_emit = 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        total = int(response.headers.get("Content-Length") or 0)
        free = shutil.disk_usage(os.path.dirname(dest)).free
        if total and free < int(total * 2.2):
            raise RuntimeError(
                "Not enough free space for the archive and extract. "
                "Need about {}, have {}. MongoDB also needs room for "
                "the restored collection.".format(
                    format_bytes(int(total * 2.2)), format_bytes(free)
                )
            )
        done = 0
        with open(dest, "wb") as handle:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                done += len(chunk)
                now = time.time()
                if now - last_emit >= 0.25:
                    last_emit = now
                    on_progress(done, total, started, now)
        on_progress(done, total or done, started, time.time())
    return done, total


def extract_archive(archive, dest, on_progress, on_member):
    total = os.path.getsize(archive)
    started = time.time()
    last_emit = [0]
    current = [""]
    members = [0]

    def on_bytes(count):
        now = time.time()
        if now - last_emit[0] < 0.25 and count != total:
            return
        last_emit[0] = now
        on_progress(count, total, started, now, current[0], members[0])

    os.makedirs(dest, exist_ok=True)
    with open(archive, "rb") as raw:
        counter = CountingReader(raw, on_bytes)
        with tarfile.open(fileobj=counter, mode="r|gz") as tar:
            for member in tar:
                if member.issym() or member.islnk():
                    raise ValueError(
                        "Refusing symlink in archive: {}".format(member.name)
                    )
                safe_member(dest, member.name)
                current[0] = member.name
                on_member(member.name, member.size)
                try:
                    tar.extract(member, dest, set_attrs=False, filter="data")
                except TypeError:
                    tar.extract(member, dest, set_attrs=False)
                members[0] += 1
                on_bytes(counter.read_bytes)
    on_progress(total, total, started, time.time(), current[0], members[0])
    return members[0]


def _dump_databases(dump):
    databases = []
    try:
        names = sorted(os.listdir(dump))
    except OSError:
        return databases
    for name in names:
        path = os.path.join(dump, name)
        if not os.path.isdir(path):
            continue
        try:
            filenames = os.listdir(path)
        except OSError:
            continue
        if any(fn.endswith(".bson") for fn in filenames):
            databases.append(name)
    return databases


def find_restore_target(root):
    root = os.path.realpath(root)
    dump_dirs = []
    bson_dirs = []
    for dirpath, _dirnames, filenames in os.walk(root):
        if any(name.endswith(".bson") for name in filenames):
            bson_dirs.append(dirpath)
        if os.path.basename(dirpath) == "dump":
            dump_dirs.append(dirpath)
    if not bson_dirs:
        raise RuntimeError("No mongodump data found in the bootstrap archive")
    for dump in dump_dirs:
        databases = _dump_databases(dump)
        if databases:
            return {"kind": "dump", "path": dump, "databases": databases}
    return {"kind": "bson", "path": bson_dirs[0], "databases": []}


def choose_source_db(databases, target_db):
    if not databases:
        return None
    if target_db in databases:
        return target_db
    if "yadacoin" in databases:
        return "yadacoin"
    if len(databases) == 1:
        return databases[0]
    raise RuntimeError(
        "Bootstrap archive has multiple databases and none match {}: {}".format(
            target_db, ", ".join(databases)
        )
    )


def bson_bytes(info, source_db):
    if info["kind"] == "dump" and source_db:
        path = os.path.join(info["path"], source_db)
    else:
        path = info["path"]
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            if name.endswith(".bson"):
                total += os.path.getsize(os.path.join(dirpath, name))
    return total


def mongorestore_argv(binary, dump_dir, target, source_db, host):
    argv = [
        binary,
        "--drop",
        "--host",
        host,
        "--port",
        str(target.port),
    ]
    if target.username:
        argv.extend(
            [
                "--username",
                target.username,
                "--password",
                target.password,
                "--authenticationDatabase",
                target.auth_source,
            ]
        )
    if source_db:
        argv.extend(
            [
                "--nsInclude",
                "{}.*".format(source_db),
                "--nsFrom",
                "{}.*".format(source_db),
                "--nsTo",
                "{}.*".format(target.database),
            ]
        )
    else:
        argv.extend(["--db", target.database])
    argv.append(dump_dir)
    return argv


def mongo_compose_network():
    if not shutil.which("docker"):
        return None
    try:
        out = subprocess.check_output(
            [
                "docker",
                "ps",
                "-q",
                "--filter",
                "name=mongodb",
                "--filter",
                "status=running",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return None
    ids = [line.strip() for line in out.splitlines() if line.strip()]
    if not ids:
        return None
    try:
        raw = subprocess.check_output(
            [
                "docker",
                "inspect",
                "-f",
                "{{json .NetworkSettings.Networks}}",
                ids[0],
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        nets = json.loads(raw)
    except Exception:
        return None
    if not nets:
        return None
    return next(iter(nets))


def mongorestore_plan(dump_dir, target, source_db):
    binary = shutil.which("mongorestore")
    if binary:
        argv = mongorestore_argv(
            binary, dump_dir, target, source_db, target.connect_host
        )
        return {
            "mode": "local",
            "argv": argv,
            "display": redact_argv(argv, target.secrets()),
        }
    if not shutil.which("docker"):
        raise RuntimeError(
            "mongorestore is not installed and docker is not available. "
            "Install MongoDB database tools or Docker."
        )
    network = mongo_compose_network()
    if network:
        docker_host = "mongodb"
    elif target.connect_host in ("127.0.0.1", "localhost", "::1", "mongodb", "mongo"):
        docker_host = "host.docker.internal"
        network = None
    else:
        docker_host = target.connect_host
        network = None
    if ":" in dump_dir:
        raise RuntimeError("Cannot mount a dump path that contains ':'")
    inner = mongorestore_argv("mongorestore", "/dump", target, source_db, docker_host)
    argv = ["docker", "run", "--rm", "-v", "{}:/dump:ro".format(dump_dir)]
    if network:
        argv.extend(["--network", network])
    else:
        argv.extend(["--add-host", "host.docker.internal:host-gateway"])
    argv.append("mongo:latest")
    argv.extend(inner)
    return {
        "mode": "docker",
        "argv": argv,
        "display": redact_argv(argv, target.secrets()),
    }


def track_proc(proc):
    with _PROCS_LOCK:
        _PROCS.append(proc)
    return proc


def stop_tracked_processes():
    with _PROCS_LOCK:
        procs = list(_PROCS)
    for proc in procs:
        if proc.poll() is not None:
            continue
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.terminate()
            except Exception:
                pass


def _iter_pty(fd):
    while True:
        try:
            data = os.read(fd, 4096)
        except OSError:
            break
        if not data:
            break
        yield data.decode("utf-8", "replace")


def _iter_pipe(stream):
    while True:
        chunk = stream.read(4096)
        if not chunk:
            break
        yield chunk


def start_proc(argv):
    if os.name == "posix":
        try:
            import fcntl
            import pty
            import struct
            import termios

            master, slave = pty.openpty()
            try:
                winsize = struct.pack("HHHH", 40, 160, 0, 0)
                fcntl.ioctl(slave, termios.TIOCSWINSZ, winsize)
            except Exception:
                pass
            proc = subprocess.Popen(
                argv,
                stdout=slave,
                stderr=slave,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
            os.close(slave)
            track_proc(proc)
            return proc, master
        except OSError:
            pass
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )
    track_proc(proc)
    return proc, None


def iter_proc_lines(proc, master_fd):
    try:
        if master_fd is not None:
            chunks = _iter_pty(master_fd)
        else:
            chunks = _iter_pipe(proc.stdout)
        for line in split_lines(chunks):
            yield line
    finally:
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass


def run_command(argv, on_line):
    proc, master = start_proc(argv)

    def reader():
        try:
            for line in iter_proc_lines(proc, master):
                on_line(line)
        except Exception as exc:
            on_line("output reader failed: {}".format(exc))

    thread = threading.Thread(target=reader, name="mongorestore-output", daemon=True)
    thread.start()
    code = proc.wait()
    thread.join(timeout=5)
    return code


def connect_client(target, timeout_ms=5000):
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise RuntimeError(
            "pymongo is required to read and truncate consensus"
        ) from exc
    kwargs = {
        "host": target.connect_host,
        "port": target.port,
        "serverSelectionTimeoutMS": timeout_ms,
    }
    if target.username:
        kwargs["username"] = target.username
        kwargs["password"] = target.password
        kwargs["authSource"] = target.auth_source
    client = MongoClient(**kwargs)
    client.admin.command("ping")
    return client


def truncate_consensus(db):
    collection = db[CONSENSUS_COLLECTION]
    before = collection.estimated_document_count()
    result = collection.delete_many({})
    after = collection.estimated_document_count()
    return {
        "before": before,
        "deleted": result.deleted_count,
        "after": after,
    }


def collection_progress(db, bson_size):
    count = None
    size = None
    try:
        stats = db.command("collStats", "blocks")
        count = stats.get("count")
        size = stats.get("size") or 0
    except Exception:
        try:
            count = db.blocks.estimated_document_count()
        except Exception:
            count = None
    percent = None
    if bson_size and size:
        percent = min(99.0, float(size) * 100.0 / float(bson_size))
    return {"documents": count, "size": size, "percent": percent}
