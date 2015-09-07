import os
import signal
import sys
import yaml
import warnings

from astropy.time import Time

# Append the POCS dir to the system path.
pocs_dir = os.getenv('POCS', os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(pocs_dir)

from .utils.logger import has_logger
from .utils.config import load_config
from .utils.database import PanMongo

from .state_machine import PanStateMachine
from .weather import WeatherStation
from .observatory import Observatory


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
        self.logger.info('*' * 80)
        self.logger.info('Initializing PANOPTES unit')
        self.logger.info('Using default state machine file: {}'.format(state_machine_file))

        state_machine_table = PanStateMachine.load_state_table(state_table_name=state_machine_file)

        # Initialize the state machine. See `PanStateMachine` for details.
        super().__init__(**state_machine_table)

        self._check_environment()

        self.logger.info('Checking config')
        self.config = load_config()
        self._check_config()

        # Setup the param server
        self.logger.info('Setting up database connection')
        self.db = PanMongo()

        self.logger.info('Setting up weather station')
        self.weather_station = WeatherStation()

        # Create our observatory, which does the bulk of the work
        self.logger.info('Setting up observatory')
        self.observatory = Observatory(config=self.config)

        if self.config.get('connect_on_startup', False):
            if hasattr(self, 'initialize'):
                self.initialize()


##################################################################################################
# Conditions
##################################################################################################
    def execute(self, event_data):
        """ Executes the main data for the state """
        self.logger.info("Inside {} state".format(event_data.state.name))

        try:
            next_state_name = event_data.state.main(self)
        except:
            self.logger.warning("Problem calling `main` for state {}".format(event_data.state.name))
            next_state_name = 'exit'

        if next_state_name in self._states:
            self.logger.info("{} returned {}".format(event_data.state.name, next_state_name))
            self.next_state = next_state_name
            self.prev_state = event_data.state.name

        if next_state_name == 'exit':
            self.logger.warning("Received exit signal")
            self.next_state = next_state_name
            self.prev_state = event_data.state.name

        self.logger.info("Next state is: {}".format(self.next_state))

    def weather_is_safe(self, event_data):
        """ Checks the safety flag of the weather

        Args:
            event_data(transitions.EventData): carries information about the event

        Returns:
            bool:   Latest safety flag of weather
        """
        is_safe = self.weather_station.check_conditions()
        self.logger.info("Weather Safe: {}".format(is_safe))

        if not is_safe:
            self.logger.info('Weather not safe, next state is parking')
            self.next_state = 'parking'

        return is_safe

    def is_dark(self, event_data):
        """ Is it dark

        Args:
            event_data(transitions.EventData): carries information about the event

        Returns:
            bool:   Is night at location

        """
        is_dark = self.observatory.is_night(Time.now())
        self.logger.info("Is Night: {}".format(is_dark))
        return is_dark


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
            self.shutdown()
            sys.exit(0)

    def _check_config(self):
        """ Checks the config file for mandatory items """
        if 'name' in self.config:
            self.logger.info('Welcome {}'.format(self.config.get('name')))

        if 'base_dir' not in self.config:
            raise error.InvalidConfig('base_dir must be specified in config_local.yaml')

        if 'mount' not in self.config:
            raise error.MountNotFound('Mount must be specified in config')

        if 'state_machine' not in self.config:
            raise error.InvalidConfig('State Table must be specified in config')
