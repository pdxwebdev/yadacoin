"""
Common helper functions to factorize code
"""

from datetime import datetime


def ts_to_utc(timestamp):
    return datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%dT%H:%M:%S UTC")


# Temp. Kept for compatibility reasons
def changetime(thing):
    if thing.get("txn"):
        thing.update(thing["txn"])
        del thing["txn"]
    thing["time"] = datetime.utcfromtimestamp(int(thing["time"])).strftime(
        "%Y-%m-%dT%H:%M:%S UTC"
    )
    return thing


def abstract_block(block):
    """Only keep header and miner info, no transaction detail"""
    abstract = dict(block)
    transactions = abstract.pop("transactions")
    for transaction in transactions:
        if len(transaction["inputs"]) == 0:
            abstract["miner"] = transaction["outputs"][0]["to"]
            abstract["reward"] = transaction["outputs"][0]["value"]
    abstract["tx_count"] = len(transactions)
    abstract["time_utc"] = ts_to_utc(abstract["time"])
    return abstract
