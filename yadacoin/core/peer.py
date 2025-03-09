"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import hashlib
import json
import time
from collections import OrderedDict
from logging import getLogger

import tornado.ioloop

from yadacoin.core.config import Config
from yadacoin.core.identity import Identity
from yadacoin.core.transaction import Transaction
from yadacoin.enums.peertypes import PEER_TYPES


class Peer:
    id_attribute = "rid"
    """An individual Peer object"""
    epoch = 1602914018
    ttl = 259200

    def __init__(
        self,
        host=None,
        port=None,
        identity=None,
        seed=None,
        seed_gateway=None,
        http_host=None,
        http_port=None,
        http_protocol=None,
        secure=None,
        protocol_version=4,
        node_version=(0, 0, 0),
        peer_type=None,
    ):
        self.host = host
        self.port = port
        self.identity = identity
        self.seed = seed
        self.seed_gateway = seed_gateway
        self.http_host = http_host
        self.http_port = http_port
        self.http_protocol = http_protocol
        self.secure = secure
        self.config = Config()
        self.app_log = getLogger("tornado.application")
        self.protocol_version = protocol_version
        self.authenticated = False
        self.node_version = tuple([int(x) for x in node_version])
        self.peer_type = peer_type

    @staticmethod
    def my_peer():
        config = Config()
        my_peer = {
            "host": config.peer_host,
            "port": config.peer_port,
            "identity": {
                "username": config.username,
                "username_signature": config.username_signature,
                "public_key": config.public_key,
            },
            "peer_type": config.peer_type,
            "http_host": config.ssl.common_name or config.peer_host,
            "http_port": config.ssl.port or config.serve_port,
            "secure": config.ssl.is_valid(),
            "protocol_version": 4,
            "node_version": config.node_version,
        }
        if config.peer_type == PEER_TYPES.SEED.value:
            if config.username_signature not in config.seeds:
                config.peer_type = PEER_TYPES.USER.value
                my_peer.update({"peer_type": PEER_TYPES.USER.value})
                return User.from_dict(my_peer, is_me=True)
            my_peer[PEER_TYPES.SEED_GATEWAY.value] = config.seeds[
                config.username_signature
            ].seed_gateway
            return Seed.from_dict(my_peer, is_me=True)
        elif config.peer_type == PEER_TYPES.SEED_GATEWAY.value:
            if config.username_signature not in config.seed_gateways:
                config.peer_type = PEER_TYPES.USER.value
                my_peer.update({"peer_type": PEER_TYPES.USER.value})
                return User.from_dict(my_peer, is_me=True)
            my_peer[PEER_TYPES.SEED.value] = config.seed_gateways[
                config.username_signature
            ].seed
            return SeedGateway.from_dict(my_peer, is_me=True)
        elif config.peer_type == PEER_TYPES.SERVICE_PROVIDER.value:
            if config.username_signature not in config.service_providers:
                config.peer_type = PEER_TYPES.USER.value
                my_peer.update({"peer_type": PEER_TYPES.USER.value})
                return User.from_dict(my_peer, is_me=True)
            my_peer[PEER_TYPES.SEED_GATEWAY.value] = config.service_providers[
                config.username_signature
            ].seed_gateway
            my_peer[PEER_TYPES.SEED.value] = config.service_providers[
                config.username_signature
            ].seed
            return ServiceProvider.from_dict(my_peer, is_me=True)
        elif config.peer_type == PEER_TYPES.POOL.value or config.pool_payout == True:
            config.peer_type = (
                PEER_TYPES.POOL.value
            )  # in case peer_type is 'user' and pool_payout is enabled
            my_peer.update({"peer_type": PEER_TYPES.POOL.value})
            return Pool.from_dict(my_peer, is_me=True)
        elif (
            config.peer_type == PEER_TYPES.USER.value or True
        ):  # default if not specified
            return User.from_dict(my_peer, is_me=True)

    @classmethod
    def from_dict(cls, peer, is_me=False):
        inst = cls(
            peer["host"],
            peer["port"],
            Identity.from_dict(peer["identity"]),
            seed=peer.get(PEER_TYPES.SEED.value),
            seed_gateway=peer.get(PEER_TYPES.SEED_GATEWAY.value),
            http_host=peer.get("http_host"),
            http_port=peer.get("http_port"),
            http_protocol=peer.get("http_protocol"),
            secure=peer.get("secure"),
            protocol_version=peer.get("protocol_version", 1),
            node_version=peer.get("node_version", (0, 0, 0)),
            peer_type=peer.get("peer_type"),
        )
        return inst

    @property
    def rid(self):
        config = Config()
        if hasattr(config, "peer"):
            return self.identity.generate_rid(config.peer.identity.username_signature)

    @classmethod
    def type_limit(cls, peer):
        raise NotImplementedError()

    async def get_outbound_class(self):
        raise NotImplementedError()

    async def get_inbound_class(self):
        raise NotImplementedError()

    async def get_outbound_peers(self):
        raise NotImplementedError()

    async def get_inbound_streams(self):
        raise NotImplementedError()

    async def get_outbound_streams(self):
        raise NotImplementedError()

    @staticmethod
    async def get_miner_streams():
        config = Config()
        miners = config.nodeServer.inbound_streams[Miner.__name__].values()
        return list([worker for miner in miners for worker in miner.values()])

    @staticmethod
    async def get_miner_pending():
        config = Config()
        miners = config.nodeServer.inbound_pending[Miner.__name__].values()
        return list([worker for miner in miners for worker in miner.values()])

    async def get_inbound_pending(self):
        raise NotImplementedError()

    async def get_outbound_pending(self):
        raise NotImplementedError()

    async def get_all_inbound_streams(self):
        return [x async for x in self.get_inbound_streams()] + [
            x async for x in self.get_inbound_pending()
        ]

    async def get_all_outbound_streams(self):
        return await self.get_outbound_streams() + await self.get_outbound_pending()

    async def get_all_streams(self):
        return (
            await self.get_inbound_streams()
            + await self.get_outbound_streams()
            + await self.get_inbound_pending()
            + await self.get_outbound_pending()
        )

    async def get_all_miner_streams(self):
        return await Peer.get_miner_streams() + await Peer.get_miner_pending()

    async def calculate_seed_gateway(self, nonce=None):
        if self.__class__ not in [Group, ServiceProvider]:
            raise Exception(
                "Should not calculate a seed gateway for anything other than groups or service providers"
            )
        username_signature_hash = hashlib.sha256(
            self.identity.username_signature.encode()
        ).hexdigest()
        # TODO: introduce some kind of unpredictability here. This uses the latest block hash.
        # So we won't be able to get the new seed without the block hash
        # which is not known in advance
        seed_time = int((time.time() - self.epoch) / self.ttl) + 1
        if not self.config.seed_gateways:
            return None
        seed_select = (int(username_signature_hash, 16) * seed_time) % len(
            self.config.seed_gateways
        )
        username_signatures = list(self.config.seed_gateways)
        first_number = seed_select
        num_reset = False
        while (
            self.config.seed_gateways[
                username_signatures[seed_select]
            ].identity.username_signature
            in self.config.nodeClient.outbound_ignore[SeedGateway.__name__]
        ):
            seed_select += 1
            if seed_select >= len(username_signatures):
                return None
            if num_reset and seed_select >= first_number:
                break  # failed to find a seed gateway
            if seed_select >= len(self.config.seed_gateways) + 1:
                if first_number > 0:
                    seed_select = 0

        seed_gateway = self.config.seed_gateways[
            list(self.config.seed_gateways)[seed_select]
        ]
        return seed_gateway

    async def ensure_peers_connected(self):
        peers = {
            self.config.peer.identity.generate_rid(x.identity.username_signature): x
            for x in (await self.get_outbound_peers()).values()
        }
        if not peers:
            return
        outbound_class = await self.get_outbound_class()
        limit = self.__class__.type_limit(outbound_class)

        stream_collection = {
            **self.config.nodeClient.outbound_streams[outbound_class.__name__],
            **self.config.nodeClient.outbound_pending[outbound_class.__name__],
            **self.config.nodeServer.inbound_streams[outbound_class.__name__],
            **self.config.nodeServer.inbound_pending[outbound_class.__name__],
        }
        outbound_ignored = {
            self.config.peer.identity.generate_rid(k): v
            for k, v in self.config.nodeClient.outbound_ignore[
                outbound_class.__name__
            ].items()
            if (time.time() - v) < 120
        }
        await self.connect(
            stream_collection,
            limit,
            peers,
            outbound_ignored,
        )

    async def connect(self, stream_collection, limit, peers, ignored_peers):
        if limit and len(stream_collection) < limit:
            for i, peer in enumerate(
                set(peers) - set(stream_collection) - set(ignored_peers)
            ):
                if i >= limit:
                    break
                tornado.ioloop.IOLoop.current().spawn_callback(
                    self.config.nodeClient.connect, peers[peer]
                )

    @staticmethod
    async def is_synced():
        streams = await Config().peer.get_outbound_streams()
        for stream in streams:
            if not stream.synced:
                return False
        return True

    def to_dict(self):
        return {
            "host": self.host,
            "port": self.port,
            "identity": self.identity.to_dict,
            "rid": self.rid,
            PEER_TYPES.SEED.value: self.seed,
            PEER_TYPES.SEED_GATEWAY.value: self.seed_gateway,
            "http_host": self.http_host,
            "http_port": self.http_port,
            "http_protocol": self.http_protocol,
            "secure": self.secure,
            "protocol_version": self.protocol_version,
            "node_version": self.node_version,
            "peer_type": self.peer_type,
        }

    def to_string(self):
        return "{}:{}".format(self.host, self.port)

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)

    async def get_payload_txn(self, payload):
        txn = None
        if payload.get("transaction"):
            txn = Transaction.from_dict(payload.get("transaction"))
        return txn


