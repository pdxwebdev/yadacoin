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


def _peer_key(peer):
    """Stable dict key for a peer in the seed/gateway/provider maps.

    Peers may carry an inline ``identity`` or only an ``identity_announcement``
    (KEL inception txn id).  Key on the identity signature when present,
    otherwise fall back to the announcement id (then host) so the map can still
    be built for KEL-anchored nodes.
    """
    if getattr(peer, "identity", None) is not None:
        return peer.identity.username_signature
    return getattr(peer, "identity_announcement", None) or peer.host


def _resolve_peer_by_ref(peers_map, ref):
    """Resolve a peer from a ``seed`` / ``seed_gateway`` cross-reference.

    A node's ``seed`` / ``seed_gateway`` field may reference the upstream peer
    by its ``username_signature`` (when the peer carries an inline identity) or
    by its ``identity_announcement`` id (when the peer is KEL-anchored and has
    no inline identity).  The peer maps (``config.seeds`` /
    ``config.seed_gateways`` / ``config.service_providers``) are keyed by
    whichever identifier the referenced node actually carries, so a reference
    value does not always equal the map key.

    Try a direct key lookup first, then fall back to scanning for a node whose
    ``identity_announcement`` or ``username_signature`` matches ``ref``.
    Returns ``None`` if no peer matches.
    """
    if not ref:
        return None
    if ref in peers_map:
        return peers_map[ref]
    for peer in peers_map.values():
        if getattr(peer, "identity_announcement", None) == ref:
            return peer
        ident = getattr(peer, "identity", None)
        if ident is not None and getattr(ident, "username_signature", None) == ref:
            return peer
    return None


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
        protocol_version=5,
        node_version=(0, 0, 0),
        peer_type=None,
        identity_announcement=None,
    ):
        self.host = host
        self.port = port
        self.identity = identity
        self.seed = seed
        self.seed_gateway = seed_gateway
        self.http_host = http_host
        self.http_port = http_port
        self.http_protocol = http_protocol
        self.config = Config()
        self.app_log = getLogger("tornado.application")
        self.protocol_version = protocol_version
        self.authenticated = False
        self.node_version = tuple([int(x) for x in node_version])
        self.peer_type = peer_type
        # When set, this peer is identified by an on-chain identity announcement
        # transaction id instead of an inline ``identity`` dict.  Clients anchor
        # KEL verification to the inception transaction referenced here.
        self.identity_announcement = identity_announcement
        # Resolved anchor public key (K0) once identity_announcement is resolved.
        self.anchor_public_key = None

    @staticmethod
    async def my_peer():
        config = Config()
        # The node's authoritative identity is its KEL inception / identity
        # announcement.  Resolve it (mempool first, then confirmed chain) and
        # prefer those values over the config-derived ones so the peer identity
        # always matches the inception identity in the relationship field.
        my_username = config.username
        my_username_signature = config.username_signature
        my_public_key = config.public_key
        my_identity_announcement = None

        kel_manager = getattr(config, "kel_manager", None)
        ia_id = getattr(kel_manager, "_inception_txn_id", None) if kel_manager else None
        if ia_id:
            from yadacoin.core.identityannouncement import IdentityAnnouncement

            ia_doc = await IdentityAnnouncement.get_by_transaction_id(ia_id)
            if ia_doc:
                my_identity_announcement = ia_id
                identity_data = ia_doc.get("identity") or {}
                if identity_data.get("username"):
                    my_username = identity_data["username"]
                if identity_data.get("username_signature"):
                    my_username_signature = identity_data["username_signature"]
                if ia_doc.get("public_key"):
                    my_public_key = ia_doc["public_key"]

        config.app_log.info(
            "my_peer: username=%s username_signature=%s public_key=%s ia_id=%s",
            my_username,
            my_username_signature[:16] if my_username_signature else None,
            my_public_key[:16] if my_public_key else None,
            my_identity_announcement,
        )

        my_peer = {
            "host": config.peer_host,
            "port": config.peer_port,
            "identity": {
                "username": my_username,
                "username_signature": my_username_signature,
                "public_key": my_public_key,
            },
            "peer_type": config.peer_type,
            "http_host": config.ssl.common_name or config.peer_host,
            "http_port": config.ssl.port or config.serve_port,
            "protocol_version": 5,
            "node_version": config.node_version,
            "identity_announcement": my_identity_announcement,
        }

        # KEL-anchored nodes carry no inline identity, so the seed/gateway/
        # provider maps key them by their identity_announcement id rather than a
        # username_signature.  Look the running node up by either identifier.
        def _lookup(map_, usig, ia):
            entry = map_.get(usig)
            if entry is None and ia:
                entry = map_.get(ia)
            return entry

        if config.peer_type == PEER_TYPES.SEED.value:
            entry = _lookup(
                config.seeds, my_username_signature, my_identity_announcement
            )
            if entry is None:
                config.peer_type = PEER_TYPES.USER.value
                my_peer.update({"peer_type": PEER_TYPES.USER.value})
                return User.from_dict(my_peer, is_me=True)
            my_peer[PEER_TYPES.SEED_GATEWAY.value] = entry.seed_gateway
            return Seed.from_dict(my_peer, is_me=True)
        elif config.peer_type == PEER_TYPES.SEED_GATEWAY.value:
            entry = _lookup(
                config.seed_gateways, my_username_signature, my_identity_announcement
            )
            if entry is None:
                config.peer_type = PEER_TYPES.USER.value
                my_peer.update({"peer_type": PEER_TYPES.USER.value})
                return User.from_dict(my_peer, is_me=True)
            my_peer[PEER_TYPES.SEED.value] = entry.seed
            return SeedGateway.from_dict(my_peer, is_me=True)
        elif config.peer_type == PEER_TYPES.SERVICE_PROVIDER.value:
            entry = _lookup(
                config.service_providers,
                my_username_signature,
                my_identity_announcement,
            )
            if entry is None:
                config.peer_type = PEER_TYPES.USER.value
                my_peer.update({"peer_type": PEER_TYPES.USER.value})
                return User.from_dict(my_peer, is_me=True)
            my_peer[PEER_TYPES.SEED_GATEWAY.value] = entry.seed_gateway
            my_peer[PEER_TYPES.SEED.value] = entry.seed
            return ServiceProvider.from_dict(my_peer, is_me=True)
        elif config.peer_type == PEER_TYPES.POOL.value or config.pool_payout == True:
            config.peer_type = (
                PEER_TYPES.POOL.value
            )  # in case peer_type is 'user' and pool_payout is enabled
            my_peer.update({"peer_type": PEER_TYPES.POOL.value})
            return Pool.from_dict(my_peer, is_me=True)
        else:  # default if not specified
            return User.from_dict(my_peer, is_me=True)

    @classmethod
    def from_dict(cls, peer, is_me=False):
        identity = peer.get("identity")
        inst = cls(
            peer["host"],
            peer["port"],
            Identity.from_dict(identity) if identity else None,
            seed=peer.get(PEER_TYPES.SEED.value),
            seed_gateway=peer.get(PEER_TYPES.SEED_GATEWAY.value),
            http_host=peer.get("http_host"),
            http_port=peer.get("http_port"),
            http_protocol=peer.get("http_protocol"),
            protocol_version=peer.get("protocol_version", 1),
            node_version=peer.get("node_version", (0, 0, 0)),
            peer_type=peer.get("peer_type") or getattr(cls, "peer_type", None),
            identity_announcement=peer.get("identity_announcement"),
        )
        return inst

    @property
    def rid(self):
        config = Config()
        # Peers keyed only by identity_announcement (KEL inception) have no
        # inline identity until resolved; their rid is unavailable until then.
        if self.identity is None:
            return None
        if (
            hasattr(config, "peer")
            and getattr(config.peer, "identity", None) is not None
        ):
            return self.identity.generate_rid(config.peer.identity.username_signature)
        return None

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

        def _gw_ignore_key(gw):
            # outbound_ignore is keyed by the gateway's inline username_signature
            # (or its identity_announcement id for KEL-anchored gateways that
            # carry no inline identity yet).
            if getattr(gw, "identity", None) is not None:
                return gw.identity.username_signature
            return getattr(gw, "identity_announcement", None)

        while (
            _gw_ignore_key(self.config.seed_gateways[username_signatures[seed_select]])
            in self.config.nodeClient.outbound_ignore[SeedGateway.__name__]
        ):
            seed_select += 1
            if num_reset and seed_select >= first_number:
                return None  # checked every gateway, all are ignored
            if seed_select >= len(username_signatures):
                seed_select = 0
                num_reset = True

        seed_gateway = self.config.seed_gateways[
            list(self.config.seed_gateways)[seed_select]
        ]
        return seed_gateway

    async def ensure_peers_connected(self):
        if (
            getattr(self.config, "peer", None) is None
            or getattr(self.config.peer, "identity", None) is None
        ):
            return
        outbound_peers = (await self.get_outbound_peers()).values()
        # Resolve any on-chain identity_announcement peers so they have a
        # concrete Identity (and therefore a stable rid) before we key on it.
        for x in outbound_peers:
            if getattr(x, "identity_announcement", None) and x.identity is None:
                await x.resolve_identity_announcement()
        self.config.app_log.info(
            "ensure_peers_connected: raw outbound_peers=%d [%s]",
            len(outbound_peers),
            ", ".join(
                f"{x.__class__.__name__}:{getattr(x, x.id_attribute, '?')}:id={getattr(x.identity, 'username_signature', '')[:16] if x.identity else None}"
                for x in outbound_peers
            ),
        )
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
        self.config.app_log.info(
            "ensure_peers_connected: outbound_class=%s limit=%s stream_collection=%d outbound_ignored=%d",
            outbound_class.__name__,
            limit,
            len(stream_collection),
            len(outbound_ignored),
        )
        await self.connect(
            stream_collection,
            limit,
            await self.get_outbound_peers(),
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
        d = {
            "host": self.host,
            "port": self.port,
            "identity": self.identity.to_dict if self.identity else None,
            "rid": self.rid,
            PEER_TYPES.SEED.value: self.seed,
            PEER_TYPES.SEED_GATEWAY.value: self.seed_gateway,
            "http_host": self.http_host,
            "http_port": self.http_port,
            "http_protocol": self.http_protocol,
            "protocol_version": self.protocol_version,
            "node_version": self.node_version,
            "peer_type": self.peer_type,
        }
        if self.identity_announcement:
            d["identity_announcement"] = self.identity_announcement
        return d

    async def resolve_identity_announcement(self) -> bool:
        """Populate ``self.identity`` (and ``self.anchor_public_key``) from the
        on-chain identity announcement referenced by ``identity_announcement``.

        Returns True if no resolution was needed or it succeeded; False if a
        configured ``identity_announcement`` could not be found on-chain.
        """
        if self.identity is not None:
            return True
        ia_id = getattr(self, "identity_announcement", None)
        if not ia_id:
            return True
        from yadacoin.core.identityannouncement import IdentityAnnouncement

        result = await IdentityAnnouncement.get_by_transaction_id(ia_id)
        if not result:
            return False
        identity_data = result.get("identity") or {}
        self.identity = Identity(
            public_key=result.get("public_key", ""),
            username=identity_data.get("username", "") or "",
            username_signature=identity_data.get("username_signature", "") or "",
        )
        self.anchor_public_key = result.get("public_key") or None
        return True

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
    peer_type = PEER_TYPES.SEED.value

    async def get_outbound_class(self):
        return Seed

    async def get_inbound_class(self):
        return SeedGateway

    async def get_outbound_peers(self):
        if (
            self.identity
            and self.config.peer.identity.public_key == self.identity.public_key
        ):
            del self.config.seeds[self.config.inception.transaction_signature]
        return self.config.seeds

    async def get_inbound_peers(self):
        if (
            self.identity
            and self.config.peer.identity.public_key == self.identity.public_key
        ):
            del self.config.seeds[self.config.peer.identity.username_signature]
        peers = {}
        peers.update(self.config.seeds)
        seed_gateway = _resolve_peer_by_ref(
            self.config.seed_gateways, self.seed_gateway
        )
        if seed_gateway is not None and seed_gateway.identity is not None:
            peers[seed_gateway.identity.username_signature] = seed_gateway
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
                bridge_seed = _resolve_peer_by_ref(
                    self.config.seeds, payload[self.source_property]
                )
                if bridge_seed is None:
                    self.config.app_log.error(
                        "No bridge seed found. Cannot route transaction."
                    )
                    return
            else:
                # this must be the identity of the destination service provider
                # the message originator must provide the necissary service provider identity information
                # typically, the originator will grab all mutual service providers of the originator and the recipient of the message
                # and send "through" every service provider so the recipient will receive the message on all services

                peer = Peer.from_dict(payload.get("dest_service_provider"))
                bridge_seed_gateway = (
                    await peer.calculate_seed_gateway()
                )  # get the seed gateway
                if bridge_seed_gateway is None or not bridge_seed_gateway.seed:
                    self.config.app_log.error(
                        "No bridge seed gateway found. Cannot route transaction."
                    )
                    return
                # Resolve the bridge seed by its reference (username_signature or
                # identity_announcement id) so KEL-anchored seeds are supported.
                bridge_seed = _resolve_peer_by_ref(
                    self.config.seeds, bridge_seed_gateway.seed
                )
                if bridge_seed is None:
                    self.config.app_log.error(
                        "No bridge seed found. Cannot route transaction."
                    )
                    return
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
                ref = (
                    getattr(
                        bridge_seed_from_payload.identity, "username_signature", None
                    )
                    or bridge_seed_from_payload.identity_announcement
                )
                bridge_seed = _resolve_peer_by_ref(self.config.seeds, ref)
                if bridge_seed is None:
                    self.config.app_log.error(
                        "No bridge seed found. Cannot route transaction."
                    )
                    return
            else:
                # this must be the identity of the destination service provider
                # the message originator must provide the necissary service provider identity information
                # typically, the originator will grab all mutual service providers of the originator and the recipient of the message
                # and send "through" every service provider so the recipient will receive the message on all services

                bridge_seed_gateway = Peer.from_dict(
                    payload.get(PEER_TYPES.SEED_GATEWAY.value)
                )
                if bridge_seed_gateway is None:
                    self.config.app_log.error(
                        "No bridge seed gateway found. Cannot route transaction."
                    )
                    return
                sg_ref = (
                    getattr(bridge_seed_gateway.identity, "username_signature", None)
                    or bridge_seed_gateway.identity_announcement
                )
                resolved_sg = _resolve_peer_by_ref(self.config.seed_gateways, sg_ref)
                if resolved_sg is None or not resolved_sg.seed:
                    self.config.app_log.error(
                        "No bridge seed gateway found. Cannot route transaction."
                    )
                    return
                bridge_seed = _resolve_peer_by_ref(self.config.seeds, resolved_sg.seed)
                if bridge_seed is None:
                    self.config.app_log.error(
                        "No bridge seed found. Cannot route transaction."
                    )
                    return
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
        # Compare against the peer's stable ref (username_signature when it
        # carries an inline identity, else its identity_announcement id) so
        # KEL-anchored peers are matched correctly.
        return self.seed_gateway == _peer_key(peer)

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
    peer_type = PEER_TYPES.SEED_GATEWAY.value

    async def get_outbound_class(self):
        return Seed

    async def get_inbound_class(self):
        return ServiceProvider

    async def get_outbound_peers(self):
        if not self.seed or self.seed not in self.config.seeds:
            self.config.app_log.warning(
                "SeedGateway.get_outbound_peers: no valid upstream seed configured "
                "(self.seed=%r); this gateway cannot dial a seed. Set the 'seed' field "
                "on this node's seed_gateway entry (the seed's username_signature / "
                "identity_announcement id).",
                self.seed,
            )
            return {}
        seed = self.config.seeds[self.seed]
        if seed.identity is None:
            return {}
        return {seed.identity.username_signature: seed}

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
        return self.seed == _peer_key(peer)


class ServiceProvider(Peer):
    id_attribute = "rid"
    source_property = "source_service_provider"
    peer_type = PEER_TYPES.SERVICE_PROVIDER.value

    async def get_outbound_class(self):
        return SeedGateway

    async def get_inbound_class(self):
        return User

    async def get_outbound_peers(self, nonce=None):
        if not self.seed_gateway:
            return self.config.seed_gateways
        seed_gateway = _resolve_peer_by_ref(
            self.config.seed_gateways, self.seed_gateway
        )
        if seed_gateway is None or seed_gateway.identity is None:
            return {}
        return {seed_gateway.identity.username_signature: seed_gateway}

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
                    peer.identity is not None
                    and peer_stream.peer.identity is not None
                    and peer.identity.username_signature
                    == peer_stream.peer.identity.username_signature
                ):
                    continue
                yield peer_stream

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
                    peer.identity is not None
                    and peer_stream.peer.identity is not None
                    and peer.identity.username_signature
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
        # Compare against the peer's stable ref (username_signature when it
        # carries an inline identity, else its identity_announcement id) so
        # KEL-anchored peers are matched correctly.
        return self.seed_gateway == _peer_key(peer)


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
    peer_type = PEER_TYPES.USER.value

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
    peer_type = PEER_TYPES.POOL.value

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
        return OrderedDict({_peer_key(x): x for x in seeds})

    @classmethod
    def get_seeds(cls):
        from yadacoin.core.nodes import Seeds

        config = Config()
        seeds = Seeds.get_nodes_for_block_height(config.LatestBlock.block.index)
        return OrderedDict({_peer_key(x): x for x in seeds})

    @staticmethod
    def get_config_seed_gateways():
        config = Config()
        seed_gateways = []
        if hasattr(config, "network_seed_gateways"):
            seed_gateways = [
                SeedGateway.from_dict(x) for x in config.network_seed_gateways
            ]
        return OrderedDict({_peer_key(x): x for x in seed_gateways})

    @classmethod
    def get_seed_gateways(cls):
        from yadacoin.core.nodes import SeedGateways

        config = Config()
        seed_gateways = SeedGateways.get_nodes_for_block_height(
            config.LatestBlock.block.index
        )
        return OrderedDict({_peer_key(x): x for x in seed_gateways})

    @staticmethod
    def get_config_service_providers():
        config = Config()
        service_providers = []
        if hasattr(config, "network_service_providers"):
            service_providers = [
                ServiceProvider.from_dict(x) for x in config.network_service_providers
            ]
        return OrderedDict(
            {
                (
                    x.identity.username_signature
                    if x.identity is not None
                    else (x.identity_announcement or x.host)
                ): x
                for x in service_providers
            }
        )

    @classmethod
    def get_service_providers(cls):
        from yadacoin.core.nodes import ServiceProviders

        config = Config()
        service_providers = ServiceProviders.get_nodes_for_block_height(
            config.LatestBlock.block.index
        )
        return OrderedDict(
            {
                (
                    x.identity.username_signature
                    if x.identity is not None
                    else (x.identity_announcement or x.host)
                ): x
                for x in service_providers
            }
        )

    @staticmethod
    def get_config_groups():
        config = Config()
        groups = []
        if hasattr(config, "network_groups"):
            groups = [Group.from_dict(x) for x in config.network_groups]
        return OrderedDict({_peer_key(x): x for x in groups})

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
        return OrderedDict({_peer_key(x): x for x in groups})
