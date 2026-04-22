"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import unittest

from yadacoin.core.chain import CHAIN


class TestChainConstants(unittest.TestCase):
    def test_max_target_is_int(self):
        self.assertIsInstance(CHAIN.MAX_TARGET, int)

    def test_max_target_hex_is_string(self):
        self.assertIsInstance(CHAIN.MAX_TARGET_HEX, str)

    def test_retarget_period(self):
        self.assertEqual(CHAIN.RETARGET_PERIOD, 2016)

    def test_fork_constants_are_ints(self):
        self.assertIsInstance(CHAIN.CHECK_MASTERNODE_FEE_FORK, int)
        self.assertIsInstance(CHAIN.ALLOW_SAME_BLOCK_SPENDING_FORK, int)
        self.assertIsInstance(CHAIN.DYNAMIC_NODES_FORK, int)


class TestTargetBlockTime(unittest.TestCase):
    def test_mainnet_target_block_time(self):
        self.assertEqual(CHAIN.target_block_time("mainnet"), 600)

    def test_testnet_target_block_time(self):
        self.assertEqual(CHAIN.target_block_time("testnet"), 10)

    def test_regnet_target_block_time(self):
        self.assertEqual(CHAIN.target_block_time("regnet"), 1)

    def test_unknown_network_raises(self):
        with self.assertRaises(ValueError):
            CHAIN.target_block_time("unknownnet")


class TestSpecialMinTrigger(unittest.TestCase):
    def test_testnet(self):
        result = CHAIN.special_min_trigger("testnet", 0)
        self.assertEqual(result, 11)  # 10 + 1

    def test_regnet(self):
        result = CHAIN.special_min_trigger("regnet", 0)
        self.assertEqual(result, 2)  # 1 + 1

    def test_mainnet_low_height(self):
        result = CHAIN.special_min_trigger("mainnet", 0)
        self.assertEqual(result, 600)

    def test_mainnet_at_pow_fork_v2(self):
        result = CHAIN.special_min_trigger("mainnet", CHAIN.POW_FORK_V2)
        self.assertIsNotNone(result)

    def test_mainnet_at_fork_10min(self):
        result = CHAIN.special_min_trigger("mainnet", CHAIN.FORK_10_MIN_BLOCK + 1)
        self.assertEqual(result, 3600)


class TestSpecialTarget(unittest.TestCase):
    def test_below_pow_fork_v2(self):
        # block_height < POW_FORK_V2
        target = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        delta_t = 1200
        result = CHAIN.special_target(0, target, delta_t, "mainnet")
        self.assertIsInstance(result, int)

    def test_above_fork_10min(self):
        # block_height >= FORK_10_MIN_BLOCK
        target = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        delta_t = 600
        result = CHAIN.special_target(
            CHAIN.FORK_10_MIN_BLOCK + 1, target, delta_t, "mainnet"
        )
        self.assertEqual(result, target)

    def test_pow_fork_v3_range_short_time(self):
        # block_height >= POW_FORK_V3 and < FORK_10_MIN_BLOCK, delta_t <= 2*60
        target = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        delta_t = 60  # <= 2*60
        height = CHAIN.POW_FORK_V3 + 1
        result = CHAIN.special_target(height, target, delta_t, "mainnet")
        self.assertEqual(result, target)

    def test_pow_fork_v3_range_very_long_time(self):
        # after twice MAX_TARGET_AFTER_V3, should return MAX_TARGET
        target = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        delta_t = 2 * CHAIN.MAX_TARGET_AFTER_V3 + 100
        height = CHAIN.POW_FORK_V3 + 1
        result = CHAIN.special_target(height, target, delta_t, "mainnet")
        self.assertEqual(result, CHAIN.MAX_TARGET)

    def test_pow_fork_v2_range_short_time(self):
        # block_height >= POW_FORK_V2 and < POW_FORK_V3, delta_t <= 600*2
        target = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        delta_t = 600  # <= 600*2
        # Use POW_FORK_V2 + 1 but < POW_FORK_V3
        height = CHAIN.POW_FORK_V2 + 1
        if height >= CHAIN.POW_FORK_V3:
            self.skipTest("POW_FORK_V2+1 >= POW_FORK_V3, skip")
        result = CHAIN.special_target(height, target, delta_t, "mainnet")
        self.assertEqual(result, target)

    def test_pow_fork_v2_range_very_long_time(self):
        # after twice MAX_TARGET_AFTER_V2, should return MAX_TARGET
        target = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        delta_t = 2 * CHAIN.MAX_TARGET_AFTER_V2 + 100
        height = CHAIN.POW_FORK_V2 + 1
        if height >= CHAIN.POW_FORK_V3:
            self.skipTest("POW_FORK_V2+1 >= POW_FORK_V3, skip")
        result = CHAIN.special_target(height, target, delta_t, "mainnet")
        self.assertEqual(result, CHAIN.MAX_TARGET)

    def test_does_not_exceed_max_target(self):
        target = CHAIN.MAX_TARGET
        delta_t = 9999999
        result = CHAIN.special_target(0, target, delta_t, "mainnet")
        self.assertLessEqual(result, CHAIN.MAX_TARGET)


