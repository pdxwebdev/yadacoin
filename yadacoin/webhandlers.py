"""
Handlers required by the web operations
"""


from yadacoin.basehandlers import BaseHandler
from yadacoin.graphutils import GraphUtils as GU
from yadacoin.blockchainutils import BU


class HomeHandler(BaseHandler):

    async def get(self):
        """
        :return:
        """
        self.render("index.html", yadacoin=self.yadacoin_vars)


class AuthenticatedHandler(BaseHandler):
    async def get(self):
        config = self.config
        rid = self.get_query_argument('rid')
        if not rid:
            return '{"error": "rid not in query params"}', 400

        txn_id = self.get_query_argument('id')
        
        bulletin_secret = self.get_query_argument('bulletin_secret')
        if not bulletin_secret:
            return '{"error": "bulletin_secret not in query params"}', 400

        self.render_as_json({
            'authenticated': False
        })
        return True
        result = GU().verify_message(
            rid,
            self.session.get('siginin_code'),
            config.public_key,
            txn_id.replace(' ', '+'))
        print(result)
        if result[1]:
            session['rid'] = rid
            username_txns = [x for x in BU().search_rid(rid)]
            session['username'] = username_txns[0]['relationship']['their_username']
            return self.render_as_json({
                'authenticated': True
            })
        
        return self.render_as_json({
            'authenticated': False
        })

class LogoutHandler(BaseHandler):
    def get(self):
        session.pop('username', None)
        session.pop('rid', None)
        self.render_as_json({
            'authenticated': False
        })


WEB_HANDLERS = [
    (r'/', HomeHandler),
    (r'/authenticated', AuthenticatedHandler),
    (r'/logout', LogoutHandler),
]
