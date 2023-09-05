import base64
import hashlib
import json
import time
from enum import Enum
from logging import getLogger
from traceback import format_exc

from bitcoin.signmessage import BitcoinMessage, VerifyMessage
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import verify_signature
from ecdsa import SECP256k1, VerifyingKey
from ecdsa.util import sigdecode_der

from yadacoin.core.chain import CHAIN
from yadacoin.core.collections import Collections
from yadacoin.core.config import get_config
from yadacoin.core.transactionutils import TU


def fix_float1(value):
    return ".".join(
        [
            "{0:.9f}".format(value).split(".")[0],
            "{0:.9f}".format(value).split(".")[1][:8],
        ]
    )


def fix_float2(value):
    return "{0:.8f}".format(value)


class TransactionAddressInvalidException(Exception):
    pass


class InvalidTransactionException(Exception):
    pass


class InvalidTransactionSignatureException(Exception):
    pass


class MissingInputTransactionException(Exception):
    pass


class NotEnoughMoneyException(Exception):
    pass


class MaxRelationshipSizeExceeded(Exception):
    pass


class TransactionInputOutputMismatchException(Exception):
    pass


class TotalValueMismatchException(Exception):
    pass


class InvalidRelationshipHashException(Exception):
    pass


class TransactionConsts(Enum):
    RELATIONSHIP_MAX_SIZE = 20480


