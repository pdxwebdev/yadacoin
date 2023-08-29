from enum import Enum


class PEER_TYPES(Enum):
    SEED = "seed"
    SEED_GATEWAY = "seed_gateway"
    SERVICE_PROVIDER = "service_provider"
    USER = "user"
    POOL = "pool"
