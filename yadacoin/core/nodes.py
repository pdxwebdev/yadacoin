from bitcoin.wallet import P2PKHBitcoinAddress
from yadacoin.core.peer import Seed, SeedGateway, ServiceProvider


class Nodes:
    fork_points = [0]

    @classmethod
    def get_fork_for_block_height(cls, height):
        prev = 0
        for x in cls.fork_points:
            if height < x:
                return prev
            prev = x
        return prev

    _get_nodes_for_block_height_cache = {
        "Seeds": {},
        "SeedGateways": {},
        "ServiceProviders": {},
    }

    @classmethod
    def get_nodes_for_block_height(cls, height, fork_point=None):
        if fork_point is None:
            fork_point = cls.get_fork_for_block_height(height)
        if fork_point not in cls._get_nodes_for_block_height_cache[cls.__name__]:
            cls._get_nodes_for_block_height_cache[cls.__name__][fork_point] = cls.NODES[
                fork_point
            ]
        return cls._get_nodes_for_block_height_cache[cls.__name__][fork_point]

    @classmethod
    def get_all_nodes_for_block_height(cls, height):
        fork_point = cls.get_fork_for_block_height(height)
        return (
            Seeds.get_nodes_for_block_height(height, fork_point)
            + SeedGateways.get_nodes_for_block_height(height, fork_point)
            + ServiceProviders.get_nodes_for_block_height(height, fork_point),
        )[fork_point]

    @classmethod
    def get_all_nodes_indexed_by_address_for_block_height(cls, height):
        nodes = cls.get_all_nodes_for_block_height(height)
        return {
            str(
                P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(node.identity.public_key))
            ): node
            for node in nodes
        }


