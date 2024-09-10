import unittest
from unittest import mock
from unittest.mock import AsyncMock, Mock

from mongomock import MongoClient

import yadacoin.core.config
from yadacoin.core.block import Block, quantize_eight
from yadacoin.core.config import Config
from yadacoin.core.nodes import Nodes
from yadacoin.core.transaction import TotalValueMismatchException

from ..test_setup import AsyncTestCase


def mock_generate_hash_from_header(header, nonce, index, something):
    return "efc6f919f2d1bb5b3609caf29bbde5c6361ebcfd3b915802edf8c3ed02000000"


def mock_get_merkle_root(a, b):
    return "48bf91114ecbfaf4a353935c245763309c8834a3147f7fcb71bd418c1a6693cf"


masternode_fee_block = {
    "version": 5,
    "time": 1724395336,
    "index": 503857,
    "public_key": "02cd94b54fa5ec2431013e047e3d609d385e40c73538639acb77f6d1b0f2b46c4a",
    "prevHash": "cedde7cc43d2c4fafcbb0548914e00201322a8b406e92693a353d33504000000",
    "nonce": "f083710172",
    "transactions": [
        {
            "time": 1724394584,
            "rid": "",
            "id": "MEUCIQDxNoDk4VCoBhhZVC3Gqr71aJxOKC7utFM/CRAzpV8RBQIgPHIyPOC9c/NQFLjdMosftIQiF6i7l4NWbJgD7AChoYk=",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "03773b7e2e25979f6424d050ae87b91e8d2fe1531581b19f15bd0a165cf52df516",
            "dh_public_key": "",
            "fee": 0.0001,
            "masternode_fee": 0.1,
            "hash": "96055eed53cc90423f3b816ae14a62b68200225587106b68812127d3083d331e",
            "inputs": [
                {
                    "id": "MEUCIQDHrmClDxuHFB8eT6I9fgE0ixSyKDZ7rPa7/SHu5VdQRAIgCU28LdmYjHcZV2SjADujcPoiH4g8UBhZej76Iut/zRQ="
                }
            ],
            "outputs": [
                {"to": "123BJPNVts6Bjo66pQRbVGn1VNTsAJMJLZ", "value": 2.9},
                {
                    "to": "1KF21jbNPbbisv5XijhTUYP2SDMih9QiKm",
                    "value": 35.723733333334184,
                },
            ],
            "version": 5,
            "private": False,
            "never_expire": False,
        },
        {
            "time": 1724395336,
            "rid": "",
            "id": "MEQCIB1y0vV9blIwLyThNEtBTrHXhyqMvO1n18Yuf5w2vHn1AiA1kjMEIpmYVYs4xfxuFF4ufyJXL+kUGkdOcWPgtab8XA==",
            "relationship": "",
            "relationship_hash": "",
            "public_key": "02cd94b54fa5ec2431013e047e3d609d385e40c73538639acb77f6d1b0f2b46c4a",
            "dh_public_key": "",
            "fee": 0.0,
            "masternode_fee": 0.0,
            "hash": "f17b4c769468737fd2e82dde745877c5859169570b96a96b0d931d7652a86654",
            "inputs": [],
            "outputs": [
                {
                    "to": "1NRnusod4G5MgAgyRaJXdJPFmqyyDyzRsK",
                    "value": 11.2501,
                },
                {
                    "to": "13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK",
                    "value": 1.35,
                },
            ],
            "version": 5,
            "private": False,
            "never_expire": False,
        },
    ],
    "hash": "efc6f919f2d1bb5b3609caf29bbde5c6361ebcfd3b915802edf8c3ed02000000",
    "merkleRoot": "48bf91114ecbfaf4a353935c245763309c8834a3147f7fcb71bd418c1a6693cf",
    "special_min": False,
    "target": "000000092b182df6cb5d80000000000000000000000000000000000000000000",
    "special_target": "000000092b182df6cb5d80000000000000000000000000000000000000000000",
    "header": "5172439533602cd94b54fa5ec2431013e047e3d609d385e40c73538639acb77f6d1b0f2b46c4a503857cedde7cc43d2c4fafcbb0548914e00201322a8b406e92693a353d33504000000{nonce}000000092b182df6cb5d8000000000000000000000000000000000000000000048bf91114ecbfaf4a353935c245763309c8834a3147f7fcb71bd418c1a6693cf",
    "id": "MEUCIQDL4tMI2YurJjanEgQPdT1jAbzz2LPmB+gqNq6O2Hvg6gIgNSE6RGq6uhpLZBlBQKgFUIGW3hUeIt9cEkKRZU9Atnk=",
    "updated_at": 1.724396174143057e9,
}

