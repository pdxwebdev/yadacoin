"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

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
        self.pool_db = self.client[self.config.pool_database]
        try:
            # test connection
            self.db.blocks.find_one()
            self.pool_db.pool_blocks.find_one()
        except Exception as e:
            raise e

        __id = IndexModel([("id", ASCENDING)], name="__id", unique=True)
        __hash = IndexModel([("hash", ASCENDING)], name="__hash")
        __time = IndexModel([("time", ASCENDING)], name="__time")
        __index = IndexModel([("index", ASCENDING)], name="__index")
        __to = IndexModel([("transactions.outputs.to", ASCENDING)], name="__to")
        __value = IndexModel(
            [("transactions.outputs.value", ASCENDING)], name="__value"
        )
        __txn_id = IndexModel([("transactions.id", ASCENDING)], name="__txn_id")
        __txn_hash = IndexModel([("transactions.hash", ASCENDING)], name="__txn_hash")
        __txn_inputs_id = IndexModel(
            [("transactions.inputs.id", ASCENDING)], name="__txn_inputs_id"
        )
        __txn_id_inputs_id = IndexModel(
            [("transactions.id", ASCENDING), ("transactions.inputs.id", ASCENDING)],
            name="__txn_id_inputs_id",
        )
        __txn_id_public_key = IndexModel(
            [("transactions.id", ASCENDING), ("transactions.public_key", ASCENDING)],
            name="__txn_id_public_key",
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
        __txn_rel_smart_contract_expiry_txn_time = IndexModel(
            [
                ("transactions.relationship.smart_contract.expiry", ASCENDING),
                ("transactions.time", ASCENDING),
            ],
            name="__txn_rel_smart_contract_expiry_txn_time",
        )
        __txn_prerotated_key_hash = IndexModel(
            [
                ("transactions.prerotated_key_hash", ASCENDING),
            ],
            name="__txn_prerotated_key_hash",
        )
        __txn_twice_prerotated_key_hash = IndexModel(
            [
                ("transactions.twice_prerotated_key_hash", ASCENDING),
            ],
            name="__txn_twice_prerotated_key_hash",
        )
        __txn_public_key_hash = IndexModel(
            [
                ("transactions.public_key_hash", ASCENDING),
            ],
            name="__txn_public_key_hash",
        )
        __txn_prev_public_key_hash = IndexModel(
            [
                ("transactions.prev_public_key_hash", ASCENDING),
            ],
            name="__txn_prev_public_key_hash",
        )

        try:
            self.db.blocks.create_indexes(
                [
                    __hash,
                    __time,
                    __index,
                    __id,
                    __to,
                    __value,
                    __txn_id,
                    __txn_hash,
                    __txn_inputs_id,
                    __txn_id_inputs_id,
                    __txn_id_public_key,
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
                    __txn_rel_smart_contract_expiry_txn_time,
                    __txn_prerotated_key_hash,
                    __txn_twice_prerotated_key_hash,
                    __txn_public_key_hash,
                    __txn_prev_public_key_hash,
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
        __rel_smart_contract = IndexModel(
            [("relationship.smart_contract", ASCENDING)], name="__rel_smart_contract"
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
                    __rel_smart_contract,
                ]
            )
        except:
            pass

        __id = IndexModel([("txn.id", ASCENDING)], name="__id")
        __hash = IndexModel([("txn.hash", ASCENDING)], name="__hash")
        __index = IndexModel(
            [("index", DESCENDING)],
            name="__index",
        )
        __outputs_to = IndexModel([("txn.outputs.to", ASCENDING)], name="__outputs_to")
        __outputs_to_index = IndexModel(
            [("txn.outputs.to", ASCENDING), ("index", DESCENDING)],
            name="__outputs_to_index",
        )
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
                    __index,
                    __outputs_to,
                    __outputs_to_index,
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
        __timestamp_archived = IndexModel(
            [("timestamp", DESCENDING), ("archived", ASCENDING)],
            name="__timestamp_archived",
        )
        try:
            self.db.node_status.create_indexes(
                [__timestamp, __archived, __timestamp_archived]
            )
        except:
            raise

        __time = IndexModel([("time", ASCENDING)], name="__time")
        __stat = IndexModel([("stat", ASCENDING)], name="__stat")
        try:
            self.db.pool_stats.create_indexes([__time, __stat])
        except:
            raise

        __time = IndexModel([("time", DESCENDING)], name="__time")
        __date = IndexModel([("date", DESCENDING)], name="__date", expireAfterSeconds=90000)
        try:
            self.pool_db.pool_hashrate_stats.create_indexes([__time, __date])
        except Exception as e:
            self.config.app_log.error(f"Error creating indexes for pool_hashrate_stats: {e}")

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
        self.async_pool_db = self.async_client[self.config.pool_database]
        self.async_db.slow_queries = []
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

        potentially_missing_block = too_high_reward_blocks = self.db.blocks.find_one(
            {"index": 516355}
        )
        if not potentially_missing_block:
            self.db.blocks.insert_one(
                {
                    "version": 5,
                    "time": 1731645792,
                    "index": 516355,
                    "public_key": "0295c2c3d504d4690a3fcb0b72e51d1e17aa52c120961027c652ebef9a8ffafcdb",
                    "prevHash": "47dded793d644cb602eb375d27694d2d05eb294ddfeb4f87ff17493504000000",
                    "nonce": "c53f0800214696",
                    "transactions": [
                        {
                            "time": 1731644667,
                            "rid": "",
                            "id": "MEQCIF9fmDjq3gKB3nocz72OonsZYxPVqkfVdfJr0w1lMwuqAiA/lEiE8h2BkFjQUBC8Lvk9zrz4uklXGBph+5Bdgo2MVw==",
                            "relationship": "12gJFegnUNmL9h5mkExzwsJfiNyTGQbsde",
                            "relationship_hash": "743d44ab9ff39f097cceec1689a99217564d9e6a61077fa7308d1ae021b901e4",
                            "public_key": "03a72fc4e18c8cab3357c461bcf1377d444f802807398996f09238e99b5e40b67f",
                            "dh_public_key": "",
                            "fee": 10.0,
                            "masternode_fee": 10.0,
                            "hash": "7ee78467e0ad5d2752470135ced9016611c5b39be9e127b8b4134702ebcd2dd3",
                            "inputs": [
                                {
                                    "id": "MEUCIQDJGDah923DbUNoubvHWAFI5Ur3zcvbkST2m3PjQ0G3tAIgaa+kBr7d2zvFcgjpH1EwJLOQWU9iGLzbh5/8GnAcRP4="
                                },
                                {
                                    "id": "MEUCIQDd2jAAtREMQP6nPa+cKdA9KMtsYQnpnJZjTMFYc/kA9wIgJWN7Un9KAemQWkHKdwHmAsdrS3vJH6Gkok/EujILiwc="
                                },
                                {
                                    "id": "MEQCIDflNFTX0IMfMR5Hkh21T9J7jKHrV8UN2FlVetTncazVAiAGM3Wk/Vtonw1DsN1esOOYCpNYvPH+Uv0emzz9vBmLJw=="
                                },
                                {
                                    "id": "MEQCIBEI8AZ2vPzMTyxC9eVFzSO7fT4ekZ0jndNrwl0M3XX+AiA96w+s6hMAdcZFCKNFn8zWstfxeVFe2DeXA8GKGFsXSg=="
                                },
                                {
                                    "id": "MEUCIQC0db37xfhz/v9PgnteICaoI7ig2nNsN35uo08CFX+TYwIgFpZWcBawii8aRZijeTRVaUfJVCJDYtNbjnG0AblTHKs="
                                },
                                {
                                    "id": "MEQCIAGNAEeL6BJWQsXSWlS1xarI52nz5s5I0b9QEiPNHw/cAiAcPNTBUd/3CWq/5/HPhQSSIDTC+0sr/2LOwpZk37ZI6Q=="
                                },
                                {
                                    "id": "MEQCIHCjcrOxPTu/5IUclVuUacxLli56gE39aOy5rmn7H9HUAiBCI4jnBaWfGL1dgDAuh3KtHikQr6lzYShVBjkR+65UgA=="
                                },
                                {
                                    "id": "MEUCIQCtZeyccQoJSRjmeimFtMohQNCH8V3eRmIQV95h4h+JDwIgZGiJi6u/5bo3WqKNPSmfslgcRvj2ys7q3mPcmBQ5zOo="
                                },
                                {
                                    "id": "MEQCIEe8oiF62qm8XsYVuwNa71rL4QOy0wB1bfRJcVtEZ6GRAiBBH1sRUbla3ARjmHcdL/cS+6SdVpmj+B1o3wh7SWbaBw=="
                                },
                                {
                                    "id": "MEUCIQC5uHeLIIZ83TudRRCrCxlxJigB+HEEN2uZBHBX81iDAwIgU6cChbMGzeX/N1wid4ZiX/iuFmRlLrxiBee4w3gz+2E="
                                },
                                {
                                    "id": "MEUCIQDmpLHCHOrDQm9k4TnAbkv65NSBQRHuX9hGZ2xztQ7z7QIgB18uhmuZ3mz8XlpYMesH7dWvnVJv80YoChJhglFXLag="
                                },
                                {
                                    "id": "MEQCIDbmqSYjv6ieni3ebawvZpFF8UB/UU2bqR/JIQEP8f5dAiBdXj7JWSQceYVOYCF88PnTv2/XkmzMfjmsoeMv9fySpA=="
                                },
                                {
                                    "id": "MEUCIQDQatB/rpV0rPGNJBTryGbXXaKRjAlQnKTIEUW2Lq6yaQIgIsyoPgSHUp9aSrJNaTts+l5a+O/YI5J3XTNbGDwnuvM="
                                },
                                {
                                    "id": "MEQCIFRhivDLgIFkz2zQ0CQHt0GEE5Q21yNBHkezQrQln7jlAiB/NAjqM/+UkNQ7sybsxlVVO0vnPokbcsG++xSP4qn6wA=="
                                },
                                {
                                    "id": "MEQCIEbwY5SgZSjsDyzL4epKL4x2xeLkUJUo9WadJUxNaG60AiBJriFlub2rRFFFUCMohrMwdhl2wZjLL1m706u+hi6zbw=="
                                },
                                {
                                    "id": "MEUCIQD/1FBXI70NIGgbiOjR5gKiBLctvHQtKnis1jcOvvUGZwIgGtKiHcxXVp3+rYktLZx0MqhJzl8zwC0EJK4cvegX/Cg="
                                },
                                {
                                    "id": "MEQCIHvc/NlGkV1p3yw3viR9InzMrlI/E3cgYU1m/8EgBfDCAiApcmmKj7CQkd80qVY+PTSTcDWpGVD6unKsYrTAldmsEg=="
                                },
                                {
                                    "id": "MEUCIQC53OC+NR7NpkC6S54M+BU0hccb3yoYSvkd8bfybtMX1QIgHEjPT0FSty0AsqFCd5z7RZkwvL7CK5j8msBDWbYKEGM="
                                },
                                {
                                    "id": "MEQCIDziaP/XJQgtnSLphVDP7/fdh6IkcLrXnKreDU+c5WR3AiBE8o2pwlJlrcr5ZFlMaU4NGntU4v3KzFWn7Oz5knZFAQ=="
                                },
                                {
                                    "id": "MEUCIQCJ8VL/+n1zIugmn4tfKOHiP5ofWD6pTkX10x+6xMqBKAIge/7mdXU5EibnajPbicmFWlFg6ZvUq313sl3mPO25MWE="
                                },
                                {
                                    "id": "MEQCIBBSFjmPqC0Epox2+0T+9CgSoNC9aziGrSq2Cj5vVA8NAiAEmV8pyMRy5eSDPvV/WbbOXvtJthzKIp+mZl6Y/TcDvA=="
                                },
                                {
                                    "id": "MEUCIQDtq5PdYDG9022CAH2CFleDZhtaO3tvzhTeLbBVd8gB+QIgUgYw59UqGwjyJcSj0DYKEqUUaGd0l+0GDTEU92EsM5k="
                                },
                                {
                                    "id": "MEUCIQCzuLnGXgMZQHrQ/CGJgzO1m29wH1HQhX/BhoIw1ydaigIgQ+QMiW87s4dbQZuSywMRvJrgDlRIoJk7qMe4sJ40Oec="
                                },
                                {
                                    "id": "MEUCIQCM23h1MMEtUrZy1MB/6OYu8FPdipfOuuS4DxuTy9t+AgIgD3Iu3uytONO7qrFPCMF145P1XVt6avlm+cayCeowC5U="
                                },
                                {
                                    "id": "MEQCIB1IQJfEpTGwiOttnsPMg0OoHezhKiiGnMwyEyHBg5w0AiA2rdOfk+V+8ZHAkXug9fkaC79pSGT7d7nqQrIQMf7D2g=="
                                },
                                {
                                    "id": "MEQCIEGM6hkMGJpcRZGzu/gdY2rLN5xOYD2sBCwE7zexJoJgAiALIEbwCw7SdrdxFrgKBoIY6cTiU7WlvhcpL4/0gWZZUg=="
                                },
                                {
                                    "id": "MEQCICV83sxn2EUYcqNCSFXAJ4rRTOlfs9SsmrsKD1w8yP0IAiAemylPUIVF6bdbF4Sc6uGiZDQFc5xL1RicZt3JjyEDkA=="
                                },
                                {
                                    "id": "MEUCIQDvKFQd7xs/Rv104ynD6iQHBV2KrN1wY1GS4uAMv3uO2QIgHpmiSnKooq+eAZ3qmygGn9gxDm8hdW+TXEpGwuMIKsk="
                                },
                                {
                                    "id": "MEQCICAEu3n/tAZNUMEWk943NcRUtcXf8FFjuSiAFTyRpbpUAiACIYz4FKYZ4zRbEYXpZHKKEFE4YZ/3QEHJTZDfghTlVg=="
                                },
                                {
                                    "id": "MEUCIQChdwZ4ON1Pwf2vyCz9+j6k4kCrV++Ng216EPEu2q/TWAIgJiB6oeQMdNlpdYuEVAMSczkCEHrhI4opkgI7riBnuRA="
                                },
                                {
                                    "id": "MEQCIBIBWGDUGZ7wG9ok/1NsuSlCyd5FBFof62/2G4Y2F6osAiATYmgevN6SvdVkcbcviOHj9aDaVBFI7e2VKj5jA9Soxw=="
                                },
                                {
                                    "id": "MEUCIQDCxFwS9wqjUErw+cUgTj8ck95UPFyhz0KMsZgJ9TT0kwIgWe68xOO9CIYB0lde6DGmkSqv7bZvTxcgIKfkE6FYr3w="
                                },
                                {
                                    "id": "MEUCIQCoS47VD3nR1JqnkjKUwlVqECPCf2c8psKiCZhMYGmK+wIgPiSzxrteMwDMHvEIk1RhAF9wbKDMeImzAnNcEgRmvT4="
                                },
                                {
                                    "id": "MEQCIDELWMXjZD0bNwoGjLAHylGNHfVUHwvdttChR+Yuz5d7AiA0fZIrupZBmxXwzgDozp0KP3qyCY59BvzHAVx7HGBmaA=="
                                },
                                {
                                    "id": "MEQCIFUUnAeYtlK4WVSYr6ZMKCyLke9ooTI63qaYBp3QYbgrAiApK+6ozOMuZbNfaj16soHgxgHFZiA5kzF9ObUhnuHMtQ=="
                                },
                                {
                                    "id": "MEQCIF7njjkRTD1o5cp2yvusUhErDXerQKjSog43j428IsmMAiBlRDperAxzLV2j0RxQQowBz8aeWbruPXGLmLvPl+gXhQ=="
                                },
                                {
                                    "id": "MEUCIQCjqfAaTu3dliyaklcEOq3ZeCdl+EG1ZldC08KIeHx/5wIgfeJgXPDWOJcIU/iJkWvoY+js5JGTGkA9pqgv9zWXZSk="
                                },
                                {
                                    "id": "MEUCIQCujYMaNrxtxXP8Gi+9op4FZsVl4o9gZdDElcNwopzeFwIgGBsMh6SXLUCzzDhzO14MBsDnah3IDVZLO7winpTT8IE="
                                },
                                {
                                    "id": "MEQCIDjwmDPQlTyW5OLm7SGsasfpzY6DrB81fiu7AB2UJOP3AiAP/GjyZsWPCadjg1GBtWf1JzhMG8eR3BNb/Jl86iIJIg=="
                                },
                                {
                                    "id": "MEUCIQDq+oadkjXYtoA6SoL2sDu2ugKfFVYNCZxnnGjguhggnQIgEwQWn1fBSRxAYBWB+HOrUYuZzZLXJCySXvkVPzD2s4c="
                                },
                                {
                                    "id": "MEQCIGcwn8yQZMS+o2VJZVJ37I3Sya7aSSVD2SZehEHEfYmCAiB0gHhQJijIj8w57MZhJWJY6pVMHhhpGIg1a1YkIvZyPg=="
                                },
                                {
                                    "id": "MEQCIF1oMYmocWxe0Mzh0tzVExjfqH5FC1SsA7592DGXgw1PAiAHivXB9yReNdp8095FicFd47QoTRkMbV3NIcpRNtYKgw=="
                                },
                                {
                                    "id": "MEQCICmavVHeygVoU/vCLtCGRAJx8yqmywcHOlIev98sogYpAiBdTURNj3Z6PjOHEUNnGsTQw6ANExI7hPPeh1jhIxzBeQ=="
                                },
                                {
                                    "id": "MEQCIAHX8OuDwugLru0h7BHe8Md4og8+ZCsJj75RdaeJkq7MAiBlPYSO8twxIANQpu9u++IqIwxJrEf43CWHaVY8K74EdA=="
                                },
                                {
                                    "id": "MEUCIQCmCcBTYnDt6oPw8awtaeX8j35YCZTC0ed6WGVOCT8cgwIgJrpLpWJdFVBMVIQwATvr+drp58RIgoV7xA1MFen3bjY="
                                },
                                {
                                    "id": "MEUCIQCvdmTQTuRWl8eGjwyfkmVxfNofi+BXLfvSdsxmbbTEwgIgEz83YLOq7pTA2tBC7ikFQisRiaiTi3csaEAdDZH9izI="
                                },
                                {
                                    "id": "MEUCIQCdCJRzpEAIh/SvZotu9NlN05F/JzlN4iB61HTz9w8RjQIgcC9tss+SKIHUXbgoZgZn3K+Rhh82MC4TjseevmPOJnU="
                                },
                                {
                                    "id": "MEQCICOYvVWgTO7vLhUVkdvreGgQsnAifVYf/d66+F4pIDrvAiA3JsgqD52MG223KHBqjoRF+cb1EZkbQuJYhNpe0E8E7g=="
                                },
                                {
                                    "id": "MEQCIBvehpkfpX3bDGCcERFfBbnQbfHEd8TFnIDuj2h24zmbAiA3Y+hR6CjFgNr4dum73FcBOqLwVATKm/YmyFVo1Xem8A=="
                                },
                                {
                                    "id": "MEUCIQC5f+iM4MZMyfHSkB8LcrP1SG8+vVIg1zhD4kBFsvaH3QIgN0Dj7yQPxzgMZnUANMHtk8Gor9+S900RAcI7kzRu6TI="
                                },
                                {
                                    "id": "MEUCIQC0mqLvuWQsZ9o7xTg0kSTDyE2jWq44gpJKBCWYuifGcAIgV/hORWOXV2BsjGfvLiGYGQTxgZazCgXFk6TE+ZQJWgs="
                                },
                                {
                                    "id": "MEQCIA8YfdZOIzxOvpEfRPtaXA7z6ljbKgph7aj9yBe2J47TAiAK0cDmoTSoAlsfsj5uCgI2AX5b+lbykOOnyo7wgUyQmw=="
                                },
                                {
                                    "id": "MEQCIBE88WJVVstnzD0rlL3xPZ7miub7FlIiRKyJ+qbkwrosAiAcWhErEcRWb/x3aKQzJr2UPc8qjSYSvPZe/trqXIb8fQ=="
                                },
                                {
                                    "id": "MEQCIF9wtoso8MvpFB/vDXptc4LWaujZTEzqUeAx6iZp99rxAiBfhycNOfoZNb1rWqxs0rVKomEvAj83U5Ayi27BLHdAUQ=="
                                },
                                {
                                    "id": "MEUCIQCUIxhCIOCmUBwT0vmt+7cGOdSx5vA4+fQoTQExkSGexQIgXhsPCcocOzWT8x+kxBniTJL2sP4ibb35rX80PsZjNQk="
                                },
                            ],
                            "outputs": [
                                {
                                    "to": "1HheDzfG82z13xzgMjC841ch8Z34eFtngG",
                                    "value": 200,
                                },
                                {
                                    "to": "18zQjpRyjnneZ5G5N2R833NjPGeiuiRVwW",
                                    "value": 0.9647920865280071,
                                },
                            ],
                            "version": 5,
                            "private": False,
                            "never_expire": False,
                        },
                        {
                            "time": 1731645044,
                            "rid": "",
                            "id": "MEUCIQCxAiUQF85n8gDSWP86liigSvnBx5eoIncbHhYF4KtfxgIgEWfYArA3+BBDNhXfRMvKm+0ZDE3uhQtjA0mInokK4bg=",
                            "relationship": "12gJFegnUNmL9h5mkExzwsJfiNyTGQbsde",
                            "relationship_hash": "743d44ab9ff39f097cceec1689a99217564d9e6a61077fa7308d1ae021b901e4",
                            "public_key": "03a72fc4e18c8cab3357c461bcf1377d444f802807398996f09238e99b5e40b67f",
                            "dh_public_key": "",
                            "fee": 10.0,
                            "masternode_fee": 10.0,
                            "hash": "e781474af79d44abccb32b54642ebd381e86aa61e820a6669c5003a2ad087fb7",
                            "inputs": [
                                {
                                    "id": "MEUCIQD0WdSblfj07KNu/MaRGEffxdQ1v0eTA+ua3SXSuWzgIwIgSEkv2CFdQR2VY8T/dC9miX7oawACfHbZksmsQVXITbM="
                                },
                                {
                                    "id": "MEUCIQCfUz17aGJKUa6hm0Tk3G+i+6FhS8IJZVcQO2kjnfji6gIgNrwEMfJtpqkuV058MLYpSuL74ljfvbEcC8PNpFOlNNA="
                                },
                                {
                                    "id": "MEUCIQDWBMMbe5TEnhR6eT/KHAsQ1iSOkAKF0AX1J2nMFq5TnAIgPBi50XEI4szXjC06HkdjawyhMt6RUtqEV1Phg40koXI="
                                },
                                {
                                    "id": "MEQCIFH+mrLigqPFFHCjLsxTRLf1HbQk/lBftIxKz/hwdniKAiBexWCPD86aXY1MWs0H+WhkpgK2ADcKda6SFTaoGT0XZw=="
                                },
                                {
                                    "id": "MEQCIGjQHSMcsn/OS9tTtQI5awMkkJyPIIwuCngAht2y8E8IAiBXzDKS+Vz14IJKxd85Jvje/DFRLNrs2o2xrUzoiy33DA=="
                                },
                                {
                                    "id": "MEQCICFL4RD0uRNS9Hc6D+KtPR2bWRhAfxibHZp5xnMYpJ+AAiAEEG6CwtrAINGlg0fcHvNIj5hjOpCE/uNEaf95RZou6Q=="
                                },
                                {
                                    "id": "MEUCIQCvPXE+utWS/ScmgtHT8PpxrauiYBBRpd9/WCymBS6DnAIgPD8V1sni2HPtp5a1BjcamZscu5DR2L9LIfXjLyO4rBU="
                                },
                                {
                                    "id": "MEUCIQDmQXtdCkx8DBDvDLG8B6GoG9YkP8Sr28BmLSb8NI3v8gIgJYEKJqcFD3LgyQP9vvafcPGJOXEaZbBghK0DnVrZAB0="
                                },
                                {
                                    "id": "MEUCIQDsMxtJTRsG8EH1l8LSuE/a8RbizbxLDCZrHSpj7JIhEwIgJ/Vpo0S9usCzhdXkv/Vazq6bUJqOK1PiVHT+KCIu3dY="
                                },
                                {
                                    "id": "MEUCIQC4uWjSOm9F5JvGx7qeQD+9p5R2IUcmja3NJeUo4q2oIAIgeW5lPjF7kVgtrK1JDJbWnuqsEXJPGW+U9ek9QPmxgvE="
                                },
                                {
                                    "id": "MEUCIQDeYTC4kHcJFqdZPVObZPZ2TRzYgZKL5OyuBNB5O6Uy2wIgIktZ6gut4fp0xyo+xwef5vptNt1fj85oz1Dv1cWiHpc="
                                },
                                {
                                    "id": "MEQCIA6BS3I9k/T/7ZiELfTi0LBCruo3xXi+uAV1Eqc4FzQ9AiA3GbYRlPhntlrpb/yJtP29jZ5VwA76EBf+Z2Xso01olg=="
                                },
                                {
                                    "id": "MEQCIBJBMafHlPhPVfq7nA7lQbyo4gCQV9G1mUUZX3IJYaHFAiA8VJO4CFwa+hMZIKIkZjs8BMRMBQsTQ/O9apPe9aSH6g=="
                                },
                                {
                                    "id": "MEQCIBl1494IV0tMroDNaWqp0NIriNOYvP62e3mOwOtQ1DRtAiBNjJZ0NFQGnW6rNqHqPY185jWa+K0OcMxxgWkQnpPl9A=="
                                },
                                {
                                    "id": "MEUCIQCtl3gx0zYg17j1FIyh39G5rnlgK/S3tl0YoFq67U6TYwIgW8irYFOM8t77KfsO3ha4kBGiJVrjt2QlbOix8OkuqbY="
                                },
                                {
                                    "id": "MEQCIDMcjoMpPJ0soiJ+qp69XsS4vKx72bzzyJNLL3xtQLERAiBfYvy9CvGCx73sgTsd32ONz27+JloFale1itmPNqx74Q=="
                                },
                                {
                                    "id": "MEUCIQD/B/rYgLno+tBlb79ibpdnSi9VzYsW2L2OQMQeT22tNgIgMLGwtvbC6lo+LHdiKCFN41NN4R/sl0piL0WNV0t3NiA="
                                },
                                {
                                    "id": "MEUCIQDx/iWl3PfR+KQ90ZfFejyC8yf5eSg8q+vmDMJRgshqTQIgawoGOIhUEhjikSBX4ad+Q2I1VSRKYLfhCVUcn0ifhGc="
                                },
                                {
                                    "id": "MEUCIQCqARtc8Dy04gg6h8136u1Pbs9hQIQxmC79XpUUW5kIWwIgXfpAJ711Y88Xx7m5E7Vr+NjtzlItMCQ48zf5X1DJ2DE="
                                },
                                {
                                    "id": "MEQCIDQmGPKUKu5OureCDD+YqBYA0XvxZ70j2Aj7pOCFyqtQAiBaHkfStKWZNAn+yXFqlbTXNaqlVf5U89AwmqypfHKJnQ=="
                                },
                                {
                                    "id": "MEQCICPZF1oQ6bUpK9K70BUea8ZCrgCu3DYrLFp/+8RVmgcCAiAqF8iT/OW0jcVR5KVPnTs/G+bKbrVvOVzYX7qXhC6uww=="
                                },
                                {
                                    "id": "MEQCIAnlrz3SpPu1apkyrXM9OZVjDej6R9Lzreni2Ff282hfAiAnUdzf9NhgaLKSxxYlpCh+g2eQlk8HoAQsPx0XtY9+Cw=="
                                },
                                {
                                    "id": "MEUCIQCtpR0imUciUImcpWNPpjEHTfIoL2UbxN7a8b8tQFVcAQIgObMYzQ/0LYxmSFRDmQnetd0oSKR69Rd1Vo+F5kYxlik="
                                },
                                {
                                    "id": "MEUCIQCUJeDu9gVTMiLvi9NItd5Og81exvurDKX1VhZkMQlCewIgGFxSUuE0wRheNKi4koZwfXbKpR8pGxQ76HePZujC6yU="
                                },
                                {
                                    "id": "MEQCIAhlazisKc8y9MjHnDMeYYQ6Qx+jB1hhrRYZkJEn9TpVAiADhtpchUkRqoORTK0lIuPtteGvOJkO7mSLiywruZtrzw=="
                                },
                                {
                                    "id": "MEQCIBvMecMdovd65engayzbqjPtwUfef+QAbc+Dwjan8f7tAiBkNU8p25RD7xXXvUlHurMPIKlK6bU4G2nS0huAMZOGGg=="
                                },
                                {
                                    "id": "MEQCIE5Ty9jjKxoeegCAAn/8xcOzOJrXyFz4+a5M8T6t7b6YAiAYqH15RpHIR9Kg/DNWn/BhLsSNx/mEs00wzc5I5podEw=="
                                },
                                {
                                    "id": "MEUCIQDl/nDpekp1Ldg+lBJluLopmnVHvCy/Lx/YOuRXxhPdZAIgUkgEozL2i0PvT+euK2c8CR/vPAyJOTHahhSt0O2T0X0="
                                },
                                {
                                    "id": "MEQCIGO8QLQXQNGuTYpQnIfzhQZw1vDcjkU7kV2fOSWTX/MxAiB7b+2+x5lOFVaIj4ggzkzvCJIBTmfCZ2javMFBEBdMUQ=="
                                },
                                {
                                    "id": "MEUCIQDXv0N3JhCrPCWDHtha6mH43iySrnP0F4Tj2tbpeGhpBQIgIzk7Jh9p5VdMnYoKq4MghgOMsNj1VbJFiT+RwS3wRBE="
                                },
                                {
                                    "id": "MEQCIELx9wFkRx5qy8Fw7qnNaON8KnClP5hZB43RyezLs7X6AiA77oZZyrJwFOd3hP168rVrYeSQzFSs7rTOvKqVR+mPig=="
                                },
                                {
                                    "id": "MEUCIQD+2SXiumzvMNHQp1UL9CmgBKcF6HF2C+f/RF2DcfUyuAIgBM/zlvlFaxg2vEoXZz0zcspLD4S3GA9mPNyMor9p7EQ="
                                },
                                {
                                    "id": "MEQCIAm5WvuRj8YikX+TehseMCG0YeVGpteHsNn1DZM3KMTiAiA4pkgjgmsWIbfM/1UdxuJDMvN0wzNpEKdGMiOlwNmuwA=="
                                },
                                {
                                    "id": "MEUCIQCzyuGPAeZsr69kKvkfr4o2kO8KTjXIbK+YN0lg3AlssQIgc42Mm9HReEXzxcXkBZf9gGEU014RFbXicMaSlH9RhKE="
                                },
                                {
                                    "id": "MEQCIALdT/HVWR+ps7vz/u2mucZhrMWer7ML2M1my/RVMYcgAiBoE/eneYoiyoCVnvvAgpBTG3PQZm6pDycVLiGWWNnF8w=="
                                },
                                {
                                    "id": "MEQCIEaTbwCYPwI+yG9EGrhofq6WjUSZGtUEV/BVmiI391ZLAiAh5MIQOFeonple3j0CPI62cYE8jZ7bbVAykmHer0PMUA=="
                                },
                                {
                                    "id": "MEQCIGVR6lRF2c+w6rZu1SS/tT7UF01DmLJDAL0pyys5EGxAAiAoog+mMxm8RcfOQS171EnPHWcG0QJJSumBdkOlP8XuUw=="
                                },
                                {
                                    "id": "MEUCIQCM7K7CNpxxcLzthRmp8z7n9cvCgdJGOhxr8Ve4idpjqQIgVFZfoc61oAQXYP/PRK1l/R9lGKwEtgzkLcqe4TTwR8M="
                                },
                                {
                                    "id": "MEUCIQCT4esbc+s03YEgQxI+h9AwkNg62boPNOXmNST6iIMgQQIgf7VFeU5kD8iZGC41mqax2nIgcrx+Z1NTPyd2LLF1S6s="
                                },
                                {
                                    "id": "MEUCIQDU3ZyolJWvVN7QDYaY8IG/NYJUXsKepy+0OK4R3TMoNAIgdfDOQwGOuETqNB2N9sZtSoMQotxfUk4+5t6QJL9qefM="
                                },
                                {
                                    "id": "MEUCIQC2s4oie42UVaNlZdoumdhjjjtw96RCHfdAEQxM5bRHKQIgQlsbb7eoIWMdxN1eTsBsyLQuV/6t5mbDXavSVJ/RjZQ="
                                },
                                {
                                    "id": "MEQCIHnHIgWFKyt6zaxeM94lZoER2IJaZFJ7IzwYk5oW4eyxAiATvMqipSbLHvlSExHgOakAQG3hioJP3rChVlwvaRv1GA=="
                                },
                                {
                                    "id": "MEUCIQDKiJ5HmN05xyyAibCKEIHCqRyQUxVf6Gq/qCNVpjZxsQIgcSx2JmtYPCV0PdAGEGRIIwx3FI4ewBFcrAC6ORSmLkA="
                                },
                                {
                                    "id": "MEUCIQC/JiUwdi7yDPY+RixTR4DrIkdyz4kd+A2uEaeyBgR3GgIgM9d+DwZXPeRobEg8m8c8Nuim6fEWUkhNRaKQZ1gDaHU="
                                },
                                {
                                    "id": "MEUCIQC8/bo6kTXUpGRFVc86nLsPy983YSUGB9sYiyuaJ5T8uwIgCkGqOxda3jlh0HbqCr/7PSnHuHVrjSb824ZtN366xFQ="
                                },
                                {
                                    "id": "MEQCIG/6qa22zIoxbVSWETBT+RYrmvSj8S/3+CSrotNTZNXqAiBjK4EiuljeWXjro1LCfm3J1lqnKLUNosnkj9zpUr00Sg=="
                                },
                                {
                                    "id": "MEUCIQCLjkRAKHT9b0KhNfBGgwdE0TIugSyj3RAyhg4KVDFsQQIgf1RtJMQlFg2aF+WZc/fbxt3ZfEZPINstRLGkVBaRvJY="
                                },
                                {
                                    "id": "MEQCIECZ+4q8/HQb7GCGYn4DuNwlxehVqrQx5bMGk21ORZzLAiB9gg50eU55m5/wGzMjJ7Y7O+71olqdtdDUP9CTyBUkEg=="
                                },
                                {
                                    "id": "MEUCIQDdEbHf98onKf4XABMr115CIyZ5gMkkMqias4p5OmoyuQIgUYCw3fomyZVERR1+k3Qyusw1g1iZVXb+W8aQzUl6Njs="
                                },
                                {
                                    "id": "MEUCIQCRpp15saqXaBxOuQ51OfZebuoJ2ktBdYMUGU8Pi4vWZAIgG2jJkKI+jqGaUgy8Z2fbKwA7YNAHpMQM4woa3rBOAUI="
                                },
                                {
                                    "id": "MEUCIQDZsKdgaBO5FD7sWY1G8UVpztD5GJf7lirhQK2SR4FtxgIgFTWxEz63oF/bwfnYR/kPVVD2YRaKtuh2Wji7562sWOM="
                                },
                                {
                                    "id": "MEUCIQC2j1IepZXbHslE4s3qgXTuRe8Bl1Y8Ccz+WPN7wHLs/wIgU7cDi4mvtEHxUQI2LqGjVaWSVjpuI4vo6+7IqMFnlIQ="
                                },
                                {
                                    "id": "MEUCIQDFD9Cav3rtIYOrwME2b0PI4Rd5rvBGuFKxqEHaniLN+wIgfQ1n1LYD/OrSOVquNsFr8ym0dTsqbhVmw/pyhZ3kV4A="
                                },
                                {
                                    "id": "MEUCIQDA2FeBIPg3hwhqPgMqYMU3MHsvM2rtqnrY++1JkAPxJgIgc33O6hj8Ej6e1fZTlKZOBd3yEk4QGwE7mTDK8jRxmZc="
                                },
                                {
                                    "id": "MEQCIB+ZTG68f3x0haTZYpOoEcaWoxcSlEe5zjMPgwCJA6iVAiAy5JkyXi2OggUZ9InsCO/GMltGZkPDhRzSoz4iG90LwQ=="
                                },
                                {
                                    "id": "MEQCIHrCMwBJFnfpLEl3iBDoWETo9zYQl9WL5NqUFV+hQvYnAiAOxK3wbWC8gD/iUnSzqs8xN6mPoiT/P420OF77vXpB6g=="
                                },
                                {
                                    "id": "MEUCIQDfINRAwzMgCycm76bO9fPzu/8qvAoB4nwX9nWIAhRxcAIgeS39z/WDBIPkyd4thyOeqRYRlQ+S9erzpa9N3RogtmA="
                                },
                                {
                                    "id": "MEUCIQD4p2BDXt0iJF79k6lttsaL1GoX0j56027gYTfl+paaqAIgJ0bi9D4kx7SF+yTc09s9uNIUyMxr0pKSPgNBjRGDhSo="
                                },
                                {
                                    "id": "MEUCIQCub1OlXV6m6PX6i2qOyCEVlCSyCSVwmcZEzopb+edX9gIgBpnGoG9T0XPTMpN922Y4SUI+kZz6fGr44LpUdH74hGY="
                                },
                                {
                                    "id": "MEQCIA5u0GwvpWHcg3vMkbDy97CtwboBzONjgWh8eN50lkBZAiAXT4BycOtBQHcPDdoDAp18s+k2QrzIwY+g6n6Wxmae4Q=="
                                },
                                {
                                    "id": "MEQCIAaNXoyWLw79etQfG2ugkZZSEqdnLcepc6GXAaTkYrIXAiA3fqdRCNqAW+cZmWErwKGZXjxa+tlZ100xN8O3cchKQQ=="
                                },
                                {
                                    "id": "MEQCIAPhLaXLREq/x6QLwV+yDS0CiX/N+sOt+jTm5iWsAW7TAiBlz+tYMqkWKjDTqN153AAT7K6jHcY3y9T27nRBlBSygw=="
                                },
                                {
                                    "id": "MEQCICGrI0g5nti6CbQYigpxxDhsvslZVwwd/9/C83iHH/EkAiB1eN0m0UEXgIqLLPZXPN90n6JmbZNSE/Oo38d8m2zeNg=="
                                },
                                {
                                    "id": "MEQCIDfVMucRgM5c6yCCoOrYBb4dsZUt7OhyCddKhWcsnKDkAiAx3OLd0IDseTNptE31dZLU34B8BcrhZCCJESubOvnDBg=="
                                },
                                {
                                    "id": "MEUCIQDdN0yZcdoMdN8dXamg4eCzvy5CmJsVyCrHWfUzKC8jgAIgQyglQcLA5iys0TK0NdrAESAG663zSHtxk2T/cXyKFxc="
                                },
                                {
                                    "id": "MEQCIBFem9O4pDgkw86W+/mqw0Sa7ayE9PylN3VWaMVkracSAiBCeU8dCGEQTu5iy2I1DHjVnsgcEd0zT8Shy5JX1OjNWw=="
                                },
                                {
                                    "id": "MEQCIHdAx5hIqlpfIwQK14UzRODRaiFr3vLyWSXHGoY0vluAAiBlAupe0Ax4yQba3ecFo18LI0yX6zcTHYlxec9MJ37k1g=="
                                },
                                {
                                    "id": "MEQCIAr4ZQcNSPkY7/DPYV4SWIXrVc1v1w+Br/YrQCYCWitwAiBC9hT/xkIEL7xResbhGHOvWBOUyJfkzRzxzTDpPhiCCQ=="
                                },
                                {
                                    "id": "MEQCIFG2Bwe5aO5CApR8JEeMxoWcCSKl3onIJo8NNvRPGYblAiBs9ovGKPVT8j/7RrPl7yFQGuNBD7c0KRuC3fR+Nb2F1w=="
                                },
                            ],
                            "outputs": [
                                {
                                    "to": "1HheDzfG82z13xzgMjC841ch8Z34eFtngG",
                                    "value": 100,
                                },
                                {
                                    "to": "18zQjpRyjnneZ5G5N2R833NjPGeiuiRVwW",
                                    "value": 0.7791345240494678,
                                },
                            ],
                            "version": 5,
                            "private": False,
                            "never_expire": False,
                        },
                        {
                            "time": 1731644946,
                            "rid": "",
                            "id": "MEUCIQCSe5hyKMnaoy+YpUOEzK+D1+PYTJjZKOTcD5MDY+Ch0AIgBeVKz+nKWWA2gy8yCZYBV5h4iQEoaAbFOgAxogBbQK8=",
                            "relationship": "",
                            "relationship_hash": "",
                            "public_key": "03672bfbbf29e31a4429e3bc18240c98f0dcfbdd4e6e12aa70657e2095b7d84425",
                            "dh_public_key": "",
                            "fee": 0.01,
                            "masternode_fee": 0.0,
                            "hash": "07b531b711f1d6d3f177b89dac036e83cb5977a21db68bd9dee64096ee441ee4",
                            "inputs": [
                                {
                                    "id": "MEUCIQDmH3XHEi5kXmr2/qJoX9T44zh3TJGekeXrEhqXfbGEOgIgbDJdXoDyp0UDz1I/ZF+mXf2XQhWL/bzXFS1HrcfTsLQ="
                                },
                                {
                                    "id": "MEUCIQCulwOLcvCEUvltoJmwqbTlxyJFZiOLlYIZXIjh7z871AIgctFQx/re57tf8uGvpj4CwrS+AB8zccYcjZbX/HmUPgA="
                                },
                            ],
                            "outputs": [
                                {
                                    "to": "136g8v7ksWZwpfTCBEB9fbfDJB6qsdYzzb",
                                    "value": 3.6238210561206285,
                                },
                                {
                                    "to": "1Gb5PoaUT83T4UYFrEyfDUUF9rbzo9wJ6m",
                                    "value": 2.462048248283588,
                                },
                                {
                                    "to": "1HaESMe3dyVFpcwdVXkytAbKbBtptbGP7H",
                                    "value": 2.4673836031941945,
                                },
                                {
                                    "to": "1N2FNSMKqeaV47KcTp9GAAWko3Go1QFaiu",
                                    "value": 4.79712299904873,
                                },
                            ],
                            "version": 3,
                            "private": False,
                            "never_expire": False,
                        },
                        {
                            "time": 1731645793,
                            "rid": "",
                            "id": "MEUCIQCWDxtfJwSzUHwj0dAIyaju57FcMq34MgliDXBRJkTHAQIgKWa7kQTlhxHMGe0m7PEpsXQxH/pPzwkRFWiaaFFj+xI=",
                            "relationship": "",
                            "relationship_hash": "",
                            "public_key": "0295c2c3d504d4690a3fcb0b72e51d1e17aa52c120961027c652ebef9a8ffafcdb",
                            "dh_public_key": "",
                            "fee": 0.0,
                            "masternode_fee": 0.0,
                            "hash": "804cd3d63e21926c66ecee8574e04ac97032b2ee82859883854914a0f37c4fd7",
                            "inputs": [],
                            "outputs": [
                                {
                                    "to": "18mitmvJWkwFG9r79uc2QRVb4bHVeqxWTN",
                                    "value": 31.26,
                                },
                                {
                                    "to": "13AYDe1jxvYdAFcrUUKGGNC2ZbECXuN5KK",
                                    "value": 7.083333333333333,
                                },
                                {
                                    "to": "1L7dEh8ckRF4ftP3TUztfJsi8hXL8KUahY",
                                    "value": 7.083333333333333,
                                },
                                {
                                    "to": "1DX4nGHqNgqQRfFHVw6CrtGeENZivh5CvK",
                                    "value": 7.083333333333333,
                                },
                            ],
                            "version": 5,
                            "private": False,
                            "never_expire": False,
                        },
                    ],
                    "hash": "70e5861572d10871c1349c41d564f112ab718a7d2720a220d5c78b170e000000",
                    "merkleRoot": "c2f88306d6c42db5ee38a0c95716f7e0867310deadc09fe7fe9b4361b524a826",
                    "special_min": False,
                    "target": "000000114d54b247544000000000000000000000000000000000000000000000",
                    "special_target": "000000114d54b247544000000000000000000000000000000000000000000000",
                    "header": "517316457920295c2c3d504d4690a3fcb0b72e51d1e17aa52c120961027c652ebef9a8ffafcdb51635547dded793d644cb602eb375d27694d2d05eb294ddfeb4f87ff17493504000000{nonce}000000114d54b247544000000000000000000000000000000000000000000000c2f88306d6c42db5ee38a0c95716f7e0867310deadc09fe7fe9b4361b524a826",
                    "id": "MEUCIQC5J3qKoR6QF5e7h9DmWMB/OU+x+ApASqkykx77FRfdowIgeF+fxe9tudwzZKiJBMTN29XdE64Tf95Y4U0pQoNF04o=",
                }
            )


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
        if not config.mongo:
            return

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

        db = config.mongo.client.get_database(event.database_name)
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
                try:
                    used_indexes = self.get_used_index_from_input_stage(winning_plan)
                except:
                    message = f"Failed getting index information: {event.command_name} : {query_planner['namespace']} : {event.command.get('pipeline', {})}"
                    config.app_log.warning(message)

            if not used_indexes:
                self.handle_unindexed_log(
                    event.command_name,
                    query_planner["namespace"],
                    event.command.get("pipeline", {}),
                )
        elif event.command.get("filter", {}):
            query_planner = explain_result.get("queryPlanner", {})
            winning_plan = query_planner.get("winningPlan", {})
            input_stage = winning_plan.get("inputStage", {})
            used_indexes = input_stage.get("indexName", False)

            if not used_indexes:
                try:
                    used_indexes = self.get_used_index_from_input_stage(winning_plan)
                except:
                    message = f"Failed getting index information: {event.command_name} : {query_planner['namespace']} : {event.command.get('filter', {})}"
                    config.app_log.warning(message)

            if not used_indexes:
                self.handle_unindexed_log(
                    event.command_name,
                    query_planner["namespace"],
                    event.command.get("filter", {}),
                )
        elif event.command.get("deletes", {}):
            query_planner = explain_result.get("queryPlanner", {})
            winning_plan = query_planner.get("winningPlan", {})
            input_stage = winning_plan.get("inputStage", {})
            used_indexes = input_stage.get("indexName", False)
            if not used_indexes:
                self.handle_unindexed_log(
                    event.command_name,
                    query_planner["namespace"],
                    event.command.get("deletes", {}),
                )
        elif event.command.get("updates", {}):
            query_planner = explain_result.get("queryPlanner", {})
            winning_plan = query_planner.get("winningPlan", {})
            input_stage = winning_plan.get("inputStage", {})
            used_indexes = input_stage.get("indexName", False)
            if not used_indexes:
                self.handle_unindexed_log(
                    event.command_name,
                    query_planner["namespace"],
                    event.command.get("updates", {}),
                )
        if used_indexes:
            message = f"Indexes used: {used_indexes} : {event.command_name} : {query_planner['namespace']} : {event.command.get('pipeline', event.command.get('filter', {}))}"
            config.app_log.info(message)
        return used_indexes

    def get_used_index_from_input_stage(self, input_stage, used_indexes=None):
        if used_indexes is None:
            used_indexes = []
        index_name = input_stage.get("indexName", False)
        if index_name:
            used_indexes.append(index_name)
            return True

        interim_input_stage = input_stage.get("inputStage", {})
        if interim_input_stage:
            input_stage = input_stage.get("inputStage", {})
            result = self.get_used_index_from_input_stage(input_stage, used_indexes)
            if not result:
                return False
        interim_input_stages = input_stage.get("inputStages", {})
        if interim_input_stages:
            for input_stg in interim_input_stages:
                result = self.get_used_index_from_input_stage(input_stg, used_indexes)
                if not result:
                    return False
            return used_indexes
        return used_indexes

    def handle_unindexed_log(self, command_name, collection, query):
        if collection.endswith("unindexed_queries") or collection.endswith("_cache"):
            return
        config = Config()
        message = f"Unindexed query detected: {command_name} : {collection} : {query}"
        config.app_log.warning(message)
        flattened_data = self.flatten_data(query)
        config.mongo.db.unindexed_queries.update_many(
            {
                "command_name": command_name,
                "collection": collection,
                **{f"query.{k}": {"$exists": True} for k, v in flattened_data.items()},
            },
            {
                "$set": {
                    "command_name": command_name,
                    "collection": collection,
                    **{f"query.{k}": v for k, v in flattened_data.items()},
                },
                "$inc": {"count": 1},
            },
            upsert=True,
        )

    def flatten_data(self, data, parent_key="", sep="."):
        items = []
        if isinstance(data, dict):
            for k, v in data.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict) or isinstance(v, list):
                    items.extend(self.flatten_data(v, new_key, sep=sep).items())
                else:
                    items.append((new_key, None))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_key = f"{parent_key}{sep}{i}" if parent_key else str(i)
                if isinstance(item, dict) or isinstance(item, list):
                    items.extend(self.flatten_data(item, new_key, sep=sep).items())
                else:
                    items.append((new_key, None))
        return dict(items)


# Register the profiling listener
listener = DeuggingListener()
