"""
Crude websocket client for tests
"""


#!/usr/bin/env python
# -*- coding: utf-8 -*-

from tornado.options import define, options
# rewriten using the https://python-socketio.readthedocs.io/en/latest/client.html for consistency
from socketio import Client, ClientNamespace

from time import sleep


__version__ = '0.0.1'


DEFAULT_PORT = 8000


class ChatNamespace(ClientNamespace):

    def on_connect(self):
        print('/Chat connected')
        pass

    def on_disconnect(self):
        pass

    def on_peers(self, data):
        print("peers", data)


if __name__ == "__main__":

    define("ip", default='127.0.0.1', help="Server IP to connect to, default 127.0.0.1")
    define("verbose", default=False, help="verbose")
    options.parse_command_line(final=False)  # final False is required or it activates the client logger.

    if options.ip != '127.0.0.1':
        URL = "ws://{}:{}/chat/".format(options.ip, DEFAULT_PORT)
        print("Using {}".format(URL))

    # See options https://python-socketio.readthedocs.io/en/latest/api.html
    sio = Client(logger=False)
    sio.register_namespace(ChatNamespace('/chat'))
    sio.connect('http://{}:{}'.format(options.ip, DEFAULT_PORT), namespaces=['/chat'])

    sleep(1)  # not needed
    # We have to id ourselve first of all
    sio.emit('hello', data={"version": 2, "ip":"127.0.0.1", "port": DEFAULT_PORT}, namespace="/chat")

    # ask the peer active list
    sio.emit('get_peers', data={}, namespace="/chat")

    # send the peer our list
    peers = {'num_peers': 3, 'peers': [{'host': '34.237.46.10', 'port': 8000, 'bulletin_secret': None, 'is_me': False},
                                       {'host': '116.203.24.126', 'port': 8000, 'bulletin_secret': None, 'is_me': False},
                                       {'host': '178.32.96.27', 'port': 8000, 'bulletin_secret': None, 'is_me': False}]}

    sio.emit('peers', data=peers, namespace="/chat")

    # sio.wait()
    sleep(10)
    sio.disconnect()
