"""
Temp. test for block reward function precision
"""

import sys
import random

sys.path.append('../')
from yadacoin.chain import CHAIN


if __name__ == "__main__":
    for i in range(1000):
        index = random.randint(1, 6930000+21000)
        value1 = CHAIN.get_block_reward_deprecated(index)
        value2 = CHAIN.get_block_reward(index)
        if value1 != value2:
            print("Error", index, value1, value2)

    # boundary tests
    test2 = (2519999, 2520000, 2520001, 2729999, 2730000, 2730001)
    for index in test2:
        value1 = CHAIN.get_block_reward_deprecated(index)
        value2 = CHAIN.get_block_reward(index)
        if value1 != value2:
            print("Error2", index, value1, value2)

