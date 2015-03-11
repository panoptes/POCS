import os
import os.path

import sockjs.tornado

import tornado.auth
import tornado.escape
import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.options as options

import zmq
import pymongo

import multiprocessing

import panoptes.admin.web.uimodules as uimodules
import panoptes.admin.web.handlers.base as handlers
import panoptes.admin.web.handlers.messaging_connection as mc

from panoptes.utils import config, database, logger


@logger.has_logger
@config.has_config
class Application(tornado.web.Application):

    """ The main Application entry for our PANOPTES admin interface """

    def __init__(self, debug=False):

        db = database.PanMongo()

        # Setup up our communication socket to listen to Observatory broker
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect("tcp://localhost:5559")

        AdminRouter = sockjs.tornado.SockJSRouter(
            mc.MessagingConnection,
            '/messaging_conn',
            user_settings=dict(db=db, socket=self.socket),
        )

        app_handlers = [
            (r"/", handlers.MainHandler),
            (r"/login", handlers.LoginHandler),
            (r"/logout", handlers.LogoutHandler),
        ] + AdminRouter.urls

        settings = dict(
            cookie_secret="PANOPTES_SUPER_DOOPER_SECRET",
            login_url="/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            db=db,
            debug=debug,
            site_title="PANOPTES",
            ui_modules=uimodules,
            compress_response=True,
            autoreload = True,
        )

        super().__init__(app_handlers, **settings)



if __name__ == '__main__':
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()