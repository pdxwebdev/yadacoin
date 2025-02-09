import base64
import json
from pathlib import Path

import tornado.ioloop
import tornado.web
import tornado.websocket
from coincurve import verify_signature

from yadacoin.core.config import Config
from yadacoin.http.base import BaseHandler

# Store connections
connections = {}
groups = {}


class MainHandler(BaseHandler):
    async def get(self):
        self.render("peerjsclient.html")


class PeerWebSocketHandler(tornado.websocket.WebSocketHandler):
    async def open(self):
        print("WebSocket opened")
        config = Config()
        peer_id = None
        i = 0
        while i < 3:
            try:
                peer_id = base64.b64decode(
                    self.get_argument("id") + "".join(["=" for x in range(i)])
                )
                break
            except:
                pass
            i += 1
        if peer_id is None:
            raise Exception("Error parsing identity")
        identity = json.loads(peer_id)
        username = identity["username"]
        username_signature = identity["username_signature"]
        public_key = identity["public_key"]

        try:
            result = verify_signature(
                base64.b64decode(username_signature),
                username.encode(),
                bytes.fromhex(public_key),
            )
            if not result:
                raise Exception("Error verifying signature.")
        except:
            raise
        sum = await config.BU.get_masternode_fees_paid_sum(
            public_key, config.LatestBlock.block.index - 144 * 7 * 4
        )
        if (
            sum < config.masternode_fee_minimum
        ):  # TODO: maybe enable a config value for free mode or white listing
            self.write_message(
                json.dumps(
                    {"type": "ERROR", "payload": {"msg": "Masternode fees not paid"}}
                )
            )
            return
        # Process peer_id or store it in a connection dictionary
        self.peer_id = self.get_argument("id")
        connections[self.peer_id] = self  # Store WebSocket connection
        self.write_message(json.dumps({"type": "OPEN", "src": self.peer_id}))

    def on_message(self, message):
        try:
            data = json.loads(message)
            print("Received message:", data)
            message_type = data.get("type")

            if message_type == "JOIN_GROUP":
                group = data.get("group")
                if group:
                    if group not in groups:
                        groups[group] = []
                    else:
                        for conn in groups[group]:
                            self.write(
                                conn.peer_id
                            )  # after the peer id is received by the browser, it sends an offer
                    groups[group].append(self)

            if message_type in ["OFFER", "CANDIDATE", "ANSWER"]:
                # Forward offer to the target peer
                to_peer = data.get("dst")
                data["src"] = self.peer_id
                if to_peer in connections:
                    connections[to_peer].write_message(json.dumps(data))
        except json.JSONDecodeError:
            self.write_message(json.dumps({"type": "ERROR", "message": "Invalid JSON"}))

    def on_close(self):
        print("WebSocket closed")

    def check_origin(self, origin):
        return True


PEERJS_HANDLERS = [
    (r"/peerjsclient", MainHandler),
    (
        r"/peerjsclient/(.*)",
        tornado.web.StaticFileHandler,
        {"path": Path(__file__).resolve().parents[2] / "static" / "peerjsclient"},
    ),
    (r"/peerjs", PeerWebSocketHandler),
]
