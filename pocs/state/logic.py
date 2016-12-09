import time
import zmq

from json import loads
from multiprocessing import Process
from multiprocessing import Queue

from ..utils import current_time
from ..utils.messaging import PanMessaging


class PanStateLogic(object):

    """ The enter and exit logic for each state. """

    def __init__(self, **kwargs):
        self.logger.debug("Setting up state logic")

        self._setup_messaging()

        self._sleep_delay = kwargs.get('sleep_delay', 2.5)  # Loop delay
        self._safe_delay = kwargs.get('safe_delay', 60 * 5)  # Safety check delay
        self._is_safe = False

##################################################################################################
# Condition Methods
##################################################################################################

    def is_safe(self):
        """ Checks the safety flag of the system to determine if safe.

        This will check the weather station as well as various other environmental
        aspects of the system in order to determine if conditions are safe for operation.

        Note:
            This condition is called by the state machine during each transition

        Args:
            event_data(transitions.EventData): carries information about the event if
            called from the state machine.

        Returns:
            bool:   Latest safety flag
        """
        is_safe_values = dict()

        # Check if night time
        is_safe_values['is_dark'] = self.is_dark()

        # Check weather
        is_safe_values['good_weather'] = self.is_weather_safe()

        safe = all(is_safe_values.values())

        if not safe:
            self.logger.warning('Unsafe conditions: {}'.format(is_safe_values))

            # Not safe so park unless we are not active
            if self.state not in ['sleeping', 'parked', 'parking', 'housekeeping', 'ready']:
                self.logger.warning('Safety failed so sending to park')
                self.park()

        return safe

    def is_dark(self):
        """ Is it dark

        Checks whether it is dark at the location provided. This checks for the config
        entry `location.horizon` or 18 degrees (astronomical twilight).

        Returns:
            bool:   Is night at location

        """
        if 'night' in self.config['simulator']:
            self.logger.debug("Night simulator says safe")
            is_dark = True
        else:
            is_dark = self.observatory.is_dark

        self.logger.debug("Dark Check: {}".format(is_dark))
        return is_dark

    def is_weather_safe(self, stale=180):
        """ Determines whether current weather conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Returns:
            bool:       Conditions are safe (True) or unsafe (False)
        """
        assert self.db.current, self.logger.warning("No connection to sensors, can't check weather safety")

        # Always assume False
        is_safe = False
        record = {'safe': False}

        if 'weather' in self.config['simulator']:
            self.logger.debug("Weather simluator always safe")
            is_safe = True
        else:
            try:
                record = self.db.current.find_one({'type': 'weather'})

                is_safe = record['data'].get('safe', False)
                timestamp = record['date']
                age = (current_time().datetime - timestamp).total_seconds()

                self.logger.debug("Weather Safety: {} [{:.0f} sec old - {}]".format(is_safe, age, timestamp))

            except TypeError:
                self.logger.warning("No record found in Mongo DB")
            else:
                if age > stale:
                    self.logger.warning("Weather record looks stale, marking unsafe.")
                    is_safe = False

        self._is_safe = is_safe

        return self._is_safe

##################################################################################################
# State Conditions
##################################################################################################

    def check_safety(self, event_data=None):
        """ Checks the safety flag of the system to determine if safe.

        This will check the weather station as well as various other environmental
        aspects of the system in order to determine if conditions are safe for operation.

        Note:
            This condition is called by the state machine during each transition

        Args:
            event_data(transitions.EventData): carries information about the event if
            called from the state machine.

        Returns:
            bool:   Latest safety flag
        """

        self.logger.debug("Checking safety for {}".format(event_data.event.name))

        # It's always safe to be in some states
        if event_data and event_data.event.name in ['park', 'set_park', 'clean_up', 'goto_sleep', 'get_ready']:
            self.logger.debug("Always safe to move to {}".format(event_data.event.name))
            is_safe = True
        else:
            is_safe = self.is_safe()

        return is_safe

    def mount_is_tracking(self, event_data):
        """ Transitional check for mount.

        This is used as a conditional check when transitioning between certain
        states.
        """
        return self.observatory.mount.is_tracking

    def mount_is_initialized(self, event_data):
        """ Transitional check for mount.

        This is used as a conditional check when transitioning between certain
        states.
        """
        return self.observatory.mount.is_initialized

##################################################################################################
# Convenience Methods
##################################################################################################

    def sleep(self, delay=2.5, with_status=True):
        """ Send POCS to sleep

        This just loops for `delay` number of seconds.

        Keyword Arguments:
            delay {float} -- Number of seconds to sleep (default: 2.5)
            with_status {bool} -- Show system status while sleeping (default: {True if delay > 2.0})
        """
        if delay is None:
            delay = self._sleep_delay

        if with_status and delay > 2.0:
            self.status()

        time.sleep(delay)

    def wait_until_safe(self):
        """ Waits until weather is safe

        This will wait until a True value is returned from the safety check,
        blocking until then.
        """
        if 'weather' not in self.config['simulator']:
            while not self.is_safe():
                self.sleep(delay=60)
        else:
            self.logger.debug("Weather simulator on, return safe")


##################################################################################################
# Private Methods
##################################################################################################

    def _setup_messaging(self):

        def cmd_forwarder():
            PanMessaging('forwarder', (6500, 6501))

        self.cmd_forwarder_process = Process(target=cmd_forwarder, name='CmdForwarder')
        self.cmd_forwarder_process.start()

        def msg_forwarder():
            PanMessaging('forwarder', (6510, 6511))

        self.msg_forwarder_process = Process(target=msg_forwarder, name='MsgForwarder')
        self.msg_forwarder_process.start()
        
        self.do_message_check = True
        self.cmd_queue = Queue()
        self.cmd_subscriber = PanMessaging('subscriber', 6501)
        self.msg_publisher = PanMessaging('publisher', 6510)
        check_messages = self._get_message_checker(self.cmd_queue)


        def check_message_loop():
            self.logger.debug('Starting command message loop')
            while self.do_message_check:
                check_messages()
                time.sleep(1)

        self.check_messages_process = Process(target=check_message_loop, name='MessageCheckLoop')
        self.check_messages_process.start()
        self.logger.debug('Command message subscriber set up on port {}'.format(6501))

    def _get_message_checker(self, queue):
        """Create a function that checks for incoming ZMQ messages

        Typically this will be the POCS_shell but could also be PAWS in the future.
        These messages arrive via 0MQ and are processed during each iteration of
        the event loop.

        Returns:
            code: A callable function that handles ZMQ messages
        """
        poller = zmq.Poller()
        poller.register(self.cmd_subscriber.subscriber, zmq.POLLIN)

        def check_message():

            self.logger.info('Checking messages')

            # Poll for messages
            sockets = dict(poller.poll(500))  # 500 ms timeout

            if self.cmd_subscriber.subscriber in sockets and sockets[self.cmd_subscriber.subscriber] == zmq.POLLIN:

                msg_type, msg = self.cmd_subscriber.subscriber.recv_string(flags=zmq.NOBLOCK).split(' ', maxsplit=1)
                msg_obj = loads(msg)
                self.logger.info("Incoming message: {} {}".format(msg_type, msg_obj))

                # Put the message in a queue to be processed
                queue.put([msg_type, msg_obj])

        return check_message
