import datetime
from json import dumps
from json import loads
import logging
from typing import Any, Dict, Union
import zmq

from astropy import units as u
from astropy.time import Time
from bson import ObjectId
import yaml

from pocs.utils import current_time

Message = Dict[str, Any]


class PanMessaging(object):

    """Messaging class for PANOPTES project. Creates a new ZMQ
    context that can be shared across parent application.

    """
    logger = logging

    def __init__(self, **kwargs) -> None:
        # Create a new context
        self.context = zmq.Context()
        self.socket = None

    @classmethod
    def create_forwarder(cls, sub_port: int, pub_port: int) -> None:
        subscriber = PanMessaging.create_subscriber(sub_port, bind=True, connect=False)
        publisher = PanMessaging.create_publisher(pub_port, bind=True, connect=False)

        try:
            zmq.device(zmq.FORWARDER, subscriber.socket, publisher.socket)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            publisher.logger.warning(e)
            publisher.logger.warning("bringing down zmq device")
        finally:
            publisher.close()
            subscriber.close()

    @classmethod
    def create_publisher(cls, port: int, bind: bool = False, connect: bool = True) -> 'PanMessaging':
        """ Create a publisher

        Args:
            port (int): The port (on localhost) to bind to.

        Returns:
            A ZMQ PUB socket
        """
        obj = cls()

        obj.logger.debug("Creating publisher. Binding to port {} ".format(port))

        socket = obj.context.socket(zmq.PUB)

        if bind:
            socket.bind('tcp://*:{}'.format(port))
        elif connect:
            socket.connect('tcp://localhost:{}'.format(port))

        obj.socket = socket

        return obj

    @classmethod
    def create_subscriber(cls, port: int, channel: str = '', bind: bool = False, connect: bool = True) -> 'PanMessaging':
        """ Create a listener

        Args:
            port (int):         The port (on localhost) to bind to.
            channel (str):      Which topic channel to subscribe to.

        """
        obj = cls()
        obj.logger.debug("Creating subscriber. Port: {} \tChannel: {}".format(port, channel))

        socket = obj.context.socket(zmq.SUB)

        if bind:
            try:
                socket.bind('tcp://*:{}'.format(port))
            except zmq.error.ZMQError:
                obj.logger.debug('Problem binding port {}'.format(port))
        elif connect:
            socket.connect('tcp://localhost:{}'.format(port))

        socket.setsockopt_string(zmq.SUBSCRIBE, channel)

        obj.socket = socket

        return obj

    def send_message(self, channel: str, message: Union[Message, str]) -> None:
        """ Responsible for actually sending message across a channel

        Args:
            channel(str):   Name of channel to send on.
            message(str|dict):   Message to be sent.

        """
        assert channel > '', self.logger.warning("Cannot send blank channel")

        if isinstance(message, str):
            message = {
                'message': message,
                'timestamp': current_time().isot.replace(
                    'T',
                    ' ').split('.')[0]}
        else:
            message = self.scrub_message(message)

        msg_object = dumps(message, skipkeys=True)

        # WARNING: There is no requirement that channel have no spaces in it, so the split
        # in receive message may fail.
        # TODO(jamessynge): File an issue about changing the encoding so that the top-level
        # format that a list of 2 items, channel and message; we can the run dumps on that.
        # Note that dumps can be extended to do what scrub_message is doing.
        full_message = '{} {}'.format(channel, msg_object)

        if channel == 'PANCHAT':
            self.logger.info("{} {}".format(channel, message['message']))

        # Send the message
        self.socket.send_string(full_message, flags=zmq.NOBLOCK)

    def receive_message(self, flags: int = 0) -> Message:
        """Receive a message

        Receives a message for the current subscriber. Blocks by default, pass
        `flags=zmq.NOBLOCK` for non-blocking.

        Args:
            flag (int, optional): Any valid recv flag, e.g. zmq.NOBLOCK

        Returns:
            tuple(str, dict): Tuple containing the channel and a dict
        """
        msg_type = None
        msg_obj = None
        try:
            message = self.socket.recv_string(flags=flags)
        except Exception:
            pass
        else:
            msg_type, msg = message.split(' ', maxsplit=1)
            try:
                msg_obj = loads(msg)
            except Exception:
                msg_obj = yaml.load(msg)

        return msg_type, msg_obj

    def close(self) -> None:
        """Close the socket """
        self.socket.close()
        self.context.term()

    def scrub_message(self, message: Message) -> Message:

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
