from .utils.config import load_config
from .utils.logger import get_logger
from .utils.messaging import PanMessaging

from .environment.monitor import EnvironmentalMonitor
from .environment.webcams import Webcams


class PanSensors(object):

    """ Control the environmental sensors used for PANOPTES

    """

    def __init__(self, start_on_init=False):
        self.logger = get_logger(self)
        self.logger.info('*' * 80)
        self.logger.info('Initializing PANOPTES sensors')

        self.config = load_config()
        self.name = self.config.get('name', 'Generic')

        # self.logger.info('Setting up messaging')
        # self.messaging = PanMessaging()

        self.logger.info('Setting up environmental monitoring')
        self.setup_monitoring()

        if start_on_init:
            self.logger.info('Starting environmental monitoring')
            self.start_monitoring()

    def setup_monitoring(self):
        """
        Starts all the environmental monitoring. This includes:
            * camera enclosure
            * computer enclosure
        """
        self.logger.debug("Inside setup_monitoring, creating sensors")
        self._create_environmental_monitor()
        self._create_webcams_monitor()

    def start_monitoring(self):
        """ Starts all the environmental monitors
        """
        self.logger.info('Starting the environmental monitors')

        self.logger.info('\t environment monitors')
        self.environment_monitor.start_monitoring()

        self.logger.info('\t webcam monitors')
        # self.webcams.start_capturing()

    def stop_monitoring(self):
        """ Shuts down the system

        Closes all the active threads that are listening.
        """
        self.logger.info("System is shutting down")

        self.environment_monitor.stop_monitoring()
        self.webcams.stop_capturing()

##########################################################################
# Private Methods
##########################################################################

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

        config = {
            'webcams': self.config.get('webcams', []),
            'webcam_dir': self.config['directories'].get('webcam', '/var/panoptes/webcams/')
        }

        self.webcams = Webcams(config=config)
