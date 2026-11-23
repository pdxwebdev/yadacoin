"""Inspect and resolve stuck USDC -> WYDA swap requests.

Pending swaps are stored in the site database under ``crypto_onramp_swaps``.
A row keeps being pushed to Yada Password until its ``status`` changes to
``denied`` or ``fulfilled``. This tool lists those rows and, with ``--apply``,
marks them resolved so they stop re-appearing.

Examples
--------
List the default affected users (alice, yadacoin.io)::

    python scripts/resolve_pending_swaps.py --config /config/config.json

Deny every pending swap for those users::

    python scripts/resolve_pending_swaps.py --config /config/config.json \
        --status denied --apply

Resolve one session::

    python scripts/resolve_pending_swaps.py --config /config/config.json \
        --session 1234abcd --status fulfilled --apply

The command is a dry run unless ``--apply`` is supplied.
"""

import argparse
import asyncio
import json
import os
import sys
import time

DEFAULT_USERS = ("alice", "yadacoin.io")
STATUSES = ("denied", "fulfilled", "pending")


def normalize_user(value):
    return str(value or "").strip().lstrip("@")


def load_config(path):
    with open(path) as handle:
        return json.load(handle)


def resolve_config_path(value):
    if value:
        return value
    env = os.environ.get("YADA_CONFIG", "")
    if env:
        return env
    for candidate in ("/config/config.json", "config/config.json"):
        if os.path.isfile(candidate):
            return candidate
    return ""


def swap_query(users, session, all_pending=False):
    if all_pending:
        return {"status": "pending"}
    if session:
        return {"_id": session}
    names = []
    for user in users:
        name = normalize_user(user)
        if not name:
            continue
        for candidate in (name, "@" + name):
            if candidate not in names:
                names.append(candidate)
    if not names:
        return {}
    return {"username": {"$in": names}, "status": "pending"}


def describe(row):
    return (
        f"session={row.get('_id')} "
        f"user={row.get('username') or '-'} "
        f"amount={row.get('source_amount') or '-'} "
        f"wallet={row.get('wallet_address') or '-'} "
        f"permit={'yes' if row.get('permit_r') else 'no'} "
        f"created={row.get('created') or '-'}"
    )


async def run(args):
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except ImportError:
        print(
            "ERROR: motor is not installed. Install requirements first.",
            file=sys.stderr,
        )
        return 2

    config_path = resolve_config_path(args.config)
    if not config_path:
        print(
            "ERROR: pass --config /path/to/config.json or set YADA_CONFIG",
            file=sys.stderr,
        )
        return 2
    config = load_config(config_path)
    host = config.get("mongodb_host") or "localhost"
    database = config.get("site_database") or "yadacoinsite"
    client_kwargs = {}
    username = str(config.get("mongodb_username") or "")
    password = str(config.get("mongodb_password") or "")
    if username and password:
        client_kwargs["username"] = username
        client_kwargs["password"] = password
    client = AsyncIOMotorClient(host, **client_kwargs)
    collection = client[database].crypto_onramp_swaps
    try:
        query = swap_query(args.user, args.session, args.all)
        if not query:
            print("ERROR: provide --user, --session, or --all", file=sys.stderr)
            return 2
        rows = await collection.find(query).sort("created", -1).to_list(200)
        print(f"config: {config_path}")
        print(f"database: {host}/{database}")
        print(f"query: {query}")
        print(f"pending swaps: {len(rows)}")
        for row in rows:
            print("  " + describe(row))
        if not rows:
            return 0
        if not args.apply:
            print("dry run: re-run with --apply to update these rows")
            return 0
        now = int(time.time())
        update = {"$set": {"status": args.status, "resolved_at": now}}
        result = await collection.update_many(query, update)
        print(
            f"updated {result.modified_count} row(s) to status={args.status} "
            f"at {now}"
        )
        return 0
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(
        description="List or resolve stuck USDC -> WYDA swap requests."
    )
    parser.add_argument(
        "--config",
        default="",
        help="path to the node config.json (default: $YADA_CONFIG or /config/config.json)",
    )
    parser.add_argument(
        "--user",
        action="append",
        default=[],
        help=f"username to resolve (repeatable; default: {', '.join(DEFAULT_USERS)})",
    )
    parser.add_argument("--session", default="", help="resolve one session id")
    parser.add_argument(
        "--all",
        action="store_true",
        help="match every pending swap (use with care)",
    )
    parser.add_argument(
        "--status",
        choices=STATUSES,
        default="denied",
        help="status to set when --apply is used (default: denied)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the change; without this flag the command is a dry run",
    )
    args = parser.parse_args()
    if args.all:
        args.user = []
        args.session = ""
    elif not args.user and not args.session:
        args.user = list(DEFAULT_USERS)
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
