"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64

from coincurve import verify_signature

from yadacoin.core.nodes import SeedGateways, Seeds, ServiceProviders

from ..test_setup import AsyncTestCase


class TestBlock(AsyncTestCase):
    async def test_set_nodes(self):
        Seeds().set_fork_points()
        Seeds().set_nodes()
        assert len(Seeds().NODES[467700]) == 11
        assert len(Seeds().NODES[472000]) == 11
        assert len(Seeds().NODES[477000]) == 12

        Seeds()._NODES = [
            {"ranges": [(0, 1)], "node": 1},
            {"ranges": [(1, 3)], "node": 2},
            {"ranges": [(0, None)], "node": 3},
            {"ranges": [(3, None)], "node": 4},
        ]
        Seeds().set_fork_points()
        Seeds().set_nodes()
        assert len(Seeds().NODES[0]) == 2
        assert len(Seeds().NODES[1]) == 2
        assert len(Seeds().NODES[3]) == 2

        assert Seeds().NODES[0][0] == 1
        assert Seeds().NODES[0][1] == 3

        assert Seeds().NODES[1][0] == 2
        assert Seeds().NODES[1][1] == 3

        assert Seeds().NODES[3][0] == 3
        assert Seeds().NODES[3][1] == 4

    async def test_nodes_valid(self):
        for i, seed_list in Seeds().NODES.items():
            for seed in seed_list:
                result = verify_signature(
                    base64.b64decode(seed.identity.username_signature),
                    seed.identity.username.encode(),
                    bytes.fromhex(seed.identity.public_key),
                )
                self.assertTrue(result)
        for i, seed_gateway_list in SeedGateways().NODES.items():
            for seed_gateway in seed_gateway_list:
                result = verify_signature(
                    base64.b64decode(seed_gateway.identity.username_signature),
                    seed_gateway.identity.username.encode(),
                    bytes.fromhex(seed_gateway.identity.public_key),
                )
                self.assertTrue(result)
        for i, service_provider_list in ServiceProviders().NODES.items():
            for service_provider in service_provider_list:
                result = verify_signature(
                    base64.b64decode(service_provider.identity.username_signature),
                    service_provider.identity.username.encode(),
                    bytes.fromhex(service_provider.identity.public_key),
                )
                self.assertTrue(result)
