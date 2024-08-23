import base64
import hashlib
from enum import Enum

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve.utils import verify_signature

from yadacoin.core.collections import Collections
from yadacoin.core.config import Config
from yadacoin.core.identity import Identity, PrivateIdentity
from yadacoin.core.transaction import (
    InvalidTransactionException,
    InvalidTransactionSignatureException,
    Transaction,
)


class PayoutOperators(Enum):
    PERCENT = "percent"
    FIXED = "fixed"


class PayoutType(Enum):
    RECURRING = "recurring"
    ONE_TIME = "one_time"


class ContractTypes(Enum):
    CHANGE_OWNERSHIP = "change_ownership"
    NEW_RELATIONSHIP = "new_relationship"


class Contract:
    def __init__(self, version, expiry, contract_type, identity, creator):
        self.config = Config()

        if not isinstance(version, int):
            self.report_init_error("version")

        if not isinstance(expiry, int):
            self.report_init_error("expiry")

        if contract_type not in [x.value for x in ContractTypes]:
            self.report_init_error("contract_type")

        if not creator or (
            not isinstance(creator, dict) and not isinstance(creator, str)
        ):
            self.report_init_error("creator")

        self.version = version
        self.expiry = expiry
        self.contract_type = contract_type
        self.identity = PrivateIdentity.from_dict(identity)
        self.creator = (
            Identity.from_dict(creator) if isinstance(creator, dict) else creator
        )

    def get_string(self, p):
        return "" if p is None else str(p)

    def report_init_error(self, member):
        raise Exception(f"Cannot instantiate contract with invalid {member}")

    @staticmethod
    def from_dict(contract):
        from yadacoin.contracts.affiliate import AffiliateContract
        from yadacoin.contracts.changeownership import ChangeOwnershipContract

        cls = None
        if contract.get("contract_type") == ContractTypes.NEW_RELATIONSHIP.value:
            cls = AffiliateContract
        elif contract.get("contract_type") == ContractTypes.CHANGE_OWNERSHIP.value:
            cls = ChangeOwnershipContract

        return cls(**contract)

    async def verify_input(self, trigger_txn):
        if await self.config.BU.is_input_spent(
            trigger_txn.transaction_signature,
            self.identity.public_key,
            inc_mempool=True,
        ):
            raise Exception("input is already spent by contract")

    async def verify(self, contract_txn, trigger_txn=None, mempool_txns=None):
        await getattr(self, f"verify_{self.proof_type}")(contract_txn, trigger_txn)

    async def verify_generation(self, block, generated_txn=None, mempool_txns=None):
        contract_txn = await generated_txn.get_generating_contract()
        if not contract_txn:
            raise Exception("Could not find corresponding smart contract")

        verify_hash = await generated_txn.generate_hash()

        if verify_hash != generated_txn.hash:
            raise InvalidTransactionException("transaction is invalid")

        try:
            result = verify_signature(
                base64.b64decode(generated_txn.miner_signature),
                hashlib.sha256(generated_txn.transaction_signature.encode())
                .hexdigest()
                .encode("utf-8"),
                bytes.fromhex(block.public_key),
            )
            if not result:
                raise Exception("Payout miner signature did not verify")
        except:
            raise InvalidTransactionSignatureException(
                "Payout miner signature did not verify"
            )

        if generated_txn.requested_rid != contract_txn.requested_rid:
            raise Exception("requested_rid does not match that of smart contract")

        await getattr(self, f"verify_{self.proof_type}")(contract_txn, generated_txn)

    async def get_funds(self, contract_txn):
        address = str(
            P2PKHBitcoinAddress.from_pubkey(
                bytes.fromhex(contract_txn.relationship.identity.public_key)
            )
        )
        async for txn in self.config.BU.get_wallet_unspent_transactions_for_spending(
            address
        ):
            yield Transaction.from_dict(txn)

    @staticmethod
    async def get_smart_contract(transaction_obj):
        smart_contract_block = await Config().mongo.async_db.blocks.find_one(
            {
                "transactions.requested_rid": transaction_obj.requested_rid,
                "transactions": {
                    "$elemMatch": {"relationship.smart_contract": {"$exists": True}}
                },
                "transactions": {
                    "$elemMatch": {"id": {"$ne": transaction_obj.transaction_signature}}
                },
                "transactions": {
                    "$elemMatch": {
                        "relationship.smart_contract.expiry": {
                            "$gt": Config().LatestBlock.block.index
                        }
                    }
                },
            },
            sort=[("index", 1)],
        )
        if not smart_contract_block:
            return
        for smart_contract in smart_contract_block.get("transactions"):
            if (
                smart_contract.get("relationship")
                and isinstance(smart_contract.get("relationship"), dict)
                and Collections.SMART_CONTRACT.value in smart_contract["relationship"]
            ):
                smart_contract_obj = Transaction.from_dict(smart_contract)
                return smart_contract_obj

    async def expire(self, contract_txn):
        return await getattr(self, f"expire_{self.proof_type}")(contract_txn)
