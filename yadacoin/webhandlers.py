"""
Handlers required by the web operations
"""


from yadacoin.basehandlers import BaseHandler


class HomeHandler(BaseHandler):

    async def get(self):
        """
        :return:
        """
        self.render("index.html", yadacoin=self.yadacoin_vars)


WEB_HANDLERS = [(r'/', HomeHandler)]
