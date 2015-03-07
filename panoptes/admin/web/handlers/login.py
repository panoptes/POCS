import tornado.auth
import tornado.escape
import tornado.web

import panoptes.admin.web.handlers.base as handlers

class LoginHandler(handlers.BaseHandler):

    """
    Login and authenticate the user and perform any actions for startup
    """

    def get(self):
        self.render("login.html")

    def post(self):
        email = tornado.escape.to_unicode(self.get_argument("email"))
        self.set_secure_cookie("email", email)
        self.redirect("/")


class LogoutHandler(handlers.BaseHandler):

    """
    Operations run when the user logs out.
    """

    def get(self):
        self.clear_cookie("email")
        self.redirect("/")