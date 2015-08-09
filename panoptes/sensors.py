import os
import signal
import sys
import yaml

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from .utils.logger import has_logger
from .utils.config import load_config
from .utils.database import PanMongo
from .utils.messaging import Messaging

from .environment.weather_station import WeatherStation
from .environment.monitor import EnvironmentalMonitor
from .environment.webcams import Webcams

@has_logger
class PanSensors(object):

    """ Control the environmental sensors used for PANOPTES

    """

    def __init__(self, start_on_init=True):
        # Setup utils for graceful shutdown
        signal.signal(signal.SIGINT, self._sigint_handler)

        self.logger.info('*' * 80)
        self.logger.info('Initializing PANOPTES sensors')

        self.config = load_config()
        self.name = self.config.get('name', 'Generic')

        self.messaging = Messaging()

        self.logger.info('Setting up environmental monitoring')
        self.setup_monitoring()

        if start_on_init:
            self.logger.info('Starting environmental monitoring')
            self.start_monitoring()

    def setup_monitoring(self):
        """
        Starts all the environmental monitoring. This includes:
            * weather station
            * camera enclosure
            * computer enclosure
        """
        self.logger.debug("Inside setup_monitoring, creating sensors")
        self._create_weather_station_monitor()
        self._create_environmental_monitor()
        self._create_webcams_monitor()

    def start_monitoring(self):
        """ Starts all the environmental monitors
        """
        self.logger.info('Starting the environmental monitors')

        self.logger.info('\t weather station monitors')
        self.weather_station.start_monitoring()

        self.logger.info('\t environment monitors')
        self.environment_monitor.start_monitoring()

        self.logger.info('\t webcam monitors')
        self.webcams.start_capturing()

    def stop_monitoring(self):
        """ Shuts down the system

        Closes all the active threads that are listening.
        """
        self.logger.info("System is shutting down")

        # self.weather_station.stop()
        self.environment_monitor.stop_monitoring()
        self.webcams.stop_capturing()

##########################################################################
# Private Methods
##########################################################################

    def _create_weather_station_monitor(self):
        """
        This will create a weather station object
        """
        self.logger.info('Creating WeatherStation')
        self.weather_station = WeatherStation(
            messaging=self.messaging,
            config=self.config.get('weather'),
            name="{} WeatherStation".format(self.name)
        )
        self.logger.info("Weather station created")

    def _create_environmental_monitor(self):
        """
        This will create an environmental monitor instance which gets values
        from the serial.
        """
        self.logger.info('Creating Environmental Monitor')
        self.environment_monitor = EnvironmentalMonitor(
            config=self.config.get('environment'),
            name="{} Environmental Monitor".format(self.name),
            connect_on_startup=False
        )
        self.logger.info("Environmental monitor created")

    def _create_webcams_monitor(self):
        """ Start the external webcam processing loop

        Webcams run in a separate process. See `panoptes.environment.webcams`
        """
        self.webcams = Webcams()

    def _sigint_handler(self, signum, frame):
        """
        Interrupt signal handler. Designed to intercept a Ctrl-C from
        the user and properly shut down the system.
        """

        print("Signal handler called with signal ", signum)
        self.stop_monitoring()
        sys.exit(0)

    def __del__(self):
        self.stop_monitoring()

if __name__ == '__main__':
    sensors = PanSensors()
