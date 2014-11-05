import os
import signal
import sys
import yaml
import zmq
import threading

from panoptes.utils import logger, config, param_server, messaging, error

import panoptes.observatory as observatory
import panoptes.state.statemachine as sm
import panoptes.environment.weather_station as weather
import panoptes.environment.camera_enclosure as camera_enclosure

import panoptes.scheduler as scheduler


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
        signal.signal(signal.SIGINT, self._sigint_handler)

        self.logger.info('*' * 80)
        self.logger.info('Initializing panoptes unit')

        # Sanity check out config
        self.logger.info('Checking config')
        self._check_config()

        # Setup the param server
        self.logger.info('Setting up global parameter server')
        self.param_server = param_server.ParamServer()

        # Setup the Messaging context
        self.logger.info('Setting up messaging')
        self.messaging = messaging.Messaging()

        # Environmental monitors
        self.logger.info('Setting up environmental monitoring')
        self.setup_environment_monitoring()

        # Create our observatory, which does the bulk of the work
        self.logger.info('Setting up observatory')
        self.observatory = observatory.Observatory()

        self.logger.info('Setting up scheduler')
        self.scheduler = scheduler.Scheduler(
            target_list_file=os.path.join(self.config['base_dir'], 'default_targets.yaml'))

        self.logger.info('Loading state table')
        self.state_table = self._load_state_table()

        # Get our state machine
        self.logger.info('Setting up state machine')
        self.state_machine = self._setup_state_machine()

        if connect_on_startup:
            self.start_environment_monitoring()

    def setup_environment_monitoring(self):
        """
        Starts all the environmental monitoring. This includes:
            * weather station
            * camera enclosure
            * computer enclosure
        """
        self._create_weather_station_monitor()
        self._create_camera_enclosure_monitor()
        self._create_computer_enclosure_monitor()

    def start_environment_monitoring(self):
        """ Starts all the environmental monitors
        """
        self.logger.info('Starting the environmental monitors...')

        self.logger.info('\t camera enclosure monitors')
        self.camera_enclosure.start_monitoring()
        
        self.logger.info('\t weather station monitors')
        self.weather_station.start_monitoring()

    def shutdown(self):
        """ Shuts down the system

        Closes all the active threads that are listening.
        """
        self.logger.info("System is shutting down")
        self.weather_station.stop()

        # Close down all active threads
        for thread in threading.enumerate():
            if thread != threading.main_thread():
                self.logger.info('Stopping thread {}'.format(thread.name))
                thread.stop()

    def _create_weather_station_monitor(self):
        """
        This will create a weather station object
        """
        self.logger.info('Creating WeatherStation')
        self.weather_station = weather.WeatherStation(messaging=self.messaging)
        self.logger.info("Weather station created")

    def _create_camera_enclosure_monitor(self):
        """
        This will create a camera enclosure montitor
        """
        self.logger.info('Creating CameraEnclosure')
        self.camera_enclosure = camera_enclosure.CameraEnclosure(messaging=self.messaging)
        self.logger.info("CameraEnclosure created")

    def _create_computer_enclosure_monitor(self):
        """
        This will create a computer enclosure montitor
        """
        pass

    def _check_config(self):
        if 'name' in self.config:
            self.logger.info('Welcome {}'.format(self.config.get('name')))

        if 'base_dir' not in self.config:
            raise error.InvalidConfig('base_dir must be specified in config_local.yaml')

        if 'mount' not in self.config:
            raise error.MountNotFound('Mount must be specified in config')

        if 'state_machine' not in self.config:
            raise error.InvalidConfig('State Table must be specified in config')

    def _load_state_table(self):
        # Get our state table
        state_table_name = self.config.get('state_machine', 'simple_state_table')

        state_table_file = "{}/resources/state_table/{}.yaml".format(self.config.get('base_dir'), state_table_name)

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

    def _sigint_handler(self, signum, frame):
        """
        Interrupt signal handler. Designed to intercept a Ctrl-C from
        the user and properly shut down the system.
        """

        print("Signal handler called with signal ", signum)
        self.shutdown()
        sys.exit(0)
