import os
import yaml
import zmq
import threading

from panoptes.utils import logger, config, param_server, messaging

import panoptes.observatory as observatory
import panoptes.state.statemachine as sm
import panoptes.environment.weather_station as weather
import panoptes.environment.camera_enclosure as camera_enclosure

@logger.has_logger
@config.has_config
class Panoptes(object):
    """ A Panoptes object is in charge of the entire unit.

    An instance of this object is responsible for total control
    of a PANOPTES unit. Has access to the observatory, state machine,
    a parameter server, and a messaging channel.

    Args:
        connect_on_startup: Controls whether unit should try to connect
            when object is created. Defaults to False
    """

    def __init__(self, connect_on_startup=False):
        # Setup utils
        self.logger.info('*' * 80)
        self.logger.info('Initializing panoptes unit')

        # Sanity check out config
        self._check_config()

        # Setup the param server
        self.param_server = param_server.ParamServer()

        # Setup the Messaging context
        self.messaging = messaging.Messaging()

        self.start_environment_monitoring()

        # Create our observatory, which does the bulk of the work
        # self.observatory = observatory.Observatory(connect_on_startup=connect_on_startup)

        # self.state_table = self._load_state_table()

        # Get our state machine
        # self.state_machine = self._setup_state_machine()

    def start_environment_monitoring(self):
        """
        Starts all the environmental monitoring. This includes:
            * weather station
            * camera enclosure
            * computer enclosure
        """
        self._create_weather_station()
        self._create_camera_enclosure()


    def _create_weather_station(self):
        """
        This will create a weather station object
        """
        self.logger.info('Creating WeatherStation')
        self.weather_station =  weather.WeatherStation(messaging=self.messaging)
        self.logger.info("Weather station created")

    def _create_camera_enclosure(self):
        """
        This will create a camera enclosure montitor
        """
        self.logger.info('Creating CameraEnclosure')
        self.camera_enclosure = camera_enclosure.CameraEnclosure(messaging=self.messaging)
        self.logger.info("CameraEnclosure created")


    def _check_config(self):
        if 'base_dir' not in self.config:
            raise error.InvalidConfig('base_dir must be specified in config_local.yaml')

        if 'name' in self.config:
            self.logger.info('Welcome {}'.format(self.config.get('name')))

        if 'mount' not in self.config:
            raise error.MountNotFound('Mount must be specified in config')

        if 'state_machine' not in self.config:
            raise error.InvalidConfig('State Table must be specified in config')


    def _load_state_table(self):
        # Get our state table
        state_table_name = self.config.get('state_machine', 'simple_state_table')

        state_table_file = "{}/resources/state_table/{}.yaml".format(self.config.get('base_dir'),state_table_name)

        state_table = dict()

        try:
            with open(state_table_file, 'r') as f:
                state_table = yaml.load(f.read())
        except OSError as err:
            raise error.InvalidConfig('Problem loading state table yaml file: {}'.format(err))
        except:
            raise error.InvalidConfig('Problem loading state table yaml file: {}'.format())

        return state_table


    def _setup_state_machine(self):
        """
        Sets up the state machine including defining all the possible states.
        """
        # Create the machine
        machine = sm.StateMachine(self.observatory, self.state_table)

        return machine


    def shutdown(self):
        """ Shuts down the system """
        self.logger.info("Taking down the system...")
        self.weather_station.stop()


    def __del__(self):
        """
        Takes down the program
        """
        self.shutdown()
