import ephem
import yaml

import panoptes.utils.logger as logger
import panoptes.utils.config as config
import panoptes.observatory as observatory

@config.has_config
@logger.do_logging
class Panoptes:

    """
    Base class for our unit. This is inherited by *every* object and is just
    used to set some base items for the application. Sets up logger, reads
    config file and starts up application.
    """

    def __init__(self):
        # Setup utils
        self.logger.info('Initializing panoptes unit')

        # This is mostly for debugging
        if 'name' in self.config:
            self.logger.info('Welcome {}'.format(self.config.get('name')))

        # Create our observatory, which does the bulk of the work
        # NOTE: Here we would pass in config options
        self.observatory = observatory.Observatory()

    def start_session(self):
        """
        Main starting point for panoptes application
        """
        self.observatory.start_observing()


if __name__ == '__main__':
    panoptes = Panoptes()
    panoptes.logger.info("Panoptes created. Starting session")
    # panoptes.start_session()
