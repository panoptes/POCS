import datetime
import zmq

from astropy import units as u
from astropy.time import Time
from bson import ObjectId
from json import dumps

from pocs.utils import current_time
from pocs.utils.logger import get_logger


class PanMessaging(object):

    """Messaging class for PANOPTES project. Creates a new ZMQ
    context that can be shared across parent application.

    """

    def __init__(self, publisher=False, listener=False, forwarder=False, **kwargs):
        # Create a new context
        self.logger = get_logger(self)
        self.context = zmq.Context()

        self.publisher = None
        self.listener = None
        self.forwarder = None

        self.pub_port = 6500
        self.sub_port = 6501

        if publisher:
            self.logger.debug("Creating publisher.")
            self.publisher = self.create_publisher(**kwargs)

        if listener:
            self.logger.debug("Creating listener.")
            self.listener = self.register_listener(**kwargs)

        if forwarder:
            self.logger.debug("Creating forwarder.")
            self.create_forwarder()

    def create_forwarder(self):
        self.publisher = self.create_publisher(bind=True, port=self.sub_port)

        self.listener = self.register_listener(bind=True, port=self.pub_port)

        self.logger.debug("Starting message forward device")
        try:
            zmq.device(zmq.FORWARDER, self.listener, self.publisher)
        except Exception as e:
            self.logger.warning(e)
            self.logger.warning("bringing down zmq device")
        finally:
            self.publisher.close()
            self.listener.close()
            self.context.term()

    def create_publisher(self, port=None, bind=False, connect=False):
        """ Create a publisher

        Args:
            port (int): The port (on localhost) to bind to.

        Returns:
            A ZMQ PUB socket
        """
        if not port:
            port = self.pub_port

        self.logger.debug("Creating publisher. Binding to port {} ".format(port))

        socket = self.context.socket(zmq.PUB)

        if bind:
            socket.bind('tcp://*:{}'.format(port))

        if connect:
            socket.connect('tcp://localhost:{}'.format(port))

        return socket

    def register_listener(self, channel='', callback=None, port=None, bind=False, connect=False, start_proc=False):
        """ Create a listener

        Args:
            channel (str):      Which topic channel to subscribe to.
            callback (code):    Function to be called when message received, function receives message as
                single parameter.

        """
        if not port:
            port = self.sub_port

        socket = self.context.socket(zmq.SUB)

        if bind:
            socket.bind('tcp://*:{}'.format(port))

        if connect:
            socket.connect('tcp://localhost:{}'.format(port))

        socket.setsockopt_string(zmq.SUBSCRIBE, channel)

        # if start_proc or (callback is not None):
        #     def get_msg():
        #         while True:
        #             msg_type, msg = socket.recv_string().split(' ', maxsplit=1)

        #             if callback is None:
        #                 self.logger.info("Web message: {} {}".format(msg_type, msg))
        #             else:
        #                 self.logger.debug('Calling callback with message')
        #                 callback(msg_type, msg)

        #             time.sleep(1)

        #     proc = Process(target=get_msg)
        #     proc.start()
        #     self.logger.debug("Starting listener process: {}".format(proc.pid))

        self.logger.debug("Starting listener for channel: {}".format(channel))

        return socket

    def send_message(self, channel, message):
        """ Responsible for actually sending message across a channel

        Args:
            channel(str):   Name of channel to send on.
            message(str):   Message to be sent.

        """
        assert channel > '', self.logger.warning("Cannot send blank channel")

        if not hasattr(self, 'publisher'):
            self.logger.debug("Creating publisher.")
            self.publisher = self.create_publisher()

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

            if isinstance(v, Time):
                v = str(v.isot).split('.')[0].replace('T', ' ')

            if isinstance(v, float):
                v = round(v, 3)

            message[k] = v

        return message

if __name__ == '__main__':
    try:
        messaging = PanMessaging(forwarder=True)
    except KeyboardInterrupt:
        print("Stopping messaging")
