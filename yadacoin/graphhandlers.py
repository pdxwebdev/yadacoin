"""
Handlers required by the graph operations
"""


from yadacoin.basehandlers import BaseHandler
from yadacoin.blockchainutils import BU


class GetGraphInfoHandler(BaseHandler):

    async def get(self):
        return self.render_as_json("TODO: Implement")


GRAPH_HANDLERS = [(r'/get-graph-info', GetGraphInfoHandler)]
