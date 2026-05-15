"""
Unit tests for yadacoin.core.recoveryannouncement — targets 100 % branch coverage.
"""

import unittest

from yadacoin.core.recoveryannouncement import (
    RecoveryAnnouncement,
    RecoveryProof,
    RecoveryTransition,
)

# ---------------------------------------------------------------------------
# RecoveryAnnouncement
# ---------------------------------------------------------------------------


class TestRecoveryAnnouncementInit(unittest.TestCase):
    def test_minimal_valid(self):
        ra = RecoveryAnnouncement("deadbeef")
        self.assertEqual(ra.witness_hash, "deadbeef")
        self.assertEqual(ra.lookup_id, "")
        self.assertEqual(ra.hints_iv, "")
        self.assertEqual(ra.hints_ct, "")
        self.assertEqual(ra.extra_fields, {})

    def test_all_fields(self):
        ra = RecoveryAnnouncement(
            "ABCD1234",
            lookup_id="EF0123",
            hints_iv="AABB",
            hints_ct="base64==",
        )
        # witness_hash and hex fields are lowercased
        self.assertEqual(ra.witness_hash, "abcd1234")
        self.assertEqual(ra.lookup_id, "ef0123")
        self.assertEqual(ra.hints_iv, "aabb")
        # ct is base64 — verbatim
        self.assertEqual(ra.hints_ct, "base64==")

    def test_uppercase_normalised_to_lowercase(self):
        ra = RecoveryAnnouncement("AABBCCDD", lookup_id="EEFF", hints_iv="1122")
        self.assertEqual(ra.witness_hash, "aabbccdd")
        self.assertEqual(ra.lookup_id, "eeff")
        self.assertEqual(ra.hints_iv, "1122")

    def test_none_optional_fields_treated_as_empty(self):
        ra = RecoveryAnnouncement("aabb", lookup_id=None, hints_iv=None, hints_ct=None)
        self.assertEqual(ra.lookup_id, "")
        self.assertEqual(ra.hints_iv, "")
        self.assertEqual(ra.hints_ct, "")

    def test_extra_kwargs_stored(self):
        ra = RecoveryAnnouncement("aabb", future_field="value")
        self.assertEqual(ra.extra_fields, {"future_field": "value"})

    def test_empty_witness_hash_raises(self):
        with self.assertRaises(ValueError):
            RecoveryAnnouncement("")

    def test_none_witness_hash_raises(self):
        with self.assertRaises(ValueError):
            RecoveryAnnouncement(None)

    def test_non_string_witness_hash_raises(self):
        with self.assertRaises(ValueError):
            RecoveryAnnouncement(12345)

    def test_non_string_lookup_id_raises(self):
        with self.assertRaises(ValueError):
            RecoveryAnnouncement("aabb", lookup_id=42)

    def test_non_string_hints_iv_raises(self):
        with self.assertRaises(ValueError):
            RecoveryAnnouncement("aabb", hints_iv=42)

    def test_non_string_hints_ct_raises(self):
        with self.assertRaises(ValueError):
            RecoveryAnnouncement("aabb", hints_ct=42)


class TestRecoveryAnnouncementFromDict(unittest.TestCase):
    def test_legacy_string(self):
        ra = RecoveryAnnouncement.from_dict("cafebabe")
        self.assertEqual(ra.witness_hash, "cafebabe")

    def test_extended_dict(self):
        ra = RecoveryAnnouncement.from_dict(
            {
                "witness_hash": "aabb",
                "lookup_id": "ccdd",
                "hints_iv": "eeff",
                "hints_ct": "ct==",
            }
        )
        self.assertEqual(ra.witness_hash, "aabb")
        self.assertEqual(ra.lookup_id, "ccdd")

    def test_non_dict_non_string_raises(self):
        with self.assertRaises(ValueError):
            RecoveryAnnouncement.from_dict(42)