class Transaction(object):
    def __init__(
        self,
        txn_time=0,
        rid="",
        transaction_signature="",
        relationship="",
        public_key="",
        dh_public_key="",
        fee=0.0,
        requester_rid="",
        requested_rid="",
        txn_hash="",
        inputs="",
        outputs="",
        coinbase=False,
        extra_blocks=None,
        seed_gateway_rid="",
        seed_rid="",
        version=None,
        miner_signature="",
        contract_generated=False,
        relationship_hash="",
        never_expire=False,
        private=False,
        masternode_fee=0.0,
        exact_match=False,
    ):
        self.app_log = getLogger("tornado.application")
        self.config = get_config()
        self.mongo = self.config.mongo
        if not txn_time:
            txn_time = 0
        self.time = txn_time if isinstance(txn_time, int) else int(txn_time)
        self.rid = rid
        self.transaction_signature = transaction_signature
        self.relationship = relationship
        self.relationship_hash = relationship_hash
        self.public_key = public_key
        self.dh_public_key = dh_public_key if dh_public_key else ""
        self.fee = float(fee)
        self.masternode_fee = float(masternode_fee)
        self.requester_rid = requester_rid if requester_rid else ""
        self.requested_rid = requested_rid if requested_rid else ""
        self.hash = txn_hash
        self.outputs = []
        self.extra_blocks = extra_blocks
        self.seed_gateway_rid = seed_gateway_rid
        self.seed_rid = seed_rid

        if version:
            self.version = version
        else:
            self.version = 1
            if self.time:
                self.version = 2

        if (
            isinstance(self.relationship, dict)
            and Collections.SMART_CONTRACT.value in self.relationship
        ):
            from yadacoin.contracts.base import Contract

            self.relationship = Contract.from_dict(
                self.relationship[Collections.SMART_CONTRACT.value]
            )

        for x in outputs:
            if not isinstance(x, Output):
                x = Output.from_dict(x)
            self.outputs.append(x)

        self.inputs = []
        for x in inputs:
            if not isinstance(x, Input):
                x = Input.from_dict(x)
            self.inputs.append(x)

        self.coinbase = coinbase
        self.miner_signature = miner_signature
        self.contract_generated = contract_generated
        self.never_expire = never_expire
        self.private = private
        self.exact_match = exact_match

    @classmethod
    async def generate(
        cls,
        username_signature="",
        username="",
        value=0,
        fee=0.0,
        rid="",
        requester_rid="",
        requested_rid="",
        public_key="",
        dh_public_key="",
        private_key="",
        dh_private_key="",
        to="",
        inputs="",
        outputs="",
        coinbase=False,
        chattext=None,
        signin=None,
        relationship="",
        no_relationship=False,
        exact_match=False,
        version=5,
        miner_signature="",
        contract_generated=False,
        do_money=True,
        never_expire=False,
        private=False,
        masternode_fee=0.0,
    ):
        cls_inst = cls()
        cls_inst.config = get_config()
        cls_inst.mongo = cls_inst.config.mongo
        cls_inst.app_log = getLogger("tornado.application")
        cls_inst.username_signature = username_signature
        cls_inst.username = username
        cls_inst.rid = rid
        cls_inst.requester_rid = requester_rid
        cls_inst.requested_rid = requested_rid
        cls_inst.public_key = public_key
        cls_inst.dh_public_key = dh_public_key
        cls_inst.private_key = private_key
        cls_inst.value = value
        cls_inst.fee = float(fee)
        cls_inst.masternode_fee = float(masternode_fee)
        cls_inst.dh_private_key = dh_private_key
        cls_inst.to = to
        cls_inst.time = int(time.time())
        cls_inst.outputs = []
        cls_inst.relationship = relationship
        cls_inst.relationship_hash = (
            (hashlib.sha256(relationship.encode()).digest().hex())
            if relationship
            else ""
        )
        cls_inst.no_relationship = no_relationship
        cls_inst.exact_match = exact_match
        cls_inst.version = version
        cls_inst.miner_signature = miner_signature

        for x in outputs:
            if isinstance(x, Output):
                out = x
            else:
                out = Output.from_dict(x)
            cls_inst.outputs.append(out)

        cls_inst.inputs = []
        for x in inputs:
            if isinstance(x, Input):
                inp = x
            else:
                inp = Input.from_dict(x)
            cls_inst.inputs.append(inp)

        cls_inst.coinbase = coinbase
        cls_inst.contract_generated = contract_generated

        await cls_inst.do_money()

        cls_inst.hash = await cls_inst.generate_hash()
        if cls_inst.private_key:
            cls_inst.transaction_signature = TU.generate_signature_with_private_key(
                private_key, cls_inst.hash
            )
        else:
            cls_inst.transaction_signature = ""

        cls_inst.never_expire = never_expire
        cls_inst.private = private
        return cls_inst

    async def get_mempool_transaction_ids(self):
        miner_transactions = self.mongo.async_db.miner_transactions.find(
            {"public_key": self.public_key}
        )
        async for mtxn in miner_transactions:
            for mtxninput in mtxn["inputs"]:
                yield mtxninput["id"]

    async def do_money(self):
        if self.coinbase:
            self.inputs = []
            return
        outputs_and_fee_total = sum([x.value for x in self.outputs]) + self.fee
        if outputs_and_fee_total == 0:
            return
        my_address = str(
            P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key))
        )

        mtxn_ids = self.get_mempool_transaction_ids()
        input_sum = 0
        inputs = []
        if self.inputs:
            input_sum = await self.evaluate_inputs(
                input_sum, my_address, inputs, outputs_and_fee_total
            )
        else:
            input_sum = await self.generate_inputs(
                input_sum,
                my_address,
                [x async for x in mtxn_ids],
                inputs,
                outputs_and_fee_total,
            )

        self.inputs = inputs

        if not self.inputs and not self.coinbase and outputs_and_fee_total > 0:
            raise NotEnoughMoneyException(
                "No inputs, not a coinbase, and transaction amount is greater than zero"
            )

        remainder = input_sum - outputs_and_fee_total
        if float(fix_float1(remainder)) == 0 and float(fix_float2(remainder)) == 0:
            remainder = 0.0

        found = False
        for x in self.outputs:
            if my_address == x.to:
                found = True
                x.value += remainder

        if not found:
            return_change_output = Output(to=my_address, value=remainder)
            self.outputs.append(return_change_output)

    async def evaluate_inputs(
        self, input_sum, my_address, inputs, outputs_and_fee_total
    ):
        async for y in self.get_inputs(self.inputs):
            txn = await self.config.BU.get_transaction_by_id(y.id, instance=True)
            if not txn:
                raise MissingInputTransactionException()

            address = my_address

            input_sum = await self.sum_inputs(
                y, txn, address, input_sum, inputs, outputs_and_fee_total
            )
            if input_sum >= outputs_and_fee_total:
                return input_sum

        raise NotEnoughMoneyException("not enough money")

    async def generate_inputs(
        self, input_sum, my_address, mtxn_ids, inputs, outputs_and_fee_total
    ):
        async for input_txn in self.config.BU.get_wallet_unspent_transactions(
            my_address, no_zeros=True, ids=mtxn_ids
        ):
            txn = await self.config.BU.get_transaction_by_id(
                input_txn.transaction_signature, instance=True
            )
            input_sum = await self.sum_inputs(
                Input.from_dict(txn.to_dict()),
                input_txn,
                my_address,
                input_sum,
                inputs,
                outputs_and_fee_total,
            )
            if input_sum >= outputs_and_fee_total:
                return input_sum

        raise NotEnoughMoneyException("not enough money")

    async def sum_inputs(
        self, input_obj, input_txn, my_address, input_sum, inputs, outputs_and_fee_total
    ):
        if isinstance(input_obj, ExternalInput):
            await input_txn.verify()
            address = str(
                P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(input_txn.public_key))
            )
        else:
            address = my_address

        for txn_output in input_txn.outputs:
            if txn_output.to == address and float(txn_output.value) > 0.0:
                fix1 = fix_float1(txn_output.value)
                fix2 = fix_float2(txn_output.value)
                fixtotal1 = fix_float1(outputs_and_fee_total)
                fixtotal2 = fix_float2(outputs_and_fee_total)
                if self.exact_match and fix1 != fixtotal1 and fix2 != fixtotal2:
                    continue
                input_sum += txn_output.value

                if input_txn not in inputs:
                    inputs.append(input_obj)

                if input_sum >= outputs_and_fee_total:
                    return input_sum
        return input_sum

    def generate_transaction_signature(self):
        return TU.generate_signature(self.hash, self.private_key)

    @classmethod
    def from_dict(cls, txn):
        return cls(
            txn_time=txn.get("time"),
            transaction_signature=txn.get("id"),
            rid=txn.get("rid", ""),
            relationship=txn.get("relationship", ""),
            public_key=txn.get("public_key"),
            dh_public_key=txn.get("dh_public_key"),
            fee=float(txn.get("fee")),
            requester_rid=txn.get("requester_rid", ""),
            requested_rid=txn.get("requested_rid", ""),
            txn_hash=txn.get("hash", ""),
            inputs=txn.get("inputs", []),
            outputs=txn.get("outputs", []),
            coinbase=txn.get("coinbase", False),
            version=txn.get("version"),
            miner_signature=txn.get("miner_signature", ""),
            contract_generated=txn.get("contract_generated", ""),
            relationship_hash=txn.get("relationship_hash", ""),
            private=txn.get("private", False),
            never_expire=txn.get("never_expire", False),
        )

    def in_the_future(self):
        """Tells whether the transaction is too far away in the future"""
        return int(self.time) > time.time() + CHAIN.TIME_TOLERANCE

    async def get_inputs(self, inputs):
        for x in inputs:
            yield x

    async def is_contract_generated(self):
        if await self.get_generating_contract():
            return True
        return False

    async def get_generating_contract(self):
        from yadacoin.contracts.base import Contract

        smart_contract_txn_block = await self.config.mongo.async_db.blocks.find_one(
            {
                "transactions.relationship.smart_contract.identity.public_key": self.public_key
            },
            sort=[("time", 1)],
        )
        if not smart_contract_txn_block:
            return
        for txn in smart_contract_txn_block.get("transactions"):
            txn_obj = Transaction.from_dict(txn)
            if (
                isinstance(txn_obj.relationship, Contract)
                and txn_obj.relationship.identity.public_key == self.public_key
            ):
                return txn_obj

    @staticmethod
    def ensure_instance(txn):
        if isinstance(txn, Transaction):
            return txn
        else:
            return Transaction.from_dict(txn)

    @staticmethod
    async def handle_exception(e, txn):
        config = get_config()
        await config.mongo.async_db.failed_transactions.insert_one(
            {
                "reason": f"{e.__class__.__name__}",
                "txn": txn.to_dict(),
                "error": format_exc(),
            }
        )
        await config.mongo.async_db.miner_transactions.delete_many(
            {"id": txn.transaction_signature}
        )
        config.app_log.warning("Exception {}".format(e))

    async def verify(self):
        from yadacoin.contracts.base import Contract

        verify_hash = await self.generate_hash()
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))

        if verify_hash != self.hash:
            raise InvalidTransactionException("transaction is invalid")

        try:
            result = verify_signature(
                base64.b64decode(self.transaction_signature),
                self.hash.encode("utf-8"),
                bytes.fromhex(self.public_key),
            )
            if not result:
                print("t verify1")
                raise Exception()
        except:
            try:
                vk = VerifyingKey.from_string(
                    bytes.fromhex(self.public_key), curve=SECP256k1
                )
                result = vk.verify(
                    base64.b64decode(self.transaction_signature),
                    self.hash.encode(),
                    hashlib.sha256,
                    sigdecode=sigdecode_der,
                )
                if not result:
                    print("t verify2")
                    raise Exception()
            except:
                try:
                    result = VerifyMessage(
                        address,
                        BitcoinMessage(self.hash, magic=""),
                        self.transaction_signature,
                    )
                    if not result:
                        print("t verify3")
                        raise
                except:
                    print("t verify3")
                    raise InvalidTransactionSignatureException(
                        "transaction signature did not verify"
                    )

        relationship = self.relationship
        if isinstance(self.relationship, Contract):
            relationship = self.relationship.to_string()

        if len(relationship) > TransactionConsts.RELATIONSHIP_MAX_SIZE.value:
            raise MaxRelationshipSizeExceeded(
                f"Relationship field cannot be greater than {TransactionConsts.RELATIONSHIP_MAX_SIZE.value} bytes"
            )

        # verify spend
        total_input = 0
        exclude_recovered_ids = []
        async for txn in self.get_inputs(self.inputs):
            txn_input = None
            input_txn = await self.config.BU.get_transaction_by_id(txn.id)

            if input_txn:
                txn_input = Transaction.from_dict(input_txn)

            if not input_txn:
                if self.extra_blocks:
                    txn_input = await self.find_in_extra_blocks(txn)
                if not txn_input:
                    result = await self.recover_missing_transaction(
                        txn.id, exclude_recovered_ids
                    )
                    exclude_recovered_ids.append(exclude_recovered_ids)
                    raise MissingInputTransactionException(
                        "Input not found on blockchain: {}".format(txn.id)
                    )

            found = False
            for output in txn_input.outputs:
                if isinstance(txn, ExternalInput):
                    ext_address = P2PKHBitcoinAddress.from_pubkey(
                        bytes.fromhex(txn_input.public_key)
                    )
                    int_address = P2PKHBitcoinAddress.from_pubkey(
                        bytes.fromhex(txn.public_key)
                    )
                    if str(output.to) == str(ext_address) and str(int_address) == str(
                        txn.address
                    ):
                        try:
                            result = verify_signature(
                                base64.b64decode(txn.signature),
                                txn.id.encode("utf-8"),
                                bytes.fromhex(txn_input.public_key),
                            )
                            if not result:
                                print("t verify4")
                                raise Exception()
                        except:
                            try:
                                result = VerifyMessage(
                                    ext_address,
                                    BitcoinMessage(txn.id, magic=""),
                                    txn.signature,
                                )
                                if not result:
                                    print("t verify5")
                                    raise
                            except:
                                raise InvalidTransactionSignatureException(
                                    "external input transaction signature did not verify"
                                )

                        found = True
                        total_input += float(output.value)
                elif str(output.to) == str(address):
                    found = True
                    total_input += float(output.value)

            if not found:
                if isinstance(txn, ExternalInput):
                    raise InvalidTransactionException(
                        "external input signing information did not match any recipients of the input transaction"
                    )
                else:
                    raise InvalidTransactionException(
                        "using inputs from a transaction where you were not one of the recipients."
                    )

        if self.coinbase or self.miner_signature:
            return

        total_output = 0
        for txn in self.outputs:
            total_output += float(txn.value)

        total = float(total_output) + float(self.fee)
        if fix_float1(total_input) != fix_float1(total) and fix_float2(
            total_input
        ) != fix_float2(total):
            raise TotalValueMismatchException(
                "inputs and outputs sum must match %s, %s, %s, %s"
                % (total_input, float(total_output), float(self.fee), total)
            )

    async def generate_hash(self):
        from yadacoin.contracts.base import Contract

        inputs_concat = await self.get_input_hashes()
        outputs_concat = self.get_output_hashes()
        if isinstance(self.relationship, Contract):
            relationship = self.relationship.to_string()
        else:
            relationship = self.relationship
        if self.version == 5:
            if relationship:
                relationship_hash = hashlib.sha256(relationship.encode()).digest().hex()
                if relationship_hash != self.relationship_hash:
                    raise InvalidRelationshipHashException()
            else:
                relationship_hash = self.relationship_hash
            hashout = (
                hashlib.sha256(
                    (
                        self.public_key
                        + str(self.time)
                        + self.dh_public_key
                        + self.rid
                        + relationship_hash
                        + "{0:.8f}".format(self.fee)
                        + "{0:.8f}".format(self.masternode_fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                        + str(self.version)
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        elif self.version == 4:
            if relationship:
                relationship_hash = hashlib.sha256(relationship.encode()).digest().hex()
                if relationship_hash != self.relationship_hash:
                    raise InvalidRelationshipHashException()
            else:
                relationship_hash = self.relationship_hash
            hashout = (
                hashlib.sha256(
                    (
                        self.public_key
                        + str(self.time)
                        + self.dh_public_key
                        + self.rid
                        + relationship_hash
                        + "{0:.8f}".format(self.fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                        + str(self.version)
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        elif self.version == 3:
            hashout = (
                hashlib.sha256(
                    (
                        self.public_key
                        + str(self.time)
                        + self.dh_public_key
                        + self.rid
                        + relationship
                        + "{0:.8f}".format(self.fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                        + str(self.version)
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        elif self.version == 2:
            hashout = (
                hashlib.sha256(
                    (
                        self.public_key
                        + str(self.time)
                        + self.dh_public_key
                        + self.rid
                        + relationship
                        + "{0:.8f}".format(self.fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        else:
            hashout = (
                hashlib.sha256(
                    (
                        self.dh_public_key
                        + self.rid
                        + self.relationship
                        + "{0:.8f}".format(self.fee)
                        + self.requester_rid
                        + self.requested_rid
                        + inputs_concat
                        + outputs_concat
                    ).encode("utf-8")
                )
                .digest()
                .hex()
            )
        return hashout

    async def get_input_hashes(self):
        return "".join(
            sorted(
                [x.id async for x in self.get_inputs(self.inputs)],
                key=lambda v: v.lower(),
            )
        )

    async def find_in_extra_blocks(self, txn_input):
        for block in self.extra_blocks:
            for xtxn in block.transactions:
                if xtxn.transaction_signature == txn_input.id:
                    return xtxn

    def get_output_hashes(self):
        outputs_sorted = sorted(
            [x.to_dict() for x in self.outputs], key=lambda x: x["to"].lower()
        )
        return "".join([x["to"] + "{0:.8f}".format(x["value"]) for x in outputs_sorted])

    async def get_coinbase_origin(self, txn_input):
        from yadacoin.core.block import Block

        blocks = await self.config.mongo.async_db.blocks.find(
            {"transactions.id": txn_input.id}
        )
        async for b in blocks:
            b = await Block.from_dict(b)
            cb = b.get_coinbase()
            if cb.id == txn_input.id:
                return cb

    async def recover_missing_transaction(self, txn_id, exclude_ids=[]):
        return False
        if await self.config.mongo.async_db.failed_recoveries.find_one(
            {"txn_id": txn_id}
        ):
            return False
        self.app_log.warning("recovering missing transaction input: {}".format(txn_id))
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.public_key)))
        missing_txns = self.config.mongo.async_db.blocks.aggregate(
            [
                {"$unwind": "$transactions"},
                {"$project": {"transaction": "$transactions", "index": "$index"}},
            ],
            allowDiskUse=True,
        )
        async for missing_txn in missing_txns:
            self.app_log.warning(
                "recovery searching block index: {}".format(missing_txn["index"])
            )
            try:
                result = verify_signature(
                    base64.b64decode(txn_id),
                    missing_txn["transaction"]["hash"].encode(),
                    bytes.fromhex(self.public_key),
                )
                if result:
                    block_index = await self.find_unspent_missing_index(
                        missing_txn["transaction"]["hash"], exclude_ids
                    )
                    if block_index:
                        await self.replace_missing_transaction_input(
                            block_index, missing_txn["transaction"]["hash"], txn_id
                        )
                        return True
                else:
                    if len(base64.b64decode(txn_id)) != 65:
                        continue
                    result = VerifyMessage(
                        address,
                        BitcoinMessage(missing_txn["transaction"]["hash"], magic=""),
                        txn_id,
                    )
                    if result:
                        block_index = await self.find_unspent_missing_index(
                            missing_txn["transaction"]["hash"], exclude_ids
                        )
                        if block_index:
                            await self.replace_missing_transaction_input(
                                block_index, missing_txn["transaction"]["hash"], txn_id
                            )
                            return True
            except:
                continue
        await self.config.mongo.async_db.failed_recoveries.update_one(
            {"txn_id": txn_id}, {"$set": {"txn_id": txn_id}}, upsert=True
        )
        return False

    async def replace_missing_transaction_input(self, block_index, txn_hash, txn_id):
        block_to_replace = await self.config.mongo.async_db.blocks.find_one(
            {"index": block_index}
        )

        async def get_txns(txns):
            for txn in txns:
                yield txn

        async for txn in get_txns(block_to_replace["transactions"]):
            if txn["hash"] == txn_hash:
                txn["id"] = txn_id
                self.app_log.warning(
                    "missing transaction input id updated: {}".format(block_index)
                )
                break
        await self.config.mongo.async_db.blocks.replace_one(
            {"index": block_index}, block_to_replace
        )
        self.app_log.warning(
            "missing transaction input recovery successful: {}".format(txn_hash)
        )
        return True

    async def find_unspent_missing_index(self, txn_hash, exclude_ids=[]):
        blocks = self.config.mongo.async_db.blocks.find({"transactions.hash": txn_hash})

        async def get_txns(txns):
            for txn in txns:
                yield txn

        async for block in blocks:
            async for txn in get_txns(block["transactions"]):
                if txn["hash"] == txn_hash and txn["id"] not in exclude_ids:
                    spents = self.config.mongo.async_db.blocks.aggregate(
                        [
                            {
                                "$match": {
                                    "transactions.inputs.id": txn["id"],
                                    "transactions.public_key": self.public_key,
                                }
                            },
                            {"$unwind": "$transactions"},
                            {
                                "$match": {
                                    "transactions.inputs.id": txn["id"],
                                    "transactions.public_key": self.public_key,
                                }
                            },
                        ]
                    )
                    found = False
                    async for spent in spents:
                        found = True
                        break
                    if not found:
                        return block["index"]

    def to_dict(self):
        relationship = self.relationship
        if hasattr(relationship, "to_dict"):
            relationship = relationship.to_dict()
        ret = {
            "time": int(self.time),
            "rid": self.rid,
            "id": self.transaction_signature,  # Beware: changing name between object/dict view is very error prone
            "relationship": relationship,
            "relationship_hash": self.relationship_hash,
            "public_key": self.public_key,
            "dh_public_key": self.dh_public_key,
            "fee": float(self.fee),
            "masternode_fee": float(self.masternode_fee),
            "hash": self.hash,
            "inputs": [x.to_dict() for x in self.inputs],
            "outputs": [x.to_dict() for x in self.outputs],
            "version": self.version,
            "private": self.private,
            "never_expire": self.never_expire,
        }
        if self.dh_public_key:
            ret["dh_public_key"] = self.dh_public_key
        if self.requester_rid:
            ret["requester_rid"] = self.requester_rid
        if self.requested_rid:
            ret["requested_rid"] = self.requested_rid
        if self.miner_signature:
            ret["miner_signature"] = self.miner_signature
        return ret

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)


class Input(object):
    def __init__(self, signature):
        self.id = signature

    @classmethod
    def from_dict(cls, txn):
        return cls(
            signature=txn.get("id", ""),
        )

    def to_dict(self):
        return {"id": self.id}


class ExternalInput(Input):
    def __init__(self, public_key, address, txn_id, signature):
        # TODO: error, superclass init missing
        self.config = get_config()
        self.mongo = self.config.mongo
        self.public_key = public_key
        self.id = txn_id
        self.signature = signature
        self.address = address

    async def verify(self):
        txn = await self.config.BU.get_transaction_by_id(self.id, instance=True)
        result = verify_signature(
            base64.b64decode(self.signature),
            self.id.encode("utf-8"),
            bytes.fromhex(txn.public_key),
        )
        if not result:
            raise Exception("Invalid external input")

    @classmethod
    def from_dict(cls, txn):
        # TODO: sig doees not match
        return cls(
            public_key=txn.get("public_key", ""),
            address=txn.get("address", ""),
            txn_id=txn.get("id", ""),
            signature=txn.get("signature", ""),
        )

    def to_dict(self):
        return {
            "public_key": self.public_key,
            "address": self.address,
            "id": self.id,
            "signature": self.signature,
        }


class Output(object):
    def __init__(self, to, value):
        self.to = to
        self.value = value

    @classmethod
    def from_dict(cls, txn):
        return cls(to=txn.get("to", ""), value=txn.get("value", ""))

    def to_dict(self):
        return {"to": self.to, "value": self.value}


class Relationship(object):
    def __init__(
        self,
        dh_private_key=None,
        their_username_signature=None,
        their_username=None,
        my_username_signature=None,
        my_username=None,
        their_public_key=None,
        their_address=None,
        group=None,
        reply=None,
        topic=None,
        my_public_key=None,
    ):
        self.dh_private_key = dh_private_key
        self.their_username_signature = their_username_signature
        self.their_username = their_username
        self.my_username_signature = my_username_signature
        self.my_username = my_username
        self.their_public_key = their_public_key
        self.their_address = their_address
        self.group = group
        self.reply = reply
        self.topic = topic
        self.my_public_key = my_public_key

    def to_dict(self):
        return {
            "dh_private_key": self.dh_private_key,
            "their_username_signature": self.their_username_signature,
            "their_username": self.their_username,
            "my_username_signature": self.my_username_signature,
            "my_username": self.my_username,
            "their_public_key": self.their_public_key,
            "their_address": self.their_address,
            "group": self.group,
            "reply": self.reply,
            "topic": self.topic,
            "my_public_key": self.my_public_key,
        }

    def to_json(self):
        return json.dumps(self.to_dict())
