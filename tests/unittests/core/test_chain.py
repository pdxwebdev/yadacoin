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


class TestGetBlockRewardDeprecated(unittest.TestCase):
    def test_block_0_reward(self):
        from unittest.mock import MagicMock

        import yadacoin.core.config as cfg

        # Need LatestBlock to be set
        mock_lb = MagicMock()
        mock_lb.block.index = 0
        # Save and restore
        old_instance = cfg.Config._instance
        try:
            c = cfg.Config.__new__(cfg.Config)
            c.initialized = True
            c.LatestBlock = mock_lb
            cfg.Config._instance = c
            reward = CHAIN.get_block_reward_deprecated(0)
            self.assertAlmostEqual(reward, 50.0)
        finally:
            cfg.Config._instance = old_instance

    def test_returns_zero_for_very_high_block(self):
        from unittest.mock import MagicMock

        import yadacoin.core.config as cfg

        mock_lb = MagicMock()
        mock_lb.block.index = 0
        old_instance = cfg.Config._instance
        try:
            c = cfg.Config.__new__(cfg.Config)
            c.initialized = True
            c.LatestBlock = mock_lb
            cfg.Config._instance = c
            reward = CHAIN.get_block_reward_deprecated(99999999)
            self.assertEqual(reward, 0.0)
        finally:
            cfg.Config._instance = old_instance


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


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
