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

from yadacoin.contracts.wrappedtoken import AssetProofTypes


def _make_identity_dict():
    from yadacoin.core.identity import Identity

    identity = Identity.generate(username="wrapped_token_test_user")
    return {
        "public_key": identity.public_key,
        "username": identity.username,
        "username_signature": identity.username_signature,
        "collection": "",
        "parent": "",
        "wif": identity.wif,
    }


class TestAssetProofTypes(unittest.TestCase):
    def test_is_enum(self):
        self.assertTrue(issubclass(AssetProofTypes, Enum))

    def test_token_value(self):
        self.assertEqual(AssetProofTypes.TOKEN.value, "token")

    def test_member_count(self):
        self.assertEqual(len(AssetProofTypes), 1)

    def test_lookup_by_value(self):
        self.assertEqual(AssetProofTypes("token"), AssetProofTypes.TOKEN)

    def test_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            AssetProofTypes("invalid")


class TestTraderPayout(unittest.TestCase):
    pass


#     def test_inactive_payout_defaults(self):
#         tp = TraderPayout()
#         self.assertFalse(tp.active)
#         self.assertEqual(tp.operator, "")
#         self.assertEqual(tp.payout_type, "")
#         self.assertEqual(tp.interval, "")
#         self.assertEqual(tp.amount, "")

#     def test_active_payout_valid(self):
#         tp = TraderPayout(
#             active=True,
#             operator=PayoutOperators.FIXED.value,
#             payout_type=PayoutType.ONE_TIME.value,
#             interval=0,
#             amount=10.0,
#         )
#         self.assertTrue(tp.active)
#         self.assertEqual(tp.operator, "fixed")

#     def test_active_invalid_operator_raises(self):
#         with self.assertRaises(Exception) as ctx:
#             TraderPayout(
#                 active=True,
#                 operator="bad",
#                 payout_type=PayoutType.ONE_TIME.value,
#                 interval=0,
#                 amount=1.0,
#             )
#         self.assertIn("operator", str(ctx.exception))

#     def test_active_invalid_payout_type_raises(self):
#         with self.assertRaises(Exception) as ctx:
#             TraderPayout(
#                 active=True,
#                 operator=PayoutOperators.FIXED.value,
#                 payout_type="bad_type",
#                 interval=0,
#                 amount=1.0,
#             )
#         self.assertIn("payout_type", str(ctx.exception))

#     def test_active_recurring_invalid_interval_raises(self):
#         with self.assertRaises(Exception) as ctx:
#             TraderPayout(
#                 active=True,
#                 operator=PayoutOperators.FIXED.value,
#                 payout_type=PayoutType.RECURRING.value,
#                 interval="not_numeric",
#                 amount=1.0,
#             )
#         self.assertIn("interval", str(ctx.exception))

#     def test_active_invalid_amount_raises(self):
#         with self.assertRaises(Exception) as ctx:
#             TraderPayout(
#                 active=True,
#                 operator=PayoutOperators.FIXED.value,
#                 payout_type=PayoutType.ONE_TIME.value,
#                 interval=0,
#                 amount="not_a_number",
#             )
#         self.assertIn("amount", str(ctx.exception))

#     def test_to_dict(self):
#         tp = TraderPayout(
#             active=True,
#             operator=PayoutOperators.PERCENT.value,
#             payout_type=PayoutType.ONE_TIME.value,
#             interval=0,
#             amount=0.05,
#         )
#         d = tp.to_dict()
#         self.assertIsInstance(d, dict)
#         self.assertTrue(d["active"])
#         self.assertEqual(d["operator"], "percent")
#         self.assertAlmostEqual(d["amount"], 0.05)

#     def test_to_string_inactive(self):
#         tp = TraderPayout(active=False)
#         self.assertEqual(tp.to_string(), "false")

#     def test_to_string_active(self):
#         tp = TraderPayout(
#             active=True,
#             operator=PayoutOperators.FIXED.value,
#             payout_type=PayoutType.ONE_TIME.value,
#             interval=0,
#             amount=5.0,
#         )
#         s = tp.to_string()
#         self.assertTrue(s.startswith("true"))
#         self.assertIn("fixed", s)

#     def test_get_string_none(self):
#         tp = TraderPayout()
#         self.assertEqual(tp.get_string(None), "")

#     def test_get_string_value(self):
#         tp = TraderPayout()
#         self.assertEqual(tp.get_string("hello"), "hello")

#     def test_report_init_error_raises(self):
#         tp = TraderPayout()
#         with self.assertRaises(Exception) as ctx:
#             tp.report_init_error("my_field")
#         self.assertIn("my_field", str(ctx.exception))


