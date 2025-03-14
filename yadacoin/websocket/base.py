"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

import base64
import hashlib
import json
from asyncio import sleep as async_sleep
from traceback import format_exc

from bitcoin.wallet import P2PKHBitcoinAddress
from coincurve import verify_signature
from ecdsa import SECP256k1, VerifyingKey
from ecdsa.util import sigdecode_der
from tornado import ioloop
from tornado.websocket import WebSocketClosedError, WebSocketHandler

from yadacoin.core.chain import CHAIN
from yadacoin.core.collections import Collections
from yadacoin.core.config import Config
from yadacoin.core.identity import Identity
from yadacoin.core.peer import Group, SeedGateway, ServiceProvider, User
from yadacoin.core.transaction import Transaction
from yadacoin.tcpsocket.base import BaseRPC


class RCPWebSocketServer(WebSocketHandler):
    inbound_streams = {}
    inbound_pending = {}
    config = None

    def __init__(self, application, request):
        super(RCPWebSocketServer, self).__init__(application, request)
        self.config = Config()
        self.peer = None

    async def open(self):
        pass

    async def on_message(self, data):
        if not data:
            return
        body = json.loads(data)
        method = body.get("method")
        await getattr(self, method)(body)
        if (
            hasattr(self.config, "websocket_traffic_debug")
            and self.config.websocket_traffic_debug == True
        ):
            self.config.app_log.debug(
                f"SERVER RECEIVED {self.peer.identity.username} {method} {data}"
            )

    def on_close(self):
        self.remove_peer(self.peer)

    def check_origin(self, origin):
        return True

    async def connect(self, body):
        params = body.get("params")
        if not params.get("identity"):
            self.close()
            return {}

        peer = User.from_dict(
            {"host": None, "port": None, "identity": params.get("identity")}
        )
        self.peer = peer
        self.peer.groups = {}
        RCPWebSocketServer.inbound_streams[User.__name__][peer.rid] = self
        for collection in Collections:
            rid = self.peer.identity.generate_rid(
                self.peer.identity.username_signature, collection.value
            )
            RCPWebSocketServer.inbound_streams[User.__name__][rid] = self

        try:
            vk = VerifyingKey.from_string(
                bytes.fromhex(peer.identity.public_key), curve=SECP256k1
            )

            result = vk.verify(
                base64.b64decode(peer.identity.username_signature),
                peer.identity.username.encode(),
                hashlib.sha256,
                sigdecode=sigdecode_der,
            )

            if not result:
                self.close()
                return
        except:
            self.config.app_log.error("invalid peer identity signature")
            self.close()
            return {}

        try:
            self.config.app_log.info("new {} is valid".format(peer.__class__.__name__))
            await self.write_result(
                "connect_confirm",
                {
                    "identity": self.config.peer.identity.to_dict,
                    "shares_required": self.config.shares_required,
                    "credit_balance": await self.get_credit_balance(),
                    "server_pool_address": f"{self.config.peer_host}:{self.config.stratum_pool_port}",
                },
                body=body,
            )
        except:
            self.config.app_log.error("invalid peer identity signature")
            self.close()
            return {}

    async def chat_history(self, body):
        results = (
            await self.config.mongo.async_db.miner_transactions.find(
                {
                    "requested_rid": self.config.peer.identity.generate_rid(
                        body.get("params", {}).get("to").get("username_signature")
                    )
                },
                {"_id": 0},
            )
            .sort([("time", -1)])
            .to_list(100)
        )
        await self.write_result(
            "chat_history_response",
            {
                "chats": sorted(results, key=lambda x: x["time"]),
                "to": body.get("params", {}).get("to"),
            },
            body=body,
        )

    async def route_confirm(self, body):
        credit_balance = await self.get_credit_balance()
        await self.write_result(
            "route_server_confirm", {"credit_balance": credit_balance}, body=body
        )

    async def route(self, body, source="websocket"):
        # our peer SHOULD only ever been a service provider if we're offering a websocket but we'll give other options here
        route_server_confirm_out = {}
        if self.config.shares_required:
            credit_balance = await self.get_credit_balance()

            if credit_balance <= 0:
                await self.write_result(
                    "route_server_confirm",
                    {"credit_balance": credit_balance},
                    body=body,
                )
                return
            route_server_confirm_out = {"credit_balance": credit_balance}

        params = body.get("params")
        route = params.get("route")
        transaction = Transaction.from_dict(params["transaction"])
        group = None
        for rid in route.split(":"):
            if rid in self.config.websocketServer.inbound_streams[User.__name__]:
                peer_stream = self.config.websocketServer.inbound_streams[
                    User.__name__
                ][rid]
                if peer_stream.peer.rid != transaction.requester_rid:
                    await peer_stream.write_params("route", params)
            if rid in self.config.websocketServer.inbound_streams[Group.__name__]:
                group = self.config.websocketServer.inbound_streams[Group.__name__][rid]
            if group and rid in group:
                peer_stream = group[rid]
                await peer_stream.write_params("route", params)
        await self.config.mongo.async_db.miner_transactions.replace_one(
            {"id": transaction.transaction_signature},
            transaction.to_dict(),
            upsert=True,
        )
        if transaction.private == True:
            await self.config.mongo.async_db.private_transactions.replace_one(
                {"id": transaction.transaction_signature},
                transaction.to_dict(),
                upsert=True,
            )
        if isinstance(self.config.peer, User) and source == "websocket":
            for rid, peer_stream in self.config.nodeClient.outbound_streams[
                ServiceProvider.__name__
            ].items():
                await BaseRPC().write_params(peer_stream, "route", params)

        await self.write_result(
            "route_server_confirm", route_server_confirm_out, body=body
        )

    async def newtxn(self, body, source="websocket"):
        params = body.get("params")
        if not params.get("transaction"):
            return

        check_max_inputs = False
        if self.config.LatestBlock.block.index > CHAIN.CHECK_MAX_INPUTS_FORK:
            check_max_inputs = True

        check_masternode_fee = False
        if self.config.LatestBlock.block.index >= CHAIN.CHECK_MASTERNODE_FEE_FORK:
            check_masternode_fee = True

        check_kel = False
        if self.config.LatestBlock.block.index >= CHAIN.CHECK_KEL_FORK:
            check_kel = True

        txn = Transaction.from_dict(params.get("transaction"))
        try:
            await txn.verify(
                check_max_inputs=check_max_inputs,
                check_masternode_fee=check_masternode_fee,
                check_kel=check_kel,
            )
        except:
            return

        await self.config.mongo.async_db.miner_transactions.replace_one(
            {"id": txn.transaction_signature}, txn.to_dict(), upsert=True
        )
        if (
            self.peer.identity.public_key
            == params.get("transaction", {}).get("public_key")
            and source == "websocket"
        ):
            if isinstance(self.config.peer, ServiceProvider):
                for rid, peer_stream in list(
                    self.config.nodeServer.inbound_streams[User.__name__].values()
                ):
                    await BaseRPC().write_params(peer_stream, "newtxn", params)

                for rid, peer_stream in list(
                    self.config.nodeClient.outbound_streams[
                        SeedGateway.__name__
                    ].values()
                ):
                    await BaseRPC().write_params(peer_stream, "newtxn", params)
            return

        await self.write_params("newtxn", params)

    async def newtxn_confirm(self, body):
        pass

    async def get_credit_balance(self):
        address = P2PKHBitcoinAddress.from_pubkey(
            bytes.fromhex(self.peer.identity.public_key)
        )

        shares = await self.config.mongo.async_db.shares.count_documents(
            {"address": str(address)}
        )

        txns_routed = (
            await self.config.mongo.async_db.miner_transactions.count_documents(
                {"public_key": self.peer.identity.public_key}
            )
        )

        credit_balance = shares - (txns_routed * 0.1)

        return credit_balance if credit_balance > 0 else 0.00

    async def join_group(self, body):
        # for rid, group in self.peer.groups.items():
        #     group_id_attr = getattr(group, group.id_attribute)
        #     if group_id_attr in self.inbound_streams[Group.__name__]:
        #         if self.peer.rid in self.inbound_streams[Group.__name__][group_id_attr]:
        #             del self.inbound_streams[Group.__name__][group_id_attr][self.peer.rid]

        #             for rid, peer_stream in RCPWebSocketServer.inbound_streams[Group.__name__][group_id_attr].items():
        #                 await peer_stream.write_result('group_user_count', {
        #                     'group_user_count': len(RCPWebSocketServer.inbound_streams[Group.__name__][group_id_attr])
        #                 }, body=body)

        if self.config.address_is_valid(body.get("params", {}).get("username")):
            address = body.get("params", {}).get("username")
            RCPWebSocketServer.inbound_streams[User.__name__][address] = self
            members = {address: self.peer.identity.to_dict}

            await self.write_result("join_confirmed", {"members": members}, body=body)
            return

        group = Identity.from_dict(body.get("params"))

        members = {}
        members.update(self.append_to_group(group, Collections.FILE_REQUEST.value))
        members.update(self.append_to_group(group, Collections.GROUP_CHAT.value))
        members.update(self.append_to_group(group, Collections.GROUP_MAIL.value))
        members.update(self.append_to_group(group, Collections.GROUP_CALENDAR.value))
        members.update(self.append_to_group(group, Collections.GROUP_CHAT_FILE.value))

        await self.write_result("join_confirmed", {"members": members}, body=body)

    async def join_proxy(self, body):
        # we're trying to establish a route back to their wallet
        data = body["params"]
        identity = Identity.from_dict(data["identity"])
        identity_rid = identity.generate_rid(self.config.username_signature)
        if "alias" in data:
            alias = Identity.from_dict(data["alias"])
        challenge = data["challenge"]
        contact = True  # self.config.GU.get_contact(username_signature=identity.username_signature)
        if contact:
            result1 = verify_signature(
                base64.b64decode(challenge["origin"]),
                challenge["message"].encode("utf-8"),
                bytes.fromhex(self.config.public_key),
            )  # did we sign it?
            result2 = verify_signature(
                base64.b64decode(challenge["signature"]),
                challenge["message"].encode("utf-8"),
                bytes.fromhex(identity.public_key),
            )  # did my contact sign it?
            if result1 and result2:
                if "alias" in data:
                    alias_rid = alias.generate_rid(self.config.username_signature)
                    if (
                        alias_rid
                        in self.config.websocketServer.inbound_streams[User.__name__]
                        and identity_rid
                        in self.config.websocketServer.inbound_streams[User.__name__]
                    ):
                        self.config.websocketServer.inbound_streams[User.__name__][
                            identity_rid
                        ].link = alias_rid
                        self.config.websocketServer.inbound_streams[User.__name__][
                            identity_rid
                        ].data = data
                        self.config.websocketServer.inbound_streams[User.__name__][
                            alias_rid
                        ].link = identity_rid
                        self.config.websocketServer.inbound_streams[User.__name__][
                            alias_rid
                        ].data = data
                        await self.config.websocketServer.inbound_streams[
                            User.__name__
                        ][alias_rid].write_params("proxy_linked", data["identity"])
                    else:
                        self.config.websocketServer.inbound_streams[User.__name__][
                            identity_rid
                        ] = self
                await self.write_result("join_proxy_confirmed", {}, body=body)

    async def proxy_auth(self, body):
        # we're trying to establish a route back to their wallet
        data = body["params"]
        identity = Identity.from_dict(data["identity"])
        identity_rid = identity.generate_rid(self.config.username_signature)
        challenge = data["challenge"]
        contact = True  # self.config.GU.get_contact(username_signature=identity.username_signature)
        if contact:
            result1 = verify_signature(
                base64.b64decode(challenge["origin"]),
                challenge["message"].encode("utf-8"),
                bytes.fromhex(self.config.public_key),
            )  # did we sign it?
            result2 = verify_signature(
                base64.b64decode(challenge["signature"]),
                challenge["message"].encode("utf-8"),
                bytes.fromhex(identity.public_key),
            )  # did my contact sign it?
            if result1 and result2 and self.config.challenges.get(identity_rid):
                link = self.config.websocketServer.inbound_streams[User.__name__][
                    identity_rid
                ].link
                await self.config.websocketServer.inbound_streams[User.__name__][
                    link
                ].write_params("proxy_signature_request", data)
                while "signature" not in self.config.challenges[identity_rid]:
                    await async_sleep(1)
                data["challenge"] = self.config.challenges[identity_rid]
                await self.config.websocketServer.inbound_streams[User.__name__][
                    identity_rid
                ].write_params(
                    "proxy_signature_response",
                    self.config.websocketServer.inbound_streams[User.__name__][
                        identity_rid
                    ].data,
                )
                del self.config.challenges[identity_rid]

    async def dh_public_key(self, body):
        data = body["result"]
        identity = Identity.from_dict(data["identity"])
        rid = identity.generate_rid(self.config.username_signature)
        if rid in self.config.websocketServer.inbound_streams[User.__name__]:
            self.config.websocketServer.inbound_streams[User.__name__][
                rid
            ].dh_public_key = data["dh_public_key"]

    async def proxy_signature_response(self, body):
        data = body["result"]
        await self.write_result("proxy_signature_response_confirm", {}, body)
        if "alias" in data:
            alias = Identity.from_dict(data["alias"])
            alias_rid = alias.generate_rid(self.config.username_signature)
            if alias_rid in self.config.websocketServer.inbound_streams[User.__name__]:
                self.config.challenges[alias_rid]["signature"] = data["challenge"][
                    "signature"
                ]

    def append_to_private(self, group, collection):
        group_rid = group.generate_rid(group.username_signature, collection)
        if group_rid not in RCPWebSocketServer.inbound_streams[Group.__name__]:
            RCPWebSocketServer.inbound_streams[Group.__name__][group_rid] = {}
        peer_rid = self.peer.identity.generate_rid(
            self.peer.identity.username_signature, collection
        )
        RCPWebSocketServer.inbound_streams[Group.__name__][group_rid][peer_rid] = self
        return {
            group_rid: [
                x.peer.identity.to_dict
                for x in list(
                    RCPWebSocketServer.inbound_streams[Group.__name__][
                        group_rid
                    ].values()
                )
            ]
        }

    def append_to_group(self, group, collection):
        group_rid = group.generate_rid(group.username_signature, collection)
        RCPWebSocketServer.inbound_streams[Group.__name__].setdefault(group_rid, {})
        peer_rid = self.peer.identity.generate_rid(
            self.peer.identity.username_signature, collection
        )
        RCPWebSocketServer.inbound_streams[Group.__name__][group_rid][peer_rid] = self
        self.peer.groups[group_rid] = Group(identity=group)
        return {
            group_rid: [
                x.peer.identity.to_dict
                for x in list(
                    RCPWebSocketServer.inbound_streams[Group.__name__][
                        group_rid
                    ].values()
                )
            ]
        }

    async def service_provider_request(self, body):
        if not body.get("params").get("group"):
            self.config.app_log.error("Group not provided")
            return
        group = Group.from_dict(
            {"host": None, "port": None, "identity": body.get("params").get("group")}
        )
        seed_gateway = await group.calculate_seed_gateway()
        if not seed_gateway:
            self.config.app_log.error("No seed gateways available.")
            return
        params = {"seed_gateway": seed_gateway.to_dict(), "group": group.to_dict()}

        for peer_stream in list(
            self.config.nodeClient.outbound_streams[SeedGateway.__name__].values()
        ):
            await BaseRPC().write_params(
                peer_stream, "service_provider_request", params
            )
        await self.write_result("service_provider_request_confirm", {}, body=body)

    async def online(self, body):
        rids = body.get("params").get("rids")
        matching_rids = set(rids) & set(
            self.config.websocketServer.inbound_streams[User.__name__].keys()
        )
        await self.write_result(
            "online", {"online_rids": list(matching_rids)}, body=body
        )

    @staticmethod
    async def send_block(block):
        payload = {"payload": {"block": block.to_dict()}}
        for stream in list(
            Config().websocketServer.inbound_streams[User.__name__].values()
        ):
            await stream.write_params("newblock", payload)

    def remove_peer(self, peer):
        if not peer:
            Config().app_log.warning("Failed removing websocket peer.")
            return
        id_attr = getattr(peer, peer.id_attribute)
        if id_attr in self.inbound_streams[peer.__class__.__name__]:
            del self.inbound_streams[peer.__class__.__name__][id_attr]

        loop = ioloop.IOLoop.current()
        for group in list(peer.groups.values()):
            rid = group.identity.generate_rid(
                group.identity.username_signature, Collections.GROUP_CHAT.value
            )
            peer_id = peer.identity.generate_rid(
                peer.identity.username_signature, Collections.GROUP_CHAT.value
            )
            if (
                rid in self.inbound_streams[Group.__name__]
                and peer_id in self.inbound_streams[Group.__name__][rid]
            ):
                del self.inbound_streams[Group.__name__][rid][peer_id]
            group_id_attr = getattr(group, group.id_attribute)
            if group_id_attr in self.inbound_streams[Group.__name__]:
                if id_attr in self.inbound_streams[Group.__name__]:
                    del self.inbound_streams[Group.__name__][group_id_attr][id_attr]
                for rid, peer_stream in list(
                    RCPWebSocketServer.inbound_streams[Group.__name__][
                        group_id_attr
                    ].values()
                ):
                    if id_attr == rid:
                        continue
                    loop.add_callback(
                        peer_stream.write_result,
                        "group_user_count",
                        {
                            "group_user_count": len(
                                RCPWebSocketServer.inbound_streams[Group.__name__][
                                    group_id_attr
                                ]
                            )
                        },
                    )

    async def write_result(self, method, data, body=None):
        await self.write_as_json(method, data, "result", body)

    async def write_params(self, method, data, body=None):
        await self.write_as_json(method, data, "params", body)

    async def write_as_json(self, method, data, rpc_type, body=None):
        req_id = body.get("id") if body else 1
        rpc_data = {"id": req_id, "method": method, "jsonrpc": 2.0, rpc_type: data}

        try:
            await self.write_message("{}".format(json.dumps(rpc_data)).encode())
        except WebSocketClosedError:
            self.remove_peer(self.peer)
        except:
            self.config.app_log.debug(format_exc())
            self.remove_peer(self.peer)

        if (
            hasattr(self.config, "websocket_traffic_debug")
            and self.config.websocket_traffic_debug == True
        ):
            self.config.app_log.debug(
                f"SENT {self.peer.identity.username} {method} {data} {rpc_type} {req_id}"
            )


WEBSOCKET_HANDLERS = [
    (r"/websocket", RCPWebSocketServer),
]
