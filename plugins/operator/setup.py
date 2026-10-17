"""Node setup gate: missing username or second factor is not fatal."""

import json
import os
import re

from yadacoin.enums.modes import MODES

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

EDITABLE_CONFIG = (
    "username",
    "modes",
    "serve_host",
    "serve_port",
    "peer_host",
    "peer_port",
    "peer_type",
    "mongodb_host",
    "database",
    "site_database",
    "network",
    "log_level",
    "max_peers",
    "max_miners",
    "pool_payout",
    "payout_frequency",
    "pool_take",
    "callbackurl",
    "wallet_host_port",
    "websocket_host_port",
    "origin",
    "ssl",
    "disabled_plugins",
)


def available_plugins():
    root = os.path.join(REPO_ROOT, "plugins")
    if not os.path.isdir(root):
        return []
    names = []
    for name in sorted(os.listdir(root)):
        if name.startswith(".") or name.startswith("__"):
            continue
        if os.path.isdir(os.path.join(root, name)):
            names.append(name)
    return names


HIDDEN_MODES = ("dns", "proxy", "ssl")


def running_in_docker():
    if os.path.exists("/.dockerenv"):
        return True
    cgroup = "/proc/1/cgroup"
    try:
        with open(cgroup, "r") as handle:
            text = handle.read()
    except OSError:
        return False
    return "docker" in text or "containerd" in text


def compose_file():
    path = os.path.join(REPO_ROOT, "docker-compose.yml")
    if os.path.isfile(path):
        return path
    return ""


def bind_second_factor_file(config):
    if (os.environ.get("SECOND_FACTOR_FILE") or "").strip():
        return
    path = (getattr(config, "second_factor_file", "") or "").strip()
    if path:
        os.environ["SECOND_FACTOR_FILE"] = path


def read_second_factor(config=None):
    if config is not None:
        bind_second_factor_file(config)
    sf_file = (os.environ.get("SECOND_FACTOR_FILE") or "").strip()
    if sf_file:
        with open(sf_file, "r") as handle:
            return handle.read().strip()
    return (os.environ.get("SECOND_FACTOR") or "").strip()


def second_factor_path(config):
    config_path = getattr(config, "config_path", "") or ""
    if config_path:
        return os.path.join(
            os.path.dirname(os.path.abspath(config_path)), "second_factor"
        )
    return os.path.abspath("second_factor")


def write_second_factor(config, secret):
    secret = str(secret or "").strip()
    if not secret:
        raise ValueError("second factor is required")
    path = second_factor_path(config)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, secret.encode("utf-8"))
    finally:
        os.close(fd)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def container_secret_path(secret_path):
    secret_path = os.path.abspath(secret_path)
    try:
        relative = os.path.relpath(secret_path, REPO_ROOT)
    except ValueError:
        relative = os.path.basename(secret_path)
    if relative.startswith(".."):
        relative = os.path.basename(secret_path)
    return "/app/" + relative.replace(os.sep, "/")


def publish_second_factor_file(config, secret_path):
    """Remember where the secret file lives after this process exits."""
    os.environ["SECOND_FACTOR_FILE"] = secret_path
    compose = compose_file()
    if compose:
        env_path = (
            container_secret_path(secret_path)
            if not running_in_docker()
            else secret_path
        )
        _set_compose_env(compose, env_path)
    if not running_in_docker():
        write_config_values(config, {"second_factor_file": secret_path}, internal=True)
        config.second_factor_file = secret_path


def _set_compose_env(compose_path, secret_path):
    with open(compose_path, "r") as handle:
        text = handle.read()
    replacement = "      - SECOND_FACTOR_FILE={}\n".format(secret_path)
    if re.search(r"(?m)^\s*-\s*SECOND_FACTOR_FILE=", text):
        text = re.sub(
            r"(?m)^(\s*-\s*SECOND_FACTOR_FILE=).*$",
            r"\1{}".format(secret_path),
            text,
            count=1,
        )
    else:
        marker = "    environment:\n"
        index = text.find(marker)
        if index < 0:
            raise ValueError("docker-compose.yml has no environment block")
        index += len(marker)
        text = text[:index] + replacement + text[index:]
    temporary = compose_path + ".tmp"
    with open(temporary, "w") as handle:
        handle.write(text)
    os.replace(temporary, compose_path)


def missing_setup(config):
    missing = []
    username = (getattr(config, "username", "") or "").strip()
    if not username:
        missing.append("username")
    try:
        second_factor = read_second_factor(config)
    except Exception:
        second_factor = ""
    if not second_factor:
        missing.append("second_factor")
    return missing


ONBOARDING_STEPS = ("announce", "apps", "seed", "signin", "done")


def onboarding_path(config):
    path = getattr(config, "config_path", "") or ""
    if not path:
        return ""
    return os.path.join(
        os.path.dirname(os.path.abspath(path)), "operator_onboarding.json"
    )


