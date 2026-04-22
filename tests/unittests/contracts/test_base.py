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

from yadacoin.contracts.base import Contract, ContractTypes, PayoutOperators, PayoutType


class TestPayoutOperators(unittest.TestCase):
    def test_is_enum(self):
        self.assertTrue(issubclass(PayoutOperators, Enum))

    def test_percent_value(self):
        self.assertEqual(PayoutOperators.PERCENT.value, "percent")

    def test_fixed_value(self):
        self.assertEqual(PayoutOperators.FIXED.value, "fixed")

    def test_member_count(self):
        self.assertEqual(len(PayoutOperators), 2)

    def test_lookup_by_value(self):
        self.assertEqual(PayoutOperators("percent"), PayoutOperators.PERCENT)
        self.assertEqual(PayoutOperators("fixed"), PayoutOperators.FIXED)

    def test_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            PayoutOperators("invalid")


class TestPayoutType(unittest.TestCase):
    def test_is_enum(self):
        self.assertTrue(issubclass(PayoutType, Enum))

    def test_recurring_value(self):
        self.assertEqual(PayoutType.RECURRING.value, "recurring")

    def test_one_time_value(self):
        self.assertEqual(PayoutType.ONE_TIME.value, "one_time")

    def test_member_count(self):
        self.assertEqual(len(PayoutType), 2)

    def test_lookup_by_value(self):
        self.assertEqual(PayoutType("recurring"), PayoutType.RECURRING)
        self.assertEqual(PayoutType("one_time"), PayoutType.ONE_TIME)

    def test_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            PayoutType("daily")


class TestContractTypes(unittest.TestCase):
    def test_is_enum(self):
        self.assertTrue(issubclass(ContractTypes, Enum))

    def test_change_ownership_value(self):
        self.assertEqual(ContractTypes.CHANGE_OWNERSHIP.value, "change_ownership")

    def test_new_relationship_value(self):
        self.assertEqual(ContractTypes.NEW_RELATIONSHIP.value, "new_relationship")

    def test_member_count(self):
        self.assertEqual(len(ContractTypes), 2)

    def test_lookup_by_value(self):
        self.assertEqual(
            ContractTypes("change_ownership"), ContractTypes.CHANGE_OWNERSHIP
        )
        self.assertEqual(
            ContractTypes("new_relationship"), ContractTypes.NEW_RELATIONSHIP
        )

    def test_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            ContractTypes("unknown")


class TestContractInit(unittest.TestCase):
    def _make_identity_dict(self):
        from yadacoin.core.identity import Identity

        identity = Identity.generate(username="test_contract_user")
        return {
            "public_key": identity.public_key,
            "username": identity.username,
            "username_signature": identity.username_signature,
            "collection": "",
            "parent": "",
            "wif": identity.wif,
        }

    @patch("yadacoin.contracts.base.Config")
    def test_valid_init_with_string_creator(self, mock_config):
        mock_config.return_value = MagicMock()
        identity_dict = self._make_identity_dict()
        contract = Contract(
            version=1,
            expiry=9999999,
            contract_type=ContractTypes.NEW_RELATIONSHIP.value,
            identity=identity_dict,
            creator="creator_public_key",
        )
        self.assertEqual(contract.version, 1)
        self.assertEqual(contract.expiry, 9999999)
        self.assertEqual(contract.contract_type, ContractTypes.NEW_RELATIONSHIP.value)
        self.assertEqual(contract.creator, "creator_public_key")

    @patch("yadacoin.contracts.base.Config")
    def test_valid_init_with_dict_creator(self, mock_config):
        mock_config.return_value = MagicMock()
        identity_dict = self._make_identity_dict()
        from yadacoin.core.identity import Identity

        creator = Identity.generate(username="creator")
        creator_dict = {
            "public_key": creator.public_key,
            "username": creator.username,
            "username_signature": creator.username_signature,
            "collection": "",
            "parent": "",
        }
        contract = Contract(
            version=1,
            expiry=9999999,
            contract_type=ContractTypes.CHANGE_OWNERSHIP.value,
            identity=identity_dict,
            creator=creator_dict,
        )
        self.assertEqual(contract.version, 1)

    @patch("yadacoin.contracts.base.Config")
    def test_invalid_version_raises(self, mock_config):
        mock_config.return_value = MagicMock()
        identity_dict = self._make_identity_dict()
        with self.assertRaises(Exception) as ctx:
            Contract(
                version="1",  # not an int
                expiry=9999999,
                contract_type=ContractTypes.NEW_RELATIONSHIP.value,
                identity=identity_dict,
                creator="creator_key",
            )
        self.assertIn("version", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_invalid_expiry_raises(self, mock_config):
        mock_config.return_value = MagicMock()
        identity_dict = self._make_identity_dict()
        with self.assertRaises(Exception) as ctx:
            Contract(
                version=1,
                expiry="9999999",  # not an int
                contract_type=ContractTypes.NEW_RELATIONSHIP.value,
                identity=identity_dict,
                creator="creator_key",
            )
        self.assertIn("expiry", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_invalid_contract_type_raises(self, mock_config):
        mock_config.return_value = MagicMock()
        identity_dict = self._make_identity_dict()
        with self.assertRaises(Exception) as ctx:
            Contract(
                version=1,
                expiry=9999999,
                contract_type="unknown_type",
                identity=identity_dict,
                creator="creator_key",
            )
        self.assertIn("contract_type", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_none_creator_raises(self, mock_config):
        mock_config.return_value = MagicMock()
        identity_dict = self._make_identity_dict()
        with self.assertRaises(Exception) as ctx:
            Contract(
                version=1,
                expiry=9999999,
                contract_type=ContractTypes.NEW_RELATIONSHIP.value,
                identity=identity_dict,
                creator=None,
            )
        self.assertIn("creator", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_get_string_with_value(self, mock_config):
        mock_config.return_value = MagicMock()
        identity_dict = self._make_identity_dict()
        contract = Contract(
            version=1,
            expiry=9999999,
            contract_type=ContractTypes.NEW_RELATIONSHIP.value,
            identity=identity_dict,
            creator="creator_key",
        )
        self.assertEqual(contract.get_string("hello"), "hello")
        self.assertEqual(contract.get_string(42), "42")

    @patch("yadacoin.contracts.base.Config")
    def test_get_string_with_none(self, mock_config):
        mock_config.return_value = MagicMock()
        identity_dict = self._make_identity_dict()
        contract = Contract(
            version=1,
            expiry=9999999,
            contract_type=ContractTypes.NEW_RELATIONSHIP.value,
            identity=identity_dict,
            creator="creator_key",
        )
        self.assertEqual(contract.get_string(None), "")

    @patch("yadacoin.contracts.base.Config")
    def test_report_init_error_raises(self, mock_config):
        mock_config.return_value = MagicMock()
        identity_dict = self._make_identity_dict()
        contract = Contract(
            version=1,
            expiry=9999999,
            contract_type=ContractTypes.NEW_RELATIONSHIP.value,
            identity=identity_dict,
            creator="creator_key",
        )
        with self.assertRaises(Exception) as ctx:
            contract.report_init_error("test_field")
        self.assertIn("test_field", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