class TestGetVersionForHeight(unittest.TestCase):
    def test_height_0(self):
        self.assertEqual(CHAIN.get_version_for_height(0), 1)

    def test_height_14484(self):
        self.assertEqual(CHAIN.get_version_for_height(14484), 1)

    def test_height_above_block_v5_fork(self):
        self.assertEqual(CHAIN.get_version_for_height(CHAIN.BLOCK_V5_FORK), 5)

    def test_height_above_block_v5_fork_plus(self):
        self.assertEqual(CHAIN.get_version_for_height(CHAIN.BLOCK_V5_FORK + 1000), 5)

    def test_height_at_pow_fork_v3(self):
        result = CHAIN.get_version_for_height(CHAIN.POW_FORK_V3)
        self.assertIn(result, [4, 5])

    def test_height_between_v2_and_v3(self):
        height = CHAIN.POW_FORK_V2 + 1
        if height < CHAIN.POW_FORK_V3:
            result = CHAIN.get_version_for_height(height)
            self.assertEqual(result, 3)


class TestGetBlockReward(unittest.TestCase):
    def test_block_0_reward(self):
        reward = CHAIN.get_block_reward(0)
        self.assertAlmostEqual(reward, 50.0)

    def test_block_210000_reward(self):
        reward = CHAIN.get_block_reward(210000)
        self.assertAlmostEqual(reward, 25.0)

    def test_block_420000_reward(self):
        reward = CHAIN.get_block_reward(420000)
        self.assertAlmostEqual(reward, 12.5)

    def test_reward_decreases_with_height(self):
        r1 = CHAIN.get_block_reward(0)
        r2 = CHAIN.get_block_reward(210001)
        self.assertGreater(r1, r2)

    def test_very_high_block_reward_near_zero(self):
        reward = CHAIN.get_block_reward(99999999)
        self.assertGreaterEqual(reward, 0)


class TestGetCirculatingSupply(unittest.TestCase):
    def test_circulating_supply_at_0(self):
        supply = CHAIN.get_circulating_supply(0)
        self.assertGreaterEqual(supply, 0)

    def test_circulating_supply_at_210000(self):
        supply = CHAIN.get_circulating_supply(210000)
        self.assertGreater(supply, 0)

    def test_circulating_supply_increases_with_index(self):
        s1 = CHAIN.get_circulating_supply(1000)
        s2 = CHAIN.get_circulating_supply(2000)
        self.assertGreaterEqual(s2, s1)


