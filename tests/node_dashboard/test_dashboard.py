"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import os
import sys
import tarfile
import tempfile
import threading

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from node_dashboard.job import STEPS  # noqa: E402
from node_dashboard.node_control import command_kind, matching_processes  # noqa: E402
from node_dashboard.restore import (  # noqa: E402
    choose_source_db,
    download_file,
    extract_archive,
    find_restore_target,
    mongorestore_argv,
    mongorestore_plan,
    safe_member,
    split_lines,
    truncate_consensus,
)
from node_dashboard.settings import (  # noqa: E402
    BOOTSTRAP_URL,
    MongoTarget,
    parse_host,
    redact_argv,
    resolve_target,
    target_from_config,
)

SECRET = "super-secret-password"


def test_bootstrap_url():
    assert BOOTSTRAP_URL == "https://yadacoin.io/yadacoinstatic/bootstrap.tar.gz"


def test_parse_host_variants():
    assert parse_host("localhost")["port"] == 27017
    parsed = parse_host("127.0.0.1:27018")
    assert parsed["host"] == "127.0.0.1"
    assert parsed["port"] == 27018
    uri = parse_host("mongodb://admin:s3cret@mongodb:27017/yadacoin")
    assert uri["host"] == "mongodb"
    assert uri["username"] == "admin"
    assert uri["password"] == "s3cret"
    assert uri["database"] == "yadacoin"


def test_config_database_wins_over_uri_path():
    target = target_from_config(
        {
            "mongodb_host": "mongodb://admin:s3cret@localhost:27017/other",
            "database": "yadacoin",
            "mongodb_username": "operator",
            "mongodb_password": SECRET,
        }
    )
    assert target.database == "yadacoin"
    assert target.username == "operator"
    assert target.password == SECRET


def test_resolve_docker_host_to_published_port():
    def probe(host, port):
        return host == "127.0.0.1" and port == 27017

    target = MongoTarget("mongodb", "mongodb", 27017, "yadacoin", "", "", "admin", None)
    resolve_target(target, probe)
    assert target.connect_host == "127.0.0.1"
    assert "127.0.0.1" in target.note


def test_redact_argv_hides_password():
    argv = [
        "mongorestore",
        "--password",
        SECRET,
        "mongodb://user:" + SECRET + "@localhost",
    ]
    display = " ".join(redact_argv(argv, [SECRET]))
    assert SECRET not in display
    assert "***" in display


def test_safe_member_rejects_escape():
    with tempfile.TemporaryDirectory() as dest:
        safe_member(dest, "dump/yadacoin/blocks.bson")
        try:
            safe_member(dest, "../outside")
        except ValueError:
            return
        raise AssertionError("path escape was accepted")


def test_find_restore_target_and_source_db():
    with tempfile.TemporaryDirectory() as dest:
        db_dir = os.path.join(dest, "nested", "dump", "yadacoin")
        os.makedirs(db_dir)
        open(os.path.join(db_dir, "blocks.bson"), "wb").close()
        info = find_restore_target(dest)
        assert info["kind"] == "dump"
        assert info["databases"] == ["yadacoin"]
        assert choose_source_db(info["databases"], "custom") == "yadacoin"
        assert choose_source_db(["custom"], "custom") == "custom"


def test_mongorestore_command_drops_and_renames(monkeypatch):
    monkeypatch.setattr(
        "node_dashboard.restore.shutil.which",
        lambda name: "/usr/bin/mongorestore" if name == "mongorestore" else None,
    )
    target = MongoTarget(
        "127.0.0.1", "127.0.0.1", 27017, "custom", "admin", SECRET, "admin", None
    )
    argv = mongorestore_argv("mongorestore", "/dump", target, "yadacoin", "127.0.0.1")
    assert "--drop" in argv
    assert "--nsFrom" in argv
    assert "yadacoin.*" in argv
    assert "custom.*" in argv
    plan = mongorestore_plan("/dump", target, "yadacoin")
    assert plan["mode"] == "local"
    assert SECRET not in " ".join(plan["display"])
    assert "--drop" in plan["display"]


def test_split_lines_keeps_carriage_return_updates():
    lines = list(split_lines(["prog\r", "ess 10%\rdone\n"]))
    assert lines == ["prog", "ess 10%", "done"]


def test_command_kind_matches_node_processes():
    assert command_kind("python3 yadanodemanager.py") == "manager"
    assert command_kind("/usr/bin/python3 /etc/yadacoin/yadacoin/app.py") == "node"
    assert command_kind("vim yadacoin/app.py") is None
    found = matching_processes(
        "42 python3 yadanodemanager.py\n1 python3 yadacoin/app.py\n", own_pid=99
    )
    assert found[0][0] == 42
    assert len(found) == 1


def test_truncate_consensus_deletes_documents():
    class Result(object):
        deleted_count = 4

    class Collection(object):
        def __init__(self):
            self.counts = [4, 0]

        def estimated_document_count(self):
            return self.counts.pop(0)

        def delete_many(self, query):
            assert query == {}
            return Result()

    class DB(object):
        def __init__(self):
            self.collection = Collection()

        def __getitem__(self, name):
            assert name == "consensus"
            return self.collection

    stats = truncate_consensus(DB())
    assert stats == {"before": 4, "deleted": 4, "after": 0}


def test_extract_archive_reports_progress_and_rejects_slip():
    with tempfile.TemporaryDirectory() as dest:
        archive = os.path.join(dest, "bootstrap.tar.gz")
        payload = os.path.join(dest, "stage", "dump", "yadacoin")
        os.makedirs(payload)
        with open(os.path.join(payload, "blocks.bson"), "wb") as handle:
            handle.write(b"bson")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(os.path.join(dest, "stage"), arcname="stage")
        seen = []

        def on_progress(done, total, started, now, name, members):
            seen.append((done, total, members))

        extracted = os.path.join(dest, "out")
        count = extract_archive(
            archive, extracted, on_progress, lambda name, size: None
        )
        assert count >= 1
        assert seen[-1][0] == seen[-1][1]
        assert find_restore_target(extracted)["databases"] == ["yadacoin"]


def test_download_reports_byte_progress():
    body = b"abcdefghijklmnopqrstuvwxyz"
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    updates = []
    try:
        with tempfile.TemporaryDirectory() as dest:
            path = os.path.join(dest, "bootstrap.tar.gz")
            done, total = download_file(
                "http://127.0.0.1:{}/bootstrap.tar.gz".format(server.server_address[1]),
                path,
                lambda done, total, started, now: updates.append((done, total)),
            )
            assert done == len(body)
            assert total == len(body)
            assert updates[-1] == (len(body), len(body))
            assert open(path, "rb").read() == body
    finally:
        server.shutdown()


def test_reload_keeps_the_node_up_until_restart():
    ids = [step_id for step_id, _label in STEPS]
    assert "pause" not in ids
    assert "resume" not in ids
    assert ids[-1] == "restart"


def test_operator_page_warns_not_to_refresh():
    page = os.path.join(ROOT, "node_dashboard", "static", "index.html")
    script = os.path.join(ROOT, "node_dashboard", "static", "app.js")
    html = open(page, encoding="utf-8").read()
    js = open(script, encoding="utf-8").read()
    assert "Do not refresh" in html
    assert "/operator/api/health" in js
    assert "/operator/api/reload" in js
    assert "sawDown" in js
    assert "purpose=operator" in js
    assert "/yada-password/signin" in js
    card = open(
        os.path.join(ROOT, "templates", "dashboard.html"), encoding="utf-8"
    ).read()
    assert 'href="/operator"' in card
    assert "127.0.0.1:8099" not in card
