import ephem
import yaml

import panoptes.utils.logger as logger
import panoptes.observatory as observatory

@logger.do_logging
class Panoptes:

    """
    Base class for our unit. This is inherited by *every* object and is just
    used to set some base items for the application. Sets up logger, reads
    config file and starts up application.
    """

    def __init__(self, config_file='config.yaml'):
        # Setup utils
        self.logger.info('Initializing panoptes unit')

        self.config = self._config(config_file)

        # This is mostly for debugging
        if 'name' in self.config:
            self.logger.info('Welcome {}'.format(self.config.get('name')))

        # Create our observatory, which does the bulk of the work
        # NOTE: Here we would pass in config options
        self.observatory = observatory.Observatory(logger=self.logger)

    def _config(self, config_file='panoptes_config.yaml'):
        """
        Reads the yaml config file and returns
        """
        config = dict()
        with open(config_file, 'r') as f:
            config = yaml.load(f.read())

        self.logger.info('Using parameters from config file')
        return config

    def start_session(self):
        """
        Main starting point for panoptes application
        """
        self.observatory.start_observing()


if __name__ == '__main__':
    panoptes = Panoptes()
    panoptes.logger.info("Panoptes created. Starting session")
    # panoptes.start_session()
