"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest
from enum import Enum
from unittest.mock import MagicMock, patch

from yadacoin.contracts.affiliate import (
    AffiliateContract,
    AffiliatePoofTypes,
    ReferPayout,
)
from yadacoin.contracts.base import ContractTypes, PayoutOperators, PayoutType


def _make_identity_dict():
    from yadacoin.core.identity import Identity

    identity = Identity.generate(username="affiliate_test_user")
    return {
        "public_key": identity.public_key,
        "username": identity.username,
        "username_signature": identity.username_signature,
        "collection": "",
        "parent": "",
        "wif": identity.wif,
    }


def _make_refer_payout(active=False):
    return ReferPayout(
        active=active,
        operator=PayoutOperators.PERCENT.value if active else "",
        payout_type=PayoutType.ONE_TIME.value if active else "",
        interval=1 if active else "",
        amount=0.1 if active else "",
    )


class TestAffiliateProofTypes(unittest.TestCase):
    def test_is_enum(self):
        self.assertTrue(issubclass(AffiliatePoofTypes, Enum))

    def test_confirmation_value(self):
        self.assertEqual(AffiliatePoofTypes.CONFIRMATION.value, "confirmation")

    def test_honor_value(self):
        self.assertEqual(AffiliatePoofTypes.HONOR.value, "honor")

    def test_member_count(self):
        self.assertEqual(len(AffiliatePoofTypes), 2)


class TestReferPayout(unittest.TestCase):
    def test_inactive_payout_no_validation(self):
        rp = ReferPayout(active=False)
        self.assertFalse(rp.active)

    def test_inactive_payout_defaults(self):
        rp = ReferPayout()
        self.assertFalse(rp.active)
        self.assertEqual(rp.operator, "")
        self.assertEqual(rp.payout_type, "")
        self.assertEqual(rp.interval, "")
        self.assertEqual(rp.amount, "")

    def test_active_payout_valid(self):
        rp = ReferPayout(
            active=True,
            operator=PayoutOperators.PERCENT.value,
            payout_type=PayoutType.ONE_TIME.value,
            interval=0,
            amount=0.1,
        )
        self.assertTrue(rp.active)
        self.assertEqual(rp.operator, "percent")
        self.assertEqual(rp.payout_type, "one_time")
        self.assertAlmostEqual(rp.amount, 0.1)

    def test_active_payout_invalid_operator_raises(self):
        with self.assertRaises(Exception) as ctx:
            ReferPayout(
                active=True,
                operator="bad_op",
                payout_type=PayoutType.ONE_TIME.value,
                interval=0,
                amount=0.1,
            )
        self.assertIn("operator", str(ctx.exception))

    def test_active_payout_invalid_payout_type_raises(self):
        with self.assertRaises(Exception) as ctx:
            ReferPayout(
                active=True,
                operator=PayoutOperators.FIXED.value,
                payout_type="bad_type",
                interval=0,
                amount=0.1,
            )
        self.assertIn("payout_type", str(ctx.exception))

    def test_active_recurring_invalid_interval_raises(self):
        with self.assertRaises(Exception) as ctx:
            ReferPayout(
                active=True,
                operator=PayoutOperators.FIXED.value,
                payout_type=PayoutType.RECURRING.value,
                interval="not_numeric",
                amount=0.1,
            )
        self.assertIn("interval", str(ctx.exception))

    def test_active_invalid_amount_raises(self):
        with self.assertRaises(Exception) as ctx:
            ReferPayout(
                active=True,
                operator=PayoutOperators.FIXED.value,
                payout_type=PayoutType.ONE_TIME.value,
                interval=0,
                amount="not_numeric",
            )
        self.assertIn("amount", str(ctx.exception))

    def test_active_recurring_valid_interval(self):
        rp = ReferPayout(
            active=True,
            operator=PayoutOperators.FIXED.value,
            payout_type=PayoutType.RECURRING.value,
            interval=10,
            amount=5.0,
        )
        self.assertTrue(rp.active)
        self.assertEqual(rp.interval, 10)

    def test_to_dict_inactive(self):
        rp = ReferPayout(active=False)
        d = rp.to_dict()
        self.assertIsInstance(d, dict)
        self.assertFalse(d["active"])
        self.assertIn("operator", d)
        self.assertIn("payout_type", d)
        self.assertIn("interval", d)
        self.assertIn("amount", d)

    def test_to_dict_active(self):
        rp = ReferPayout(
            active=True,
            operator=PayoutOperators.PERCENT.value,
            payout_type=PayoutType.ONE_TIME.value,
            interval=0,
            amount=0.05,
        )
        d = rp.to_dict()
        self.assertTrue(d["active"])
        self.assertEqual(d["operator"], "percent")
        self.assertEqual(d["payout_type"], "one_time")
        self.assertAlmostEqual(d["amount"], 0.05)

    def test_to_string_inactive(self):
        rp = ReferPayout(active=False)
        s = rp.to_string()
        self.assertEqual(s, "false")

    def test_to_string_active(self):
        rp = ReferPayout(
            active=True,
            operator=PayoutOperators.FIXED.value,
            payout_type=PayoutType.ONE_TIME.value,
            interval=0,
            amount=2.0,
        )
        s = rp.to_string()
        self.assertTrue(s.startswith("true"))
        self.assertIn("fixed", s)
        self.assertIn("one_time", s)

    def test_get_string_none(self):
        rp = ReferPayout()
        self.assertEqual(rp.get_string(None), "")

    def test_get_string_value(self):
        rp = ReferPayout()
        self.assertEqual(rp.get_string("abc"), "abc")
        self.assertEqual(rp.get_string(123), "123")

    def test_report_init_error_raises(self):
        rp = ReferPayout()
        with self.assertRaises(Exception) as ctx:
            rp.report_init_error("my_field")
        self.assertIn("my_field", str(ctx.exception))


