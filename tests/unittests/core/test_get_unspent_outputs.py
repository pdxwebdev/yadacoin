import hashlib
import logging
import time
import unittest
from unittest.mock import MagicMock

import yadacoin.core.config
from tests.unittests.test_setup import AsyncTestCase
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.config import Config
from yadacoin.core.mongo import Mongo

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

block1 = {
    "merkleRoot": "c816fe62ee6c883226cb8dad100d9338963544c5d9fe8384c5b0be9aaf0cd961",
    "time": 1537979085,
    "index": 11000,
    "version": 1,
    "target": "0000003fffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "public_key": "03672bfbbf29e31a4429e3bc18240c98f0dcfbdd4e6e12aa70657e2095b7d84425",
    "hash": "00000027175a9dde28a7b26517b026a7866ddb1cfcceaa3627558b5931a1e6c3",
    "nonce": 14636080,
    "transactions": [
        {
            "time": 1734008946,
            "rid": "",
            "id": "MEQCIFv+0r78YqWcdmgMNasrtfzAzvdSinZpQGTrNax3GYA1AiAUbdf4cWp2kDoulPd7Dm3NlJ2cZebmyplKw5QSyH6SQQ==",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "026951d27f9195d02d0706c8d7bb86aa2fff92e7f0ef5cbfe75a714104644f442e",
            "dh_public_key": "",
            "fee": 0,
            "masternode_fee": 0,
            "hash": "b612e7fa10b8de12a30611b378442ab33d34471526af24c43c60881782c91d2e",
            "inputs": [
                {
                    "id": "MEUCIQCYsY/i6EhcHOQ/RTceVkKPeuk70heeUJKJxUKr5ZfBjgIgMF/EHFIhKJX73b/YM6TrImhaayTZe7ANjKRu3ffxpaQ="
                }
            ],
            "outputs": [
                {"to": "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu", "value": 40},
                {"to": "17QaWQLspYBwsiV7MZ59jeTcXKzFXMbAjy", "value": 10},
            ],
            "version": 5,
            "prerotated_key_hash": "",
        },
        {
            "time": 1734013795,
            "rid": "",
            "id": "MEUCIQDNeRV9ZOx57cDYybt8Kz64MZfWpuxHRbyWVvvd33XZsAIgBtKGlJhFP9lKLU3ma2WuZYF0za2OKF5FD8Rs8y4uXr8=",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "03672bfbbf29e31a4429e3bc18240c98f0dcfbdd4e6e12aa70657e2095b7d84425",
            "dh_public_key": "",
            "fee": 0,
            "masternode_fee": 0,
            "hash": "8dea4a8d5cf82b4fa66057b8c54cfe4dab7a886fb8580e9995c5b5799c4798c8",
            "inputs": [],
            "outputs": [
                {"to": "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu", "value": 12.25},
                {"to": "13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK", "value": 2.3125},
                {"to": "1L7dEh8ckRF4ftP3TUztfJsi8hXL8KUahY", "value": 2.3125},
                {"to": "1DX4nGHqNgqQRfFHVw6CrtGeENZivh5CvK", "value": 2.3125},
                {"to": "1BMzVAyQQB4y5MUyGtp9jrPQGPsetqVRpy", "value": 2.3125},
            ],
            "version": 6,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "",
        },
    ],
    "id": "MEQCIFChEOyOTkWmSGp9fkXo6VJ6DJ+//gmEk68ZW8503gKhAiB6RQYV4XLPFzLjP8ESQ3k/CRDRRb8w9P80QW/G8BmcAw==",
    "header": "",
    "prevHash": "00000000c7dc961a0b86785fdd68298fc2bfcfffe86a8a343e6e6feb33916c5c",
}