class Seed(Peer):
    id_attribute = "rid"
    source_property = "source_seed"

    async def get_outbound_class(self):
        return Seed

    async def get_inbound_class(self):
        return SeedGateway

    async def get_outbound_peers(self):
        if self.config.username_signature in self.config.seeds:
            del self.config.seeds[self.config.username_signature]
        return self.config.seeds

    async def get_inbound_peers(self):
        if self.config.username_signature in self.config.seeds:
            del self.config.seeds[self.config.username_signature]
        peers = {}
        peers.update(self.config.seeds)
        peers.update(
            {
                self.config.seed_gateways[
                    self.seed_gateway
                ].identity.username_signature: self.config.seed_gateways[
                    self.seed_gateway
                ]
            }
        )
        return peers

    @classmethod
    def type_limit(cls, peer):
        if peer == Seed:
            return Config().max_peers or 100000
        elif peer == SeedGateway:
            return 1
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [Seed, SeedGateway]

    async def get_route_peers(self, peer, payload):
        if isinstance(peer, SeedGateway):
            # this if statement allow bi-directional communication cross-seed
            if self.source_property in payload:
                # this is a response
                bridge_seed = self.config.seeds[payload[self.source_property]]
            else:
                # this must be the identity of the destination service provider
                # the message originator must provide the necissary service provider identity information
                # typically, the originator will grab all mutual service providers of the originator and the recipient of the message
                # and send "through" every service provider so the recipient will receive the message on all services

                peer = Peer.from_dict(payload.get("dest_service_provider"))
                bridge_seed_gateway = (
                    await peer.calculate_seed_gateway()
                )  # get the seed gateway
                bridge_seed = bridge_seed_gateway.seed
                payload[
                    self.source_property
                ] = self.config.peer.identity.username_signature
            if bridge_seed.rid in self.config.nodeServer.inbound_streams[Seed.__name__]:
                peer_stream = self.config.nodeServer.inbound_streams[Seed.__name__][
                    bridge_seed.rid
                ]
            elif (
                bridge_seed.rid
                in self.config.nodeClient.outbound_streams[Seed.__name__]
            ):
                peer_stream = self.config.nodeClient.outbound_streams[Seed.__name__][
                    bridge_seed.rid
                ]
            else:
                self.config.app_log.error(
                    "No bridge seed found. Cannot route transaction."
                )
            yield peer_stream
        elif isinstance(peer, Seed):
            for peer_stream in list(
                self.config.nodeServer.inbound_streams[SeedGateway.__name__].values()
            ):
                yield peer_stream

            for peer_stream in list(
                self.config.nodeClient.outbound_streams[Seed.__name__].values()
            ):
                yield peer_stream

    async def get_service_provider_request_peers(self, peer, payload):
        if isinstance(peer, SeedGateway):
            # this if statement allow bi-directional communication cross-seed
            if self.source_property in payload:
                # this is a response
                bridge_seed_from_payload = Peer.from_dict(payload[self.source_property])
                bridge_seed = self.config.seeds[
                    bridge_seed_from_payload.identity.username_signature
                ]
            else:
                # this must be the identity of the destination service provider
                # the message originator must provide the necissary service provider identity information
                # typically, the originator will grab all mutual service providers of the originator and the recipient of the message
                # and send "through" every service provider so the recipient will receive the message on all services

                bridge_seed_gateway = Peer.from_dict(
                    payload.get(PEER_TYPES.SEED_GATEWAY.value)
                )
                bridge_seed = self.config.seeds[
                    self.config.seed_gateways[
                        bridge_seed_gateway.identity.username_signature
                    ].seed
                ]
                payload[
                    self.source_property
                ] = self.config.peer.identity.username_signature
            if bridge_seed.rid in self.config.nodeServer.inbound_streams[Seed.__name__]:
                peer_stream = self.config.nodeServer.inbound_streams[Seed.__name__][
                    bridge_seed.rid
                ]
            elif (
                bridge_seed.rid
                in self.config.nodeClient.outbound_streams[Seed.__name__]
            ):
                peer_stream = self.config.nodeClient.outbound_streams[Seed.__name__][
                    bridge_seed.rid
                ]
            else:
                self.config.app_log.error(
                    "No bridge seed found. Cannot route transaction."
                )
            yield peer_stream
        elif isinstance(peer, Seed):
            for peer_stream in list(
                self.config.nodeServer.inbound_streams[SeedGateway.__name__].values()
            ):
                yield peer_stream

    async def get_sync_peers(self):
        for y in list(
            self.config.nodeServer.inbound_streams[SeedGateway.__name__].values()
        ):
            yield y

        for y in list(self.config.nodeServer.inbound_streams[Seed.__name__].values()):
            yield y

        for y in list(self.config.nodeClient.outbound_streams[Seed.__name__].values()):
            yield y

    async def get_peer_by_id(self, id_attr):
        if self.config.nodeServer.inbound_streams[SeedGateway.__name__].get(id_attr):
            return self.config.nodeServer.inbound_streams[SeedGateway.__name__].get(
                id_attr
            )

        if self.config.nodeServer.inbound_streams[Seed.__name__].get(id_attr):
            return self.config.nodeServer.inbound_streams[Seed.__name__].get(id_attr)

        if self.config.nodeClient.outbound_streams[Seed.__name__].get(id_attr):
            return self.config.nodeClient.outbound_streams[Seed.__name__].get(id_attr)

    def is_linked_peer(self, peer):
        if self.seed_gateway == peer.identity.username_signature:
            return True
        return False

    async def get_inbound_streams(self):
        for peer_stream in list(
            list(self.config.nodeServer.inbound_streams[Seed.__name__].values())
            + list(
                self.config.nodeServer.inbound_streams[SeedGateway.__name__].values()
            )
        ):
            yield peer_stream

    async def get_outbound_streams(self):
        return list(self.config.nodeClient.outbound_streams[Seed.__name__].values())

    async def get_inbound_pending(self):
        for peer_stream in list(
            list(self.config.nodeServer.inbound_pending[Seed.__name__].values())
            + list(
                self.config.nodeServer.inbound_pending[
                    ServiceProvider.__name__
                ].values()
            )
        ):
            yield peer_stream

    async def get_outbound_pending(self):
        return list(self.config.nodeClient.outbound_pending[Seed.__name__].values())


