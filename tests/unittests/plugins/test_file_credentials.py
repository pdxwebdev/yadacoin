"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import time
import unittest

from plugins.credentialissuer.service import build_vc
from plugins.credentialissuer.zkp import generate_proof
from plugins.fileannouncement.credentials import (
    PresentationError,
    badge_satisfies,
    credential_requirements,
    credentials_satisfy,
    presentation_from_parts,
    requirement_applies,
    verify_presentation,
)
from yadacoin.core.credentialannouncement import did_for

_SUBJECT = "subjectUsernameSignatureAAAA"
_ISSUER = "issuerUsernameSignatureBBBB"
_OTHER = "otherIssuerSignatureCCCC"


def _vc(claim="ageOver18", issuer=_ISSUER, subject=_SUBJECT, expires=None):
    expires = int(expires or (time.time() + 3600))
    proof = generate_proof("11" * 32, prev_key_hash=subject)
    return build_vc(subject, issuer, claim, expires, proof)


def _vp(vc, holder=None):
    return {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        "type": ["VerifiablePresentation"],
        "holder": holder if holder is not None else did_for(_SUBJECT),
        "verifiableCredential": [vc],
    }


class TestCredentialGate(unittest.TestCase):
    def test_thumbnail_is_not_gated(self):
        live = {
            "file_id": "media",
            "thumbnail_file_id": "thumb",
            "required_claim": "ageOver18",
        }
        self.assertTrue(requirement_applies(live, "media"))
        self.assertFalse(requirement_applies(live, "thumb"))
        self.assertFalse(requirement_applies({"file_id": "media"}, "media"))
        listed = {
            "file_id": "media",
            "required_credentials": [
                {"claim": "ageOver18", "issuer": ""},
                {"claim": "member", "issuer": _ISSUER},
            ],
        }
        self.assertEqual(len(credential_requirements(listed)), 2)
        self.assertTrue(requirement_applies(listed, "media"))

    def test_badge_list_blocks_missing_claim_and_issuer(self):
        now = int(time.time())
        badge = {
            "claim": "ageOver18",
            "expires": now + 100,
            "issuer_username_signature": _ISSUER,
            "proof_valid": True,
        }
        self.assertTrue(badge_satisfies(badge, "ageOver18", "", now))
        self.assertFalse(badge_satisfies(badge, "member", "", now))
        self.assertTrue(badge_satisfies(badge, "ageOver18", _ISSUER, now))
        self.assertFalse(badge_satisfies(badge, "ageOver18", _OTHER, now))
        self.assertFalse(
            badge_satisfies(dict(badge, expires=now - 1), "ageOver18", "", now)
        )

    def test_presentation_accepts_matching_vc(self):
        verified = verify_presentation(_vp(_vc()), "ageOver18", _ISSUER)
        self.assertEqual(verified["subject"], _SUBJECT)

    def test_presentation_rejects_wrong_claim_issuer_and_replay_shape(self):
        with self.assertRaises(PresentationError):
            verify_presentation(_vp(_vc()), "member", "")
        with self.assertRaises(PresentationError):
            verify_presentation(_vp(_vc()), "ageOver18", _OTHER)
        with self.assertRaises(PresentationError):
            verify_presentation(_vp(_vc(), holder=did_for(_OTHER)), "ageOver18", "")
        with self.assertRaises(PresentationError):
            verify_presentation(None, "ageOver18", "")
        expired = _vc(expires=int(time.time()) - 10)
        with self.assertRaises(PresentationError):
            verify_presentation(_vp(expired), "ageOver18", "")

    def test_presentation_requires_every_gate(self):
        age = _vc("ageOver18")
        member = _vc("member", issuer=_OTHER)
        both = _vp(age)
        both["verifiableCredential"].append(member)
        gates = [
            {"claim": "ageOver18", "issuer": ""},
            {"claim": "member", "issuer": _OTHER},
        ]
        verified = verify_presentation(both, gates=gates)
        self.assertEqual(verified["subject"], _SUBJECT)
        with self.assertRaises(PresentationError):
            verify_presentation(_vp(age), gates=gates)

    def test_username_issuer_matches_identity_signature(self):
        names = {_ISSUER: "local_node_B"}
        badge = {
            "claim": "ageOver18",
            "expires": int(time.time()) + 100,
            "issuer_username_signature": _ISSUER,
            "issuer_username": "local_node_B",
            "proof_valid": True,
        }
        member = dict(badge, claim="member")
        gates = [
            {"claim": "ageOver18", "issuer": "local_node_B"},
            {"claim": "member", "issuer": "local_node_B"},
        ]
        self.assertTrue(badge_satisfies(badge, "ageOver18", "local_node_B"))
        self.assertTrue(credentials_satisfy([badge, member], gates, issuer_names=names))
        self.assertFalse(credentials_satisfy([badge], gates, issuer_names=names))
        verified = verify_presentation(
            _vp(_vc()), "ageOver18", "local_node_B", issuer_names=names
        )
        self.assertEqual(verified["subject"], _SUBJECT)

    def test_presentation_query_roundtrip(self):
        import base64
        import json

        raw = json.dumps(_vp(_vc())).encode()
        token = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        again = presentation_from_parts("", token)
        self.assertEqual(again["type"], ["VerifiablePresentation"])
        verified = verify_presentation(again, "ageOver18", "")
        self.assertTrue(verified["ok"])
