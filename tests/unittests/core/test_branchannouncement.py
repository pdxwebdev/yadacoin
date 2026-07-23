"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

from yadacoin.core.branchannouncement import BranchAnnouncement

_PRE = "1PrerotatedKeyHashAAAAAAAAAAAAAAA"
_TWICE = "1TwicePrerotatedKeyHashBBBBBBBBBB"


class TestBranchAnnouncementInit(unittest.TestCase):
    def test_valid_construction(self):
        ba = BranchAnnouncement(
            prerotated_key_hash=_PRE, twice_prerotated_key_hash=_TWICE
        )
        self.assertEqual(ba.prerotated_key_hash, _PRE)
        self.assertEqual(ba.twice_prerotated_key_hash, _TWICE)

    def test_empty_pre_raises(self):
        with self.assertRaises(ValueError):
            BranchAnnouncement(prerotated_key_hash="", twice_prerotated_key_hash=_TWICE)

    def test_empty_twice_raises(self):
        with self.assertRaises(ValueError):
            BranchAnnouncement(prerotated_key_hash=_PRE, twice_prerotated_key_hash="")

    def test_none_pre_raises(self):
        with self.assertRaises(ValueError):
            BranchAnnouncement(
                prerotated_key_hash=None, twice_prerotated_key_hash=_TWICE
            )

    def test_none_twice_raises(self):
        with self.assertRaises(ValueError):
            BranchAnnouncement(prerotated_key_hash=_PRE, twice_prerotated_key_hash=None)

    def test_non_string_raises(self):
        with self.assertRaises(ValueError):
            BranchAnnouncement(
                prerotated_key_hash=123, twice_prerotated_key_hash=_TWICE
            )
        with self.assertRaises(ValueError):
            BranchAnnouncement(prerotated_key_hash=_PRE, twice_prerotated_key_hash=123)

    def test_relationship_key_constant(self):
        self.assertEqual(BranchAnnouncement.RELATIONSHIP_KEY, "branch")

    def test_to_dict(self):
        ba = BranchAnnouncement(
            prerotated_key_hash=_PRE, twice_prerotated_key_hash=_TWICE
        )
        self.assertEqual(
            ba.to_dict(),
            {
                "prerotated_key_hash": _PRE,
                "twice_prerotated_key_hash": _TWICE,
            },
        )

    def test_to_dict_includes_extra_fields(self):
        ba = BranchAnnouncement(
            prerotated_key_hash=_PRE,
            twice_prerotated_key_hash=_TWICE,
            note="x",
        )
        d = ba.to_dict()
        self.assertEqual(d["note"], "x")
        self.assertEqual(d["prerotated_key_hash"], _PRE)

    def test_to_string_order(self):
        ba = BranchAnnouncement(
            prerotated_key_hash=_PRE, twice_prerotated_key_hash=_TWICE
        )
        self.assertEqual(ba.to_string(), _PRE + _TWICE)
        self.assertEqual(ba.to_string(), ba.to_string())

    def test_get_string_none_returns_empty(self):
        self.assertEqual(BranchAnnouncement.get_string(None), "")
        self.assertEqual(BranchAnnouncement.get_string("x"), "x")

    def test_from_dict_valid(self):
        ba = BranchAnnouncement.from_dict(
            {"prerotated_key_hash": _PRE, "twice_prerotated_key_hash": _TWICE}
        )
        self.assertEqual(ba.prerotated_key_hash, _PRE)
        self.assertEqual(ba.twice_prerotated_key_hash, _TWICE)

    def test_from_dict_non_dict_raises(self):
        with self.assertRaises(ValueError):
            BranchAnnouncement.from_dict("bad")

    def test_from_dict_missing_pre_raises(self):
        with self.assertRaises(ValueError):
            BranchAnnouncement.from_dict({"twice_prerotated_key_hash": _TWICE})

    def test_from_dict_missing_twice_raises(self):
        with self.assertRaises(ValueError):
            BranchAnnouncement.from_dict({"prerotated_key_hash": _PRE})

    def test_from_relationship_valid(self):
        ba = BranchAnnouncement.from_relationship(
            {
                "branch": {
                    "prerotated_key_hash": _PRE,
                    "twice_prerotated_key_hash": _TWICE,
                }
            }
        )
        self.assertEqual(ba.prerotated_key_hash, _PRE)
        self.assertEqual(ba.twice_prerotated_key_hash, _TWICE)

    def test_from_relationship_missing_key_raises(self):
        with self.assertRaises(ValueError):
            BranchAnnouncement.from_relationship({"other": {}})

    def test_round_trip(self):
        ba = BranchAnnouncement(
            prerotated_key_hash=_PRE, twice_prerotated_key_hash=_TWICE
        )
        ba2 = BranchAnnouncement.from_dict(ba.to_dict())
        self.assertEqual(ba.to_string(), ba2.to_string())

    def test_repr(self):
        ba = BranchAnnouncement(
            prerotated_key_hash=_PRE, twice_prerotated_key_hash=_TWICE
        )
        self.assertIn("BranchAnnouncement", repr(ba))
        self.assertIn(_PRE, repr(ba))
        self.assertIn(_TWICE, repr(ba))


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
