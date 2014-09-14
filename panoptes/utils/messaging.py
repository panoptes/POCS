import zmq

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

        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind('tcp://*:{}'.format(port))

        return self.socket

    def create_subscriber(self, channel='system'):
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