import base64

from coincurve import verify_signature

from yadacoin.core.nodes import SeedGateways, Seeds, ServiceProviders

from ..test_setup import AsyncTestCase


class TestBlock(AsyncTestCase):
    async def test_nodes_valid(self):
        for i, seed_list in Seeds.NODES.items():
            for seed in seed_list:
                result = verify_signature(
                    base64.b64decode(seed.identity.username_signature),
                    seed.identity.username.encode(),
                    bytes.fromhex(seed.identity.public_key),
                )
                self.assertTrue(result)
        for i, seed_gateway_list in SeedGateways.NODES.items():
            for seed_gateway in seed_gateway_list:
                result = verify_signature(
                    base64.b64decode(seed_gateway.identity.username_signature),
                    seed_gateway.identity.username.encode(),
                    bytes.fromhex(seed_gateway.identity.public_key),
                )
                self.assertTrue(result)
        for i, service_provider_list in ServiceProviders.NODES.items():
            for service_provider in service_provider_list:
                result = verify_signature(
                    base64.b64decode(service_provider.identity.username_signature),
                    service_provider.identity.username.encode(),
                    bytes.fromhex(service_provider.identity.public_key),
                )
                self.assertTrue(result)
