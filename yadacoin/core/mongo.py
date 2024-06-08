from time import time

from motor.motor_tornado import MotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel, MongoClient
from pymongo.monitoring import CommandListener

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
            self.db.blocks.find_one()
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
        __cache_time = IndexModel([("cache_time", ASCENDING)], name="__cache_time")
        try:
            self.db.unspent_cache.create_indexes([__id, __height, __cache_time])
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
        __cache_time = IndexModel([("cache_time", ASCENDING)], name="__cache_time")
        try:
            self.db.transactions_by_rid_cache.create_indexes([__txn_id, __cache_time])
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

        __time = IndexModel([("time", ASCENDING)], name="__time")
        __stat = IndexModel([("stat", ASCENDING)], name="__stat")
        try:
            self.db.pool_stats.create_indexes([__time, __stat])
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
                event_listeners=[listener],
            )
        else:
            self.async_client = MotorClient(
                self.config.mongodb_host, event_listeners=[listener]
            )
        self.async_db = self.async_client[self.config.database]
        # self.async_db = self.async_client[self.config.database]
        self.async_site_db = self.async_client[self.config.site_database]
        self.async_db.slow_queries = []
        self.async_db.unindexed_queries = []
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


class DeuggingListener(CommandListener):
    commands = [
        "find",
        "delete",
        "insert_one",
        "update",
        "aggregate",
    ]

    def get_collection_name(self, event):
        if event.command_name in self.commands:
            return event.command.get(event.command_name)
        return None

    def started(self, event):
        if event.command_name not in self.commands:
            return
        config = Config()
        config.mongo_debug = True
        if not hasattr(config, "mongo_debug"):
            return
        if not config.mongo_debug:
            return
        event.command["start_time"] = time()
        event.command["max_time_ms"] = config.mongo_query_timeout
        if event.command.get(event.command_name) == "child_keys":
            return
        self.log_explain_output(event)

    def succeeded(self, event):
        config = Config()
        if not hasattr(config, "mongo_debug"):
            return
        if not config.mongo_debug:
            return
        if not hasattr(event, "command"):
            return
        self.duration = time() - event.command["start_time"]
        self.do_logging(event.command_name, event.command)

    def failed(self, event):
        config = Config()
        if not hasattr(config, "mongo_debug"):
            return
        if not config.mongo_debug:
            return
        self.duration = time() - event.command["start_time"]
        self.do_logging(event.command_name, event.command)

    def do_logging(self, query_type, args, kwargs):
        config = Config()
        self.set_duration()
        message = f"QUERY: {query_type} {self.collection} {args}, {kwargs}, duration: {self.duration}"
        if self.duration > 3 and getattr(config, "slow_query_logging", None):
            config.app_log.warning(f"SLOW {message}")
            config.mongo.async_db.slow_queries.append(message)
        else:
            if hasattr(config, "mongo_debug") and config.mongo_debug:
                config.app_log.debug(message)

    def log_explain_output(self, event):
        config = Config()
        # Perform the explain command asynchronously
        collection_name = self.get_collection_name(event)
        explain_command = event.command.copy()
        explain_command["explain"] = event.command_name

        if hasattr(config, "mongodb_username") and hasattr(config, "mongodb_password"):
            client = MongoClient(
                *event.connection_id,
                username=config.mongodb_username,
                password=config.mongodb_password,
            )
        else:
            client = MongoClient(
                *event.connection_id,
            )
        db = client.get_database(event.database_name)
        if event.command_name in [
            "find",
            "find_one",
            "insert_one",
        ] and event.command.get("filter", {}):
            explain_result = getattr(db[collection_name], event.command_name)(
                event.command.get("filter", {})
            ).explain()

            self.get_used_indexes(explain_result, event)
        elif event.command_name in [
            "delete",
        ] and event.command.get("deletes", {}):
            for delete_op in event.command.get("deletes", []):
                filter_criteria = delete_op.get("q", {})
                if not filter_criteria:
                    return
                explain_result = db[collection_name].find(filter_criteria).explain()
                self.get_used_indexes(explain_result, event)
        elif event.command_name in [
            "update",
        ] and event.command.get("updates", {}):
            for delete_op in event.command.get("updates", []):
                filter_criteria = delete_op.get("q", {})
                if not filter_criteria:
                    return
                explain_result = db[collection_name].find(filter_criteria).explain()
                self.get_used_indexes(explain_result, event)
        elif event.command_name == "aggregate" and explain_command.get("pipeline", []):
            if event.command.get("explain"):
                return
            pipeline = explain_command.get("pipeline", [])
            explain_result = db.command(
                {
                    "aggregate": collection_name,
                    "pipeline": pipeline,
                    "explain": True,
                }
            )
            self.get_used_indexes(explain_result, event)
        else:
            return False

    def get_used_indexes(self, explain_result, event):
        if not explain_result:
            return
        config = Config()
        used_indexes = False
        if event.command.get("pipeline", {}):
            if explain_result.get("stages"):
                query_planner = explain_result["stages"][0]["$cursor"].get(
                    "queryPlanner", {}
                )
            else:
                query_planner = explain_result.get("queryPlanner", {})
            winning_plan = query_planner.get("winningPlan", {})
            used_indexes = winning_plan.get("indexName", False)
            if not used_indexes:
                input_stage = winning_plan.get("inputStage", {})
                input_stage = input_stage.get("inputStage", {})
                used_indexes = input_stage.get("indexName", False)
            if not used_indexes:
                message = f"Unindexed query detected: {event.command_name} : {query_planner['namespace']} : {event.command.get('pipeline', {})}"
                config.app_log.warning(message)
                config.mongo.async_db.unindexed_queries.append(message)
        elif event.command.get("filter", {}):
            query_planner = explain_result.get("queryPlanner", {})
            winning_plan = query_planner.get("winningPlan", {})
            input_stage = winning_plan.get("inputStage", {})
            used_indexes = input_stage.get("indexName", False)
            if not used_indexes:
                message = f"Unindexed query detected: {event.command_name} : {query_planner['namespace']} : {event.command.get('filter', {})}"
                config.app_log.warning(message)
                config.mongo.async_db.unindexed_queries.append(message)
        elif event.command.get("deletes", {}):
            query_planner = explain_result.get("queryPlanner", {})
            winning_plan = query_planner.get("winningPlan", {})
            input_stage = winning_plan.get("inputStage", {})
            used_indexes = input_stage.get("indexName", False)
            if not used_indexes:
                message = f"Unindexed query detected: {event.command_name} : {query_planner['namespace']} : {event.command.get('deletes', {})}"
                config.app_log.warning(message)
                config.mongo.async_db.unindexed_queries.append(message)
        elif event.command.get("updates", {}):
            query_planner = explain_result.get("queryPlanner", {})
            winning_plan = query_planner.get("winningPlan", {})
            input_stage = winning_plan.get("inputStage", {})
            used_indexes = input_stage.get("indexName", False)
            if not used_indexes:
                message = f"Unindexed query detected: {event.command_name} : {query_planner['namespace']} : {event.command.get('updates', {})}"
                config.app_log.warning(message)
                config.mongo.async_db.unindexed_queries.append(message)
        return used_indexes


# Register the profiling listener
listener = DeuggingListener()
