import os
import signal
import sys
import warnings
import threading

from astropy.time import Time

from .utils.logger import has_logger
from .utils.config import load_config
from .utils.database import PanMongo
from .utils.indi import PanIndiServer
from .utils.messaging import PanMessaging
from .utils import error

from .observatory import Observatory
from .state_machine import PanStateMachine
from .weather import WeatherStationMongo, WeatherStationSimulator


@has_logger
class Panoptes(PanStateMachine):

    """ A Panoptes object is in charge of the entire unit.

    An instance of this object is responsible for total control
    of a PANOPTES unit. Has access to the observatory, state machine,
    a parameter server, and a messaging channel.

    Args:
        connect_on_startup: Controls whether unit should try to connect
            when object is created. Defaults to False
    """

    def __init__(self, state_machine_file='simple_state_table', *args, **kwargs):
        self.logger.info('*'*80)

        # Setup utils for graceful shutdown
        self.logger.info("Setting up interrupt handlers for state machine")
        signal.signal(signal.SIGINT, self._sigint_handler)

        if kwargs.get('simulator', False):
            self.logger.info("Using a simulator")
            self._is_simulator = True

        self.logger.info('Initializing PANOPTES unit')
        self.logger.info('Using default state machine file: {}'.format(state_machine_file))

        state_machine_table = PanStateMachine.load_state_table(state_table_name=state_machine_file)

        # Initialize the state machine. See `PanStateMachine` for details.
        super().__init__(**state_machine_table)

        self._check_environment()

        self.logger.info('Checking config')
        self.config = self._check_config(load_config())

        self.name = self.config.get('name', 'Generic PANOPTES Unit')
        self.logger.info('Setting up {}:'.format(self.name))

        # Setup the param server. Note: PanStateMachine should
        # set up the db first.
        self.logger.info('\t database connection')
        if not self.db:
            self.db = PanMongo()

        self.logger.info('\t INDI Server')
        self.indi_server = PanIndiServer()

        self.logger.info('\t messaging system')
        self.messaging = self._create_messaging()

        self.logger.info('\t weather station')
        self.weather_station = self._create_weather_station()

        # Create our observatory, which does the bulk of the work
        self.logger.info('\t observatory')
        self.observatory = Observatory(config=self.config)

        # Setting up automatic status check. Value is number of seconds between checks
        # Zero or negative values disable check
        self._check_status_delay = 5

        self.say("Hi!")


##################################################################################################
# Methods
##################################################################################################

    def say(self, msg):
        """ PANOPTES Units like to talk!

        Send a message. Message sent out through zmq has unit name as channel.

        Args:
            msg(str): Message to be sent
        """
        self.logger.info("{} says: {}".format(self.name, msg))
        self.messaging.send_message(self.name, msg)

    def power_down(self):
        """ Actions to be performed upon shutdown

        Note:
            This method is automatically called from the interrupt handler. The definition should
            include what you want to happen upon shutdown but you don't need to worry about calling
            it manually.
        """
        print("Shutting down, please be patient...")
        self.logger.info("Shutting down {}".format(self.name))

        if self.observatory.mount.is_connected:
            if not self.observatory.mount.is_parked:
                self.logger.info("Parking mount")
                self.observatory.mount.home_and_park()

        self.logger.info("Stopping INDI server")
        self.indi_server.stop()

        self.logger.info("Bye!")
        print("Thanks! Bye!")
        sys.exit(0)

    def check_status(self, daemon=False):
        """ Checks the status of the PANOPTES system.

        This method will gather status information from the entire unit for reporting purproses.

        Note:
            This method will automatically call itself after `_check_status_delay` seconds. Zero or
            negative values will cause automatic check to disable itself.
        """
        if self._check_status_delay:
            self.logger.debug("Checking status of unit")

            self.messaging.send_message("MOUNT", self.observatory.mount.status())

            if daemon:
                threading.Timer(self._check_status_delay, self.check_status).start()

    def is_dark(self):
        """ Is it dark

        Checks whether it is dark at the location provided. This checks for the config
        entry `location.horizon` or 18 degrees (astronomical twilight).

        Returns:
            bool:   Is night at location

        """
        horizon = self.observatory.location.get('horizon', 18)
        is_dark = self.observatory.scheduler.is_night(self.now(), horizon=horizon)

        self.logger.debug("Is dark: {}".format(is_dark))
        return is_dark

    def now(self):
        """ Convenience method to return the "current" time according to the system

        If the system is running in a simulator mode this returns the "current" now for the
        system, which does not necessarily reflect now in the real world. If not in a simulator
        mode, this simply returns `Time.now()`

        Returns:
            (astropy.time.Time):    `Time` object representing now.
        """
        now = Time.now()

        return now

##################################################################################################
# State Conditions
##################################################################################################

    def is_safe(self, *args, **kwargs):
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
        is_safe = list()

        # Check if night time
        is_safe.append(self.is_dark())

        # Check weather
        is_safe.append(self.weather_station.is_safe())

        if not all(is_safe):
            self.logger.warning('System is not safe')

        return all(is_safe) if not self._is_simulator else True

##################################################################################################
# Private Methods
##################################################################################################

    def _check_environment(self):
        """ Checks to see if environment is set up correctly

        There are a number of environmental variables that are expected
        to be set in order for PANOPTES to work correctly. This method just
        sanity checks our environment.

            POCS    Base directory for PANOPTES
        """
        if os.getenv('POCS') is None:
            warnings.warn('Please make sure $POCS environment variable is set')
            self.power_down()

    def _check_config(self, temp_config):
        """ Checks the config file for mandatory items """
        if 'name' in temp_config:
            self.logger.info('Welcome {}'.format(temp_config.get('name')))

        if 'base_dir' not in temp_config:
            raise error.InvalidConfig('base_dir must be specified in config_local.yaml')

        if 'mount' not in temp_config:
            raise error.MountNotFound('Mount must be specified in config')

        if 'state_machine' not in temp_config:
            raise error.InvalidConfig('State Table must be specified in config')

        return temp_config

    def _create_weather_station(self):
        """ Determines which weather station to create base off of config values """
        weather_station = None

        # Lookup appropriate weather stations
        station_lookup = {
            'simulator': WeatherStationSimulator,
            'mongo': WeatherStationMongo,
        }
        weather_module = station_lookup.get(self.config['weather']['station'], WeatherStationMongo)

        self.logger.debug('Creating weather station {}'.format(weather_module))

        try:
            weather_station = weather_module()
        except:
            raise error.PanError(msg="Weather station could not be created")

        return weather_station

    def _create_messaging(self):
        """ Creates a ZeroMQ messaging system """
        messaging = None

        self.logger.debug('Creating messaging')

        try:
            messaging = PanMessaging(publisher=True)
        except:
            raise error.PanError(msg="ZeroMQ could not be created")

        return messaging

    def _sigint_handler(self, signum, frame):
        """
        Interrupt signal handler. Designed to intercept a Ctrl-C from
        the user and properly shut down the system.
        """
        self.logger.error("Signal handler called with signal {}".format(signum))
        try:
            self.power_down()
        except Exception as e:
            self.logger.error("Problem powering down. PLEASE MANUALLY INSPECT THE MOUNT.")
            self.logger.error("Error: {}".format(e))
        finally:
            sys.exit(0)

    def __del__(self):
        self.power_down()
