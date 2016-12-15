import os
import queue
import shutil
import time
import zmq

from multiprocessing import Process
from multiprocessing import Queue

from astropy import units as u

from . import PanBase
from .observatory import Observatory
from .state.machine import PanStateMachine
from .utils import current_time
from .utils.messaging import PanMessaging


class POCS(PanStateMachine, PanBase):

    """ The main class representing the Panoptes Observatory Control Software (POCS).

    Interaction with a PANOPTES unit is done through instances of this class. An instance consists
    primarily of an `Observatory` object, which contains the mount, cameras, scheduler, etc.
    See `pocs.Observatory`. The instance itself is designed to be run as a state machine with
    the `get_ready()` method the transition that is responsible for moving to the initial state.

    Args:
        state_machine_file(str):    Filename of the state machine to use, defaults to 'simple_state_table'
        simulator(list):            A list of the different modules that can run in simulator mode. Possible
            modules include: all, mount, camera, weather, night. Defaults to an empty list.

    """

    def __init__(self, state_machine_file='simple_state_table', messaging=None, **kwargs):

        # Explicitly call the base classes in the order we want
        PanBase.__init__(self, **kwargs)

        self.logger.info('{:*^80}'.format(' Starting POCS '))
        self.logger.info('Initializing PANOPTES unit')

        self._setup_messaging()

        self._sleep_delay = kwargs.get('sleep_delay', 2.5)  # Loop delay
        self._safe_delay = kwargs.get('safe_delay', 60 * 5)  # Safety check delay
        self._is_safe = False

        PanStateMachine.__init__(self, state_machine_file, **kwargs)

        # Create our observatory, which does the bulk of the work
        self.logger.info('\t observatory')
        self.observatory = Observatory(**kwargs)

        self._connected = True
        self._initialized = False
        self._interrupted = False

        self.status()

        self.name = self.config.get('name', 'Generic PANOPTES Unit')
        self.logger.info('Welcome {}!'.format(self.name))
        self.say("Hi there!")

    @property
    def is_initialized(self):
        """ Indicates if POCS has been initalized or not """
        return self._initialized

    @property
    def interrupted(self):
        return self._interrupted


##################################################################################################
# Methods
##################################################################################################

    def initialize(self):
        """ """

        if not self._initialized:
            self.say("Initializing the system! Woohoo!")

            try:
                # Initialize the mount
                self.logger.debug("Initializing mount")
                self.observatory.mount.initialize()

            except Exception as e:
                self.say("Oh wait. There was a problem initializing: {}".format(e))
                self.say("Since we didn't initialize, I'm going to exit.")
                self.power_down()
            else:
                self._initialized = True

        self.status()
        return self._initialized

    def status(self):
        status = dict()

        try:
            status['state'] = self.state
            status['observatory'] = self.observatory.status()
        except Exception as e:  # pragma: no cover
            self.logger.warning("Can't get status: {}".format(e))

        self.send_message(status, channel='STATUS')

        return status

    def say(self, msg):
        """ PANOPTES Units like to talk!

        Send a message. Message sent out through zmq has unit name as channel.

        Args:
            msg(str): Message to be sent
        """
        self.send_message(msg, channel='PANCHAT')

    def send_message(self, msg, channel='POCS'):
        """ Send a message

        This will use the `self.msg_publisher` to send a message

        Note:
            The `channel` and `msg` params are switched for convenience

        Arguments:
            msg {str} -- Message to be sent

        Keyword Arguments:
            channel {str} -- Channel to send message on (default: {'POCS'})
        """
        self.msg_publisher.send_message(channel, msg)

    def check_messages(self):
        try:

            msg_obj = self.cmd_queue.get_nowait()
            self.logger.info(msg_obj)

            if msg_obj['message'] == 'park':
                self.logger.info('Park interrupt received')
                self.next_state = 'parking'
                self._interrupted = True

        except queue.Empty:
            pass

    def power_down(self):
        """Actions to be performed upon shutdown

        Note:
            This method is automatically called from the interrupt handler. The definition should
            include what you want to happen upon shutdown but you don't need to worry about calling
            it manually.
        """
        if self._connected:
            self.say("I'm powering down")
            self.logger.info("Shutting down {}, please be patient and allow for exit.".format(self.name))

            # Observatory shut down
            self.observatory.power_down()

            # Park if needed
            if self.state not in ['parking', 'parked', 'sleeping', 'housekeeping']:
                if self.observatory.mount.is_connected:
                    if not self.observatory.mount.is_parked:
                        self.logger.info("Parking mount")
                        self.park()

            if self.state == 'parking':
                if self.observatory.mount.is_connected:
                    if self.observatory.mount.is_parked:
                        self.logger.info("Mount is parked, setting Parked state")
                        self.set_park()

            # Shut down messaging
            self.logger.debug('Shutting down messaging system')

            if self.check_messages_process.is_alive():
                self.check_messages_process.terminate()

            if self.cmd_forwarder_process.is_alive():
                self.cmd_forwarder_process.terminate()

            if self.msg_forwarder_process.is_alive():
                self.msg_forwarder_process.terminate()

            self.logger.info("Power down complete")