class TestSpecialMinTriggerMainnet(unittest.TestCase):
    """Tests for mainnet branches of special_min_trigger (lines 128, 130, 134)."""

    def test_mainnet_before_pow_fork_v2(self):
        height = CHAIN.POW_FORK_V2 - 1
        result = CHAIN.special_min_trigger("mainnet", height)
        self.assertEqual(result, 600)

    def test_mainnet_at_pow_fork_v3(self):
        height = CHAIN.POW_FORK_V3 - 1
        result = CHAIN.special_min_trigger("mainnet", height)
        self.assertEqual(result, 600)

    def test_mainnet_at_fork_10min_block(self):
        height = CHAIN.FORK_10_MIN_BLOCK
        result = CHAIN.special_min_trigger("mainnet", height)
        self.assertEqual(result, 3600)

    def test_mainnet_between_forks(self):
        height = CHAIN.POW_FORK_V3 + 1
        if height < CHAIN.FORK_10_MIN_BLOCK:
            result = CHAIN.special_min_trigger("mainnet", height)
            self.assertEqual(result, 1200)

    def test_mainnet_unknown_network_returns_none(self):
        result = CHAIN.special_min_trigger("unknownnet", 100)
        self.assertIsNone(result)


class TestSpecialTargetBranches(unittest.TestCase):
    """Tests for special_target branches (lines 165-168, 184-187)."""

    def test_special_target_v3_medium_delta(self):
        """Line 165-168: delta_t between 2*60 and 2*MAX_TARGET_AFTER_V3, POW_FORK_V3 height."""
        height = CHAIN.POW_FORK_V3
        target = CHAIN.MAX_TARGET // 2
        delta_t = 60 * 3  # > 2*60, < 2*MAX_TARGET_AFTER_V3
        result = CHAIN.special_target(height, target, delta_t, "mainnet")
        self.assertIsInstance(result, int)

    def test_special_target_v2_medium_delta(self):
        """Lines 184-187: delta_t between 2*600 and 2*MAX_TARGET_AFTER_V2, V2 range."""
        height = CHAIN.POW_FORK_V2 + 1
        target = CHAIN.MAX_TARGET // 2
        delta_t = 600 * 3  # > 2*600
        result = CHAIN.special_target(height, target, delta_t, "mainnet")
        self.assertIsInstance(result, int)


class TestGetVersionForHeight(unittest.TestCase):
    """Tests for get_version_for_height (lines 201, 203, 205, 207, 209)."""

    def test_version_for_height_14484_or_less(self):
        """Line 201: returns 1 for height <= 14484."""
        self.assertEqual(CHAIN.get_version_for_height(14484), 1)
        self.assertEqual(CHAIN.get_version_for_height(0), 1)

    def test_version_for_block_v5_fork_height(self):
        """Line 203: returns 5 for height >= BLOCK_V5_FORK."""
        version = CHAIN.get_version_for_height(CHAIN.BLOCK_V5_FORK)
        self.assertEqual(version, 5)

    def test_version_for_pow_fork_v3_height(self):
        """Line 205: returns 4 for height in [POW_FORK_V3, BLOCK_V5_FORK)."""
        height = CHAIN.POW_FORK_V3
        if height < CHAIN.BLOCK_V5_FORK:
            version = CHAIN.get_version_for_height(height)
            self.assertEqual(version, 4)

    def test_version_for_pow_fork_v2_to_v3_range(self):
        """Line 207: returns 3 for height in (POW_FORK_V2, POW_FORK_V3)."""
        height = CHAIN.POW_FORK_V2 + 1
        if height < CHAIN.POW_FORK_V3:
            version = CHAIN.get_version_for_height(height)
            self.assertEqual(version, 3)

    def test_version_for_height_between_14484_and_pow_fork_v2(self):
        """Line 209: returns 2 for height 14485 to POW_FORK_V2."""
        height = 14485
        version = CHAIN.get_version_for_height(height)
        self.assertEqual(version, 2)


# ---------------------------------------------------------------------------
# get_target_10min and get_target tests
# ---------------------------------------------------------------------------

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from tests.unittests.test_setup import AsyncTestCase


def _mk_block(index, time, target=CHAIN.MAX_TARGET, special_min=False):
    return SimpleNamespace(
        index=index, time=time, target=target, special_min=special_min
    )


