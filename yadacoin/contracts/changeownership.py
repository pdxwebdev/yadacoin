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
from yadacoin.contracts.asset import Asset
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
        market,
        proof_type,
        identity,
        creator,
        price,
        asset
    ):
        super().__init__(
            version,
            expiry,
            contract_type,
            identity,
            creator
        )

        if not isinstance(payout_amount, float) and not isinstance(payout_amount, int):
            self.report_init_error('payout_amount')

        if payout_operator not in [x.value for x in PayoutOperators]:
            self.report_init_error('payout_operator')

        if payout_type not in [x.value for x in PayoutType]:
            self.report_init_error('payout_type')

        if not market or not isinstance(market, str):
            self.report_init_error('market')

        if not asset or (not isinstance(asset, dict) and not isinstance(asset, str)):
            self.report_init_error('asset')

        if not isinstance(price, float) and not isinstance(price, int):
            self.report_init_error('price')

        if proof_type not in [x.value for x in AssetProofTypes]:
            self.report_init_error('proof_type')

        self.payout_amount = payout_amount
        self.payout_operator = payout_operator
        self.payout_type = payout_type
        self.market = market
        self.asset = Asset.from_dict(asset) if isinstance(asset, dict) else asset
        self.price = price
        self.proof_type = proof_type

    @classmethod
    async def generate(
        cls,
        expiry=None,
        contract_type=None,
        payout_amount=None,
        payout_operator=None,
        payout_type=None,
        market=None,
        proof_type=None,
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
            market=market,
            proof_type=AssetProofTypes.CONFIRMATION.value,
            price=price or 1,
            identity=identity,
            asset=asset,
            creator=creator
        )

    async def process(self, contract_txn, trigger_txn, mempool_txns):
        from yadacoin.core.transaction import Transaction
        from yadacoin.core.transactionutils import TU

        await self.verify(contract_txn, trigger_txn, mempool_txns)
        await self.verify_payout_generated_already(contract_txn, trigger_txn)

        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.identity.public_key)))
        return_address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(contract_txn.public_key)))

        if self.proof_type in [AssetProofTypes.CONFIRMATION.value, AssetProofTypes.AUCTION.value]:
            bid = await getattr(self, f'get_{self.proof_type}_bid')(contract_txn)
        elif self.proof_type == AssetProofTypes.FIRST_COME.value:
            bid = trigger_txn

        value_sent_to_address = sum([x.value for x in bid.outputs if x.to == address])

        payout_txn = Transaction.from_dict({
            'value': value_sent_to_address,
            'inputs': [{'id': bid.transaction_signature}],
            'fee': 0,
            'outputs': [{'to': return_address, 'value': value_sent_to_address}],
            'time': int(time.time()),
            'public_key': self.identity.public_key,
            'requester_rid': trigger_txn.requester_rid,
            'requested_rid': contract_txn.requested_rid,
            'rid': trigger_txn.rid,
            'contract_generated': True
        })

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

    async def verify_payout_generated_already(self, contract_txn, trigger_txn):
        block_result = await self.config.mongo.async_db.blocks.find_one({
          'transactions.public_key': self.identity.public_key,
          'transactions.requester_rid': trigger_txn.requester_rid,
          'transactions.requested_rid': contract_txn.requested_rid,
          'transactions.rid': trigger_txn.rid
        })
        if block_result:
            raise Exception('Contract already generated payout')

    async def verify_first_come(self, contract_txn, trigger_txn):
        await self.verify_input(trigger_txn)

    async def get_first_come_bid(self, contract_txn):
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.identity.public_key)))
        bids = self.get_funds(contract_txn)
        highest = 0
        selected_bid = None
        async for bid in bids:
            total_output_to_contract = sum([x.value for x in bid.outputs if x.to == address])

            if total_output_to_contract > highest:
                selected_bid = bid
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

    async def expire_first_come(self, contract_txn):
        from yadacoin.core.transaction import Transaction, Output
        from yadacoin.core.transactionutils import TU
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(contract_txn.public_key)))
        balance = await self.config.BU.get_wallet_balance(str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.identity.public_key))))
        if not float(balance):
            return
        payout_txn = await Transaction.generate(
            fee=0,
            outputs=[Output(
                to=address,
                value=balance
            )],
            public_key=self.identity.public_key,
            requester_rid=contract_txn.requester_rid,
            requested_rid=contract_txn.requested_rid,
            rid=contract_txn.rid,
            private_key=binascii.hexlify(base58.b58decode(self.identity.wif))[2:-10].decode()
        )
        payout_txn.miner_signature = TU.generate_signature_with_private_key(
            self.config.private_key,
            hashlib.sha256(payout_txn.transaction_signature.encode()).hexdigest()
        )
        return payout_txn

    async def expire_auction(self, contract_txn):
        from yadacoin.core.transaction import Transaction, Output, Input
        from yadacoin.core.transactionutils import TU

        purchase_txn = await self.get_purchase_txn(contract_txn)
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(contract_txn.public_key)))
        payout = await self.get_amount(contract_txn, purchase_txn)
        payout_txn = await Transaction.generate(
            fee=0,
            outputs=[Output(
                to=address,
                value=payout
            )],
            inputs=[Input(
                purchase_txn.transaction_signature
            )],
            public_key=self.identity.public_key,
            requester_rid=contract_txn.requester_rid,
            requested_rid=contract_txn.requested_rid,
            rid=contract_txn.rid,
            private_key=binascii.hexlify(base58.b58decode(self.identity.wif))[2:-10].decode()
        )
        payout_txn.miner_signature = TU.generate_signature_with_private_key(
            self.config.private_key,
            hashlib.sha256(payout_txn.transaction_signature.encode()).hexdigest()
        )
        return payout_txn

    async def get_purchase_txn(self, contract_txn):
        from yadacoin.core.transaction import Transaction, Output
        purchase_txn_blocks = self.config.mongo.async_db.blocks.aggregate([
            {
                '$match': {
                    'transactions.requested_rid': contract_txn.requested_rid,
                    'transactions': {'$elemMatch': {'id': {'$ne': contract_txn.transaction_signature}}}
                }
            },
            {
                '$unwind': '$transactions'
            },
            {
                '$match': {
                    'transactions.requested_rid': contract_txn.requested_rid,
                    'transactions.id': {'$ne': contract_txn.transaction_signature}
                }
            }
        ])
        highest_amount = 0
        winning_purchase_txn = None
        async for purchase_txn_block in purchase_txn_blocks:
            purchase_txn_obj = Transaction.from_dict(purchase_txn_block.get('transactions'))
            purchase_amount = await self.get_amount(contract_txn, purchase_txn_obj)
            if purchase_amount > highest_amount:
                winning_purchase_txn = purchase_txn_obj
        return winning_purchase_txn

    async def get_amount(self, smart_contract_obj, purchase_txn_obj):
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(smart_contract_obj.relationship.identity.public_key)))
        amount = 0
        for output in purchase_txn_obj.outputs:
            if output.to == address:
                amount += output.value
        return amount

    def to_dict(self):
        return {
            Collections.SMART_CONTRACT.value: {
                'version': self.version,
                'expiry': self.expiry,
                'contract_type': self.contract_type,
                'payout_amount': self.payout_amount,
                'payout_operator': self.payout_operator,
                'payout_type': self.payout_type,
                'market': self.market,
                'proof_type': self.proof_type,
                'price': self.price,
                'identity': self.identity.to_dict,
                'asset': self.asset.to_dict() if isinstance(self.asset, Asset) else self.asset,
                'creator': self.creator.to_dict if isinstance(self.creator, Identity) else self.creator
            }
        }

    def to_string(self):
        return (
            self.get_string(self.version) +
            self.get_string(self.expiry) +
            self.get_string(self.contract_type) +
            self.get_string(self.payout_amount) +
            self.get_string(self.payout_operator) +
            self.get_string(self.payout_type) +
            self.get_string(self.market) +
            self.get_string(self.proof_type) +
            self.get_string(self.price) +
            self.get_string(self.identity.username_signature) +
            self.get_string(self.asset.to_self.get_stringing() if isinstance(self.asset, Asset) else self.asset) +
            self.get_string(self.creator)
        )