##################################################################################################
# Safety Methods
##################################################################################################

    def is_safe(self):
        """Checks the safety flag of the system to determine if safe.

        This will check the weather station as well as various other environmental
        aspects of the system in order to determine if conditions are safe for operation.

        Note:
            This condition is called by the state machine during each transition

        Args:
            called from the state machine.

        Returns:
            bool: Latest safety flag

        Deleted Parameters:
            event_data(transitions.EventData): carries information about the event if
        """
        is_safe_values = dict()

        # Check if night time
        is_safe_values['is_dark'] = self.is_dark()

        # Check weather
        is_safe_values['good_weather'] = self.is_weather_safe()

        is_safe_values['free_space'] = self.has_free_space()

        safe = all(is_safe_values.values())

        if not safe:
            self.logger.warning('Unsafe conditions: {}'.format(is_safe_values))

            # Not safe so park unless we are not active
            if self.state not in ['sleeping', 'parked', 'parking', 'housekeeping', 'ready']:
                self.logger.warning('Safety failed so sending to park')
                self.park()

        return safe

    def is_dark(self):
        """Is it dark

        Checks whether it is dark at the location provided. This checks for the config
        entry `location.horizon` or 18 degrees (astronomical twilight).

        Returns:
            bool: Is night at location

        """
        if 'night' in self.config['simulator']:
            self.logger.debug("Night simulator says safe")
            is_dark = True
        else:
            is_dark = self.observatory.is_dark

        self.logger.debug("Dark Check: {}".format(is_dark))
        return is_dark

    def is_weather_safe(self, stale=180):
        """Determines whether current weather conditions are safe or not

        Args:
            stale (int, optional): Number of seconds before record is stale, defaults to 180

        Returns:
            bool: Conditions are safe (True) or unsafe (False)

        """
        assert self.db.current, self.logger.warning("No connection to sensors, can't check weather safety")

        # Always assume False
        is_safe = False
        record = {'safe': False}

        if 'weather' in self.config['simulator']:
            self.logger.debug("Weather simulator always safe")
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

    def has_free_space(self, required_space=0.5 * u.gigabyte):
        """Does hard drive have disk space (>= 0.5 GB)

        Args:
            required_space (u.gigabyte, optional): Amount of free space required
            for operation

        Returns:
            bool: True if enough space
        """
        _, _, free_space = shutil.disk_usage(os.getenv('POCS'))
        free_space = (free_space * u.byte).to(u.gigabyte)

        return free_space.value >= required_space.to(u.gigabyte).value


##################################################################################################
# Convenience Methods
##################################################################################################

    def sleep(self, delay=2.5, with_status=True):
        """ Send POCS to sleep

        Loops for `delay` number of seconds. If `delay` is more than 10.0 seconds,
        `check_messages` will be called every 10.0 seconds in order to allow for
        interrupt.

        Keyword Arguments:
            delay {float} -- Number of seconds to sleep (default: 2.5)
            with_status {bool} -- Show system status while sleeping (default: {True if delay > 2.0})
        """
        if delay is None:
            delay = self._sleep_delay

        if with_status and delay > 2.0:
            self.status()

        # If delay is greater than 10 seconds check for messages during wait
        if delay >= 10.0:
            while delay >= 10.0:
                time.sleep(10.0)
                delay -= 10.0
                self.check_messages()

        if delay > 0.0:
            time.sleep(delay)

    def wait_until_safe(self):
        """ Waits until weather is safe

        This will wait until a True value is returned from the safety check,
        blocking until then.
        """
        while not self.is_safe():
            self.sleep(delay=self._safe_delay)


##################################################################################################
# Private Methods
##################################################################################################

    def _setup_messaging(self):

        cmd_port = self.config['messaging']['cmd_port']
        msg_port = self.config['messaging']['msg_port']

        def create_forwarder(port):
            PanMessaging('forwarder', (port, port + 1))

        self.cmd_forwarder_process = Process(target=create_forwarder, args=(cmd_port,), name='CmdForwarder')
        self.cmd_forwarder_process.start()

        self.msg_forwarder_process = Process(target=create_forwarder, args=(msg_port,), name='MsgForwarder')
        self.msg_forwarder_process.start()

        self.do_message_check = True
        self.cmd_queue = Queue()

        self.msg_publisher = PanMessaging('publisher', msg_port)

        def check_message_loop(cmd_queue):
            cmd_subscriber = PanMessaging('subscriber', cmd_port + 1)

            poller = zmq.Poller()
            poller.register(cmd_subscriber.subscriber, zmq.POLLIN)

            while self.do_message_check:
                # Poll for messages
                sockets = dict(poller.poll(500))  # 500 ms timeout

                if cmd_subscriber.subscriber in sockets and sockets[cmd_subscriber.subscriber] == zmq.POLLIN:

                    msg_type, msg_obj = cmd_subscriber.receive_message(flags=zmq.NOBLOCK)

                    # Put the message in a queue to be processed
                    if msg_type == 'POCS-CMD':
                        cmd_queue.put(msg_obj)

                time.sleep(1)

        self.logger.debug('Starting command message loop')
        self.check_messages_process = Process(target=check_message_loop, args=(self.cmd_queue,))
        self.check_messages_process.name = 'MessageCheckLoop'
        self.check_messages_process.start()
        self.logger.debug('Command message subscriber set up on port {}'.format(6501))
