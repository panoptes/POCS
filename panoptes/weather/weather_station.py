import datetime
import os
import sys
import re
import zmq

from panoptes.utils import logger, config, messaging, threads

@logger.has_logger
@config.has_config
class WeatherStation(object):
    """
    This object is used to determine the weather safe/unsafe condition. It listens
    on the 'weather' channel of the messaging system.

    Config:
        weather_station.port (int): Port to publish to. Defaults to 6500
        weather_station.channel (str): the channel topic to publish on. Defaults to 'weather'

    Args:
        messaging (panoptes.messaging.Messaging): A messaging Object for creating new
            sockets.
    """
    def __init__(self, messaging=None):

        if messaging is None:
            messaging = messaging.Messaging()

        self.sleep_time = 1

        self.port = self.config.get('messaging').get('port', 6500)
        self.channel = self.config.get('messaging').get('channel', 'weather')

        self.messaging = messaging
        self.socket = self.messaging.create_publisher(port=self.port)

        self.thread = threads.Thread(target=self.start_publishing, args=())
        self.thread.start()


    def send_message(self, message=''):
        """
        Sends a message over the weather station line

        Args:
            message (str): Message to be sent
        """
        if(message > ''):
            self._send_message(message)


    def stop(self):
        """ Stops the running thread """
        self.thread.stop()


    def start_publishing(self):
        """
        Reads serial information off the attached weather station and publishes
        message with status

        Args:
            stop_event (threading.Event): A threading event that allows for stopping
                of thread.
        """

        while not self.thread.is_stopped():
            self._send_message('SAFE')

            self.thread.wait(self.sleep_time)

        self.logger.info("{} exiting...".format(__name__))


    def _send_message(self, message=''):
        """ Responsible for actually sending message. Appends the channel
        and timestamp to outgoing message

        """
        assert message > '', self.logger.warn("Cannot send blank message")

        timestamp = datetime.datetime.now()

        full_message = '{} {} {}'.format(self.channel, timestamp, message)

        # Send the message
        self.socket.send_string(full_message)


if __name__ == '__main__':
    weather = WeatherStation()
    weather.run()