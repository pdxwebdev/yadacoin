"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from enum import Enum
from typing import TYPE_CHECKING

from bitcoin.wallet import P2PKHBitcoinAddress

from yadacoin.core.config import Config
from yadacoin.core.transaction import Transaction

if TYPE_CHECKING:
    from yadacoin.core.block import Block


class KELException(Exception):
    pass


class KELExceptionMissingInceptionKeyEvent(KELException):
    pass


class KELExceptionMissingUnconfirmedKeyEvent(KELException):
    pass


class KELExceptionMissingConfirmingKeyEvent(KELException):
    pass


class KeyEventTransactionRelationshipException(KELException):
    pass


class PublicKeyMismatchException(Exception):
    pass


class KeyEventChainStatus(Enum):
    ONCHAIN = "onchain"
    MEMPOOL = "mempool"


class KeyEventFlag(Enum):
    CONFIRMING = "confirming"
    INCEPTION = "inception"
    UNCONFIRMED = "unconfirmed"


class BlocksQueryFields(Enum):
    TWICE_PREROTATED_KEY_HASH = "transactions.twice_prerotated_key_hash"
    PREROTATED_KEY_HASH = "transactions.prerotated_key_hash"
    PUBLIC_KEY_HASH = "transactions.public_key_hash"
    PREV_PUBLIC_KEY_HASH = "transactions.prev_public_key_hash"


class KeyEventException(Exception):
    pass


class KeyEventPrerotatedKeyHashException(KeyEventException):
    pass


class KeyEventSingleOutputException(KeyEventException):
    pass


class MissingKeyEventParameterException(KeyEventException):
    pass


class FatalKeyEventException(Exception):
    def __init__(self, message, other_txn_to_delete=None):
        super().__init__(message)
        self.other_txn_to_delete = other_txn_to_delete


class DoesNotSpendEntirelyToPrerotatedKeyHashException(FatalKeyEventException):
    pass


