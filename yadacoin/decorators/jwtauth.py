"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import jwt

secret_key = "my_secret_key"
# Hardcoded revocation cutoff (Unix epoch, 2026-06-30 00:00:00 UTC).
# Any wallet JWT/cookie whose issue timestamp predates this is rejected, so
# every token issued before deploy is revoked without needing an unlock to
# write a cutoff into Mongo. Bump this constant to force a fresh revocation.
AUTH_REVOCATION_CUTOFF = 1782777600
options = {
    "verify_signature": True,
    "verify_exp": True,
    "verify_nbf": False,
    "verify_iat": True,
    "verify_aud": False,
}


def jwtauthwallet(handler_class):
    """Handle Tornado JWT Auth"""

    def wrap_execute(handler_execute):
        def require_auth(handler, kwargs):
            auth = handler.request.headers.get("Authorization")
            if auth:
                parts = auth.split()

                if len(parts) != 2:
                    return False
                elif parts[0].lower() != "bearer":
                    return False

                token = parts[1]
                try:
                    handler.jwt = jwt.decode(
                        token,
                        handler.config.jwt_public_key,
                        verify=True,
                        algorithms=["ES256"],
                        options=handler.config.jwt_options,
                    )
                    if handler.jwt.get("timestamp", 0) < AUTH_REVOCATION_CUTOFF:
                        return False

                except:
                    return False
            else:
                return False

            return True

        def _execute(self, transforms, *args, **kwargs):
            try:
                authorized = require_auth(self, kwargs)
            except Exception:
                self.jwt = {}
                return False

            # jwt.decode() populates self.jwt before the revocation/timestamp
            # check runs, so a revoked or otherwise rejected token can still
            # leave "key_or_wif": "true" in self.jwt. Clear it on any auth
            # failure so the in-handler check cannot be satisfied by a token
            # that require_auth rejected.
            if not authorized:
                self.jwt = {}

            return handler_execute(self, transforms, *args, **kwargs)

        return _execute

    handler_class._execute = wrap_execute(handler_class._execute)
    return handler_class


def jwtauthwebuser(handler_class):
    """Handle Tornado JWT Auth"""

    def wrap_execute(handler_execute):
        def require_auth(handler, kwargs):
            auth = handler.request.headers.get("Authorization")

            if auth:
                parts = auth.split()
                if len(parts) != 3:
                    return False
                elif parts[0].lower() != "bearer":
                    return False

                token = parts[1]
                rid = parts[2]
                try:
                    handler.jwt = jwt.decode(
                        token,
                        handler.config.jwt_public_key,
                        verify=True,
                        algorithms=["ES256"],
                        options=handler.config.jwt_options,
                    )
                    mongo_jwt = handler.config.mongo.site_db.web_tokens.find_one(
                        {"token": token, "rid": rid}
                    )
                    if not mongo_jwt or handler.jwt["timestamp"] < mongo_jwt.get(
                        "value", {}
                    ).get("timestamp", 0):
                        return False

                except:
                    return False
            else:
                return False

            return True

        def _execute(self, transforms, *args, **kwargs):
            try:
                authorized = require_auth(self, kwargs)
            except Exception:
                self.jwt = {}
                return False

            # jwt.decode() populates self.jwt before the revocation/timestamp
            # check runs, so a revoked or otherwise rejected token can still
            # leave "key_or_wif": "true" in self.jwt. Clear it on any auth
            # failure so the in-handler check cannot be satisfied by a token
            # that require_auth rejected.
            if not authorized:
                self.jwt = {}

            return handler_execute(self, transforms, *args, **kwargs)

        return _execute

    handler_class._execute = wrap_execute(handler_class._execute)
    return handler_class
