from tornado.ioloop import IOLoop
from tornado.web import RequestHandler, Application, url

class HelloHandler(RequestHandler):
    def get(self):
		loader = template.Loader("/var/panoptes/POCS/admin/static/templates")
		print loader.load("test.html").generate(myvalue="XXX")

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
