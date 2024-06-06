from time import time

from motor.motor_tornado import MotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel, MongoClient

from yadacoin.core.config import Config


class Mongo(object):
    def __init__(self):
        self.config = Config()
        if hasattr(self.config, "mongodb_username") and hasattr(
            self.config, "mongodb_password"
        ):
            try:
                self.client = MongoClient(self.config.mongodb_host)
                admin_db = self.client["admin"]
                admin_db.command(
                    "createUser",
                    self.config.mongodb_username,
                    pwd=self.config.mongodb_password,
                    roles=["root"],
                )
            except:
                pass
            self.client = MongoClient(
                self.config.mongodb_host,
                username=self.config.mongodb_username,
                password=self.config.mongodb_password,
            )
        else:
            self.client = MongoClient(self.config.mongodb_host)
        self.db = self.client[self.config.database]
        self.site_db = self.client[self.config.site_database]
        try:
            # test connection
            self.db.yadacoin.find_one()
        except Exception as e:
            raise e

        __id = IndexModel([("id", ASCENDING)], name="__id", unique=True)
        __hash = IndexModel([("hash", ASCENDING)], name="__hash")
        __time = IndexModel([("time", ASCENDING)], name="__time")
        __index = IndexModel([("index", ASCENDING)], name="__index")
        __to = IndexModel([("transactions.outputs.to", ASCENDING)], name="__to")
        __txn_id = IndexModel([("transactions.id", ASCENDING)], name="__txn_id")
        __txn_inputs_id = IndexModel(
            [("transactions.inputs.id", ASCENDING)], name="__txn_inputs_id"
        )
        __txn_public_key = IndexModel(
            [("transactions.public_key", ASCENDING)], name="__txn_public_key"
        )
        __txn_inputs_public_key = IndexModel(
            [("transactions.inputs.public_key", ASCENDING)],
            name="__txn_inputs_public_key",
        )
        __txn_inputs_address = IndexModel(
            [("transactions.inputs.address", ASCENDING)], name="__txn_inputs_address"
        )
        __txn_public_key_inputs_public_key_address = IndexModel(
            [
                ("transactions.public_key", ASCENDING),
                ("transactions.inputs.public_key", ASCENDING),
                ("transactions.inputs.address", ASCENDING),
            ],
            name="__txn_public_key_inputs_public_key_address",
        )
        __public_key_index = IndexModel(
            [("public_key", ASCENDING), ("index", DESCENDING)],
            name="__public_key_index",
        )
        __public_key_time = IndexModel(
            [
                ("public_key", ASCENDING),
                ("time", ASCENDING),
            ],
            name="__public_key_time",
        )
        __public_key = IndexModel([("public_key", ASCENDING)], name="__public_key")
        __prev_hash = IndexModel([("prevHash", ASCENDING)], name="__prev_hash")
        __txn_public_key_inputs_id = IndexModel(
            [
                ("transactions.public_key", ASCENDING),
                ("transactions.inputs.id", ASCENDING),
            ],
            name="__txn_public_key_inputs_id",
        )
        __txn_rid = IndexModel([("transactions.rid", ASCENDING)], name="__txn_rid")
        __txn_requested_rid = IndexModel(
            [("transactions.requested_rid", ASCENDING)], name="__txn_requested_rid"
        )
        __txn_requester_rid = IndexModel(
            [("transactions.requester_rid", ASCENDING)], name="__txn_requester_rid"
        )
        __txn_index_rid = IndexModel(
            [("index", ASCENDING), ("transactions.rid", ASCENDING)],
            name="__txn_index_rid",
        )
        __txn_index_requested_rid = IndexModel(
            [("index", ASCENDING), ("transactions.requested_rid", ASCENDING)],
            name="__txn_index_requested_rid",
        )
        __txn_index_requester_rid = IndexModel(
            [("index", ASCENDING), ("transactions.requester_rid", ASCENDING)],
            name="__txn_index_requester_rid",
        )
        __txn_time = IndexModel([("transactions.time", DESCENDING)], name="__txn_time")
        __txn_contract_rid = IndexModel(
            [("transactions.contract.rid", ASCENDING)], name="__txn_contract_rid"
        )
        __txn_rel_contract_identity_public_key = IndexModel(
            [
                (
                    "transactions.relationship.smart_contract.identity.public_key",
                    ASCENDING,
                )
            ],
            name="__txn_rel_contract_identity_public_key",
        )
        __txn_rel_contract_expiry = IndexModel(
            [
                (
                    "transactions.relationship.smart_contract.expiry",
                    ASCENDING,
                )
            ],
            name="__txn_rel_contract_expiry",
        )
        __updated_at = IndexModel(
            [
                (
                    "updated_at",
                    ASCENDING,
                )
            ],
            name="__updated_at",
        )
        __txn_outputs_to_index = IndexModel(
            [("transactions.outputs.to", ASCENDING), ("index", ASCENDING)],
            name="__txn_outputs_to_index",
        )
        __txn_inputs_0 = IndexModel(
            [("transactions.inputs.0", ASCENDING)],
            partialFilterExpression={"transactions.inputs.0": {"$exists": False}},
            name="__txn_inputs_0",
        )

        try:
            self.db.blocks.create_indexes(
                [
                    __hash,
                    __time,
                    __index,
                    __id,
                    __to,
                    __txn_id,
                    __txn_inputs_id,
                    __txn_public_key,
                    __txn_inputs_public_key,
                    __txn_inputs_address,
                    __txn_public_key_inputs_public_key_address,
                    __public_key_index,
                    __public_key_time,
                    __public_key,
                    __prev_hash,
                    __txn_public_key_inputs_id,
                    __txn_rid,
                    __txn_requested_rid,
                    __txn_requester_rid,
                    __txn_index_rid,
                    __txn_index_requested_rid,
                    __txn_index_requester_rid,
                    __txn_time,
                    __txn_contract_rid,
                    __txn_rel_contract_identity_public_key,
                    __txn_rel_contract_expiry,
                    __updated_at,
                    __txn_outputs_to_index,
                    __txn_inputs_0,
                ]
            )
        except:
            pass

        __id = IndexModel([("id", ASCENDING)], name="__id")
        __height = IndexModel([("height", ASCENDING)], name="__height")
        try:
            self.db.unspent_cache.create_indexes([__id, __height])
        except:
            pass

        __id = IndexModel([("id", ASCENDING)], name="__id")
        __index = IndexModel([("index", ASCENDING)], name="__index")
        __block_hash = IndexModel([("block.hash", ASCENDING)], name="__block_hash")
        __block_prevHash_index_version = IndexModel(
            [
                ("block.prevHash", ASCENDING),
                ("block.index", ASCENDING),
                ("block.version", ASCENDING),
            ],
            name="__block_prevHash_index_version",
        )
        try:
            self.db.consensus.create_indexes(
                [__id, __index, __block_hash, __block_prevHash_index_version]
            )
        except:
            pass

        __address = IndexModel([("address", ASCENDING)], name="__address")
        __address_desc = IndexModel([("address", DESCENDING)], name="__address_desc")
        __address_only = IndexModel(
            [("address_only", ASCENDING)], name="__address_only"
        )
        __address_only_desc = IndexModel(
            [("address_only", DESCENDING)], name="__address_only_desc"
        )
        __index = IndexModel([("index", ASCENDING)], name="__index")
        __hash = IndexModel([("hash", ASCENDING)], name="__hash")
        __time = IndexModel([("time", DESCENDING)], name="__time")
        try:
            self.db.shares.create_indexes(
                [
                    __address,
                    __address_desc,
                    __address_only,
                    __address_only_desc,
                    __index,
                    __hash,
                    __time,
                ]
            )
        except:
            pass

        __index = IndexModel([("index", DESCENDING)], name="__index")
        try:
            self.db.share_payout.create_indexes(
                [
                    __index,
                ]
            )
        except:
            pass

        __txn_id = IndexModel([("txn.id", ASCENDING)], name="__txn_id")
        try:
            self.db.transactions_by_rid_cache.create_indexes([__txn_id])
        except:
            pass

        __id = IndexModel([("id", ASCENDING)], name="__id")
        __hash = IndexModel([("hash", ASCENDING)], name="__hash")
        __outputs_to = IndexModel([("outputs.to", ASCENDING)], name="__outputs_to")
        __public_key = IndexModel([("public_key", ASCENDING)], name="__public_key")
        __rid = IndexModel([("rid", ASCENDING)], name="__rid")
        __requested_rid = IndexModel(
            [("requested_rid", ASCENDING)], name="__requested_rid"
        )
        __requester_rid = IndexModel(
            [("requester_rid", ASCENDING)], name="__requester_rid"
        )
        __time = IndexModel([("time", DESCENDING)], name="__time")
        __inputs_id = IndexModel([("inputs.id", ASCENDING)], name="__inputs_id")
        __fee_time = IndexModel(
            [("fee", DESCENDING), ("time", ASCENDING)], name="__fee_time"
        )
        try:
            self.db.miner_transactions.create_indexes(
                [
                    __id,
                    __hash,
                    __outputs_to,
                    __public_key,
                    __rid,
                    __requested_rid,
                    __requester_rid,
                    __time,
                    __inputs_id,
                    __fee_time,
                ]
            )
        except:
            pass

        __id = IndexModel([("txn.id", ASCENDING)], name="__id")
        __hash = IndexModel([("txn.hash", ASCENDING)], name="__hash")
        __outputs_to = IndexModel([("txn.outputs.to", ASCENDING)], name="__outputs_to")
        __public_key = IndexModel([("txn.public_key", ASCENDING)], name="__public_key")
        __rid = IndexModel([("txn.rid", ASCENDING)], name="__rid")
        __requested_rid = IndexModel(
            [("txn.requested_rid", ASCENDING)], name="__requested_rid"
        )
        __requester_rid = IndexModel(
            [("txn.requester_rid", ASCENDING)], name="__requester_rid"
        )
        __time = IndexModel([("txn.time", DESCENDING)], name="__time")
        __inputs_id = IndexModel([("txn.inputs.id", ASCENDING)], name="__inputs_id")
        __fee_time = IndexModel(
            [("txn.fee", DESCENDING), ("txn.time", ASCENDING)], name="__fee_time"
        )
        try:
            self.db.failed_transactions.create_indexes(
                [
                    __id,
                    __hash,
                    __outputs_to,
                    __public_key,
                    __rid,
                    __requested_rid,
                    __requester_rid,
                    __time,
                    __inputs_id,
                    __fee_time,
                ]
            )
        except:
            pass

        __time = IndexModel([("time", ASCENDING)], name="__time")
        __rid = IndexModel([("rid", ASCENDING)], name="__rid")
        __username_signature = IndexModel(
            [("username_signature", ASCENDING)], name="__username_signature"
        )
        __rid_username_signature = IndexModel(
            [("rid", ASCENDING), ("username_signature", ASCENDING)],
            name="__rid_username_signature",
        )
        try:
            self.db.user_collection_last_activity.create_indexes(
                [__time, __rid, __username_signature, __rid_username_signature]
            )
        except:
            pass

        __timestamp = IndexModel([("timestamp", DESCENDING)], name="__timestamp")
        __archived = IndexModel([("archived", ASCENDING)], name="__archived")
        try:
            self.db.node_status.create_indexes([__timestamp, __archived])
        except:
            raise

        # TODO: add indexes for peers

        if hasattr(self.config, "mongodb_username") and hasattr(
            self.config, "mongodb_password"
        ):
            self.async_client = MotorClient(
                self.config.mongodb_host,
                username=self.config.mongodb_username,
                password=self.config.mongodb_password,
            )
        else:
            self.async_client = MotorClient(self.config.mongodb_host)
        self.async_db = AsyncDB(self.async_client)
        # self.async_db = self.async_client[self.config.database]
        self.async_site_db = self.async_client[self.config.site_database]

        # convert block time from string to number
        blocks_to_convert = self.db.blocks.find({"time": {"$type": 2}})
        for block in blocks_to_convert:
            self.config.app_log.warning(
                f'Converting block time to int for block: {block["index"]}'
            )
            self.db.blocks.update(
                {"index": block["index"]}, {"$set": {"time": int(block["time"])}}
            )

        # convert mempool transaction time from string to number
        txns_to_convert = self.db.miner_transactions.find({"time": {"$type": 2}})
        for txn in txns_to_convert:
            self.config.app_log.warning(
                f'Converting txn time to int for txn: {txn["id"]}'
            )
            self.db.miner_transactions.update(
                {"id": txn["id"]}, {"$set": {"time": int(txn["time"])}}
            )

        # convert blockchain transaction time from string to number
        blockchain_txns_to_convert = self.db.blocks.find(
            {"transactions.time": {"$type": 2}}
        )
        for block in blockchain_txns_to_convert:
            changed = False
            for txn in block.get("transactions"):
                changed = True
                if "time" in txn:
                    self.config.app_log.warning(
                        f'Converting blockchain txn time to int for index and txn: {block["index"]} {txn["id"]}'
                    )
                    if txn["time"] in ["", 0, "0"]:
                        del txn["time"]
                    else:
                        txn["time"] = int(txn["time"])
            if changed:
                self.db.blocks.update({"index": block["index"]}, {"$set": block})

        too_high_reward_blocks = self.db.blocks.find({"index": {"$gte": 210000}})
        for block in too_high_reward_blocks:
            for txn in block["transactions"]:
                if txn["public_key"] == block["public_key"] and len(txn["inputs"]) == 0:
                    total_output = 0
                    for txn_out in txn["outputs"]:
                        total_output += txn_out["value"]
                    if total_output >= 50:
                        self.config.app_log.warning(
                            f'Removing block with too high of reward: {block["index"]}'
                        )
                        self.db.blocks.delete_one({"index": block["index"]})