def read_onboarding(config):
    path = onboarding_path(config)
    if not path or not os.path.isfile(path):
        return "done" if not missing_setup(config) else ""
    try:
        with open(path, "r") as handle:
            document = json.load(handle)
    except Exception:
        return ""
    step = (document or {}).get("step") or ""
    if step not in ONBOARDING_STEPS:
        return ""
    return step


def write_onboarding(config, step):
    if step not in ONBOARDING_STEPS:
        raise ValueError("invalid onboarding step")
    path = onboarding_path(config)
    if not path:
        raise ValueError("config path is not set")
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump({"step": step}, handle)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    config.operator_onboarding = step
    return step


def note_password_inception(config, txn):
    rel = getattr(txn, "relationship", None)
    identity = (
        rel.get("identity") if isinstance(rel, dict) else getattr(rel, "identity", None)
    )
    if isinstance(identity, dict):
        username = identity.get("username") or ""
    else:
        username = getattr(identity, "username", "") or ""
    expected = (getattr(config, "username", "") or "").strip()
    if expected and str(username).strip() == expected:
        config.password_inception_seen = True
        return True
    return False


def onboarding_pending(config):
    if missing_setup(config):
        return False
    step = getattr(config, "operator_onboarding", None)
    if step is None:
        step = read_onboarding(config)
        config.operator_onboarding = step
    return bool(step) and step != "done"


def apply_setup_gate(config):
    bind_second_factor_file(config)
    if not getattr(config, "configured_modes", None):
        config.configured_modes = list(config.modes or [])
    missing = missing_setup(config)
    config.setup_missing = missing
    config.setup_required = bool(missing)
    if missing:
        config.modes = [MODES.WEB.value]
    else:
        config.modes = list(
            config.configured_modes or config.modes or [MODES.WEB.value]
        )
    config.operator_onboarding = read_onboarding(config)
    return missing


def write_config_values(config, values, internal=False):
    path = getattr(config, "config_path", "") or ""
    if not path:
        raise ValueError("config path is not set")
    with open(path, "r") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError("config file is not an object")
    saved = {}
    for key, value in values.items():
        if key not in EDITABLE_CONFIG and not (
            internal and key == "second_factor_file"
        ):
            raise ValueError("unsupported key: {}".format(key))
        if key in (
            "serve_port",
            "peer_port",
            "max_peers",
            "max_miners",
            "payout_frequency",
        ):
            value = int(value)
            if key == "payout_frequency" and value < 1:
                raise ValueError("payout_frequency must be at least 1")
        if key == "pool_take":
            value = float(value)
            if value < 0 or value > 1:
                raise ValueError("pool_take must be between 0 and 1")
        if key == "modes":
            if isinstance(value, str):
                value = [part.strip() for part in value.split(",") if part.strip()]
            allowed = [mode.value for mode in MODES]
            if not isinstance(value, list) or not value:
                raise ValueError("modes must be a non-empty list")
            unknown = [mode for mode in value if mode not in allowed]
            if unknown:
                raise ValueError("unknown modes: {}".format(", ".join(unknown)))
            kept = [
                mode
                for mode in (document.get("modes") or [])
                if mode in ("dns", "proxy")
            ]
            value = [mode for mode in value if mode not in HIDDEN_MODES]
            value.extend(mode for mode in kept if mode not in value)
        if key == "ssl":
            if not isinstance(value, dict):
                raise ValueError("ssl must be an object")
            from plugins.operator.letsencrypt import ssl_document

            value = ssl_document(value)
            modes = list(document.get("modes") or [])
            if value.get("common_name"):
                if MODES.SSL.value not in modes:
                    modes.append(MODES.SSL.value)
            else:
                modes = [mode for mode in modes if mode != MODES.SSL.value]
            document["modes"] = modes
            saved["modes"] = modes
        if key == "pool_payout":
            value = value in (True, "true", "True", "1", 1, "on")
        if key == "disabled_plugins":
            if isinstance(value, str):
                value = [part.strip() for part in value.split(",") if part.strip()]
            if not isinstance(value, list):
                raise ValueError("disabled_plugins must be a list")
            known = available_plugins()
            unknown = [name for name in value if name not in known]
            if unknown:
                raise ValueError("unknown plugins: {}".format(", ".join(unknown)))
            value = [name for name in value if name != "operator"]
        if key == "username":
            value = str(value or "").strip()
            if not value:
                raise ValueError("username is required")
        document[key] = value
        saved[key] = value
    if "ssl" in saved:
        modes = [
            mode
            for mode in (document.get("modes") or [])
            if mode not in HIDDEN_MODES or mode in ("dns", "proxy")
        ]
        if saved["ssl"].get("common_name") and MODES.SSL.value not in modes:
            modes.append(MODES.SSL.value)
        if not saved["ssl"].get("common_name"):
            modes = [mode for mode in modes if mode != MODES.SSL.value]
        document["modes"] = modes
        saved["modes"] = modes
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(document, handle, indent=4)
        handle.write("\n")
    os.replace(temporary, path)
    return saved
