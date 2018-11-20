from socketIO_client import SocketIO, BaseNamespace
from config import Config
from mongo import Mongo
from peers import Peers
from transaction import TransactionFactory, Output, NotEnoughMoneyException
from transactionutils import TU


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

class Send(object):
    @classmethod
    def run(cls, to, value):
        Mongo.init()
        Peers.init()

        try:
            transaction = TransactionFactory(
                fee=0.01,
                public_key=Config.public_key,
                private_key=Config.private_key,
                outputs=[
                    Output(to=to, value=value)
                ]
            )
        except NotEnoughMoneyException as e:
            print "not enough money yet"
            return
        except:
            raise
        try:
            transaction.transaction.verify()
        except:
            print 'transaction failed'
        TU.save(transaction.transaction)
        print 'Transaction generated successfully. Sending:', value, 'To:', to 
        for peer in Peers.peers:
            try:
                socketIO = SocketIO(peer.host, peer.port, wait_for_connection=False)
                chat_namespace = socketIO.define(ChatNamespace, '/chat')
                chat_namespace.emit('newtransaction', transaction.transaction.to_dict())
                socketIO.disconnect()
                print 'Sent to:', peer.host, peer.port
            except Exception as e:
                print e