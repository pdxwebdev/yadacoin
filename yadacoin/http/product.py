"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.

This software is licensed under YOSL v1.1 – for personal and research use only.
NO commercial use, NO blockchain forks, and NO branding use without permission.

For commercial license inquiries, contact: info@yadacoin.io

Full license terms: see LICENSE.txt in this repository.
"""

from yadacoin.http.base import BaseHandler


class ProductHandler(BaseHandler):
    async def get(self):
        product = self.config.products[self.get_query_argument("id")]
        return self.render_as_json({"product": product})


PRODUCT_HANDLERS = [
    (r"/product", ProductHandler),
]
