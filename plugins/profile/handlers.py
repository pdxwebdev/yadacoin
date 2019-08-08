"""
Handlers required by the web operations
"""
import os
import json
from tornado.web import Application, StaticFileHandler
from yadacoin.basehandlers import BaseHandler

class BaseWebHandler(BaseHandler):

    def prepare(self):

        if self.request.protocol == 'http' and self.config.ssl:
            self.redirect('https://' + self.request.host + self.request.uri, permanent=False)

    def get_template_path(self):
        return os.path.join(os.path.dirname(__file__), 'templates')

class AdminHandler(BaseWebHandler):

    async def get(self):
        """
        :return:
        """
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif:
            return self.redirect('/auth')
        if key_or_wif.decode() not in [self.config.wif, self.config.private_key]:
            return self.redirect('/auth')
        profile_data = self.config.mongo.site_db.profile.find_one({'key': self.config.private_key})
        self.render(
            "index.html",
            remote_ip=self.request.remote_ip,
            peers=self.config.peers
        )

class EditProcessHandler(BaseWebHandler):

    async def get(self):
        """
        :return:
        """
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif:
            return self.redirect('/auth')
        if key_or_wif.decode() not in [self.config.wif, self.config.private_key]:
            return self.redirect('/auth')
        
        self.render(
            "edit-process.html"
        )


class ProfileHandler(BaseWebHandler):

    async def get(self):
        """
        :return:
        """
        profile_data = self.config.mongo.site_db.profile.find_one({'key': self.config.private_key})
        self.render(
            "profile.html",
            remote_ip=self.request.remote_ip,
            profile={
                'avatar': '',
                'about_me': profile_data.get('about_me')
            },
            posts=[]
        )


class ProfileEditHandler(BaseWebHandler):

    async def get(self):
        """
        :return:
        """
        key_or_wif = self.get_secure_cookie("key_or_wif")
        if not key_or_wif:
            return self.redirect('/auth')
        if key_or_wif.decode() not in [self.config.wif, self.config.private_key]:
            return self.redirect('/auth')

        profile_data = self.config.mongo.site_db.profile.find_one({'key': self.get_secure_cookie('key_or_wif').decode()})

        return self.render(
            "edit.html",
            editordata=profile_data.get('about_me')
        )
    
    async def post(self):
        if self.get_secure_cookie('key_or_wif').decode() in [self.config.wif, self.config.private_key]:
            editor_data = self.get_body_argument('editordata')
            self.config.mongo.site_db.profile.update_one({'key': self.config.private_key}, {'$set': {'about_me': editor_data}}, upsert=True)
            return self.redirect('/admin')


class ProfileAuthHandler(BaseWebHandler):

    async def get(self):
        """
        :return:
        """
        self.render(
            "auth.html"
        )
    
    async def post(self):
        try:
            key_or_wif = self.get_body_argument('key_or_wif')
        except:
            key_or_wif = json.loads(self.request.body.decode()).get('key_or_wif')
        if key_or_wif in [self.config.wif, self.config.private_key]:
            self.set_secure_cookie("key_or_wif", key_or_wif)
            
            self.write({'status': 'ok'})
            self.set_header('Content-Type', 'application/json')
            return self.finish()
        else:
            self.write({'status': 'error', 'message': 'Wrong private key or WIF. You must provide the private key or WIF of the currently running server.'})
            self.set_header('Content-Type', 'application/json')
            return self.finish()

class LogoutHandler(BaseWebHandler):

    async def get(self):
        """
        :return:
        """
        self.set_secure_cookie("key_or_wif", '')
        return self.redirect('/auth')


HANDLERS = [
    (r'/admin', AdminHandler),
    (r'/profile', ProfileHandler),
    (r'/profile/edit', ProfileEditHandler),
    (r'/auth', ProfileAuthHandler),
    (r'/logout', LogoutHandler),
    (r'/edit-process', EditProcessHandler),
]