class TestAffiliateContract(unittest.TestCase):
    def _make_contract(self, mock_config, **overrides):
        mock_config.return_value = MagicMock()
        identity_dict = _make_identity_dict()
        referrer = _make_refer_payout(active=False)
        referee = _make_refer_payout(active=False)
        defaults = dict(
            version=1,
            expiry=9999999,
            contract_type=ContractTypes.NEW_RELATIONSHIP.value,
            proof_type=AffiliatePoofTypes.HONOR.value,
            target="",
            market="market1",
            identity=identity_dict,
            creator="creator_key",
            referrer=referrer,
            referee=referee,
        )
        defaults.update(overrides)
        return AffiliateContract(**defaults)

    @patch("yadacoin.contracts.base.Config")
    def test_valid_affiliate_contract(self, mock_config):
        contract = self._make_contract(mock_config)
        self.assertEqual(contract.version, 1)
        self.assertEqual(contract.contract_type, ContractTypes.NEW_RELATIONSHIP.value)
        self.assertEqual(contract.proof_type, AffiliatePoofTypes.HONOR.value)

    @patch("yadacoin.contracts.base.Config")
    def test_affiliate_contract_stores_referrer(self, mock_config):
        contract = self._make_contract(mock_config)
        self.assertIsInstance(contract.referrer, ReferPayout)
        self.assertIsInstance(contract.referee, ReferPayout)

    @patch("yadacoin.contracts.base.Config")
    def test_affiliate_contract_with_dict_referrer(self, mock_config):
        mock_config.return_value = MagicMock()
        identity_dict = _make_identity_dict()
        referrer_dict = {
            "active": False,
            "operator": "",
            "payout_type": "",
            "interval": "",
            "amount": "",
        }
        referee_dict = {
            "active": False,
            "operator": "",
            "payout_type": "",
            "interval": "",
            "amount": "",
        }
        contract = AffiliateContract(
            version=1,
            expiry=9999999,
            contract_type=ContractTypes.NEW_RELATIONSHIP.value,
            proof_type=AffiliatePoofTypes.CONFIRMATION.value,
            target="target",
            market="market",
            identity=identity_dict,
            creator="creator_key",
            referrer=referrer_dict,
            referee=referee_dict,
        )
        self.assertIsInstance(contract.referrer, ReferPayout)
        self.assertIsInstance(contract.referee, ReferPayout)

    @patch("yadacoin.contracts.base.Config")
    def test_to_string_returns_string(self, mock_config):
        contract = self._make_contract(mock_config)
        s = contract.to_string()
        self.assertIsInstance(s, str)
        self.assertIn("1", s)  # version

    @patch("yadacoin.contracts.base.Config")
    def test_to_dict_structure(self, mock_config):
        contract = self._make_contract(mock_config)
        d = contract.to_dict()
        self.assertIsInstance(d, dict)
        from yadacoin.core.collections import Collections

        self.assertIn(Collections.SMART_CONTRACT.value, d)
        inner = d[Collections.SMART_CONTRACT.value]
        self.assertIn("version", inner)
        self.assertIn("expiry", inner)
        self.assertIn("contract_type", inner)
        self.assertIn("proof_type", inner)
        self.assertIn("target", inner)
        self.assertIn("market", inner)
        self.assertIn("identity", inner)
        self.assertIn("referrer", inner)
        self.assertIn("referee", inner)
        self.assertIn("creator", inner)

    @patch("yadacoin.contracts.base.Config")
    def test_affiliate_contract_target_and_market(self, mock_config):
        contract = self._make_contract(
            mock_config, target="my_target", market="my_market"
        )
        self.assertEqual(contract.target, "my_target")
        self.assertEqual(contract.market, "my_market")


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
