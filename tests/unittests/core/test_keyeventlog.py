import json
import unittest
from unittest import mock
from unittest.mock import AsyncMock

from mongomock import MongoClient

import yadacoin.core.config
from yadacoin.core.block import Block
from yadacoin.core.config import Config
from yadacoin.core.keyeventlog import (
    KELExceptionMissingConfirmingKeyEvent,
    KELExceptionMissingUnconfirmedKeyEvent,
    KeyEventLog,
    KeyEventPrerotatedKeyHashException,
    KeyEventSingleOutputException,
)
from yadacoin.core.transaction import Output

from ..test_setup import AsyncTestCase

check_kel_inception_block = {
    "version": 5,
    "time": 1724395336,
    "index": 522000,
    "public_key": "02cd94b54fa5ec2431013e047e3d609d385e40c73538639acb77f6d1b0f2b46c4a",
    "prevHash": "cedde7cc43d2c4fafcbb0548914e00201322a8b406e92693a353d33504000000",
    "nonce": "f083710172",
    "transactions": [
        {
            "txn_time": 0,
            "inputs": [],
            "time": 1733280530243,
            "public_key": "026e406e692647b4092862fc91a01c53e9844d3746b0e2bbc42c2cf22f47f553c6",
            "dh_public_key": "",
            "fee": 0,
            "masternode_fee": 0,
            "requester_rid": "",
            "requested_rid": "",
            "outputs": [{"to": "1Afmnw9vDdRN6hZwDuJKt8fvSVTc4wssS4"}],
            "version": 2,
            "prerotated_key_hash": "1Afmnw9vDdRN6hZwDuJKt8fvSVTc4wssS4",
            "twice_prerotated_key_hash": "1KpQbYXo7ixCY1zLkYpT2yzLomkZFyNkdh",
            "public_key_hash": "1Kwn4a7hpWkqBEkdxZFNZHX8RKtBWYBaeD",
        }
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

check_kel_single_rotation_block = {
    "version": 5,
    "time": 1724395336,
    "index": 522001,
    "public_key": "02cd94b54fa5ec2431013e047e3d609d385e40c73538639acb77f6d1b0f2b46c4a",
    "prevHash": "cedde7cc43d2c4fafcbb0548914e00201322a8b406e92693a353d33504000000",
    "nonce": "f083710172",
    "transactions": [
        {
            "txn_time": 0,
            "inputs": [],
            "time": 1733282554376,
            "public_key": "0212a8a5d39905af26eddc4d2c6c35129527217eaa0ab3b120c50becc06fdbf003",
            "dh_public_key": "",
            "fee": 0,
            "masternode_fee": 0,
            "requester_rid": "",
            "requested_rid": "",
            "outputs": [{"to": "1KpQbYXo7ixCY1zLkYpT2yzLomkZFyNkdh"}],
            "version": 2,
            "prerotated_key_hash": "1KpQbYXo7ixCY1zLkYpT2yzLomkZFyNkdh",
            "twice_prerotated_key_hash": "12eMVdSXmqHLCbzD1kPSakC5N4KenhzuU1",
            "public_key_hash": "1Afmnw9vDdRN6hZwDuJKt8fvSVTc4wssS4",
        },
        {
            "txn_time": 0,
            "inputs": [],
            "time": 1733282554381,
            "public_key": "02855b4b074e4fc5561ba038148b3ffcbe912ba14d8bd201e1719cd830cdda0367",
            "dh_public_key": "",
            "fee": 0,
            "masternode_fee": 0,
            "requester_rid": "",
            "requested_rid": "",
            "outputs": [{"to": "12eMVdSXmqHLCbzD1kPSakC5N4KenhzuU1"}],
            "version": 2,
            "prerotated_key_hash": "12eMVdSXmqHLCbzD1kPSakC5N4KenhzuU1",
            "twice_prerotated_key_hash": "1KpDDetEZ4ntAZ6VvuEEuQUGAUDgEZYyFN",
            "public_key_hash": "1KpQbYXo7ixCY1zLkYpT2yzLomkZFyNkdh",
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

check_kel_single_rotation_block_external_unconfirmed = {
    "version": 5,
    "time": 1724395336,
    "index": 522001,
    "public_key": "02cd94b54fa5ec2431013e047e3d609d385e40c73538639acb77f6d1b0f2b46c4a",
    "prevHash": "cedde7cc43d2c4fafcbb0548914e00201322a8b406e92693a353d33504000000",
    "nonce": "f083710172",
    "transactions": [
        {
            "txn_time": 0,
            "inputs": [],
            "time": 1733282554376,
            "public_key": "0212a8a5d39905af26eddc4d2c6c35129527217eaa0ab3b120c50becc06fdbf003",
            "dh_public_key": "",
            "fee": 0,
            "masternode_fee": 0,
            "requester_rid": "",
            "requested_rid": "",
            "outputs": [{"to": "some external address"}],
            "version": 2,
            "prerotated_key_hash": "1KpQbYXo7ixCY1zLkYpT2yzLomkZFyNkdh",
            "twice_prerotated_key_hash": "12eMVdSXmqHLCbzD1kPSakC5N4KenhzuU1",
            "public_key_hash": "1Afmnw9vDdRN6hZwDuJKt8fvSVTc4wssS4",
        },
        {
            "txn_time": 0,
            "inputs": [],
            "time": 1733282554381,
            "public_key": "02855b4b074e4fc5561ba038148b3ffcbe912ba14d8bd201e1719cd830cdda0367",
            "dh_public_key": "",
            "fee": 0,
            "masternode_fee": 0,
            "requester_rid": "",
            "requested_rid": "",
            "outputs": [{"to": "12eMVdSXmqHLCbzD1kPSakC5N4KenhzuU1"}],
            "version": 2,
            "prerotated_key_hash": "12eMVdSXmqHLCbzD1kPSakC5N4KenhzuU1",
            "twice_prerotated_key_hash": "1KpDDetEZ4ntAZ6VvuEEuQUGAUDgEZYyFN",
            "public_key_hash": "1KpQbYXo7ixCY1zLkYpT2yzLomkZFyNkdh",
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


class TestKeyEventLog(AsyncTestCase):
    @mock.patch(
        "yadacoin.core.blockchain.Blockchain.mongo", new_callable=lambda: MongoClient
    )
    async def asyncSetUp(self, mongo):
        mongo.async_db = mock.AsyncMock()
        mongo.async_db.blocks = mock.AsyncMock()
        mongo.async_db.blocks.aggregate = mock.AsyncMock()
        yadacoin.core.config.CONFIG = Config.generate()
        Config().mongo = mongo

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_one_key_event(self, mock_aggregate):
        inception_block = await Block.from_dict(check_kel_inception_block)

        mock_cursor = mock.Mock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_aggregate.return_value = mock_cursor

        for txn in inception_block.transactions:
            await KeyEventLog.from_transaction_with_block(txn, inception_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events(self, mock_aggregate):
        single_rotation_block = await Block.from_dict(
            json.loads(json.dumps(check_kel_single_rotation_block))
        )

        for txn in single_rotation_block.transactions:
            clone_check_kel_inception_block = json.loads(
                json.dumps(check_kel_inception_block)
            )
            clone_check_kel_inception_block[
                "transactions"
            ] = clone_check_kel_inception_block["transactions"][0]
            mock_cursor = mock.Mock()
            mock_cursor.to_list = AsyncMock(
                return_value=[clone_check_kel_inception_block]
            )
            mock_aggregate.return_value = mock_cursor
            await KeyEventLog.from_transaction_with_block(txn, single_rotation_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_external_unconfirmed(
        self, mock_aggregate
    ):
        single_rotation_block_external_unconfirmed = await Block.from_dict(
            json.loads(json.dumps(check_kel_single_rotation_block_external_unconfirmed))
        )

        for txn in single_rotation_block_external_unconfirmed.transactions:
            clone_check_kel_inception_block = json.loads(
                json.dumps(check_kel_inception_block)
            )
            clone_check_kel_inception_block[
                "transactions"
            ] = clone_check_kel_inception_block["transactions"][0]
            mock_cursor = mock.Mock()
            mock_cursor.to_list = AsyncMock(
                return_value=[clone_check_kel_inception_block]
            )
            mock_aggregate.return_value = mock_cursor
            await KeyEventLog.from_transaction_with_block(
                txn, single_rotation_block_external_unconfirmed
            )

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_missing_confirming(
        self, mock_aggregate
    ):
        clone_dict = json.loads(
            json.dumps(check_kel_single_rotation_block_external_unconfirmed)
        )
        del clone_dict["transactions"][1]
        clone_block = await Block.from_dict(clone_dict)

        with self.assertRaises(KELExceptionMissingConfirmingKeyEvent):
            for txn in clone_block.transactions:
                clone_check_kel_inception_block = json.loads(
                    json.dumps(check_kel_inception_block)
                )
                clone_check_kel_inception_block[
                    "transactions"
                ] = clone_check_kel_inception_block["transactions"][0]
                mock_cursor = mock.Mock()
                mock_cursor.to_list = AsyncMock(
                    return_value=[clone_check_kel_inception_block]
                )
                mock_aggregate.return_value = mock_cursor
                await KeyEventLog.from_transaction_with_block(txn, clone_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_missing_unconfirmed(
        self, mock_aggregate
    ):
        clone_dict = json.loads(
            json.dumps(check_kel_single_rotation_block_external_unconfirmed)
        )
        del clone_dict["transactions"][0]
        clone_block = await Block.from_dict(clone_dict)
        with self.assertRaises(KELExceptionMissingUnconfirmedKeyEvent):
            for txn in clone_block.transactions:
                clone_check_kel_inception_block = json.loads(
                    json.dumps(check_kel_inception_block)
                )
                clone_check_kel_inception_block[
                    "transactions"
                ] = clone_check_kel_inception_block["transactions"][0]
                mock_cursor = mock.Mock()
                mock_cursor.to_list = AsyncMock(
                    return_value=[clone_check_kel_inception_block]
                )
                mock_aggregate.return_value = mock_cursor
                await KeyEventLog.from_transaction_with_block(txn, clone_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_external_confirming(
        self, mock_aggregate
    ):
        clone_dict = json.loads(
            json.dumps(check_kel_single_rotation_block_external_unconfirmed)
        )
        clone_block = await Block.from_dict(clone_dict)
        clone_block.transactions[1].outputs[0].to = "some external output"
        with self.assertRaises(KeyEventPrerotatedKeyHashException):
            for txn in clone_block.transactions:
                clone_check_kel_inception_block = json.loads(
                    json.dumps(check_kel_inception_block)
                )
                clone_check_kel_inception_block[
                    "transactions"
                ] = clone_check_kel_inception_block["transactions"][0]
                mock_cursor = mock.Mock()
                mock_cursor.to_list = AsyncMock(
                    return_value=[clone_check_kel_inception_block]
                )
                mock_aggregate.return_value = mock_cursor
                await KeyEventLog.from_transaction_with_block(txn, clone_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_multiple_outputs_confirming(
        self, mock_aggregate
    ):
        clone_dict = json.loads(
            json.dumps(check_kel_single_rotation_block_external_unconfirmed)
        )
        clone_block = await Block.from_dict(clone_dict)
        clone_block.transactions[1].outputs.append(
            json.loads(json.dumps(clone_block.transactions[1].outputs[0].to_dict()))
        )
        with self.assertRaises(KeyEventSingleOutputException):
            for txn in clone_block.transactions:
                clone_check_kel_inception_block = json.loads(
                    json.dumps(check_kel_inception_block)
                )
                clone_check_kel_inception_block[
                    "transactions"
                ] = clone_check_kel_inception_block["transactions"][0]
                mock_cursor = mock.Mock()
                mock_cursor.to_list = AsyncMock(
                    return_value=[clone_check_kel_inception_block]
                )
                mock_aggregate.return_value = mock_cursor
                await KeyEventLog.from_transaction_with_block(txn, clone_block)

    @mock.patch("yadacoin.core.config.CONFIG.mongo.async_db.blocks.aggregate")
    async def test_from_transaction_with_block_two_key_events_multiple_outputs_unconfirmed(
        self, mock_aggregate
    ):
        clone_dict = json.loads(
            json.dumps(check_kel_single_rotation_block_external_unconfirmed)
        )
        clone_block = await Block.from_dict(clone_dict)
        clone_block.transactions[0].outputs.append(
            Output.from_dict(
                json.loads(json.dumps(clone_block.transactions[1].outputs[0].to_dict()))
            )
        )
        clone_block.transactions[0].outputs.append(
            Output.from_dict(
                json.loads(json.dumps(clone_block.transactions[1].outputs[0].to_dict()))
            )
        )
        clone_block.transactions[0].outputs[0].to = "first external output"
        clone_block.transactions[0].outputs[1].to = "second external output"
        clone_block.transactions[0].outputs[2].to = "third external output"
        for txn in clone_block.transactions:
            clone_check_kel_inception_block = json.loads(
                json.dumps(check_kel_inception_block)
            )
            clone_check_kel_inception_block[
                "transactions"
            ] = clone_check_kel_inception_block["transactions"][0]
            mock_cursor = mock.Mock()
            mock_cursor.to_list = AsyncMock(
                return_value=[clone_check_kel_inception_block]
            )
            mock_aggregate.return_value = mock_cursor
            await KeyEventLog.from_transaction_with_block(txn, clone_block)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
