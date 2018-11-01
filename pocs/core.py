import os
import sys
import queue
import time
import warnings
import multiprocessing
import zmq
from contextlib import suppress

from astropy import units as u

from pocs.base import PanBase
from pocs.observatory import Observatory
from pocs.state.machine import PanStateMachine
from pocs.utils import current_time
from pocs.utils import get_free_space
from pocs.utils import CountdownTimer
from pocs.utils import listify
from pocs.utils import error
from pocs.utils.messaging import PanMessaging


class POCS(PanStateMachine, PanBase):

    """The main class representing the Panoptes Observatory Control Software (POCS).

    Interaction with a PANOPTES unit is done through instances of this class. An instance consists
    primarily of an `Observatory` object, which contains the mount, cameras, scheduler, etc.
    See `pocs.Observatory`. The observatory should create all attached hardware
    but leave the initialization up to POCS (i.e. this class will call the observatory
    `initialize` method).

    The POCS instance itself is designed to be run as a state machine via
    the `run` method.

    Args:
        observatory(Observatory): An instance of a `pocs.observatory.Observatory`
            class. POCS will call the `initialize` method of the observatory.
        state_machine_file(str): Filename of the state machine to use, defaults to
            'simple_state_table'.
        messaging(bool): If messaging should be included, defaults to False.
        simulator(list): A list of the different modules that can run in simulator mode. Possible
            modules include: all, mount, camera, weather, night. Defaults to an empty list.

    Attributes:
        name (str): Name of PANOPTES unit
        observatory (`pocs.observatory.Observatory`): The `~pocs.observatory.Observatory` object

    """

    def __init__(
            self,
            observatory,
            state_machine_file=None,
            messaging=False,
            **kwargs):

        # Explicitly call the base classes in the order we want
        PanBase.__init__(self, **kwargs)

        assert isinstance(observatory, Observatory)

        self.name = self.config.get('name', 'Generic PANOPTES Unit')
        self.logger.info('Initializing PANOPTES unit - {} - {}',
                         self.name,
                         self.config['location']['name']
                         )

        self._processes = {}

        self._has_messaging = None
        self.has_messaging = messaging

        self._sleep_delay = kwargs.get('sleep_delay', 2.5)  # Loop delay
        self._safe_delay = kwargs.get('safe_delay', 60 * 5)  # Safety check delay

        if state_machine_file is None:
            state_machine_file = self.config.get('state_machine', 'simple_state_table')

        PanStateMachine.__init__(self, state_machine_file, **kwargs)

        # Add observatory object, which does the bulk of the work
        self.observatory = observatory

        self._connected = True
        self._initialized = False
        self._interrupted = False
        self.force_reschedule = False

        self._retry_attempts = kwargs.get('retry_attempts', 3)
        self._obs_run_retries = self._retry_attempts

        self.status()

        self.say("Hi there!")

    @property
    def is_initialized(self):
        """ Indicates if POCS has been initalized or not """
        return self._initialized

    @property
    def interrupted(self):
        """If POCS has been interrupted

        Returns:
            bool: If an interrupt signal has been received
        """
        return self._interrupted

    @property
    def connected(self):
        """ Indicates if POCS is connected """
        return self._connected

    @property
    def has_messaging(self):
        return self._has_messaging

    @has_messaging.setter
    def has_messaging(self, value):
        self._has_messaging = value
        if self._has_messaging:
            self._setup_messaging()

    @property
    def should_retry(self):
        return self._obs_run_retries >= 0