class Seeds(Nodes):
    NODES = {
        0: [
            Seed.from_dict(
                {
                    "host": "yadacoin.io",
                    "port": 8000,
                    "identity": {
                        "username": "",
                        "username_signature": "MEUCIQCP+rF5R4sZ7pHJCBAWHxARLg9GN4dRw+/pobJ0MPmX3gIgX0RD4OxhSS9KPJTUonYI1Tr+ZI2N9uuoToZo1RGOs2M=",
                        "public_key": "02fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc",
                    },
                    "seed_gateway": "MEQCIHONdT7i8K+ZTzv3PHyPAhYkaksoh6FxEJUmPLmXZqFPAiBHOnt1CjgMtNzCGdBk/0S/oikPzJVys32bgThxXtAbgQ==",
                }
            ),
            Seed.from_dict(
                {
                    "host": "seed.hashyada.com",
                    "port": 8002,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIHrMlgx3RzvLg+8eU1LXfY5QLk2le1mOUM2JLnRSSqTRAiByXKWP7cKasX2kB9VqIm43wT004evxNRQX+YYl5I30jg==",
                        "public_key": "0254c7e913ebf0c49c80129c7acc306033a62ac52219ec03e41a6f0a2549b91658",
                    },
                    "seed_gateway": "MEQCIF3Wlbk99pgxKVrb6Iqdd6L5AJMJgVhc9rrB64P+oHhKAiAfTDCx1GaSWYUyX69k+7GuctPeEclpdXCbR0vly/q77A==",
                }
            ),
            Seed.from_dict(
                {
                    "host": "seedau.hashyada.com",
                    "port": 8002,
                    "identity": {
                        "username": "",
                        "username_signature": "MEUCIQDndXZRuUTF/l8ANXHvOaWW4+u/8yJPHhGoo80L4AdwrgIgGJtUm+1h/PGrBaqtKwZuNVYcDh6t/yEM/aT3ryYVCMU=",
                        "public_key": "029fa1eed6c2129f2eb00729c06bd945282c193b09f4cb566738b488268ed131bf",
                    },
                    "seed_gateway": "MEQCIAfwzpFwXbBqKpAWAK10D89EiVw4TzJZL6lnAyMzangsAiBclX/x4vn+KT0y92bDrB6vaX6zQ9otAndoOyI8wonTFw==",
                }
            ),
        ],
        443500: [
            Seed.from_dict(
                {
                    "host": "yadacoin.io",
                    "port": 8000,
                    "identity": {
                        "username": "",
                        "username_signature": "MEUCIQCP+rF5R4sZ7pHJCBAWHxARLg9GN4dRw+/pobJ0MPmX3gIgX0RD4OxhSS9KPJTUonYI1Tr+ZI2N9uuoToZo1RGOs2M=",
                        "public_key": "02fa9550f57055c96c7ce4c6c9cd1411856beba5c7d5a07417e980a39aa03da3dc",
                    },
                    "seed_gateway": "MEQCIHONdT7i8K+ZTzv3PHyPAhYkaksoh6FxEJUmPLmXZqFPAiBHOnt1CjgMtNzCGdBk/0S/oikPzJVys32bgThxXtAbgQ==",
                }
            ),
            Seed.from_dict(
                {
                    "host": "seed.hashyada.com",
                    "port": 8002,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIHrMlgx3RzvLg+8eU1LXfY5QLk2le1mOUM2JLnRSSqTRAiByXKWP7cKasX2kB9VqIm43wT004evxNRQX+YYl5I30jg==",
                        "public_key": "0254c7e913ebf0c49c80129c7acc306033a62ac52219ec03e41a6f0a2549b91658",
                    },
                    "seed_gateway": "MEQCIF3Wlbk99pgxKVrb6Iqdd6L5AJMJgVhc9rrB64P+oHhKAiAfTDCx1GaSWYUyX69k+7GuctPeEclpdXCbR0vly/q77A==",
                }
            ),
            Seed.from_dict(
                {
                    "host": "seedau.hashyada.com",
                    "port": 8002,
                    "identity": {
                        "username": "",
                        "username_signature": "MEUCIQDndXZRuUTF/l8ANXHvOaWW4+u/8yJPHhGoo80L4AdwrgIgGJtUm+1h/PGrBaqtKwZuNVYcDh6t/yEM/aT3ryYVCMU=",
                        "public_key": "029fa1eed6c2129f2eb00729c06bd945282c193b09f4cb566738b488268ed131bf",
                    },
                    "seed_gateway": "MEQCIAfwzpFwXbBqKpAWAK10D89EiVw4TzJZL6lnAyMzangsAiBclX/x4vn+KT0y92bDrB6vaX6zQ9otAndoOyI8wonTFw==",
                }
            ),
            Seed.from_dict(
                {
                    "host": "seed.crbrain.online",
                    "port": 8000,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIE1NbKkxlr6lOAETGPL5BXmI5+pcADnieJ7Je8rHcdv9AiBcS4garwsDGhILMU4Chwd8pJAg0JFcmVTGHZ2wIA/y4Q==",
                        "public_key": "020d96b95281506e3e7f03ae3bbb7a91ddf6a6eb573d88fca88d292923be9f9f8d",
                    },
                    "seed_gateway": "MEUCIQCa8eobxfvfSM4E6ipM1qRFYXJVKdj1g3NiS+ZotzdNswIgNbJwvU/g+myeyr9FWSH+jDlPTavGO/tDLyRnjLGB+vQ=",
                }
            ),
        ],
    }