masternode_fee_input = {
    "time": 1724393850,
    "rid": "",
    "id": "MEUCIQDHrmClDxuHFB8eT6I9fgE0ixSyKDZ7rPa7/SHu5VdQRAIgCU28LdmYjHcZV2SjADujcPoiH4g8UBhZej76Iut/zRQ=",
    "relationship": "",
    "relationship_hash": "",
    "public_key": "03773b7e2e25979f6424d050ae87b91e8d2fe1531581b19f15bd0a165cf52df516",
    "dh_public_key": "",
    "fee": 0.0,
    "masternode_fee": 0.0,
    "hash": "5e8f0b68bf21e87171d74fa2f5c23be020e077bfe13d154f47830aee71e4705b",
    "inputs": [
        {
            "id": "MEUCIQCGdGnXWfPZ8asqEF5GRBH7EsRNjGSYjv0G51KCRaCzYwIgcU/RNMu3rEh8q6DfRPzJy9g46KOilIn2Y1f52+03BFA="
        }
    ],
    "outputs": [
        {"to": "123BJPNVts6Bjo66pQRbVGn1VNTsAJMJLZ", "value": 2.9},
        {
            "to": "1CHaD71RcagWeRamuwZo1ycpQtR4FRYNJ",
            "value": 38.62383333333418,
        },
    ],
    "version": 5,
    "private": False,
    "never_expire": False,
}