##################################################################################################
# Methods
##################################################################################################

    def initialize(self):
        """Initialize POCS.

        Calls the Observatory `initialize` method.

        Returns:
            bool: True if all initialization succeeded, False otherwise.
        """

        if not self._initialized:
            self.logger.info('*' * 80)
            self.say("Initializing the system! Woohoo!")

            try:
                self.logger.debug("Initializing observatory")
                self.observatory.initialize()

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
            status['system'] = {
                'free_space': get_free_space().value,
            }
            status['observatory'] = self.observatory.status()
        except Exception as e:  # pragma: no cover
            self.logger.warning("Can't get status: {}".format(e))
        else:
            self.send_message(status, topic='STATUS')

        return status

    def say(self, msg):
        """ PANOPTES Units like to talk!

        Send a message.

        Args:
            msg(str): Message to be sent to topic PANCHAT.
        """
        if self.has_messaging is False:
            self.logger.info('Unit says: {}', msg)
        self.send_message(msg, topic='PANCHAT')

    def send_message(self, msg, topic='POCS'):
        """ Send a message

        This will use the `self._msg_publisher` to send a message

        Note:
            The `topic` and `msg` params are switched for convenience

        Arguments:
            msg {str} -- Message to be sent

        Keyword Arguments:
            topic {str} -- Topic to send message on (default: {'POCS'})
        """
        if self.has_messaging:
            self._msg_publisher.send_message(topic, msg)

    def check_messages(self):
        """ Check messages for the system

        If `self.has_messaging` is True then there is a separate process running
        responsible for checking incoming zeromq messages. That process will fill
        various `queue.Queue`s with messages depending on their type. This method
        is a thin-wrapper around private methods that are responsible for message
        dispatching based on which queue received a message.
        """
        if self.has_messaging:
            self._check_messages('command', self._cmd_queue)
            self._check_messages('schedule', self._sched_queue)

    def power_down(self):
        """Actions to be performed upon shutdown

        Note:
            This method is automatically called from the interrupt handler. The definition should
            include what you want to happen upon shutdown but you don't need to worry about calling
            it manually.
        """
        if self.connected:
            self.say("I'm powering down")
            self.logger.info(
                "Shutting down {}, please be patient and allow for exit.", self.name)

            if not self.observatory.close_dome():
                self.logger.critical('Unable to close dome!')

            # Park if needed
            if self.state not in ['parking', 'parked', 'sleeping', 'housekeeping']:
                # TODO(jamessynge): Figure out how to handle the situation where we have both
                # mount and dome, but this code is only checking for a mount.
                if self.observatory.mount.is_connected:
                    if not self.observatory.mount.is_parked:
                        self.logger.info("Parking mount")
                        self.park()

            if self.state == 'parking':
                if self.observatory.mount.is_connected:
                    if self.observatory.mount.is_parked:
                        self.logger.info("Mount is parked, setting Parked state")
                        self.set_park()

            if not self.observatory.mount.is_parked:
                self.logger.info('Mount not parked, parking')
                self.observatory.mount.park()

            # Observatory shut down
            self.observatory.power_down()

            # Shut down messaging
            self.logger.debug('Shutting down messaging system')

            for name, proc in self._processes.items():
                if proc.is_alive():
                    self.logger.debug('Terminating {} - PID {}'.format(name, proc.pid))
                    proc.terminate()

            self._keep_running = False
            self._do_states = False
            self._connected = False
            self.logger.info("Power down complete")

    def reset_observing_run(self):
        """Reset an observing run loop. """
        self.logger.debug("Resetting observing run attempts")
        self._obs_run_retries = self._retry_attempts

