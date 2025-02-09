from collections import defaultdict

from bitcoin.wallet import P2PKHBitcoinAddress

from yadacoin.core.peer import Seed, SeedGateway, ServiceProvider


class Nodes:
    @classmethod
    def set_fork_points(cls):
        cls().fork_points = []
        for NODE in cls()._NODES:
            for rng in NODE["ranges"]:
                cls().fork_points.append(rng[0])
        cls().fork_points = sorted(list(set(cls().fork_points)))

    @classmethod
    def set_nodes(cls):
        cls().NODES = defaultdict(list)
        for fork_point in cls().fork_points:
            for NODE in cls()._NODES:
                for rng in NODE["ranges"]:
                    if rng[1] and rng[1] <= fork_point:
                        continue
                    if rng[0] <= fork_point:
                        cls().NODES[fork_point].append(NODE["node"])

    @classmethod
    def get_fork_for_block_height(cls, height):
        prev = 0
        for x in cls().fork_points:
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
    def get_nodes_for_block_height(cls, height):
        fork_point = cls().get_fork_for_block_height(height)
        if fork_point is None:
            fork_point = cls().get_fork_for_block_height(height)
        if fork_point not in cls()._get_nodes_for_block_height_cache[cls.__name__]:
            cls()._get_nodes_for_block_height_cache[cls.__name__][
                fork_point
            ] = cls().NODES[fork_point]
        return cls()._get_nodes_for_block_height_cache[cls.__name__][fork_point]

    @classmethod
    def get_all_nodes_for_block_height(cls, height):
        return (
            Seeds.get_nodes_for_block_height(height)
            + SeedGateways.get_nodes_for_block_height(height)
            + ServiceProviders.get_nodes_for_block_height(height),
        )[0]

    @classmethod
    def get_all_nodes_indexed_by_address_for_block_height(cls, height):
        nodes = cls().get_all_nodes_for_block_height(height)
        return {
            str(
                P2PKHBitcoinAddress.from_pubkey(bytes.fromhex(node.identity.public_key))
            ): node
            for node in nodes
        }


