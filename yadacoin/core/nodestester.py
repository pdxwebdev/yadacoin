import asyncio
import aiohttp
import socket
import time

from yadacoin.core.config import Config
from yadacoin.core.nodes import Nodes

class NodesTester:
    """
    Masternode tester that checks node availability via HTTP `/get-status`.

    - `successful_nodes` – nodes that passed the test.
    - `failed_nodes` – nodes that had temporary problems (will be retested).
    - `permanently_failed_nodes` – nodes without DNS or HTTP (will not be retested).
    - `all_nodes` – full list of all known nodes.
    """
    all_nodes = []
    successful_nodes = []
    failed_nodes = set()
    permanently_failed_nodes = set()

    @classmethod
    async def test_all_nodes(cls, block_index):
        """
        Tests all masternodes (MN) via HTTP and returns a list of valid ones.

        - Each node is checked for `/get-status` availability.

        - Nodes without DNS or HTTP-port are moved to `permanently_failed_nodes` and skipped in subsequent tests.

        - Nodes that have not responded for a while are moved to `failed_nodes` and will be tested again.

        If no node passes the test:
        - `nodes_to_test` are used (i.e. tested nodes).

        - If `nodes_to_test` is also empty (e.g. no internet), `all_nodes` are used (all known nodes).

        Test results are written to MongoDB (`tested_nodes`).

        """
        config = Config()
        semaphore = asyncio.Semaphore(10)

        nodes = Nodes.get_all_nodes_for_block_height(block_index)
        nodes_to_test = [node for node in nodes if node.host not in cls.permanently_failed_nodes]

        tasks = [cls.test_node(config, node, semaphore) for node in nodes_to_test]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_nodes = [node for node in results if node is not None]
        failed_nodes = len(nodes) - len(successful_nodes)

        cls.successful_nodes = successful_nodes
        cls.all_nodes = nodes

        config.app_log.info(
            f"Node testing completed: {len(successful_nodes)} successful, {failed_nodes} failed, Total Nodes: {len(nodes)}"
        )

        if not successful_nodes:
            config.app_log.warning("No nodes passed the test. Falling back to all tested nodes.")
            cls.successful_nodes = nodes_to_test
            cls.failed_nodes = set()

        if not nodes_to_test:
            config.app_log.warning("No internet access detected! Using all known nodes.")
            cls.successful_nodes = cls.all_nodes
            cls.permanently_failed_nodes = set()
            cls.failed_nodes = set()

        await config.mongo.async_db.tested_nodes.replace_one(
            {"_id": "latest_test"},
            {
                "test_time": time.time(),
                "successful_nodes": [node.to_dict() for node in cls.successful_nodes],
                "failed_nodes": list(cls.failed_nodes),
                "permanently_failed_nodes": list(cls.permanently_failed_nodes),
            },
            upsert=True
        )

        return successful_nodes

    @staticmethod
    async def test_node(config, node, semaphore):
        """
        Tests a single masternode (MN) over HTTP.

        - Checks if the node has DNS and if the HTTP-port is working.
        - Sends a query to `/get-status` to check the node type (`peer_type`).
        - If the type matches, the node passes the test.
        - If the `peer_type` does not match, the node is rejected.
        - Nodes without DNS or HTTP are moved to `permanently_failed_nodes` and will not be tested again.
        - Nodes that had temporary problems go to `failed_nodes` and will be tested in the next iterations.

        """
        async with semaphore:
            if node.host in NodesTester.permanently_failed_nodes:
                return None

            if not await NodesTester.has_dns(node.host):
                config.app_log.warning(f"No DNS found for {node.host}, skipping permanently.")
                NodesTester.permanently_failed_nodes.add(node.host)
                return None

            if not node.http_port or not node.http_protocol:
                config.app_log.warning(f"Missing HTTP info for {node.host}, skipping permanently.")
                NodesTester.permanently_failed_nodes.add(node.host)
                return None

            url = f"{node.http_protocol}://{node.host}:{node.http_port}/get-status"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("peer_type") == node.peer_type:
                                config.app_log.info(f"{node.host} PASSED as {node.peer_type}")
                                return node
                            else:
                                config.app_log.warning(f"{node.host} returned wrong type {data.get('peer_type')}, expected {node.peer_type}")
            except Exception as e:
                config.app_log.warning(f"Failed {node.host} (temporary failure): {e}")
                NodesTester.failed_nodes.add(node.host)

            return None

    @staticmethod
    async def has_dns(host):
        """
        Checks if the host has a valid DNS record.

        - If the host has DNS → returns `True`
        - If it doesn't → returns `False` and marks the node as `permanently_failed`
        """
        try:
            socket.gethostbyname(host)
            return True
        except socket.gaierror:
            return False
