import os
import os.path

import sockjs.tornado

import tornado.auth
import tornado.escape
import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.options

import zmq
import pymongo

import multiprocessing

import panoptes.admin.web.uimodules as uimodules
import panoptes.admin.web.handlers.base as handlers
import panoptes.admin.web.handlers.messaging_connection as mc
import panoptes.admin.web.handlers.login as login

from panoptes.utils import config, database, logger


@logger.has_logger
@config.has_config
class BaseApp(tornado.web.Application):

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
            (r"/login", login.LoginHandler),
            (r"/logout", login.LogoutHandler),
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
        )

        super().__init__(app_handlers, **settings)

@logger.has_logger
@config.has_config
class Application(BaseApp):

    """ Class that controls the web admin interface.

    Responsible for putting the web interface into a separate
    process and controlling how it stops/starts.
    """

    def __init__(self):
        self._processes = list()

        webapp_process = multiprocessing.Process(target=self.loop_capture, args=[])
        webapp_process.daemon = True
        webapp_process.name = 'web_admin_process'
        self._processes.append(webapp_process)

    def loop_capture(self):
        """ Starts the loop capture """
        port = self.config.get('admin').get('web').get('port', 8888)
        debug = self.config.get('admin').get('web').get('debug', False)

        http_server = tornado.httpserver.HTTPServer(BaseApp(debug=debug))
        http_server.listen(port)
        tornado.ioloop.IOLoop.instance().start()

    def start_app(self):
        """ Starts the web admin app """

        for process in self._processes:
            self.logger.info("Staring admin interface process {}".format(process.name))
            process.start()

    def stop_app(self):
        """ Stops the web app """
        for process in self._processes:
            self.logger.info("Stopping admin interface {}".format(process.name))
            process.terminate()
            process.join()

if __name__ == '__main__':
    web = Application()
    web.start_app()