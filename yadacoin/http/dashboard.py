from yadacoin.http.base import BaseHandler

class DashboardHandler(BaseHandler):
    def get(self):
        self.redirect("/yadacoinstatic/dashboard/index.html")

DASHBOARD_HANDLERS = [
    (r"/dashboard", DashboardHandler),
]