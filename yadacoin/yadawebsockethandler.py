"""
Webb socket handler for yadacoin
"""

import socketio

SIO = socketio.AsyncServer(async_mode='tornado')


@SIO.on('connect', namespace='/chat')
async def chat_connect(sid, environ):
    print('Client connected')
    await SIO.emit('my response', {'data': 'Connected', 'count': 0}, room=sid,
                   namespace='/chat')


@SIO.on('disconnect request', namespace='/chat')
async def disconnect_request(sid):
    print('Disconnect request')
    await SIO.disconnect(sid, namespace='/chat')


@SIO.on('disconnect', namespace='/chat')
def chat_disconnect(sid):
    print('Client disconnected')


@SIO.on('newtransaction', namespace='/chat')
async def newtransaction(sid, message):
    print("newtransaction", sid, message)
