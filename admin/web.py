import tornado
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application, url

class WebCamHandler(RequestHandler):
    def get(self):
        self.render("webcams.html", myvalue="FooBar")


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")

class MainHandler(BaseHandler):
    def get(self):
        if not self.current_user:
            self.redirect("/login")
            return
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
        url(r"/", WebCamHandler),
        ],
            cookie_secret="PANOPTES_SUPER_SECRET",
            template_path="admin/static/templates",
            debug=True,
        )

def main():

    app = make_app()
    app.listen(8880)
    IOLoop.current().start()

if __name__ == '__main__':
    main()
