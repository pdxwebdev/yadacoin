from flask import request, Flask
from flask_cors import CORS
from flask_socketio import SocketIO

from yadacoin import endpoints_old
from yadacoin.graph import Graph


class Serve(object):
    def __init__(self, config, mongo, app):
        self.app = app
        self.app.config['yada_config'] = config
        self.app.config['yada_mongo'] = mongo
        self.app.debug = True
        self.app.secret_key = '23ljk2l9a08sd7f09as87df09as87df3k4j'
        CORS(self.app, supports_credentials=True)
        endpoints_old.BaseGraphView.get_base_graph = self.get_base_graph

        self.app.add_url_rule('/transaction', view_func=endpoints_old.TransactionView.as_view('transaction'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-info', view_func=endpoints_old.GraphView.as_view('graph'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-sent-friend-requests', view_func=endpoints_old.GraphSentFriendRequestsView.as_view('graphsentfriendrequests'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-friend-requests', view_func=endpoints_old.GraphFriendRequestsView.as_view('graphfriendrequests'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-friends', view_func=endpoints_old.GraphFriendsView.as_view('graphfriends'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-posts', view_func=endpoints_old.GraphPostsView.as_view('graphposts'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-messages', view_func=endpoints_old.GraphMessagesView.as_view('graphmessages'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-new-messages', view_func=endpoints_old.GraphNewMessagesView.as_view('graphnewmessages'), methods=['GET', 'POST'])
        self.app.add_url_rule('/get-graph-comments', view_func=endpoints_old.GraphCommentsView.as_view('get-comments'), methods=['POST'])
        self.app.add_url_rule('/get-graph-reacts', view_func=endpoints_old.GraphReactsView.as_view('get-reacts'), methods=['POST'])
        self.app.add_url_rule('/get-graph-wallet', view_func=endpoints_old.RidWalletView.as_view('get-wallet'))
        self.app.add_url_rule('/wallet', view_func=endpoints_old.WalletView.as_view('wallet'))
        self.app.add_url_rule('/faucet', view_func=endpoints_old.FaucetView.as_view('faucet'))
        # P
        self.app.add_url_rule('/pool', view_func=endpoints_old.MiningPoolView.as_view('pool'))
        # P
        self.app.add_url_rule('/pool-submit', view_func=endpoints_old.MiningPoolSubmitView.as_view('poolsubmit'), methods=['GET', 'POST'])
        # P
        self.app.add_url_rule('/pool-explorer', view_func=endpoints_old.MiningPoolExplorerView.as_view('pool-explorer'))

        # C
        self.app.add_url_rule('/get-block', view_func=endpoints_old.GetBlockByHashView.as_view('get-block'), methods=['GET'])
        self.app.add_url_rule('/getblockheight', view_func=endpoints_old.GetBlockHeightView.as_view('get-block-height'))


        self.app.add_url_rule('/newtransaction', view_func=endpoints_old.NewTransactionView.as_view('new-transaction'), methods=['POST'])

        self.app.add_url_rule('/newblock', view_func=endpoints_old.NewBlockView.as_view('new-block'), methods=['POST'])
        # C
        self.app.add_url_rule('/get-blocks', view_func=endpoints_old.GetBlocksView.as_view('get-blocks-range'))


        self.app.add_url_rule('/create-raw-transaction', view_func=endpoints_old.CreateRawTransactionView.as_view('create-raw-transaction'), methods=['POST'])
        self.app.add_url_rule('/sign-raw-transaction', view_func=endpoints_old.SignRawTransactionView.as_view('sign-raw-transaction'), methods=['POST'])
        self.app.add_url_rule('/generate-wallet', view_func=endpoints_old.GenerateWalletView.as_view('generate-wallet'))
        self.app.add_url_rule('/generate-child-wallet', view_func=endpoints_old.GenerateChildWalletView.as_view('generate-child-wallet'), methods=['POST'])
        self.app.add_url_rule('/explorer-search', view_func=endpoints_old.ExplorerSearchView.as_view('explorer-search'))
        # C
        self.app.add_url_rule('/get-latest-block', view_func=endpoints_old.GetLatestBlockView.as_view('get-latest-block'))


        self.app.add_url_rule('/register', view_func=endpoints_old.RegisterView.as_view('register'))
        self.app.add_url_rule('/create-relationship', view_func=endpoints_old.CreateRelationshipView.as_view('create-relationship'), methods=['POST'])
        self.app.add_url_rule('/post-fastgraph-transaction', view_func=endpoints_old.PostFastGraphView.as_view('post-fastgraph-transaction'), methods=['POST'])
        self.app.add_url_rule('/yada_config.json', view_func=endpoints_old.GetYadaConfigView.as_view('yada-config'))
        self.app.add_url_rule('/login', view_func=endpoints_old.GetSiginCodeView.as_view('login'))
        #
        self.app.add_url_rule('/', view_func=endpoints_old.HomeView.as_view('home'))
        self.app.add_url_rule('/search', view_func=endpoints_old.SearchView.as_view('search'))
        self.app.add_url_rule('/react', view_func=endpoints_old.ReactView.as_view('react'), methods=['POST'])
        self.app.add_url_rule('/comment-react', view_func=endpoints_old.CommentReactView.as_view('comment-react'), methods=['POST'])
        self.app.add_url_rule('/get-comment-reacts', view_func=endpoints_old.GetCommentReactsView.as_view('get-comment-reacts'), methods=['POST'])
        self.app.add_url_rule('/get-comment-reacts-detail', view_func=endpoints_old.GetCommentReactsDetailView.as_view('get-comment-reacts-detail'), methods=['POST'])
        self.app.add_url_rule('/comment', view_func=endpoints_old.CommentView.as_view('comment'), methods=['POST'])


        self.socketio = SocketIO(self.app)
        self.socketio.on_namespace(endpoints_old.BlockchainSocketServer('/chat'))

    def get_base_graph(self):
        bulletin_secret = request.args.get('bulletin_secret').replace(' ', '+')
        if request.json:
            ids = request.json.get('ids')
        else:
            ids = []
        graph = Graph(self.app.config['yada_config'], self.app.config['yada_mongo'], bulletin_secret, ids)
        return graph

