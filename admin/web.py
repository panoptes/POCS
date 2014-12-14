import os.path
import uuid
import logging
import tornado.auth
import tornado.escape
import tornado.ioloop
import tornado.web
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
            (r"/login", AuthLoginHandler),
            (r"/logout", AuthLogoutHandler),
            (r"/webcams", WebCamHandler),
        ]

        # Create a global connection to Mongo
        db = motor.MotorClient().panoptes

        settings = dict(
            cookie_secret="PANOPTES_SUPER_DOOPER_SECRET",
            login_url="/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            db=db,
            debug=options.debug,
        )

        super(Application, self).__init__(handlers, **settings)


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        """ Simple property to access the DB easier """
        return self.settings['db']


    @gen.coroutine
    def get_current_user(self):
        username = self.get_secure_cookie("username")
        if not username: return None

        user_data = yield db.test_collection.find_one({'username': username})
        return user_data


class MainHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        name = tornado.escape.xhtml_escape(self.current_user)
        self.render("main.html", name=name)


class WebCamHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.render("webcams.html", myvalue="FooBar")


class AuthLoginHandler(BaseHandler, tornado.auth.GoogleMixin):

    @gen.coroutine
    def get(self):
        if self.get_argument("openid.mode", None):
            user = yield self.get_authenticated_user()
            self.set_secure_cookie("user",
                                   tornado.escape.json_encode(user))
            self.redirect("/")
            return
        self.authenticate_redirect(ax_attrs=["name"])


class AuthLogoutHandler(BaseHandler):

    def get(self):
        self.clear_cookie("user")
        self.write("You are now logged out")


def main():
    tornado.options.parse_command_line()
    app = tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/login", AuthLoginHandler),
            (r"/logout", AuthLogoutHandler),
            (r"/webcams", WebCamHandler),
        ],
        cookie_secret="PANOPTES_SUPER_DOOPER_SECRET",
        login_url="/login",
        template_path=os.path.join(os.path.dirname(__file__), "templates"),
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        xsrf_cookies=True,
        debug=options.debug,
    )
    app.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()
