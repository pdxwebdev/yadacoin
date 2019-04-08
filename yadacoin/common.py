"""
Common helper functions to factorize code
"""

from datetime import datetime


def ts_to_utc(timestamp):
    return datetime.utcfromtimestamp(int(timestamp)).strftime('%Y-%m-%dT%H:%M:%S UTC')