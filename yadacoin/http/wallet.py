"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

"""
Handlers required by the wallet operations
"""

import binascii
import datetime
import hashlib
import json
import time

import base58
import jwt
from bip32utils import BIP32Key
from bitcoin.wallet import P2PKHBitcoinAddress

from yadacoin.core.config import Config
from yadacoin.core.identity import Identity
from yadacoin.core.transaction import Transaction
from yadacoin.core.transactionutils import TU
from yadacoin.decorators.jwtauth import jwtauthwallet
from yadacoin.http.base import BaseHandler


class WalletHandler(BaseHandler):
    async def get(self, path):
        """
        :return:
        """
        self.render("wallet.html")


class UnwrapHandler(BaseHandler):
    async def get(self, path):
        self.render("unwrap.html")


class GenerateWalletHandler(BaseHandler):
    async def get(self):
        return self.render_as_json("TODO: Implement")


@jwtauthwallet
class GenerateChildWalletHandler(BaseHandler):
    async def post(self):
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif and self.jwt.get("key_or_wif") != "true":
            return self.render_as_json({"error": "not authorized"})
        try:
            args = json.loads(self.request.body)
        except:
            self.set_status(400)
            return self.render_as_json(
                {"status": False, "message": "invalid json body"}
            )
        if "index" not in args:
            return self.render_as_json(
                {"status": False, "message": "index not provided"}
            )
        try:
            uindex = int(args.get("index"))
        except:
            return self.render_as_json(
                {"status": False, "message": "index is not integer"}
            )
        if uindex > 4294967295:
            return self.render_as_json(
                {"status": False, "message": "index cannot be greater than 4294967295"}
            )
        if await self.config.mongo.async_db.child_keys.find_one(
            {
                "index": uindex,
            }
        ):
            return self.render_as_json(
                {
                    "status": False,
                    "message": "Child wallet already exists for this index",
                }
            )
        exkey = BIP32Key.fromExtendedKey(self.config.xprv)
        child_key = exkey.ChildKey(uindex)
        public_key = child_key.PublicKey().hex()
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        private_key = child_key.PrivateKey().hex()
        wif = self.to_wif(private_key)
        await self.config.mongo.async_db.child_keys.update_one(
            {
                "index": uindex,
            },
            {
                "$set": {
                    "index": uindex,
                    "extended": child_key.ExtendedKey(),
                    "public_key": public_key,
                    "address": address,
                    "private_key": private_key,
                    "wif": wif,
                }
            },
            upsert=True,
        )
        return self.render_as_json({"address": address, "status": True})

    def to_wif(self, private_key):
        # to wif
        private_key_static = private_key
        extended_key = "80" + private_key_static + "01"
        first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key)).hexdigest()
        second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
        final_key = extended_key + second_sha256[:8]
        return base58.b58encode(binascii.unhexlify(final_key)).decode("utf-8")


class GetAddressesHandler(BaseHandler):
    async def get(self):
        addresses = []
        async for x in self.config.mongo.async_db.child_keys.find():
            addresses.append(x["address"])
        addresses.append(self.config.address)

        return self.render_as_json({"addresses": list(set(addresses))})


class GetBalanceSum(BaseHandler):
    async def post(self):
        args = json.loads(self.request.body.decode())
        addresses = args.get("addresses", None)
        if not addresses:
            self.render_as_json({})
            return
        balance = 0.0
        for address in addresses:
            balance += await self.config.BU.get_wallet_balance(address)
        return self.render_as_json("{0:.8f}".format(balance))


