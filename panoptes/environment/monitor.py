import datetime
import zmq

from panoptes.utils import logger, config, messaging, threads


@logger.has_logger
@config.has_config
class EnvironmentalMonitor(object):

    """
    This is the base environmental monitor that the other monitors inherit from.
    It handles having a generic stoppable thread.

    Args:
        messaging (panoptes.messaging.Messaging): A messaging Object for creating new
            sockets.
        channel (str): The channel topic that this monitor is associated with. Defaults
            to 'default'
    """

    def __init__(self, messaging=None, channel='default', name=None):

        if messaging is None:
            messaging = messaging.Messaging()

        self.sleep_time = 1

        self.messaging = messaging
        self.channel = channel

        # Create the thread and start monitoring
        self.thread = threads.Thread(target=self._start_monitoring, args=())

        if name is not None:
            self.thread.name = name

    def start_monitoring(self):
        """
        Starts the actual thread
        """
        self.logger.info("Starting {} monitoring".format(self.thread.name))
        self.thread.start()

    def stop(self):
        """ Stops the running thread """
        self.logger.info("Stopping {} monitoring".format(self.thread.name))
        self.thread.stop()

    def _start_monitoring(self):
        """ Starts the actual monitoring of the thread.

        Calls out to the public monitoring() method that is implemented
        in child classes.

        Runs the child monitor() method in a loop, checking whether the
        thread has received a stop signal each time. Sleeps for self.sleep_time
        between.
        """

        while not self.thread.is_stopped():
            self.monitor()
            self.thread.wait(self.sleep_time)

    def monitor(self):
        raise NotImplementedError()

    def send_message(self, message, channel=None):
        """
        Sends a message over the socket. Checks to ensure message is not
        zero-length.

        Args:
            message (str): Message to be sent
            channel (str): Channel to send message on. Defaults to value set
                for the instance.
        """
        if(message > ''):
            if channel is None:
                channel = self.channel

            self._send_message(message, channel)

    def _send_message(self, message='', channel=None):
        """ Responsible for actually sending message. Appends the channel
        and timestamp to outgoing message.

        Args:
            message (str): Message to be sent
            channel (str): Channel to send message on. Defaults to value set
                for the instance.
        """
        assert self.socket is not None, self.logger.warning("No socket, cannot send message")
        assert message > '', self.logger.warning("Cannot send blank message")

        if channel is None:
            channel = self.channel

        timestamp = datetime.datetime.now()

        full_message = '{} {} {}'.format(channel, timestamp, message)

        # Send the message
        self.socket.send_string(full_message)

    def __del__(self):
        """ Shut down the monitor """
        self.logger.info("Shutting down the monitor")
        self.stop()