# class TestWrappedTokenContract(unittest.TestCase):
#     @patch("yadacoin.contracts.base.Config")
#     def test_valid_init(self, mock_config):
#         mock_config.return_value = MagicMock()
#         identity_dict = _make_identity_dict()
#         contract = WrappedTokenContract(
#             version=1,
#             expiry=9999999,
#             contract_type=ContractTypes.CHANGE_OWNERSHIP.value,
#             identity=identity_dict,
#             creator="creator_key",
#             proof_type=AssetProofTypes.TOKEN.value,
#             off_chain_dest_address="0xAbcDef1234567890",
#         )
#         self.assertEqual(contract.version, 1)
#         self.assertEqual(contract.proof_type, AssetProofTypes.TOKEN.value)
#         self.assertEqual(contract.off_chain_dest_address, "0xAbcDef1234567890")

#     @patch("yadacoin.contracts.base.Config")
#     def test_invalid_proof_type_raises(self, mock_config):
#         mock_config.return_value = MagicMock()
#         identity_dict = _make_identity_dict()
#         with self.assertRaises(Exception) as ctx:
#             WrappedTokenContract(
#                 version=1,
#                 expiry=9999999,
#                 contract_type=ContractTypes.CHANGE_OWNERSHIP.value,
#                 identity=identity_dict,
#                 creator="creator_key",
#                 proof_type="invalid_proof",
#                 off_chain_dest_address="0xAbcDef1234567890",
#             )
#         self.assertIn("proof_type", str(ctx.exception))

#     @patch("yadacoin.contracts.base.Config")
#     def test_invalid_off_chain_dest_raises(self, mock_config):
#         mock_config.return_value = MagicMock()
#         identity_dict = _make_identity_dict()
#         with self.assertRaises(Exception) as ctx:
#             WrappedTokenContract(
#                 version=1,
#                 expiry=9999999,
#                 contract_type=ContractTypes.CHANGE_OWNERSHIP.value,
#                 identity=identity_dict,
#                 creator="creator_key",
#                 proof_type=AssetProofTypes.TOKEN.value,
#                 off_chain_dest_address=12345,  # not a string
#             )
#         self.assertIn("off_chain_dest_address", str(ctx.exception))

#     @patch("yadacoin.contracts.base.Config")
#     def test_to_string_returns_string(self, mock_config):
#         mock_config.return_value = MagicMock()
#         identity_dict = _make_identity_dict()
#         contract = WrappedTokenContract(
#             version=1,
#             expiry=9999999,
#             contract_type=ContractTypes.CHANGE_OWNERSHIP.value,
#             identity=identity_dict,
#             creator="creator_key",
#             proof_type=AssetProofTypes.TOKEN.value,
#             off_chain_dest_address="0xAddress",
#         )
#         s = contract.to_string()
#         self.assertIsInstance(s, str)
#         self.assertIn("token", s)
#         self.assertIn("0xAddress", s)

#     @patch("yadacoin.contracts.base.Config")
#     def test_to_dict_structure(self, mock_config):
#         mock_config.return_value = MagicMock()
#         identity_dict = _make_identity_dict()
#         contract = WrappedTokenContract(
#             version=1,
#             expiry=9999999,
#             contract_type=ContractTypes.CHANGE_OWNERSHIP.value,
#             identity=identity_dict,
#             creator="creator_key",
#             proof_type=AssetProofTypes.TOKEN.value,
#             off_chain_dest_address="0xAddress",
#         )
#         d = contract.to_dict()
#         from yadacoin.core.collections import Collections

#         self.assertIn(Collections.SMART_CONTRACT.value, d)
#         inner = d[Collections.SMART_CONTRACT.value]
#         self.assertIn("version", inner)
#         self.assertIn("proof_type", inner)
#         self.assertIn("off_chain_dest_address", inner)
#         self.assertEqual(inner["off_chain_dest_address"], "0xAddress")

#     @patch("yadacoin.contracts.base.Config")
#     def test_expire_token_returns_none(self, mock_config):
#         import asyncio

#         mock_config.return_value = MagicMock()
#         identity_dict = _make_identity_dict()
#         contract = WrappedTokenContract(
#             version=1,
#             expiry=9999999,
#             contract_type=ContractTypes.CHANGE_OWNERSHIP.value,
#             identity=identity_dict,
#             creator="creator_key",
#             proof_type=AssetProofTypes.TOKEN.value,
#             off_chain_dest_address="0xAddress",
#         )
#         result = asyncio.get_event_loop().run_until_complete(
#             contract.expire_token(MagicMock())
#         )
#         self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