block2 = {
    "merkleRoot": "c816fe62ee6c883226cb8dad100d9338963544c5d9fe8384c5b0be9aaf0cd962",
    "time": 1537979085,
    "index": 11001,
    "version": 1,
    "target": "0000003fffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "public_key": "03672bfbbf29e31a4429e3bc18240c98f0dcfbdd4e6e12aa70657e2095b7d84425",
    "hash": "00000027175a9dde28a7b26517b026a7866ddb1cfcceaa3627558b5931a1e6c4",
    "nonce": 14636080,
    "transactions": [
        {
            "time": 1734014275,
            "rid": "",
            "id": "MEUCIQCs71oq9RCVIzhEfkB4Fh9GvcskmJ0Pm4Xb6McjQpreqwIgDLWGTNP5ipXfCBd8JjCQ9QKrkFrl+O5sQtDojQX3dXQ=",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "03672bfbbf29e31a4429e3bc18240c98f0dcfbdd4e6e12aa70657e2095b7d84425",
            "dh_public_key": "",
            "fee": 1,
            "masternode_fee": 8,
            "hash": "bf6a327425fc1eb61c13e27f4e1535bca054dc6175bfe2356a57a33d16c583bd",
            "inputs": [
                {
                    "id": "MEUCIQDNeRV9ZOx57cDYybt8Kz64MZfWpuxHRbyWVvvd33XZsAIgBtKGlJhFP9lKLU3ma2WuZYF0za2OKF5FD8Rs8y4uXr8="
                }
            ],
            "outputs": [
                {"to": "136g8v7ksWZwpfTCBEB9fbfDJB6qsdYzzb", "value": 10},
                {"to": "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu", "value": 2.25},
            ],
            "version": 6,
            "prerotated_key_hash": "",
        },
        {
            "time": 1734248890,
            "rid": "",
            "id": "MEUCIQCbXTEPRp+0cb80gxjOAharft7JCCMjIW0vZDXhR5t59QIgVsFeqs0b5QwXRd6S4/cemjwLIMl7cr+MjosdZeDApo4=",
            "relationship": "",
            "public_key": "02fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc",
            "dh_public_key": "",
            "fee": 0,
            "masternode_fee": 0,
            "hash": "1f35c1b5564a901d4d1c6e6aba156815c3cfffa42fbf705557495f0e01293ff0",
            "inputs": [],
            "outputs": [
                {"to": "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu", "value": 12.25},
                {"to": "13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK", "value": 2.3125},
                {"to": "1L7dEh8ckRF4ftP3TUztfJsi8hXL8KUahY", "value": 2.3125},
                {"to": "1DX4nGHqNgqQRfFHVw6CrtGeENZivh5CvK", "value": 2.3125},
                {"to": "1BMzVAyQQB4y5MUyGtp9jrPQGPsetqVRpy", "value": 2.3125},
            ],
            "version": 6,
            "private": False,
            "never_expire": False,
            "prerotated_key_hash": "",
        },
    ],
    "id": "MEUCIQDVQKsWTCc5TeAk8PoFUGDqYUyLXWp8pfANz40qvCMF7gIgb0MrEze0XfvD7KBGj86f12A4m4AHauCziwSEY7ny0dg=",
    "header": "",
    "prevHash": "00000027175a9dde28a7b26517b026a7866ddb1cfcceaa3627558b5931a1e6c3",
}

mempool = {
    "time": 1734020000,
    "rid": "",
    "id": "MEQCIDqgRGrgzHT/k74RfCDViFpaCFZA0o76IH14ZKVY7OfZAiBMFTpyXhgSeQQIUGf0bT92xHJ9qpkpaRaxFKD5VX8UnA==",
    "relationship": "",
    "public_key": "03672bfbbf29e31a4429e3bc18240c98f0dcfbdd4e6e12aa70657e2095b7d84425",
    "dh_public_key": "",
    "fee": 0.0,
    "hash": "cf8b32354890a36b7f9f8bdb8c823f222ad47434b02a6f74b123f6b94b82890c",
    "inputs": [
        {
            "id": "MEUCIQCbXTEPRp+0cb80gxjOAharft7JCCMjIW0vZDXhR5t59QIgVsFeqs0b5QwXRd6S4/cemjwLIMl7cr+MjosdZeDApo4="
        }
    ],
    "outputs": [
        {"to": "13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK", "value": 7.25},
        {"to": "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu", "value": 5},
    ],
}


