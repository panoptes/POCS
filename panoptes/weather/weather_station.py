import datetime
import os
import sys
import re
import zmq

from panoptes.utils import logger, messaging

@logger.has_logger
class WeatherStation(object):
    """
    This object is used to determine the weather safe/unsafe condition. It listens
    on the 'weather' channel of the messaging system.

    Args:
        messaging (panoptes.messaging.Messaging): A messaging Object for creating new
            sockets.
    """
    def __init__(self, messaging=None):

        if messaging is None:
            messaging = messaging.Messaging()

        port = self.config.get('messaging').get('port')

        self.messaging = messaging
        self.socket = self.messaging.create_publisher(port=port)


    def run(self):
        """
        Reads serial information off the attached weather station and publishes
        message with status
        """

        while True:
            message = 'SAFE'

            # Send the message
            self.socket.send(message)

            time.sleep(1)



if __name__ == '__main__':
    weather = WeatherStation()
    weather.run()