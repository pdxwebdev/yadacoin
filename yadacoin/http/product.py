from yadacoin.http.base import BaseHandler


class ProductHandler(BaseHandler):

    async def get(self):
        product = self.config.products[self.get_query_argument('id')]
        return self.render_as_json({'product': product})

PRODUCT_HANDLERS = [
    (r'/product', ProductHandler),
]
