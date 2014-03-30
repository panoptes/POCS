#!/usr/bin/env python

import ephem
import yaml

import panoptes.observatory as observatory
import panoptes.utils.logger as logger

@logger.do_logging
class Panoptes:
    """
    Sets up logger, reads config file and starts up application.
    """
    def __init__(self, config_file='config.yaml'):
        self.logger.info('Initializing panoptes')

        with open(config_file, 'r') as f:
            self.config = json.dump(f.read())

        if self.config:
            if self.config.get('name'): self.logger.info('Welcome'.format(name))
            self.logger.info('Using parameters from config file')
    
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