class Seeds(Nodes):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Seeds, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return
        self.initialized = True
        self._NODES = [
            {
                "ranges": [(0, None)],
                "node": Seed.from_dict(
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
            },
            {
                "ranges": [(0, None)],
                "node": Seed.from_dict(
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
            },
            {
                "ranges": [(0, None)],
                "node": Seed.from_dict(
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
            },
            {
                "ranges": [(443600, None)],
                "node": Seed.from_dict(
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
            },
            {
                "ranges": [(443700, None)],
                "node": Seed.from_dict(
                    {
                        "host": "yada-alpha.mynodes.live",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCICCXzIpmoNdU2sZsI35lqIl1bt5W1MW49NhjO95S2wlSAiAY04erBPVYvLWJ1SJCm5FtgJ3hyikVH3sw/fGlNUYuGQ==",
                            "public_key": "039f52499e24b192ffd3f93d161965816d1fd41c4f8963fdd654067034e2716e93",
                        },
                        "seed_gateway": "MEQCIFvpbWRQU9Ty4JXxoGH4YXgR8RiLoLBm11RNKBVeaz4GAiAyGMbhXc+J+z5VIh2GGJi9uDsqdPpEweerViSrxpxzPQ==",
                    }
                ),
            },
            {
                "ranges": [(446400, None)],
                "node": Seed.from_dict(
                    {
                        "host": "seed.yada.toksyk.pl",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQCOONwPlGftYSOGfzCnRGT0y5DH401G6I8nDNwbsYemfQIgBP7XketGtzfsocIR82xjyMYt06j3VY59yO6w6SXwMjk=",
                            "public_key": "033bd1fea8397cd471333ddd27c43a0d580dde3d477efa7ee1ffe61a770f26e256",
                        },
                        "seed_gateway": "MEQCIAvo5gGrW6Uod4L6Qo5bekaKpursERu0UII1VTCR1i8zAiAW4UeZD/GKevh3/lSezWaFHZ4+oBq5wTCggEpvCljhUA==",
                    }
                ),
            },
            {
                "ranges": [(449000, None)],
                "node": Seed.from_dict(
                    {
                        "host": "seed.darksidetx.net",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQDArjnhho8q8tCxHLmgvuDDS4qdSgQx1y7aNEGYHi/4ywIgWG/aboG4krfQQ4MS5MaPkedsc1syIbz+jfAGsg/siG4=",
                            "public_key": "02549a9dc415bc2fd7a4ad8d3ead9be82d051ff605590db8781f45b3f8c5ede431",
                        },
                        "seed_gateway": "MEUCIQDFjb4L3Pv0GaBqdzB0WazxMjUQ8cNG7FBY/v/n9yUgIwIgA+FFy88yMIWqM6fyIeariS4EpyZj33JChr8UJe+Ummc=",
                    }
                ),
            },
            {
                "ranges": [(449000, None)],
                "node": Seed.from_dict(
                    {
                        "host": "seedno.hashyada.com",
                        "port": 8002,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQCS++mJ1UNC1qywcYFr46l6rOadA0TYGchrA4RSWbsFqQIgM+VqpSkFdvsML5XHHtYFG5oXbQbjdQgXWQIHPuhfFHg=",
                            "public_key": "03637f6c620bac37adb03106a47682ac0c787cf6b46b5b6670f05989a6983bb1ea",
                        },
                        "seed_gateway": "MEUCIQC4unLqHmurNumWFIqyTwNJFTOttVhfIyMWxfpqDlxh2AIgHpK8UOO8geA916203XcjIb8cpbeKKjT1nKHH6f1a+ds=",
                    }
                ),
            },
            {
                "ranges": [(452000, None)],
                "node": Seed.from_dict(
                    {
                        "host": "seed.friendspool.club",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQDPBUWV9XpFBLkrwbWalS/NrVST87JTYwWBjiPlSZD/BwIgYdGYC/Kuy4C3CYNzUpQFg/oRC+oPvsMERyYURGN0G8I=",
                            "public_key": "034f740341e3e5d317e0284fd7420352a8f4af15e2d754f0f852c956ecd66c66c4",
                        },
                        "seed_gateway": "MEUCIQCWPClBEn7FVXuICcLTLxgxAINccOVsjrpHftPcATFLnQIgCUYxh+SFiJhXnd0vGpjxxJq9rQGm2P7dGmqyG3VehTw=",
                    }
                ),
            },
            {
                "ranges": [(467200, None)],
                "node": Seed.from_dict(
                    {
                        "host": "seed.berkinyada.xyz",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQDNbo0Mnw7IGt8Agm6tff+3GN+pFdi/5yn0kLqfV1FSSwIgcsURlw/G2oAgQd01lKQUzrDiotIVKUMyLfjicq8syyo=",
                            "public_key": "02eaa032e5cbb32b24541831a86b1df941fa351957fa27b309af0b52c77b21dab3",
                        },
                        "seed_gateway": "MEUCIQCeSYhmcosLZxrYrya2r7eyY78gQrTn6B83wjlA0ZIpjAIgec2OmwpFf5B3sLBRlAJdkzrGyioV9CSwu55xcuWtdnQ=",
                    }
                ),
            },
            {
                "ranges": [(467700, 472000)],
                "node": Seed.from_dict(
                    {
                        "host": "seed.funckyman.xyz",
                        "port": 8003,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCIDRvZf+3x9puA9kX7lj9va5CkJSxoAJXmXAMsT1ZsMFmAiANPPdJ4icpmQTzJ3QYHdM2OupQaWl03zyiESEgH/nzfQ==",
                            "public_key": "02e0b80642b8c7b3a74e4b38d9e69d4a1bea8e43bed131bbc6d05a3ac05b8eb8ad",
                        },
                        "seed_gateway": "MEQCIGT3g6nJQjXIeYQ7PG7Nt79LPWcgGWHhjYJ3icjVzpGrAiBU8c4tgRsye0frdkckNpKyk3dw6yNuYAHRQtso8dtzEg==",
                    }
                ),
            },
            {
                "ranges": [(472000, None)],  # UPDATED IDENTITY INFORMATION
                "node": Seed.from_dict(
                    {
                        "host": "seed.funckyman.xyz",
                        "port": 8003,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQDJVkQIx3zuLyqy5ntlisTQn4tNwLd651TieH2f5OGjjAIgAX9rG3+wW1W5YI+3qMlZiay2HrfQVMMZKQa07mJmZ3k=",
                            "public_key": "03557f082c201a7629f7afd5463e7df30e7feee62dd29a7cf46e559befacbc3a39",
                        },
                        "seed_gateway": "MEQCIEMcoEkJ1k7VzipqLLFlT7RiPsM4UAgPD7IFbf+pFkz1AiAPcV1ZftxnH9MotGe0VcS9TDc0vIjhmrAtHbho7FnZ1Q==",
                    }
                ),
            },
            {
                "ranges": [(477000, None)],
                "node": Seed.from_dict(
                    {
                        "host": "yadaseed1.hashrank.top",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQD91w1mGUZD/+E4KH08LiTXkJ69cgkPnBPBWXL0DZP5nQIgLD55ep9dKQUvXjznaNJ0/t5ARSy2sChqSveKRqOmnlI=",
                            "public_key": "02e21f8edf6cb09d28e96e561c6fab47f3e34041a8b636154f750be04874078f49",
                        },
                        "seed_gateway": "MEQCICH8oRaWHoZTXvkx3f2g5WCEonod0nhdzyRWJBOw8ldOAiB+6YjjDVfHmceHyg3F6ZQqpH1J4gqEpwu/ass2ul5/8g==",
                    }
                ),
            },
            {
                "ranges": [(479700, None)],
                "node": Seed.from_dict(
                    {
                        "host": "seed.supahash.com",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCIE6I6sfqh69hy6VoPKY4kCNfYflcnW3vkOgCH9S3GFR6AiAGf+pDYzpuSywaAaoW6c6q0Rq07Kx+oFQndhPf4MRzDQ==",
                            "public_key": "0281d4b412373d5330620e78159744cd821f2414d6e1fc300364bd36eb062ee411",
                        },
                        "seed_gateway": "MEUCIQCNas40A04R/y2YrC6e22dU/qYDrgCmrmuGQlbstgTmdwIgbh7dVw6KmU+ee6RRgOc2Vx81G8cLsCUOZdKHa6OBa3s=",
                    }
                ),
            },
            {
                "ranges": [(480100, None)],
                "node": Seed.from_dict(
                    {
                        "host": "seed.nephotim.co",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCICV3BfyeG/d3wthW5L9nWYZYejExBHAhJVlzW5iiTjs8AiAQNq0HnPNAm91ymsKu740lgfWwYcUs8gJHuiS9tz5fAA==",
                            "public_key": "0286fe6085cca02c0ec38b3e628b4d3392c7ee7f052b710519916d33bae3de69da",
                        },
                        "seed_gateway": "MEQCICHeWBWcuQu7LsziPqX7xQI8svUskEidCJVbUYRxp+D2AiA3P9o19J6Ke6KIY+RGNFE3WPziHYBHwgB6xvyWLZ5BQg==",
                    }
                ),
            },
            {
                "ranges": [(505600, None)],
                "node": Seed.from_dict(
                    {
                        "host": "seed.rogue-miner.com",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQD0MsT34TkNpYL5kOhLA/4E4YY+SzFhHtIPWPzHCShVGwIgYlzAQeujWvesmU6ZWrTMRwtLFFtjePZjLJDJjTMEQlc=",
                            "public_key": "03c815e3160b72c0fdd98f5b9fcca5a5ead09163272bc01e4be6397d1d3dbda9b3",
                        },
                        "seed_gateway": "MEUCIQC/PWvXpjny1yDGDPRtBzl6g7Lb9lcUuI0v0Kf6wxYi4AIgeRb5PtNhO2Eks6iiPEBuebKuXSeTM9euU9sWqOZYUec=",
                    }
                ),
            },
            {
                "ranges": [(522000, None)],
                "node": Seed.from_dict(
                    {
                        "host": "seed.yadaid.au",
                        "port": 8001,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCIDutdOZzlHtNCuALhNI6U9f91lDixf4l4owUqb0WPILCAiBbaHqiuTf4buogQ+67k7FztznKISufCgBZx6muhLTK0g==",
                            "public_key": "021dd60d6cf94a8964274d0a4ed95398e588f9b05a8df2c69f7538159910638a57",
                        },
                        "seed_gateway": "MEUCIQDDPFg2GcvhNy3aB+6/rprlhaiexnemo2bg7ovDjQUtrQIgSkhwJGQVe2+f83W7PzOIZWo9k5CbtI6BIcs5zqnQ7eo=",
                    }
                ),
            },
        ]

        Seeds.set_fork_points()
        Seeds.set_nodes()