@jwtauthwallet
class CreateTransactionView(BaseHandler):
    async def post(self):
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif and self.jwt.get("key_or_wif") != "true":
            return self.render_as_json({"error": "not authorized"})
        config = self.config

        args = json.loads(self.request.body)
        address = args.get("address")
        if not address:
            return self.render_as_json({})

        fee = args.get("fee", 0.0)
        outputs = args.get("outputs")
        if not outputs:
            return self.render_as_json({})
        from_addresses = args.get("from", [])

        inputs = []
        for from_address in from_addresses:
            inputs.extend(
                [
                    x
                    async for x in self.config.BU.get_wallet_unspent_transactions_for_spending(
                        from_address, inc_mempool=True
                    )
                ]
            )

        txn = await Transaction.generate(
            private_key=config.private_key,
            public_key=config.public_key,
            fee=float(fee),
            inputs=inputs,
            outputs=outputs,
        )
        return self.render_as_json(txn.to_dict())


@jwtauthwallet
class CreateRawTransactionView(BaseHandler):
    async def post(self):
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif and self.jwt.get("key_or_wif") != "true":
            return self.render_as_json({"error": "not authorized"})
        config = self.config

        args = json.loads(self.request.body)
        address = args.get("address")
        if not address:
            return self.render_as_json({})

        fee = args.get("fee", 0.0)
        outputs = args.get("outputs")
        if not outputs:
            return self.render_as_json({})
        from_addresses = args.get("from", [])

        inputs = []
        for from_address in from_addresses:
            inputs.extend(
                [
                    x
                    async for x in self.config.BU.get_wallet_unspent_transactions_for_spending(
                        from_address, inc_mempool=True
                    )
                ]
            )

        txn = await Transaction.generate(
            public_key=config.public_key, fee=float(fee), inputs=inputs, outputs=outputs
        )
        return self.render_as_json(txn.to_dict())


@jwtauthwallet
class SendTransactionView(BaseHandler):
    async def post(self):
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif and self.jwt.get("key_or_wif") != "true":
            return self.render_as_json({"error": "not authorized"})
        config = self.config
        args = json.loads(self.request.body.decode())
        to = args.get("address")
        outputs = args.get("outputs")
        value = float(args.get("value", 0))
        from_address = args.get("from")
        inputs = args.get("inputs")
        dry_run = args.get("dry_run")
        exact_match = args.get("exact_match", False)
        txn = await TU.send(
            config,
            to,
            value,
            from_address=from_address,
            inputs=inputs,
            dry_run=dry_run,
            exact_match=exact_match,
            outputs=outputs,
        )
        return self.render_as_json(txn)


@jwtauthwallet
class UnlockedHandler(BaseHandler):
    async def prepare(self):
        origin = self.get_query_argument("origin", "*")
        if origin[-1] == "/":
            origin = origin[:-1]
        self.set_header("Access-Control-Allow-Origin", origin)
        self.set_header("Access-Control-Allow-Credentials", "true")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.set_header("Access-Control-Expose-Headers", "Content-Type")
        self.set_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, Depth, User-Agent, X-File-Size, X-Requested-With, X-Requested-By, If-Modified-Since, X-File-Name, Cache-Control",
        )
        self.set_header("Access-Control-Max-Age", 600)
        await super(UnlockedHandler, self).prepare()

    async def get(self):
        if self.get_secure_cookie("key_or_wif") == "true":
            return self.render_as_json({"unlocked": True})

        if self.jwt.get("key_or_wif") == "true":
            return self.render_as_json({"unlocked": True})

        return self.render_as_json({"unlocked": False})


class UnlockHandler(BaseHandler):
    async def get(self):
        """
        :return:
        """
        self.render("auth.html")

    async def post(self):
        try:
            key_or_wif = self.get_body_argument("key_or_wif")
            expires = self.get_body_argument("expires", 23040)
        except:
            json_body = json.loads(self.request.body.decode())
            key_or_wif = json_body.get("key_or_wif")
            expires = json_body.get("expires", 23040)
        if key_or_wif in [self.config.wif, self.config.private_key, self.config.seed]:
            self.set_secure_cookie("key_or_wif", "true")

            payload = {
                "timestamp": time.time(),
                "key_or_wif": "true",
                "exp": datetime.datetime.utcnow()
                + datetime.timedelta(seconds=int(expires)),
            }

            self.encoded = jwt.encode(
                payload, self.config.jwt_secret_key, algorithm="ES256"
            )
            await self.config.mongo.async_db.config.update_one(
                {"key": "jwt"}, {"$set": {"key": "jwt", "value": payload}}, upsert=True
            )
            return self.render_as_json({"token": self.encoded})
        else:
            self.write(
                {
                    "status": "error",
                    "message": "Wrong private key or WIF. You must provide the private key or WIF of the currently running server.",
                }
            )
            self.set_header("Content-Type", "application/json")
            return self.finish()


