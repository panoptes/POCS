# -*- coding: utf-8 -*-
"""POCS is a the Panoptes Observatory Control System

* Documentation: http://panoptes-pocs.readthedocs.org/
* Source Code: https://github.com/panoptes/POCS
"""
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
        self.logger.info('Initializing panoptes unit')

        # This is mostly for debugging
        if 'name' in self.config:
            self.logger.info('Welcome {}'.format(self.config.get('name')))

        if 'mount' not in self.config:
            raise error.MountNotFound('Mount must be specified in config')

        if 'state_machine' not in self.config:
            raise error.InvalidConfig('State Table must be specified in config')            

        # Create our observatory, which does the bulk of the work
        # NOTE: Here we would pass in config options
        self.observatory = observatory.Observatory()

        # Get our state machine
        self.state_machine = self._setup_state_machine()

        
    def _setup_state_machine(self):
        """
        Sets up the state machine including defining all the possible states.
        """
        # Get the state table to be used from the config
        state_table_name = self.config.get('state_machine')

        state_table = dict()

        # Look for yaml file corresponding to state_table
        try:
            state_table_file = '{}/{}.yaml'.format('panoptes/state_table/',state_table_name)
            with open(state_table_file, 'r') as f:
                state_table = yaml.load(f.read())

            self.logger.debug('state_table:\n{}'.format(state_table))
        except:
            self.logger.error('Invalid yaml file for state_table: {}'.format(state_table_name))

        # Create the machine
        machine = StateMachine(self.observatory, state_table)

        return machine


if __name__ == '__main__':
    panoptes = Panoptes()
    panoptes.logger.info("Panoptes created. Starting session")