##################################################################################################
# Safety Methods
##################################################################################################

    def is_safe(self, no_warning=False):
        """Checks the safety flag of the system to determine if safe.

        This will check the weather station as well as various other environmental
        aspects of the system in order to determine if conditions are safe for operation.

        Note:
            This condition is called by the state machine during each transition

        Args:
            no_warning (bool, optional): If a warning message should show in logs,
                defaults to False.

        Returns:
            bool: Latest safety flag

        """
        if not self.connected:
            return False

        is_safe_values = dict()

        # Check if AC power connected and return immediately if not
        has_power = self.has_ac_power()
        if not has_power:
            return False

        is_safe_values['ac_power'] = has_power

        # Check if night time
        is_safe_values['is_dark'] = self.is_dark()

        # Check weather
        is_safe_values['good_weather'] = self.is_weather_safe()

        # Hard-drive space
        is_safe_values['free_space'] = self.has_free_space()

        safe = all(is_safe_values.values())

        if not safe:
            if no_warning is False:
                self.logger.warning('Unsafe conditions: {}'.format(is_safe_values))

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
        # See if dark - we check this first because we want to know
        # the sun position even if using a simulator.
        is_dark = self.observatory.is_dark

        # Check simulator
        with suppress(KeyError):
            if 'night' in self.config['simulator']:
                is_dark = True

        self.logger.debug("Dark Check: {}".format(is_dark))
        return is_dark

    def is_weather_safe(self, stale=180):
        """Determines whether current weather conditions are safe or not

        Args:
            stale (int, optional): Number of seconds before record is stale, defaults to 180

        Returns:
            bool: Conditions are safe (True) or unsafe (False)

        """

        # Always assume False
        self.logger.debug("Checking weather safety")
        is_safe = False

        # Check if we are using weather simulator
        with suppress(KeyError):
            if 'weather' in self.config['simulator']:
                self.logger.debug("Weather simulator always safe")
                return True

        # Get current weather readings from database
        try:
            record = self.db.get_current('weather')
            is_safe = record['data'].get('safe', False)

            timestamp = record['date'].replace(tzinfo=None)  # current_time is timezone naive
            age = (current_time().datetime - timestamp).total_seconds()

            self.logger.debug("Weather Safety: {} [{:.0f} sec old - {:%Y-%m-%d %H:%M:%S}]",
                              is_safe,
                              age,
                              timestamp)

        except (TypeError, KeyError) as e:
            self.logger.warning("No record found in DB: {}", e)
        except Exception as e:  # pragma: no cover
            self.logger.error("Error checking weather: {}", e)
        else:
            if age > stale:
                self.logger.warning("Weather record looks stale, marking unsafe.")
                is_safe = False

        return is_safe

    def has_free_space(self, required_space=0.25 * u.gigabyte):
        """Does hard drive have disk space (>= 0.5 GB)

        Args:
            required_space (u.gigabyte, optional): Amount of free space required
            for operation

        Returns:
            bool: True if enough space
        """
        free_space = get_free_space()
        return free_space.value >= required_space.to(u.gigabyte).value

    def has_ac_power(self, stale=90):
        """Check for system AC power.

        Power readings are done by the arduino and are placed in the metadata
        database. This method looks for entries saved with type `power` and key
        `main` the `current` collection. The method will also return False if
        the record is older than `stale` seconds.

        Args:
            stale (int, optional): Number of seconds before record is stale,
                defaults to 90 seconds.

        Returns:
            bool: True if system AC power is present.
        """
        # Always assume False
        self.logger.debug("Checking for AC power")
        has_power = False

        # TODO(wtgee): figure out if we really want to simulate no power
        # Check if we are using power simulator
        with suppress(KeyError):
            if 'power' in self.config['simulator']:
                self.logger.debug("AC power simulator always safe")
                return True

        # Get current power readings from database
        try:
            record = self.db.get_current('power')
            has_power = bool(record['data'].get('main', False))

            timestamp = record['date'].replace(tzinfo=None)  # current_time is timezone naive
            age = (current_time().datetime - timestamp).total_seconds()

            self.logger.debug("Power Safety: {} [{:.0f} sec old - {:%Y-%m-%d %H:%M:%S}]",
                              has_power,
                              age,
                              timestamp)

        except (TypeError, KeyError) as e:
            self.logger.warning("No record found in DB: {}", e)
        except Exception as e:  # pragma: no cover
            self.logger.error("Error checking weather: {}", e)
        else:
            if age > stale:
                self.logger.warning("Power record looks stale, marking unsafe.")
                has_power = False

        if not has_power:
            self.logger.critical('AC power not detected.')

        return has_power


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
            with_status {bool} -- Show system status while sleeping
                (default: {True if delay > 2.0})
        """
        if delay is None:
            delay = self._sleep_delay

        if with_status and delay > 2.0:
            self.status()

        # If delay is greater than 10 seconds check for messages during wait
        if delay >= 10.0:
            while delay >= 10.0:
                self.check_messages()
                # If we shutdown leave loop
                if self.connected is False:
                    return

                time.sleep(10.0)
                delay -= 10.0

        if delay > 0.0:
            time.sleep(delay)

    def wait_for_events(self,
                        events,
                        timeout,
                        sleep_delay=1 * u.second,
                        status_interval=10 * u.second,
                        msg_interval=30 * u.second,
                        event_type='generic'):
        """Wait for event(s) to be set.

        This method will wait for a maximum of `timeout` seconds for all of the
        `events` to complete.

        Will check at least every `sleep_delay` seconds for the events to be done,
        and also for interrupts and bad weather. Will log debug messages approximately
        every `status_interval` seconds, and will output status messages approximately
        every `msg_interval` seconds.

        Args:
            events (list(`threading.Event`)): An Event or list of Events to wait on.
            timeout (float|`astropy.units.Quantity`): Timeout in seconds to wait for events.
            sleep_delay (float, optional): Time in seconds between event checks.
            status_interval (float, optional): Time in seconds between status checks of the system.
            msg_interval (float, optional): Time in seconds between sending of status messages.
            event_type (str, optional): The type of event, used for outputting in log messages,
                default 'generic'.

        Raises:
            error.Timeout: Raised if events have not all been set before `timeout` seconds.
        """
        events = listify(events)

        # Remove units from these values.
        if isinstance(timeout, u.Quantity):
            timeout = timeout.to(u.second).value

        if isinstance(sleep_delay, u.Quantity):
            sleep_delay = sleep_delay.to(u.second).value

        # ADD units to these values. Ugly.
        if not isinstance(status_interval, u.Quantity):
            status_interval = status_interval * u.second

        if not isinstance(msg_interval, u.Quantity):
            msg_interval = msg_interval * u.second

        timer = CountdownTimer(timeout)

        start_time = current_time()
        next_status_time = start_time + status_interval
        next_msg_time = start_time + msg_interval

        while not all([event.is_set() for event in events]):
            self.check_messages()
            if self.interrupted:
                self.logger.info("Waiting for events has been interrupted")
                break

            now = current_time()
            if now >= next_msg_time:
                elapsed_secs = (now - start_time).to(u.second).value
                self.logger.debug('Waiting for {} events: {} seconds elapsed',
                                  event_type,
                                  round(elapsed_secs))
                next_msg_time += msg_interval
                now = current_time()

            if now >= next_status_time:
                self.status()
                next_status_time += status_interval
                now = current_time()

            if timer.expired():
                raise error.Timeout("Timedout waiting for {} event".format(event_type))

            # Sleep for a little bit.
            time.sleep(sleep_delay)

    def wait_until_safe(self):
        """ Waits until weather is safe.

        This will wait until a True value is returned from the safety check,
        blocking until then.
        """
        while not self.is_safe(no_warning=True):
            self.sleep(delay=self._safe_delay)

##################################################################################################
# Class Methods
##################################################################################################

    @classmethod
    def check_environment(cls):
        """ Checks to see if environment is set up correctly

        There are a number of environmental variables that are expected
        to be set in order for PANOPTES to work correctly. This method just
        sanity checks our environment and shuts down otherwise.

            PANDIR    Base directory for PANOPTES
            POCS      Base directory for POCS
        """
        if sys.version_info[:2] < (3, 0):  # pragma: no cover
            warnings.warn("POCS requires Python 3.x to run")

        pandir = os.getenv('PANDIR')
        if not os.path.exists(pandir):
            sys.exit("$PANDIR dir does not exist or is empty: {}".format(pandir))

        pocs = os.getenv('POCS')
        if pocs is None:  # pragma: no cover
            sys.exit('Please make sure $POCS environment variable is set')

        if not os.path.exists(pocs):
            sys.exit("$POCS directory does not exist or is empty: {}".format(pocs))

        if not os.path.exists("{}/logs".format(pandir)):
            print("Creating log dir at {}/logs".format(pandir))
            os.makedirs("{}/logs".format(pandir))

##################################################################################################
# Private Methods
##################################################################################################

    def _check_messages(self, queue_type, q):
        cmd_dispatch = {
            'command': {
                'park': self._interrupt_and_park,
                'shutdown': self._interrupt_and_shutdown,
            },
            'schedule': {}
        }

        while True:
            try:
                msg_obj = q.get_nowait()
                call_method = msg_obj.get('message', '')
                # Lookup and call the method
                self.logger.info('Message received: {} {}'.format(queue_type, call_method))
                cmd_dispatch[queue_type][call_method]()
            except queue.Empty:
                break
            except KeyError:
                pass
            except Exception as e:
                self.logger.warning('Problem calling method from messaging: {}'.format(e))
            else:
                break

    def _interrupt_and_park(self):
        self.logger.info('Park interrupt received')
        self._interrupted = True
        self.park()

    def _interrupt_and_shutdown(self):
        self.logger.warning('Shutdown command received')
        self._interrupted = True
        self.power_down()

    def _setup_messaging(self):

        cmd_port = self.config['messaging']['cmd_port']
        msg_port = self.config['messaging']['msg_port']

        def create_forwarder(port):
            try:
                PanMessaging.create_forwarder(port, port + 1)
            except Exception:
                pass

        cmd_forwarder_process = multiprocessing.Process(
            target=create_forwarder, args=(
                cmd_port,), name='CmdForwarder')
        cmd_forwarder_process.start()

        msg_forwarder_process = multiprocessing.Process(
            target=create_forwarder, args=(
                msg_port,), name='MsgForwarder')
        msg_forwarder_process.start()

        self._do_cmd_check = True
        self._cmd_queue = multiprocessing.Queue()
        self._sched_queue = multiprocessing.Queue()

        self._msg_publisher = PanMessaging.create_publisher(msg_port)

        def check_message_loop(cmd_queue):
            cmd_subscriber = PanMessaging.create_subscriber(cmd_port + 1)

            poller = zmq.Poller()
            poller.register(cmd_subscriber.socket, zmq.POLLIN)

            try:
                while self._do_cmd_check:
                    # Poll for messages
                    sockets = dict(poller.poll(500))  # 500 ms timeout

                    if cmd_subscriber.socket in sockets and \
                            sockets[cmd_subscriber.socket] == zmq.POLLIN:

                        topic, msg_obj = cmd_subscriber.receive_message(flags=zmq.NOBLOCK)

                        # Put the message in a queue to be processed
                        if topic == 'POCS-CMD':
                            cmd_queue.put(msg_obj)

                    time.sleep(1)
            except KeyboardInterrupt:
                pass

        self.logger.debug('Starting command message loop')
        check_messages_process = multiprocessing.Process(
            target=check_message_loop, args=(self._cmd_queue,))
        check_messages_process.name = 'MessageCheckLoop'
        check_messages_process.start()
        self.logger.debug('Command message subscriber set up on port {}'.format(cmd_port))

        self._processes = {
            'check_messages': check_messages_process,
            'cmd_forwarder': cmd_forwarder_process,
            'msg_forwarder': msg_forwarder_process,
        }
