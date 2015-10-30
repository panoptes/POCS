import os
import os.path
import sys

import tornado.escape
import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.options

sys.path.append(os.getenv('POCS', os.path.join(os.path.dirname(__file__), "..")))

from ..utils import load_config, database

from .web import uimodules
from .web import handlers

tornado.options.define("port", default=8888, help="port", type=int)
tornado.options.define("debug", default=False, help="debug mode")


class WebAdmin(tornado.web.Application):

    """ The main Application entry for our PANOPTES admin interface """

    def __init__(self):

        db = database.PanMongo()

        config = load_config()

        app_handlers = [
            (r"/", handlers.MainHandler),
        ]
        settings = dict(
            cookie_secret="PANOPTES_SUPER_DOOPER_SECRET",
            template_path=os.path.join(os.path.dirname(__file__), "web/templates"),
            static_path=os.path.join(os.path.dirname(__file__), "web/static"),
            xsrf_cookies=True,
            db=db,
            config=config,
            site_title="PANOPTES",
            ui_modules=uimodules,
            compress_response=True,
            autoreload=tornado.options.options.debug
        )

        super().__init__(app_handlers, **settings)


if __name__ == '__main__':
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(WebAdmin())
    http_server.listen(tornado.options.options.port)
    tornado.ioloop.IOLoop.instance().start()
