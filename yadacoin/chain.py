"""
This is a class to store the global chain params
"""



class CHAIN(object):

    # Max possible target for a block
    MAX_TARGET = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    MAX_TARGET_HEX = 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'

    # The fork checkpoints, so we have a single reference for all the codebase and can use explicit names for forks.
    POW_FORK_V2 = 60000

    RETARGET_PERIOD = 2016  # blocks
    TWO_WEEKS = 1209600  # seconds
    HALF_WEEK = 302400  # seconds

    # TODO: add block time depending on network + escape hatch

    @classmethod
    def target_block_time(cls, network:str):
        """What is the target block time for a specific network?"""
        if network == 'mainnet':
            return 600
        elif network == 'testnet':
            return 10
        elif network == 'regnet':
            # Avoid possible divisions by 0
            return 1
        raise ValueError("Unknown network")

    @classmethod
    def special_min_trigger(cls, network: str, block_height: int):
        """When should special_min be activated?"""
        # For testnet and regnet, special min triggers at target_block_time + 1
        if network == 'testnet':
            return 10 + 1
        elif network == 'regnet':
            return 1 +1
        elif network == 'mainnet':
            if block_height <= cls.POW_FORK_V2:
                return 600
            else:
                return 600 * 2
        raise ValueError("Unknown network")

    @classmethod
    def get_version_for_height(cls, height: int):
        if int(height) <= 14484:
            return 1
        elif int(height) <= cls.POW_FORK_V2:
            return 2
        else:
            # Version3: no more special_min in header, fixed target even at special_min, target as 66 hex char
            return 3

    @classmethod
    def get_block_reward_deprecated(cls, block_index=None):
        block_rewards = [
            {"block": "0", "reward": "50"},
            {"block": "210000", "reward": "25"},
            {"block": "420000", "reward": "12.5"},
            {"block": "630000", "reward": "6.25"},
            {"block": "840000", "reward": "3.125"},
            {"block": "1050000", "reward": "1.5625"},
            {"block": "1260000", "reward": "0.78125"},
            {"block": "1470000", "reward": "0.390625"},
            {"block": "1680000", "reward": "0.1953125"},
            {"block": "1890000", "reward": "0.09765625"},
            {"block": "2100000", "reward": "0.04882812"},
            {"block": "2310000", "reward": "0.02441406"},
            {"block": "2520000", "reward": "0.01220703"},
            {"block": "2730000", "reward": "0.00610351"},
            {"block": "2940000", "reward": "0.00305175"},
            {"block": "3150000", "reward": "0.00152587"},
            {"block": "3360000", "reward": "0.00076293"},
            {"block": "3570000", "reward": "0.00038146"},
            {"block": "3780000", "reward": "0.00019073"},
            {"block": "3990000", "reward": "0.00009536"},
            {"block": "4200000", "reward": "0.00004768"},
            {"block": "4410000", "reward": "0.00002384"},
            {"block": "4620000", "reward": "0.00001192"},
            {"block": "4830000", "reward": "0.00000596"},
            {"block": "5040000", "reward": "0.00000298"},
            {"block": "5250000", "reward": "0.00000149"},
            {"block": "5460000", "reward": "0.00000074"},
            {"block": "5670000", "reward": "0.00000037"},
            {"block": "5880000", "reward": "0.00000018"},
            {"block": "6090000", "reward": "0.00000009"},
            {"block": "6300000", "reward": "0.00000004"},
            {"block": "6510000", "reward": "0.00000002"},
            {"block": "6720000", "reward": "0.00000001"},
            {"block": "6930000", "reward": "0"}
        ]

        if block_index is None:
            from yadacoin.blockchainutil import BU
            block_index = BU().get_latest_block()['index'] + 1

        try:
            for t, block_reward in enumerate(block_rewards):
                if int(block_reward['block']) <= block_index < int(block_rewards[t+1]['block']):
                    break

            return float(block_reward['reward'])
        except:
            return 0.0

    @classmethod
    def get_block_reward(cls, block_index=None):
        """Returns the reward matching a given block height, next block if None is provided"""
        if block_index is None:
            from yadacoin.blockchainutils import BU
            block_index = BU().get_latest_block()['index'] + 1
        index = block_index // 210000
        reward = int(50.0 * 1e8 / 2 ** index) / 1e8
        return reward