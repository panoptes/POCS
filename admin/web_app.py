import os
import os.path
import sys

import sockjs.tornado

import tornado.escape
import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.options as options

import zmq

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import admin.web.uimodules as uimodules
import admin.web.handlers.base as handlers
import admin.web.handlers.messaging as messaging

from panoptes.utils import config, database, logger

tornado.options.define("port", default=8888, help="port", type=int)
tornado.options.define("debug", default=False, help="debug mode")

@logger.has_logger
@config.has_config
class WebAdmin(tornado.web.Application):

    """ The main Application entry for our PANOPTES admin interface """

    def __init__(self):

        db = database.PanMongo()

        # Setup up our communication socket to listen to Observatory broker
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect("tcp://localhost:5559")

        MessagingRouter = sockjs.tornado.SockJSRouter(
            messaging.MessagingConnection,
            '/messaging_conn',
            user_settings=dict(db=db, socket=self.socket),
        )

        app_handlers = [
            (r"/", handlers.MainHandler),
        ] + MessagingRouter.urls

        settings = dict(
            cookie_secret="PANOPTES_SUPER_DOOPER_SECRET",
            template_path=os.path.join(os.path.dirname(__file__), "web/templates"),
            static_path=os.path.join(os.path.dirname(__file__), "web/static"),
            xsrf_cookies=True,
            db=db,
            site_title="PANOPTES",
            ui_modules=uimodules,
            compress_response=True,
        )

        super().__init__(app_handlers, **settings)



if __name__ == '__main__':
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(WebAdmin())
    http_server.listen(tornado.options.options.port)
    tornado.ioloop.IOLoop.instance().start()