class KeyEvent:
    def __init__(
        self,
        txn: Transaction = None,
        flag: KeyEventFlag = None,
        status: KeyEventChainStatus = None,
    ):
        if not txn or not isinstance(txn, Transaction):
            raise MissingKeyEventParameterException(
                "Transaction parameter is invalid or missing"
            )
        self.txn = txn
        self.flag = flag
        self.status = status
        self.config = Config()

    def verify_fields(self, prev_public_key_hash_required=False):
        if not Config().address_is_valid(self.txn.twice_prerotated_key_hash):
            raise KeyEventException("twice_prerotated_key_hash is not a valid hash")

        if not Config().address_is_valid(self.txn.prerotated_key_hash):
            raise KeyEventException("prerotated_key_hash is not a valid hash")

        if not Config().address_is_valid(self.txn.public_key_hash):
            raise KeyEventException("public_key_hash is not a valid hash")

        if prev_public_key_hash_required:  # optional for inception
            if not Config().address_is_valid(self.txn.prev_public_key_hash):
                raise KeyEventException("prev_public_key_hash is not a valid hash")

    def verify_inception(self, onchain=False):
        self.verify_fields(prev_public_key_hash_required=False)

        if len(self.txn.outputs) != 1:
            raise KeyEventSingleOutputException(
                f"{self.flag.value.upper()} key event should only have a single output"
            )
        if self.txn.outputs[0].to != self.txn.prerotated_key_hash:
            raise KeyEventPrerotatedKeyHashException(
                f"{self.flag.value.upper()} key event output should equal the prerotated_key_hash"
            )
        if self.txn.relationship != "":
            raise KeyEventTransactionRelationshipException(
                f"{self.flag.value.upper()} key event attempts to populate relationship field. This is not allowed."
            )

        if (onchain and self.status == KeyEventChainStatus.MEMPOOL) or (
            not onchain and self.status == KeyEventChainStatus.ONCHAIN
        ):
            raise KeyEventException("not a valid inception key event. Invalid status.")

    def verify_unconfirmed(self):
        self.verify_fields(prev_public_key_hash_required=True)
        if (
            not self.txn.relationship
            and len(self.txn.outputs) == 1
            and self.txn.outputs[0].to == self.txn.prerotated_key_hash
        ):
            raise KeyEventException(
                "not a valid unconfirmed key event. invalid relationship, outpus, or prerotated_key_hash."
            )

        if self.status != KeyEventChainStatus.MEMPOOL:
            raise KeyEventException(
                "not a valid unconfirmed key event. Invalid status."
            )

    def verify_confirming(self, onchain=False):
        self.verify_fields(prev_public_key_hash_required=True)

        if len(self.txn.outputs) != 1:
            raise KeyEventSingleOutputException(
                f"{self.flag.value.upper()} key event should only have a single output"
            )
        if self.txn.outputs[0].to != self.txn.prerotated_key_hash:
            raise KeyEventPrerotatedKeyHashException(
                f"{self.flag.value.upper()} key event output should equal the prerotated_key_hash"
            )
        if self.txn.relationship != "":
            raise KeyEventTransactionRelationshipException(
                f"{self.flag.value.upper()} key event attempts to populate relationship field. This is not allowed."
            )

        if (onchain and self.status == KeyEventChainStatus.MEMPOOL) or (
            not onchain and self.status == KeyEventChainStatus.ONCHAIN
        ):
            raise KeyEventException("not a valid confirming key event. Invalid status.")

    async def verify(self):
        address = str(
            P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.txn.public_key))
        )
        if address != self.txn.public_key_hash:
            raise PublicKeyMismatchException(
                "transaction public_key does not correspond to public_key_hash"
            )

        if await self.sends_to_past_kel_entry():
            await self.config.mongo.async_db.miner_transactions.delete_one(
                {"id": self.txn.transaction_signature}
            )
            raise KELException(
                "Unconfirmed key event sends to an expired key event. Removing."
            )

        if await self.txn.is_already_onchain():
            raise KELException("Key event is already onchain")

    async def sends_to_past_kel_entry(self):
        for output in self.txn.outputs:
            config = Config()
            result = config.mongo.async_db.blocks.aggregate(
                [
                    {
                        "$match": {
                            BlocksQueryFields.PUBLIC_KEY_HASH.value: output.to,
                        },
                    },
                    {"$unwind": "$transactions"},
                    {
                        "$match": {
                            BlocksQueryFields.PUBLIC_KEY_HASH.value: output.to,
                        },
                    },
                ]
            )
            res = await result.to_list(length=1)
            if res:
                txn = Transaction.from_dict(res[0]["transactions"])
                key_event = KeyEvent(
                    txn,
                    flag=(
                        KeyEventFlag.CONFIRMING
                        if txn.prev_public_key_hash
                        else KeyEventFlag.INCEPTION
                    ),
                    status=KeyEventChainStatus.ONCHAIN,
                )
                return key_event
        return False

    async def get_onchain_parent(self):
        config = Config()
        res = config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        "$or": [
                            {
                                BlocksQueryFields.TWICE_PREROTATED_KEY_HASH.value: self.txn.prerotated_key_hash,
                            },
                            {
                                BlocksQueryFields.PREROTATED_KEY_HASH.value: self.txn.public_key_hash,
                            },
                        ]
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        "$or": [
                            {
                                BlocksQueryFields.TWICE_PREROTATED_KEY_HASH.value: self.txn.prerotated_key_hash,
                            },
                            {
                                BlocksQueryFields.PREROTATED_KEY_HASH.value: self.txn.public_key_hash,
                            },
                        ]
                    }
                },
                {"$limit": 1},
            ]
        )
        result = await res.to_list(length=None)
        if result:
            txn = Transaction.from_dict(result[0]["transactions"])
            key_event = KeyEvent(
                txn,
                flag=(
                    KeyEventFlag.CONFIRMING
                    if txn.prev_public_key_hash
                    else KeyEventFlag.INCEPTION
                ),
                status=KeyEventChainStatus.ONCHAIN,
            )

            return {
                "key_event": key_event,
            }

    async def get_onchain_child(self):
        config = Config()
        res = config.mongo.async_db.blocks.aggregate(
            [
                {
                    "$match": {
                        BlocksQueryFields.PREROTATED_KEY_HASH.value: self.txn.twice_prerotated_key_hash,
                    }
                },
                {"$unwind": "$transactions"},
                {
                    "$match": {
                        BlocksQueryFields.PREROTATED_KEY_HASH.value: self.txn.twice_prerotated_key_hash,
                    }
                },
                {"$limit": 1},
            ]
        )
        result = await res.to_list(length=None)
        if result:
            txn = Transaction.from_dict(result[0]["transactions"])
            return KeyEvent(
                txn,
                flag=(
                    KeyEventFlag.CONFIRMING
                    if self.txn.prev_public_key_hash
                    else KeyEventFlag.INCEPTION
                ),
                status=KeyEventChainStatus.ONCHAIN,
            )


