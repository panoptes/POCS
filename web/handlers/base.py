import tornado.escape
import tornado.web
from tornado.websocket import WebSocketHandler

import zmq
from zmq.eventloop.zmqstream import ZMQStream

from panoptes.utils.logger import has_logger


class BaseHandler(tornado.web.RequestHandler):

    """
    BaseHandler is inherited by all Handlers and is responsible for any
    global operations. Provides the `db` property and the `get_current_user`
    """

    def initialize(self):
        self.config = self.settings['config']
        self.db = self.settings['db']

    def get_current_user(self):
        """
        Looks for a cookie that shows we have been logged in. If cookie
        is found, attempt to look up user info in the database
        """
        # Get email from cookie
        email = tornado.escape.to_unicode(self.get_secure_cookie("email"))
        if not email:
            return None

        # Look up user data
        user_data = self.db.admin.find_one({'username': email})
        if user_data is None:
            return None

        return user_data


class MainHandler(BaseHandler):

    def get(self):
        user_data = self.get_current_user()

        self.render("main.html", user_data=user_data)

@has_logger
class MyWebSocket(WebSocketHandler):

    def open(self):
        messaging = self.settings['messaging']
        self.pubsub = ZMQPubSub(self.on_data, messaging, self.settings['name'])
        self.pubsub.connect()
        self.logger.info("WS Opened")

    def on_message(self, message):
        self.logger.info("WS Sent: {}".format(message))

    def on_close(self):
        self.logger.info("WS Closed")

    def on_data(self, data):
        self.logger.info("WS Received: {}".format(data))
        self.write_message(data)


class ZMQPubSub(object):

    def __init__(self, callback, messaging, channel):
        self.callback = callback
        self.messaging = messaging
        self.channel = channel

    def connect(self):
        self.socket = self.messaging.create_subscriber(channel=self.channel)
        self.stream = ZMQStream(self.socket)
        self.stream.on_recv(self.callback)