class SeedGateways(Nodes):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SeedGateways, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return
        self.initialized = True
        self._NODES = [
            {
                "ranges": [(0, None)],
                "node": SeedGateway.from_dict(
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
            },
            {
                "ranges": [(0, None)],
                "node": SeedGateway.from_dict(
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
            },
            {
                "ranges": [(0, None)],
                "node": SeedGateway.from_dict(
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
            },
            {
                "ranges": [(443600, None)],
                "node": SeedGateway.from_dict(
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
            },
            {
                "ranges": [(443700, None)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "yada-bravo.mynodes.live",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCIFvpbWRQU9Ty4JXxoGH4YXgR8RiLoLBm11RNKBVeaz4GAiAyGMbhXc+J+z5VIh2GGJi9uDsqdPpEweerViSrxpxzPQ==",
                            "public_key": "03e235fcbe254c4cf4ff569f3c151083513aea0d0d226ae9d869811bfa375eacb9",
                        },
                        "seed": "MEQCICCXzIpmoNdU2sZsI35lqIl1bt5W1MW49NhjO95S2wlSAiAY04erBPVYvLWJ1SJCm5FtgJ3hyikVH3sw/fGlNUYuGQ==",
                    }
                ),
            },
            {
                "ranges": [(446400, None)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "seedgateway.yada.toksyk.pl",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCIAvo5gGrW6Uod4L6Qo5bekaKpursERu0UII1VTCR1i8zAiAW4UeZD/GKevh3/lSezWaFHZ4+oBq5wTCggEpvCljhUA==",
                            "public_key": "034254d690ad21ca307886c3cf5d6a37cca77520408fbc831921967f84468442cf",
                        },
                        "seed": "MEUCIQCOONwPlGftYSOGfzCnRGT0y5DH401G6I8nDNwbsYemfQIgBP7XketGtzfsocIR82xjyMYt06j3VY59yO6w6SXwMjk=",
                    }
                ),
            },
            {
                "ranges": [(449000, None)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "seedgateway.darksidetx.net",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQDFjb4L3Pv0GaBqdzB0WazxMjUQ8cNG7FBY/v/n9yUgIwIgA+FFy88yMIWqM6fyIeariS4EpyZj33JChr8UJe+Ummc=",
                            "public_key": "03e1ab14af772224ba6cca0a8be1a8471c3deffd0745b7a911634320b30416d910",
                        },
                        "seed": "MEUCIQDArjnhho8q8tCxHLmgvuDDS4qdSgQx1y7aNEGYHi/4ywIgWG/aboG4krfQQ4MS5MaPkedsc1syIbz+jfAGsg/siG4=",
                    }
                ),
            },
            {
                "ranges": [(449000, None)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "seedgatewayno.hashyada.com",
                        "port": 8004,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQC4unLqHmurNumWFIqyTwNJFTOttVhfIyMWxfpqDlxh2AIgHpK8UOO8geA916203XcjIb8cpbeKKjT1nKHH6f1a+ds=",
                            "public_key": "030efaa3bf8b3d2833aa2f30434dfde2fc89f39a12985f8c0e037f3a351f861e71",
                        },
                        "seed": "MEUCIQCS++mJ1UNC1qywcYFr46l6rOadA0TYGchrA4RSWbsFqQIgM+VqpSkFdvsML5XHHtYFG5oXbQbjdQgXWQIHPuhfFHg=",
                    }
                ),
            },
            {
                "ranges": [(452000, None)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "seedgateway.friendspool.club",
                        "port": 8010,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQCWPClBEn7FVXuICcLTLxgxAINccOVsjrpHftPcATFLnQIgCUYxh+SFiJhXnd0vGpjxxJq9rQGm2P7dGmqyG3VehTw=",
                            "public_key": "02ca31aaee2f8cda90080cbc3732f7b107cb254adee6d2efce142a59e76cd86b38",
                        },
                        "seed": "MEUCIQDPBUWV9XpFBLkrwbWalS/NrVST87JTYwWBjiPlSZD/BwIgYdGYC/Kuy4C3CYNzUpQFg/oRC+oPvsMERyYURGN0G8I=",
                    }
                ),
            },
            {
                "ranges": [(467200, None)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "seedgat.berkinyada.xyz",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQCeSYhmcosLZxrYrya2r7eyY78gQrTn6B83wjlA0ZIpjAIgec2OmwpFf5B3sLBRlAJdkzrGyioV9CSwu55xcuWtdnQ=",
                            "public_key": "029f5d639031ecb391c1858ef9a557b11861a1a6e44c0254db857280b42b2a0d98",
                        },
                        "seed": "MEUCIQDNbo0Mnw7IGt8Agm6tff+3GN+pFdi/5yn0kLqfV1FSSwIgcsURlw/G2oAgQd01lKQUzrDiotIVKUMyLfjicq8syyo=",
                    }
                ),
            },
            {
                "ranges": [(467700, 472000)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "seedgateway.funckyman.xyz",
                        "port": 8005,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCIGT3g6nJQjXIeYQ7PG7Nt79LPWcgGWHhjYJ3icjVzpGrAiBU8c4tgRsye0frdkckNpKyk3dw6yNuYAHRQtso8dtzEg==",
                            "public_key": "025a3c3f7a43f9bea789d227612b8367217117175c7864bcf62d5b228571c70414",
                        },
                        "seed": "MEQCIDRvZf+3x9puA9kX7lj9va5CkJSxoAJXmXAMsT1ZsMFmAiANPPdJ4icpmQTzJ3QYHdM2OupQaWl03zyiESEgH/nzfQ==",
                    }
                ),
            },
            {
                "ranges": [(472000, None)],  # UPDATED IDENTITY INFORMATION
                "node": SeedGateway.from_dict(
                    {
                        "host": "seedgateway.funckyman.xyz",
                        "port": 8005,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCIEMcoEkJ1k7VzipqLLFlT7RiPsM4UAgPD7IFbf+pFkz1AiAPcV1ZftxnH9MotGe0VcS9TDc0vIjhmrAtHbho7FnZ1Q==",
                            "public_key": "02aba3f23ed5abcfd56456781e505b14a12cc836136d5392b4705bbe38ddf591ad",
                        },
                        "seed": "MEUCIQDJVkQIx3zuLyqy5ntlisTQn4tNwLd651TieH2f5OGjjAIgAX9rG3+wW1W5YI+3qMlZiay2HrfQVMMZKQa07mJmZ3k=",
                    }
                ),
            },
            {
                "ranges": [(477000, None)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "yadaseed2.hashrank.top",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCICH8oRaWHoZTXvkx3f2g5WCEonod0nhdzyRWJBOw8ldOAiB+6YjjDVfHmceHyg3F6ZQqpH1J4gqEpwu/ass2ul5/8g==",
                            "public_key": "03fb0d840b77ede1c26638fb5f60dd02e84cf06f9083b895605bd899b900b31880",
                        },
                        "seed": "MEUCIQD91w1mGUZD/+E4KH08LiTXkJ69cgkPnBPBWXL0DZP5nQIgLD55ep9dKQUvXjznaNJ0/t5ARSy2sChqSveKRqOmnlI=",
                    }
                ),
            },
            {
                "ranges": [(479700, None)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "seedgateway.supahash.com",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQCNas40A04R/y2YrC6e22dU/qYDrgCmrmuGQlbstgTmdwIgbh7dVw6KmU+ee6RRgOc2Vx81G8cLsCUOZdKHa6OBa3s=",
                            "public_key": "023e19a600c2a88e150fd903c12c2386831ddebca2ba51473ecb6a0fae7916f657",
                        },
                        "seed": "MEQCIE6I6sfqh69hy6VoPKY4kCNfYflcnW3vkOgCH9S3GFR6AiAGf+pDYzpuSywaAaoW6c6q0Rq07Kx+oFQndhPf4MRzDQ==",
                    }
                ),
            },
            {
                "ranges": [(480100, None)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "gateway.nephotim.co",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCICHeWBWcuQu7LsziPqX7xQI8svUskEidCJVbUYRxp+D2AiA3P9o19J6Ke6KIY+RGNFE3WPziHYBHwgB6xvyWLZ5BQg==",
                            "public_key": "0393110452c520d98ebf69bfadf8db36719c3de1b42ef31f31e81523fb87d7b8db",
                        },
                        "seed": "MEQCICV3BfyeG/d3wthW5L9nWYZYejExBHAhJVlzW5iiTjs8AiAQNq0HnPNAm91ymsKu740lgfWwYcUs8gJHuiS9tz5fAA==",
                    }
                ),
            },
            {
                "ranges": [(505600, None)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "seedgateway.rogue-miner.com",
                        "port": 8002,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQC/PWvXpjny1yDGDPRtBzl6g7Lb9lcUuI0v0Kf6wxYi4AIgeRb5PtNhO2Eks6iiPEBuebKuXSeTM9euU9sWqOZYUec=",
                            "public_key": "020ce4988acc611e651d539cc2064ec12e04f22b0f95f54cbdfb223174c0d6ee7f",
                        },
                        "seed": "MEUCIQD0MsT34TkNpYL5kOhLA/4E4YY+SzFhHtIPWPzHCShVGwIgYlzAQeujWvesmU6ZWrTMRwtLFFtjePZjLJDJjTMEQlc=",
                    }
                ),
            },
            {
                "ranges": [(522000, None)],
                "node": SeedGateway.from_dict(
                    {
                        "host": "seedgateway.yadaid.au",
                        "port": 8001,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQDDPFg2GcvhNy3aB+6/rprlhaiexnemo2bg7ovDjQUtrQIgSkhwJGQVe2+f83W7PzOIZWo9k5CbtI6BIcs5zqnQ7eo=",
                            "public_key": "0327fde5ba4541a19376cd8af41cb22f4aeac39df1e1dfab7b054ceefb2f77c7d6",
                        },
                        "seed": "MEQCIDutdOZzlHtNCuALhNI6U9f91lDixf4l4owUqb0WPILCAiBbaHqiuTf4buogQ+67k7FztznKISufCgBZx6muhLTK0g==",
                    }
                ),
            },
        ]

        SeedGateways.set_fork_points()
        SeedGateways.set_nodes()