class TestBlock(AsyncTestCase):
    @mock.patch(
        "yadacoin.core.blockchain.Blockchain.mongo", new_callable=lambda: MongoClient
    )
    async def asyncSetUp(self, mongo):
        mongo.async_db = mock.MagicMock()
        mongo.async_db.blocks = mock.MagicMock()
        yadacoin.core.config.CONFIG = Config.generate()
        Config().mongo = mongo

    async def test_init_async(self):
        block = await Block.init_async()
        self.assertIsInstance(block, Block)

    async def test_copy(self):
        block = await Block.init_async()
        block_copy = await block.copy()
        self.assertIsInstance(block_copy, Block)

    async def test_to_dict(self):
        block = await Block.init_async()
        self.assertIsInstance(block.to_dict(), dict)

    async def test_from_dict(self):
        block = await Block.init_async()
        self.assertIsInstance(await Block.from_dict(block.to_dict()), Block)

    async def test_get_coinbase(self):
        block = await Block.init_async()
        coinbase = block.get_coinbase()
        self.assertIsNone(coinbase)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_generate(self, mock_blocks):
        from yadacoin.core.blockchainutils import BlockChainUtils
        from yadacoin.core.chain import CHAIN
        from yadacoin.core.latestblock import LatestBlock

        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        self.assertIsInstance(block, Block)

        Config().BU = BlockChainUtils()

        @property
        async def contract_generated(a):
            return False

        @contract_generated.setter
        def contract_generated(self, value):
            pass

        generate_hash = AsyncMock(
            return_value="96055eed53cc90423f3b816ae14a62b68200225587106b68812127d3083d331e"
        )

        verify_signature = Mock(return_value=True)

        get_transaction_by_id = AsyncMock(return_value=masternode_fee_input)

        def handle_exception(e, txn):
            raise e

        nodes = Nodes.get_all_nodes_for_block_height(CHAIN.CHECK_MASTERNODE_FEE_FORK)

        async def test_all_nodes(a):
            return nodes

        with mock.patch(
            "yadacoin.core.transaction.Transaction.contract_generated",
            new=contract_generated,
        ), mock.patch(
            "yadacoin.core.transaction.Transaction.generate_hash",
            new=generate_hash,
        ), mock.patch(
            "yadacoin.core.transaction.Transaction.verify_signature",
            new=verify_signature,
        ), mock.patch(
            "yadacoin.core.blockchainutils.BlockChainUtils.get_transaction_by_id",
            new=get_transaction_by_id,
        ), mock.patch(
            "yadacoin.core.transaction.Transaction.handle_exception",
            new=handle_exception,
        ), mock.patch(
            "yadacoin.core.block.test_all_nodes", new=test_all_nodes
        ):
            block.index = CHAIN.CHECK_MASTERNODE_FEE_FORK
            Config().LatestBlock = LatestBlock()
            Config().LatestBlock.block = block
            masternode_fee_input["outputs"][1]["value"] = 38.72383333333418
            block = await Block.generate(
                public_key=yadacoin.core.config.CONFIG.public_key,
                private_key=yadacoin.core.config.CONFIG.private_key,
                index=CHAIN.CHECK_MASTERNODE_FEE_FORK,  # activate masternode fee fork, correct masternode fee
                prev_hash="prevhash",
                transactions=[masternode_fee_block["transactions"][0]],
            )
            self.assertIsInstance(block, Block)
            self.assertEqual(
                len(block.transactions[1].outputs), len(nodes) + 1
            )  # + 1 for the miner output
            self.assertEqual(
                float(
                    quantize_eight(
                        sum([x.value for x in block.transactions[1].outputs])
                    )
                ),
                12.6001,
            )
            self.assertEqual(
                float(quantize_eight(block.transactions[1].outputs[1].value)), 0.03
            )

            masternode_fee_block["transactions"][0]["masternode_fee"] = 5
            with self.assertRaises(TotalValueMismatchException):
                await Block.generate(
                    public_key=yadacoin.core.config.CONFIG.public_key,
                    private_key=yadacoin.core.config.CONFIG.private_key,
                    index=CHAIN.CHECK_MASTERNODE_FEE_FORK,  # activate masternode fee fork, incorrect masternode fee
                    prev_hash="prevhash",
                    transactions=[masternode_fee_block["transactions"][0]],
                )

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_generate_hash_from_header(self, mock_blocks):
        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
        )
        block_hash = block.generate_hash_from_header(0, block.header, 0)

        self.assertIsInstance(block_hash, str)
        self.assertTrue(len(block_hash), 64)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_verify(self, mock_blocks):
        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            nonce="0",
        )
        block.hash = block.generate_hash_from_header(0, block.header, "0")
        try:
            await block.verify()
        except Exception:
            from traceback import format_exc

            self.fail(f"verify() raised an exception. {format_exc()}")

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_get_transaction_hashes(self, mock_blocks):
        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            nonce="0",
        )
        self.assertEqual(block.transactions[0].hash, block.get_transaction_hashes()[0])

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_set_merkle_root(self, mock_blocks):
        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            nonce="0",
        )
        block.set_merkle_root(block.get_transaction_hashes())
        self.assertEqual(len(block.merkle_root), 64)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_to_json(self, mock_blocks):
        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})
        block = await Block.generate(
            public_key=yadacoin.core.config.CONFIG.public_key,
            private_key=yadacoin.core.config.CONFIG.private_key,
            nonce="0",
        )
        self.assertIsInstance(block.to_json(), str)

    @mock.patch(
        "yadacoin.core.block.Block.generate_hash_from_header",
        new=mock_generate_hash_from_header,
    )
    @mock.patch("yadacoin.core.block.Block.get_merkle_root", new=mock_get_merkle_root)
    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks")
    async def test_verify_masternode_fee(self, mock_blocks):
        from yadacoin.core.blockchainutils import BlockChainUtils
        from yadacoin.core.chain import CHAIN

        Config().BU = BlockChainUtils()

        mock_blocks.find_one = AsyncMock(return_value={"transactions": []})

        @property
        async def contract_generated(a):
            return False

        @contract_generated.setter
        def contract_generated(self, value):
            pass

        generate_hash = AsyncMock(
            return_value="96055eed53cc90423f3b816ae14a62b68200225587106b68812127d3083d331e"
        )

        verify_signature = Mock(return_value=True)

        get_transaction_by_id = AsyncMock(return_value=masternode_fee_input)

        with mock.patch(
            "yadacoin.core.transaction.Transaction.contract_generated",
            new=contract_generated,
        ), mock.patch(
            "yadacoin.core.transaction.Transaction.generate_hash",
            new=generate_hash,
        ), mock.patch(
            "yadacoin.core.transaction.Transaction.verify_signature",
            new=verify_signature,
        ), mock.patch(
            "yadacoin.core.blockchainutils.BlockChainUtils.get_transaction_by_id",
            new=get_transaction_by_id,
        ):
            block = await Block.from_dict(masternode_fee_block)
            CHAIN.CHECK_MASTERNODE_FEE_FORK = 0
            block.transactions[0].masternode_fee = 0.1  # reset
            block.transactions[1].outputs[1].value = 1.35  # reset
            self.assertIsNone(
                await block.verify()
            )  # test masternode fee fork activated, correct masternode fee

            block.transactions[0].masternode_fee = 1
            with self.assertRaises(TotalValueMismatchException):
                await block.verify()  # test masternode fee fork activated, incorrect masternode fee

            block.transactions[0].masternode_fee = 0.1  # reset
            block.transactions[1].outputs[1].value = 1.25  # reset
            CHAIN.CHECK_MASTERNODE_FEE_FORK = block.index + 1
            self.assertIsNone(
                await block.verify()
            )  # test masternode fee fork deactivated, correct masternode fee

            block.transactions[0].masternode_fee = 1
            self.assertIsNone(
                await block.verify()
            )  # test masternode fee fork deactivated, incorrect masternode fee

            block.transactions[0].masternode_fee = 0.1  # reset
            block.transactions[1].outputs[1].value = 1.25  # reset
            masternode_fee_input["outputs"][1]["value"] = 38.62383333333418  # reset
            await block.transactions[0].verify(
                check_masternode_fee=False
            )  # test masternode fee fork deactivated, incorrect masternode fee

            with self.assertRaises(TotalValueMismatchException):
                await block.transactions[0].verify(
                    check_masternode_fee=True
                )  # test masternode fee fork activated, incorrect masternode fee

            block.transactions[0].masternode_fee = 0.1  # reset
            await block.transactions[0].verify(
                check_masternode_fee=False
            )  # test masternode fee fork deactivated, correct masternode fee
        block.transactions[0].masternode_fee = 0.1  # reset
        masternode_fee_input["outputs"][1]["value"] = 38.72383333333418  # reset
        get_transaction_by_id = AsyncMock(return_value=masternode_fee_input)
        with mock.patch(
            "yadacoin.core.transaction.Transaction.contract_generated",
            new=contract_generated,
        ), mock.patch(
            "yadacoin.core.transaction.Transaction.generate_hash",
            new=generate_hash,
        ), mock.patch(
            "yadacoin.core.transaction.Transaction.verify_signature",
            new=verify_signature,
        ), mock.patch(
            "yadacoin.core.blockchainutils.BlockChainUtils.get_transaction_by_id",
            new=get_transaction_by_id,
        ):
            await block.transactions[0].verify(
                check_masternode_fee=True
            )  # test masternode fee fork activated, correct masternode fee


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
