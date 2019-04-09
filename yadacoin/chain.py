"""
This is a class to store the global chain params
"""



class CHAIN(object):

    # Max possible target for a block
    MAX_TARGET = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    MAX_TARGET_HEX = 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'

    # The fork checkpoints, so we have a single reference for all the codebase and can use explicit names for forks.
    POW_FORK_60000 = 60000

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
    def special_min_trigger(cls, network:str, block_height:int):
        """When should special_min be activated?"""
        # For testnet and regnet, special min triggers at target_block_time + 1
        if network == 'testnet':
            return 10 + 1
        elif network == 'regnet':
            return 1 +1
        elif network == 'mainnet':
            if block_height < cls.POW_FORK_60000:
                return 600
            else:
                return 600 * 2
        raise ValueError("Unknown network")