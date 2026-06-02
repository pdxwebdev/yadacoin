"""auth.py -- shared auth constants: challenge secret, validator, and OAuth provider registry."""
import os

from yadacoin_agent_auth import AgentAuthValidator, YadaCoinNodeKelProvider

# ---------------------------------------------------------------------------
# Challenge secret
# ---------------------------------------------------------------------------
_CHALLENGE_SECRET = os.environ.get(
    "YADACOIN_AGENT_SECRET", "yadacoin-demo-agent-secret-2026"
).encode("utf-8")

_validator = AgentAuthValidator(
    challenge_secret=_CHALLENGE_SECRET,
    kel_provider=YadaCoinNodeKelProvider(),
)

# ---------------------------------------------------------------------------
# OAuth 2.0 Device Authorization Grant registry (RFC 8628)
# Public clients only — no client_secret required or distributed.
# client_id is resolved at request time from self.config using config_key.
# ---------------------------------------------------------------------------
_OAUTH_PROVIDERS: dict = {
    "github": {
        "name": "GitHub",
        "icon": "\U0001f419",
        "config_key": "github_device_client_id",
        "device_auth_url": "https://github.com/login/device/code",
        "token_url": "https://github.com/login/oauth/access_token",
        "scope": "repo read:user user:email notifications",
    },
    "microsoft": {
        "name": "Microsoft",
        "icon": "\U0001fa9f",
        "config_key": "microsoft_device_client_id",
        "device_auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "scope": "user.read offline_access Mail.Read Mail.Send Calendars.ReadWrite Tasks.ReadWrite",
    },
}
