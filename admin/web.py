import os.path
import uuid
import logging
import tornado.auth
import tornado.escape
import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.options as options

from tornado.concurrent import Future
from tornado import gen
from tornado.options import define, options

import motor  # MongoDB Async

define("port", default=8888, help="port", type=int)
define("db", default="panoptes", help="Name of the Mongo DB to use")
define("collection", default="admin", help="Name of the Mongo Collection to use")
define("debug", default=False, help="debug mode")


class Application(tornado.web.Application):

    """ The main Application entry for our PANOPTES admin interface """

    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            (r"/webcams", WebCamHandler),
        ]

        # Create a global connection to Mongo
        db = motor.MotorClient().panoptes

        settings = dict(
            cookie_secret="PANOPTES_SUPER_DOOPER_SECRET",
            login_url="/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            # xsrf_cookies=True,
            db=db,
            debug=options.debug,
            site_title="PANOPTES",
        )

        super(Application, self).__init__(handlers, **settings)


class BaseHandler(tornado.web.RequestHandler):

    """
    BaseHandler is inherited by all Handlers and is responsible for any
    global operations. Provides the `db` property and the `get_current_user`
    """
    @property
    def db(self):
        """ Simple property to access the DB easier """
        return self.settings['db']

    def get_current_user(self):
        """
        Looks for a cookie that shows we have been logged in. If cookie
        is found, attempt to look up user info in the database
        """
        # Get username from cookie
        username = self.get_secure_cookie("username")
        print("username: {}".format(username))
        if not username:
            return None

        # Look up user data
        # user_data = yield self.db.find_one({'username': username})
        # print("user_data: {}".format(user_data))
        # if user_data.result() is None:
        #     return None

        return username


class MainHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        user_data = self.current_user
        self.render("main.html", user_data=user_data)


class WebCamHandler(BaseHandler):

    def get(self):
        self.render("webcams.html", myvalue="42")


class LoginHandler(BaseHandler):

    """
    Login and authenticate the user and perform any actions for startup
    """
    def get(self):
        self.render("login.html")

    def post(self):
        self.set_secure_cookie("username", self.get_argument("username"))
        self.redirect("/")


class LogoutHandler(BaseHandler):

    """
    Operations run when the user logs out.
    """

    def get(self):
        print("Removing cookie")
        self.clear_cookie("username")
        self.redirect("/")


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()
