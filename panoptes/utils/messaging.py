import zmq
from json import dumps
from astropy.time import Time

from .logger import get_logger


class PanMessaging(object):

    """Messaging class for PANOPTES project. Creates a new ZMQ
    context that can be shared across parent application.

    """

    def __init__(self, publisher=False):
        # Create a new context
        self.logger = get_logger(self)
        self.context = zmq.Context()

        if publisher:
            self.logger.debug("Creating publisher.")
            self.publisher = self.create_publisher()

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

    def create_subscriber(self, port=6500, channel='system'):
        """ Create a subscriber

        Args:
            channel (str):      Which topic channel to subscribe to, default to 'system'.
        """
        socket = self.context.socket(zmq.SUB)
        socket.connect('tcp://localhost:{}'.format(port))

        socket.setsockopt_string(zmq.SUBSCRIBE, channel)

        self.logger.debug("Creating subscriber on {} {}".format(port, channel))
        return socket

    def register_callback(self, channel, callback, port=6500):
        """ Create a subscriber

        Args:
            channel (str):      Which topic channel to subscribe to.
            callback (code):    Function to be called when message received, function receives message as
                single parameter.

        """
        socket = self.context.socket(zmq.SUB)
        socket.connect('tcp://localhost:{}'.format(port))

        socket.setsockopt_string(zmq.SUBSCRIBE, channel)

        return socket

    def send_message(self, channel, message):
        """ Responsible for actually sending message across a channel

        Args:
            channel(str):   Name of channel to send on.
            message(str):   Message to be sent.

        """
        assert channel > '', self.logger.warning("Cannot send blank channel")

        # If just a string, wrap in object
        if isinstance(message, str):
            message = {'message': message, 'timestamp': Time.now().isot.replace('T', ' ').split('.')[0]}

        msg_object = dumps(message)

        full_message = '{} {}'.format(channel, msg_object)

        self.logger.debug("Sending message: {}".format(full_message))

        # Send the message
        self.publisher.send_string(full_message)
