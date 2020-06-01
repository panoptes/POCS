import os
import sys
import warnings
from threading import Thread
from contextlib import suppress

from astropy import units as u

from panoptes.pocs.base import PanBase
from panoptes.pocs.observatory import Observatory
from panoptes.pocs.state.machine import PanStateMachine
from panoptes.utils import current_time
from panoptes.utils import get_free_space
from panoptes.utils import CountdownTimer


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
            *args, **kwargs):

        # Explicitly call the base classes in the order we want
        PanBase.__init__(self, *args, **kwargs)

        assert isinstance(observatory, Observatory)

        self.name = self.get_config('name', default='Generic PANOPTES Unit')
        location = self.get_config('location.name', default='Unknown location')
        self.logger.info(f'Initializing PANOPTES unit - {self.name} - {location}')

        if state_machine_file is None:
            state_machine_file = self.get_config('state_machine', default='simple_state_table')

        self.logger.info(f'Making a POCS state machine from {state_machine_file}')
        PanStateMachine.__init__(self, state_machine_file, **kwargs)

        # Add observatory object, which does the bulk of the work
        self.observatory = observatory

        self.is_initialized = False
        self._free_space = None

        self._obs_run_retries = self.get_config('pocs.RETRY_ATTEMPTS', default=3)

        # We want to call and record the status on a periodic interval.
        def get_status():
            while True:
                status = self.status
                self.logger.debug(f'Periodic status call: {status!r}')
                self.db.insert_current('status', status)
                CountdownTimer(self.get_config('status_check_interval', default=60)).sleep()

        self._status_thread = Thread(target=get_status, daemon=True)
        self._status_thread.start()

        self.connected = True
        self.say("Hi there!")

    @property
    def is_initialized(self):
        """ Indicates if POCS has been initialized or not """
        return self.get_config('pocs.INITIALIZED', default=False)

    @is_initialized.setter
    def is_initialized(self, new_value):
        self.set_config('pocs.INITIALIZED', new_value)

    @property
    def interrupted(self):
        """If POCS has been interrupted.

        Returns:
            bool: If an interrupt signal has been received
        """
        return self.get_config('pocs.INTERRUPTED', default=False)

    @interrupted.setter
    def interrupted(self, new_value):
        self.set_config('pocs.INTERRUPTED', new_value)
        if new_value:
            self.logger.critical(f'POCS has been interrupted')

    @property
    def connected(self):
        """ Indicates if POCS is connected """
        return self.get_config('pocs.CONNECTED', default=False)

    @connected.setter
    def connected(self, new_value):
        self.set_config('pocs.CONNECTED', new_value)

    @property
    def keep_running(self):
        return self.get_config('pocs.KEEP_RUNNING', default=True)

    @keep_running.setter
    def keep_running(self, new_value):
        self.set_config('pocs.KEEP_RUNNING', new_value)

    @property
    def do_states(self):
        return self.get_config('pocs.DO_STATES', default=True)

    @do_states.setter
    def do_states(self, new_value):
        self.set_config('pocs.DO_STATES', new_value)

    @property
    def run_once(self):
        return self.get_config('pocs.RUN_ONCE', default=False)

    @run_once.setter
    def run_once(self, new_value):
        self.set_config('pocs.RUN_ONCE', new_value)

    @property
    def should_retry(self):
        return self._obs_run_retries >= 0

    @property
    def status(self):
        status = dict()

        try:
            status['state'] = self.state
            status['system'] = {
                'free_space': str(self._free_space),
            }
            status['observatory'] = self.observatory.status
        except Exception as e:  # pragma: no cover
            self.logger.warning(f"Can't get status: {e!r}")

        return status

    ##################################################################################################
    # Methods
    ##################################################################################################

    def initialize(self):
        """Initialize POCS.

        Calls the Observatory `initialize` method.

        Returns:
            bool: True if all initialization succeeded, False otherwise.
        """

        if not self.is_initialized:
            self.logger.info('*' * 80)
            self.say("Initializing the system! Woohoo!")

            try:
                self.logger.debug("Initializing observatory")
                self.observatory.initialize()

            except Exception as e:
                self.say(f"Oh wait. There was a problem initializing: {e!r}")
                self.say("Since we didn't initialize, I'm going to exit.")
                self.power_down()
            else:
                self.is_initialized = True

        return self.is_initialized

    def say(self, msg):
        """ PANOPTES Units like to talk!

        Send a message.

        Args:
            msg(str): Message to be sent to topic PANCHAT.
        """
        self.logger.success(f'Unit says: {msg}')

    def power_down(self):
        """Actions to be performed upon shutdown

        Note:
            This method is automatically called from the interrupt handler. The definition should
            include what you want to happen upon shutdown but you don't need to worry about calling
            it manually.
        """
        if self.connected:
            self.say("I'm powering down")
            self.logger.info(f'Shutting down {self.name}, please be patient and allow for exit.')

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
                        self.logger.info("Mount is parked, setting state to 'parked'")
                        self.set_park()

            if self.observatory.mount and self.observatory.mount.is_parked is False:
                self.logger.info('Mount not parked, parking')
                self.observatory.mount.park()

            # Observatory shut down
            self.observatory.power_down()

            self.keep_running = True
            self.do_states = True
            self.is_initialized = False
            self.interrupted = False
            self.connected = False

            # Clear all the config items.
            self.logger.info("Power down complete")

    def reset_observing_run(self):
        """Reset an observing run loop. """
        self.logger.debug("Resetting observing run attempts")
        self._obs_run_retries = self.get_config('pocs.RETRY_ATTEMPTS', default=3)

    ##################################################################################################
    # Safety Methods
    ##################################################################################################

    def is_safe(self, no_warning=False, horizon='observe'):
        """Checks the safety flag of the system to determine if safe.

        This will check the weather station as well as various other environmental
        aspects of the system in order to determine if conditions are safe for operation.

        Note:
            This condition is called by the state machine during each transition

        Args:
            no_warning (bool, optional): If a warning message should show in logs,
                defaults to False.
            horizon (str, optional): For night time check use given horizon,
                default 'observe'.
        Returns:
            bool: Latest safety flag.

        """
        if not self.connected:
            return False

        is_safe_values = dict()

        # Check if AC power connected and return immediately if not.
        has_power = self.has_ac_power()
        if not has_power:
            return False

        is_safe_values['ac_power'] = has_power

        # Check if night time
        is_safe_values['is_dark'] = self.is_dark(horizon=horizon)

        # Check weather
        is_safe_values['good_weather'] = self.is_weather_safe()

        # Hard-drive space
        is_safe_values['free_space'] = self.has_free_space()

        safe = all(is_safe_values.values())

        # Insert safety reading
        self.db.insert_current('safety', is_safe_values)

        if not safe:
            if no_warning is False:
                self.logger.warning(f'Unsafe conditions: {is_safe_values}')

            # These states are already "parked" so don't send to parking.
            safe_states = [
                'parked',
                'parking',
                'sleeping',
                'housekeeping',
                'ready'
            ]
            if self.state not in safe_states:
                self.logger.warning('Safety failed so sending to park')
                self.park()

        return safe

    def is_dark(self, horizon='observe'):
        """Is it dark

        Checks whether it is dark at the location provided. This checks for the config
        entry `location.flat_horizon` by default.

        Args:
            horizon (str, optional): Which horizon to use, 'flat''focus', or
                'observe' (default).

        Returns:
            bool: Is sun below horizon at location
        """
        # See if dark - we check this first because we want to know
        # the sun position even if using a simulator.
        is_dark = self.observatory.is_dark(horizon=horizon)
        self.logger.debug(f'Observatory is_dark: {is_dark}')

        # Check simulator
        with suppress(KeyError):
            if 'night' in self.get_config('simulator', default=[]):
                self.logger.debug(f'Using night simulator')
                is_dark = True

        self.logger.debug(f"Dark Check: {is_dark}")
        return is_dark

    def is_weather_safe(self, stale=180):
        """Determines whether current weather conditions are safe or not.

        Args:
            stale (int, optional): Number of seconds before record is stale, defaults to 180

        Returns:
            bool: Conditions are safe (True) or unsafe (False)

        """

        # Always assume False
        self.logger.debug("Checking weather safety")
        is_safe = False

        # Check if we are using weather simulator
        simulator_values = self.get_config('simulator', default=[])
        if len(simulator_values):
            self.logger.debug(f'simulator_values: {simulator_values}')

        if 'weather' in simulator_values:
            self.logger.info("Weather simulator always safe")
            return True

        # Get current weather readings from database
        try:
            record = self.db.get_current('weather')
            if record is None:
                return False

            is_safe = record['data'].get('safe', False)

            timestamp = record['date'].replace(tzinfo=None)  # current_time is timezone naive
            age = (current_time().datetime - timestamp).total_seconds()

            self.logger.debug(f"Weather Safety: {is_safe} [{age:.0f} sec old - {timestamp:%Y-%m-%d %H:%M:%S}]")

        except (TypeError, KeyError) as e:
            self.logger.warning(f"No record found in DB: {e!r}")
        except Exception as e:  # pragma: no cover
            self.logger.error(f"Error checking weather: {e!r}")
        else:
            if age >= stale:
                self.logger.warning("Weather record looks stale, marking unsafe.")
                is_safe = False

        return is_safe

    def has_free_space(self, required_space=0.25 * u.gigabyte, low_space_percent=1.5):
        """Does hard drive have disk space (>= 0.5 GB).

        Args:
            required_space (u.gigabyte, optional): Amount of free space required
                for operation
            low_space_percent (float, optional): Give warning if space is less
                than this times the required space, default 1.5, i.e.,
                the logs will show a warning at `.25 GB * 1.5 = 0.375 GB`.

        Returns:
            bool: True if enough space
        """
        req_space = required_space.to(u.gigabyte)
        self._free_space = get_free_space()

        space_is_low = self._free_space.value <= (req_space.value * low_space_percent)

        # Explicitly cast to bool (instead of numpy.bool)
        has_space = bool(self._free_space.value >= req_space.value)

        if not has_space:
            self.logger.error(f'No disk space: Free {self._free_space:.02f}\tReq: {req_space:.02f}')
        elif space_is_low:
            self.logger.warning(f'Low disk space: Free {self._free_space:.02f}\tReq: {req_space:.02f}')

        return has_space

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
        simulator_values = self.get_config('simulator', default=[])
        if 'power' in simulator_values:
            self.logger.debug("AC power simulator always safe")
            return True

        # Get current power readings from database
        try:
            record = self.db.get_current('power')
            if record is None:
                self.logger.warning(f'No mains "power" reading found in database.')

            has_power = False  # Assume not
            for power_key in ['main', 'mains']:  # Legacy control boards have `main`.
                with suppress(KeyError):
                    has_power = bool(record['data'][power_key])

            timestamp = record['date'].replace(tzinfo=None)  # current_time is timezone naive
            age = (current_time().datetime - timestamp).total_seconds()

            self.logger.debug(f"Power Safety: {has_power} [{age:.0f} sec old - {timestamp:%Y-%m-%d %H:%M:%S}]")

        except (TypeError, KeyError) as e:
            self.logger.warning(f"No record found in DB: {e!r}")
        except Exception as e:  # pragma: no cover
            self.logger.error(f"Error checking weather: {e!r}")
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

    def wait(self, delay=None):
        """ Send POCS to wait.

        Loops for `delay` number of seconds. If `delay` is more than 30.0 seconds,
        then check for status signals (which are updated every 60 seconds by default).

        Keyword Arguments:
            delay {float|None} -- Number of seconds to wait. If default `None`, look up value in
                config, otherwise 2.5 seconds.
        """
        if delay is None:
            delay = self.get_config('wait_delay', default=2.5)

        sleep_timer = CountdownTimer(delay)
        self.logger.info(f'Starting a wait timer of {delay} seconds')
        while not sleep_timer.expired() and not self.interrupted:
            self.logger.debug(f'Wait timer: {sleep_timer.time_left():.02f} / {delay:.02f}')
            sleep_timer.sleep(max_sleep=30)

        is_expired = sleep_timer.expired()
        self.logger.debug(f'Leaving wait timer: expired={is_expired}')
        return is_expired

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
            sys.exit(f"$PANDIR dir does not exist or is empty: {pandir}")

        pocs = os.getenv('POCS')
        if pocs is None:  # pragma: no cover
            sys.exit('Please make sure $POCS environment variable is set')

        if not os.path.exists(pocs):
            sys.exit(f"$POCS directory does not exist or is empty: {pocs}")

        if not os.path.exists(f"{pandir}/logs"):
            print(f"Creating log dir at {pandir}/logs")
            os.makedirs(f"{pandir}/logs")
