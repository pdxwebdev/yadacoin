"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2026 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

from coincurve import PrivateKey

from plugins.credentialissuer.zkp import generate_proof
from plugins.livestreamannouncement import obs, postboot, service, store, vp
from plugins.livestreamannouncement.handlers import ChannelListHandler
from yadacoin.core.branchannouncement import BranchAnnouncement
from yadacoin.core.credentialannouncement import did_for

from ..test_setup import AsyncTestCase

_PRE = "1PrerotatedKeyHashAAAAAAAAAAAAAAA"
_TWICE = "1TwicePrerotatedKeyHashBBBBBBBBBB"


class _FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *a, **k):
        return self

    def skip(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    async def to_list(self, length=None):
        return list(self.docs)


class _Coll:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def find_one(self, filt):
        for d in self.docs:
            if _match(d, filt):
                return dict(d)
        return None

    async def update_one(self, filt, update, upsert=False):
        for i, d in enumerate(self.docs):
            if _match(d, filt):
                if "$set" in update:
                    d.update(update["$set"])
                return MagicMock()
        if upsert:
            doc = dict(filt)
            if "$set" in update:
                doc.update(update["$set"])
            self.docs.append(doc)
        return MagicMock()

    async def update_many(self, filt, update):
        for d in self.docs:
            if _match(d, filt):
                d.update(update.get("$set") or {})
        return MagicMock()

    async def delete_one(self, filt):
        self.docs = [d for d in self.docs if not _match(d, filt)]

    async def replace_one(self, filt, doc, upsert=False):
        for i, d in enumerate(self.docs):
            if _match(d, filt):
                self.docs[i] = dict(doc)
                return
        if upsert:
            self.docs.append(dict(doc))

    def find(self, filt=None):
        filt = filt or {}
        return _FakeCursor([d for d in self.docs if _match(d, filt)])


def _match(doc, filt):
    if not filt:
        return True
    if "$or" in filt:
        return any(_match(doc, c) for c in filt["$or"])
    for k, v in filt.items():
        if k == "$or":
            continue
        if isinstance(v, dict) and "$ne" in v:
            if doc.get(k) == v["$ne"]:
                return False
            continue
        if doc.get(k) != v:
            return False
    return True


class _FakeDB:
    def __init__(self):
        self.livestream_channels = _Coll()
        self.livestream_grants = _Coll()
        self.livestream_blocked_branches = _Coll()
        self.livestream_challenges = _Coll()
        self.livestream_settings = _Coll()
        self.key_event_log = _Coll()

    def __getitem__(self, name):
        return getattr(self, name)


def _config():
    cfg = MagicMock()
    cfg.peer_type = "service_provider"
    cfg.username_signature = "nodeSig"
    cfg.livestream_ingest_url = "rtmp://sp/live"
    cfg.livestream_playback_url = "https://sp/live"
    cfg.age_credential_issuers = ["issuerTxn"]
    cfg.obs_websocket_host = "127.0.0.1"
    cfg.obs_websocket_port = 4455
    cfg.obs_websocket_password = "static-otp"
    cfg.capabilities = {}
    db = _FakeDB()
    cfg.mongo.async_db = db
    return cfg


class TestApiUnwrap(AsyncTestCase):
    def test_result_wrapper(self):
        wrapped = {"status": True, "result": {"nonce": "abc"}}
        self.assertEqual(service._result(wrapped)["nonce"], "abc")
        self.assertEqual(service._result({"nonce": "abc"})["nonce"], "abc")


class TestOBSAuth(AsyncTestCase):
    def test_static_password_not_per_start(self):
        a = obs.obs_auth_string("static-otp", "salt", "challenge")
        b = obs.obs_auth_string("static-otp", "salt", "challenge")
        self.assertEqual(a, b)
        other = obs.obs_auth_string("other", "salt", "challenge")
        self.assertNotEqual(a, other)


class TestBranchTypeHash(AsyncTestCase):
    def test_untyped_to_string_pre_twice(self):
        ba = BranchAnnouncement(
            prerotated_key_hash=_PRE, twice_prerotated_key_hash=_TWICE
        )
        self.assertEqual(ba.to_string(), _PRE + _TWICE)


class TestPostbootCapabilities(AsyncTestCase):
    async def test_service_provider_sets_ingest(self):
        cfg = _config()
        app = MagicMock()
        app.config = cfg
        await postboot.go(app)
        cap = cfg.capabilities["livestream"]
        self.assertTrue(cap["ingest"])
        self.assertEqual(cap["protocol"], "rtmp")
        self.assertEqual(cap["url"], "rtmp://sp/live")

    async def test_missing_url_ingest_false(self):
        cfg = _config()
        cfg.livestream_ingest_url = ""
        app = MagicMock()
        app.config = cfg
        await postboot.go(app)
        self.assertFalse(cfg.capabilities["livestream"]["ingest"])


def _vp_for(cfg, nonce, issuer_id="issuerTxn"):
    sk = PrivateKey()
    subject = "subjectSig"
    proof = generate_proof("22" * 32, prev_key_hash=subject)
    vc = {
        "type": ["VerifiableCredential", "AgeOver18Credential"],
        "issuer": did_for("issuerSig"),
        "credentialSubject": {"id": did_for(subject), "ageOver18": True},
        "expirationDate": "2099-01-01T00:00:00Z",
        "expires": int(time.time()) + 3600,
        "issuer_identity_announcement": issuer_id,
        "proof": proof,
    }
    return vp.build_vp(
        sk.to_hex(), subject, vc, nonce, issuer_identity_announcement=issuer_id
    )


async def _allow_branch_key(cfg, channel_id, sk):
    pub = sk.public_key.format(compressed=True).hex()
    await cfg.mongo.async_db.key_event_log.insert_one(
        {
            "branch_peer": f"livestream:{channel_id}",
            "public_key_hash": service.signing_address(pub),
        }
    )


class TestGrantsAndAgeGate(AsyncTestCase):
    async def test_grant_rejected_for_unknown_branch_key(self):
        cfg = _config()
        await store.insert_challenge(
            cfg,
            {
                "nonce": "n0",
                "aud": "a",
                "exp": int(time.time()) + 60,
                "action": "grant",
                "channel_id": "ch1",
            },
        )
        sk = PrivateKey()
        with self.assertRaises(service.LivestreamServiceError) as ctx:
            await service.accept_grant(
                cfg,
                {
                    "channel_id": "ch1",
                    "nonce": "n0",
                    "ratchet_pub": sk.public_key.format(compressed=True).hex(),
                    "signature": service.sign_ratchet_nonce(sk.to_hex(), "n0"),
                },
            )
        self.assertIn("not authorized", str(ctx.exception))

    async def test_publish_requires_grant(self):
        cfg = _config()
        with self.assertRaises(service.LivestreamServiceError):
            await service.assert_publish_allowed(cfg, "live/ch1")
        await store.insert_grant(
            cfg,
            {
                "channel_id": "ch1",
                "active": True,
                "expires": int(time.time()) + 60,
                "age_restricted": False,
            },
        )
        result = await service.assert_publish_allowed(cfg, "live/ch1")
        self.assertEqual(result["channel_id"], "ch1")

    async def test_grant_rejected_without_vp_when_age_restricted(self):
        cfg = _config()
        ch = await store.insert_challenge(
            cfg,
            {
                "nonce": "n1",
                "aud": "a",
                "exp": int(time.time()) + 60,
                "action": "grant",
                "channel_id": "ch1",
            },
        )
        sk = PrivateKey()
        await _allow_branch_key(cfg, "ch1", sk)
        nonce = "n1"
        sig = service.sign_ratchet_nonce(sk.to_hex(), nonce)
        with self.assertRaises(service.LivestreamServiceError) as ctx:
            await service.accept_grant(
                cfg,
                {
                    "channel_id": "ch1",
                    "age_restricted": True,
                    "nonce": nonce,
                    "ratchet_pub": sk.public_key.format(compressed=True).hex(),
                    "signature": sig,
                    "publisher_username_signature": "pub",
                },
            )
        self.assertIn("VP is required", str(ctx.exception))

    async def test_grant_rejected_if_issuer_not_in_allowlist(self):
        cfg = _config()
        await store.insert_challenge(
            cfg,
            {
                "nonce": "n2",
                "aud": "a",
                "exp": int(time.time()) + 60,
                "action": "grant",
                "channel_id": "ch1",
            },
        )
        sk = PrivateKey()
        await _allow_branch_key(cfg, "ch1", sk)
        nonce = "n2"
        sig = service.sign_ratchet_nonce(sk.to_hex(), nonce)
        presentation = _vp_for(cfg, nonce, issuer_id="not-allowed")
        with self.assertRaises(service.LivestreamServiceError) as ctx:
            await service.accept_grant(
                cfg,
                {
                    "channel_id": "ch1",
                    "age_restricted": True,
                    "nonce": nonce,
                    "ratchet_pub": sk.public_key.format(compressed=True).hex(),
                    "signature": sig,
                    "publisher_username_signature": "pub",
                    "vp": presentation,
                },
            )
        self.assertIn("issuer is not in age_credential_issuers", str(ctx.exception))

    async def test_grant_accepted_with_vp(self):
        cfg = _config()
        await store.insert_challenge(
            cfg,
            {
                "nonce": "n3",
                "aud": "a",
                "exp": int(time.time()) + 60,
                "action": "grant",
                "channel_id": "ch1",
            },
        )
        sk = PrivateKey()
        await _allow_branch_key(cfg, "ch1", sk)
        nonce = "n3"
        sig = service.sign_ratchet_nonce(sk.to_hex(), nonce)
        presentation = _vp_for(cfg, nonce, issuer_id="issuerTxn")
        grant = await service.accept_grant(
            cfg,
            {
                "channel_id": "ch1",
                "age_restricted": True,
                "nonce": nonce,
                "ratchet_pub": sk.public_key.format(compressed=True).hex(),
                "signature": sig,
                "publisher_username_signature": "pub",
                "vp": presentation,
            },
        )
        self.assertTrue(grant["active"])
        self.assertTrue(grant["vp_verified"])

    async def test_blocked_branch_refuses_live(self):
        cfg = _config()
        await store.insert_channel(
            cfg,
            {
                "channel_id": "chb",
                "title": "t",
                "announcement_txn_id": "txn1",
                "branch_commit": "commit1",
                "status": "idle",
            },
        )
        await store.upsert_blocked_branch(
            cfg,
            channel_id="chb",
            branch_commit="commit1",
            transaction_id="txn1",
            reason_code="csam",
        )
        with self.assertRaises(service.LivestreamServiceError) as ctx:
            await service.on_publish(cfg, "chb")
        self.assertIn("blocked", str(ctx.exception))

    async def test_whitelist_allows(self):
        cfg = _config()
        await store.insert_channel(
            cfg,
            {
                "channel_id": "chw",
                "title": "t",
                "announcement_txn_id": "txn2",
                "branch_commit": "commit2",
                "status": "idle",
            },
        )
        await store.upsert_blocked_branch(
            cfg,
            channel_id="chw",
            branch_commit="commit2",
            transaction_id="txn2",
            reason_code="csam",
        )
        await store.whitelist_blocked(cfg, "chw")
        await store.insert_grant(
            cfg,
            {
                "channel_id": "chw",
                "active": True,
                "expires": int(time.time()) + 60,
                "age_restricted": False,
                "vp_verified": False,
            },
        )
        result = await service.on_publish(cfg, "chw")
        self.assertTrue(result["ok"])


class TestPublicLiveList(AsyncTestCase):
    async def test_live_list_includes_protocol_identity(self):
        cfg = _config()
        await store.insert_channel(
            cfg,
            {
                "channel_id": "chan1",
                "title": "On air",
                "description": "now",
                "status": "live",
                "age_restricted": False,
                "branch_peer": "livestream:chan1",
                "announcement_txn_id": "ann1",
                "publisher_username_signature": "sig1",
            },
        )
        await store.insert_grant(
            cfg,
            {
                "channel_id": "chan1",
                "active": True,
                "publishing": True,
                "expires": int(time.time()) + 60,
                "age_restricted": False,
            },
        )
        identity = {
            "skip": False,
            "branch_type": "livestream",
            "protocol_livestream": True,
            "owner": "inception1",
            "public_key_hash": "pkh1",
            "username": "alice",
            "transaction_id": "ann1",
            "publisher_username_signature": "sig1",
        }
        with patch.object(
            service, "_identity_for_channel", new=AsyncMock(return_value=identity)
        ):
            results = await service.public_live_list(cfg)
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row["kind"], "livestream")
        self.assertEqual(row["branch_type"], "livestream")
        self.assertTrue(row["protocol_livestream"])
        self.assertEqual(row["username"], "alice")
        self.assertEqual(row["public_key_hash"], "pkh1")
        self.assertEqual(row["playback_url"], "https://sp/live/chan1")

    async def test_identity_follows_livestream_branch_announcement(self):
        cfg = _config()
        cfg.mongo.async_db.miner_transactions = _Coll()
        await cfg.mongo.async_db.miner_transactions.insert_one(
            {
                "id": "ann-peer",
                "inception_public_key_hash": "inc",
                "public_key_hash": "pkh-peer",
                "relationship": {
                    "branch": {
                        "type": "peer",
                        "prerotated_key_hash": "a",
                        "twice_prerotated_key_hash": "b",
                    }
                },
            }
        )
        peer = await service._identity_for_channel(
            cfg,
            {
                "announcement_txn_id": "ann-peer",
                "branch_peer": "livestream:x",
            },
        )
        self.assertTrue(peer["skip"])
        await cfg.mongo.async_db.miner_transactions.insert_one(
            {
                "id": "ann-live",
                "inception_public_key_hash": "inc-live",
                "public_key_hash": "pkh-live",
                "relationship": {
                    "branch": {
                        "type": "livestream",
                        "prerotated_key_hash": "c",
                        "twice_prerotated_key_hash": "d",
                    }
                },
            }
        )
        live = await service._identity_for_channel(
            cfg,
            {
                "announcement_txn_id": "ann-live",
                "branch_peer": "livestream:chan",
                "publisher_username_signature": "sig-live",
            },
        )
        self.assertFalse(live["skip"])
        self.assertTrue(live["protocol_livestream"])
        self.assertEqual(live["owner"], "inc-live")
        self.assertEqual(live["public_key_hash"], "pkh-live")
        self.assertEqual(live["branch_type"], "livestream")

    async def test_non_livestream_branch_is_omitted(self):
        cfg = _config()
        await store.insert_channel(
            cfg,
            {
                "channel_id": "chan2",
                "title": "Nope",
                "status": "live",
                "branch_peer": "peer:chan2",
            },
        )
        await store.insert_grant(
            cfg,
            {
                "channel_id": "chan2",
                "active": True,
                "publishing": True,
                "expires": int(time.time()) + 60,
            },
        )
        with patch.object(
            service,
            "_identity_for_channel",
            new=AsyncMock(return_value={"skip": True}),
        ):
            results = await service.public_live_list(cfg)
        self.assertEqual(results, [])

    async def test_go_live_flag_is_not_enough(self):
        cfg = _config()
        await store.insert_channel(
            cfg,
            {
                "channel_id": "chan",
                "title": "Starting",
                "status": "live",
                "branch_peer": "livestream:chan",
            },
        )
        await store.insert_grant(
            cfg,
            {
                "channel_id": "chan",
                "active": True,
                "publishing": False,
                "expires": int(time.time()) + 60,
            },
        )
        self.assertEqual(await service.public_live_list(cfg), [])

    async def test_on_publish_confirms_live(self):
        cfg = _config()
        await store.insert_channel(
            cfg,
            {
                "channel_id": "chan",
                "title": "On air",
                "status": "starting",
                "age_restricted": False,
                "branch_peer": "livestream:chan",
            },
        )
        await store.insert_grant(
            cfg,
            {
                "channel_id": "chan",
                "active": True,
                "publishing": False,
                "expires": int(time.time()) + 60,
                "age_restricted": False,
            },
        )
        self.assertEqual(await service.public_live_list(cfg), [])
        result = await service.on_publish(cfg, "chan")
        self.assertTrue(result["ok"])
        results = await service.public_live_list(cfg)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["channel_id"], "chan")
        self.assertEqual(results[0]["status"], "live")


class TestWalletUnlock(AsyncTestCase):
    async def test_wallet_locked_returns_401_on_mint_routes(self):
        handler = ChannelListHandler.__new__(ChannelListHandler)
        handler.request = MagicMock()
        handler.request.method = "POST"
        handler.request.path = "/livestream-announcements/api/v1/channels"
        handler._finished = False
        handler.set_status = MagicMock()
        handler.render_as_json = MagicMock()
        handler.wallet_is_unlocked = AsyncMock(return_value=False)
        from yadacoin.http.base import BaseHandler

        async def fake_prepare(self, exceptions=None):
            return None

        with patch.object(BaseHandler, "prepare", fake_prepare):
            await ChannelListHandler.prepare(handler)
        handler.set_status.assert_called_with(401)
