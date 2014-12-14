from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application, url

class HelloHandler(RequestHandler):
    def get(self):
		loader = template.Loader("/")
		print loader.load("test.html").generate(myvalue="XXX")
        self.write("<img src='/static/webcams/pier_west.png' />")

def make_app():
    return Application([
        url(r"/", HelloHandler),
        ])

def main():
    app = make_app()
    app.listen(8888)
    IOLoop.current().start()

if __name__ == '__main__':
    main()