class KELHashCollectionException(Exception):
    pass


class KELHashCollection:
    @classmethod
    async def init_async(cls, block: "Block", verify_only=False):
        self = cls()
        self.config = Config()
        self.twice_prerotated_key_hashes = {}
        self.prerotated_key_hashes = {}
        self.public_key_hashes = {}
        self.prev_public_key_hashes = {}
        for transaction in block.transactions[:]:
            try:
                self.add(transaction)
            except KELHashCollectionException as e:
                if verify_only:
                    raise e
                self.config.app_log.info(f"Txn removed from block: {e}")
                block.transactions.remove(transaction)
                await self.config.mongo.async_db.miner_transactions.delete_one(
                    {"id": transaction.transaction_signature}
                )
        return self

    def add(self, transaction):
        if transaction.twice_prerotated_key_hash:
            if (
                transaction.twice_prerotated_key_hash
                in self.twice_prerotated_key_hashes
            ):
                raise KELHashCollectionException(
                    "Duplication key event in mempool. Removing."
                )
            self.twice_prerotated_key_hashes[
                transaction.twice_prerotated_key_hash
            ] = transaction

        if transaction.prerotated_key_hash:
            if transaction.prerotated_key_hash in self.prerotated_key_hashes:
                raise KELHashCollectionException(
                    "Duplication key event in mempool. Removing."
                )
            self.prerotated_key_hashes[transaction.prerotated_key_hash] = transaction

        if transaction.public_key_hash:
            if transaction.public_key_hash in self.public_key_hashes:
                raise KELHashCollectionException(
                    "Duplication key event in mempool. Removing."
                )
            self.public_key_hashes[transaction.public_key_hash] = transaction

        if transaction.prev_public_key_hash:
            if transaction.prev_public_key_hash in self.prev_public_key_hashes:
                raise KELHashCollectionException(
                    "Duplication key event in mempool. Removing."
                )
            self.prev_public_key_hashes[transaction.prev_public_key_hash] = transaction


