import os.path
import tornado.auth
import tornado.escape
import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.options as options

from tornado.concurrent import Future
from tornado import gen
from tornado.options import define, options

import sockjs.tornado

import uimodules

import pymongo
import bson.json_util as json_util

define("port", default=8888, help="port", type=int)
define("db", default="panoptes", help="Name of the Mongo DB to use")
define("collection", default="admin", help="Name of the Mongo Collection to use")
define("debug", default=False, help="debug mode")


class Application(tornado.web.Application):

    """ The main Application entry for our PANOPTES admin interface """

    def __init__(self):
        SensorRouter = sockjs.tornado.SockJSRouter(SensorSocket, '/sensors')

        handlers = [
            (r"/", MainHandler),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            (r"/webcams", WebCamHandler),
        ] + SensorRouter.urls

        # Create a global connection to Mongo
        db = pymongo.MongoClient().panoptes

        settings = dict(
            cookie_secret="PANOPTES_SUPER_DOOPER_SECRET",
            login_url="/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            db=db,
            debug=options.debug,
            site_title="PANOPTES",
            ui_modules=uimodules,
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
        # Get email from cookie
        email = tornado.escape.to_unicode(self.get_secure_cookie("email"))
        if not email:
            return None

        # Look up user data
        user_data = self.db.admin.find_one({'username': email})
        if user_data is None:
            return None

        return user_data


class MainHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        user_data = self.current_user

        self.render("main.html", user_data=user_data)


class SensorSocket(sockjs.tornado.SockJSConnection):

    """ Handler for the environmental sensors.

    Implemented with sockjs for websockets or long polling
    """

    # Class level variable
    observers = set()

    def on_open(self, info):
        # Add client to the clients list
        self.observers.add(self)

    def on_message(self, message):
        # Broadcast message
        self.broadcast(self.observers, message)

    def on_close(self):
        # Remove client from the clients list and broadcast leave message
        self.observers.remove(self)


class WebCamHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.render("webcams.html")


class LoginHandler(BaseHandler):

    """
    Login and authenticate the user and perform any actions for startup
    """

    def get(self):
        self.render("login.html")

    def post(self):
        email = tornado.escape.to_unicode(self.get_argument("email"))
        self.set_secure_cookie("email", email)
        self.redirect("/")


class LogoutHandler(BaseHandler):

    """
    Operations run when the user logs out.
    """

    def get(self):
        self.clear_cookie("email")
        self.redirect("/")


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()
