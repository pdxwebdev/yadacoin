"""
Coverage tests for transaction.py using real block data.
"""
import unittest

from yadacoin.core.config import Config
from yadacoin.core.transaction import Transaction

from ..test_setup import AsyncTestCase

# Real block data from user
BLOCK_DATA = {
    "status": True,
    "block": {
        "version": 5,
        "time": 1784048778,
        "index": 605032,
        "public_key": "02c057b19c21009d43aabc8a2101270b10798f777506a93a0d2c83d13da468f819",
        "prevHash": "feef4ed8583cee544d0a8ae0a7fff178eddfbf6a270b00643f4865e1c9010000",
        "nonce": "",
        "transactions": [
            {
                "time": 1784018254,
                "rid": "",
                "id": "MEUCIQD5pGtyuGq1vOSI4RP+URyjJvp6HNY2EI6lX0DJ49CLyAIgJX+3pxSsgJw9yAyCVhEm6ySahvx52ana/8Ew5HPEteo=",
                "relationship": {
                    "identity": {
                        "username": "local_node_B",
                        "username_signature": "MEUCIQDUlsZea29TrKNYmQ3vN9UCRtXxomINak5y9RO4RZBXZAIgR+xlxfs6BjzFm6hs3rDu6+Au7L971hf0GqTsM4lGP6o=",
                        "identity_type": "social",
                    }
                },
                "relationship_hash": "33b7e0265aa310ee608a4359d9348e4008f2253f3a1e5f88e1df533c4203ceef",
                "public_key": "03efac9022ac34cb86c658705f2f57e317915132bbb58247212674c49cde313e71",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "4efbb7e7df0e8a065c13ad18ac79c701eafd8c671754098617005dde2806730c",
                "inputs": [],
                "outputs": [{"to": "1E9dN3RjvaTvXdYw4WYnoXh5HY1JpXxwKS", "value": 0.0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "1E9dN3RjvaTvXdYw4WYnoXh5HY1JpXxwKS",
                "twice_prerotated_key_hash": "15AbtYATStt77DBQjP8Vz6vCFBxcvRi9Y7",
                "public_key_hash": "1KRZ2Lek7JtMaVp1RRMFPx7Rtk1G7Wsakj",
                "prev_public_key_hash": "",
            },
            {
                "time": 1784018260,
                "rid": "",
                "id": "MEQCIBDkgpI9MVZt1Kecn/QMunPh4zq2upROSsr8mHTKyYpuAiBNZoXbasBYi75km5q/1ULSEZZValnaRaJhocWg9kC6LQ==",
                "relationship": "block reanchor",
                "relationship_hash": "8602201e6e3cb11683a612ca0a81121ff89e8bbfcc0a1bfb4abaa478a4b6dec2",
                "public_key": "0345c729dd4391e32d00936f07d6042ef3d4fca9f5e339f6d5c947ad119f4f79f3",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "df80da7625b567db3fe39890cb69e338903375477c2a936ff43c0cfd7b0c9325",
                "inputs": [],
                "outputs": [{"to": "15AbtYATStt77DBQjP8Vz6vCFBxcvRi9Y7", "value": 0.0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "15AbtYATStt77DBQjP8Vz6vCFBxcvRi9Y7",
                "twice_prerotated_key_hash": "12F3sB9JnyXZA2ddXCFe5kjRKXgX5f6vyZ",
                "public_key_hash": "1E9dN3RjvaTvXdYw4WYnoXh5HY1JpXxwKS",
                "prev_public_key_hash": "1KRZ2Lek7JtMaVp1RRMFPx7Rtk1G7Wsakj",
            },
            {
                "time": 1784048779,
                "rid": "",
                "id": "MEUCIQCTJJhcyQBHWa82NhTR4WzWhpKiPXRhxZOpmbOv139MhgIgQ8tYmm0959ckaBSC4fTRjqEcLMqBnvnH/n3js7alQMY=",
                "relationship": "",
                "relationship_hash": "",
                "public_key": "0373003ae02f297de5c9c3c1196ae05308a1558714190f49abff0c795004bef42e",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "ee897617e98fe0a74a731eb194632e7920435b87231c977cecb91050ff6570f0",
                "inputs": [],
                "outputs": [{"to": "1FiAsfCaa2s8TVk1yAzSH19ADnh3nj9QCF", "value": 0.0}],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "1FiAsfCaa2s8TVk1yAzSH19ADnh3nj9QCF",
                "twice_prerotated_key_hash": "1CiUxTWC1XgEYsD4R69wYGkCq5XtKN5Vjb",
                "public_key_hash": "1HXzeAP58wn9TBBVqW9op65CqbPjNXixJ2",
                "prev_public_key_hash": "1MCFtraKPah7vwCjqFgJnPF5afjajo7eWz",
            },
            {
                "time": 0,
                "rid": "",
                "id": "MEQCIDjj7C3Jm5ynHshw8PG0JK4YyrLnMC3ooXQMHMdnlaGRAiAmWe1WdGPAL+5SggKdTYIpURAQxz6oJ2wSYzbzzTaLfA==",
                "relationship": "",
                "relationship_hash": "",
                "public_key": "02c057b19c21009d43aabc8a2101270b10798f777506a93a0d2c83d13da468f819",
                "dh_public_key": "",
                "fee": 0.0,
                "masternode_fee": 0.0,
                "hash": "5fa127ee6562feab4b634e50aaf614e26bed320e0e62542f3a67de1f32d42dd3",
                "inputs": [],
                "outputs": [
                    {"to": "1HXzeAP58wn9TBBVqW9op65CqbPjNXixJ2", "value": 12.5}
                ],
                "version": 7,
                "private": False,
                "never_expire": False,
                "prerotated_key_hash": "1HXzeAP58wn9TBBVqW9op65CqbPjNXixJ2",
                "twice_prerotated_key_hash": "1FiAsfCaa2s8TVk1yAzSH19ADnh3nj9QCF",
                "public_key_hash": "1MCFtraKPah7vwCjqFgJnPF5afjajo7eWz",
                "prev_public_key_hash": "183LdxhbsaGi3AS2kaAEqDXqgHEiW1dngR",
            },
        ],
    },
}


class TestTransactionFromRealBlock(AsyncTestCase):
    """Test transaction.py uncovered lines using real block data."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.config = Config()
        self.config.network = "regnet"

    async def test_from_dict_identity_relationship(self):
        """Line 217-230: identity relationship parsing."""
        txn_data = BLOCK_DATA["block"]["transactions"][0]
        txn = Transaction.from_dict(txn_data)
        self.assertIsNotNone(txn)
        # identity relationship is parsed into IdentityAnnouncement object
        self.assertTrue(hasattr(txn.relationship, "username"))

    async def test_from_dict_coinbase_transaction(self):
        """Coinbase transaction has time=0."""
        txn_data = BLOCK_DATA["block"]["transactions"][3]
        txn = Transaction.from_dict(txn_data)
        self.assertIsNotNone(txn)
        # Coinbase is detected by time == 0 in from_dict
        self.assertEqual(txn.time, 0)

    async def test_has_key_event_log_no_public_key(self):
        """Line 1360: has_key_event_log returns False when no public_key."""
        txn_data = BLOCK_DATA["block"]["transactions"][3].copy()
        txn_data["public_key"] = ""
        txn = Transaction.from_dict(txn_data)
        result = await txn.has_key_event_log()
        self.assertFalse(result)

    async def test_has_key_event_log_bad_public_key(self):
        """Lines 1365-1368: has_key_event_log catches unparseable public_key."""
        txn_data = BLOCK_DATA["block"]["transactions"][3].copy()
        txn_data["public_key"] = "NOT_VALID_HEX!!!"
        txn = Transaction.from_dict(txn_data)
        result = await txn.has_key_event_log()
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