class SeedGateway(Peer):
    id_attribute = "rid"
    source_property = "source_seed_gateway"

    async def get_outbound_class(self):
        return Seed

    async def get_inbound_class(self):
        return ServiceProvider

    async def get_outbound_peers(self):
        return {
            self.config.seeds[self.seed].identity.username_signature: self.config.seeds[
                self.seed
            ]
        }

    async def get_inbound_peers(self):
        return {}

    async def get_inbound_streams(self):
        for peer_stream in list(
            self.config.nodeServer.inbound_streams[ServiceProvider.__name__].values()
        ):
            yield peer_stream

    async def get_outbound_streams(self):
        return list(self.config.nodeClient.outbound_streams[Seed.__name__].values())

    async def get_inbound_pending(self):
        for peer_stream in list(
            self.config.nodeServer.inbound_pending[ServiceProvider.__name__].values()
        ):
            yield peer_stream

    async def get_outbound_pending(self):
        return list(self.config.nodeClient.outbound_pending[Seed.__name__].values())

    @classmethod
    def type_limit(cls, peer):
        if peer == Seed:
            return 1
        elif peer == ServiceProvider:
            return Config().max_peers or 100000
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [Seed, ServiceProvider]

    async def get_route_peers(self, peer, payload):
        if isinstance(peer, Seed):
            for peer_stream in list(
                self.config.nodeServer.inbound_streams[
                    ServiceProvider.__name__
                ].values()
            ):
                yield peer_stream
        elif isinstance(peer, ServiceProvider):
            for peer_stream in list(
                self.config.nodeClient.outbound_streams[Seed.__name__].values()
            ):
                yield peer_stream

    async def get_service_provider_request_peers(self, peer, payload):
        if isinstance(peer, Seed):
            for peer_stream in list(
                self.config.nodeServer.inbound_streams[
                    ServiceProvider.__name__
                ].values()
            ):
                yield peer_stream

        elif isinstance(peer, ServiceProvider):
            for peer_stream in list(
                self.config.nodeClient.outbound_streams[Seed.__name__].values()
            ):
                yield peer_stream

    async def get_sync_peers(self):
        for y in list(
            self.config.nodeServer.inbound_streams[ServiceProvider.__name__].values()
        ):
            yield y

        for y in list(self.config.nodeClient.outbound_streams[Seed.__name__].values()):
            yield y

    async def get_peer_by_id(self, id_attr):
        if self.config.nodeServer.inbound_streams[ServiceProvider.__name__].get(
            id_attr
        ):
            return self.config.nodeServer.inbound_streams[ServiceProvider.__name__].get(
                id_attr
            )

        if self.config.nodeClient.outbound_streams[Seed.__name__].get(id_attr):
            return self.config.nodeClient.outbound_streams[Seed.__name__].get(id_attr)

    def is_linked_peer(self, peer):
        if self.seed == peer.identity.username_signature:
            return True
        return False


