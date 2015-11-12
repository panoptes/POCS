import zmq

from .logger import has_logger


@has_logger
class PanMessaging(object):

    """Messaging class for PANOPTES project. Creates a new ZMQ
    context that can be shared across parent application.

    """

    def __init__(self, publisher=False):
        # Create a new context
        self.context = zmq.Context()

        if publisher:
            self.publisher = self.create_publisher()

    def create_publisher(self, port=6500):
        """ Create a publisher

        Args:
            port (int): The port (on localhost) to bind to.

        Returns:
            A ZMQ PUB socket
        """

        assert port is not None

        self.logger.info("Creating publisher. Binding to port {} ".format(port))

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

        self.logger.info("Creating subscriber on {} {}".format(port, channel))
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
        assert message > '', self.logger.warning("Cannot send blank message")
        assert channel > '', self.logger.warning("Cannot send blank channel")

        full_message = '{} {}'.format(channel, message)

        self.logger.info("Sending message: {}".format(full_message))

        # Send the message
        self.publisher.send_string(full_message)