class SeedGateways(Nodes):
    NODES = {
        0: [
            SeedGateway.from_dict(
                {
                    "host": "remotelyrich.com",
                    "port": 8000,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIHONdT7i8K+ZTzv3PHyPAhYkaksoh6FxEJUmPLmXZqFPAiBHOnt1CjgMtNzCGdBk/0S/oikPzJVys32bgThxXtAbgQ==",
                        "public_key": "03362203ee71bc15918a7992f3c76728fc4e45f4916d2c0311c37aad0f736b26b9",
                    },
                    "seed": "MEUCIQCP+rF5R4sZ7pHJCBAWHxARLg9GN4dRw+/pobJ0MPmX3gIgX0RD4OxhSS9KPJTUonYI1Tr+ZI2N9uuoToZo1RGOs2M=",
                }
            ),
            SeedGateway.from_dict(
                {
                    "host": "seedgateway.hashyada.com",
                    "port": 8004,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIF3Wlbk99pgxKVrb6Iqdd6L5AJMJgVhc9rrB64P+oHhKAiAfTDCx1GaSWYUyX69k+7GuctPeEclpdXCbR0vly/q77A==",
                        "public_key": "0399f61da3f69d3e1600269c9a946a4c21d3a933d5362f9db613d33fb6a0cb164e",
                    },
                    "seed": "MEQCIHrMlgx3RzvLg+8eU1LXfY5QLk2le1mOUM2JLnRSSqTRAiByXKWP7cKasX2kB9VqIm43wT004evxNRQX+YYl5I30jg==",
                }
            ),
            SeedGateway.from_dict(
                {
                    "host": "seedgatewayau.hashyada.com",
                    "port": 8004,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIAfwzpFwXbBqKpAWAK10D89EiVw4TzJZL6lnAyMzangsAiBclX/x4vn+KT0y92bDrB6vaX6zQ9otAndoOyI8wonTFw==",
                        "public_key": "02ea1f0f1214196f8e59616ec1b670e06f9decd250d1eaa345cf6a4667523bbecb",
                    },
                    "seed": "MEUCIQDndXZRuUTF/l8ANXHvOaWW4+u/8yJPHhGoo80L4AdwrgIgGJtUm+1h/PGrBaqtKwZuNVYcDh6t/yEM/aT3ryYVCMU=",
                }
            ),
        ],
        443500: [
            SeedGateway.from_dict(
                {
                    "host": "remotelyrich.com",
                    "port": 8000,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIHONdT7i8K+ZTzv3PHyPAhYkaksoh6FxEJUmPLmXZqFPAiBHOnt1CjgMtNzCGdBk/0S/oikPzJVys32bgThxXtAbgQ==",
                        "public_key": "03362203ee71bc15918a7992f3c76728fc4e45f4916d2c0311c37aad0f736b26b9",
                    },
                    "seed": "MEUCIQCP+rF5R4sZ7pHJCBAWHxARLg9GN4dRw+/pobJ0MPmX3gIgX0RD4OxhSS9KPJTUonYI1Tr+ZI2N9uuoToZo1RGOs2M=",
                }
            ),
            SeedGateway.from_dict(
                {
                    "host": "seedgateway.hashyada.com",
                    "port": 8004,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIF3Wlbk99pgxKVrb6Iqdd6L5AJMJgVhc9rrB64P+oHhKAiAfTDCx1GaSWYUyX69k+7GuctPeEclpdXCbR0vly/q77A==",
                        "public_key": "0399f61da3f69d3e1600269c9a946a4c21d3a933d5362f9db613d33fb6a0cb164e",
                    },
                    "seed": "MEQCIHrMlgx3RzvLg+8eU1LXfY5QLk2le1mOUM2JLnRSSqTRAiByXKWP7cKasX2kB9VqIm43wT004evxNRQX+YYl5I30jg==",
                }
            ),
            SeedGateway.from_dict(
                {
                    "host": "seedgatewayau.hashyada.com",
                    "port": 8004,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIAfwzpFwXbBqKpAWAK10D89EiVw4TzJZL6lnAyMzangsAiBclX/x4vn+KT0y92bDrB6vaX6zQ9otAndoOyI8wonTFw==",
                        "public_key": "02ea1f0f1214196f8e59616ec1b670e06f9decd250d1eaa345cf6a4667523bbecb",
                    },
                    "seed": "MEUCIQDndXZRuUTF/l8ANXHvOaWW4+u/8yJPHhGoo80L4AdwrgIgGJtUm+1h/PGrBaqtKwZuNVYcDh6t/yEM/aT3ryYVCMU=",
                }
            ),
            SeedGateway.from_dict(
                {
                    "host": "seedgateway.crbrain.online",
                    "port": 8000,
                    "identity": {
                        "username": "",
                        "username_signature": "MEUCIQCa8eobxfvfSM4E6ipM1qRFYXJVKdj1g3NiS+ZotzdNswIgNbJwvU/g+myeyr9FWSH+jDlPTavGO/tDLyRnjLGB+vQ=",
                        "public_key": "031a2a3d5f6c7698c20e46fd426bd31b2a30085bfaa1707b430f651899a5f2a5d9",
                    },
                    "seed": "MEQCIE1NbKkxlr6lOAETGPL5BXmI5+pcADnieJ7Je8rHcdv9AiBcS4garwsDGhILMU4Chwd8pJAg0JFcmVTGHZ2wIA/y4Q==",
                }
            ),
        ],
    }


