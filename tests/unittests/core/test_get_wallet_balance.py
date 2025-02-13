import hashlib
import logging
import time
import unittest
from unittest import mock

from mongomock import MongoClient

import yadacoin.core.config
from tests.unittests.test_setup import AsyncTestCase
from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.config import Config
from yadacoin.core.mongo import Mongo

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestWalletBalance(AsyncTestCase):
    @mock.patch(
        "yadacoin.core.blockchain.Blockchain.mongo", new_callable=lambda: MongoClient
    )
    async def asyncSetUp(self, mongo):
        mongo.async_db = mock.MagicMock()
        mongo.async_db.blocks = mock.MagicMock()
        yadacoin.core.config.CONFIG = Config.generate()
        Config().mongo = mongo

    async def setBlock(self):
        self.block = await Block.from_dict(block)

    async def test_get_wallet_balance(self):
        config = Config()
        config.database = hashlib.sha256(str(time.time()).encode()).hexdigest()[:10]
        config.mongo = Mongo()
        config.BU = yadacoin.core.blockchainutils.BlockChainUtils()
        genesis_block = await Blockchain.get_genesis_block()
        await config.mongo.async_db.blocks.insert_one(genesis_block.to_dict())

        spend_block = await Block.from_dict(
            {
                "merkleRoot": "c816fe62ee6c883226cb8dad100d9338963544c5d9fe8384c5b0be9aaf0cd961",
                "time": 1537979085,
                "index": 11356,
                "version": 1,
                "target": "0000003fffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "public_key": "03672bfbbf29e31a4429e3bc18240c98f0dcfbdd4e6e12aa70657e2095b7d84425",
                "hash": "00000027175a9dde28a7b26517b026a7866ddb1cfcceaa3627558b5931a1e6c3",
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
                                "id": "MEUCIQCuu5+qnktLtzXnyZJDvalOsIPcLVhrHzT9p6w65D4QuwIgMTWKvwU0tWLJsIvJyJ900HG+ZHgx4KOtN200HXjUGNI="
                            }
                        ],
                        "outputs": [
                            {"to": "136g8v7ksWZwpfTCBEB9fbfDJB6qsdYzzb", "value": 20},
                            {"to": "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu", "value": 10},
                        ],
                        "version": 6,
                        "prerotated_key_hash": "",
                    },
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
                        "time": 1734110905,
                        "rid": "",
                        "id": "MEMCIHTGaAXZRG+ttkiwdIZk74JbWy3wyCQBRfdkQWyF4ZOVAh8lxKEeDe+wNJ8udZIKb994PhDbggmvf+Fbq5MsvtGZ",
                        "relationship": "",
                        "relationship_hash": "",
                        "public_key": "03e1ab14af772224ba6cca0a8be1a8471c3deffd0745b7a911634320b30416d910",
                        "dh_public_key": "",
                        "fee": 0,
                        "masternode_fee": 0,
                        "hash": "8e04663c19f7f3c98aaef5897bf8b3427f5eee6fb95fc99dc82c77e735a01e71",
                        "inputs": [
                            {
                                "id": "MEQCIA7EM2td8gpIKbBcM2uytf0DD1UT22T3+p7i5y7eVz8yAiBy6n4OQLZpFgPca4Yj3lVOOoEgvfAlUJi8fTl1o5FwvQ=="
                            },
                            {
                                "id": "MEUCIQCaVzf5FQ3lqCc7VOguN/O1OjX/BOJQByqP0r1dRxNU0gIgHwsIcPESsdWBbMNumHWqi9FpCeLgu5MsVAdCP2dW16A="
                            },
                        ],
                        "outputs": [
                            {"to": "1BMzVAyQQB4y5MUyGtp9jrPQGPsetqVRpy", "value": 2700}
                        ],
                        "version": 6,
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
                            {
                                "to": "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu",
                                "value": 12.25,
                            },
                            {
                                "to": "13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK",
                                "value": 2.3125,
                            },
                            {
                                "to": "1L7dEh8ckRF4ftP3TUztfJsi8hXL8KUahY",
                                "value": 2.3125,
                            },
                            {
                                "to": "1DX4nGHqNgqQRfFHVw6CrtGeENZivh5CvK",
                                "value": 2.3125,
                            },
                            {
                                "to": "1BMzVAyQQB4y5MUyGtp9jrPQGPsetqVRpy",
                                "value": 2.3125,
                            },
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
                "updated_at": 1.5724002324503367e9,
            }
        )

        await config.mongo.async_db.blocks.insert_one(spend_block.to_dict())

        # Test address 1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu
        address = "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu"
        expected_coinbase_balance = 12.25
        expected_mn_coinbase_balance = 0.0
        expected_total_received = 40.0
        # Total spent includes 20 (transaction output) + 1 (fee) + 8 (masternode fee)
        expected_total_spent = 29.0
        expected_final_balance = (
            expected_coinbase_balance
            + expected_mn_coinbase_balance
            + expected_total_received
            - expected_total_spent
        )

        coinbase_balance = await config.BU.get_coinbase_total_output_balance(address)
        mn_coinbase_balance = await config.BU.get_masternode_coinbase_balance(address)
        total_received_balance = await config.BU.get_total_received_balance(address)
        total_spent_balance = await config.BU.get_spent_balance(address)
        final_balance = (
            coinbase_balance
            + total_received_balance
            + mn_coinbase_balance
            - total_spent_balance
        )

        logger.info(f"Coinbase balance for {address}: {coinbase_balance}")
        logger.info(f"Masternode coinbase balance for {address}: {mn_coinbase_balance}")
        logger.info(f"Total received balance for {address}: {total_received_balance}")
        logger.info(f"Total spent balance for {address}: {total_spent_balance}")
        logger.info(f"Final balance for {address}: {final_balance}")

        self.assertAlmostEqual(coinbase_balance, expected_coinbase_balance, places=8)
        self.assertAlmostEqual(
            mn_coinbase_balance, expected_mn_coinbase_balance, places=8
        )
        self.assertAlmostEqual(
            total_received_balance, expected_total_received, places=8
        )
        self.assertAlmostEqual(total_spent_balance, expected_total_spent, places=8)
        self.assertAlmostEqual(final_balance, expected_final_balance, places=8)

        # Test MN address 1BMzVAyQQB4y5MUyGtp9jrPQGPsetqVRpy
        mn_address = "1BMzVAyQQB4y5MUyGtp9jrPQGPsetqVRpy"
        expected_miner_coinbase_balance = 0.0
        expected_mn_coinbase_balance = 2.3125
        expected_mn_total_received = 0.0
        expected_mn_total_spent = 0.0
        expected_mn_final_balance = (
            expected_miner_coinbase_balance
            + expected_mn_coinbase_balance
            + expected_mn_total_received
            - expected_mn_total_spent
        )

        miner_coinbase_balance = await config.BU.get_coinbase_total_output_balance(
            mn_address
        )
        mn_coinbase_balance = await config.BU.get_masternode_coinbase_balance(
            mn_address
        )
        mn_total_received_balance = await config.BU.get_total_received_balance(
            mn_address
        )
        mn_total_spent_balance = await config.BU.get_spent_balance(mn_address)
        mn_final_balance = (
            miner_coinbase_balance
            + mn_coinbase_balance
            + mn_total_received_balance
            - mn_total_spent_balance
        )

        logger.info(f"Coinbase balance for MN {mn_address}: {miner_coinbase_balance}")
        logger.info(
            f"Masternode coinbase balance for MN {mn_address}: {mn_coinbase_balance}"
        )
        logger.info(
            f"Total received balance for MN {mn_address}: {mn_total_received_balance}"
        )
        logger.info(
            f"Total spent balance for MN {mn_address}: {mn_total_spent_balance}"
        )
        logger.info(f"Final balance for MN {mn_address}: {mn_final_balance}")

        self.assertAlmostEqual(
            miner_coinbase_balance, expected_miner_coinbase_balance, places=8
        )
        self.assertAlmostEqual(
            mn_coinbase_balance, expected_mn_coinbase_balance, places=8
        )
        self.assertAlmostEqual(
            mn_total_received_balance, expected_mn_total_received, places=8
        )
        self.assertAlmostEqual(
            mn_total_spent_balance, expected_mn_total_spent, places=8
        )
        self.assertAlmostEqual(mn_final_balance, expected_mn_final_balance, places=8)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