class SentPendingTransactionsView(BaseHandler):
    async def get(self):
        public_key = self.get_query_argument("public_key")
        include_zero = self.get_query_argument("include_zero", False)
        page = int(self.get_query_argument("page", 1)) - 1

        query = {
            "public_key": public_key,
        }
        if not include_zero:
            query["outputs.value"] = {"$gt": 0}
        pending_txns = (
            await self.config.mongo.async_db.miner_transactions.find(
                query,
                {"_id": 0},
            )
            .sort([("time", -1)])
            .skip(page * 10)
            .limit(10)
            .to_list(10)
        )

        return self.render_as_json({"past_pending_transactions": pending_txns})


class SentTransactionsView(BaseHandler):
    async def get(self):
        public_key = self.get_query_argument("public_key")
        include_zero = self.get_query_argument("include_zero", False)
        page = int(self.get_query_argument("page", 1)) - 1
        query = [
            {
                "$match": {
                    "transactions.inputs.0": {"$exists": True},
                    "transactions.public_key": public_key,
                }
            },
            {"$unwind": "$transactions"},
            {
                "$match": {
                    "transactions.inputs.0": {"$exists": True},
                    "transactions.public_key": public_key,
                }
            },
            {"$sort": {"transactions.time": -1}},
            {"$skip": page * 10},
            {"$limit": 10},
        ]
        if not include_zero:
            query[0]["$match"]["transactions.outputs.value"] = {"$gt": 0}
            query[2]["$match"]["transactions.outputs.value"] = {"$gt": 0}
        txns = self.config.mongo.async_db.blocks.aggregate(query)

        return self.render_as_json(
            {
                "past_transactions": [x["transactions"] async for x in txns],
            }
        )


class ReceivedPendingTransactionsView(BaseHandler):
    async def get(self):
        public_key = self.get_query_argument("public_key")
        include_zero = self.get_query_argument("include_zero", False)
        page = int(self.get_query_argument("page", 1)) - 1
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        query = {
            "outputs.to": address,
            "public_key": {"$ne": public_key},
        }
        if not include_zero:
            query["outputs.value"] = {"$gt": 0}
        pending_txns = (
            await self.config.mongo.async_db.miner_transactions.find(
                query,
                {"_id": 0},
            )
            .sort([("time", -1)])
            .skip(page * 10)
            .limit(10)
            .to_list(10)
        )

        return self.render_as_json({"past_pending_transactions": pending_txns})


class ReceivedTransactionsView(BaseHandler):
    async def get(self):
        public_key = self.get_query_argument("public_key")
        include_zero = self.get_query_argument("include_zero", False)
        page = int(self.get_query_argument("page", 1)) - 1
        address = str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key)))
        query = [
            {
                "$match": {
                    "transactions.outputs.to": address,
                    "transactions.outputs.value": {"$gt": 0},
                    "$or": [
                        {
                            "transactions": {
                                "$elemMatch": {"public_key": {"$ne": public_key}}
                            }
                        },
                        {
                            "public_key": public_key,
                            "transactions.inputs.0": {"$exists": False},
                        },
                    ],
                }
            },
            {"$unwind": "$transactions"},
            {
                "$match": {
                    "transactions.outputs.to": address,
                    "transactions.outputs.value": {"$gt": 0},
                    "$or": [
                        {"transactions.public_key": {"$ne": public_key}},
                        {
                            "public_key": public_key,
                            "transactions.inputs.0": {"$exists": False},
                        },
                    ],
                }
            },
            {"$sort": {"transactions.time": -1}},
            {"$skip": page * 10},
            {"$limit": 10},
        ]
        if not include_zero:
            query[0]["$match"]["transactions.outputs.value"] = {"$gt": 0}
            query[2]["$match"]["transactions.outputs.value"] = {"$gt": 0}
        txns = self.config.mongo.async_db.blocks.aggregate(query)

        return self.render_as_json(
            {
                "past_transactions": [x["transactions"] async for x in txns],
            }
        )