class ServiceProvider(Peer):
    id_attribute = "rid"
    source_property = "source_service_provider"

    async def get_outbound_class(self):
        return SeedGateway

    async def get_inbound_class(self):
        return User

    async def get_outbound_peers(self, nonce=None):
        if not self.seed_gateway:
            return self.config.seed_gateways
        return {
            self.config.seed_gateways[
                self.seed_gateway
            ].identity.username_signature: self.config.seed_gateways[self.seed_gateway]
        }

    async def get_inbound_streams(self):
        for peer_stream in list(
            self.config.nodeServer.inbound_streams[User.__name__].values()
        ):
            yield peer_stream

        for peer_stream in list(
            self.config.nodeServer.inbound_streams[Pool.__name__].values()
        ):
            yield peer_stream

    async def get_outbound_streams(self):
        return list(
            self.config.nodeClient.outbound_streams[SeedGateway.__name__].values()
        )

    async def get_inbound_pending(self):
        for peer_stream in list(
            self.config.nodeServer.inbound_pending[User.__name__].values()
        ):
            yield peer_stream

        for peer_stream in list(
            self.config.nodeServer.inbound_pending[Pool.__name__].values()
        ):
            yield peer_stream

    async def get_outbound_pending(self):
        return list(
            self.config.nodeClient.outbound_pending[SeedGateway.__name__].values()
        )

    @classmethod
    def type_limit(cls, peer):
        if peer == SeedGateway:
            return 1
        elif peer in [User, Pool]:
            return Config().max_peers or 100000
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [ServiceProvider, User, Pool]

    async def get_route_peers(self, peer, payload):
        if isinstance(peer, User):
            for peer_stream in list(
                self.config.nodeClient.outbound_streams[SeedGateway.__name__].values()
            ):
                yield peer_stream

            for peer_stream in list(
                self.config.websocketServer.inbound_streams.values()
            ):
                if (
                    peer.identity.username_signature
                    == peer_stream.peer.identity.username_signature
                ):
                    continue
                yield peer_stream

        elif isinstance(peer, SeedGateway):
            txn = self.get_payload_txn(payload)
            if txn:
                txn_sum = sum([x.value for x in txn.outputs])

                if not peer and not txn_sum:
                    self.config.app_log.error(
                        "Zero sum transaction and no routing information. Cannot route transaction."
                    )
                    return

                from_peer = None
                if payload.get("from_peer"):
                    from_peer = Identity.from_dict(payload.get("from_peer"))

                rid = None
                if (
                    txn.requester_rid
                    in self.config.nodeServer.inbound_streams[User.__name__]
                ):
                    rid = txn.requester_rid
                elif (
                    txn.requested_rid
                    in self.config.nodeServer.inbound_streams[User.__name__]
                ):
                    rid = txn.requested_rid
                elif (
                    from_peer
                    and from_peer
                    in self.config.nodeServer.inbound_streams[User.__name__]
                ):
                    rid = from_peer.rid
                else:
                    self.config.app_log.error(
                        "No user found. Cannot route transaction."
                    )

                if txn_sum:
                    self.config.mongo.async_db.miner_transactions.replace_one(
                        {"id": txn.transaction_signature}, txn.to_dict()
                    )
                    for peer_stream in list(
                        self.config.nodeServer.inbound_streams[User.__name__].values()
                    ):
                        yield peer_stream
                elif rid:
                    yield self.config.nodeServer.inbound_streams[User.__name__][rid]

    async def get_service_provider_request_peers(self, peer, payload):
        if isinstance(peer, User):
            for peer_stream in list(
                self.config.nodeClient.outbound_streams[SeedGateway.__name__].values()
            ):
                yield peer_stream

            for peer_stream in list(
                self.config.websocketServer.inbound_streams.values()
            ):
                if (
                    peer.identity.username_signature
                    == peer_stream.peer.identity.username_signature
                ):
                    continue
                yield peer_stream

        elif isinstance(peer, SeedGateway):
            for peer_stream in list(
                self.config.nodeServer.inbound_streams[User.__name__].values()
            ):
                yield peer_stream

            for peer_stream in list(
                self.config.websocketServer.inbound_streams[User.__name__].values()
            ):
                yield peer_stream

    async def get_sync_peers(self):
        for y in list(self.config.nodeServer.inbound_streams[User.__name__].values()):
            yield y

        for y in list(self.config.nodeServer.inbound_streams[Pool.__name__].values()):
            yield y

        for y in list(
            self.config.nodeClient.outbound_streams[SeedGateway.__name__].values()
        ):
            yield y

    async def get_peer_by_id(self, id_attr):
        if self.config.nodeServer.inbound_streams[User.__name__].get(id_attr):
            return self.config.nodeServer.inbound_streams[User.__name__].get(id_attr)

        if self.config.nodeServer.inbound_streams[Pool.__name__].get(id_attr):
            return self.config.nodeServer.inbound_streams[Pool.__name__].get(id_attr)

        if self.config.nodeClient.outbound_streams[SeedGateway.__name__].get(id_attr):
            return self.config.nodeClient.outbound_streams[SeedGateway.__name__].get(
                id_attr
            )

    def is_linked_peer(self, peer):
        if self.seed_gateway == peer.identity.username_signature:
            return True
        return False


