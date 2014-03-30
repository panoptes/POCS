#!/usr/bin/env python

import ephem

import panoptes.utils.logger as logger
import panoptes.observatory as observatory

class Panoptes:
    """
    Sets up logger, reads config file and starts up application.
    """
    def __init__(self):
        # Setup utils
        self.logger = logger.Logger()

        self.logger.info('Initializing panoptes')
    
        # Create our observatory, which does the bulk of the work
        # NOTE: Here we would pass in config options
        self.observatory = observatory.Observatory( logger=self.logger )
        
    def start_session(self):
        """
        Main starting point for panoptes application
        """
        self.observatory.start_observing()


if __name__ == '__main__':
    panoptes = Panoptes()
    panoptes.logger.info("Panoptes created. Starting session")
    # panoptes.start_session()