class ServiceProviders(Nodes):
    NODES = {
        0: [
            ServiceProvider.from_dict(
                {
                    "host": "centeridentity.com",
                    "port": 8000,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIC7ADPLI3VPDNpQPaXAeB8gUk2LrvZDJIdEg9C12dj5PAiB61Te/sen1D++EJAcgnGLH4iq7HTZHv/FNByuvu4PrrA==",
                        "public_key": "02a9aed3a4d69013246d24e25ded69855fbd590cb75b4a90fbfdc337111681feba",
                    },
                    "seed_gateway": "MEQCIHONdT7i8K+ZTzv3PHyPAhYkaksoh6FxEJUmPLmXZqFPAiBHOnt1CjgMtNzCGdBk/0S/oikPzJVys32bgThxXtAbgQ==",
                    "seed": "MEUCIQCP+rF5R4sZ7pHJCBAWHxARLg9GN4dRw+/pobJ0MPmX3gIgX0RD4OxhSS9KPJTUonYI1Tr+ZI2N9uuoToZo1RGOs2M=",
                }
            ),
            ServiceProvider.from_dict(
                {
                    "host": "serviceprovider.hashyada.com",
                    "port": 8006,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIDs4GfdyUMFMptmtXsn2vbgQ+rIBfT50nkm++v9swNsjAiA15mHrFehtusgqszbMI5S3nIXQYBUM8Q3smZ615PjL1w==",
                        "public_key": "023c1bb0de2b8b10f4ff84e13dc6c8d02e113ed297b83e561ca6b302cb70377f0e",
                    },
                    "seed_gateway": "MEQCIF3Wlbk99pgxKVrb6Iqdd6L5AJMJgVhc9rrB64P+oHhKAiAfTDCx1GaSWYUyX69k+7GuctPeEclpdXCbR0vly/q77A==",
                    "seed": "MEQCIHrMlgx3RzvLg+8eU1LXfY5QLk2le1mOUM2JLnRSSqTRAiByXKWP7cKasX2kB9VqIm43wT004evxNRQX+YYl5I30jg==",
                }
            ),
            ServiceProvider.from_dict(
                {
                    "host": "serviceproviderau.hashyada.com",
                    "port": 8006,
                    "identity": {
                        "username": "",
                        "username_signature": "MEUCIQDvnHZnh1T5dilboTJdYhNT1Rf18SZxDLpNf6TT90RZZwIgXuIvlOVyxepRkskItsTUSaSlZdl9EkzlTP4UEFZ9zmQ=",
                        "public_key": "02852ea36ef2ccb1274f473d7c65f7fa59731cdfd99c2fc04fd30b097b3b457e6a",
                    },
                    "seed_gateway": "MEQCIAfwzpFwXbBqKpAWAK10D89EiVw4TzJZL6lnAyMzangsAiBclX/x4vn+KT0y92bDrB6vaX6zQ9otAndoOyI8wonTFw==",
                    "seed": "MEUCIQDndXZRuUTF/l8ANXHvOaWW4+u/8yJPHhGoo80L4AdwrgIgGJtUm+1h/PGrBaqtKwZuNVYcDh6t/yEM/aT3ryYVCMU=",
                }
            ),
        ],
        443500: [
            ServiceProvider.from_dict(
                {
                    "host": "centeridentity.com",
                    "port": 8000,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIC7ADPLI3VPDNpQPaXAeB8gUk2LrvZDJIdEg9C12dj5PAiB61Te/sen1D++EJAcgnGLH4iq7HTZHv/FNByuvu4PrrA==",
                        "public_key": "02a9aed3a4d69013246d24e25ded69855fbd590cb75b4a90fbfdc337111681feba",
                    },
                    "seed_gateway": "MEQCIHONdT7i8K+ZTzv3PHyPAhYkaksoh6FxEJUmPLmXZqFPAiBHOnt1CjgMtNzCGdBk/0S/oikPzJVys32bgThxXtAbgQ==",
                    "seed": "MEUCIQCP+rF5R4sZ7pHJCBAWHxARLg9GN4dRw+/pobJ0MPmX3gIgX0RD4OxhSS9KPJTUonYI1Tr+ZI2N9uuoToZo1RGOs2M=",
                }
            ),
            ServiceProvider.from_dict(
                {
                    "host": "serviceprovider.hashyada.com",
                    "port": 8006,
                    "identity": {
                        "username": "",
                        "username_signature": "MEQCIDs4GfdyUMFMptmtXsn2vbgQ+rIBfT50nkm++v9swNsjAiA15mHrFehtusgqszbMI5S3nIXQYBUM8Q3smZ615PjL1w==",
                        "public_key": "023c1bb0de2b8b10f4ff84e13dc6c8d02e113ed297b83e561ca6b302cb70377f0e",
                    },
                    "seed_gateway": "MEQCIF3Wlbk99pgxKVrb6Iqdd6L5AJMJgVhc9rrB64P+oHhKAiAfTDCx1GaSWYUyX69k+7GuctPeEclpdXCbR0vly/q77A==",
                    "seed": "MEQCIHrMlgx3RzvLg+8eU1LXfY5QLk2le1mOUM2JLnRSSqTRAiByXKWP7cKasX2kB9VqIm43wT004evxNRQX+YYl5I30jg==",
                }
            ),
            ServiceProvider.from_dict(
                {
                    "host": "serviceproviderau.hashyada.com",
                    "port": 8006,
                    "identity": {
                        "username": "",
                        "username_signature": "MEUCIQDvnHZnh1T5dilboTJdYhNT1Rf18SZxDLpNf6TT90RZZwIgXuIvlOVyxepRkskItsTUSaSlZdl9EkzlTP4UEFZ9zmQ=",
                        "public_key": "02852ea36ef2ccb1274f473d7c65f7fa59731cdfd99c2fc04fd30b097b3b457e6a",
                    },
                    "seed_gateway": "MEQCIAfwzpFwXbBqKpAWAK10D89EiVw4TzJZL6lnAyMzangsAiBclX/x4vn+KT0y92bDrB6vaX6zQ9otAndoOyI8wonTFw==",
                    "seed": "MEUCIQDndXZRuUTF/l8ANXHvOaWW4+u/8yJPHhGoo80L4AdwrgIgGJtUm+1h/PGrBaqtKwZuNVYcDh6t/yEM/aT3ryYVCMU=",
                }
            ),
            ServiceProvider.from_dict(
                {
                    "host": "serviceprovider.crbrain.online",
                    "port": 8000,
                    "identity": {
                        "username": "",
                        "username_signature": "MEUCIQChurCpzDcki2m8qWjYrU/BZXFLXpwtUXDUltXY/B261AIgfzBQKuMm5nKrKAnA9SUCtS0vdBsVbIF592cK28Dpvfg=",
                        "public_key": "03e0dabdd40c7ccb6859131b5c2968e6ac6099222eee51f10ba7d3549f4ae465e3",
                    },
                    "seed_gateway": "MEUCIQCa8eobxfvfSM4E6ipM1qRFYXJVKdj1g3NiS+ZotzdNswIgNbJwvU/g+myeyr9FWSH+jDlPTavGO/tDLyRnjLGB+vQ=",
                    "seed": "MEQCIE1NbKkxlr6lOAETGPL5BXmI5+pcADnieJ7Je8rHcdv9AiBcS4garwsDGhILMU4Chwd8pJAg0JFcmVTGHZ2wIA/y4Q==",
                }
            ),
        ],
    }