class Group(Peer):
    id_attribute = "rid"

    async def get_outbound_class(self):
        return ServiceProvider

    async def get_inbound_class(self):
        return User

    async def get_outbound_peers(self, nonce=None):
        service_provider = await self.calculate_service_provider()
        return {service_provider.identity.username_signature: service_provider}

    @classmethod
    def type_limit(cls, peer):
        if peer == SeedGateway:
            return 1
        elif peer == User:
            return 1
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [ServiceProvider, User]


class User(Peer):
    id_attribute = "rid"

    async def get_outbound_class(self):
        return ServiceProvider

    async def get_inbound_class(self):
        return User

    async def get_outbound_peers(self):
        return self.config.service_providers

    async def get_inbound_streams(self):
        for peer_stream in list(
            self.config.nodeServer.inbound_streams[User.__name__].values()
        ):
            yield peer_stream

    async def get_outbound_streams(self):
        return list(
            self.config.nodeClient.outbound_streams[ServiceProvider.__name__].values()
        )

    async def get_inbound_pending(self):
        for peer_stream in list(
            self.config.nodeServer.inbound_pending[User.__name__].values()
        ):
            yield peer_stream

    async def get_outbound_pending(self):
        return list(
            self.config.nodeClient.outbound_pending[ServiceProvider.__name__].values()
        )

    @classmethod
    def type_limit(cls, peer):
        if peer == ServiceProvider:
            return 3
        elif peer == User:
            return Config().max_peers or 100000
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [ServiceProvider]

    async def get_sync_peers(self):
        for y in list(
            self.config.nodeClient.outbound_streams[ServiceProvider.__name__].values()
        ):
            yield y

    async def get_peer_by_id(self, id_attr):
        return self.config.nodeClient.outbound_streams[ServiceProvider.__name__].get(
            id_attr
        )

    async def get_route_peers(self, peer, payload):
        for y in list(self.config.nodeClient.outbound_streams[User.__name__].values()):
            yield y

        for y in list(self.config.nodeServer.inbound_streams[User.__name__].values()):
            yield y

    def is_linked_peer(self, peer):
        return False


