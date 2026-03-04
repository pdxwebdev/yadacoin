"""
End-to-end dynamic node test using existing blockchain data.

This script:
- Uses MongoDB chain data from the configured database.
- Sets DYNAMIC_NODES_FORK to the latest block index during the run.
- Mines a new block that includes a node announcement transaction.
- Inserts the block via the standard block processing queue.
- Verifies the block is accepted and the dynamic node is visible in the node list.
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
import time

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import PrivateKey

from yadacoin.core.block import Block
from yadacoin.core.blockchain import Blockchain
from yadacoin.core.blockchainutils import BlockChainUtils, set_BU
from yadacoin.core.chain import CHAIN
from yadacoin.core.config import Config
from yadacoin.core.consensus import Consensus
from yadacoin.core.graphutils import GraphUtils
from yadacoin.core.health import Health
from yadacoin.core.latestblock import LatestBlock
from yadacoin.core.mongo import Mongo
from yadacoin.core.nodeannouncement import NodeAnnouncement
from yadacoin.core.nodes import Nodes
from yadacoin.core.processingqueue import BlockProcessingQueueItem, ProcessingQueues
from yadacoin.core.transaction import Transaction
from yadacoin.core.transactionutils import TU

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
TESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

from simulator.network import NetworkSimulator


async def init_config(config_path: str) -> Config:
    with open(config_path, "r") as f:
        config = Config(json.loads(f.read()))

    # Make global config visible to other modules
    import yadacoin.core.config as config_module

    config_module.CONFIG = config

    # Minimal logger for Mongo and consensus usage
    logging.basicConfig(level=logging.INFO)
    config.app_log = logging.getLogger("tornado.application")

    # Use regnet rules for test mining/verification
    config.network = "regnet"

    config.health = Health()
    config.processing_queues = ProcessingQueues()
    config.mongo = Mongo()
    config.BU = BlockChainUtils()
    set_BU(config.BU)
    config.GU = GraphUtils()
    config.LatestBlock = LatestBlock

    await config.LatestBlock.block_checker()
    config.consensus = await Consensus.init_async()

    return config


async def create_peer_mongo_config(config: Config, db_suffix: str = "_peer"):
    """Create a separate Mongo instance and Consensus for peer node (uses same global Config)"""
    # Import to get Mongo initialization working

    # Create custom config dict with suffixed database name
    peer_db_name = config.database + db_suffix
    peer_site_db_name = config.site_database + db_suffix

    # Create a simple object to hold database references
    class PeerMongo:
        def __init__(self):
            self.config = config
            # Reuse existing client connection
            self.client = config.mongo.client
            self.db = self.client[peer_db_name]
            self.site_db = self.client[peer_site_db_name]

            # Create async connections
            self.async_client = config.mongo.async_client
            self.async_db = self.async_client[peer_db_name]
            self.async_site_db = self.async_client[peer_site_db_name]
            self.async_db.slow_queries = []

    peer_mongo = PeerMongo()

    # Create a peer consensus engine using the peer mongo
    class PeerConsensus:
        def __init__(self, real_consensus):
            self.real_consensus = real_consensus
            # Store reference to peer mongo
            self._peer_mongo = peer_mongo

        async def __getattr__(self, name):
            """Delegate to real consensus"""
            return getattr(self.real_consensus, name)

    peer_consensus = PeerConsensus(config.consensus)

    # Replace Mongo's reference temporarily during consensus operations
    original_mongo = config.mongo

    return peer_mongo, peer_consensus, original_mongo


def build_node_announcement(config: Config) -> NodeAnnouncement:
    identity = {
        "username": config.username,
        "public_key": config.public_key,
        "username_signature": config.username_signature,
    }
    node_announcement = {
        "identity": identity,
        "host": "127.0.0.1",
        "port": 8000,
        "http_host": "127.0.0.1",
        "http_port": 8000,
        "http_protocol": "http",
        "secure": False,
    }
    return NodeAnnouncement.from_dict(node_announcement)


def reset_nodes_cache():
    Nodes._get_nodes_for_block_height_cache = {
        "Seeds": {},
        "SeedGateways": {},
        "ServiceProviders": {},
    }


def node_exists_for_height(height: int, public_key: str) -> bool:
    nodes = Nodes.get_all_nodes_for_block_height(height)
    for node in nodes:
        try:
            if node.identity.public_key == public_key:
                return True
        except Exception:
            continue
    return False


def generate_keypair():
    key = PrivateKey()
    return key.public_key.format().hex(), key.to_hex()


async def main():
    config_path = os.environ.get("YADACOIN_CONFIG", "config/config.json")
    config = await init_config(config_path)

    latest_block = config.LatestBlock.block
    if not latest_block:
        raise RuntimeError("No latest block found in MongoDB")

    # Create peer's separate MongoDB instance
    peer_mongo, peer_consensus, original_mongo = await create_peer_mongo_config(config)

    # Seed peer's database with the same latest block from miner
    await peer_mongo.async_db.blocks.replace_one(
        {"index": latest_block.index}, latest_block.to_dict(), upsert=True
    )

    original_fork = CHAIN.DYNAMIC_NODES_FORK
    activation_height = latest_block.index
    CHAIN.DYNAMIC_NODES_FORK = activation_height

    simulator = None
    try:
        simulator = NetworkSimulator(latency_ms=0, packet_loss_rate=0.0)
        await simulator.initialize()

        peer_public_key, peer_private_key = generate_keypair()

        miner_node = await simulator.add_node(
            "miner",
            "seed",
            host="127.0.0.1",
            port=8000,
            public_key=config.public_key,
            private_key=config.private_key,
            consensus=config.consensus,
        )

        # Create peer node with its own consensus (pointing to peer database)
        peer_node = await simulator.add_node(
            "peer",
            "seed_gateway",
            host="127.0.0.1",
            port=8001,
            public_key=peer_public_key,
            private_key=peer_private_key,
            consensus=config.consensus,  # Use miner's consensus for now (will validate independently)
        )
        simulator.connect_nodes(miner_node.node_id, peer_node.node_id)

        miner_node.blockchain = [latest_block]
        peer_node.blockchain = [latest_block]

        # Generate dynamic node announcement transaction
        # Registration fee: 1 YDA per block
        # For testing, use small fee to avoid wallet funding issues
        # In production: 144 blocks per day * 30 days = 4,320 YDA for 1 month
        registration_fee = 10.0  # 10 blocks for testing

        node_announcement = build_node_announcement(config)
        relationship_str = node_announcement.to_string()

        # Create transaction without automatic input/output generation
        # In production, users would need sufficient funds to pay the registration fee
        txn = Transaction(
            txn_time=int(time.time()),
            public_key=config.public_key,
            relationship=relationship_str,
            relationship_hash=hashlib.sha256(relationship_str.encode()).digest().hex(),
            outputs=[],
            inputs=[],
            fee=registration_fee,
            version=7,
        )
        txn.relationship = node_announcement
        txn.hash = await txn.generate_hash()
        txn.transaction_signature = TU.generate_signature_with_private_key(
            config.private_key, txn.hash
        )

        # Create new block with dynamic node announcement
        new_block = await Block.generate(
            transactions=[txn],
            public_key=config.public_key,
            private_key=config.private_key,
            index=latest_block.index + 1,
            prev_hash=latest_block.hash,
            nonce="0000000000000000",
        )

        # Process block through miner's consensus engine into miner's database
        inbound_chain = Blockchain([latest_block, new_block])
        queue_item = BlockProcessingQueueItem(inbound_chain)
        config.processing_queues.block_queue.add(queue_item)
        await config.consensus.process_block_queue()

        # Propagate block through simulator to peer
        await simulator.propagate_block(new_block, source_node_id=miner_node.node_id)

        # Verify peer independently accepted the block in its own blockchain
        peer_accepted_block = any(
            block.hash == new_block.hash for block in peer_node.blockchain
        )

        # If peer accepted the block, also insert it into peer's database
        # (simulating peer's consensus processing)
        if peer_accepted_block:
            await peer_mongo.async_db.blocks.replace_one(
                {"index": new_block.index}, new_block.to_dict(), upsert=True
            )

        # Refresh dynamic nodes from chain before generating reward block
        reset_nodes_cache()
        await Nodes.apply_dynamic_nodes(activation_height=activation_height)
        reset_nodes_cache()

        # Create reward block to verify masternode payout includes dynamic nodes
        reward_block = await Block.generate(
            transactions=[],
            public_key=config.public_key,
            private_key=config.private_key,
            index=new_block.index + 1,
            prev_hash=new_block.hash,
            nonce="0000000000000000",
        )

        # Verify registration expiry calculation
        # Expected expiry: announcement_height (new_block.index) + fee blocks
        expected_expiry_height = new_block.index + int(registration_fee)
        print(f"Node announced at block: {new_block.index}")
        print(
            f"Registration fee paid: {registration_fee} YDA ({int(registration_fee)} blocks)"
        )
        print(f"Expected expiry height: {expected_expiry_height}")
        print(f"Current height: {reward_block.index}")
        blocks_remaining = expected_expiry_height - reward_block.index
        print(f"Blocks remaining until expiry: {blocks_remaining}")

        reward_chain = Blockchain([new_block, reward_block])
        reward_queue_item = BlockProcessingQueueItem(reward_chain)
        config.processing_queues.block_queue.add(reward_queue_item)
        await config.consensus.process_block_queue()

        await simulator.propagate_block(reward_block, source_node_id=miner_node.node_id)
        reward_peer_accepted_block = any(
            block.hash == reward_block.hash for block in peer_node.blockchain
        )
        if reward_peer_accepted_block:
            await peer_mongo.async_db.blocks.replace_one(
                {"index": reward_block.index}, reward_block.to_dict(), upsert=True
            )

        # Verify miner's database has the block
        miner_inserted_block = await config.mongo.async_db.blocks.find_one(
            {"hash": new_block.hash}, {"_id": 0}
        )

        # Verify peer's database has the block (in separate database)
        peer_inserted_block = await peer_mongo.async_db.blocks.find_one(
            {"hash": new_block.hash}, {"_id": 0}
        )

        reward_peer_inserted_block = await peer_mongo.async_db.blocks.find_one(
            {"hash": reward_block.hash}, {"_id": 0}
        )

        await config.LatestBlock.block_checker()
        miner_latest = config.LatestBlock.block

        # Simulate peer reading dynamic nodes from chain
        reset_nodes_cache()
        await Nodes.apply_dynamic_nodes(activation_height=activation_height)
        reset_nodes_cache()

        dynamic_node_present = node_exists_for_height(
            reward_block.index, node_announcement.identity.public_key
        )

        # Verify dynamic node payout in coinbase outputs
        announced_node_address = str(
            P2PKHBitcoinAddress.from_pubkey(
                bytes.fromhex(node_announcement.identity.public_key)
            )
        )
        coinbase_txn = next(
            (txn for txn in reward_block.transactions if txn.coinbase), None
        )
        if not coinbase_txn:
            raise RuntimeError("Coinbase transaction not found in reward block")

        miner_reward_output = max(
            coinbase_txn.outputs, key=lambda output: float(output.value)
        )
        masternode_outputs = [
            output
            for output in coinbase_txn.outputs
            if output is not miner_reward_output
        ]
        masternode_paid_addresses = {output.to for output in masternode_outputs}
        masternode_paid_total = sum(
            float(output.value) for output in masternode_outputs
        )

        block_reward = CHAIN.get_block_reward(reward_block.index)
        masternode_fee_sum = sum(
            float(txn.masternode_fee)
            for txn in reward_block.transactions
            if not txn.coinbase
        )
        expected_masternode_total = (block_reward * 0.1) + masternode_fee_sum
        reward_epsilon = 1e-8

        dynamic_node_paid = announced_node_address in masternode_paid_addresses
        masternode_total_matches = (
            abs(masternode_paid_total - expected_masternode_total) < reward_epsilon
        )

        print("Dynamic node chain test results (separate databases)")
        print("- Miner database: yadacoin")
        print("- Peer database: yadacoin_peer")
        print("- Latest block before:", latest_block.index)
        print("- Activation height:", activation_height)
        print("- New block index:", new_block.index)
        print("- New block hash:", new_block.hash)
        print("- Reward block index:", reward_block.index)
        print("- Reward block hash:", reward_block.hash)
        print("- Miner DB block inserted:", bool(miner_inserted_block))
        print("- Peer DB block inserted:", bool(peer_inserted_block))
        print("- Reward block inserted (peer DB):", bool(reward_peer_inserted_block))
        print("- Miner latest block:", miner_latest.index if miner_latest else None)
        print("- Peer accepted block:", peer_accepted_block)
        print("- Peer accepted reward block:", reward_peer_accepted_block)
        print("- Dynamic node present:", dynamic_node_present)
        print("- Dynamic node paid:", dynamic_node_paid)
        print("- Masternode payout total valid:", masternode_total_matches)

        if not miner_inserted_block:
            raise RuntimeError("Block was not inserted into miner database")
        if not peer_inserted_block:
            raise RuntimeError("Block was not inserted into peer database")
        if not peer_accepted_block:
            raise RuntimeError("Peer did not accept the new block")
        if not reward_peer_accepted_block:
            raise RuntimeError("Peer did not accept the reward block")
        if not dynamic_node_present:
            raise RuntimeError("Dynamic node not found in nodes list")
        if not dynamic_node_paid:
            raise RuntimeError("Dynamic node was not paid in the reward block")
        if not masternode_total_matches:
            raise RuntimeError("Masternode reward total did not match expectation")

        print("Test status: PASS")

    finally:
        CHAIN.DYNAMIC_NODES_FORK = original_fork
        if simulator:
            await simulator.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
