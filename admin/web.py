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
    """
    BaseHandler is inherited by all Handlers and is responsible for any
    global operations. Provides the `db` property and the `get_current_user`
    """
    @property
    def db(self):
        """ Simple property to access the DB easier """
        return self.settings['db']

    @gen.coroutine
    def get_current_user(self):
        """
        Looks for a cookie that shows we have been logged in. If cookie
        is found, attempt to look up user info in the database
        """
        # Get username from cookie
        username = self.get_secure_cookie("username")
        if not username: return None

        # Look up user data
        user_data = yield self.db.find_one({'username': username})
        if not user_data: return None

        return user_data


class MainHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        username = tornado.escape.xhtml_escape(self.current_user)
        self.render("main.html", username=username)


class WebCamHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.render("webcams.html", myvalue="FooBar")


class AuthLoginHandler(BaseHandler, tornado.auth.GoogleMixin):
    """
    Login and authenticate the user and perform any actions for startup
    """
    @gen.coroutine
    def get(self):
        if self.get_argument("openid.mode", None):
            self.get_authenticated_user(self._on_auth)
            return
        self.authenticate_redirect()

    def _on_auth(self, user):
        if not user:
            raise tornado.web.HTTPError(500, "Google auth failed")
        author = self.db.get("SELECT * FROM authors WHERE email = %s",
                             user["email"])
        if not author:
            # Auto-create first author
            any_author = self.db.get("SELECT * FROM authors LIMIT 1")
            if not any_author:
                author_id = self.db.execute(
                    "INSERT INTO authors (email,name) VALUES (%s,%s)",
                    user["email"], user["name"])
            else:
                self.redirect("/")
                return
        else:
            author_id = author["id"]
        self.set_secure_cookie("blogdemo_user", str(author_id))
        self.redirect(self.get_argument("next", "/"))


class AuthLogoutHandler(BaseHandler):
    """
    Operations run when the user logs out.
    """
    def get(self):
        self.clear_cookie("username")
        self.redirect("/")


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
