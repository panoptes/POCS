import zmq
import datetime

from panoptes.utils import logger, config

@config.has_config
@logger.has_logger
class Messaging(object):
    """Messaging class for PANOPTES project. Creates a new ZMQ
    context that can be shared across parent application.

    """
    def __init__(self):
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

    def create_subscriber(self, port=6500, channel='system'):
        """ Create a subscriber

        Args:
            channel (str): Which topic channel to subscribe to. Defaults to 'system'

        Returns:
            A ZMQ SUB socket
        """

        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect('tcp://localhost:{}'.format(self.config.get('port', '6500')))

        self.socket.setsockopt_string(zmq.SUBSCRIBE, channel)

        return self.socket


    def _send_message(self, message=''):
        """ Responsible for actually sending message. Appends the channel
        and timestamp to outgoing message

        """
        assert message > '', self.logger.warn("Cannot send blank message")

        timestamp = datetime.datetime.now()

        full_message = '{} {} {}'.format(self.channel, timestamp, message)

        # Send the message
        self.socket.send_string(full_message)