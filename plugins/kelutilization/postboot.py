"""
postboot.py — startup hook for the kelutilization plugin.

Required indexes (blocks.transactions.time and
blocks.transactions.prerotated_key_hash) are already managed by mongo.py.
"""


async def go(app):
    pass