class TransactionConfirmationsHandler(BaseHandler):
    async def get(self):
        txn_id = self.get_query_argument("id").replace(" ", "+")
        result = await self.config.mongo.async_db.blocks.find_one(
            {"transactions.id": txn_id}, {"_id": 0}, sort=[("transactions.time", -1)]
        )
        return self.render_as_json(
            {
                "confirmations": (
                    self.config.LatestBlock.block.index - result["index"]
                    if result
                    else 0
                )
            }
        )

    async def post(self):
        data = json.loads(self.request.body)
        results = []
        for txn_id in data["txn_ids"]:
            result = await self.config.mongo.async_db.blocks.find_one(
                {"transactions.id": txn_id},
                {"_id": 0},
                sort=[("transactions.time", -1)],
            )
            results.append(
                {
                    "txn_id": txn_id,
                    "confirmations": (
                        self.config.LatestBlock.block.index - result["index"]
                        if result
                        else 0
                    ),
                }
            )
        return self.render_as_json({"confirmations": results})


class PaymentHandler(BaseHandler):
    async def get(self):
        newer_than = self.get_query_argument("newer_than", None)
        to_address = self.get_query_argument("to_address", None)
        from_address = self.get_query_argument("from_address", None)
        try:
            identity = Identity.from_dict(
                json.loads(self.get_secure_cookie("identity"))
            )
        except:
            return self.redirect("/logout")
        query = [
            {
                "$match": {
                    "$and": [
                        {"transactions.outputs.to": to_address},
                        {"transactions.outputs.to": from_address or to_address},
                    ]
                }
            },
            {"$unwind": "$transactions"},
            {
                "$match": {
                    "$and": [
                        {"transactions.outputs.to": to_address},
                        {"transactions.outputs.to": from_address or to_address},
                    ]
                }
            },
            {"$project": {"_id": 0, "txn": "$transactions"}},
        ]
        if newer_than:
            query.append({"$match": {"txn.time": {"$gt": int(newer_than)}}})
        query.append({"$sort": {"txn.time": -1}})
        result = self.config.mongo.async_db.blocks.aggregate(query)
        pending_query = [
            {
                "$match": {
                    "$and": [
                        {"outputs.to": to_address},
                        {"outputs.to": from_address or to_address},
                    ]
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "pending": True,
                    "outputs": "$outputs",
                    "inputs": "$inputs",
                    "id": "$id",
                    "hash": "$hash",
                    "time": "$time",
                    "public_key": "$public_key",
                }
            },
        ]
        if newer_than:
            pending_query.append({"$match": {"time": {"$gt": int(newer_than)}}})
        pending_query.append({"$sort": {"time": -1}})
        pending = self.config.mongo.async_db.miner_transactions.aggregate(pending_query)
        mempool = [
            x
            async for x in pending
            if to_address
            != str(P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(x["public_key"])))
        ]
        blockchain = [
            x["txn"]
            async for x in result
            if to_address
            != str(
                P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(x["txn"]["public_key"]))
            )
        ]
        return self.render_as_json({"payments": blockchain + mempool})


class ValidateAddressHandler(BaseHandler):
    async def get(self):
        address = self.get_argument("address")
        return self.render_as_json(
            {"status": Config().address_is_valid(address), "address": address}
        )


