import datetime
import logging
import zmq

from astropy import units as u
from astropy.time import Time
from bson import ObjectId
from json import dumps

from pocs.utils import current_time
# from pocs.utils.logger import get_logger


class PanMessaging(object):

    """Messaging class for PANOPTES project. Creates a new ZMQ
    context that can be shared across parent application.

    """
    logger = logging

    def __init__(self, socket_type, port, **kwargs):
        assert socket_type is not None
        assert port is not None

        # Create a new context
        # self.logger = get_logger(self)
        self.context = zmq.Context()

        self.publisher = None
        self.subscriber = None

        if socket_type == 'publisher':
            self.publisher = self.create_publisher(port, connect=True)

        if socket_type == 'subscriber':
            self.subscriber = self.create_subscriber(port, connect=True)

        if socket_type == 'forwarder':
            self.create_forwarder(port[0], port[1])

    def create_forwarder(self, sub_port, pub_port):
        self.logger.debug("Starting message forward device")

        self.subscriber = self.create_subscriber(sub_port, bind=True)
        self.publisher = self.create_publisher(pub_port, bind=True)

        try:
            zmq.device(zmq.FORWARDER, self.subscriber, self.publisher)
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("bringing down zmq device")
        finally:
            self.publisher.close()
            self.subscriber.close()
            self.context.term()

    def create_publisher(self, port, bind=False, connect=False):
        """ Create a publisher

        Args:
            port (int): The port (on localhost) to bind to.

        Returns:
            A ZMQ PUB socket
        """
        self.logger.debug("Creating publisher. Binding to port {} ".format(port))

        socket = self.context.socket(zmq.PUB)

        if bind:
            socket.bind('tcp://*:{}'.format(port))

        if connect:
            socket.connect('tcp://localhost:{}'.format(port))

        return socket

    def create_subscriber(self, port, channel='', bind=False, connect=False):
        """ Create a listener

        Args:
            port (int):         The port (on localhost) to bind to.
            channel (str):      Which topic channel to subscribe to.

        """
        self.logger.debug("Creating subscriber. Port: {} \tChannel: {}".format(port, channel))

        socket = self.context.socket(zmq.SUB)

        if bind:
            socket.bind('tcp://*:{}'.format(port))

        if connect:
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

        if isinstance(message, str):
            message = {'message': message, 'timestamp': current_time().isot.replace('T', ' ').split('.')[0]}
        else:
            message = self.scrub_message(message)

        msg_object = dumps(message, skipkeys=True)

        full_message = '{} {}'.format(channel, msg_object)

        if channel.endswith('_SHELL'):
            self.logger.debug(full_message)

        # Send the message
        self.publisher.send_string(full_message, flags=zmq.NOBLOCK)

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

            if isinstance(v, Time):
                v = str(v.isot).split('.')[0].replace('T', ' ')

            # Hmmmm
            if k.endswith('_time'):
                v = str(v).split(' ')[-1]

            if isinstance(v, float):
                v = round(v, 3)

            message[k] = v

        return message