class Pool(Peer):
    id_attribute = "rid"

    async def get_outbound_class(self):
        return ServiceProvider

    async def get_inbound_class(self):
        return User

    async def get_outbound_peers(self):
        return self.config.service_providers

    async def get_inbound_streams(self):
        for peer_stream in list(
            self.config.nodeServer.inbound_streams[User.__name__].values()
        ):
            yield peer_stream

    async def get_outbound_streams(self):
        return list(
            self.config.nodeClient.outbound_streams[ServiceProvider.__name__].values()
        )

    async def get_inbound_pending(self):
        for peer_stream in list(
            self.config.nodeServer.inbound_pending[User.__name__].values()
        ):
            yield peer_stream

    async def get_outbound_pending(self):
        return list(
            self.config.nodeClient.outbound_pending[ServiceProvider.__name__].values()
        )

    @classmethod
    def type_limit(cls, peer):
        if peer == ServiceProvider:
            return 3
        elif peer == User:
            return Config().max_peers or 100000
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [ServiceProvider]

    async def get_sync_peers(self):
        for y in list(
            self.config.nodeClient.outbound_streams[ServiceProvider.__name__].values()
        ):
            yield y

    async def get_peer_by_id(self, id_attr):
        return self.config.nodeClient.outbound_streams[ServiceProvider.__name__].get(
            id_attr
        )

    async def get_route_peers(self, peer, payload):
        for y in list(self.config.nodeClient.outbound_streams[User.__name__].values()):
            yield y

        for y in list(self.config.nodeServer.inbound_streams[User.__name__].values()):
            yield y

    def is_linked_peer(self, peer):
        return False


