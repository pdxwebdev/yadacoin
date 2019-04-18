#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Crude websocket pool client for tests
Real one should be async or threaded
"""


from tornado.options import define, options
from socketio import Client, ClientNamespace

from time import sleep


__version__ = '0.0.2'


DEFAULT_PORT = 8000


class PoolNamespace(ClientNamespace):

    def on_connect(self):
        print('/Pool connected')
        self.emit('register',
                  data={"version": 2, "worker": "demo", "address": options.address, "type": "demo_miner"},
                  namespace="/pool")

        pass

    def on_disconnect(self):
        print('/Pool disconnected')
        self.client.connected  =False
        pass

    def on_header(self, data):
        print("header", data)


def mine():
    global sio
    while sio.connected:
        sleep(10)
        sio.emit('nonce', data="fakenonce", namespace="/pool")


if __name__ == "__main__":

    define("ip", default='127.0.0.1', help="Pool IP to connect to, default 127.0.0.1")
    define("address", help="Yadacoin address to mine to")
    define("verbose", default=False, help="verbose")
    options.parse_command_line(final=False)  # final False is required or it activates the client logger.

    if options.ip != '127.0.0.1':
        URL = "http://{}:{}".format(options.ip, DEFAULT_PORT)
        print("Using {}".format(URL))

    # See options https://python-socketio.readthedocs.io/en/latest/api.html
    sio = Client(logger=False, reconnection=False)
    sio.register_namespace(PoolNamespace('/pool'))
    sio.connected = True
    sio.connect('http://{}:{}'.format(options.ip, DEFAULT_PORT), namespaces=['/pool'])
    sleep(10)
    # We have to id ourselve first of all
    mine()
    # sio.wait()
    sio.disconnect()
