"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import json
import time
import traceback
import uuid

from tornado.iostream import StreamClosedError

from yadacoin.core.config import Config
from yadacoin.core.miner import Miner
from yadacoin.core.peer import Peer
from yadacoin.core.processingqueue import NonceProcessingQueueItem
from yadacoin.core.transactionutils import TU
from yadacoin.tcpsocket.base import RPCSocketServer


class StratumServer(RPCSocketServer):
    current_header = ""
    config = None

    def __init__(self):
        super(StratumServer, self).__init__()
        self.config = Config()

    @classmethod
    async def block_checker(cls):
        if not cls.config:
            cls.config = Config()

        if time.time() - cls.config.mp.block_factory.time > 600:
            await cls.config.mp.refresh()

        if cls.current_header != cls.config.mp.block_factory.header:
            try:
                await cls.send_jobs()
            except:
                cls.config.app_log.warning(traceback.format_exc())

    @classmethod
    async def send_jobs(cls):
        if not cls.config:
            cls.config = Config()
        for miner in list(StratumServer.inbound_streams[Miner.__name__].values()):
            for stream in miner.values():
                try:
                    await cls.send_job(stream)
                except:
                    cls.config.app_log.warning(traceback.format_exc())

    @classmethod
    async def send_job(cls, stream):
        job = await cls.config.mp.block_template(stream.peer.agent, stream.peer.peer_id)
        stream.jobs[job.id] = job
        cls.current_header = cls.config.mp.block_factory.header
        params = {
            "blob": job.blob,
            "job_id": job.job_id,
            "target": job.target,
            "seed_hash": job.seed_hash,
            "height": job.index,
            "extra_nonce": job.extra_nonce,
            "algo": job.algo,
        }
        rpc_data = {"jsonrpc": "2.0", "method": "job", "params": params}
        try:
            cls.config.app_log.info(f"Sent job to Miner: {stream.peer.to_json()}")
            cls.config.app_log.debug(f"RPC Data: {json.dumps(rpc_data)}")
            await stream.write("{}\n".format(json.dumps(rpc_data)).encode())
        except StreamClosedError:
            await StratumServer.remove_peer(stream)
        except Exception:
            cls.config.app_log.warning(traceback.format_exc())

    @classmethod
    async def update_miner_count(cls):
        if not cls.config:
            cls.config = Config()
        await cls.config.mongo.async_db.pool_stats.update_one(
            {"stat": "worker_count"},
            {
                "$set": {
                    "value": len(StratumServer.inbound_streams[Miner.__name__].keys())
                }
            },
            upsert=True,
        )
        await cls.config.mongo.async_db.pool_stats.update_one(
            {"stat": "miner_count"},
            {"$set": {"value": len(await Peer.get_miner_streams())}},
            upsert=True,
        )

    @classmethod
    async def remove_peer(cls, stream, reason=None):
        if reason:
            Config().app_log.warning(f"remove_peer: {reason}")
        stream.close()
        if not hasattr(stream, "peer"):
            return
        if stream.peer.address_only in StratumServer.inbound_streams[Miner.__name__]:
            if (
                stream.peer.worker
                in StratumServer.inbound_streams[Miner.__name__][
                    stream.peer.address_only
                ]
            ):
                del StratumServer.inbound_streams[Miner.__name__][
                    stream.peer.address_only
                ][stream.peer.worker]
            if (
                len(
                    StratumServer.inbound_streams[Miner.__name__][
                        stream.peer.address_only
                    ].keys()
                )
                == 0
            ):
                del StratumServer.inbound_streams[Miner.__name__][
                    stream.peer.address_only
                ]
        await StratumServer.update_miner_count()

    async def getblocktemplate(self, body, stream):
        return await StratumServer.config.mp.block_template(stream.peer.info)

    async def get_info(self, body, stream):
        return await StratumServer.config.mp.block_template(stream.peer.info)

    async def get_balance(self, body, stream):
        balance = StratumServer.config.BU.get_wallet_balance(
            StratumServer.config.address
        )
        return {"balance": balance, "unlocked_balance": balance}

    async def getheight(self, body, stream):
        return {"height": StratumServer.config.LatestBlock.block.index}

    async def transfer(self, body, stream):
        for x in body.get("params").get("destinations"):
            result = await TU.send(
                StratumServer.config,
                x["address"],
                x["amount"],
                from_address=StratumServer.config.address,
            )
            result["tx_hash"] = result["hash"]
        return result

    async def get_bulk_payments(self, body, stream):
        result = []
        for y in body.get("params").get("payment_ids"):
            config = Config.generate(prv=y)
            async for (
                x
            ) in StratumServer.config.BU.get_wallet_unspent_transactions_for_spending(
                config.address, inc_mempool=True
            ):
                txn = {"amount": 0}
                txn["block_height"] = x["height"]
                for j in x["outputs"]:
                    if j["to"] == config.address:
                        txn["amount"] += j["value"]
                if txn["amount"]:
                    result.append(txn)
        return result

    async def submit(self, body, stream):
        self.config.processing_queues.nonce_queue.add(
            NonceProcessingQueueItem(miner=stream.peer, stream=stream, body=body)
        )

    async def login(self, body, stream):
        # if len(await Peer.get_miner_streams()) > self.config.max_miners:
        #     await stream.write(
        #         "{}\n".format(
        #             json.dumps(
        #                 {
        #                     "id": "1",
        #                     "method": "login",
        #                     "jsonrpc": "2.0",
        #                     "error": {
        #                         "message": "Maximum number of miners connected. Please see https://miningpoolstats.stream/yadacoin for more pools."
        #                     },
        #                 }
        #             )
        #         ).encode()
        #     )
        #     await StratumServer.remove_peer(stream)
        #     return
        peer_id = str(uuid.uuid4())
        # await StratumServer.block_checker()
        job = await StratumServer.config.mp.block_template(
            body["params"].get("agent"), peer_id
        )
        if not hasattr(stream, "jobs"):
            stream.jobs = {}
        stream.jobs[job.id] = job
        result = {"id": job.id, "job": job.to_dict()}
        rpc_data = {
            "id": body.get("id"),
            "method": body.get("method"),
            "jsonrpc": body.get("jsonrpc"),
            "result": result,
        }

        try:
            stream.peer = Miner(
                address=body["params"].get("login"),
                agent=body["params"].get("agent"),
                peer_id=peer_id,
            )
            self.config.app_log.info(f"Connected to Miner: {stream.peer.to_json()}")
            StratumServer.inbound_streams[Miner.__name__].setdefault(
                stream.peer.address_only, {}
            )
            StratumServer.inbound_streams[Miner.__name__][stream.peer.address_only][
                stream.peer.worker
            ] = stream
            await StratumServer.update_miner_count()
        except:
            rpc_data["error"] = {"message": "Invalid wallet address or invalid format"}
        self.config.app_log.debug(f"Login RPC Data: {json.dumps(rpc_data)}")
        await stream.write("{}\n".format(json.dumps(rpc_data)).encode())

    async def keepalived(self, body, stream):
        rpc_data = {
            "id": body.get("id"),
            "method": body.get("method"),
            "jsonrpc": body.get("jsonrpc"),
            "result": {"status": "KEEPALIVED"},
        }
        await stream.write("{}\n".format(json.dumps(rpc_data)).encode())

    @classmethod
    async def status(self):
        return {
            "miners": len(
                list(
                    set(
                        [
                            address
                            for address in StratumServer.inbound_streams[
                                Miner.__name__
                            ].keys()
                        ]
                    )
                )
            ),
            "workers": len(await Peer.get_miner_streams()),
        }
