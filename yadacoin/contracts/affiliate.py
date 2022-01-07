import base64
import time
import binascii
import base58
import hashlib
from enum import Enum
from bitcoin.signmessage import BitcoinMessage, VerifyMessage
from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve.utils import verify_signature

from yadacoin.contracts.base import (
    Contract,
    ContractTypes,
    PayoutOperators,
    PayoutType
)
from yadacoin.core.collections import Collections
from yadacoin.core.identity import Identity, PrivateIdentity
from yadacoin.core.transaction import (
    InvalidTransactionException,
    InvalidTransactionSignatureException,
    Output
)


class AffiliatePoofTypes(Enum):
    CONFIRMATION = 'confirmation'
    HONOR = 'honor'


class ReferPayout:
    def __init__(
      self,
      active,
      operator,
      payout_type,
      amount
    ):

        if not isinstance(active, bool):
            self.report_init_error('active')

        if operator not in [x.value for x in PayoutOperators]:
            self.report_init_error('operator')

        if payout_type not in [x.value for x in PayoutType]:
            self.report_init_error('payout_type')

        if not isinstance(amount, float) and not isinstance(amount, int):
            self.report_init_error('amount')

        self.active = active
        self.operator = operator
        self.payout_type = payout_type
        self.amount = amount

    def to_dict(self):
        return {
            'active': self.active,
            'operator': self.operator,
            'payout_type': self.payout_type,
            'amount': self.amount
        }

    def to_string(self):
        return (
            ('true' if self.active else 'false') +
            str(self.operator) +
            str(self.payout_type) +
            str(self.amount)
        )


class AffiliateContract(Contract):

    def __init__(
        self,
        version,
        expiry,
        contract_type,
        affiliate_proof_type,
        target,
        market,
        identity,
        creator,
        referrer,
        referee
    ):
        super().__init__(
            version,
            expiry,
            contract_type,
            affiliate_proof_type,
            identity,
            creator
        )

        self.affiliate_proof_type = affiliate_proof_type

        self.referrer = referrer if isinstance(referrer, ReferPayout) else ReferPayout(**referrer)

        self.referee = referee if isinstance(referee, ReferPayout) else ReferPayout(**referee)

        self.target = target

        self.market = market

    @classmethod
    async def generate(
        cls,
        expiry=(time.time() + (60 * 60)),
        contract_type=ContractTypes.NEW_RELATIONSHIP.value,
        affiliate_proof_type=AffiliatePoofTypes.HONOR.value,
        target='',
        market='',
        username='',
        creator=None,
        referrer=None,
        referee=None
    ):
        identity = PrivateIdentity.generate(username)
        return cls(
            version=1,
            expiry=expiry,
            contract_type=contract_type,
            affiliate_proof_type=affiliate_proof_type,
            target=target,
            market=market,
            identity=identity,
            creator=creator,
            referrer=referrer,
            referee=referee
        )

    async def process(self, contract_txn, trigger_txn, mempool_txns):
        from yadacoin.core.transaction import Transaction
        from yadacoin.core.transactionutils import TU

        await self.verify(contract_txn, trigger_txn, mempool_txns)

        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.identity.public_key)))
        value_sent_to_address = sum([x.value for x in trigger_txn.outputs if x.to == address])

        referrer = await self.get_referrer(trigger_txn)

        outputs = []
        if self.referrer.active:
            output = Output(
                to=str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(referrer.public_key)))
            )
            if self.referrer.operator == PayoutOperators.PERCENT:
                output.value = self.referrer.amount * value_sent_to_address
            if self.referrer.operator == PayoutOperators.FIXED:
                output.value = self.referrer.amount
            outputs.append(output)

        if self.referee.active:
            output = Output(
                to=str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(trigger_txn.public_key)))
            )
            if self.referee.operator == PayoutOperators.PERCENT:
                output.value = self.referee.amount * value_sent_to_address
            if self.referee.operator == PayoutOperators.FIXED:
                output.value = self.referee.amount
            outputs.append(output)

        total_payout = sum([x.value for x in outputs])

        return_address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(referrer.public_key)))

        funding_txns = await getattr(self, f'get_{self.affiliate_proof_type}_funds')(contract_txn, total_payout)

        payout_txn = Transaction.from_dict({
            'value': value_sent_to_address,
            'inputs': [{'id': funding_txn.transaction_signature} for funding_txn in funding_txns],
            'fee': 0,
            'outputs': outputs,
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

    async def verify_affiliate(self, contract_txn, trigger_txn):
        referrer = await self.get_referrer(trigger_txn)
        if not referrer:
            raise Exception('Referrer not found')

        if trigger_txn.requested_rid != contract_txn.requested_rid:
            raise Exception('Referee is not for this contract')

    async def get_affiliate_funds(self, contract_txn, total_payout):
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(self.identity.public_key)))
        funds = self.get_funds(self, contract_txn)
        total_output_to_contract = 0
        selected_funds = []
        async for fund in funds:
            total_output_to_contract += sum([x.value for x in fund.outputs if x.to == address])
            selected_funds.append(fund)

            if total_output_to_contract >= total_payout:
                break
        return selected_funds

    async def get_referrer(self, trigger_txn):
        referrers = self.config.mongo.async_db.blocks.aggregate([
            {
                '$match': {
                    'transactions.referrer_rid': trigger_txn.referrer_rid
                }
            },
            {
                '$unwind': 'transactions'
            },
            {
                '$match': {
                    'transactions.referrer_rid': trigger_txn.referrer_rid
                }
            },
            {
                '$sort': {'index': 1, 'transactions.time': 1}
            },
            {
                '$limit': 1
            }
        ])
        results = [referrer async for referrer in referrers]
        if results:
            return results[0]

    def to_dict(self):
        return {
            Collections.SMART_CONTRACT.value: {
                'version': self.version,
                'expiry': self.expiry,
                'contract_type': self.contract_type,
                'affiliate_proof_type': self.affiliate_proof_type,
                'target': self.target,
                'market': self.market,
                'identity': self.identity.to_dict,
                'referrer': self.referrer.to_dict(),
                'referee': self.referee.to_dict(),
                'creator': self.creator
            }
        }

    def to_string(self):
        return (
            str(self.version) +
            str(self.expiry) +
            str(self.contract_type) +
            str(self.affiliate_proof_type) +
            str(self.target) +
            str(self.market) +
            str(self.identity.username_signature) +
            self.referrer.to_string() +
            self.referee.to_string() +
            str(self.creator)
        )