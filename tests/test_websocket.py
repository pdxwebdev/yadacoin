"""
Crude websocket client for tests
"""


#!/usr/bin/env python
# -*- coding: utf-8 -*-

from tornado.options import define, options
from socketIO_client import SocketIO, BaseNamespace

# TODO: rewrite using the https://python-socketio.readthedocs.io/en/latest/client.html
# So not to require two different libs for client and server.

__version__ = '0.0.1'


DEFAULT_PORT = 8000


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print('error')


if __name__ == "__main__":

    define("ip", default='127.0.0.1', help="Server IP to connect to, default 127.0.0.1")
    define("verbose", default=False, help="verbose")
    options.parse_command_line()

    if options.ip != '127.0.0.1':
        URL = "ws://{}:{}/chat/".format(options.ip, DEFAULT_PORT)
        print("Using {}".format(URL))

    socketIO = SocketIO(options.ip, DEFAULT_PORT, wait_for_connection=False)
    chat_namespace = socketIO.define(ChatNamespace, '/chat')
    chat_namespace.emit('hello', {"version": 2, "ip":"127.0.0.1", "port":DEFAULT_PORT})
    # chat_namespace.emit('newtransaction', {"data":0})


    socketIO.disconnect()
