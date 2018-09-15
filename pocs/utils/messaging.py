import datetime
import re
import zmq

import yaml

from astropy import units as u
from astropy.time import Time
from bson import ObjectId
from json import dumps
from json import loads

from pocs.utils import current_time
from pocs.utils.logger import get_root_logger


class PanMessaging(object):
    """Provides messaging services within a PANOPTES robotic telescope.

    Supports broadcasting messages from publishers (e.g. a POCS or
    ArduinoIO class instance) to subscribers (also typically class
    instances). The publishers and subscribers may be in the same
    process, or in separate processes. The messages all go through
    a message forwarder; this is a process which listens for messages
    from all publishers on one TCP port and forwards each message to
    all subscribers that are connected to a second TCP port.

    Do not create PanMessaging instances directly. Publishers should
    call PanMessaging.create_publisher to create an instance of
    PanMessaging, on which they can then call send_message.
    Subscribers should call PanMessaging.create_subscriber to create
    an instance of PanMessaging, on which they can then call
    receive_message.

    Messages are sent to channels, a name that can be used to allow
    a high-level partitioning of messages. A channel name may not
    include whitespace. Among the currently used channel names are:

      * PANCHAT (sent from POCS.say)
      * PAWS-CMD (sent from PAWS websockets.py)
      * POCS (sent by class POCS)
      * POCS-CMD (sent by class POCS)
      * STATUS (sent by class POCS)
      * weather (from peas/sensors.py)
      * environment (from peas/sensors.py)
      * telemetry:commands (in ArduinoIO... new)
      * camera:commands (in ArduinoIO... new)

    And some other channels are used in tests:

      * TEST-CHANNEL (test_messaging.py)
      * RUNNING (test_pocs.py)
      * POCS-CMD (test_pocs.py)

    The method receive_message will return messages from all channels;
    the caller must check the returned channel name to determine if
    the message value is of interest.

    Note: PAWS doesn't use PanMessaging, which will likely result in
    problems as we evolve PanMessaging and the set of channels.
    TODO: Figure out how to share PanMessaging with PAWS.

    Note: there is some inconsistency in the code. Senders refer to
    the channel of a message, but receivers refer to messages as having
    a msg_type.
    TODO: Make this more consistent.

    The value of a message being sent may be a string (in which case it
    is wrapped in a dict(message=<value>, timestamp=<now>) or a dict,
    in which case it will be "scrubbed", i.e. the dict entries will be
    modified as necessary to so that the dict can be serialized using
    json.dumps.

    TODO Pick an encoding of strings (e.g. UTF-8) so that non-ASCII
    strings may be sent and received without corruption of the data
    or exceptions being thrown.

    ZeroMQ is used to provide the underlying pub-sub support. ZeroMQ
    supports only a very basic message format: an array of bytes.
    PanMessaging converts the provided message channel and value into
    a byte array of this format:
        <channel-name><space><serialized-value>
    """
    logger = get_root_logger()

    # Channel names must consist of the characters.
    name_re = re.compile('[a-zA-Z][-a-zA-Z0-9_.:]*')

    def __init__(self, **kwargs):
        """Do not call this directly."""
        # Create a new context
        self.context = zmq.Context()
        self.socket = None

    @classmethod
    def create_forwarder(cls, sub_port, pub_port, ready_fn=None, done_fn=None):
        subscriber, publisher = PanMessaging.create_forwarder_sockets(sub_port, pub_port)
        PanMessaging.run_forwarder(subscriber, publisher, ready_fn=ready_fn, done_fn=done_fn)

    @classmethod
    def create_forwarder_sockets(cls, sub_port, pub_port):
        subscriber = PanMessaging.create_subscriber(sub_port, bind=True, connect=False)
        publisher = PanMessaging.create_publisher(pub_port, bind=True, connect=False)
        return subscriber, publisher

    @classmethod
    def run_forwarder(cls, subscriber, publisher, ready_fn=None, done_fn=None):
        try:
            if ready_fn:
                ready_fn()
            zmq.device(zmq.FORWARDER, subscriber.socket, publisher.socket)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            publisher.logger.warning(e)
            publisher.logger.warning("bringing down zmq device")
        finally:
            publisher.close()
            subscriber.close()
            if done_fn:
                done_fn()

    @classmethod
    def create_publisher(cls, port, bind=False, connect=True):
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
    def create_subscriber(cls, port, channel='', bind=False, connect=True):
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

    def send_message(self, channel, message):
        """ Responsible for actually sending message across a channel

        Args:
            channel(str):   Name of channel to send on. The name must
                match name_re.
            message:   Message to be sent (a string or a dict).
        """
        if not isinstance(channel, str):
            raise ValueError('Channel name must be a string')
        elif not self.name_re.fullmatch(channel):
            raise ValueError('Channel name ("{}") is not valid'
                .format(channel))

        if isinstance(message, str):
            message = {
                'message': message,
                'timestamp': current_time().isot.replace(
                    'T',
                    ' ').split('.')[0]}
        elif isinstance(message, dict):
            message = self.scrub_message(message)
        else:
            raise ValueError('Message value must be a string or dict')

        msg_object = dumps(message, skipkeys=True)

        full_message = '{} {}'.format(channel, msg_object)

        if channel == 'PANCHAT':
            self.logger.info("{} {}".format(channel, message['message']))

        # Send the message
        self.socket.send_string(full_message, flags=zmq.NOBLOCK)

    def receive_message(self, blocking=True, flags=0):
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
        if not blocking:
            flags = flags | zmq.NOBLOCK
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

    def close(self):
        """Close the socket """
        self.socket.close()
        self.context.term()

    def scrub_message(self, message):
        result = {}

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

            # Hmmmm. What is going on here? We need some documentation.
            if k.endswith('_time'):
                v = str(v).split(' ')[-1]

            if isinstance(v, float):
                v = round(v, 3)

            result[k] = v

        return result
