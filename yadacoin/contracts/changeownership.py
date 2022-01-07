import base64
import time
import binascii
import base58
import hashlib
from enum import Enum
from bitcoin.signmessage import BitcoinMessage, VerifyMessage
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve.utils import verify_signature
from yadacoin.core.collections import Collections
from yadacoin.contracts.base import (
    Contract,
    ContractTypes,
    PayoutOperators,
    PayoutType
)
from yadacoin.core.asset import Asset
from yadacoin.core.identity import Identity, PrivateIdentity
from yadacoin.core.transaction import (
    InvalidTransactionException,
    InvalidTransactionSignatureException
)


class AssetProofTypes(Enum):
    COINBASE = 'coinbase'
    CONFIRMATION = 'confirmation'
    FIRST_COME = 'first_come'
    AUCTION = 'auction'


class ChangeOwnershipContract(Contract):

    def __init__(
        self,
        version,
        expiry,
        contract_type,
        payout_amount,
        payout_operator,
        payout_type,
        asset_proof_type,
        identity,
        creator,
        price,
        asset
    ):
        super().__init__(
            version,
            expiry,
            contract_type,
            asset_proof_type,
            identity,
            creator
        )

        if not isinstance(payout_amount, float) and not isinstance(payout_amount, int):
            self.report_init_error('payout_amount')

        if payout_operator not in [x.value for x in PayoutOperators]:
            self.report_init_error('payout_operator')

        if payout_type not in [x.value for x in PayoutType]:
            self.report_init_error('payout_type')

        if not asset or (not isinstance(asset, dict) and not isinstance(asset, str)):
            self.report_init_error('asset')

        if not isinstance(price, float) and not isinstance(price, int):
            self.report_init_error('price')

        if asset_proof_type not in [x.value for x in AssetProofTypes]:
            self.report_init_error('asset_proof_type')

        self.price = price
        self.asset = Asset.from_dict(asset) if isinstance(asset, dict) else asset

    @classmethod
    async def generate(
        cls,
        expiry=None,
        contract_type=None,
        payout_amount=None,
        payout_operator=None,
        payout_type=None,
        asset_proof_type=None,
        price=None,
        username=None,
        asset=None,
        creator=None
    ):
        identity = PrivateIdentity.generate(username)
        return cls(
            version=1,
            expiry=expiry or (time.time() + (60 * 60)),
            contract_type=contract_type or ContractTypes.CHANGE_OWNERSHIP.value,
            payout_amount=payout_amount or 1,
            payout_operator=payout_operator or PayoutOperators.FIXED,
            payout_type=payout_type or PayoutType.ONE_TIME.value,
            asset_proof_type=AssetProofTypes.CONFIRMATION.value,
            price=price or 1,
            identity=identity,
            asset=asset,
            creator=creator
        )

    async def process(self, contract_txn, trigger_txn, mempool_txns):
        from yadacoin.core.transaction import Transaction
        from yadacoin.core.transactionutils import TU

        await self.verify(contract_txn, trigger_txn, mempool_txns)

        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.identity.public_key)))
        return_address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(contract_txn.public_key)))

        bid = await getattr(self, f'get_{self.asset_proof_type}_bid')(contract_txn)
        value_sent_to_address = sum([x.value for x in bid.outputs if x.to == address])

        payout_txn = Transaction.from_dict({
            'value': value_sent_to_address,
            'inputs': [{'id': bid.transaction_signature}],
            'fee': 0,
            'outputs': [{'to': return_address, 'value': value_sent_to_address}],
            'time': int(time.time()),
            'public_key': self.identity.public_key,
            'requester_rid': contract_txn.requester_rid,
            'requested_rid': contract_txn.requested_rid,
            'rid': contract_txn.rid
        })
        payout_txn.hash = await payout_txn.generate_hash()
        payout_txn.transaction_signature = TU.generate_signature_with_private_key(
            binascii.hexlify(base58.b58decode(self.identity.wif))[2:-10].decode(),
            payout_txn.hash
        )
        payout_txn.miner_signature = TU.generate_signature_with_private_key(
            self.config.private_key,
            hashlib.sha256(payout_txn.transaction_signature).hexdigest().encode('utf-8')
        )
        return payout_txn

    async def verify_first_come(self, contract_txn, trigger_txn):
        await self.verify_input(trigger_txn)
        if not await self.get_first_come_bid(contract_txn):
            raise Exception('No bid matching the contract terms found')

    async def get_first_come_bid(self, contract_txn):
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.identity.public_key)))
        bids = self.get_funds(contract_txn)
        highest = 0
        selected_bid = None
        async for bid in bids:
            total_output_to_contract = sum([x.value for x in bid.outputs if x.to == address])

            if total_output_to_contract > highest:
                slected_bid = bid
                highest = total_output_to_contract
        return selected_bid

    async def verify_auction(self, contract_txn, trigger_txn):
        if self.expiry > self.config.LatestBlock.block.index:
            raise Exception('Expiry block height has not yet been reached.')

        if not await self.get_auction_bid(contract_txn):
            raise Exception('No winning bid for this auction')

    async def get_auction_bid(self, contract_txn):
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.identity.public_key)))
        bids = await self.get_funds(self, contract_txn)
        highest = 0
        selected_bid = None
        async for bid in bids:
            total_output_to_contract = sum([x.value for x in bid.outputs if x.to == address])

            if total_output_to_contract > highest:
                slected_bid = bid
        return selected_bid

    async def verify_confirmation(self, contract_txn, trigger_txn):
        if contract_txn.public_key != trigger_txn.public_key:
            raise Exception('Trigger transaction is not a confirmation by contract owner')

        if contract_txn.requested_rid != trigger_txn.requested_rid:
            raise Exception('requested_rid of confirmation transaction does not match that of the purchasing transaction')

        if not await self.get_confirmation_bid(contract_txn, trigger_txn):
            raise Exception('Confirmation transaction does not reference a transaction matching the terms of this contract')

    async def get_confirmation_bid(self, contract_txn, trigger_txn):
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.identity.public_key)))
        bids = await self.get_funds(self, contract_txn)
        async for bid in bids:
            if (
                trigger_txn.requested_rid == bid.requested_rid and
                trigger_txn.requester_rid == bid.requester_rid and
                trigger_txn.rid == bid.rid
            ):
                total_output_to_contract = sum([x.value for x in bid.outputs if x.to == address])

                if total_output_to_contract < self.price:
                    return bid

    def to_dict(self):
        return {
            Collections.SMART_CONTRACT.value: {
                'version': self.version,
                'expiry': self.expiry,
                'contract_type': self.contract_type,
                'payout_amount': self.payout_amount,
                'payout_operator': self.payout_operator,
                'payout_type': self.payout_type,
                'asset_proof_type': self.asset_proof_type,
                'price': self.price,
                'identity': self.identity.to_dict,
                'asset': self.asset.to_dict() if isinstance(self.asset, Asset) else self.asset,
                'creator': self.creator.to_dict if isinstance(self.creator, Identity) else self.creator
            }
        }

    def to_string(self):
        return (
            str(self.version) +
            str(self.expiry) +
            str(self.contract_type) +
            str(self.payout_amount) +
            str(self.payout_operator) +
            str(self.payout_type) +
            str(self.asset_proof_type) +
            str(self.price) +
            str(self.identity.username_signature) +
            str(self.asset.to_string() if isinstance(self.asset, Asset) else self.asset) +
            str(self.creator)
        )
