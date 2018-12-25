from socketIO_client import SocketIO, BaseNamespace
from config import Config
from mongo import Mongo
from peers import Peers
from blockchainutils import BU
from transactionutils import TU
from transaction import Transaction, TransactionFactory, Output, NotEnoughMoneyException


class ChatNamespace(BaseNamespace):
    def on_error(self, event, *args):
        print 'error'

class Faucet(object):
    @classmethod
    def run(cls, config):
        mongo = Mongo(config)
        used_inputs = []
        new_inputs = []
        for x in mongo.site_db.faucet.find({'active': True}):
            balance = BU.get_wallet_balance(x['address'])
            if balance >= 25:
                mongo.site_db.faucet.update({'_id': x['_id']}, {'active': False, 'address': x['address']})

                continue
            last_id_in_blockchain = x.get('last_id')
            if last_id_in_blockchain and not mongo.db.blocks.find({'transactions.id': last_id_in_blockchain}).count():

                continue

            try:
                transaction = TransactionFactory(
                    fee=0.01,
                    public_key=config.public_key,
                    private_key=config.private_key,
                    outputs=[
                        Output(to=x['address'], value=5)
                    ]
                )
            except NotEnoughMoneyException as e:
                print "not enough money yet"
                return
            except Exception as e:
                print x
            try:
                transaction.transaction.verify()
            except:
                mongo.site_db.failed_faucet_transactions.insert(transaction.transaction.to_dict())
                print 'faucet transaction failed'
            TU.save(transaction.transaction)
            x['last_id'] = transaction.transaction.transaction_signature
            mongo.site_db.faucet.update({'_id': x['_id']}, x)
            print 'saved. sending...', x['address']
            for peer in Peers.peers:
                try:
                    socketIO = SocketIO(peer.host, peer.port, wait_for_connection=False)
                    chat_namespace = socketIO.define(ChatNamespace, '/chat')
                    chat_namespace.emit('newtransaction', transaction.transaction.to_dict())
                    socketIO.disconnect()
                except Exception as e:
                    print e