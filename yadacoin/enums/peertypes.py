"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from enum import Enum


class PEER_TYPES(Enum):
    SEED = "seed"
    SEED_GATEWAY = "seed_gateway"
    SERVICE_PROVIDER = "service_provider"
    USER = "user"
    POOL = "pool"
