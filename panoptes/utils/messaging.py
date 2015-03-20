import zmq
import datetime

from panoptes.utils import logger, config

@config.has_config
@logger.has_logger
class Messaging(object):
    """Messaging class for PANOPTES project. Creates a new ZMQ
    context that can be shared across parent application.

    """
    def __init__(self, channel='system'):
        # Create a new context
        self.context = zmq.Context()


    def create_publisher(self, port=6500):
        """ Create a publisher

        Args:
            port (int): The port (on localhost) to bind to.

        Returns:
            A ZMQ PUB socket
        """

        assert port is not None

        self.logger.info("Creating publisher. Binding to port {} ".format(port))

        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind('tcp://*:{}'.format(port))

        return self.socket

    def create_subscriber(self, port=6500, channel=None):
        """ Create a subscriber

        Args:
            channel (str): Which topic channel to subscribe to. Defaults to 'system'

        Returns:
            A ZMQ SUB socket
        """
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect('tcp://localhost:{}'.format(port))

        self.socket.setsockopt_string(zmq.SUBSCRIBE, channel)

        return self.socket


    def send_message(self, message='', channel=None):
        """ Responsible for actually sending message across a channel


        """
        assert message > '', self.logger.warning("Cannot send blank message")
        assert channel > '', self.logger.warning("Cannot send blank channel")

        full_message = '{} {}'.format(channel, message)

        # Send the message
        self.socket.send_string(full_message)