class ServiceProviders(Nodes):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ServiceProviders, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "initialized"):
            return
        self.initialized = True
        self._NODES = [
            {
                "ranges": [(0, None)],
                "node": ServiceProvider.from_dict(
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
            },
            {
                "ranges": [(0, None)],
                "node": ServiceProvider.from_dict(
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
            },
            {
                "ranges": [(0, None)],
                "node": ServiceProvider.from_dict(
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
            },
            {
                "ranges": [(443600, None)],
                "node": ServiceProvider.from_dict(
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
            },
            {
                "ranges": [(443700, None)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "yada-charlie.mynodes.live",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCIG5VITo79hYorFepmBB6zRqSl/PSbRPpz5gTaSteJQlaAiAmuQnTZFCuccjTtufWJ8CI+w/ddka/AoNQgat3H+18Jw==",
                            "public_key": "02247e2c03792a20c6a22da086641aae3bced66c9d6a98212c77622ba9bc5476ff",
                        },
                        "seed_gateway": "MEQCIFvpbWRQU9Ty4JXxoGH4YXgR8RiLoLBm11RNKBVeaz4GAiAyGMbhXc+J+z5VIh2GGJi9uDsqdPpEweerViSrxpxzPQ==",
                        "seed": "MEQCICCXzIpmoNdU2sZsI35lqIl1bt5W1MW49NhjO95S2wlSAiAY04erBPVYvLWJ1SJCm5FtgJ3hyikVH3sw/fGlNUYuGQ==",
                    }
                ),
            },
            {
                "ranges": [(446400, None)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "serviceprovider.yada.toksyk.pl",
                        "port": 8080,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCIEH/G/iTuiJSdcC0Q3tZ+HepDYetUf5kN2s195pT8SjnAiArhoo4Dm6PbNYIPNDlbuOLzcBiO/A7ONYmviBYDCTW9Q==",
                            "public_key": "0308531862af7ce061fa1742cba9c25d142b2535cd7cb104281196b764e79b3d4f",
                        },
                        "seed_gateway": "MEQCIAvo5gGrW6Uod4L6Qo5bekaKpursERu0UII1VTCR1i8zAiAW4UeZD/GKevh3/lSezWaFHZ4+oBq5wTCggEpvCljhUA==",
                        "seed": "MEUCIQCOONwPlGftYSOGfzCnRGT0y5DH401G6I8nDNwbsYemfQIgBP7XketGtzfsocIR82xjyMYt06j3VY59yO6w6SXwMjk=",
                    }
                ),
            },
            {
                "ranges": [(449000, None)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "serviceprovider.darksidetx.net",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCICD0iFCEux94iEwHKMBQxxV665VW/ozsr9rSfktt+BRSAiB0FvEvODTVufiBKiARKOq2zSyFKIckjvGtRi52ow45Ig==",
                            "public_key": "0276534e0133e6ee3b1267d4ad9046d23db89dbe2b4e1ba5d18382791cf7f63a93",
                        },
                        "seed_gateway": "MEUCIQDFjb4L3Pv0GaBqdzB0WazxMjUQ8cNG7FBY/v/n9yUgIwIgA+FFy88yMIWqM6fyIeariS4EpyZj33JChr8UJe+Ummc=",
                        "seed": "MEUCIQDArjnhho8q8tCxHLmgvuDDS4qdSgQx1y7aNEGYHi/4ywIgWG/aboG4krfQQ4MS5MaPkedsc1syIbz+jfAGsg/siG4=",
                    }
                ),
            },
            {
                "ranges": [(449000, None)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "serviceproviderno.hashyada.com",
                        "port": 8006,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCIF1qj/XOXWT8a77NLiqcz/x5mHLa19YSwk/BSY6qb3EkAiBQjo6fHUkuSWQqwp5sZUdaou9a8hMGhqpmcuP9oKbAkw==",
                            "public_key": "0299c1cfe9f2490f14836032f772391b3c53fb2df513f3c502790a650ec17dc105",
                        },
                        "seed_gateway": "MEUCIQC4unLqHmurNumWFIqyTwNJFTOttVhfIyMWxfpqDlxh2AIgHpK8UOO8geA916203XcjIb8cpbeKKjT1nKHH6f1a+ds=",
                        "seed": "MEUCIQCS++mJ1UNC1qywcYFr46l6rOadA0TYGchrA4RSWbsFqQIgM+VqpSkFdvsML5XHHtYFG5oXbQbjdQgXWQIHPuhfFHg=",
                    }
                ),
            },
            {
                "ranges": [(452000, None)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "serviceprovider.friendspool.club",
                        "port": 8011,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQDO6Nj9pcRZCo6TtOf9ayy17h0PfyKmgxVHSH81EtdITgIgM9TrMrfomG9AnIj697tbmDW4LZOz8+ao48iApGHfdXk=",
                            "public_key": "0388318e5a7cbfc2a0a7501d0ebad6495f17d09fb068f295efad23b90bfd572eb4",
                        },
                        "seed_gateway": "MEUCIQCWPClBEn7FVXuICcLTLxgxAINccOVsjrpHftPcATFLnQIgCUYxh+SFiJhXnd0vGpjxxJq9rQGm2P7dGmqyG3VehTw=",
                        "seed": "MEUCIQDPBUWV9XpFBLkrwbWalS/NrVST87JTYwWBjiPlSZD/BwIgYdGYC/Kuy4C3CYNzUpQFg/oRC+oPvsMERyYURGN0G8I=",
                    }
                ),
            },
            {
                "ranges": [(467200, None)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "servic.berkinyada.xyz",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQDbkNuFjpMi8YcMKFHOjpWtlpM5Ul+lnskdIiwSFRcNmAIgMbTCmXBYL/vNxxlnzoWvscAuv0jQ0J9U8biL812+O+U=",
                            "public_key": "03685f915435a2dbd185b3998902f59915a24ef339c35792313afc4d712acc4bd5",
                        },
                        "seed_gateway": "MEUCIQCeSYhmcosLZxrYrya2r7eyY78gQrTn6B83wjlA0ZIpjAIgec2OmwpFf5B3sLBRlAJdkzrGyioV9CSwu55xcuWtdnQ=",
                        "seed": "MEUCIQDNbo0Mnw7IGt8Agm6tff+3GN+pFdi/5yn0kLqfV1FSSwIgcsURlw/G2oAgQd01lKQUzrDiotIVKUMyLfjicq8syyo=",
                    }
                ),
            },
            {
                "ranges": [(467700, 472000)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "serviceprovider.funckyman.xyz",
                        "port": 8007,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQCJpJ8EYXEB9dgeVOTjiycxsVf8y/3yulsO1BtlryGlxAIgJzou0GBjJJZDgcym8dvr6eOPIZ8HZFXQdRzInE1eAV4=",
                            "public_key": "0398796055a38c4ca375f8dec793101e520c5035a0407b856b597a57d38147aa09",
                        },
                        "seed_gateway": "MEQCIGT3g6nJQjXIeYQ7PG7Nt79LPWcgGWHhjYJ3icjVzpGrAiBU8c4tgRsye0frdkckNpKyk3dw6yNuYAHRQtso8dtzEg==",
                        "seed": "MEQCIDRvZf+3x9puA9kX7lj9va5CkJSxoAJXmXAMsT1ZsMFmAiANPPdJ4icpmQTzJ3QYHdM2OupQaWl03zyiESEgH/nzfQ==",
                    }
                ),
            },
            {
                "ranges": [(472000, None)],  # UPDATED IDENTITY INFORMATION
                "node": ServiceProvider.from_dict(
                    {
                        "host": "serviceprovider.funckyman.xyz",
                        "port": 8007,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQDSI+CA17XkAYWlCQsKRkXwWlBoz5hddxCT+/ECTTJW5AIgUvim2ZqBqtAfRRYdM2FmWIXOI/KyqH7Bgxwh09x8ads=",
                            "public_key": "02eda40d55a2bc1019e319bd360af79e9798c64575e010a20b8a74e3e2b825aeb3",
                        },
                        "seed_gateway": "MEQCIEMcoEkJ1k7VzipqLLFlT7RiPsM4UAgPD7IFbf+pFkz1AiAPcV1ZftxnH9MotGe0VcS9TDc0vIjhmrAtHbho7FnZ1Q==",
                        "seed": "MEUCIQDJVkQIx3zuLyqy5ntlisTQn4tNwLd651TieH2f5OGjjAIgAX9rG3+wW1W5YI+3qMlZiay2HrfQVMMZKQa07mJmZ3k=",
                    }
                ),
            },
            {
                "ranges": [(477000, None)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "yadaseed3.hashrank.top",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQDIxOMoBkry0+BkJrUm2YBS9jrXkOtnOQwaGFLBkm3fvgIgUrHT6IV7isnIBFeJCzoi6jr4NbvMJU5w4APnNAIHNaI=",
                            "public_key": "0273b3c11252c0b997c3936b2a3cc46f1c3245e24e8b2efff8cda8320e07b33cfb",
                        },
                        "seed_gateway": "MEQCICH8oRaWHoZTXvkx3f2g5WCEonod0nhdzyRWJBOw8ldOAiB+6YjjDVfHmceHyg3F6ZQqpH1J4gqEpwu/ass2ul5/8g==",
                        "seed": "MEUCIQD91w1mGUZD/+E4KH08LiTXkJ69cgkPnBPBWXL0DZP5nQIgLD55ep9dKQUvXjznaNJ0/t5ARSy2sChqSveKRqOmnlI=",
                    }
                ),
            },
            {
                "ranges": [(479700, None)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "serviceprovider.supahash.com",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQCi7PkxJrgR7T2PDK5BCxT8DJ/oLhoa/zpuPbqb0EqapwIgM4NXxuAZn4nh+cncIgb/VkJLeQAQnqj+sNj39oRWvn8=",
                            "public_key": "03853af02ad22e2a76fb0cf6e3f5ae5d173eb1ba2cdd2b140df266690d8063ebcf",
                        },
                        "seed_gateway": "MEUCIQCNas40A04R/y2YrC6e22dU/qYDrgCmrmuGQlbstgTmdwIgbh7dVw6KmU+ee6RRgOc2Vx81G8cLsCUOZdKHa6OBa3s=",
                        "seed": "MEQCIE6I6sfqh69hy6VoPKY4kCNfYflcnW3vkOgCH9S3GFR6AiAGf+pDYzpuSywaAaoW6c6q0Rq07Kx+oFQndhPf4MRzDQ==",
                    }
                ),
            },
            {
                "ranges": [(480100, None)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "serviceprovider.nephotim.co",
                        "port": 8000,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCIDLZN6Q5WLperdJbHu1mNyZsXmk7fqA6l7tXlthkArglAiAfapsk3v4s8cTLZf22R62ht2SocD2+jSX2HNc4C05SMA==",
                            "public_key": "021aab430ef88f35eaeb183dcf6f82128d7ad02b628b6e705c90d5708fc66f4c33",
                        },
                        "seed_gateway": "MEQCICHeWBWcuQu7LsziPqX7xQI8svUskEidCJVbUYRxp+D2AiA3P9o19J6Ke6KIY+RGNFE3WPziHYBHwgB6xvyWLZ5BQg==",
                        "seed": "MEQCICV3BfyeG/d3wthW5L9nWYZYejExBHAhJVlzW5iiTjs8AiAQNq0HnPNAm91ymsKu740lgfWwYcUs8gJHuiS9tz5fAA==",
                    }
                ),
            },
            {
                "ranges": [(505600, None)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "serviceprovider.rogue-miner.com",
                        "port": 8003,
                        "identity": {
                            "username": "",
                            "username_signature": "MEUCIQDgXK4dHUpOAiqfaItWyweWijHRGez+k071wEvqSKm9rgIgZA7MJEjvHSN1FDrnMVsSKx2j74q4gaUiYcs+WYW261M=",
                            "public_key": "024321b0dc01c7d200e2d2f5b4f0a15883fb3dc91f7ff1df36daa7a195defcd171",
                        },
                        "seed_gateway": "MEUCIQC/PWvXpjny1yDGDPRtBzl6g7Lb9lcUuI0v0Kf6wxYi4AIgeRb5PtNhO2Eks6iiPEBuebKuXSeTM9euU9sWqOZYUec=",
                        "seed": "MEUCIQD0MsT34TkNpYL5kOhLA/4E4YY+SzFhHtIPWPzHCShVGwIgYlzAQeujWvesmU6ZWrTMRwtLFFtjePZjLJDJjTMEQlc==",
                    }
                ),
            },
            {
                "ranges": [(522000, None)],
                "node": ServiceProvider.from_dict(
                    {
                        "host": "serviceprovider.yadaid.au",
                        "port": 8001,
                        "identity": {
                            "username": "",
                            "username_signature": "MEQCICmKX5wUJGm/rGe1tnoL1I3eA2V5jFaJk0WUQe7cHIABAiBi+BnM3emLl4nQp+alleXYWm3KLmqaXRP9zp+yfm9E1w==",
                            "public_key": "03b7e27e592af0b385c71b791910d172bddf9659e71aae0a39572f223bb7c26856",
                        },
                        "seed_gateway": "MEUCIQDDPFg2GcvhNy3aB+6/rprlhaiexnemo2bg7ovDjQUtrQIgSkhwJGQVe2+f83W7PzOIZWo9k5CbtI6BIcs5zqnQ7eo=",
                        "seed": "MEQCIDutdOZzlHtNCuALhNI6U9f91lDixf4l4owUqb0WPILCAiBbaHqiuTf4buogQ+67k7FztznKISufCgBZx6muhLTK0g==",
                    }
                ),
            },
        ]
        ServiceProviders.set_fork_points()
        ServiceProviders.set_nodes()
