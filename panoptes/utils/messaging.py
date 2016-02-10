import zmq
import datetime
import time
from multiprocessing import Process
from json import dumps
from bson import ObjectId
from astropy import units as u

from .logger import get_logger
from . import current_time


class PanMessaging(object):

    """Messaging class for PANOPTES project. Creates a new ZMQ
    context that can be shared across parent application.

    """

    def __init__(self, publisher=False, listener=False):
        # Create a new context
        self.logger = get_logger(self)
        self.context = zmq.Context()

        if publisher:
            self.logger.debug("Creating publisher.")
            self.publisher = self.create_publisher()

        if listener:
            self.logger.debug("Creating listener.")
            self.listener = self.register_listener()

    def create_publisher(self, port=6500):
        """ Create a publisher

        Args:
            port (int): The port (on localhost) to bind to.

        Returns:
            A ZMQ PUB socket
        """

        assert port is not None

        self.logger.debug("Creating publisher. Binding to port {} ".format(port))

        socket = self.context.socket(zmq.PUB)
        socket.bind('tcp://*:{}'.format(port))

        return socket

    def register_listener(self, channel='', callback=None, port=6500):
        """ Create a listener

        Args:
            channel (str):      Which topic channel to subscribe to.
            callback (code):    Function to be called when message received, function receives message as
                single parameter.

        """
        socket = self.context.socket(zmq.SUB)
        socket.connect('tcp://localhost:{}'.format(port))

        socket.setsockopt_string(zmq.SUBSCRIBE, channel)

        if callback is None:
            self.logger.debug('Creating call back for messages')

            def show_web_msg():
                self.logger.info('In show_web_msg')
                while True:
                    msg_type, msg = socket.recv_string().split(' ', maxsplit=1)
                    # if msg_type == channel or channel == '*':
                    self.logger.info("Web message: {} {}".format(msg_type, msg))

                    time.sleep(1)

            proc = Process(target=show_web_msg)
        else:
            # Create another process to call callback
            proc = Process(target=callback, args=(socket,))

        proc.start()
        self.logger.debug("Starting listener process: {}".format(proc.pid))

    def send_message(self, channel, message):
        """ Responsible for actually sending message across a channel

        Args:
            channel(str):   Name of channel to send on.
            message(str):   Message to be sent.

        """
        assert channel > '', self.logger.warning("Cannot send blank channel")

        if isinstance(message, str):
            message = {'message': message, 'timestamp': current_time().isot.replace('T', ' ').split('.')[0]}
        else:
            message = self.scrub_message(message)

        # msg_object = dumps(self.scrub_message(message))
        msg_object = dumps(message, skipkeys=True)

        full_message = '{} {}'.format(channel, msg_object)

        self.logger.debug("Sending message: {}".format(full_message))

        # Send the message
        self.publisher.send_string(full_message)

    def scrub_message(self, message):

        for k, v in message.items():
            if isinstance(v, dict):
                v = self.scrub_message(v)

            if isinstance(v, u.Quantity):
                v = v.value

            if isinstance(v, datetime.datetime):
                v = v.isoformat()

            if isinstance(v, ObjectId):
                v = str(v)

            message[k] = v

        return message