class TransactionByIdHandler(BaseHandler):
    async def get(self):
        txn_id = self.get_query_argument("id").replace(" ", "+")
        best_mt_txn = await self.config.mongo.async_db.miner_transactions.find_one(
            {"id": txn_id}, {"_id": 0}, sort=[("time", -1)]
        )
        if best_mt_txn:
            best_mt_txn["mempool"] = True
        result = await self.config.mongo.async_db.blocks.find_one(
            {"transactions.id": txn_id}, {"_id": 0}, sort=[("transactions.time", -1)]
        )
        all_block_txn = []
        if result:
            for txn in result["transactions"]:
                if txn["id"] == txn_id:
                    all_block_txn.append(txn)

        best_block_txn = None
        if all_block_txn:
            best_block_txn = sorted(
                all_block_txn, key=lambda x: int(x["time"]), reverse=True
            )[0]

        if best_mt_txn and best_block_txn:
            return self.render_as_json(
                best_mt_txn
                if int(best_mt_txn["time"]) >= int(best_block_txn["time"])
                else best_block_txn
            )
        elif best_mt_txn or best_block_txn:
            return self.render_as_json(best_mt_txn if best_mt_txn else best_block_txn)
        else:
            self.status_code = 404
            return self.render_as_json({"status": False, "message": "user not found"})


class ConvertPublicKeyToAddressHandler(BaseHandler):
    async def get(self):
        public_key = self.get_query_argument("public_key")
        return self.render_as_json(
            {
                "address": str(
                    P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(public_key))
                ),
                "public_key": public_key,
            }
        )


class FeeEstimateHandler(BaseHandler):
    async def get(self):
        # Fetch up to 1000 transactions with non-zero fees
        cursor = self.config.mongo.async_db.miner_transactions.aggregate(
            [
                {"$match": {"transactions.fee": {"$gt": 0}}},
                {"$project": {"fee": "$transactions.fee"}},
                {"$sort": {"fee": -1}},
                {"$limit": 1000},
            ]
        )

        txns = await cursor.to_list(length=1000)

        if len(txns) < 1000:
            self.write(
                {
                    "status": "not_congested",
                    "txns_count": len(txns),
                    "message": "Block not full. Any non-zero fee likely to be accepted.",
                    "recommended_fee": 0.00,  # or any minimum you consider valid
                }
            )
            return

        fees = [round(tx["fee"], 8) for tx in txns]
        estimate = {
            "min_fee": fees[-1],
            "median_fee": fees[len(fees) // 2],
            "percentile_25_fee": fees[len(fees) // 4],
            "percentile_75_fee": fees[3 * len(fees) // 4],
            "max_fee": fees[0],
        }

        self.write(
            {
                "status": "congested",
                "txns_considered": len(fees),
                "fee_estimate": estimate,
            }
        )


WALLET_HANDLERS = [
    (r"/wallet?([\/a-z]+)", WalletHandler),
    (r"/unwrap?([\/a-z]+)", UnwrapHandler),
    (r"/generate-wallet", GenerateWalletHandler),
    (r"/generate-child-wallet", GenerateChildWalletHandler),
    (r"/get-addresses", GetAddressesHandler),
    (r"/create-transaction", CreateTransactionView),
    (r"/create-raw-transaction", CreateRawTransactionView),
    (r"/get-balance-sum", GetBalanceSum),
    (r"/send-transaction", SendTransactionView),
    (r"/unlocked", UnlockedHandler),
    (r"/unlock", UnlockHandler),
    (r"/get-past-pending-sent-txns", SentPendingTransactionsView),
    (r"/get-past-sent-txns", SentTransactionsView),
    (r"/get-past-pending-received-txns", ReceivedPendingTransactionsView),
    (r"/get-past-received-txns", ReceivedTransactionsView),
    (r"/get-transaction-confirmations", TransactionConfirmationsHandler),
    (r"/payment", PaymentHandler),
    (r"/validate-address", ValidateAddressHandler),
    (r"/get-transaction-by-id", TransactionByIdHandler),
    (r"/convert-public-key-to-address", ConvertPublicKeyToAddressHandler),
    (r"/fee-estimate", FeeEstimateHandler),
]
