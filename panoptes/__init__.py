# -*- coding: utf-8 -*-
"""POCS is a the Panoptes Observatory Control System

* Documentation: http://panoptes-pocs.readthedocs.org/
* Source Code: https://github.com/panoptes/POCS
"""
import os
import yaml

import panoptes.utils.logger as logger
import panoptes.utils.config as config
import panoptes.utils.error as error

import panoptes.observatory as observatory

from panoptes.state import StateMachine

@logger.has_logger
@config.has_config
class Panoptes(object):

    """
    This class is a driver program that holds a :py:class:`panoptes.Observatory`
    """

    def __init__(self):
        # Setup utils
        self.logger.info('*'*80)
        self.logger.info('Initializing panoptes unit')

        # This is mostly for debugging
        if 'base_dir' not in self.config:
            raise error.InvalidConfig('base_dir must be specified in config_local.yaml')

        if 'name' in self.config:
            self.logger.info('Welcome {}'.format(self.config.get('name')))

        if 'mount' not in self.config:
            raise error.MountNotFound('Mount must be specified in config')

        if 'state_machine' not in self.config:
            raise error.InvalidConfig('State Table must be specified in config')

        # Create our observatory, which does the bulk of the work
        self.observatory = observatory.Observatory()

        # Get our state machine
        self.state_machine = self._setup_state_machine()


    def _setup_state_machine(self):
        """
        Sets up the state machine including defining all the possible states.
        """
        # Create the machine
        machine = StateMachine(self.observatory)

        return machine


if __name__ == '__main__':
    panoptes = Panoptes()
    panoptes.logger.info("Panoptes created. Starting session")
