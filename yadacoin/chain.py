"""
This is a class to store the global chain params
"""



class CHAIN(object):

    # Max possible target for a block
    MAX_TARGET = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    MAX_TARGET_HEX = 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'

    MAX_NONCE_LEN = 64

    # The fork checkpoints, so we have a single reference for all the codebase and can use explicit names for forks.
    POW_FORK_V2 = 60000
    POW_FORK_V3 = 61110

    RETARGET_PERIOD = 2016  # blocks
    TWO_WEEKS = 1209600  # seconds
    HALF_WEEK = 302400  # seconds

    MAX_BLOCKS_PER_MESSAGE = 200  # Not really a chain param, but better if coherent across peers
    MAX_RETRACE_DEPTH = 20  # Max allowed retrace. Deeper retrace would need manual chain truncating

    TIME_TOLERANCE = 10  # MAX # of seconds in the future we allow a bloc or TX to be. NTP Sync required for nodes.
    CHECK_TIME_FROM = 59710  # Begin checks there
    MINING_AND_TXN_REFORM_FORK = 60000

    ONE_DAY_IN_SECONDS = 1440 * 60
    RETARGET_PERIOD_V2 = 144  # blocks = 1 day at 10 min per block
    RETARGET_PERIOD_V3 = 1  # blocks = 1 day at 10 min per block
    MAX_SECONDS_V2 = ONE_DAY_IN_SECONDS * 7  # seconds - avoid to drop to fast.
    MIN_SECONDS_V2 = 3600  # seconds = 1h - avoid too high a raise.
    MAX_SECONDS_V3 = ONE_DAY_IN_SECONDS * 7  # seconds - avoid to drop to fast.
    MIN_SECONDS_V3 = 3600  # seconds = 1h - avoid too high a raise.
    # target block time is now 600 sec
    # special_min triggers after 2 * block time
    # we want max target (= min diff) is reached after long enough it does not drop too fast.
    # Could be raised later on depending on the net hash rate. calibrating for very low hash
    MAX_TARGET_AFTER_V2 = 600 * 6 * 8 # after 8 hours, target will hit  MAX_TARGET_V2. after twice that time, absolute max.
    MAX_TARGET_AFTER_V3 = 600 * 3 # after 8 hours, target will hit  MAX_TARGET_V2. after twice that time, absolute max.

    # Max possible target for a block, v2 after MAX_TARGET_AFTER_V2: reasonable target for a single cpu miner.
    MAX_TARGET_V2 = 0x000000000fffffffffffffffffffffffffffffffffffffffffffffffffffffff
    MAX_TARGET_HEX_V2 = '000000000fffffffffffffffffffffffffffffffffffffffffffffffffffffff'
    MAX_TARGET_V3 = 0x000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    MAX_TARGET_HEX_V3 = '000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'

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
    def special_min_trigger(cls, network: str, block_height: int) -> int:
        """When should special_min be activated?"""
        # For testnet and regnet, special min triggers at target_block_time + 1
        try:
            if network == 'testnet':
                return 10 + 1
            elif network == 'regnet':
                return 1 +1
            elif network == 'mainnet':
                if int(block_height) <= cls.POW_FORK_V2:
                    # return 120  # temp debug
                    return 600
                elif int(block_height) <= cls.POW_FORK_V3:
                    return 600
                else:
                    return 600 * 2
            raise ValueError("Unknown network")
        except Exception as e:
            print(e)
            import sys, os
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

    @classmethod
    def special_target(cls, block_height: int, target:int, delta_t:int, network: str='mainnet') -> int:
        """Given the regular target and time since last block, gives the current target
        This is supposed to be the only place where this is computed, to ease maintenance"""
        if int(block_height) < cls.POW_FORK_V2:
            target_factor = delta_t / cls.target_block_time(network)
            special_target = int(target * (target_factor * 4))
        elif int(block_height) >= cls.POW_FORK_V3:
            # from 60k, POW_FORK_V3, we aim to reach MAX_TARGET_V3 after MAX_TARGET_AFTER_V3
            if delta_t >= 2 * cls.MAX_TARGET_AFTER_V3:
                # but after twice that time, if still stuck - hard block - allow anything (MAX_TARGET)
                special_target = cls.MAX_TARGET
            elif delta_t <= 60 * 2:
                special_target = target
            else:
                delta_target = abs(cls.MAX_TARGET_V3 - target)  # abs to make sure, should not happen
                special_target = int(target + delta_target *  (delta_t - 2 * 60) // (cls.MAX_TARGET_AFTER_V3 - 2 * 60 ) )
        elif int(block_height) >= cls.POW_FORK_V2 and int(block_height) < cls.POW_FORK_V3:
            # from 60k, POW_FORK_V2, we aim to reach MAX_TARGET_V2 after MAX_TARGET_AFTER_V2
            if delta_t >= 2 * cls.MAX_TARGET_AFTER_V2:
                # but after twice that time, if still stuck - hard block - allow anything (MAX_TARGET)
                special_target = cls.MAX_TARGET
            elif delta_t <= 600 * 2:
                special_target = target
            else:
                delta_target = abs(cls.MAX_TARGET_V2 - target)  # abs to make sure, should not happen
                special_target = int(target + delta_target *  (delta_t - 2 * 600) // (cls.MAX_TARGET_AFTER_V2 - 2 * 600 ) )

        if special_target > cls.MAX_TARGET:
            special_target = cls.MAX_TARGET
        return special_target

    @classmethod
    def get_version_for_height(cls, height: int):
        if int(height) <= 14484:
            return 1
        elif int(height) >= cls.POW_FORK_V3:
            return 4
        elif int(height) > cls.POW_FORK_V2 and int(height) < cls.POW_FORK_V3:
            return 3
        else:
            return 2

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
        index = block_index // 2100000
        reward = int(50.0 * 1e8 / 2 ** index) / 1e8
        return reward