class AsyncDB:
    def __init__(self, async_client):
        self.async_client = async_client
        self._config = Config()
        self.slow_queries = []

    def __getattr__(self, __name: str):
        return Collection(self.async_client, __name)

    async def list_collection_names(self, *args, **kwargs):
        start_time = time()
        self._db = self.async_client[self._config.database]
        result = await self._db.list_collection_names()
        if time() - start_time > 3:
            self._config.app_log.warning(f"SLOW QUERY: find_one {args}, {kwargs}")
        return result

    def __getitem__(self, name):
        return getattr(self, name)


class Collection:
    def __init__(self, async_client, collection):
        self._config = Config()
        self._db = async_client[self._config.database]
        self.collection = collection

    def set_start_time(self):
        self.start_time = time()

    def set_duration(self):
        self.duration = float("%.3f" % (time() - self.start_time))

    def do_logging(self, query_type, args, kwargs):
        self.set_duration()
        message = f"QUERY: {query_type} {self.collection} {args}, {kwargs}, duration: {self.duration}"
        if self.duration > 3 and getattr(self._config, "slow_query_logging", None):
            self._config.app_log.warning(f"SLOW {message}")
            self._config.mongo.async_db.slow_queries.append(message)
        else:
            if hasattr(self._config, "mongo_debug") and self._config.mongo_debug:
                self._config.app_log.debug(message)

    async def find_one(self, *args, **kwargs):
        self.set_start_time()
        kwargs["max_time_ms"] = self._config.mongo_query_timeout
        result = await self._db.get_collection(self.collection).find_one(
            *args, **kwargs
        )
        if self.collection == "child_keys":
            return result
        self.do_logging("find_one", args, kwargs)
        return result

    def find(self, *args, **kwargs):
        self.set_start_time()
        kwargs["max_time_ms"] = self._config.mongo_query_timeout
        result = self._db.get_collection(self.collection).find(*args, **kwargs)
        if self.collection == "child_keys":
            return result
        self.do_logging("find", args, kwargs)
        return result

    async def count_documents(self, *args, **kwargs):
        self.set_start_time()
        pipeline = [
            {"$match": args[0]},
            {"$group": {"_id": None, "count": {"$sum": 1}}},
        ]
        cursor = self._db.get_collection(self.collection).aggregate(
            pipeline, maxTimeMS=self._config.mongo_query_timeout
        )
        result = 0
        async for doc in cursor:
            result = doc.get("count", 0)
            break
        if self.collection == "child_keys":
            return result

        self.do_logging("count_documents", args, kwargs)
        return result

    async def delete_many(self, *args, **kwargs):
        self.set_start_time()
        result = await self._db.get_collection(self.collection).delete_many(
            *args, **kwargs
        )
        if self.collection == "child_keys":
            return result
        self.do_logging("delete_many", args, kwargs)
        return result

    async def insert_one(self, *args, **kwargs):
        self.set_start_time()
        result = await self._db.get_collection(self.collection).insert_one(
            *args, **kwargs
        )
        if self.collection == "child_keys":
            return result
        self.do_logging("insert_one", args, kwargs)
        return result

    async def replace_one(self, *args, **kwargs):
        self.set_start_time()
        result = await self._db.get_collection(self.collection).replace_one(
            *args, **kwargs
        )
        if self.collection == "child_keys":
            return result
        self.do_logging("replace_one", args, kwargs)
        return result

    async def update_one(self, *args, **kwargs):
        self.set_start_time()
        result = await self._db.get_collection(self.collection).update_one(
            *args, **kwargs
        )
        if self.collection == "child_keys":
            return result
        self.do_logging("update_one", args, kwargs)
        return result

    async def update_many(self, *args, **kwargs):
        self.set_start_time()
        result = await self._db.get_collection(self.collection).update_many(
            *args, **kwargs
        )
        if self.collection == "child_keys":
            return result
        self.do_logging("update_many", args, kwargs)
        return result

    def aggregate(self, *args, **kwargs):
        self.set_start_time()
        result = self._db.get_collection(self.collection).aggregate(
            *args, **kwargs, maxTimeMS=self._config.mongo_query_timeout
        )
        if self.collection == "child_keys":
            return result
        self.do_logging("aggregate", args, kwargs)
        return result
