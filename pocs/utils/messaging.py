import datetime
import logging
import zmq

from astropy import units as u
from astropy.time import Time
from bson import ObjectId
from json import dumps
from json import loads
from warnings import warn

from pocs.utils import current_time


class PanMessaging(object):

    """Messaging class for PANOPTES project. Creates a new ZMQ
    context that can be shared across parent application.

    """
    logger = logging

    def __init__(self, socket_type, port, **kwargs):
        assert socket_type is not None
        assert port is not None

        # Create a new context
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
        assert self.publisher is not None, warn('Only publishers can receive messages')
        assert channel > '', self.logger.warning("Cannot send blank channel")

        if isinstance(message, str):
            message = {'message': message, 'timestamp': current_time().isot.replace('T', ' ').split('.')[0]}
        else:
            message = self.scrub_message(message)

        msg_object = dumps(message, skipkeys=True)

        full_message = '{} {}'.format(channel, msg_object)

        if channel == 'PANCHAT':
            self.logger.info("{} {}".format(channel, message['message']))

        # Send the message
        self.publisher.send_string(full_message, flags=zmq.NOBLOCK)

    def receive_message(self, flag=0):
        """Recive a message

        Receives a message for the current subscriber. Blocks by default.

        Args:
            flag (int, optional): Any valid recv flag, e.g. zmq.NOBLOCK

        Returns:
            tuple(str, dict): Tuple containing the channel and a dict
        """
        assert self.subscriber is not None, warn('Only subscribers can receive messages')
        msg_type, msg = self.subscriber.recv_string(flags=flag).split(' ', maxsplit=1)
        msg_obj = loads(msg)

        return msg_type, msg_obj

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
