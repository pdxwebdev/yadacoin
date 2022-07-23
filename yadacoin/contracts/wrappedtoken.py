import base58
import binascii
import hashlib
import time
from enum import Enum
from bitcoin.wallet import CBitcoinSecret, P2PKHBitcoinAddress
from yadacoin.core.collections import Collections
from yadacoin.core.identity import Identity, PrivateIdentity
from base import Contract
from yadacoin.core.block import quantize_eight


class AssetProofTypes(Enum):
    TOKEN = 'token'


class WrappedTokenContract(Contract):

    def __init__(
        self,
        version,
        expiry,
        contract_type,
        identity,
        creator,
        proof_type,
        off_chain_dest_address
    ):
        super().__init__(
            version,
            expiry,
            contract_type,
            identity,
            creator
        )

        if proof_type not in [x.value for x in AssetProofTypes]:
            self.report_init_error('proof_type')

        if not isinstance(off_chain_dest_address, str):
            self.report_init_error('off_chain_dest_address')

        self.proof_type = proof_type
        self.off_chain_dest_address = off_chain_dest_address

    @classmethod
    async def generate(
        cls,
        expiry=None,
        contract_type=None,
        creator=None,
        username=None,
        proof_type=None,
        off_chain_dest_address=None
    ):
        identity = PrivateIdentity.generate(username)
        return cls(
            version=1,
            expiry=expiry,
            identity=identity,
            creator=creator,
            proof_type=AssetProofTypes.TOKEN.value,
            off_chain_dest_address=off_chain_dest_address
        )

    async def process(self, contract_txn, trigger_txn, mempool_txns):

        await self.verify(contract_txn, trigger_txn, mempool_txns)
        await self.verify_payout_generated_already(contract_txn, trigger_txn, mempool_txns)

        return await self.generate_transaction(contract_txn, trigger_txn)

    async def generate_transaction(self, contract_txn, trigger_txn):
        from yadacoin.core.transaction import Transaction, Input, Output
        from yadacoin.core.transactionutils import TU
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.identity.public_key)))
        return_address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(contract_txn.public_key)))
        value_sent_to_address = sum([x.value for x in trigger_txn.outputs if x.to == address])

        payout_txn = await Transaction.generate(
            value=value_sent_to_address,
            inputs=[Input(trigger_txn.transaction_signature)],
            fee=0,
            outputs=[Output(to=return_address, value=value_sent_to_address)],
            public_key=self.identity.public_key,
            requester_rid=trigger_txn.requester_rid,
            requested_rid=contract_txn.requested_rid,
            rid=trigger_txn.rid,
            contract_generated=True
        )

        payout_txn.hash = await payout_txn.generate_hash()
        payout_txn.transaction_signature = TU.generate_signature_with_private_key(
            binascii.hexlify(base58.b58decode(self.identity.wif))[2:-10].decode(),
            payout_txn.hash
        )
        payout_txn.miner_signature = TU.generate_signature_with_private_key(
            self.config.private_key,
            hashlib.sha256(payout_txn.transaction_signature.encode()).hexdigest()
        )
        return payout_txn

    async def verify_payout_generated_already(self, contract_txn, trigger_txn, mempool_txns):
        match = {
            'transactions.public_key': self.identity.public_key,
            'transactions.requester_rid': trigger_txn.requester_rid,
            'transactions.requested_rid': contract_txn.requested_rid,
            'transactions.rid': trigger_txn.rid
        }
        block_results = self.config.mongo.async_db.blocks.aggregate([
            {
                '$match': match
            },
            {
                '$unwind': '$transactions'
            },
            {
                '$match': match
            },
            {
                '$sort': {'index': -1, 'transactions.fee': -1, 'transactions.time': -1}
            }
        ])
        async for block_result in block_results:
            raise Exception('Contract already generated payout')

    async def expire_token(self, contract_txn):
        return None # wrapped tokens never expire

    def to_dict(self):
        return {
            Collections.SMART_CONTRACT.value: {
                'version': self.version,
                'expiry': self.expiry,
                'contract_type': self.contract_type,
                'identity': self.identity.to_dict,
                'creator': self.creator.to_dict if isinstance(self.creator, Identity) else self.creator,
                'proof_type': self.proof_type,
                'off_chain_dest_address': self.off_chain_dest_address
            }
        }

    def to_string(self):
        return (
            self.get_string(self.version) +
            self.get_string(self.expiry) +
            self.get_string(self.contract_type) +
            self.get_string(self.identity.username_signature) +
            self.get_string(self.creator) +
            self.get_string(self.proof_type) +
            self.get_string(self.off_chain_dest_address)
        )