class TestUTXO(AsyncTestCase):
    """
    This test class verifies the functionality of the `get_unspent_outputs` method,
    which is responsible for retrieving unspent transaction outputs (UTXOs) for a given address.
    """

    async def asyncSetUp(self):
        """
        Sets up a new test environment for each test case:
        - Creates a new MongoDB instance specific to this test.
        - Configures a fresh blockchain state with a genesis block.
        - Mocks application logging to avoid conflicts during testing.
        """
        self.config = Config.generate()  # Generates default configuration for testing
        self.config.database = hashlib.sha256(str(time.time()).encode()).hexdigest()[
            :10
        ]
        self.config.mongo = Mongo()
        self.config.BU = yadacoin.core.blockchainutils.BlockChainUtils()

        # Mocking the logger to suppress logs in testing environment
        self.config.app_log = MagicMock()

        # Add the genesis block to the mock database
        genesis_block = await Blockchain.get_genesis_block()
        await self.config.mongo.async_db.blocks.insert_one(genesis_block.to_dict())

    async def test_utxo(self):
        """
        Tests the retrieval of UTXOs for a given address. The test verifies:
        - The UTXO count matches the expected results.
        - The total balance from UTXOs matches the expected sum.
        - Individual UTXOs match their expected values (id and outputs).
        """
        # Insert mock blocks and mempool transactions into the test database
        await self.config.mongo.async_db.blocks.insert_one(block1)
        await self.config.mongo.async_db.blocks.insert_one(block2)
        await self.config.mongo.async_db.miner_transactions.insert_one(mempool)

        # Define the address, amount needed, and minimum value for UTXO filtering
        address = "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu"
        amount_needed = 42.25
        min_value = 0

        # Fetch the unspent outputs for the specified address
        utxo_result = await self.config.BU.get_unspent_outputs(
            address, amount_needed=amount_needed, min_value=min_value
        )

        # Define the expected UTXO outputs for the given address
        expected_unspent_utxos = [
            {
                "id": "MEQCIFv+0r78YqWcdmgMNasrtfzAzvdSinZpQGTrNax3GYA1AiAUbdf4cWp2kDoulPd7Dm3NlJ2cZebmyplKw5QSyH6SQQ==",
                "outputs": [{"to": "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu", "value": 40}],
            },
            {
                "id": "MEUCIQCs71oq9RCVIzhEfkB4Fh9GvcskmJ0Pm4Xb6McjQpreqwIgDLWGTNP5ipXfCBd8JjCQ9QKrkFrl+O5sQtDojQX3dXQ=",
                "outputs": [
                    {"to": "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu", "value": 2.25}
                ],
            },
        ]

        # Assert the total count of UTXOs matches the expected count
        self.assertEqual(len(utxo_result["unspent_utxos"]), len(expected_unspent_utxos))

        # Assert the total balance matches the sum of expected UTXO values
        self.assertAlmostEqual(
            utxo_result["balance"],
            sum([utxo["outputs"][0]["value"] for utxo in expected_unspent_utxos]),
            places=8,
        )

        # Assert each UTXO in the result matches the expected values
        for expected, actual in zip(
            expected_unspent_utxos, utxo_result["unspent_utxos"]
        ):
            self.assertEqual(expected["id"], actual["id"])
            self.assertEqual(expected["outputs"], actual["outputs"])

        # Log the results for debugging purposes
        logger.info(f"Unspent UTXOs: {utxo_result['unspent_utxos']}")
        logger.info(f"Total Balance: {utxo_result['balance']}")

    async def asyncTearDown(self):
        """
        Cleans up the test environment by dropping the test database
        created during `asyncSetUp`. This ensures no leftover data interferes
        with subsequent tests.
        """
        await self.config.mongo.async_db.client.drop_database(self.config.database)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
