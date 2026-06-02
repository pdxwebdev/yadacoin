"""node_config.py — Node configuration HTTP handler."""
import json

from yadacoin_agent_auth import AgentAuthValidator, AuthError

from yadacoin.http.base import BaseHandler

from ..core.auth import _validator


def _coerce_config_value(key: str, raw):
    """Coerce a raw (possibly string) value to the expected type for key."""
    target = _CONFIG_WRITEABLE[key]
    # Normalise tuple targets to the first concrete type for coercion.
    primary = target[0] if isinstance(target, tuple) else target

    if primary is bool:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            if raw.lower() in ("true", "1", "yes", "on"):
                return True
            if raw.lower() in ("false", "0", "no", "off"):
                return False
        raise ValueError(f"Cannot coerce {raw!r} to bool for '{key}'")

    if primary is float:
        return float(raw)

    if primary is int:
        return int(float(raw))  # handles "3.0" → 3

    if primary is list:
        if isinstance(raw, list):
            return raw
        if isinstance(raw, str):
            # Accept JSON array strings or comma-separated values
            stripped = raw.strip()
            if stripped.startswith("["):
                import json as _json

                return _json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        raise ValueError(f"Cannot coerce {raw!r} to list for '{key}'")

    # str
    return str(raw)


class NodeConfigApplyHandler(BaseHandler):
    """
    POST /ai-agent-auth/api/node-config/apply

    Apply a single config change to the active config.json file and
    schedule a graceful node restart so the change takes effect.

    Requires a valid KEL-backed VP (key rotation / second-factor authorization)
    with authorizationType == "NodeConfigAuthorization" in the scope.  The
    flow mirrors the vendor VP endpoints:
      1. GET /ai-agent-auth/api/challenge?public_key=<hex>  → challenge token
      2. Browser derives next child key, broadcasts a rotation transaction
         with scope = {authorizationType: "NodeConfigAuthorization",
                       config_key: "<key>", config_value: "<value>"}
      3. POST here with {public_key, challenge, vp, key, value}

    Body (JSON)
    -----------
    public_key : hex compressed secp256k1 public key (the prerotated agent key)
    challenge  : hex string from GET /api/challenge
    vp         : W3C VP object {type, holder, verifiableCredential, proof}
    key        : str — the config setting name (must be in _CONFIG_WRITEABLE)
    value      : any — the new value (will be type-coerced)

    Response (JSON)
    ---------------
    {"status": "ok", "key": ..., "value": ..., "restarting": true}
    """

    async def post(self):
        import os
        import signal
        import tempfile

        import tornado.ioloop

        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid json body"})

        public_key = (body.get("public_key") or "").strip()
        challenge = (body.get("challenge") or "").strip()
        vp = body.get("vp")
        key = (body.get("key") or "").strip()
        raw_value = body.get("value")

        # ── Basic field validation ──────────────────────────────────────────
        if not public_key or not challenge or not vp:
            self.set_status(400)
            return self.render_as_json(
                {
                    "status": False,
                    "message": "public_key, challenge, and vp are required",
                }
            )

        if not key:
            self.set_status(400)
            return self.render_as_json({"error": "key is required"})

        if key not in _CONFIG_WRITEABLE:
            self.set_status(400)
            return self.render_as_json(
                {
                    "error": f"'{key}' is not a settable config option via chat. "
                    "See the allowed list in the node_config agent."
                }
            )

        if raw_value is None:
            self.set_status(400)
            return self.render_as_json({"error": "value is required"})

        try:
            coerced = _coerce_config_value(key, raw_value)
        except (ValueError, TypeError) as exc:
            self.set_status(400)
            return self.render_as_json({"error": f"Invalid value: {exc}"})

        # ── KEL / VP validation (second-factor / key rotation) ─────────────
        try:
            auth = await _validator.validate_vp(public_key, challenge, vp)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"status": False, "message": str(exc)})

        try:
            AgentAuthValidator.enforce_scope(auth, services=["NodeConfigAuthorization"])
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json(
                {"status": False, "message": str(exc), "scope": auth.scope}
            )

        # ── Locate the config file ──────────────────────────────────────────
        config_path = getattr(self.config, "config_path", None)
        if not config_path:
            config_path = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), "..", "..", "config", "config.json"
                )
            )

        if not os.path.isfile(config_path):
            self.set_status(500)
            return self.render_as_json(
                {"error": f"Config file not found at {config_path}"}
            )

        # ── Read → patch → write atomically ────────────────────────────────
        try:
            with open(config_path, "r") as fh:
                cfg_dict = json.load(fh)
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json({"error": f"Failed to read config: {exc}"})

        cfg_dict[key] = coerced

        config_dir = os.path.dirname(config_path)
        try:
            fd, tmp_path = tempfile.mkstemp(dir=config_dir, suffix=".tmp")
            with os.fdopen(fd, "w") as fh:
                json.dump(cfg_dict, fh, indent=4)
            os.replace(tmp_path, config_path)
        except Exception as exc:
            self.set_status(500)
            return self.render_as_json({"error": f"Failed to write config: {exc}"})

        # ── Update the in-memory Config singleton ───────────────────────────
        try:
            setattr(self.config, key, coerced)
        except Exception:
            pass  # best-effort; restart will reload from disk anyway

        # ── Respond, then schedule graceful restart ─────────────────────────
        self.render_as_json(
            {
                "status": "ok",
                "key": key,
                "value": coerced,
                "restarting": True,
                "authorized_address": auth.address,
                "kel_depth": len(auth.kel),
                "kel_txid": auth.kel_txid,
                "message": (
                    f"Config updated: {key} = {coerced!r}. "
                    "Node is restarting to apply the change."
                ),
            }
        )

        def _do_restart():
            os.kill(os.getpid(), signal.SIGTERM)

        tornado.ioloop.IOLoop.current().call_later(2, _do_restart)


# ── Wallet Agent API handlers ─────────────────────────────────────────────────
