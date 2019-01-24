import endpoints
import socketio
from flask import request, Flask
from flask_cors import CORS
from graph import Graph
from peers import Peers, Peer
from config import Config
from gevent import pywsgi

class Serve(object):
    def __init__(self, config):
        self.app = Flask(__name__)
        self.app.config['yada_config'] = config
        self.app.debug = True
        self.app.secret_key = '23ljk2l9a08sd7f09as87df09as87df3k4j'
        CORS(self.app, supports_credentials=True)
        endpoints.BaseGraphView.get_base_graph = self.get_base_graph
        self.app.add_url_rule('/transaction', view_func=endpoints.TransactionView.as_view('transaction'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-info', view_func=endpoints.GraphView.as_view('graph'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-sent-friend-requests', view_func=endpoints.GraphSentFriendRequestsView.as_view('graphsentfriendrequests'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-friend-requests', view_func=endpoints.GraphFriendRequestsView.as_view('graphfriendrequests'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-friends', view_func=endpoints.GraphFriendsView.as_view('graphfriends'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-posts', view_func=endpoints.GraphPostsView.as_view('graphposts'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-messages', view_func=endpoints.GraphMessagesView.as_view('graphmessages'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-new-messages', view_func=endpoints.GraphNewMessagesView.as_view('graphnewmessages'), methods=['GET', 'POST'])
        self.app.add_url_rule('/wallet', view_func=endpoints.WalletView.as_view('wallet'))
        self.app.add_url_rule('/faucet', view_func=endpoints.FaucetView.as_view('faucet'))
        self.app.add_url_rule('/pool', view_func=endpoints.MiningPoolView.as_view('pool'))
        self.app.add_url_rule('/pool-submit', view_func=endpoints.MiningPoolSubmitView.as_view('poolsubmit'), methods=['GET', 'POST'])
        self.app.add_url_rule('/pool-explorer', view_func=endpoints.MiningPoolExplorerView.as_view('pool-explorer'))
        self.app.add_url_rule('/get-block', view_func=endpoints.GetBlockByHashView.as_view('get-block'), methods=['GET'])
        self.app.add_url_rule('/getblockheight', view_func=endpoints.GetBlockHeightView.as_view('get-block-height'))
        self.app.add_url_rule('/newtransaction', view_func=endpoints.NewTransactionView.as_view('new-transaction'), methods=['POST'])
        self.app.add_url_rule('/newblock', view_func=endpoints.NewBlockView.as_view('new-block'), methods=['POST'])
        self.app.add_url_rule('/get-blocks', view_func=endpoints.GetBlocksView.as_view('get-blocks-range'))
        self.app.add_url_rule('/create-raw-transaction', view_func=endpoints.CreateRawTransactionView.as_view('create-raw-transaction'), methods=['POST'])
        self.app.add_url_rule('/sign-raw-transaction', view_func=endpoints.SignRawTransactionView.as_view('sign-raw-transaction'), methods=['POST'])
        self.app.add_url_rule('/generate-wallet', view_func=endpoints.GenerateWalletView.as_view('generate-wallet'))
        self.app.add_url_rule('/generate-child-wallet', view_func=endpoints.GenerateChildWalletView.as_view('generate-child-wallet'), methods=['POST'])
        self.app.add_url_rule('/explorer-search', view_func=endpoints.ExplorerSearchView.as_view('explorer-search'))
        self.app.add_url_rule('/get-latest-block', view_func=endpoints.GetLatestBlockView.as_view('get-latest-block'))
        self.app.add_url_rule('/register', view_func=endpoints.RegisterView.as_view('register'))
        self.app.add_url_rule('/create-relationship', view_func=endpoints.CreateRelationshipView.as_view('create-relationship'), methods=['POST'])
        self.app.add_url_rule('/post-fastgraph-transaction', view_func=endpoints.PostFastGraphView.as_view('post-fastgraph-transaction'), methods=['POST'])
        self.app.add_url_rule('/yada_config.json', view_func=endpoints.GetYadaConfigView.as_view('yada-config'))
        self.app.add_url_rule('/login', view_func=endpoints.GetSiginCodeView.as_view('login'))
        self.app.add_url_rule('/', view_func=endpoints.HomeView.as_view('home'))
        self.app.add_url_rule('/search', view_func=endpoints.SearchView.as_view('search'))
        self.app.add_url_rule('/react', view_func=endpoints.ReactView.as_view('react'), methods=['POST'])
        self.app.add_url_rule('/get-reacts', view_func=endpoints.GetReactsView.as_view('get-reacts'), methods=['POST'])
        self.app.add_url_rule('/get-reacts-detail', view_func=endpoints.GetReactsDetailView.as_view('get-reacts-detail'), methods=['POST'])
        self.app.add_url_rule('/comment-react', view_func=endpoints.CommentReactView.as_view('comment-react'), methods=['POST'])
        self.app.add_url_rule('/get-comment-reacts', view_func=endpoints.GetCommentReactsView.as_view('get-comment-reacts'), methods=['POST'])
        self.app.add_url_rule('/get-comment-reacts-detail', view_func=endpoints.GetCommentReactsDetailView.as_view('get-comment-reacts-detail'), methods=['POST'])
        self.app.add_url_rule('/comment', view_func=endpoints.CommentView.as_view('comment'), methods=['POST'])
        self.app.add_url_rule('/get-comments', view_func=endpoints.GetCommentsView.as_view('get-comments'), methods=['POST'])

        sio = socketio.Server(async_mode='gevent')
        sio.register_namespace(endpoints.BlockchainSocketServer('/chat'))
        socketio.Middleware(sio, self.app)

    def get_base_graph(self):
        bulletin_secret = request.args.get('bulletin_secret').replace(' ', '+')
        graph = Graph(self.app.config['yada_config'], bulletin_secret)
        return graph
    
