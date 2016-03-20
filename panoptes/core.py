import os
import sys

from astropy import units as u

from .utils.logger import get_root_logger
from .utils.config import load_config
from .utils.database import PanMongo
from .utils.messaging import PanMessaging
# from .utils.indi import PanIndiServer
from .utils import error

from .observatory import Observatory
from .state.machine import PanStateMachine
from .state.logic import PanStateLogic
from .state.event import PanEventManager
from .weather import WeatherStationMongo, WeatherStationSimulator


class PanBase(object):
    _shared_state = {}  # See note below
    """ Shared base instance for all PANOPTES.

    This class acts as a Borg module (see Note below), insuring that multiple instances of
    the `Panoptes` class cooperatively control a single unit. Basically, the first time an
    instance is created the _shared_state variable is used and all other instances then also
    use that _shared_state (via the `self.__dict__`).

    Note:
        PANOPTES instances run as a collective for each unit. Hence, this module is really just a Borg module.
        This is similar to a Singleton but more effective.

        See https://www.safaribooksonline.com/library/view/python-cookbook/0596001673/ch05s23.html

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


class Panoptes(PanStateMachine, PanStateLogic, PanEventManager, PanBase):

    """ The main class representing a PANOPTES unit.

    Interaction with a PANOPTES unit is done through instances of this class. An instance consists
    primarily of an `Observatory` object, which contains the mount, cameras, scheduler, etc.
    See `panoptes.Observatory`. The instance itself is designed to be run as a state machine with
    the `get_ready()` method the transition that is responsible for moving to the initial state.

    Args:
        state_machine_file(str):    Filename of the state machine to use, defaults to 'simple_state_table'
        simulator(list):            A list of the different modules that can run in simulator mode. Possible
            modules include: all, mount, camera, weather. Defaults to an empty list.

    """

    def __init__(self, state_machine_file='simple_state_table', simulator=[], **kwargs):

        # Explicitly call the base classes in the order we want
        PanBase.__init__(self, simulator)
        PanEventManager.__init__(self, **kwargs)
        PanStateLogic.__init__(self, **kwargs)
        PanStateMachine.__init__(self, state_machine_file, **kwargs)

        # Setup the config
        if not hasattr(self, '_connected') or not self._connected:

            # Database
            if not self.db:
                self.logger.info('\t database connection')
                self.db = PanMongo()

            # Remove logger information from config
            del self.config['logger']
            self.db.insert_current('config', self.config)

            # Device Communication
            # self.logger.info('\t INDI Server')
            # self.indi_server = PanIndiServer()

            # Messaging
            # self.logger.info('\t messaging system')
            # self.messaging = self._create_messaging()

            # Weather
            self.logger.info('\t weather station')
            self.weather_station = self._create_weather_station()

            # Create our observatory, which does the bulk of the work
            self.logger.info('\t observatory')
            self.observatory = Observatory(config=self.config, **kwargs)

            self._connected = True
            self._initialized = False

            # This should all move to the `states.pointing` module
            point_config = self.config.get('pointing', {})
            self._max_iterations = point_config.get('max_iterations', 3)
            self._pointing_exptime = point_config.get('exptime', 30) * u.s
            self._pointing_threshold = point_config.get('threshold', 0.01) * u.deg
            self._pointing_iteration = 0

            self.say("Hi there!")
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

    def power_down(self):
        """ Actions to be performed upon shutdown

        Note:
            This method is automatically called from the interrupt handler. The definition should
            include what you want to happen upon shutdown but you don't need to worry about calling
            it manually.
        """
        if self._connected:
            self.logger.info("Shutting down {}, please be patient and allow for exit.".format(self.name))

            if self.state not in ['parking', 'parked', 'sleeping', 'housekeeping']:
                if self.observatory.mount.is_connected:
                    if not self.observatory.mount.is_parked:
                        self.logger.info("Parking mount")
                        self.park()

            if self.state == 'parking':
                if self.observatory.mount.is_connected:
                    if not self.observatory.mount.is_parked:
                        self.logger.info("Parking mount")
                        self.set_park()

            # Stop the monitors
            self.observatory.power_down()

            self.logger.info("Bye!")
            print("Thanks! Bye!")

            # Remove shutdown file
            if os.path.exists(self._shutdown_file):
                os.unlink(self._shutdown_file)

            self._connected = False

    def check_mount_status(self):
        """ Checks the status of the PANOPTES system.

        This method will gather status information from the entire unit for reporting purproses.
        """
        mount_status = {}
        try:
            mount_status = self.observatory.mount.status()
            self.db.insert_current('mount', mount_status)

        except Exception as e:
            self.logger.warning("Can't get status: {}".format(e))

        return mount_status

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
        pocs = os.getenv('POCS')
        if pocs is None:
            sys.exit('Please make sure $POCS environment variable is set')

        self._shutdown_file = os.path.join(pocs, 'shutdown')

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
