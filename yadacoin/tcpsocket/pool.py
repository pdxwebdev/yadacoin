import json
import time
import traceback
import uuid
import asyncio

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
    block_checker_in_use = False

    def __init__(self):
        super(StratumServer, self).__init__()
        self.config = Config()

    @classmethod
    async def block_checker(cls):
        try:
            if cls.block_checker_in_use:
                cls.config.app_log.info("Skipping block_checker, already in use")
                return

            cls.block_checker_in_use = True

            if not cls.config:
                cls.config = Config()

            if time.time() - cls.config.mp.block_factory.time > 1500:
                await cls.config.mp.refresh()

            if cls.current_header != cls.config.mp.block_factory.header:
                await cls.send_jobs()
        except Exception as e:
            cls.config.app_log.warning(f"Error in block checker: {e}")
        finally:
            cls.block_checker_in_use = False

    @classmethod
    async def send_jobs(cls):
        if not cls.config:
            cls.config = Config()
        tasks = []
        for miner in list(StratumServer.inbound_streams[Miner.__name__].values()):
            for stream in miner.values():
                try:
                    tasks.append(cls.send_job(stream))
                except:
                    cls.config.app_log.warning(traceback.format_exc())
        await asyncio.gather(*tasks)

    @classmethod
    async def send_job(cls, stream, max_retries=3):
        for _ in range(max_retries):
            try:
                job = await cls.config.mp.block_template(stream.peer.agent, stream.peer.custom_diff, stream.peer.peer_id)
                stream.jobs[job.id] = job
                cls.current_header = cls.config.mp.block_factory.header
                params = {"blob": job.blob, "job_id": job.job_id, "target": job.target, "seed_hash": job.seed_hash, "extra_nonce": job.extra_nonce, "height": job.index}
                rpc_data = {"jsonrpc": "2.0", "method": "job", "params": params}
                cls.config.app_log.info(f"Sent job to Miner: {stream.peer.to_json()}")
                cls.config.app_log.debug(f"RPC Data: {json.dumps(rpc_data)}")
                cls.config.app_log.debug(f"Jobs Dictionary: {stream.jobs}")
                await stream.write("{}\n".format(json.dumps(rpc_data)).encode())
                return
            except StreamClosedError:
                await StratumServer.remove_peer(stream, reason="StreamClosedErrorSendJob")
                return
            except Exception as e:
                cls.config.app_log.warning(f"Error sending job: {e}")

        await StratumServer.remove_peer(stream, reason="MaxRetriesExceeded")

    @classmethod
    async def update_miner_count(cls):
        if not cls.config:
            cls.config = Config()

        unique_miner_addresses = set()
        for peer_id, workers in StratumServer.inbound_streams[Miner.__name__].items():
            for (address_only, worker) in workers:
                unique_miner_addresses.add(address_only)

        await cls.config.mongo.async_db.pool_stats.update_one(
            {"stat": "miner_count"},
            {
                "$set": {
                    "value": len(unique_miner_addresses)
                }
            },
            upsert=True,
        )
        await cls.config.mongo.async_db.pool_stats.update_one(
            {"stat": "worker_count"},
            {
                "$set": {
                    "value": len(await Peer.get_miner_streams())
                }
            },
            upsert=True,
        )

    @classmethod
    async def remove_peer(cls, stream, reason=None):
        if reason:
            Config().app_log.warning(f"remove_peer: {reason}")

        if hasattr(stream, "peer") and hasattr(stream.peer, "peer_id"):
            peer_id = stream.peer.peer_id
            Config().app_log.warning(f"Removing peer with peer_id: {peer_id}")

            stream.close()

            if peer_id in StratumServer.inbound_streams[Miner.__name__]:
                del StratumServer.inbound_streams[Miner.__name__][peer_id]

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
            async for x in StratumServer.config.BU.get_wallet_unspent_transactions(
                config.address
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
        await self.config.processing_queues.nonce_queue.add(
            NonceProcessingQueueItem(miner=stream.peer, stream=stream, body=body)
        )

    async def login(self, body, stream):
        if len(await Peer.get_miner_streams()) > self.config.max_miners:
            await stream.write(
                "{}\n".format(
                    json.dumps(
                        {
                            "id": "1",
                            "method": "login",
                            "jsonrpc": "2.0",
                            "error": {
                                "message": "Maximum number of miners connected. Please see https://miningpoolstats.stream/yadacoin for more pools."
                            },
                        }
                    )
                ).encode()
            )
            await StratumServer.remove_peer(stream)
            return

        custom_diff = None
        peer_id = str(uuid.uuid4())

        if "@" in body["params"].get("login"):
            parts = body["params"].get("login").split("@")
            body["params"]["login"] = parts[0]
            custom_diff = int(parts[1]) if len(parts) > 1 else 0

        await StratumServer.block_checker()
        job = await StratumServer.config.mp.block_template(
            body["params"].get("agent"), custom_diff, peer_id
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
                custom_diff=custom_diff,
                peer_id=peer_id,
            )
            stream.peer.custom_diff = custom_diff
            stream.peer.peer_id = peer_id
            self.config.app_log.info(f"Connected to Miner: {stream.peer.to_json()}")
            
            StratumServer.inbound_streams[Miner.__name__].setdefault(
                peer_id, {}
            )
            StratumServer.inbound_streams[Miner.__name__][peer_id][
                stream.peer.address_only, stream.peer.worker
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
    async def status(cls):
        unique_miner_addresses = set()
        for peer_id, workers in StratumServer.inbound_streams[Miner.__name__].items():
            for (address_only, worker) in workers:
                unique_miner_addresses.add(address_only)

        return {
            "miners": len(unique_miner_addresses),
            "workers": len(await Peer.get_miner_streams()),
        }
