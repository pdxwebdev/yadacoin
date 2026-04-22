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

from yadacoin.contracts.base import ContractTypes, PayoutOperators, PayoutType
from yadacoin.contracts.changeownership import AssetProofTypes, ChangeOwnershipContract


def _make_identity_dict():
    from yadacoin.core.identity import Identity

    identity = Identity.generate(username="co_test_user")
    return {
        "public_key": identity.public_key,
        "username": identity.username,
        "username_signature": identity.username_signature,
        "collection": "",
        "parent": "",
        "wif": identity.wif,
    }


def _make_asset_dict():
    """Create a minimal valid asset dict."""
    from yadacoin.core.identity import Identity

    identity = Identity.generate(username="asset_user")
    return {
        "identity": {
            "public_key": identity.public_key,
            "username": identity.username,
            "username_signature": identity.username_signature,
            "collection": "",
            "parent": "",
        },
        "data": "some asset data",
        "checksum": "checksum123",
    }


class TestChangeOwnershipAssetProofTypes(unittest.TestCase):
    def test_is_enum(self):
        self.assertTrue(issubclass(AssetProofTypes, Enum))

    def test_coinbase_value(self):
        self.assertEqual(AssetProofTypes.COINBASE.value, "coinbase")

    def test_confirmation_value(self):
        self.assertEqual(AssetProofTypes.CONFIRMATION.value, "confirmation")

    def test_first_come_value(self):
        self.assertEqual(AssetProofTypes.FIRST_COME.value, "first_come")

    def test_auction_value(self):
        self.assertEqual(AssetProofTypes.AUCTION.value, "auction")

    def test_member_count(self):
        self.assertEqual(len(AssetProofTypes), 4)

    def test_lookup_by_value(self):
        self.assertEqual(AssetProofTypes("coinbase"), AssetProofTypes.COINBASE)
        self.assertEqual(AssetProofTypes("confirmation"), AssetProofTypes.CONFIRMATION)
        self.assertEqual(AssetProofTypes("first_come"), AssetProofTypes.FIRST_COME)
        self.assertEqual(AssetProofTypes("auction"), AssetProofTypes.AUCTION)


class TestChangeOwnershipContract(unittest.TestCase):
    def _make_contract(self, mock_config, **overrides):
        mock_config.return_value = MagicMock()
        identity_dict = _make_identity_dict()
        defaults = dict(
            version=1,
            expiry=9999999,
            contract_type=ContractTypes.CHANGE_OWNERSHIP.value,
            payout_amount=1.0,
            payout_operator=PayoutOperators.FIXED.value,
            payout_type=PayoutType.ONE_TIME.value,
            market="test_market",
            proof_type=AssetProofTypes.CONFIRMATION.value,
            identity=identity_dict,
            creator="creator_key",
            price=1.0,
            asset="asset_string",  # use string to avoid Asset.from_dict
        )
        defaults.update(overrides)
        return ChangeOwnershipContract(**defaults)

    @patch("yadacoin.contracts.base.Config")
    def test_valid_init(self, mock_config):
        contract = self._make_contract(mock_config)
        self.assertEqual(contract.version, 1)
        self.assertEqual(contract.payout_amount, 1.0)
        self.assertEqual(contract.payout_operator, PayoutOperators.FIXED.value)
        self.assertEqual(contract.payout_type, PayoutType.ONE_TIME.value)
        self.assertEqual(contract.market, "test_market")
        self.assertEqual(contract.price, 1.0)
        self.assertEqual(contract.proof_type, AssetProofTypes.CONFIRMATION.value)

    @patch("yadacoin.contracts.base.Config")
    def test_invalid_payout_amount_raises(self, mock_config):
        with self.assertRaises(Exception) as ctx:
            self._make_contract(mock_config, payout_amount="not_numeric")
        self.assertIn("payout_amount", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_invalid_payout_operator_raises(self, mock_config):
        with self.assertRaises(Exception) as ctx:
            self._make_contract(mock_config, payout_operator="bad_op")
        self.assertIn("payout_operator", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_invalid_payout_type_raises(self, mock_config):
        with self.assertRaises(Exception) as ctx:
            self._make_contract(mock_config, payout_type="bad_type")
        self.assertIn("payout_type", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_empty_market_raises(self, mock_config):
        with self.assertRaises(Exception) as ctx:
            self._make_contract(mock_config, market="")
        self.assertIn("market", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_none_market_raises(self, mock_config):
        with self.assertRaises(Exception) as ctx:
            self._make_contract(mock_config, market=None)
        self.assertIn("market", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_invalid_price_raises(self, mock_config):
        with self.assertRaises(Exception) as ctx:
            self._make_contract(mock_config, price="not_a_number")
        self.assertIn("price", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_invalid_proof_type_raises(self, mock_config):
        with self.assertRaises(Exception) as ctx:
            self._make_contract(mock_config, proof_type="invalid_proof")
        self.assertIn("proof_type", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_none_asset_raises(self, mock_config):
        with self.assertRaises(Exception) as ctx:
            self._make_contract(mock_config, asset=None)
        self.assertIn("asset", str(ctx.exception))

    @patch("yadacoin.contracts.base.Config")
    def test_string_asset_accepted(self, mock_config):
        contract = self._make_contract(mock_config, asset="asset_string")
        self.assertEqual(contract.asset, "asset_string")

    @patch("yadacoin.contracts.base.Config")
    def test_payout_amount_as_int(self, mock_config):
        contract = self._make_contract(mock_config, payout_amount=2)
        self.assertEqual(contract.payout_amount, 2)

    @patch("yadacoin.contracts.base.Config")
    def test_price_as_int(self, mock_config):
        contract = self._make_contract(mock_config, price=5)
        self.assertEqual(contract.price, 5)

    @patch("yadacoin.contracts.base.Config")
    def test_to_dict_structure(self, mock_config):
        contract = self._make_contract(mock_config)
        d = contract.to_dict()
        from yadacoin.core.collections import Collections

        self.assertIn(Collections.SMART_CONTRACT.value, d)
        inner = d[Collections.SMART_CONTRACT.value]
        self.assertIn("version", inner)
        self.assertIn("payout_amount", inner)
        self.assertIn("payout_operator", inner)
        self.assertIn("market", inner)
        self.assertIn("proof_type", inner)
        self.assertIn("price", inner)
        self.assertIn("asset", inner)

    @patch("yadacoin.contracts.base.Config")
    def test_auction_proof_type_accepted(self, mock_config):
        contract = self._make_contract(
            mock_config, proof_type=AssetProofTypes.AUCTION.value
        )
        self.assertEqual(contract.proof_type, AssetProofTypes.AUCTION.value)

    @patch("yadacoin.contracts.base.Config")
    def test_first_come_proof_type_accepted(self, mock_config):
        contract = self._make_contract(
            mock_config, proof_type=AssetProofTypes.FIRST_COME.value
        )
        self.assertEqual(contract.proof_type, AssetProofTypes.FIRST_COME.value)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
