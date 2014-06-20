# -*- coding: utf-8 -*-
"""POCS is a the Panoptes Observatory Control System

* Documentation: http://panoptes-pocs.readthedocs.org/
* Source Code: https://github.com/panoptes/POCS
"""

import panoptes.utils.logger as logger
import panoptes.utils.config as config
import panoptes.utils.error as error

import panoptes.observatory as observatory

from panoptes.state import StateMachine, State

@logger.has_logger
@config.has_config
class Panoptes(object):

    """
    This class is a driver program that holds a :py:class:`panoptes.Observatory`
    """

    def __init__(self):
        # Setup utils
        self.logger.info('Initializing panoptes unit')

        # This is mostly for debugging
        if 'name' in self.config:
            self.logger.info('Welcome {}'.format(self.config.get('name')))

        if 'mount' not in self.config:
            raise error.MountNotFound('Mount must be specified in config')

        # Create our observatory, which does the bulk of the work
        # NOTE: Here we would pass in config options
        self.observatory = observatory.Observatory()

        self.machine = StateMachine()
        self.machine.add_state('start', self.observatory.initialize)
        self.machine.add_state('park', self.observatory.park)
        self.machine.add_state('stop', self.observatory.park, end_state=1)

        self.machine.set_start('start')

    def start_session(self):
        """
        Main starting point for panoptes application
        """
        while self.observatory.is_available:
            self.logger.info("Beginning new visit")
    
            self.machine.run(self.observatory)
        

if __name__ == '__main__':
    panoptes = Panoptes()
    panoptes.logger.info("Panoptes created. Starting session")
