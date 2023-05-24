"""
This is a class to store the global chain params
"""
from yadacoin.core.config import get_config


class CHAIN(object):
    # Max possible target for a block
    MAX_TARGET = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    MAX_TARGET_HEX = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"

    MAX_NONCE_LEN = 64

    # The fork checkpoints, so we have a single reference for all the codebase and can use explicit names for forks.
    CHECK_TIME_FROM = 59710  # Begin checks there
    CHECK_DOUBLE_SPEND_FROM = 81871
    POW_FORK_V2 = 60000
    MINING_AND_TXN_REFORM_FORK = 60000
    POW_FORK_V3 = 61110

    BLOCK_V5_FORK = 176000
    RANDOMX_FORK = 65000
    FORK_10_MIN_BLOCK = 65500
    SPECIAL_MIN_FORK = 38600
    TXN_V3_FORK = 269600
    TXN_V3_FORK_CHECK_MINER_SIGNATURE = 270700
    FORK_SMOOTH_RETARGET = 422110
    REQUIRE_NODE_VERSION_566 = 424200
    LITTLE_HASH_DIFF_FIX = 430000

    RETARGET_PERIOD = 2016  # blocks
    TWO_WEEKS = 1209600  # seconds
    HALF_WEEK = 302400  # seconds

    MAX_BLOCKS_PER_MESSAGE = (
        200  # Not really a chain param, but better if coherent across peers
    )
    MAX_RETRACE_DEPTH = (
        20  # Max allowed retrace. Deeper retrace would need manual chain truncating
    )

    TIME_TOLERANCE = 10  # MAX # of seconds in the future we allow a bloc or TX to be. NTP Sync required for nodes.

    ONE_DAY_IN_SECONDS = 1440 * 60
    RETARGET_PERIOD_V2 = 144  # blocks = 1 day at 10 min per block
    RETARGET_PERIOD_V3 = 1  # blocks = 1 day at 10 min per block
    MAX_SECONDS_V2 = ONE_DAY_IN_SECONDS * 7  # seconds - avoid to drop to fast.
    MIN_SECONDS_V2 = 3600  # seconds = 1h - avoid too high a raise.
    MAX_SECONDS_V3 = ONE_DAY_IN_SECONDS * 7  # seconds - avoid to drop to fast.
    MIN_SECONDS_V3 = 3600  # seconds = 1h - avoid too high a raise.
    # target block time is now 600 sec
    # special_min triggers after 2 * block time
    # we want max target (= min diff) is reached after long enough it does not drop too fast.
    # Could be raised later on depending on the net hash rate. calibrating for very low hash
    MAX_TARGET_AFTER_V2 = (
        600 * 6 * 8
    )  # after 8 hours, target will hit  MAX_TARGET_V2. after twice that time, absolute max.
    MAX_TARGET_AFTER_V3 = (
        600 * 3
    )  # after 8 hours, target will hit  MAX_TARGET_V2. after twice that time, absolute max.

    # Max possible target for a block, v2 after MAX_TARGET_AFTER_V2: reasonable target for a single cpu miner.
    MAX_TARGET_V2 = 0x000000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    MAX_TARGET_HEX_V2 = (
        "000000000fffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    )
    MAX_TARGET_V3 = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    MAX_TARGET_HEX_V3 = (
        "000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    )

    FORCE_CONSENSUS_TIME_THRESHOLD = 30

    @classmethod
    def target_block_time(cls, network: str):
        """What is the target block time for a specific network?"""
        if network == "mainnet":
            return 600
        elif network == "testnet":
            return 10
        elif network == "regnet":
            # Avoid possible divisions by 0
            return 1
        raise ValueError("Unknown network")

    @classmethod
    def special_min_trigger(cls, network: str, block_height: int) -> int:
        """When should special_min be activated?"""
        # For testnet and regnet, special min triggers at target_block_time + 1
        try:
            if network == "testnet":
                return 10 + 1
            elif network == "regnet":
                return 1 + 1
            elif network == "mainnet":
                if int(block_height) <= cls.POW_FORK_V2:
                    # return 120  # temp debug
                    return 600
                elif int(block_height) <= cls.POW_FORK_V3:
                    return 600
                elif int(block_height) <= cls.POW_FORK_V3:
                    return 600
                elif int(block_height) >= cls.FORK_10_MIN_BLOCK:
                    return 3600
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
    def special_target(
        cls, block_height: int, target: int, delta_t: int, network: str = "mainnet"
    ) -> int:
        """Given the regular target and time since last block, gives the current target
        This is supposed to be the only place where this is computed, to ease maintenance
        """
        if int(block_height) < cls.POW_FORK_V2:
            target_factor = delta_t / cls.target_block_time(network)
            special_target = int(target * (target_factor * 4))
        elif int(block_height) >= cls.FORK_10_MIN_BLOCK:
            special_target = int(target)  # we handle the adjustment in get_target now.
        elif int(block_height) >= cls.POW_FORK_V3:
            # from 60k, POW_FORK_V3, we aim to reach MAX_TARGET_V3 after MAX_TARGET_AFTER_V3
            if delta_t >= 2 * cls.MAX_TARGET_AFTER_V3:
                # but after twice that time, if still stuck - hard block - allow anything (MAX_TARGET)
                special_target = cls.MAX_TARGET
            elif delta_t <= 60 * 2:
                special_target = target
            else:
                delta_target = abs(
                    cls.MAX_TARGET_V3 - target
                )  # abs to make sure, should not happen
                special_target = int(
                    target
                    + delta_target
                    * (delta_t - 2 * 60)
                    // (cls.MAX_TARGET_AFTER_V3 - 2 * 60)
                )
        elif (
            int(block_height) >= cls.POW_FORK_V2 and int(block_height) < cls.POW_FORK_V3
        ):
            # from 60k, POW_FORK_V2, we aim to reach MAX_TARGET_V2 after MAX_TARGET_AFTER_V2
            if delta_t >= 2 * cls.MAX_TARGET_AFTER_V2:
                # but after twice that time, if still stuck - hard block - allow anything (MAX_TARGET)
                special_target = cls.MAX_TARGET
            elif delta_t <= 600 * 2:
                special_target = target
            else:
                delta_target = abs(
                    cls.MAX_TARGET_V2 - target
                )  # abs to make sure, should not happen
                special_target = int(
                    target
                    + delta_target
                    * (delta_t - 2 * 600)
                    // (cls.MAX_TARGET_AFTER_V2 - 2 * 600)
                )

        if special_target > cls.MAX_TARGET:
            special_target = cls.MAX_TARGET
        return special_target

    @classmethod
    def get_version_for_height(cls, height: int):
        if int(height) <= 14484:
            return 1
        elif int(height) >= cls.BLOCK_V5_FORK:
            return 5
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
            {"block": "6930000", "reward": "0"},
        ]

        if block_index is None:
            block_index = get_config().LatestBlock.block.index + 1

        try:
            for t, block_reward in enumerate(block_rewards):
                if (
                    int(block_reward["block"])
                    <= block_index
                    < int(block_rewards[t + 1]["block"])
                ):
                    break

            return float(block_reward["reward"])
        except:
            return 0.0

    @classmethod
    def get_block_reward(cls, block_index=None):
        """Returns the reward matching a given block height, next block if None is provided"""
        if block_index is None:
            block_index = get_config().LatestBlock.block.index + 1
        index = block_index // 210000
        reward = int(50.0 * 1e8 / 2**index) / 1e8
        return reward

    @classmethod
    def get_circulating_supply(cls, current_index):
        circulating = 0
        index = 0
        while True:
            i = current_index - index
            if i < 0:
                break
            circulating += (210000 if i > 210000 else i) * CHAIN.get_block_reward(index)
            index += 210000
        return circulating

    @classmethod
    async def get_target_10min(
        cls,
        last_block,  # This is the latest on chain block we have in db
        block,  # This is the block we are currently mining, not on chain yet, with current time in it.
        extra_blocks=None,
    ):
        cls.config = get_config()
        if extra_blocks is None:
            extra_blocks = []
        from yadacoin.core.block import Block

        # Aim at 5 min average block time, with escape hatch
        max_target = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF  # A single cpu does that under a minute.
        retarget_period = (
            6 * 5
        )  # 5 hours at 10 min per block - needs to be high enough to account for organic variance of the miners
        retarget_period2 = int(
            6 * 1.5
        )  # 1 hour and 30 min at 10 min per block - Faster reaction to drops in blocktime, we want to make "instamine" harder
        target_time = 10 * 60  # 10 min
        # That should not happen
        if int(block.time) - int(last_block.time) > 3600:
            cls.config.app_log.debug("Block time over max. Max target set.")
            return int(max_target)
        # decrease after 2x target - can be 3 as well
        current_block_time = int(block.time) - int(last_block.time)
        adjusted = False

        if current_block_time > 2 * target_time:
            if block.index >= CHAIN.FORK_SMOOTH_RETARGET:
                current_target = last_block.target
                # Linear decrease to reach max target after one hour block time.
                new_target = int(
                    current_target
                    + current_target
                    * ((current_block_time - target_time) / current_block_time)
                )
                # print("adjust", current_block_time, MinerSimulator.HEX(new_target), latest_target)
                adjusted = new_target
                # To be used later on, once the rest is calc'd
            else:
                latest_target = last_block.target
                delta = max_target - latest_target
                # Linear decrease to reach max target after one hour block time.
                new_target = int(latest_target + delta * current_block_time / 3600)
                adjusted = new_target

        start_index = last_block.index

        block_from_retarget_period_ago = None
        for extra_block in extra_blocks:
            if extra_block.index == start_index - retarget_period:
                block_from_retarget_period_ago = extra_block
                break

        if not block_from_retarget_period_ago:
            block_data = await get_config().mongo.async_db.blocks.find_one(
                {"index": start_index - retarget_period}
            )
            if not block_data:
                return False
            block_from_retarget_period_ago = await Block.from_dict(block_data)

        retarget_period_ago_time = block_from_retarget_period_ago.time
        elapsed_time_from_retarget_period_ago = int(block.time) - int(
            retarget_period_ago_time
        )
        average_block_time = elapsed_time_from_retarget_period_ago / retarget_period

        block_from_retarget_period2_ago = None
        for extra_block in extra_blocks:
            if extra_block.index == start_index - retarget_period2:
                block_from_retarget_period2_ago = extra_block
                break

        if not block_from_retarget_period2_ago:
            block_data = await get_config().mongo.async_db.blocks.find_one(
                {"index": start_index - retarget_period2}
            )
            if not block_data:
                return False
            block_from_retarget_period2_ago = await Block.from_dict(block_data)

        retarget_period2_ago_time = block_from_retarget_period2_ago.time
        elapsed_time_from_retarget_period2_ago = int(block.time) - int(
            retarget_period2_ago_time
        )
        average_block_time2 = elapsed_time_from_retarget_period2_ago / retarget_period2

        # React faster to a drop in block time than to a raise. short block times are more a threat than large ones.
        if average_block_time2 < target_time:
            hash_sum2 = 0
            for i in range(start_index, start_index - retarget_period2, -1):
                found = False
                for extra_block in extra_blocks:
                    if extra_block.index == i:
                        hash_sum2 += extra_block.target
                        found = True
                        break
                if not found:
                    this_block = await get_config().mongo.async_db.blocks.find_one(
                        {"index": i}
                    )
                    if this_block:
                        block_tmp = await Block.from_dict(this_block)
                        hash_sum2 += block_tmp.target
            average_target = hash_sum2 / retarget_period2
            target = int(average_target * average_block_time2 / target_time)
        else:
            hash_sum = 0
            for i in range(start_index, start_index - retarget_period, -1):
                found = False
                for extra_block in extra_blocks:
                    if extra_block.index == i:
                        hash_sum += extra_block.target
                        found = True
                        break
                if not found:
                    this_block = await get_config().mongo.async_db.blocks.find_one(
                        {"index": i}
                    )
                    if this_block:
                        block_tmp = await Block.from_dict(this_block)
                        hash_sum += block_tmp.target
            average_target = hash_sum / retarget_period
            # This adjusts both ways
            target = int(average_target * average_block_time / target_time)
        if adjusted:
            # Take min of calc and adjusted
            if adjusted > target:
                target = adjusted

        cls.config.app_log.debug("average block time {}".format(average_block_time))
        cls.config.app_log.debug(
            "average target {:02x} target {:02x}".format(
                int(average_target), int(target)
            )
        )
        if target < 1:
            target = 1
            block.special_min = False

        if target > max_target:
            target = max_target
        return int(target)

    @classmethod
    async def get_target(cls, height, last_block, block, extra_blocks=None) -> int:
        from yadacoin.core.block import Block

        cls.config = get_config()
        # change target
        max_target = CHAIN.MAX_TARGET
        if get_config().network in ["regnet", "testnet"]:
            return int(max_target)

        max_block_time = CHAIN.target_block_time(get_config().network)
        retarget_period = CHAIN.RETARGET_PERIOD  # blocks
        max_seconds = CHAIN.TWO_WEEKS  # seconds
        min_seconds = CHAIN.HALF_WEEK  # seconds
        if height >= CHAIN.POW_FORK_V3:
            retarget_period = CHAIN.RETARGET_PERIOD_V3
            max_seconds = CHAIN.MAX_SECONDS_V3  # seconds
            min_seconds = CHAIN.MIN_SECONDS_V3  # seconds
        elif height >= CHAIN.POW_FORK_V2:
            retarget_period = CHAIN.RETARGET_PERIOD_V2
            max_seconds = CHAIN.MAX_SECONDS_V2  # seconds
            min_seconds = CHAIN.MIN_SECONDS_V2  # seconds
        if height > 0 and height % retarget_period == 0:
            cls.config.app_log.debug(
                "RETARGET get_target height {} - last_block {} - block {}/time {}".format(
                    height, last_block.index, block.index, block.time
                )
            )
            block_data = await get_config().BU.get_block_by_index(
                height - retarget_period
            )
            block_from_2016_ago = None
            if block_data:
                block_from_2016_ago = await Block.from_dict(block_data)
            elif extra_blocks:
                for extra_block in extra_blocks:
                    if extra_block.index == height - retarget_period:
                        block_from_2016_ago = extra_block
                        break
                if not block_from_2016_ago:
                    return False

            cls.config.app_log.debug(
                "Block_from_2016_ago - block {}/time {}".format(
                    block_from_2016_ago.index, block_from_2016_ago.time
                )
            )
            two_weeks_ago_time = block_from_2016_ago.time
            elapsed_time_from_2016_ago = int(last_block.time) - int(two_weeks_ago_time)
            cls.config.app_log.debug(
                "elapsed_time_from_2016_ago {} s {} days".format(
                    int(elapsed_time_from_2016_ago),
                    elapsed_time_from_2016_ago / (60 * 60 * 24),
                )
            )
            # greater than two weeks?
            if elapsed_time_from_2016_ago > max_seconds:
                time_for_target = max_seconds
                cls.config.app_log.debug("gt max")
            elif elapsed_time_from_2016_ago < min_seconds:
                time_for_target = min_seconds
                cls.config.app_log.debug("lt min")
            else:
                time_for_target = int(elapsed_time_from_2016_ago)

            block_to_check = last_block

            start_index = last_block.index

            cls.config.app_log.debug("start_index {}".format(start_index))
            if (
                block_to_check.special_min
                or block_to_check.target == max_target
                or not block_to_check.target
            ):
                block_data = await get_config().mongo.async_db.blocks.find_one(
                    {
                        "$and": [
                            {"index": {"$lte": start_index}},
                            {"special_min": False},
                            {"target": {"$ne": hex(max_target)[2:]}},
                        ]
                    },
                    sort=[("index", -1)],
                )
                block_to_check = None
                if block_data:
                    block_to_check = await Block.from_dict(block_data)
                elif extra_blocks:
                    for extra_block in extra_blocks:
                        if (
                            extra_block.index <= start_index
                            and extra_block.special_min
                            and extra_block != max_target
                        ):
                            block_to_check = extra_block
                            break
                    if not block_to_check:
                        return False

            target = block_to_check.target
            cls.config.app_log.debug(
                "start_index2 {}, target {}".format(
                    block_to_check.index, hex(int(target))[2:].rjust(64, "0")
                )
            )

            new_target = int((time_for_target * target) / max_seconds)
            cls.config.app_log.debug(
                "new_target {}".format(hex(int(new_target))[2:].rjust(64, "0"))
            )

            if new_target > max_target:
                target = max_target
            else:
                target = new_target

        elif height == 0:
            target = max_target
        else:
            block_to_check = block
            delta_t = int(block.time) - int(last_block.time)
            if (
                block.index >= CHAIN.SPECIAL_MIN_FORK
                and delta_t > max_block_time
                and block.special_min
            ):
                special_target = CHAIN.special_target(
                    block.index, block.target, delta_t, get_config().network
                )
                return special_target

            block_to_check = last_block  # this would be accurate. right now, it checks if the current block is under its own target, not the previous block's target

            start_index = last_block.index

            while 1:
                if start_index == 0:
                    return block_to_check.target
                if (
                    block_to_check.special_min
                    or block_to_check.target == max_target
                    or not block_to_check.target
                ):
                    block_data = await get_config().mongo.async_db.blocks.find_one(
                        {"index": start_index}
                    )
                    prev_block = None
                    if block_data:
                        prev_block = await Block.from_dict(block_data)
                    elif extra_blocks:
                        for extra_block in extra_blocks:
                            if extra_block.index == start_index:
                                prev_block = extra_block
                                break
                    if not prev_block:
                        start_index -= 1
                        continue
                    block_to_check = prev_block
                    start_index -= 1
                else:
                    target = block_to_check.target
                    break
        return int(target)
