import tornado
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application, url


class WebCamHandler(RequestHandler):

    @tornado.web.authenticated
    def get(self):
        self.render("webcams.html", myvalue="FooBar")


class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        return self.get_secure_cookie("user")


class MainHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        name = tornado.escape.xhtml_escape(self.current_user)
        self.write("Hello, " + name)


class LoginHandler(BaseHandler):

    def get(self):
        self.write('<html><body><form action="/login" method="post">'
                   'Name: <input type="text" name="name">'
                   '<input type="submit" value="Sign in">'
                   '</form></body></html>')

    def post(self):
        self.set_secure_cookie("user", self.get_argument("name"))
        self.redirect("/")


def make_app():
    return Application([
        url(r"/", MainHandler),
        url(r"/webcams", WebCamHandler),
        url(r"/login", LoginHandler),
    ],
        cookie_secret="PANOPTES_SUPER_SECRET",
        template_path="admin/static/templates",
        login_url="/login",
        debug=True,
    )


def main():

    app = make_app()
    app.listen(8880)
    IOLoop.current().start()

if __name__ == '__main__':
    main()
