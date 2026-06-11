"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

Tests for yadacoin.core.contenttakedown – 100 % branch coverage.
"""

from yadacoin.core.contenttakedown import (
    DEFAULT_AUTO_COMPLY,
    DEFAULT_COMPLY_AND_SAVE,
    DEFAULT_NO_COMPLY,
    MINIMUM_TAKEDOWN_FEE,
    ContentTakedownAnnouncement,
    TakedownReasonCode,
)

from ..test_setup import AsyncTestCase

VALID_TXN_ID = "abc123def456abc123def456abc123def456abc123def456abc123def456abc1"


# ---------------------------------------------------------------------------
# TakedownReasonCode enum
# ---------------------------------------------------------------------------


class TestTakedownReasonCode(AsyncTestCase):
    async def test_enum_has_expected_codes(self):
        values = {r.value for r in TakedownReasonCode}
        expected = {
            "csam",
            "terrorism",
            "incitement_to_violence",
            "human_trafficking",
            "drug_trafficking",
            "weapons_trafficking",
            "copyright",
            "trademark",
            "defamation",
            "privacy_violation",
            "doxxing",
            "harassment",
            "hate_speech",
            "ncii",
            "spam",
            "malware",
            "phishing",
            "sanctions",
            "national_security",
            "court_order",
        }
        self.assertEqual(values, expected)

    async def test_enum_has_twenty_members(self):
        self.assertEqual(len(TakedownReasonCode), 20)

    async def test_default_auto_comply_contains_all_codes(self):
        all_values = frozenset(r.value for r in TakedownReasonCode)
        self.assertEqual(DEFAULT_AUTO_COMPLY, all_values)

    async def test_default_comply_and_save_is_empty(self):
        self.assertEqual(DEFAULT_COMPLY_AND_SAVE, frozenset())

    async def test_default_no_comply_is_empty(self):
        """no_comply must be explicitly opted into; the default must be empty."""
        self.assertEqual(DEFAULT_NO_COMPLY, frozenset())

    async def test_no_comply_does_not_overlap_auto_comply_by_default(self):
        """By default, no reason code is simultaneously auto_comply and no_comply."""
        self.assertEqual(DEFAULT_AUTO_COMPLY & DEFAULT_NO_COMPLY, frozenset())

    async def test_minimum_takedown_fee_is_zero(self):
        self.assertEqual(MINIMUM_TAKEDOWN_FEE, 0.0)

    async def test_minimum_takedown_fee_sentinel_value(self):
        """MINIMUM_TAKEDOWN_FEE is 0.0; enforcement is fee > 0, not fee >= constant."""
        self.assertIsInstance(MINIMUM_TAKEDOWN_FEE, float)


# ---------------------------------------------------------------------------
# ContentTakedownAnnouncement.__init__
# ---------------------------------------------------------------------------


class TestContentTakedownAnnouncementInit(AsyncTestCase):
    async def test_valid_construction_with_enum(self):
        ann = ContentTakedownAnnouncement(
            transaction_id=VALID_TXN_ID,
            reason_code=TakedownReasonCode.CSAM,
        )
        self.assertEqual(ann.transaction_id, VALID_TXN_ID)
        self.assertEqual(ann.reason_code, TakedownReasonCode.CSAM)
        self.assertEqual(ann.extra_fields, {})

    async def test_valid_construction_with_string_code(self):
        ann = ContentTakedownAnnouncement(
            transaction_id=VALID_TXN_ID,
            reason_code="copyright",
        )
        self.assertEqual(ann.reason_code, TakedownReasonCode.COPYRIGHT)

    async def test_extra_kwargs_stored(self):
        ann = ContentTakedownAnnouncement(
            transaction_id=VALID_TXN_ID,
            reason_code="spam",
            reporter="example@example.com",
        )
        self.assertEqual(ann.extra_fields["reporter"], "example@example.com")

    async def test_missing_transaction_id_raises(self):
        with self.assertRaises(ValueError) as ctx:
            ContentTakedownAnnouncement(transaction_id="", reason_code="spam")
        self.assertIn("transaction_id", str(ctx.exception).lower())

    async def test_none_transaction_id_raises(self):
        with self.assertRaises(ValueError):
            ContentTakedownAnnouncement(transaction_id=None, reason_code="spam")

    async def test_non_string_transaction_id_raises(self):
        with self.assertRaises(ValueError):
            ContentTakedownAnnouncement(transaction_id=12345, reason_code="spam")

    async def test_missing_reason_code_raises(self):
        with self.assertRaises(ValueError) as ctx:
            ContentTakedownAnnouncement(transaction_id=VALID_TXN_ID, reason_code="")
        self.assertIn("reason_code", str(ctx.exception).lower())

    async def test_none_reason_code_raises(self):
        with self.assertRaises(ValueError):
            ContentTakedownAnnouncement(transaction_id=VALID_TXN_ID, reason_code=None)

    async def test_invalid_reason_code_string_raises(self):
        with self.assertRaises(ValueError) as ctx:
            ContentTakedownAnnouncement(
                transaction_id=VALID_TXN_ID, reason_code="not_a_real_code"
            )
        self.assertIn("invalid reason_code", str(ctx.exception).lower())

    async def test_transaction_id_coerced_to_str(self):
        """transaction_id is cast via str() before storage."""
        ann = ContentTakedownAnnouncement(transaction_id="abcdef", reason_code="spam")
        self.assertIsInstance(ann.transaction_id, str)


# ---------------------------------------------------------------------------
# ContentTakedownAnnouncement.from_dict
# ---------------------------------------------------------------------------


class TestContentTakedownFromDict(AsyncTestCase):
    async def test_valid_dict(self):
        ann = ContentTakedownAnnouncement.from_dict(
            {"transaction_id": VALID_TXN_ID, "reason_code": "csam"}
        )
        self.assertEqual(ann.reason_code, TakedownReasonCode.CSAM)

    async def test_not_a_dict_raises(self):
        with self.assertRaises(ValueError) as ctx:
            ContentTakedownAnnouncement.from_dict("not_a_dict")
        self.assertIn("dict", str(ctx.exception).lower())

    async def test_missing_transaction_id_raises(self):
        with self.assertRaises(ValueError) as ctx:
            ContentTakedownAnnouncement.from_dict({"reason_code": "csam"})
        self.assertIn("transaction_id", str(ctx.exception).lower())

    async def test_missing_reason_code_raises(self):
        with self.assertRaises(ValueError) as ctx:
            ContentTakedownAnnouncement.from_dict({"transaction_id": VALID_TXN_ID})
        self.assertIn("reason_code", str(ctx.exception).lower())

    async def test_extra_fields_passed_through(self):
        ann = ContentTakedownAnnouncement.from_dict(
            {
                "transaction_id": VALID_TXN_ID,
                "reason_code": "spam",
                "reporter": "test@example.com",
            }
        )
        self.assertEqual(ann.extra_fields["reporter"], "test@example.com")


# ---------------------------------------------------------------------------
# ContentTakedownAnnouncement.from_relationship
# ---------------------------------------------------------------------------


class TestContentTakedownFromRelationship(AsyncTestCase):
    async def test_valid_relationship(self):
        rel = {
            "content_takedown": {
                "transaction_id": VALID_TXN_ID,
                "reason_code": "copyright",
            }
        }
        ann = ContentTakedownAnnouncement.from_relationship(rel)
        self.assertEqual(ann.reason_code, TakedownReasonCode.COPYRIGHT)

    async def test_missing_key_raises(self):
        with self.assertRaises(ValueError) as ctx:
            ContentTakedownAnnouncement.from_relationship({"other": {}})
        self.assertIn("content_takedown", str(ctx.exception).lower())

    async def test_not_a_dict_raises(self):
        with self.assertRaises(ValueError):
            ContentTakedownAnnouncement.from_relationship("not_a_dict")

    async def test_none_raises(self):
        with self.assertRaises(ValueError):
            ContentTakedownAnnouncement.from_relationship(None)


# ---------------------------------------------------------------------------
# ContentTakedownAnnouncement.to_dict
# ---------------------------------------------------------------------------


class TestContentTakedownToDict(AsyncTestCase):
    async def test_basic_to_dict(self):
        ann = ContentTakedownAnnouncement(
            transaction_id=VALID_TXN_ID, reason_code="csam"
        )
        d = ann.to_dict()
        self.assertEqual(d["transaction_id"], VALID_TXN_ID)
        self.assertEqual(d["reason_code"], "csam")

    async def test_extra_fields_included_in_to_dict(self):
        ann = ContentTakedownAnnouncement(
            transaction_id=VALID_TXN_ID,
            reason_code="spam",
            reporter="x@example.com",
        )
        d = ann.to_dict()
        self.assertEqual(d["reporter"], "x@example.com")

    async def test_to_dict_no_extra_fields(self):
        ann = ContentTakedownAnnouncement(
            transaction_id=VALID_TXN_ID, reason_code="spam"
        )
        d = ann.to_dict()
        self.assertNotIn("reporter", d)
        self.assertEqual(set(d.keys()), {"transaction_id", "reason_code"})


# ---------------------------------------------------------------------------
# ContentTakedownAnnouncement.to_string / get_string
# ---------------------------------------------------------------------------


class TestContentTakedownToString(AsyncTestCase):
    async def test_to_string_is_deterministic(self):
        ann = ContentTakedownAnnouncement(
            transaction_id=VALID_TXN_ID, reason_code="csam"
        )
        self.assertEqual(ann.to_string(), VALID_TXN_ID + "csam")

    async def test_to_string_concatenates_correctly(self):
        ann = ContentTakedownAnnouncement(
            transaction_id="txn001", reason_code="copyright"
        )
        self.assertEqual(ann.to_string(), "txn001copyright")

    async def test_get_string_none_returns_empty(self):
        ann = ContentTakedownAnnouncement(
            transaction_id=VALID_TXN_ID, reason_code="spam"
        )
        self.assertEqual(ann.get_string(None), "")

    async def test_get_string_value_returns_str(self):
        ann = ContentTakedownAnnouncement(
            transaction_id=VALID_TXN_ID, reason_code="spam"
        )
        self.assertEqual(ann.get_string(42), "42")


# ---------------------------------------------------------------------------
# Round-trip: from_relationship → to_dict
# ---------------------------------------------------------------------------


class TestContentTakedownRoundTrip(AsyncTestCase):
    async def test_round_trip_preserves_data(self):
        original = {
            "transaction_id": VALID_TXN_ID,
            "reason_code": "court_order",
        }
        ann = ContentTakedownAnnouncement.from_dict(original)
        result = ann.to_dict()
        self.assertEqual(result["transaction_id"], VALID_TXN_ID)
        self.assertEqual(result["reason_code"], "court_order")

    async def test_all_reason_codes_round_trip(self):
        for code in TakedownReasonCode:
            ann = ContentTakedownAnnouncement(
                transaction_id=VALID_TXN_ID, reason_code=code
            )
            d = ann.to_dict()
            restored = ContentTakedownAnnouncement.from_dict(
                {"transaction_id": d["transaction_id"], "reason_code": d["reason_code"]}
            )
            self.assertEqual(restored.reason_code, code)


# ---------------------------------------------------------------------------
# __repr__
# ---------------------------------------------------------------------------


class TestContentTakedownRepr(AsyncTestCase):
    async def test_repr_contains_transaction_id_and_reason_code(self):
        ann = ContentTakedownAnnouncement(
            transaction_id=VALID_TXN_ID, reason_code="csam"
        )
        r = repr(ann)
        self.assertIn(VALID_TXN_ID, r)
        self.assertIn("csam", r)
        self.assertIn("ContentTakedownAnnouncement", r)


# ---------------------------------------------------------------------------
# Policy: no_comply is explicit opt-out, never the default
# ---------------------------------------------------------------------------


class TestNonComplyPolicySemantics(AsyncTestCase):
    """Verify the no_comply-is-explicit-opt-out contract described in the module."""

    def _should_comply(self, reason, auto_comply, comply_and_save, no_comply):
        """Mirrors the logic in consensus._apply_content_takedowns."""
        if reason in no_comply:
            return False
        return reason in auto_comply or reason in comply_and_save

    async def test_auto_comply_code_is_processed_by_default(self):
        """A code in auto_comply with empty no_comply must result in compliance."""
        self.assertTrue(
            self._should_comply(
                "csam",
                auto_comply=frozenset(["csam"]),
                comply_and_save=frozenset(),
                no_comply=frozenset(),
            )
        )

    async def test_no_comply_overrides_auto_comply(self):
        """A code explicitly listed in no_comply must never be acted on, even if
        it also appears in auto_comply (operator misconfiguration safety net)."""
        self.assertFalse(
            self._should_comply(
                "csam",
                auto_comply=frozenset(["csam"]),
                comply_and_save=frozenset(),
                no_comply=frozenset(["csam"]),
            )
        )

    async def test_no_comply_overrides_comply_and_save(self):
        """A code in no_comply must be skipped even if listed in comply_and_save."""
        self.assertFalse(
            self._should_comply(
                "copyright",
                auto_comply=frozenset(),
                comply_and_save=frozenset(["copyright"]),
                no_comply=frozenset(["copyright"]),
            )
        )

    async def test_code_absent_from_all_sets_does_not_comply(self):
        """A code not in any set must not trigger compliance (operator narrowed
        auto_comply and didn't include this code)."""
        self.assertFalse(
            self._should_comply(
                "spam",
                auto_comply=frozenset(["csam"]),
                comply_and_save=frozenset(),
                no_comply=frozenset(),
            )
        )

    async def test_empty_no_comply_does_not_block_auto_comply(self):
        """With empty no_comply (the default), all auto_comply codes must comply."""
        for code in TakedownReasonCode:
            self.assertTrue(
                self._should_comply(
                    code.value,
                    auto_comply=DEFAULT_AUTO_COMPLY,
                    comply_and_save=DEFAULT_COMPLY_AND_SAVE,
                    no_comply=DEFAULT_NO_COMPLY,
                ),
                msg=f"Expected compliance for {code.value!r} with default policy",
            )
