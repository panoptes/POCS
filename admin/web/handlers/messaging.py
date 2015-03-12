import tornado.auth
import tornado.escape
import tornado.web

import zmq
import pymongo
import bson.json_util as json_util

import sockjs.tornado

from panoptes.utils import logger, database


@logger.has_logger
class MessagingConnection(sockjs.tornado.SockJSConnection):

    """ Handler for the messaging connection.

    This is the connection between the administrative web interface and
    the running `Panoptes` instance.

    Implemented with sockjs for websockets or long polling.
    """

    def __init__(self, session):
        """ """
        self.session = session

        self.logger.info('Setting up websocket mount control')

        # Get or create a socket
        self.logger.info("Getting socket connection")
        try:
            self.socket = self.user_settings['socket']
        else:
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.REQ)
        finally:
            self.logger.info("Socket created, connecting")
            self.socket.connect("tcp://localhost:5559")

        # Get or create a mongo connection
        self.logger.info("Getting connection to mongo db")
        try:
            self.db = self.user_settings['db']
        else:
            self.db = database.PanMongo()

        self._mount_connected = False

    def on_open(self, info):
        """ Action to be performed when a client first connects

        Create periodic callbacks for the admin. Callbacks include:

            * _send_environment_stats:
            * _send_mount_status:

        Note:
            Delay times for the callbacks should not be hardcoded
        """
        self.logger.info('New connection to mount established')

        self.logger.info('Creating periodic callback for sensor stats')
        self.stats_loop = tornado.ioloop.PeriodicCallback(self._send_environment_stats, 1000)
        self.stats_loop.start()

        self.logger.info('Creating periodic callback for mount stats')
        self.mount_status_loop = tornado.ioloop.PeriodicCallback(self._send_mount_status, 2000)
        self.mount_status_loop.start()

    def on_message(self, message):
        """ A message received from the client

        The client will be passing commands to our `Panoptes` instance, which
        are captured here and processed. Uses the REQ socket to communicate
        with Observatory broker

        Args:
            message(str):       Message received from client (web). This is
                command that is then passed on to the broker, which is a
                `Panoptes` instance.
        """

        self.logger.info("Message Received: {}".format(message))

        # Send message to Mount
        self.socket.send_string(message)

        # Get response
        raw_response = self.socket.recv().decode('ascii')

        response = json_util.dumps({
            'type': 'mount',
            'message': raw_response,
        })

        # Send the response back to the web socket
        self.send(response)

    def on_close(self):
        """ Actions to be performed when web admin client leaves """
        self.stats_loop.stop()
        self.mount_status_loop.stop()

    def _send_environment_stats(self):
        """ Sends the current environment stats to the web admin client

        Called periodically from the `on_open` method, this simply grabs the
        current stats from the mongo db, serializes them to json, and then sends
        to the client.
        """
        data_raw = self.db.sensors.find_one({'status': 'current', 'type': 'environment'})
        data = json_util.dumps({
            'type': 'environment',
            'message': data_raw.get('data'),
        })
        self.send(data)

    def _send_mount_status(self):
        """ Gets the status read off of the mount ands sends to admin

        """
        # Send message to Mount
        self.socket.send_string('get_status')

        # Get response - NOTE: just gets the status code,
        # which is the second character [1]. See the iOptron manual
        status_response = self.socket.recv().decode('ascii')[1]

        if status_response == "Mount not connected":
            # Stop the mount loop since we don't have a connection
            self.mount_status_loop.stop()

            response = json_util.dumps({
                'type': 'mount_status',
                'message': status_response,
            })
        else:

            # Send message to Mount
            self.socket.send_string('current_coords')

            # Get response - NOTE: just gets the status code,
            # which is the second character [1]. See the iOptron manual
            coords_response = self.socket.recv().decode('ascii')

            # Send message to Mount
            self.socket.send_string('get_coordinates_altaz')

            # Get response - NOTE: just gets the status code,
            # which is the second character [1]. See the iOptron manual
            coords_altaz_response = self.socket.recv().decode('ascii')

            status_map = {
                '0': 'Stopped - Not at zero position',
                '1': 'Tracking (PEC Disabled)',
                '2': 'Slewing',
                '3': 'Guiding',
                '4': 'Meridian Flipping',
                '5': 'Tracking',
                '6': 'Parked',
                '7': 'Home',
            }

            response = json_util.dumps({
                'type': 'mount_status',
                'message': status_map.get(status_response, 'No response from mount'),
                'code': status_response,
                'coords': coords_response,
                'coords_altaz': coords_altaz_response,
            })

        # Send the response back to the web admins
        self.send(response)
