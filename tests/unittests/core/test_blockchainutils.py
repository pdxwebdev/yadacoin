import time
import unittest

from yadacoin.app import NodeApplication
from yadacoin.core.block import Block
from yadacoin.core.config import Config

from ..test_setup import AsyncTestCase


class TestBlockchainUtils(AsyncTestCase):
    async def setBlock(self):
        self.block = await Block.from_dict(
            {
                "nonce": 0,
                "hash": "0dd0ec9ab91e9defe535841a4c70225e3f97b7447e5358250c2dc898b8bd3139",
                "public_key": "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
                "id": "MEUCIQDDicnjg9DTSnGOMLN3rq2VQC1O9ABDiXygW7QDB6SNzwIga5ri7m9FNlc8dggJ9sDg0QXUugrHwpkVKbmr3kYdGpc=",
                "merkleRoot": "705d831ced1a8545805bbb474e6b271a28cbea5ada7f4197492e9a3825173546",
                "index": 0,
                "target": "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "special_min": False,
                "version": "1",
                "transactions": [
                    {
                        "public_key": "03f44c7c4dca3a9204f1ba284d875331894ea8ab5753093be847d798274c6ce570",
                        "fee": 0.0000000000000000,
                        "hash": "71429326f00ba74c6665988bf2c0b5ed9de1d57513666633efd88f0696b3d90f",
                        "dh_public_key": "",
                        "relationship": "",
                        "inputs": [],
                        "outputs": [
                            {
                                "to": "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4",
                                "value": 50.0000000000000000,
                            }
                        ],
                        "rid": "",
                        "id": "MEUCIQDZbaCDMmJJ+QJHldj1EWu0yG7enlwRAXoO1/B617KaxgIgBLB4L2ICWpDZf5Eo2bcXgUmKd91ayrOG/6jhaIZAPb0=",
                    }
                ],
                "time": "1537127756",
                "prevHash": "",
            }
        )

    async def test_is_input_spent(self):
        NodeApplication(test=True)
        config = Config()
        await self.setBlock()
        start = time.time()
        await config.BU.is_input_spent(
            [x.id for x in self.block.transactions[0].inputs],
            self.block.transactions[1].public_key,
        )
        duration = time.time() - start
        config.app_log.info(f"Duration: {duration}")

    async def test_get_wallet_unspent_transactions(self):
        NodeApplication(test=True)
        config = Config()
        await self.setBlock()
        start = time.time()
        config.mongo_query_timeout = 100
        [
            x
            async for x in config.BU.get_wallet_unspent_transactions(
                "1iNw3QHVs45woB9TmXL1XWHyKniTJhzC4"
            )
        ]
        duration = time.time() - start
        config.app_log.info(f"Duration: {duration}")


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
