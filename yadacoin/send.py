# TODO: Not converted yet

from socketIO_client import SocketIO, BaseNamespace

from yadacoin.peers import Peers
from yadacoin.transaction import TransactionFactory, Output, NotEnoughMoneyException
from yadacoin.transactionutils import TU
from yadacoin.blockchainutils import BU


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print('error')


class Send(object):
    @classmethod
    def run(cls, config, mongo, to, value):
        Peers.init(config, mongo, config.network)

        try:
            transaction = TransactionFactory(
                block_height=config.BU.get_latest_block()['index'],
                fee=0.01,
                public_key=config.public_key,
                private_key=config.private_key,
                outputs=[
                    {'to': to, 'value': value}
                ]
            )
        except NotEnoughMoneyException as e:
            print("not enough money yet")
            return
        except:
            raise
        try:
            transaction.transaction.verify()
        except:
            print('transaction failed')
        TU.save(config, mongo, transaction.transaction)
        print('Transaction generated successfully. Sending:', value, 'To:', to)
        for peer in Peers.peers:
            try:
                with SocketIO(peer.host, peer.port, ChatNamespace, wait_for_connection=False) as socketIO:
                    chat_namespace = socketIO.define(ChatNamespace, '/chat')
                    chat_namespace.emit('newtransaction', transaction.transaction.to_dict())
                    socketIO.disconnect()
                    print('Sent to:', peer.host, peer.port)
            except Exception as e:
                print(e)
