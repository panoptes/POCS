from .utils.config import load_config
from .utils.logger import get_logger

from peas.webcams import Webcams


class PanCams(object):

    """ Control the environmental sensors used for PANOPTES

    """

    def __init__(self, start_on_init=False):
        self.logger = get_logger(self)
        self.logger.info('*' * 80)
        self.logger.info('Initializing PANOPTES webcams')

        self.config = load_config()
        self.name = self.config.get('name', 'Generic')

        self.logger.info('Setting up webcams')
        self.setup_webcams()

        if start_on_init:
            self.logger.info('Starting environmental monitoring')
            self.start_monitoring()

    def start_webcams(self):
        """ Starts all the environmental monitors
        """
        self.logger.info('Starting the webcams')
        self.webcams.start_capturing()

    def stop_monitoring(self):
        """ Shuts down the webcams """
        self.logger.info("Webcams are shutting down")
        self.webcams.stop_capturing()

    def setup_webcams(self):
        """ Setup webcams """

        config = {
            'webcams': self.config.get('webcams', []),
            'webcam_dir': self.config['directories'].get('webcam', '/var/panoptes/webcams/')
        }

        self.webcams = Webcams(config=config)

##########################################################################
# Private Methods
##########################################################################