class TestRecoveryAnnouncementFromRelationship(unittest.TestCase):
    def test_legacy_flat(self):
        ra = RecoveryAnnouncement.from_relationship({"recovery": "deadbeef"})
        self.assertEqual(ra.witness_hash, "deadbeef")

    def test_extended_dict(self):
        ra = RecoveryAnnouncement.from_relationship(
            {"recovery": {"witness_hash": "aa", "lookup_id": "bb"}}
        )
        self.assertEqual(ra.witness_hash, "aa")
        self.assertEqual(ra.lookup_id, "bb")

    def test_missing_recovery_key_raises(self):
        with self.assertRaises(ValueError):
            RecoveryAnnouncement.from_relationship({"wrong_key": "value"})

    def test_non_dict_raises(self):
        with self.assertRaises(ValueError):
            RecoveryAnnouncement.from_relationship("not a dict")


class TestRecoveryAnnouncementToDict(unittest.TestCase):
    def test_legacy_form_when_no_extras(self):
        ra = RecoveryAnnouncement("abcd")
        d = ra.to_dict()
        self.assertEqual(d, {"recovery": "abcd"})

    def test_extended_form_with_lookup_id(self):
        ra = RecoveryAnnouncement("abcd", lookup_id="1234")
        d = ra.to_dict()
        self.assertEqual(d["recovery"]["witness_hash"], "abcd")
        self.assertEqual(d["recovery"]["lookup_id"], "1234")
        self.assertNotIn("hints_iv", d["recovery"])
        self.assertNotIn("hints_ct", d["recovery"])

    def test_extended_form_with_hints(self):
        ra = RecoveryAnnouncement("abcd", hints_iv="iv", hints_ct="ct==")
        d = ra.to_dict()
        self.assertEqual(d["recovery"]["hints_iv"], "iv")
        self.assertEqual(d["recovery"]["hints_ct"], "ct==")

    def test_extended_form_with_extra_fields(self):
        ra = RecoveryAnnouncement("abcd", future="yes")
        d = ra.to_dict()
        self.assertIsInstance(d["recovery"], dict)
        self.assertEqual(d["recovery"]["future"], "yes")

    def test_roundtrip_legacy(self):
        original = {"recovery": "cafebabe"}
        ra = RecoveryAnnouncement.from_relationship(original)
        self.assertEqual(ra.to_dict(), original)

    def test_roundtrip_extended(self):
        original = {
            "recovery": {
                "witness_hash": "aabb",
                "lookup_id": "ccdd",
                "hints_iv": "eeff",
                "hints_ct": "abc+==",
            }
        }
        ra = RecoveryAnnouncement.from_relationship(original)
        self.assertEqual(ra.to_dict(), original)


class TestRecoveryAnnouncementToString(unittest.TestCase):
    def test_legacy_preimage(self):
        ra = RecoveryAnnouncement("abcd")
        self.assertEqual(ra.to_string(), "abcd")

    def test_extended_preimage(self):
        ra = RecoveryAnnouncement("wh", lookup_id="lid", hints_iv="iv", hints_ct="ct")
        self.assertEqual(ra.to_string(), "whlidivct")

    def test_partial_fields(self):
        ra = RecoveryAnnouncement("wh", lookup_id="lid")
        self.assertEqual(ra.to_string(), "whlid")


class TestRecoveryAnnouncementHasHints(unittest.TestCase):
    def test_false_when_no_hints(self):
        ra = RecoveryAnnouncement("abcd")
        self.assertFalse(ra.has_hints())

    def test_false_when_only_iv(self):
        ra = RecoveryAnnouncement("abcd", hints_iv="iv")
        self.assertFalse(ra.has_hints())

    def test_false_when_only_ct(self):
        ra = RecoveryAnnouncement("abcd", hints_ct="ct==")
        self.assertFalse(ra.has_hints())

    def test_true_when_both_iv_and_ct(self):
        ra = RecoveryAnnouncement("abcd", hints_iv="iv", hints_ct="ct==")
        self.assertTrue(ra.has_hints())