class Miner(Peer):
    id_attribute = "address"

    async def get_outbound_class(self):
        return ServiceProvider

    async def get_inbound_class(self):
        return User

    async def get_outbound_peers(self):
        return self.config.service_providers

    @classmethod
    def type_limit(cls, peer):
        if peer == ServiceProvider:
            return 1
        else:
            return 0

    @classmethod
    def compatible_types(cls):
        return [ServiceProvider]


class Peers:
    @staticmethod
    def get_config_seeds():
        config = Config()
        seeds = []
        if hasattr(config, "network_seeds"):
            seeds = [Seed.from_dict(x) for x in config.network_seeds]
        return OrderedDict({x.identity.username_signature: x for x in seeds})

    @classmethod
    def get_seeds(cls):
        from yadacoin.core.nodes import Seeds

        config = Config()
        seeds = Seeds.get_nodes_for_block_height(config.LatestBlock.block.index)
        return OrderedDict({x.identity.username_signature: x for x in seeds})

    @staticmethod
    def get_config_seed_gateways():
        config = Config()
        seed_gateways = []
        if hasattr(config, "network_seed_gateways"):
            seed_gateways = [
                SeedGateway.from_dict(x) for x in config.network_seed_gateways
            ]
        return OrderedDict({x.identity.username_signature: x for x in seed_gateways})

    @classmethod
    def get_seed_gateways(cls):
        from yadacoin.core.nodes import SeedGateways

        config = Config()
        seed_gateways = SeedGateways.get_nodes_for_block_height(
            config.LatestBlock.block.index
        )
        return OrderedDict({x.identity.username_signature: x for x in seed_gateways})

    @staticmethod
    def get_config_service_providers():
        config = Config()
        service_providers = []
        if hasattr(config, "network_service_providers"):
            service_providers = [
                ServiceProvider.from_dict(x) for x in config.network_service_providers
            ]
        return OrderedDict(
            {x.identity.username_signature: x for x in service_providers}
        )

    @classmethod
    def get_service_providers(cls):
        from yadacoin.core.nodes import ServiceProviders

        config = Config()
        service_providers = ServiceProviders.get_nodes_for_block_height(
            config.LatestBlock.block.index
        )
        return OrderedDict(
            {x.identity.username_signature: x for x in service_providers}
        )

    @staticmethod
    def get_config_groups():
        config = Config()
        groups = []
        if hasattr(config, "network_groups"):
            groups = [Group.from_dict(x) for x in config.network_groups]
        return OrderedDict({x.identity.username_signature: x for x in groups})

    @classmethod
    def get_groups(cls):
        groups = [
            Group.from_dict(
                {
                    "host": None,
                    "port": None,
                    "identity": {
                        "username": "group",
                        "username_signature": "MEUCIQDIlC+SpeLwUI4fzV1mkEsJCG6HIvBvazHuMMNGuVKi+gIgV8r1cexwDHM3RFGkP9bURi+RmcybaKHUcco1Qu0wvxw=",
                        "public_key": "036f99ba2238167d9726af27168384d5fe00ef96b928427f3b931ed6a695aaabff",
                        "wif": "KydUVG4w2ZSQkg6DAZ4UCEbfZz9Tg4PsjJFnvHwFsfmRkqXAHN8W",
                    },
                }
            )
        ]
        return OrderedDict({x.identity.username_signature: x for x in groups})

    @staticmethod
    async def get_routes():
        config = Config()
        outbound_peers = await config.peer.get_outbound_peers()
        routes = []
        for outbound_peer in outbound_peers.values():
            if config.peer_type == PEER_TYPES.SEED.value:
                routes = [config.identity.generate_rid(config.identity)]
            elif config.peer_type == PEER_TYPES.SEED_GATEWAY.value:
                routes.append(f"{outbound_peer.rid}")
            elif config.peer_type == PEER_TYPES.SERVICE_PROVIDER.value:
                seed_rid = config.seeds[outbound_peer.seed].identity.generate_rid(
                    config.seed_gateways[
                        outbound_peer.identity.username_signature
                    ].identity.username_signature
                )
                routes.append(f"{seed_rid}:{outbound_peer.rid}")
            elif config.peer_type in [PEER_TYPES.USER.value, PEER_TYPES.POOL.value]:
                seed_rid = config.seeds[outbound_peer.seed].identity.generate_rid(
                    config.seed_gateways[
                        outbound_peer.seed_gateway
                    ].identity.username_signature
                )
                seed_gateway_rid = config.seed_gateways[
                    outbound_peer.seed_gateway
                ].identity.generate_rid(outbound_peer.identity.username_signature)
                routes.append(f"{seed_rid}:{seed_gateway_rid}:{outbound_peer.rid}")
        return routes
