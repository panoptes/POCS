import os
import sys
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
    _shared_state = {}  # See note below
    """ Shared base instance for all PANOPTES.

    This class acts as a Borg module (see Note below), insuring that multiple instances of
    the `Panoptes` class cooperatively control a single unit. Basically, the first time an
    instance is created the _shared_state variable is used and all other instances then also
    use that _shared_state (via the `self.__dict__`).


    """

    def __init__(self, simulator=[]):
        self.__dict__ = self._shared_state

        # If this is our first instance.
        if not hasattr(self, 'config') or self.config is None:

            self._check_environment()

            # Config
            self.config = self._check_config(load_config())

            # Simulator
            if 'all' in simulator:
                simulator = ['camera', 'mount', 'weather']
            self.config.setdefault('simulator', simulator)

            # Logger
            self.logger = get_root_logger()
            self.logger.info('*' * 80)
            self.logger.info('Initializing PANOPTES unit')

            self.name = self.config.get('name', 'Generic PANOPTES Unit')
            self.logger.info('Welcome {}!'.format(self.name))

        else:
            self.logger.info('Creating another instance of {}:'.format(self.name))


class Panoptes(PanBase, PanEventLogic, PanStateLogic, PanStateMachine):

    """ A Panoptes object is in charge of the entire unit.

    An instance of this object is responsible for total control
    of a PANOPTES unit. Has access to the observatory, state machine,
    a parameter server, and a messaging channel.

    Note:
        PANOPTES instances run as a collective for each unit. Hence, this module is really just a Borg module.
        This is similar to a Singleton but more effective.

        See https://www.safaribooksonline.com/library/view/python-cookbook/0596001673/ch05s23.html

    Args:
        state_machine_file(str):    Filename of the state machine to use, defaults to 'simple_state_table'
        simulator(list):            A list of the different modules that can run in simulator mode. Possible
            modules include: all, mount, camera, weather. Defaults to an empty list.

    """

    def __init__(self, state_machine_file='simple_state_table', simulator=[], **kwargs):

        # Explicitly call the base classes in the order we want
        PanBase.__init__(self, simulator)
        PanEventLogic.__init__(self, **kwargs)
        PanStateLogic.__init__(self, **kwargs)
        PanStateMachine.__init__(self, state_machine_file)

        # Setup the config
        if not hasattr(self, '_connected') or not self._connected:

            # Database
            if not self.db:
                self.logger.info('\t database connection')
                self.db = PanMongo()

            # Device Communication
            # self.logger.info('\t INDI Server')
            # self.indi_server = PanIndiServer()

            # Messaging
            self.logger.info('\t messaging system')
            self.messaging = self._create_messaging()

            # Weather
            self.logger.info('\t weather station')
            self.weather_station = self._create_weather_station()

            # Create our observatory, which does the bulk of the work
            self.logger.info('\t observatory')
            self.observatory = Observatory(config=self.config, **kwargs)

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
            self.logger.info("Shutting down {}, please be patient and allow for exit.".format(self.name))

            if self.state not in ['parked', 'sleeping']:
                if self.observatory.mount.is_connected:
                    if not self.observatory.mount.is_parked:
                        self.logger.info("Parking mount")
                        self.park()

            # self.logger.info("Stopping INDI server")
            # self.indi_server.stop()

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
        horizon = self.observatory.location.get('horizon', 12)
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

        if 'weather' in self.config['simulator']:
            self.logger.debug("Weather simluator always safe")
            safe = True

        if not safe:
            self.logger.warning('System is not safe')
            self.logger.warning('{}'.format(is_safe))

        return safe

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
        sanity checks our environment and shuts down otherwise.

            POCS    Base directory for PANOPTES
        """
        if os.getenv('POCS') is None:
            sys.exit('Please make sure $POCS environment variable is set')

    def _check_config(self, temp_config):
        """ Checks the config file for mandatory items """

        if 'directories' not in temp_config:
            raise error.InvalidConfig('directories must be specified in config_local.yaml')

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
