"""Let's Encrypt paths, issue, and renew for the operator SSL subform."""

import os
import shutil
import subprocess
import threading

LIVE = "/etc/letsencrypt/live"


def ssl_document(value):
    domain = str(value.get("common_name") or "").strip().lower().rstrip(".")
    email = str(value.get("email") or "").strip()
    port = value.get("port") or 443
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ValueError("ssl port must be an integer")
    if domain and ("/" in domain or " " in domain):
        raise ValueError("ssl common_name must be a hostname")
    if not domain:
        return {
            "cafile": "",
            "certfile": "",
            "keyfile": "",
            "port": port,
            "common_name": "",
            "email": email,
        }
    live = os.path.join(LIVE, domain)
    return {
        "cafile": os.path.join(live, "fullchain.pem"),
        "certfile": os.path.join(live, "cert.pem"),
        "keyfile": os.path.join(live, "privkey.pem"),
        "port": port,
        "common_name": domain,
        "email": email,
    }


def issue_certificate(domain, email):
    certbot = shutil.which("certbot")
    if not certbot:
        return False, "certbot is not installed"
    if not domain or not email:
        return False, "common_name and email are required"
    live = os.path.join(LIVE, domain, "fullchain.pem")
    command = [certbot, "renew", "--quiet", "--cert-name", domain]
    if not os.path.exists(live):
        command = [
            certbot,
            "certonly",
            "--non-interactive",
            "--agree-tos",
            "--email",
            email,
            "--standalone",
            "-d",
            domain,
        ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "certbot failed").strip()
        return False, detail
    return True, "certificate issued"


def renew_certificates():
    certbot = shutil.which("certbot")
    if not certbot:
        return False, "certbot is not installed"
    try:
        result = subprocess.run(
            [certbot, "renew", "--quiet"],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "renew failed").strip()
    return True, "renewed"


def start_renew_loop(config):
    ssl_config = getattr(config, "ssl", None)
    domain = getattr(ssl_config, "common_name", "") if ssl_config else ""
    if not domain or getattr(config, "_letsencrypt_renew_started", False):
        return
    config._letsencrypt_renew_started = True

    def loop():
        while True:
            renew_certificates()
            threading.Event().wait(12 * 60 * 60)

    threading.Thread(target=loop, name="letsencrypt-renew", daemon=True).start()