class TestRecoveryAnnouncementRepr(unittest.TestCase):
    def test_repr_contains_witness_hash(self):
        ra = RecoveryAnnouncement("abcdef")
        r = repr(ra)
        self.assertIn("abcdef", r)
        self.assertIn("RecoveryAnnouncement", r)


# ---------------------------------------------------------------------------
# RecoveryProof
# ---------------------------------------------------------------------------


class TestRecoveryProofInit(unittest.TestCase):
    def test_valid(self):
        rp = RecoveryProof("aa", "bb", "cc")
        self.assertEqual(rp.commitment, "aa")
        self.assertEqual(rp.R, "bb")
        self.assertEqual(rp.s, "cc")
        self.assertEqual(rp.extra_fields, {})

    def test_extra_kwargs_stored(self):
        rp = RecoveryProof("aa", "bb", "cc", extra="x")
        self.assertEqual(rp.extra_fields, {"extra": "x"})

    def test_empty_commitment_raises(self):
        with self.assertRaises(ValueError):
            RecoveryProof("", "bb", "cc")

    def test_none_commitment_raises(self):
        with self.assertRaises(ValueError):
            RecoveryProof(None, "bb", "cc")

    def test_non_string_R_raises(self):
        with self.assertRaises(ValueError):
            RecoveryProof("aa", 42, "cc")

    def test_empty_s_raises(self):
        with self.assertRaises(ValueError):
            RecoveryProof("aa", "bb", "")


class TestRecoveryProofFromDict(unittest.TestCase):
    def test_valid(self):
        rp = RecoveryProof.from_dict({"commitment": "aa", "R": "bb", "s": "cc"})
        self.assertEqual(rp.commitment, "aa")

    def test_non_dict_raises(self):
        with self.assertRaises(ValueError):
            RecoveryProof.from_dict("not a dict")

    def test_missing_field_raises(self):
        with self.assertRaises(ValueError):
            RecoveryProof.from_dict({"commitment": "aa", "R": "bb"})

    def test_extra_fields_passed_through(self):
        rp = RecoveryProof.from_dict(
            {"commitment": "aa", "R": "bb", "s": "cc", "extra": "yes"}
        )
        self.assertEqual(rp.extra_fields, {"extra": "yes"})


class TestRecoveryProofFromRelationship(unittest.TestCase):
    def test_valid(self):
        rp = RecoveryProof.from_relationship(
            {"recovers": {"commitment": "aa", "R": "bb", "s": "cc"}}
        )
        self.assertEqual(rp.R, "bb")

    def test_missing_recovers_key_raises(self):
        with self.assertRaises(ValueError):
            RecoveryProof.from_relationship({"wrong": {}})

    def test_non_dict_raises(self):
        with self.assertRaises(ValueError):
            RecoveryProof.from_relationship("not a dict")


class TestRecoveryProofToDict(unittest.TestCase):
    def test_basic(self):
        rp = RecoveryProof("aa", "bb", "cc")
        d = rp.to_dict()
        self.assertEqual(d, {"recovers": {"commitment": "aa", "R": "bb", "s": "cc"}})

    def test_extra_fields_included(self):
        rp = RecoveryProof("aa", "bb", "cc", extra="yes")
        d = rp.to_dict()
        self.assertEqual(d["recovers"]["extra"], "yes")


class TestRecoveryProofToString(unittest.TestCase):
    def test_concatenation(self):
        rp = RecoveryProof("aabb", "ccdd", "eeff")
        self.assertEqual(rp.to_string(), "aabbccddeeff")


class TestRecoveryProofRepr(unittest.TestCase):
    def test_repr_contains_class_name(self):
        rp = RecoveryProof("abcdefgh", "12345678", "aabbccdd")
        r = repr(rp)
        self.assertIn("RecoveryProof", r)
        # Repr truncates to first 8 chars of each field
        self.assertIn("abcdefgh", r)


