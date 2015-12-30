import os
import sys
import warnings
import threading

from astropy.time import Time

from .utils.logger import get_root_logger
from .utils.config import load_config
from .utils.database import PanMongo
from .utils.indi import PanIndiServer
from .utils.messaging import PanMessaging
from .utils import error

from .observatory import Observatory
from .state.machine import PanStateMachine
from .state.logic import PanStateLogic
from .state.event import PanEventLogic
from .weather import WeatherStationMongo, WeatherStationSimulator


class PanBase(object):
    _shared_state = {}
    """ Shared base instance for all PANOPTES

    Note:
        PANOPTES instances run as a collective for each unit. Hence, this module is really just a Borg module.
        See https://www.safaribooksonline.com/library/view/python-cookbook/0596001673/ch05s23.html
    """

    def __init__(self, **kwargs):
        self.__dict__ = self._shared_state

        if not hasattr(self, '_connected'):

            self.logger = get_root_logger()
            self.logger.info('*' * 80)
            self.logger.info('Initializing PANOPTES unit')


class Panoptes(PanBase, PanEventLogic, PanStateLogic, PanStateMachine):

    """ A Panoptes object is in charge of the entire unit.

    An instance of this object is responsible for total control
    of a PANOPTES unit. Has access to the observatory, state machine,
    a parameter server, and a messaging channel.

    Args:
        connect_on_startup: Controls whether unit should try to connect
            when object is created. Defaults to False
    """

    def __init__(self, state_machine_file='simple_state_table', simulator=False, **kwargs):
        # Explicitly call the base classes in the order we want
        PanBase.__init__(self)
        PanEventLogic.__init__(self, **kwargs)
        PanStateLogic.__init__(self, **kwargs)
        PanStateMachine.__init__(self, state_machine_file)

        if not hasattr(self, '_connected'):

            self._check_environment()

            self.logger.debug('Loading config')
            self.config = self._check_config(load_config())

            if simulator:
                self.is_simulator = True
                self.config.setdefault('simulator', True)

            self.name = self.config.get('name', 'Generic PANOPTES Unit')
            self.logger.info('Setting up {}:'.format(self.name))

            # Setup the param server. Note: PanStateMachine should
            # set up the db first.
            if not self.db:
                self.logger.info('\t database connection')
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

            self._connected = True
            self._initialized = False

            self.say("Hi! I'm all set to go!")
        else:
            self.say("Howdy! I'm already running!")


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
        if self._connected:
            print("Shutting down, please be patient...")
            self.logger.info("Shutting down {}".format(self.name))

            if not self.state == 'sleeping':
                if self.observatory.mount.is_connected:
                    if not self.observatory.mount.is_parked:
                        self.logger.info("Parking mount")
                        self.park()

            self.logger.info("Stopping INDI server")
            self.indi_server.stop()

            self.logger.info("Bye!")
            print("Thanks! Bye!")

            self._connected = False

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
        is_safe = dict()

        # Check if night time
        is_safe['is_dark'] = self.is_dark()

        # Check weather
        is_safe['weather'] = self.weather_station.is_safe()

        safe = all(is_safe.values())

        if not safe and not self.is_simulator:
            self.logger.warning('System is not safe')
            self.logger.warning('{}'.format(is_safe))

        return safe if not self.is_simulator else True

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