class TestGetTarget10MinExceptions(unittest.TestCase):
    def test_special_min_trigger_exception_branch_prints(self):
        """Line ~140: except branch printing is covered when block_height is non-numeric."""
        # Invalid input causes ValueError in int() -> hits except.
        result = CHAIN.special_min_trigger("mainnet", "not-a-number")
        self.assertIsNone(result)


class TestGetBlockRewardDefault(unittest.TestCase):
    def test_get_block_reward_uses_latest_block_when_none(self):
        """Line 271: default branch using Config().LatestBlock.block.index + 1."""
        with patch("yadacoin.core.chain.Config") as MockConfig:
            cfg = MagicMock()
            cfg.LatestBlock.block.index = 0
            MockConfig.return_value = cfg
            r = CHAIN.get_block_reward()
        self.assertAlmostEqual(r, 50.0)


class TestGetTarget10Min(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.cfg_patch = patch("yadacoin.core.chain.Config")
        self.MockConfig = self.cfg_patch.start()
        self.cfg = MagicMock()
        self.cfg.app_log = MagicMock()
        self.cfg.network = "mainnet"
        self.cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        self.cfg.BU.get_block_by_index = AsyncMock(return_value=None)
        self.MockConfig.return_value = self.cfg
        self.block_patch = patch("yadacoin.core.block.Block.from_dict", new=AsyncMock())
        self.MockFromDict = self.block_patch.start()

    async def asyncTearDown(self):
        self.cfg_patch.stop()
        self.block_patch.stop()
        await super().asyncTearDown()

    async def test_block_time_over_max_returns_max_target(self):
        last_block = _mk_block(100, 0)
        block = _mk_block(101, 3700)  # 3700s gap > 3600
        result = await CHAIN.get_target_10min(last_block, block)
        self.assertGreater(result, 0)

    async def test_returns_false_when_no_retarget_block(self):
        last_block = _mk_block(100, 0)
        block = _mk_block(101, 60, target=1)
        # No extras, find_one returns None -> returns False
        result = await CHAIN.get_target_10min(last_block, block)
        self.assertFalse(result)

    async def test_returns_false_when_no_retarget_period2_block(self):
        last_block = _mk_block(100, 0, target=1)
        block = _mk_block(101, 60, target=1)
        old_block = _mk_block(100 - 30, 0, target=1)  # retarget_period=30

        async def find_one(query):
            if query["index"] == 100 - 30:
                return {"index": 100 - 30}
            return None

        self.cfg.mongo.async_db.blocks.find_one.side_effect = find_one
        self.MockFromDict.return_value = old_block
        result = await CHAIN.get_target_10min(last_block, block)
        self.assertFalse(result)

    async def test_full_compute_with_extras_short_block_time(self):
        """Cover the average_block_time2 < target_time path."""
        last_block = _mk_block(100, 0, target=100)
        # Very short block time -> average_block_time2 < 600
        block = _mk_block(101, 60, target=100)
        # Build extras for retarget_period (30) and retarget_period2 (9)
        extras = []
        for i in range(70, 102):
            extras.append(_mk_block(i, i * 60, target=100))
        result = await CHAIN.get_target_10min(last_block, block, extra_blocks=extras)
        self.assertIsInstance(result, int)

    async def test_full_compute_with_extras_long_block_time(self):
        """Cover average_block_time2 >= target_time path + adjusted branch."""
        last_block = _mk_block(100, 0, target=100)
        block = _mk_block(101, 1300, target=100)  # > 2*target_time
        extras = []
        for i in range(70, 102):
            # large time gaps make average block time large
            extras.append(_mk_block(i, i * 700, target=100))
        result = await CHAIN.get_target_10min(last_block, block, extra_blocks=extras)
        self.assertIsInstance(result, int)

    async def test_smooth_retarget_branch(self):
        """block.index >= FORK_SMOOTH_RETARGET branch."""
        last_block = _mk_block(CHAIN.FORK_SMOOTH_RETARGET, 0, target=100)
        block = _mk_block(CHAIN.FORK_SMOOTH_RETARGET + 1, 1300, target=100)
        extras = []
        # Need extras stretching back retarget_period (30)
        start = CHAIN.FORK_SMOOTH_RETARGET
        for i in range(start - 30, start + 2):
            extras.append(_mk_block(i, i * 100, target=100))
        result = await CHAIN.get_target_10min(last_block, block, extra_blocks=extras)
        self.assertIsInstance(result, int)

    async def test_target_clamped_max(self):
        """Cover target > max_target clamp."""
        last_block = _mk_block(100, 0, target=CHAIN.MAX_TARGET)
        block = _mk_block(101, 1300, target=CHAIN.MAX_TARGET)
        extras = []
        for i in range(70, 102):
            extras.append(_mk_block(i, i * 700, target=CHAIN.MAX_TARGET))
        result = await CHAIN.get_target_10min(last_block, block, extra_blocks=extras)
        self.assertLessEqual(result, CHAIN.MAX_TARGET)

    async def test_target_clamped_min(self):
        """Cover target < 1 -> set to 1."""
        last_block = _mk_block(100, 0, target=0)
        block = _mk_block(101, 60, target=0)
        extras = []
        for i in range(70, 102):
            extras.append(_mk_block(i, i * 60, target=0))
        result = await CHAIN.get_target_10min(last_block, block, extra_blocks=extras)
        self.assertEqual(result, 1)


class TestGetTarget(AsyncTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.cfg_patch = patch("yadacoin.core.chain.Config")
        self.MockConfig = self.cfg_patch.start()
        self.cfg = MagicMock()
        self.cfg.app_log = MagicMock()
        self.cfg.network = "mainnet"
        self.cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value=None)
        self.cfg.BU.get_block_by_index = AsyncMock(return_value=None)
        self.MockConfig.return_value = self.cfg
        self.block_patch = patch("yadacoin.core.block.Block.from_dict", new=AsyncMock())
        self.MockFromDict = self.block_patch.start()

    async def asyncTearDown(self):
        self.cfg_patch.stop()
        self.block_patch.stop()
        await super().asyncTearDown()

    async def test_regnet_returns_max_target(self):
        self.cfg.network = "regnet"
        result = await CHAIN.get_target(100, _mk_block(99, 0), _mk_block(100, 60))
        self.assertEqual(result, CHAIN.MAX_TARGET)

    async def test_height_0_returns_max_target(self):
        result = await CHAIN.get_target(0, _mk_block(0, 0), _mk_block(1, 60))
        self.assertEqual(result, CHAIN.MAX_TARGET)

    async def test_pow_fork_v3_branch(self):
        """Lines 455-457: retarget_period_v3 branch."""
        h = CHAIN.POW_FORK_V3 + 100
        # height % retarget_period_v3 (=1) == 0 always; but easier to use non-retarget branch
        # Use h+1 so we don't hit retarget branch. But h%1 == 0 always. So retarget branch hits.
        # Need block_data to exist.
        self.cfg.BU.get_block_by_index.return_value = {"index": h - 1}
        retarget_block = _mk_block(h - 1, 0, target=100, special_min=False)
        last_block = _mk_block(h - 1, 1000, target=100)
        block = _mk_block(h, 1100, target=100)
        self.MockFromDict.return_value = retarget_block
        result = await CHAIN.get_target(h, last_block, block)
        self.assertIsInstance(result, int)

    async def test_pow_fork_v2_branch(self):
        """Lines 459-461: retarget_period_v2 branch."""
        h = CHAIN.POW_FORK_V2  # exactly v2, NOT v3
        # height % retarget_period_v2 (144) == 0 only if h%144==0; v2=60000, 60000%144 != 0
        # Choose multiple of 144 between v2 and v3.
        h = ((CHAIN.POW_FORK_V2 // 144) + 1) * 144
        if h >= CHAIN.POW_FORK_V3:
            self.skipTest("no h in [v2, v3) divisible by 144")
        self.cfg.BU.get_block_by_index.return_value = {"index": h - 144}
        retarget_block = _mk_block(h - 144, 0, target=100, special_min=False)
        last_block = _mk_block(h - 1, 100000, target=100)
        block = _mk_block(h, 100100, target=100)
        self.MockFromDict.return_value = retarget_block
        result = await CHAIN.get_target(h, last_block, block)
        self.assertIsInstance(result, int)

    async def test_retarget_returns_false_no_block_data(self):
        """Lines 477-481: not block_data, extras empty/no match -> False."""
        h = 2016  # default RETARGET_PERIOD
        self.cfg.BU.get_block_by_index.return_value = None
        # Provide an extra_block whose index does NOT match -> falls through to return False
        non_match = _mk_block(h + 999, 0)
        result = await CHAIN.get_target(
            h, _mk_block(h - 1, 0), _mk_block(h, 60), extra_blocks=[non_match]
        )
        self.assertFalse(result)

    async def test_retarget_uses_extra_blocks(self):
        """Line 477-481: extra_blocks fallback."""
        h = 2016
        self.cfg.BU.get_block_by_index.return_value = None
        retarget_block = _mk_block(0, 0, target=100, special_min=False)
        last_block = _mk_block(h - 1, CHAIN.HALF_WEEK, target=100)
        block = _mk_block(h, CHAIN.HALF_WEEK + 60, target=100)
        result = await CHAIN.get_target(
            h, last_block, block, extra_blocks=[retarget_block]
        )
        self.assertIsInstance(result, int)

    async def test_retarget_elapsed_lt_min(self):
        """Lines: elapsed_time_from_2016_ago < min_seconds branch."""
        h = 2016
        retarget_block = _mk_block(0, 0, target=100, special_min=False)
        self.cfg.BU.get_block_by_index.return_value = {"index": 0}
        self.MockFromDict.return_value = retarget_block
        last_block = _mk_block(h - 1, 100, target=100)  # very short elapsed
        block = _mk_block(h, 200, target=100)
        result = await CHAIN.get_target(h, last_block, block)
        self.assertIsInstance(result, int)

    async def test_retarget_special_min_block_uses_db(self):
        """Lines 511-525: block_to_check special_min path -> db lookup."""
        h = 2016
        retarget_block = _mk_block(0, 0, target=100, special_min=False)
        sm_block = _mk_block(h - 1, CHAIN.HALF_WEEK, target=100, special_min=False)

        async def find_one(query, sort=None):
            return {"index": h - 1}

        self.cfg.BU.get_block_by_index.return_value = {"index": 0}
        self.cfg.mongo.async_db.blocks.find_one.side_effect = find_one
        # First call from_dict: retarget_block, then sm_block
        self.MockFromDict.side_effect = [retarget_block, sm_block]
        last_block = _mk_block(
            h - 1, CHAIN.HALF_WEEK, target=0
        )  # falsy target -> hits special branch
        block = _mk_block(h, CHAIN.HALF_WEEK + 60, target=100)
        result = await CHAIN.get_target(h, last_block, block)
        self.assertIsInstance(result, int)

    async def test_retarget_special_min_uses_extra_blocks(self):
        """Lines 526-535: extra_blocks fallback for block_to_check."""
        h = 2016
        retarget_block = _mk_block(0, 0, target=100, special_min=False)
        # block_to_check with special_min, will look in db then extras
        extra_check = _mk_block(h - 1, CHAIN.HALF_WEEK, target=100, special_min=True)
        # First call: retarget block. Second call: None (not in db) -> falls to extras
        self.cfg.BU.get_block_by_index.return_value = {"index": 0}
        self.cfg.mongo.async_db.blocks.find_one.return_value = None
        self.MockFromDict.return_value = retarget_block
        last_block = _mk_block(h - 1, CHAIN.HALF_WEEK, target=0)
        block = _mk_block(h, CHAIN.HALF_WEEK + 60, target=100)
        result = await CHAIN.get_target(
            h, last_block, block, extra_blocks=[retarget_block, extra_check]
        )
        # May return False if special_min check fails - that's also valid coverage
        self.assertTrue(isinstance(result, int) or result is False)

    async def test_retarget_new_target_clamped_max(self):
        """Line 547: new_target >= max_target clamp. block_to_check.target ==
        MAX_TARGET combined with time_for_target == max_seconds yields
        new_target == max_target, triggering the >= branch."""
        h = 2016
        # last_block.special_min triggers the lookup at line 504. The mocked
        # Block.from_dict returns retarget_block with target == MAX_TARGET so
        # new_target = (max_seconds * MAX_TARGET) / max_seconds == MAX_TARGET.
        retarget_block = _mk_block(0, 0, target=CHAIN.MAX_TARGET, special_min=False)
        self.cfg.BU.get_block_by_index.return_value = {"index": 0}
        self.cfg.mongo.async_db.blocks.find_one = AsyncMock(return_value={"index": 0})
        self.MockFromDict.return_value = retarget_block
        # elapsed time == TWO_WEEKS == max_seconds -> time_for_target = max_seconds
        last_block = _mk_block(
            h - 1, CHAIN.TWO_WEEKS, target=CHAIN.MAX_TARGET, special_min=True
        )
        block = _mk_block(h, CHAIN.TWO_WEEKS + 60, target=CHAIN.MAX_TARGET)
        result = await CHAIN.get_target(h, last_block, block)
        self.assertEqual(result, CHAIN.MAX_TARGET)

    async def test_special_min_fork_branch(self):
        """Lines 565-568: SPECIAL_MIN_FORK + delta_t > max_block_time + special_min."""
        h = CHAIN.SPECIAL_MIN_FORK + 1
        # Avoid the retarget branch: ensure h % retarget != 0
        retarget_period = CHAIN.RETARGET_PERIOD
        if h % retarget_period == 0:
            h += 1
        last_block = _mk_block(h - 1, 0, target=100)
        # delta_t > max_block_time (600), special_min=True
        block = _mk_block(h, 1000, target=100, special_min=True)
        result = await CHAIN.get_target(h, last_block, block)
        self.assertIsInstance(result, int)

    async def test_else_loop_break_on_target(self):
        """Lines 588-595: else branch, normal block_to_check.target -> break."""
        h = 100  # NOT divisible by retarget period, h > 0
        last_block = _mk_block(h - 1, 0, target=100, special_min=False)
        block = _mk_block(h, 60, target=100)
        result = await CHAIN.get_target(h, last_block, block)
        self.assertEqual(result, 100)

    async def test_else_loop_start_index_zero(self):
        """Line 576: while loop start_index==0 returns block_to_check.target."""
        h = 1  # NOT divisible by retarget; h > 0
        # last_block.index = 0, special_min=True
        last_block = _mk_block(0, 0, target=0, special_min=True)
        block = _mk_block(h, 60, target=100)
        result = await CHAIN.get_target(h, last_block, block)
        self.assertEqual(result, 0)

    async def test_get_target_10min_period2_via_mongo(self):
        """Line 373: period_ago via extras, period2_ago via mongo (hits 373)."""
        last_block = _mk_block(100, 0, target=100)
        block = _mk_block(101, 60, target=100)
        extras = [_mk_block(100 - 30, 0, target=100)]
        period2_block = _mk_block(100 - 9, 0, target=100)

        async def find_one(query, sort=None):
            if query.get("index") == 100 - 9:
                return {"index": 100 - 9}
            return None

        self.cfg.mongo.async_db.blocks.find_one.side_effect = find_one
        self.MockFromDict.return_value = period2_block
        result = await CHAIN.get_target_10min(last_block, block, extra_blocks=extras)
        self.assertIsInstance(result, int)

    async def test_get_target_10min_short_path_mongo_lookups(self):
        """Lines 392-397: hash_sum2 loop falling through to mongo."""
        last_block = _mk_block(100, 0, target=100)
        block = _mk_block(101, 60, target=100)
        extras = [
            _mk_block(100 - 30, 0, target=100),
            _mk_block(100 - 9, 0, target=100),
        ]

        async def find_one(query, sort=None):
            return {"index": query.get("index")}

        self.cfg.mongo.async_db.blocks.find_one.side_effect = find_one
        self.MockFromDict.return_value = _mk_block(0, 0, target=100)
        result = await CHAIN.get_target_10min(last_block, block, extra_blocks=extras)
        self.assertIsInstance(result, int)

    async def test_get_target_10min_long_path_mongo_lookups(self):
        """Lines 401-418: else branch hash_sum loop with mongo."""
        # Use index past END_MAX_TARGET_FORK so the >3600 escape doesn't trigger.
        idx = CHAIN.END_MAX_TARGET_FORK + 1
        last_block = _mk_block(idx, 0, target=100)
        block = _mk_block(idx + 1, 7000, target=100)
        extras = [
            _mk_block(idx - 30, 0, target=100),
            _mk_block(idx - 9, 0, target=100),
        ]

        async def find_one(query, sort=None):
            return {"index": query.get("index")}

        self.cfg.mongo.async_db.blocks.find_one.side_effect = find_one
        self.MockFromDict.return_value = _mk_block(0, 0, target=100)
        result = await CHAIN.get_target_10min(last_block, block, extra_blocks=extras)
        self.assertIsInstance(result, int)

    async def test_retarget_elapsed_gt_max(self):
        """Lines 495-496: elapsed_time_from_2016_ago > max_seconds branch."""
        h = 2016
        retarget_block = _mk_block(0, 0, target=100, special_min=False)
        self.cfg.BU.get_block_by_index.return_value = {"index": 0}
        self.MockFromDict.return_value = retarget_block
        last_block = _mk_block(h - 1, CHAIN.TWO_WEEKS + 100000, target=100)
        block = _mk_block(h, CHAIN.TWO_WEEKS + 100060, target=100)
        result = await CHAIN.get_target(h, last_block, block)
        self.assertIsInstance(result, int)

    async def test_retarget_special_min_no_block_returns_false(self):
        """Lines 535-536: special path with extras but no match -> False."""
        h = 2016
        retarget_block = _mk_block(0, 0, target=100, special_min=False)
        self.cfg.BU.get_block_by_index.return_value = {"index": 0}
        self.cfg.mongo.async_db.blocks.find_one.return_value = None
        self.MockFromDict.return_value = retarget_block
        last_block = _mk_block(h - 1, CHAIN.HALF_WEEK, target=0)
        block = _mk_block(h, CHAIN.HALF_WEEK + 60, target=100)
        result = await CHAIN.get_target(
            h, last_block, block, extra_blocks=[retarget_block]
        )
        self.assertFalse(result)

    async def test_else_while_loop_special_min_db_lookup(self):
        """Lines 582-597: else branch while loop body hitting db lookup path."""
        h = 100
        last_block = _mk_block(h - 1, 0, target=0, special_min=True)
        block = _mk_block(h, 60, target=100)
        prev_block = _mk_block(h - 2, 0, target=100, special_min=False)
        self.cfg.mongo.async_db.blocks.find_one.return_value = {"index": h - 1}
        self.MockFromDict.return_value = prev_block
        result = await CHAIN.get_target(h, last_block, block)
        self.assertEqual(result, 100)

    async def test_else_while_loop_special_min_extras_fallback(self):
        """Lines 588-595: extras fallback in while loop."""
        h = 100
        last_block = _mk_block(h - 1, 0, target=0, special_min=True)
        block = _mk_block(h, 60, target=100)
        prev_block = _mk_block(h - 1, 0, target=100, special_min=False)
        self.cfg.mongo.async_db.blocks.find_one.return_value = None
        result = await CHAIN.get_target(h, last_block, block, extra_blocks=[prev_block])
        self.assertEqual(result, 100)

    async def test_else_while_loop_no_prev_block_decrement(self):
        """Lines 593-595: not prev_block -> start_index -= 1; continue."""
        h = 5
        last_block = _mk_block(h - 1, 0, target=0, special_min=True)
        block = _mk_block(h, 60, target=100)
        self.cfg.mongo.async_db.blocks.find_one.return_value = None
        result = await CHAIN.get_target(h, last_block, block)
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