# ---------------------------------------------------------------------------
# RecoveryTransition
# ---------------------------------------------------------------------------


class TestRecoveryTransitionInit(unittest.TestCase):
    def test_stores_proof_and_announcement(self):
        proof = RecoveryProof("aa", "bb", "cc")
        ann = RecoveryAnnouncement("dd")
        rt = RecoveryTransition(proof, ann)
        self.assertIs(rt.proof, proof)
        self.assertIs(rt.announcement, ann)


class TestRecoveryTransitionFromRelationship(unittest.TestCase):
    def _make_rel(self, with_hints=False):
        rel = {
            "recovers": {"commitment": "aa", "R": "bb", "s": "cc"},
            "recovery": "dd",
        }
        if with_hints:
            rel["recovery"] = {
                "witness_hash": "dd",
                "lookup_id": "ee",
                "hints_iv": "ff",
                "hints_ct": "gg==",
            }
        return rel

    def test_valid_legacy_recovery(self):
        rt = RecoveryTransition.from_relationship(self._make_rel())
        self.assertEqual(rt.proof.commitment, "aa")
        self.assertEqual(rt.announcement.witness_hash, "dd")

    def test_valid_extended_recovery(self):
        rt = RecoveryTransition.from_relationship(self._make_rel(with_hints=True))
        self.assertEqual(rt.announcement.lookup_id, "ee")

    def test_non_dict_raises(self):
        with self.assertRaises(ValueError):
            RecoveryTransition.from_relationship("not a dict")

    def test_missing_recovers_key_raises(self):
        with self.assertRaises(ValueError):
            RecoveryTransition.from_relationship({"recovery": "dd"})

    def test_missing_recovery_key_raises(self):
        with self.assertRaises(ValueError):
            RecoveryTransition.from_relationship(
                {"recovers": {"commitment": "aa", "R": "bb", "s": "cc"}}
            )


class TestRecoveryTransitionToDict(unittest.TestCase):
    def test_merges_proof_and_announcement(self):
        proof = RecoveryProof("aa", "bb", "cc")
        ann = RecoveryAnnouncement("dd")
        rt = RecoveryTransition(proof, ann)
        d = rt.to_dict()
        self.assertIn("recovers", d)
        self.assertIn("recovery", d)
        self.assertEqual(d["recovers"]["commitment"], "aa")
        # Legacy announcement → flat string
        self.assertEqual(d["recovery"], "dd")

    def test_extended_announcement_in_dict(self):
        proof = RecoveryProof("aa", "bb", "cc")
        ann = RecoveryAnnouncement("dd", lookup_id="ee")
        rt = RecoveryTransition(proof, ann)
        d = rt.to_dict()
        self.assertIsInstance(d["recovery"], dict)
        self.assertEqual(d["recovery"]["witness_hash"], "dd")


class TestRecoveryTransitionToString(unittest.TestCase):
    def test_concatenates_proof_and_announcement(self):
        proof = RecoveryProof("aa", "bb", "cc")
        ann = RecoveryAnnouncement("dd", lookup_id="ee", hints_iv="ff", hints_ct="gg")
        rt = RecoveryTransition(proof, ann)
        expected = proof.to_string() + ann.to_string()
        self.assertEqual(rt.to_string(), expected)

    def test_legacy_announcement(self):
        proof = RecoveryProof("aa", "bb", "cc")
        ann = RecoveryAnnouncement("dd")
        rt = RecoveryTransition(proof, ann)
        self.assertEqual(rt.to_string(), "aabbccdd")


class TestRecoveryTransitionRepr(unittest.TestCase):
    def test_repr_contains_class_names(self):
        proof = RecoveryProof("abcdefgh", "12345678", "aabbccdd")
        ann = RecoveryAnnouncement("eeffgghh")
        rt = RecoveryTransition(proof, ann)
        r = repr(rt)
        self.assertIn("RecoveryTransition", r)


if __name__ == "__main__":
    unittest.main()