class KeyEventLog:
    base_key_event: KeyEvent = None
    unconfirmed_key_event: KeyEvent = None
    confirming_key_event: KeyEvent = None

    @staticmethod
    async def init_async(
        key_event: KeyEvent = None, hash_collection: KELHashCollection = None
    ):
        self = KeyEventLog()
        self.config = Config()
        # step 1: if transaction is tracked on-chain in an existing key event log
        result = await key_event.get_onchain_parent()

        if result and result["key_event"]:
            # step 1.1: If found, check that this entry is the latest entry, if not, raise exception
            if await result["key_event"].get_onchain_child():
                raise FatalKeyEventException(
                    "key_event.txn has onchain parent that already has an onchain child.",
                    other_txn_to_delete=hash_collection.prerotated_key_hashes.get(  # get the confirming key event if present
                        key_event.txn.twice_prerotated_key_hash
                    ),
                )

            # check if public key hash and prev public key hash match
            if (
                result["key_event"].txn.public_key_hash
                != key_event.txn.prev_public_key_hash
            ):
                raise FatalKeyEventException(
                    "key_event.txn onchain parent public_key_hash does not equal key_event.txn.prev_public_key_hash",
                    other_txn_to_delete=hash_collection.prerotated_key_hashes.get(  # get the confirming key event if present
                        key_event.txn.twice_prerotated_key_hash
                    ),
                )

            # step 1.2: if not onchain child is found then check if it's confirming or unconfirmed

            # assign confirming key event and flag
            if (
                not key_event.txn.relationship
                and len(key_event.txn.outputs) == 1
                and key_event.txn.outputs[0].to == key_event.txn.prerotated_key_hash
                and key_event.txn.prev_public_key_hash
            ):
                key_event.flag = KeyEventFlag.CONFIRMING
                self.confirming_key_event = key_event

                # assign inception/onchain key event and flag
                self.base_key_event = result["key_event"]

            # assign unconfirmed key event and flag
            else:
                past_key_event = await key_event.sends_to_past_kel_entry()
                if past_key_event:
                    raise FatalKeyEventException(
                        "Unconfirmed key event sends to past key event.",
                        other_txn_to_delete=hash_collection.prerotated_key_hashes.get(  # get the confirming key event if present
                            key_event.txn.twice_prerotated_key_hash
                        ),
                    )

                key_event.flag = KeyEventFlag.UNCONFIRMED
                self.unconfirmed_key_event = key_event
                self.base_key_event = result["key_event"]

                # assign confirming key event and flag
                if (
                    key_event.txn.twice_prerotated_key_hash
                    in hash_collection.prerotated_key_hashes
                ):
                    self.confirming_key_event = KeyEvent(
                        hash_collection.prerotated_key_hashes[
                            key_event.txn.twice_prerotated_key_hash
                        ],
                        KeyEventFlag.CONFIRMING,
                        KeyEventChainStatus.MEMPOOL,
                    )
                else:
                    raise FatalKeyEventException(
                        "No confirming key event present in hash_collection.",
                        other_txn_to_delete=hash_collection.prerotated_key_hashes.get(  # get the confirming key event if present
                            key_event.txn.twice_prerotated_key_hash
                        ),
                    )

        # step 2: If onchain parent not found
        # Check within this hash_collection for an off-chain parent
        elif (
            key_event.txn.public_key_hash not in hash_collection.prerotated_key_hashes
            and key_event.txn.prerotated_key_hash
            not in hash_collection.twice_prerotated_key_hashes
            and key_event.txn.public_key_hash
            not in hash_collection.twice_prerotated_key_hashes
            and not key_event.txn.prev_public_key_hash
        ):
            # step 2.1 if parent is not found, this is an inception key event
            # assign inception key event and flag
            key_event.flag = KeyEventFlag.INCEPTION
            self.base_key_event = key_event
        else:
            # step 2.2 if parent is not found in blockchain, this should be a confirming key event
            # with an unconfirmed key event in the mempool as well
            if (
                key_event.txn.public_key_hash
                in hash_collection.twice_prerotated_key_hashes
            ):
                # if grand parent is in hash_collection, raise exception
                raise KELException(
                    "cannot have inception/previous confirming and newest confirming in same hash_collection."
                )

            if (
                key_event.txn.relationship
                or len(key_event.txn.outputs) != 1
                or key_event.txn.outputs[0].to != key_event.txn.prerotated_key_hash
            ):
                raise KELException("No onchain key event for unconfirmed key event.")

            # assign confirming key event and flag
            key_event.flag = KeyEventFlag.CONFIRMING
            self.confirming_key_event = key_event

            # assign unconfirmed key event and flag
            if (
                key_event.txn.prerotated_key_hash
                in hash_collection.twice_prerotated_key_hashes
            ):
                unconfirmed_key_event = KeyEvent(
                    hash_collection.twice_prerotated_key_hashes[
                        key_event.txn.prerotated_key_hash
                    ],
                    KeyEventFlag.UNCONFIRMED,
                    KeyEventChainStatus.MEMPOOL,
                )
            else:
                raise FatalKeyEventException(
                    "No unconfirmed key event present in hash_collection.",
                    other_txn_to_delete=hash_collection.twice_prerotated_key_hashes.get(  # get the confirming key event if present
                        key_event.txn.prerotated_key_hash
                    ),
                )

            # assign inception/onchain key event
            self.unconfirmed_key_event = unconfirmed_key_event
            result = await unconfirmed_key_event.get_onchain_parent()
            if result and result["key_event"]:
                self.base_key_event = result["key_event"]
            else:
                raise KELException("No onchain key event for unconfirmed key event.")

        # check that KEL is one of five scenarios.
        # 1. Inception
        if (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.INCEPTION
            and self.base_key_event.status == KeyEventChainStatus.MEMPOOL
            and not self.unconfirmed_key_event
            and not self.confirming_key_event
        ):
            self.base_key_event.verify_inception()

        # 2. Inception and confirming
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.INCEPTION
            and self.base_key_event.status == KeyEventChainStatus.ONCHAIN
            and not self.unconfirmed_key_event
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            # we don't need to check if the onchain key event is an inception or not.
            # If prev_hash has is not set, then it must be an inception which is enforced by rule 1
            self.base_key_event.verify_inception(onchain=True)
            self.confirming_key_event.verify_confirming()
            self.verify_links()

        # 3. onchain confirming and confirming
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.CONFIRMING
            and self.base_key_event.status == KeyEventChainStatus.ONCHAIN
            and not self.unconfirmed_key_event
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            self.base_key_event.verify_confirming(onchain=True)
            self.confirming_key_event.verify_confirming()
            self.verify_links()

        # 4. Inception, unconfirmed, and confirming
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.INCEPTION
            and self.base_key_event.status == KeyEventChainStatus.ONCHAIN
            and self.unconfirmed_key_event
            and self.unconfirmed_key_event.flag == KeyEventFlag.UNCONFIRMED
            and self.unconfirmed_key_event.status == KeyEventChainStatus.MEMPOOL
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            self.base_key_event.verify_inception(onchain=True)
            self.unconfirmed_key_event.verify_unconfirmed()
            self.confirming_key_event.verify_confirming()
            self.verify_links()

        # 5. Onchain confirming, unconfirmed, and confirming
        elif (
            self.base_key_event
            and self.base_key_event.flag == KeyEventFlag.CONFIRMING
            and self.base_key_event.status == KeyEventChainStatus.ONCHAIN
            and self.unconfirmed_key_event
            and self.unconfirmed_key_event.flag == KeyEventFlag.UNCONFIRMED
            and self.unconfirmed_key_event.status == KeyEventChainStatus.MEMPOOL
            and self.confirming_key_event
            and self.confirming_key_event.flag == KeyEventFlag.CONFIRMING
            and self.confirming_key_event.status == KeyEventChainStatus.MEMPOOL
        ):
            self.base_key_event.verify_confirming(onchain=True)
            self.unconfirmed_key_event.verify_unconfirmed()
            self.confirming_key_event.verify_confirming()
            self.verify_links()

        else:
            raise KELException("Invalid KEL scenario")
        return self

    def verify_links(self):
        if (
            self.base_key_event
            and self.unconfirmed_key_event
            and self.confirming_key_event
        ):
            self.verify_base_and_unconfirmed()
            self.verify_unconfirmed_and_confirming()
            return

        if self.base_key_event and self.confirming_key_event:
            self.verify_base_and_confirming()
            return

    def verify_base_and_unconfirmed(self):
        if (
            self.base_key_event.txn.twice_prerotated_key_hash
            != self.unconfirmed_key_event.txn.prerotated_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.twice_prerotated_key_hash does not match unconfirmed_key_event.txn.prerotated_key_hash"
            )
        if (
            self.base_key_event.txn.prerotated_key_hash
            != self.unconfirmed_key_event.txn.public_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.prerotated_key_hash does not match unconfirmed_key_event.txn.public_key_hash"
            )
        if (
            self.base_key_event.txn.public_key_hash
            != self.unconfirmed_key_event.txn.prev_public_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.public_key_hash does not match unconfirmed_key_event.txn.prev_public_key_hash"
            )

    def verify_unconfirmed_and_confirming(self):
        if (
            self.unconfirmed_key_event.txn.twice_prerotated_key_hash
            != self.confirming_key_event.txn.prerotated_key_hash
        ):
            raise KELException(
                "Mismatch: unconfirmed_key_event.txn.twice_prerotated_key_hash does not match confirming_key_event.txn.prerotated_key_hash"
            )
        if (
            self.unconfirmed_key_event.txn.prerotated_key_hash
            != self.confirming_key_event.txn.public_key_hash
        ):
            raise KELException(
                "Mismatch: unconfirmed_key_event.txn.prerotated_key_hash does not match confirming_key_event.txn.public_key_hash"
            )
        if (
            self.unconfirmed_key_event.txn.public_key_hash
            != self.confirming_key_event.txn.prev_public_key_hash
        ):
            raise KELException(
                "Mismatch: unconfirmed_key_event.txn.public_key_hash does not match confirming_key_event.txn.prev_public_key_hash"
            )

    def verify_base_and_confirming(self):
        if (
            self.base_key_event.txn.twice_prerotated_key_hash
            != self.confirming_key_event.txn.prerotated_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.twice_prerotated_key_hash does not match confirming_key_event.txn.prerotated_key_hash"
            )
        if (
            self.base_key_event.txn.prerotated_key_hash
            != self.confirming_key_event.txn.public_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.prerotated_key_hash does not match confirming_key_event.txn.public_key_hash"
            )
        if (
            self.base_key_event.txn.public_key_hash
            != self.confirming_key_event.txn.prev_public_key_hash
        ):
            raise KELException(
                "Mismatch: base_key_event.txn.public_key_hash does not match confirming_key_event.txn.prev_public_key_hash"
            )

    @staticmethod
    async def build_from_public_key(public_key):
        config = Config()
        log = []
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        inception = None
        while True:
            result = config.mongo.async_db.blocks.aggregate(
                [
                    {
                        "$match": {BlocksQueryFields.PUBLIC_KEY_HASH.value: address},
                    },
                    {
                        "$unwind": "$transactions",
                    },
                    {
                        "$match": {BlocksQueryFields.PUBLIC_KEY_HASH.value: address},
                    },
                ]
            )
            res = await result.to_list(length=1)
            if res:
                txn = Transaction.from_dict(res[0]["transactions"])
                if not txn.prev_public_key_hash:
                    inception = txn
                    break
                address = str(
                    P2PKHBitcoinAddress.from_pubkey(
                        bytes.fromhex(txn.prev_public_key_hash)
                    )
                )
            else:
                break
        if inception:
            log.append(inception)
            txn = inception
            while True:
                address = txn.prerotated_key_hash
                result = config.mongo.async_db.blocks.aggregate(
                    [
                        {
                            "$match": {
                                BlocksQueryFields.PUBLIC_KEY_HASH.value: address
                            },
                        },
                        {
                            "$unwind": "$transactions",
                        },
                        {
                            "$match": {
                                BlocksQueryFields.PUBLIC_KEY_HASH.value: address
                            },
                        },
                    ]
                )
                res = await result.to_list(length=1)
                if not res:
                    break

                txn = Transaction.from_dict(res[0]["transactions"])
                log.append(txn)
        return log
