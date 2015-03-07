import os
import os.path
import sys

import sockjs.tornado

import zmq
import pymongo

import panoptes.admin.uimodules as uimodules
import panoptes.admin.handlers as handlers

from panoptes.utils import config, database, logger

@logger.has_logger
@config.has_config
class Application(tornado.web.Application):

    """ The main Application entry for our PANOPTES admin interface """

    def __init__(self):

        db = database.PanMongo()

        # Setup up our communication socket to listen to Observatory broker
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect("tcp://localhost:5559")

        AdminRouter = sockjs.tornado.SockJSRouter(
            handlers.MessagingConnection,
            '/messaging_conn',
            user_settings=dict(db=db, socket=self.socket),
        )

        handlers = [
            (r"/", handlers.MainHandler),
            (r"/sensors", handlers.SensorHandler),
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
            debug=options.debug,
            site_title="PANOPTES",
            ui_modules=uimodules,
        )

        super(Application, self).__init__(handlers, **settings)